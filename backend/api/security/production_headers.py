"""
Production Security Headers and Content Security Policy (CSP)
Comprehensive security header implementation with advanced CSP configuration,
threat detection, and monitoring integration.
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Union
from urllib.parse import urlparse
from enum import Enum

from fastapi import Request, Response
from fastapi.security import HTTPBearer

from ...config.production import ProductionConfig
from ...services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class CSPDirective(str, Enum):
    """Content Security Policy directive types."""
    DEFAULT_SRC = "default-src"
    SCRIPT_SRC = "script-src"
    STYLE_SRC = "style-src"
    IMG_SRC = "img-src"
    CONNECT_SRC = "connect-src"
    FONT_SRC = "font-src"
    OBJECT_SRC = "object-src"
    MEDIA_SRC = "media-src"
    FRAME_SRC = "frame-src"
    SANDBOX = "sandbox"
    REPORT_URI = "report-uri"
    CHILD_SRC = "child-src"
    FORM_ACTION = "form-action"
    FRAME_ANCESTORS = "frame-ancestors"
    PLUGIN_TYPES = "plugin-types"
    BASE_URI = "base-uri"
    REPORT_TO = "report-to"
    WORKER_SRC = "worker-src"
    MANIFEST_SRC = "manifest-src"
    PREFETCH_SRC = "prefetch-src"
    NAVIGATE_TO = "navigate-to"


class SecurityHeaderType(str, Enum):
    """Security header types."""
    CSP = "Content-Security-Policy"
    CSP_REPORT_ONLY = "Content-Security-Policy-Report-Only"
    HSTS = "Strict-Transport-Security"
    X_CONTENT_TYPE_OPTIONS = "X-Content-Type-Options"
    X_FRAME_OPTIONS = "X-Frame-Options"
    X_XSS_PROTECTION = "X-XSS-Protection"
    REFERRER_POLICY = "Referrer-Policy"
    PERMISSIONS_POLICY = "Permissions-Policy"
    CROSS_ORIGIN_EMBEDDER_POLICY = "Cross-Origin-Embedder-Policy"
    CROSS_ORIGIN_OPENER_POLICY = "Cross-Origin-Opener-Policy"
    CROSS_ORIGIN_RESOURCE_POLICY = "Cross-Origin-Resource-Policy"
    EXPECT_CT = "Expect-CT"
    FEATURE_POLICY = "Feature-Policy"


@dataclass
class CSPViolation:
    """CSP violation report structure."""
    blocked_uri: str
    disposition: str
    document_uri: str
    effective_directive: str
    original_policy: str
    referrer: str
    status_code: int
    violated_directive: str
    timestamp: float = field(default_factory=time.time)
    user_agent: Optional[str] = None
    source_file: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None


@dataclass
class SecurityHeaderConfig:
    """Security header configuration."""
    # Content Security Policy
    csp_enabled: bool = True
    csp_report_only: bool = False
    csp_report_uri: Optional[str] = None
    csp_directives: Dict[CSPDirective, List[str]] = field(default_factory=dict)
    
    # Security headers
    hsts_enabled: bool = True
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = True
    
    x_frame_options: str = "DENY"
    x_content_type_options: str = "nosniff"
    x_xss_protection: str = "1; mode=block"
    referrer_policy: str = "strict-origin-when-cross-origin"
    
    # Advanced headers
    cross_origin_embedder_policy: str = "require-corp"
    cross_origin_opener_policy: str = "same-origin"
    cross_origin_resource_policy: str = "same-site"
    
    # Permissions Policy
    permissions_policy: Dict[str, List[str]] = field(default_factory=lambda: {
        "camera": [],
        "microphone": [],
        "geolocation": [],
        "interest-cohort": [],
        "payment": ["self"],
        "usb": [],
        "screen-wake-lock": ["self"]
    })
    
    # Certificate Transparency
    expect_ct_enabled: bool = True
    expect_ct_max_age: int = 86400  # 1 day
    expect_ct_enforce: bool = False
    expect_ct_report_uri: Optional[str] = None
    
    # Custom headers
    custom_headers: Dict[str, str] = field(default_factory=dict)


class ProductionSecurityHeaders:
    """
    Production security headers manager with advanced CSP configuration,
    violation reporting, and threat detection.
    """
    
    def __init__(
        self,
        config: Optional[SecurityHeaderConfig] = None,
        production_config: Optional[ProductionConfig] = None,
        metrics_service: Optional[MetricsService] = None
    ):
        """Initialize security headers manager."""
        self.config = config or SecurityHeaderConfig()
        self.production_config = production_config
        self.metrics_service = metrics_service
        
        # Violation tracking
        self.violations: List[CSPViolation] = []
        self.violation_stats: Dict[str, int] = {}
        
        # Nonce management
        self.nonces: Set[str] = set()
        self.nonce_lifetime = 300  # 5 minutes
        
        # Initialize default CSP if not configured
        if not self.config.csp_directives:
            self._initialize_default_csp()
        
        logger.info("Production security headers manager initialized")
    
    def _initialize_default_csp(self):
        """Initialize default production CSP policy."""
        self.config.csp_directives = {
            CSPDirective.DEFAULT_SRC: ["'self'"],
            CSPDirective.SCRIPT_SRC: ["'self'", "'strict-dynamic'"],
            CSPDirective.STYLE_SRC: ["'self'", "'unsafe-inline'"],
            CSPDirective.IMG_SRC: ["'self'", "data:", "https:"],
            CSPDirective.CONNECT_SRC: ["'self'", "https://api.google.com"],
            CSPDirective.FONT_SRC: ["'self'", "https://fonts.googleapis.com", "https://fonts.gstatic.com"],
            CSPDirective.OBJECT_SRC: ["'none'"],
            CSPDirective.MEDIA_SRC: ["'self'"],
            CSPDirective.FRAME_SRC: ["'none'"],
            CSPDirective.BASE_URI: ["'self'"],
            CSPDirective.FORM_ACTION: ["'self'"],
            CSPDirective.FRAME_ANCESTORS: ["'none'"],
            CSPDirective.WORKER_SRC: ["'self'"],
            CSPDirective.MANIFEST_SRC: ["'self'"]
        }
    
    def generate_nonce(self) -> str:
        """Generate cryptographically secure nonce for CSP."""
        import secrets
        nonce = secrets.token_urlsafe(16)
        self.nonces.add(nonce)
        
        # Clean old nonces
        self._cleanup_old_nonces()
        
        return nonce
    
    def _cleanup_old_nonces(self):
        """Clean up old nonces to prevent memory leaks."""
        # This is simplified; in production you'd track nonce creation times
        if len(self.nonces) > 1000:
            # Keep only recent nonces (simplified cleanup)
            recent_nonces = list(self.nonces)[-500:]
            self.nonces = set(recent_nonces)
    
    def build_csp_header(self, nonce: Optional[str] = None) -> str:
        """
        Build Content Security Policy header value.
        
        Args:
            nonce: Optional nonce for script/style sources
            
        Returns:
            CSP header value
        """
        csp_parts = []
        
        for directive, sources in self.config.csp_directives.items():
            directive_sources = sources.copy()
            
            # Add nonce to script and style sources if provided
            if nonce and directive in [CSPDirective.SCRIPT_SRC, CSPDirective.STYLE_SRC]:
                directive_sources.append(f"'nonce-{nonce}'")
            
            csp_parts.append(f"{directive.value} {' '.join(directive_sources)}")
        
        # Add report URI if configured
        if self.config.csp_report_uri:
            csp_parts.append(f"report-uri {self.config.csp_report_uri}")
        
        return "; ".join(csp_parts)
    
    def build_hsts_header(self) -> str:
        """Build HTTP Strict Transport Security header."""
        hsts_parts = [f"max-age={self.config.hsts_max_age}"]
        
        if self.config.hsts_include_subdomains:
            hsts_parts.append("includeSubDomains")
        
        if self.config.hsts_preload:
            hsts_parts.append("preload")
        
        return "; ".join(hsts_parts)
    
    def build_permissions_policy_header(self) -> str:
        """Build Permissions Policy header."""
        policy_parts = []
        
        for feature, allowlist in self.config.permissions_policy.items():
            if not allowlist:
                policy_parts.append(f"{feature}=()")
            elif allowlist == ["*"]:
                policy_parts.append(f"{feature}=*")
            else:
                origins = " ".join(f'"{origin}"' if origin != "self" else "self" for origin in allowlist)
                policy_parts.append(f"{feature}=({origins})")
        
        return ", ".join(policy_parts)
    
    def build_expect_ct_header(self) -> str:
        """Build Expect-CT header."""
        ct_parts = [f"max-age={self.config.expect_ct_max_age}"]
        
        if self.config.expect_ct_enforce:
            ct_parts.append("enforce")
        
        if self.config.expect_ct_report_uri:
            ct_parts.append(f'report-uri="{self.config.expect_ct_report_uri}"')
        
        return ", ".join(ct_parts)
    
    def apply_security_headers(self, request: Request, response: Response, nonce: Optional[str] = None) -> Response:
        """
        Apply security headers to response.
        
        Args:
            request: FastAPI request object
            response: FastAPI response object
            nonce: Optional nonce for CSP
            
        Returns:
            Response with security headers applied
        """
        try:
            # Content Security Policy
            if self.config.csp_enabled:
                csp_header = self.build_csp_header(nonce)
                header_name = (SecurityHeaderType.CSP_REPORT_ONLY if self.config.csp_report_only 
                             else SecurityHeaderType.CSP)
                response.headers[header_name.value] = csp_header
            
            # HTTP Strict Transport Security (HTTPS only)
            if self.config.hsts_enabled and request.url.scheme == "https":
                response.headers[SecurityHeaderType.HSTS.value] = self.build_hsts_header()
            
            # Basic security headers
            response.headers[SecurityHeaderType.X_CONTENT_TYPE_OPTIONS.value] = self.config.x_content_type_options
            response.headers[SecurityHeaderType.X_FRAME_OPTIONS.value] = self.config.x_frame_options
            response.headers[SecurityHeaderType.X_XSS_PROTECTION.value] = self.config.x_xss_protection
            response.headers[SecurityHeaderType.REFERRER_POLICY.value] = self.config.referrer_policy
            
            # Advanced CORS headers
            response.headers[SecurityHeaderType.CROSS_ORIGIN_EMBEDDER_POLICY.value] = self.config.cross_origin_embedder_policy
            response.headers[SecurityHeaderType.CROSS_ORIGIN_OPENER_POLICY.value] = self.config.cross_origin_opener_policy
            response.headers[SecurityHeaderType.CROSS_ORIGIN_RESOURCE_POLICY.value] = self.config.cross_origin_resource_policy
            
            # Permissions Policy
            permissions_header = self.build_permissions_policy_header()
            if permissions_header:
                response.headers[SecurityHeaderType.PERMISSIONS_POLICY.value] = permissions_header
            
            # Expect-CT (HTTPS only)
            if self.config.expect_ct_enabled and request.url.scheme == "https":
                response.headers[SecurityHeaderType.EXPECT_CT.value] = self.build_expect_ct_header()
            
            # Custom headers
            for header_name, header_value in self.config.custom_headers.items():
                response.headers[header_name] = header_value
            
            # Security monitoring
            if self.metrics_service:
                self.metrics_service.record_security_event("headers_applied", "info")
            
        except Exception as e:
            logger.error(f"Failed to apply security headers: {e}")
            if self.metrics_service:
                self.metrics_service.record_security_event("header_application_error", "error")
        
        return response
    
    def handle_csp_violation(self, violation_data: Dict[str, Any]) -> None:
        """
        Handle CSP violation report.
        
        Args:
            violation_data: CSP violation report data
        """
        try:
            # Parse violation report
            violation = CSPViolation(
                blocked_uri=violation_data.get("blocked-uri", ""),
                disposition=violation_data.get("disposition", ""),
                document_uri=violation_data.get("document-uri", ""),
                effective_directive=violation_data.get("effective-directive", ""),
                original_policy=violation_data.get("original-policy", ""),
                referrer=violation_data.get("referrer", ""),
                status_code=violation_data.get("status-code", 0),
                violated_directive=violation_data.get("violated-directive", ""),
                user_agent=violation_data.get("user-agent"),
                source_file=violation_data.get("source-file"),
                line_number=violation_data.get("line-number"),
                column_number=violation_data.get("column-number")
            )
            
            # Store violation
            self.violations.append(violation)
            
            # Update statistics
            directive = violation.violated_directive
            if directive not in self.violation_stats:
                self.violation_stats[directive] = 0
            self.violation_stats[directive] += 1
            
            # Log violation
            logger.warning(f"CSP violation: {violation.violated_directive} blocked {violation.blocked_uri}")
            
            # Metrics
            if self.metrics_service:
                self.metrics_service.record_security_event("csp_violation", "warning")
            
            # Clean up old violations (keep only recent ones)
            if len(self.violations) > 10000:
                self.violations = self.violations[-5000:]  # Keep last 5000
            
        except Exception as e:
            logger.error(f"Failed to handle CSP violation: {e}")
    
    def analyze_violations(self) -> Dict[str, Any]:
        """Analyze CSP violations for patterns and threats."""
        analysis = {
            "total_violations": len(self.violations),
            "violation_stats": dict(self.violation_stats),
            "top_blocked_uris": {},
            "suspicious_patterns": [],
            "recommendations": []
        }
        
        if not self.violations:
            return analysis
        
        # Analyze blocked URIs
        uri_counts = {}
        for violation in self.violations[-1000:]:  # Last 1000 violations
            uri = violation.blocked_uri
            if uri not in uri_counts:
                uri_counts[uri] = 0
            uri_counts[uri] += 1
        
        # Top blocked URIs
        analysis["top_blocked_uris"] = dict(sorted(uri_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        
        # Detect suspicious patterns
        for violation in self.violations[-100:]:  # Recent violations
            uri = violation.blocked_uri
            
            # Suspicious patterns
            if re.match(r'^data:', uri):
                analysis["suspicious_patterns"].append(f"Data URI injection: {uri[:50]}...")
            elif re.match(r'^javascript:', uri):
                analysis["suspicious_patterns"].append(f"JavaScript injection: {uri[:50]}...")
            elif 'eval(' in uri or 'Function(' in uri:
                analysis["suspicious_patterns"].append(f"Dynamic code execution: {uri[:50]}...")
        
        # Generate recommendations
        if self.violation_stats.get("script-src", 0) > 10:
            analysis["recommendations"].append("Consider reviewing script-src policy - high violation count")
        
        if any("inline" in pattern for pattern in analysis["suspicious_patterns"]):
            analysis["recommendations"].append("Consider using nonces instead of 'unsafe-inline'")
        
        return analysis
    
    def get_security_report(self) -> Dict[str, Any]:
        """Get comprehensive security headers report."""
        return {
            "configuration": {
                "csp_enabled": self.config.csp_enabled,
                "csp_report_only": self.config.csp_report_only,
                "hsts_enabled": self.config.hsts_enabled,
                "hsts_max_age": self.config.hsts_max_age,
                "permissions_policy_features": len(self.config.permissions_policy)
            },
            "violations": self.analyze_violations(),
            "nonce_management": {
                "active_nonces": len(self.nonces),
                "nonce_lifetime": self.nonce_lifetime
            },
            "headers_applied": {
                "csp": bool(self.config.csp_directives),
                "hsts": self.config.hsts_enabled,
                "permissions_policy": bool(self.config.permissions_policy),
                "custom_headers": len(self.config.custom_headers)
            }
        }


class SecurityHeadersMiddleware:
    """
    FastAPI middleware for applying security headers.
    """
    
    def __init__(
        self,
        security_headers: ProductionSecurityHeaders,
        generate_nonces: bool = True
    ):
        """Initialize security headers middleware."""
        self.security_headers = security_headers
        self.generate_nonces = generate_nonces
    
    async def __call__(self, request: Request, call_next):
        """Apply security headers to all responses."""
        # Generate nonce for this request if enabled
        nonce = self.security_headers.generate_nonce() if self.generate_nonces else None
        
        # Add nonce to request state for template usage
        if nonce:
            request.state.csp_nonce = nonce
        
        # Process request
        response = await call_next(request)
        
        # Apply security headers
        response = self.security_headers.apply_security_headers(request, response, nonce)
        
        return response


def create_production_security_headers(
    production_config: Optional[ProductionConfig] = None,
    metrics_service: Optional[MetricsService] = None
) -> ProductionSecurityHeaders:
    """
    Create production security headers with configuration from production config.
    
    Args:
        production_config: Production configuration
        metrics_service: Metrics service for monitoring
        
    Returns:
        Configured ProductionSecurityHeaders instance
    """
    # Create security header configuration
    if production_config:
        security_config = production_config.security
        header_config = SecurityHeaderConfig(
            csp_enabled=security_config.enable_csp,
            hsts_enabled=security_config.enable_https,
            csp_directives=security_config.csp_policy,
            custom_headers=security_config.security_headers
        )
    else:
        header_config = SecurityHeaderConfig()
    
    return ProductionSecurityHeaders(
        config=header_config,
        production_config=production_config,
        metrics_service=metrics_service
    )


def setup_security_headers_middleware(
    app,
    production_config: Optional[ProductionConfig] = None,
    metrics_service: Optional[MetricsService] = None
) -> ProductionSecurityHeaders:
    """
    Set up security headers middleware for FastAPI application.
    
    Args:
        app: FastAPI application instance
        production_config: Production configuration
        metrics_service: Metrics service
        
    Returns:
        ProductionSecurityHeaders instance
    """
    # Create security headers manager
    security_headers = create_production_security_headers(production_config, metrics_service)
    
    # Add middleware
    middleware = SecurityHeadersMiddleware(security_headers)
    app.middleware("http")(middleware)
    
    # Add CSP violation reporting endpoint
    @app.post("/security/csp-report")
    async def csp_violation_report(request: Request):
        """Handle CSP violation reports."""
        try:
            violation_data = await request.json()
            if "csp-report" in violation_data:
                security_headers.handle_csp_violation(violation_data["csp-report"])
        except Exception as e:
            logger.error(f"Failed to process CSP report: {e}")
        
        return {"status": "ok"}
    
    logger.info("Security headers middleware configured")
    return security_headers