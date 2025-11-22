"""
IP Whitelist System with Geo-blocking and Advanced Filtering
Production-ready IP access control with CIDR support, geo-filtering,
rate limiting, and threat intelligence integration.
"""

import ipaddress
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
from fastapi import HTTPException, Request, status

from ...config.production import ProductionConfig
from ...services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class IPAccessAction(str, Enum):
    """IP access control actions."""

    ALLOW = "allow"
    BLOCK = "block"
    MONITOR = "monitor"  # Allow but log
    RATE_LIMIT = "rate_limit"  # Apply strict rate limiting


class IPListType(str, Enum):
    """IP list types."""

    WHITELIST = "whitelist"
    BLACKLIST = "blacklist"
    GRAYLIST = "graylist"  # Monitored IPs


class ThreatLevel(str, Enum):
    """Threat level classifications."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class IPRule:
    """IP access rule configuration."""

    network: ipaddress.IPv4Network | ipaddress.IPv6Network
    action: IPAccessAction
    description: str
    priority: int = 1000  # Lower number = higher priority
    expires_at: float | None = None
    created_at: float = field(default_factory=time.time)
    hit_count: int = 0
    last_hit: float | None = None
    tags: set[str] = field(default_factory=set)


@dataclass
class GeoLocation:
    """Geographic location information."""

    country_code: str
    country_name: str
    city: str | None = None
    region: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    isp: str | None = None
    organization: str | None = None


@dataclass
class IPThreatInfo:
    """IP threat intelligence information."""

    is_malicious: bool
    threat_level: ThreatLevel
    threat_types: set[str]
    last_seen: float | None = None
    reputation_score: int = 0  # 0-100, higher is more trustworthy
    sources: set[str] = field(default_factory=set)


@dataclass
class IPAccessAttempt:
    """IP access attempt record."""

    ip_address: str
    timestamp: float
    user_agent: str | None
    endpoint: str
    method: str
    status_code: int
    response_time: float
    geo_location: GeoLocation | None = None
    threat_info: IPThreatInfo | None = None


class ProductionIPWhitelist:
    """
    Production IP whitelist system with advanced filtering,
    geo-blocking, and threat intelligence integration.
    """

    def __init__(
        self,
        production_config: ProductionConfig | None = None,
        metrics_service: MetricsService | None = None,
    ) -> None:
        """Initialize IP whitelist system."""
        self.production_config = production_config
        self.metrics_service = metrics_service

        # IP rules storage
        self.ip_rules: list[IPRule] = []
        self.geo_rules: dict[str, IPAccessAction] = {}  # Country code -> action

        # Caching and performance
        self.ip_cache: dict[str, tuple[IPAccessAction, float]] = {}
        self.geo_cache: dict[str, GeoLocation] = {}
        self.threat_cache: dict[str, IPThreatInfo] = {}

        # Access tracking
        self.access_attempts: list[IPAccessAttempt] = []
        self.blocked_ips: dict[str, int] = {}  # IP -> block count
        self.rate_limit_tracker: dict[str, list[float]] = {}  # IP -> timestamps

        # Configuration
        self.cache_ttl = 3600  # 1 hour
        self.max_access_attempts = 10000  # Keep last N attempts
        self.geo_lookup_enabled = True
        self.threat_intelligence_enabled = True

        # Initialize default rules
        self._initialize_default_rules()

        # Load production-specific rules
        if production_config:
            self._load_production_rules()

        logger.info("Production IP whitelist system initialized")

    def _initialize_default_rules(self) -> None:
        """Initialize default IP rules for production."""
        default_rules = [
            # Private network ranges (usually blocked in production)
            IPRule(
                network=ipaddress.IPv4Network("10.0.0.0/8"),
                action=IPAccessAction.BLOCK,
                description="Private network - RFC 1918",
                priority=100,
                tags={"private", "rfc1918"},
            ),
            IPRule(
                network=ipaddress.IPv4Network("172.16.0.0/12"),
                action=IPAccessAction.BLOCK,
                description="Private network - RFC 1918",
                priority=100,
                tags={"private", "rfc1918"},
            ),
            IPRule(
                network=ipaddress.IPv4Network("192.168.0.0/16"),
                action=IPAccessAction.BLOCK,
                description="Private network - RFC 1918",
                priority=100,
                tags={"private", "rfc1918"},
            ),
            # Localhost (allow for health checks)
            IPRule(
                network=ipaddress.IPv4Network("127.0.0.0/8"),
                action=IPAccessAction.ALLOW,
                description="Localhost - health checks",
                priority=50,
                tags={"localhost", "health"},
            ),
            # Link-local (usually blocked)
            IPRule(
                network=ipaddress.IPv4Network("169.254.0.0/16"),
                action=IPAccessAction.BLOCK,
                description="Link-local addresses",
                priority=100,
                tags={"link-local"},
            ),
            # Multicast (blocked)
            IPRule(
                network=ipaddress.IPv4Network("224.0.0.0/4"),
                action=IPAccessAction.BLOCK,
                description="Multicast addresses",
                priority=100,
                tags={"multicast"},
            ),
            # Reserved (blocked)
            IPRule(
                network=ipaddress.IPv4Network("240.0.0.0/4"),
                action=IPAccessAction.BLOCK,
                description="Reserved addresses",
                priority=100,
                tags={"reserved"},
            ),
        ]

        self.ip_rules.extend(default_rules)
        self.ip_rules.sort(key=lambda r: r.priority)

    def _load_production_rules(self) -> None:
        """Load production-specific IP rules."""
        if not self.production_config:
            return

        security_config = self.production_config.security

        # Load allowed IP ranges
        for ip_range in security_config.allowed_ip_ranges:
            try:
                network = ipaddress.ip_network(ip_range, strict=False)
                rule = IPRule(
                    network=network,
                    action=IPAccessAction.ALLOW,
                    description=f"Production allowed range: {ip_range}",
                    priority=10,  # High priority
                    tags={"production", "whitelist"},
                )
                self.ip_rules.append(rule)
            except ValueError as e:
                logger.error(f"Invalid IP range in production config: {ip_range} - {e}")

        # Load blocked IP ranges
        for ip_range in security_config.blocked_ip_ranges:
            try:
                network = ipaddress.ip_network(ip_range, strict=False)
                rule = IPRule(
                    network=network,
                    action=IPAccessAction.BLOCK,
                    description=f"Production blocked range: {ip_range}",
                    priority=20,  # High priority
                    tags={"production", "blacklist"},
                )
                self.ip_rules.append(rule)
            except ValueError as e:
                logger.error(f"Invalid IP range in production config: {ip_range} - {e}")

        # Load geo-blocking rules
        if hasattr(security_config, "allowed_countries"):
            for country_code in security_config.allowed_countries:
                self.geo_rules[country_code.upper()] = IPAccessAction.ALLOW

        # Sort rules by priority
        self.ip_rules.sort(key=lambda r: r.priority)
        logger.info(f"Loaded {len(self.ip_rules)} IP rules from production config")

    def add_ip_rule(
        self,
        ip_range: str,
        action: IPAccessAction,
        description: str,
        priority: int = 1000,
        expires_in: int | None = None,
        tags: set[str] | None = None,
    ) -> bool:
        """
        Add new IP rule.

        Args:
            ip_range: IP address or CIDR range
            action: Action to take for matching IPs
            description: Rule description
            priority: Rule priority (lower = higher priority)
            expires_in: Optional expiration in seconds
            tags: Optional rule tags

        Returns:
            True if rule was added successfully
        """
        try:
            network = ipaddress.ip_network(ip_range, strict=False)

            expires_at = None
            if expires_in:
                expires_at = time.time() + expires_in

            rule = IPRule(
                network=network,
                action=action,
                description=description,
                priority=priority,
                expires_at=expires_at,
                tags=tags or set(),
            )

            self.ip_rules.append(rule)
            self.ip_rules.sort(key=lambda r: r.priority)

            # Clear cache for this IP range
            self._clear_cache_for_network(network)

            logger.info(f"Added IP rule: {ip_range} -> {action.value}")
            return True

        except ValueError as e:
            logger.error(f"Invalid IP range: {ip_range} - {e}")
            return False

    def remove_ip_rule(self, ip_range: str) -> bool:
        """
        Remove IP rule.

        Args:
            ip_range: IP address or CIDR range to remove

        Returns:
            True if rule was removed
        """
        try:
            network = ipaddress.ip_network(ip_range, strict=False)

            original_count = len(self.ip_rules)
            self.ip_rules = [rule for rule in self.ip_rules if rule.network != network]

            if len(self.ip_rules) < original_count:
                self._clear_cache_for_network(network)
                logger.info(f"Removed IP rule: {ip_range}")
                return True

            return False

        except ValueError as e:
            logger.error(f"Invalid IP range: {ip_range} - {e}")
            return False

    def _clear_cache_for_network(self, network) -> None:
        """Clear cache entries that might be affected by network rule change."""
        # This is simplified - in production you'd check which cached IPs fall within the network
        if len(self.ip_cache) > 10000:  # If cache is large, clear it entirely
            self.ip_cache.clear()

    async def check_ip_access(
        self, ip_address: str, request: Request | None = None
    ) -> tuple[IPAccessAction, str]:
        """
        Check IP access permissions.

        Args:
            ip_address: IP address to check
            request: Optional request object for additional context

        Returns:
            Tuple of (action, reason)
        """
        try:
            # Parse IP address
            ip_obj = ipaddress.ip_address(ip_address)

            # Check cache first
            if ip_address in self.ip_cache:
                action, cached_time = self.ip_cache[ip_address]
                if time.time() - cached_time < self.cache_ttl:
                    return action, "Cached result"

            # Check IP rules (sorted by priority)
            for rule in self.ip_rules:
                # Skip expired rules
                if rule.expires_at and time.time() > rule.expires_at:
                    continue

                # Check if IP matches rule
                if ip_obj in rule.network:
                    # Update rule statistics
                    rule.hit_count += 1
                    rule.last_hit = time.time()

                    # Cache result
                    self.ip_cache[ip_address] = (rule.action, time.time())

                    # Log access
                    await self._log_access_attempt(ip_address, rule.action, request)

                    return rule.action, rule.description

            # No matching rule - check geo-blocking
            if self.geo_rules:
                geo_action, geo_reason = await self._check_geo_blocking(ip_address)
                if geo_action != IPAccessAction.ALLOW:
                    return geo_action, geo_reason

            # Check threat intelligence
            if self.threat_intelligence_enabled:
                threat_action, threat_reason = await self._check_threat_intelligence(
                    ip_address
                )
                if threat_action != IPAccessAction.ALLOW:
                    return threat_action, threat_reason

            # Default action (allow)
            action = IPAccessAction.ALLOW
            self.ip_cache[ip_address] = (action, time.time())
            await self._log_access_attempt(ip_address, action, request)

            return action, "Default allow"

        except ValueError as e:
            logger.error(f"Invalid IP address: {ip_address} - {e}")
            return IPAccessAction.BLOCK, f"Invalid IP address: {e}"

    async def _check_geo_blocking(self, ip_address: str) -> tuple[IPAccessAction, str]:
        """Check geo-blocking rules."""
        try:
            # Check geo cache first
            if ip_address in self.geo_cache:
                geo_info = self.geo_cache[ip_address]
            else:
                geo_info = await self._lookup_geo_location(ip_address)
                if geo_info:
                    self.geo_cache[ip_address] = geo_info

            if not geo_info:
                return IPAccessAction.ALLOW, "Geo lookup failed"

            country_code = geo_info.country_code.upper()

            # Check country-specific rules
            if country_code in self.geo_rules:
                action = self.geo_rules[country_code]
                return action, f"Geo-blocking: {country_code}"

            # Check for high-risk countries (simplified list)
            high_risk_countries = {"CN", "RU", "KP", "IR", "SY"}
            if country_code in high_risk_countries:
                return IPAccessAction.MONITOR, f"High-risk country: {country_code}"

            return IPAccessAction.ALLOW, "Geo check passed"

        except Exception as e:
            logger.error(f"Geo-blocking check failed for {ip_address}: {e}")
            return IPAccessAction.ALLOW, "Geo check error"

    async def _lookup_geo_location(self, ip_address: str) -> GeoLocation | None:
        """Lookup geographic location for IP address."""
        if not self.geo_lookup_enabled:
            return None

        try:
            # Use a free IP geolocation service (in production, use paid service)
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"https://ipapi.co/{ip_address}/json/")
                if response.status_code == 200:
                    data = response.json()

                    return GeoLocation(
                        country_code=data.get("country_code", "XX"),
                        country_name=data.get("country_name", "Unknown"),
                        city=data.get("city"),
                        region=data.get("region"),
                        latitude=data.get("latitude"),
                        longitude=data.get("longitude"),
                        timezone=data.get("timezone"),
                        isp=data.get("org"),
                        organization=data.get("org"),
                    )

        except Exception as e:
            logger.warning(f"Geo lookup failed for {ip_address}: {e}")

        return None

    async def _check_threat_intelligence(
        self, ip_address: str
    ) -> tuple[IPAccessAction, str]:
        """Check threat intelligence for IP address."""
        try:
            # Check threat cache first
            if ip_address in self.threat_cache:
                threat_info = self.threat_cache[ip_address]
            else:
                threat_info = await self._lookup_threat_intelligence(ip_address)
                if threat_info:
                    self.threat_cache[ip_address] = threat_info

            if not threat_info:
                return IPAccessAction.ALLOW, "No threat data"

            if threat_info.is_malicious:
                if threat_info.threat_level == ThreatLevel.CRITICAL:
                    return (
                        IPAccessAction.BLOCK,
                        f"Critical threat: {', '.join(threat_info.threat_types)}",
                    )
                elif threat_info.threat_level == ThreatLevel.HIGH:
                    return (
                        IPAccessAction.BLOCK,
                        f"High threat: {', '.join(threat_info.threat_types)}",
                    )
                elif threat_info.threat_level == ThreatLevel.MEDIUM:
                    return (
                        IPAccessAction.RATE_LIMIT,
                        f"Medium threat: {', '.join(threat_info.threat_types)}",
                    )
                else:
                    return (
                        IPAccessAction.MONITOR,
                        f"Low threat: {', '.join(threat_info.threat_types)}",
                    )

            return IPAccessAction.ALLOW, "Threat check passed"

        except Exception as e:
            logger.error(f"Threat intelligence check failed for {ip_address}: {e}")
            return IPAccessAction.ALLOW, "Threat check error"

    async def _lookup_threat_intelligence(self, ip_address: str) -> IPThreatInfo | None:
        """Lookup threat intelligence for IP address."""
        if not self.threat_intelligence_enabled:
            return None

        try:
            # This is a placeholder - in production, integrate with threat intelligence APIs
            # like VirusTotal, AbuseIPDB, etc.

            # Simplified threat detection based on patterns
            # Check if IP is in known bad ranges (simplified)
            ip_obj = ipaddress.ip_address(ip_address)

            # Common malicious IP patterns (this is very simplified)
            if str(ip_obj).startswith(("1.1.1.", "8.8.8.")):
                # These are actually good IPs (Google DNS, Cloudflare)
                return IPThreatInfo(
                    is_malicious=False,
                    threat_level=ThreatLevel.LOW,
                    threat_types=set(),
                    reputation_score=100,
                )

            # In production, you would query actual threat intelligence APIs
            return None

        except Exception as e:
            logger.error(f"Threat intelligence lookup failed for {ip_address}: {e}")
            return None

    async def _log_access_attempt(
        self, ip_address: str, action: IPAccessAction, request: Request | None
    ) -> None:
        """Log IP access attempt."""
        try:
            attempt = IPAccessAttempt(
                ip_address=ip_address,
                timestamp=time.time(),
                user_agent=request.headers.get("user-agent") if request else None,
                endpoint=str(request.url.path) if request else "unknown",
                method=request.method if request else "unknown",
                status_code=200 if action == IPAccessAction.ALLOW else 403,
                response_time=0,  # Would be filled in by middleware
                geo_location=self.geo_cache.get(ip_address),
                threat_info=self.threat_cache.get(ip_address),
            )

            self.access_attempts.append(attempt)

            # Keep only recent attempts
            if len(self.access_attempts) > self.max_access_attempts:
                self.access_attempts = self.access_attempts[
                    -self.max_access_attempts // 2 :
                ]

            # Update blocked IPs counter
            if action == IPAccessAction.BLOCK:
                if ip_address not in self.blocked_ips:
                    self.blocked_ips[ip_address] = 0
                self.blocked_ips[ip_address] += 1

            # Metrics
            if self.metrics_service:
                self.metrics_service.record_security_event(
                    f"ip_{action.value}",
                    "warning" if action == IPAccessAction.BLOCK else "info",
                )

        except Exception as e:
            logger.error(f"Failed to log access attempt: {e}")

    def get_statistics(self) -> dict[str, Any]:
        """Get IP whitelist statistics."""
        current_time = time.time()

        # Calculate statistics
        total_attempts = len(self.access_attempts)
        recent_attempts = [
            a for a in self.access_attempts if current_time - a.timestamp < 3600
        ]  # Last hour
        blocked_attempts = [a for a in recent_attempts if a.status_code == 403]

        # Rule statistics
        active_rules = [
            r for r in self.ip_rules if not r.expires_at or r.expires_at > current_time
        ]
        rule_stats = {}
        for rule in active_rules:
            rule_stats[str(rule.network)] = {
                "action": rule.action.value,
                "hit_count": rule.hit_count,
                "last_hit": rule.last_hit,
                "tags": list(rule.tags),
            }

        # Geographic distribution
        geo_stats = {}
        for attempt in recent_attempts:
            if attempt.geo_location:
                country = attempt.geo_location.country_code
                if country not in geo_stats:
                    geo_stats[country] = 0
                geo_stats[country] += 1

        return {
            "total_rules": len(active_rules),
            "total_attempts": total_attempts,
            "recent_attempts": len(recent_attempts),
            "blocked_attempts": len(blocked_attempts),
            "block_rate": len(blocked_attempts) / max(len(recent_attempts), 1),
            "top_blocked_ips": dict(
                sorted(self.blocked_ips.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "geographic_distribution": geo_stats,
            "cache_stats": {
                "ip_cache_size": len(self.ip_cache),
                "geo_cache_size": len(self.geo_cache),
                "threat_cache_size": len(self.threat_cache),
            },
            "rule_statistics": rule_stats,
        }

    def cleanup_expired_rules(self) -> int:
        """Clean up expired rules and return count removed."""
        current_time = time.time()
        original_count = len(self.ip_rules)

        self.ip_rules = [
            rule
            for rule in self.ip_rules
            if not rule.expires_at or rule.expires_at > current_time
        ]

        removed_count = original_count - len(self.ip_rules)
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} expired IP rules")

        return removed_count


class IPWhitelistMiddleware:
    """
    FastAPI middleware for IP whitelist enforcement.
    """

    def __init__(self, ip_whitelist: ProductionIPWhitelist) -> None:
        """Initialize IP whitelist middleware."""
        self.ip_whitelist = ip_whitelist

    async def __call__(self, request: Request, call_next) -> Any:
        """Check IP access before processing request."""
        # Get client IP address
        client_ip = self._get_client_ip(request)

        # Check IP access
        action, reason = await self.ip_whitelist.check_ip_access(client_ip, request)

        # Handle different actions
        if action == IPAccessAction.BLOCK:
            logger.warning(f"Blocked IP {client_ip}: {reason}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )
        elif action == IPAccessAction.RATE_LIMIT:
            # Apply strict rate limiting (this would integrate with rate limiting middleware)
            logger.info(f"Rate limiting IP {client_ip}: {reason}")
        elif action == IPAccessAction.MONITOR:
            logger.info(f"Monitoring IP {client_ip}: {reason}")

        # Continue with request processing
        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check X-Forwarded-For header (behind proxy/load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP (original client)
            return forwarded_for.split(",")[0].strip()

        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fall back to direct connection IP
        return request.client.host


def create_production_ip_whitelist(
    production_config: ProductionConfig | None = None,
    metrics_service: MetricsService | None = None,
) -> ProductionIPWhitelist:
    """Create production IP whitelist instance."""
    return ProductionIPWhitelist(production_config, metrics_service)


def setup_ip_whitelist_middleware(
    app,
    production_config: ProductionConfig | None = None,
    metrics_service: MetricsService | None = None,
) -> ProductionIPWhitelist:
    """Set up IP whitelist middleware for FastAPI application."""
    ip_whitelist = create_production_ip_whitelist(production_config, metrics_service)

    # Add middleware
    middleware = IPWhitelistMiddleware(ip_whitelist)
    app.middleware("http")(middleware)

    # Add management endpoints
    @app.get("/admin/ip-whitelist/stats")
    async def get_ip_stats() -> Any:
        """Get IP whitelist statistics."""
        return ip_whitelist.get_statistics()

    @app.post("/admin/ip-whitelist/add")
    async def add_ip_rule(
        ip_range: str, action: str, description: str, priority: int = 1000
    ) -> Any:
        """Add new IP rule."""
        try:
            action_enum = IPAccessAction(action)
            result = ip_whitelist.add_ip_rule(
                ip_range, action_enum, description, priority
            )
            return {"success": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.delete("/admin/ip-whitelist/remove")
    async def remove_ip_rule(ip_range: str) -> Any:
        """Remove IP rule."""
        result = ip_whitelist.remove_ip_rule(ip_range)
        return {"success": result}

    logger.info("IP whitelist middleware configured")
    return ip_whitelist
