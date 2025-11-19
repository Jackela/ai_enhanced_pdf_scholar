"""
Request Signing Validation Middleware
HMAC-based request signing for API authentication with replay attack prevention,
key rotation, and comprehensive security monitoring.
"""

import hashlib
import hmac
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ...config.production import ProductionConfig
from ...core.secrets_vault import ProductionSecretsManager
from ...services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class SigningAlgorithm(str, Enum):
    """Supported HMAC signing algorithms."""

    SHA256 = "sha256"
    SHA384 = "sha384"
    SHA512 = "sha512"


class RequestSigningError(Exception):
    """Request signing validation error."""

    pass


@dataclass
class SigningKey:
    """API signing key configuration."""

    key_id: str
    secret: bytes
    algorithm: SigningAlgorithm
    created_at: float
    expires_at: float | None = None
    is_active: bool = True
    usage_count: int = 0
    last_used: float | None = None
    allowed_methods: set[str] = field(
        default_factory=lambda: {"GET", "POST", "PUT", "DELETE"}
    )
    allowed_paths: set[str] = field(default_factory=set)  # Empty = allow all
    client_id: str | None = None
    description: str = ""


@dataclass
class SignatureValidationResult:
    """Result of signature validation."""

    is_valid: bool
    key_id: str | None = None
    algorithm: SigningAlgorithm | None = None
    timestamp: float | None = None
    error_message: str | None = None
    validation_time: float = 0.0


@dataclass
class RequestSignature:
    """Parsed request signature information."""

    key_id: str
    signature: str
    algorithm: SigningAlgorithm
    timestamp: float
    nonce: str | None = None
    headers_to_sign: list[str] = field(default_factory=list)


class ProductionRequestSigning:
    """
    Production request signing validation system with HMAC-based authentication,
    replay attack prevention, and key management.
    """

    def __init__(
        self,
        secrets_manager: ProductionSecretsManager | None = None,
        production_config: ProductionConfig | None = None,
        metrics_service: MetricsService | None = None,
    ) -> None:
        """Initialize request signing system."""
        self.secrets_manager = secrets_manager
        self.production_config = production_config
        self.metrics_service = metrics_service

        # Signing keys management
        self.signing_keys: dict[str, SigningKey] = {}

        # Replay attack prevention
        self.used_nonces: set[str] = set()
        self.used_signatures: dict[str, float] = {}  # signature_hash -> timestamp
        self.signature_ttl = 300  # 5 minutes
        self.clock_skew_tolerance = 60  # 1 minute

        # Performance optimization
        self.signature_cache: dict[str, SignatureValidationResult] = {}
        self.cache_ttl = 60  # Cache validation results for 1 minute

        # Security settings
        self.require_timestamp = True
        self.require_nonce = False  # Can be enabled for extra security
        self.max_timestamp_age = 300  # 5 minutes
        self.default_headers_to_sign = [
            "host",
            "date",
            "content-type",
            "content-length",
        ]

        # Load signing keys
        self._load_signing_keys()

        logger.info("Production request signing system initialized")

    def _load_signing_keys(self) -> None:
        """Load signing keys from secrets manager or configuration."""
        if self.secrets_manager:
            try:
                # In production, keys would be loaded from encrypted storage
                # This is a simplified implementation
                default_key = SigningKey(
                    key_id="default",
                    secret=b"default-signing-key-change-in-production",
                    algorithm=SigningAlgorithm.SHA256,
                    created_at=time.time(),
                    description="Default signing key",
                )
                self.signing_keys["default"] = default_key
                logger.info("Loaded signing keys from secrets manager")
            except Exception as e:
                logger.error(f"Failed to load signing keys: {e}")

        # Load from production config if available
        if self.production_config and hasattr(
            self.production_config.security, "signing_keys"
        ):
            # This would load from production configuration
            pass

    def add_signing_key(
        self,
        key_id: str,
        secret: str | bytes,
        algorithm: SigningAlgorithm = SigningAlgorithm.SHA256,
        expires_in: int | None = None,
        allowed_methods: set[str] | None = None,
        allowed_paths: set[str] | None = None,
        client_id: str | None = None,
        description: str = "",
    ) -> bool:
        """
        Add new signing key.

        Args:
            key_id: Unique key identifier
            secret: Signing secret (string or bytes)
            algorithm: HMAC algorithm to use
            expires_in: Optional expiration time in seconds
            allowed_methods: Allowed HTTP methods
            allowed_paths: Allowed URL paths (empty = all paths)
            client_id: Associated client ID
            description: Key description

        Returns:
            True if key was added successfully
        """
        try:
            if isinstance(secret, str):
                secret = secret.encode("utf-8")

            expires_at = None
            if expires_in:
                expires_at = time.time() + expires_in

            signing_key = SigningKey(
                key_id=key_id,
                secret=secret,
                algorithm=algorithm,
                created_at=time.time(),
                expires_at=expires_at,
                allowed_methods=allowed_methods or {"GET", "POST", "PUT", "DELETE"},
                allowed_paths=allowed_paths or set(),
                client_id=client_id,
                description=description,
            )

            self.signing_keys[key_id] = signing_key

            # Clear cache when keys change
            self.signature_cache.clear()

            logger.info(f"Added signing key: {key_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add signing key {key_id}: {e}")
            return False

    def rotate_signing_key(self, key_id: str, new_secret: str | bytes) -> bool:
        """
        Rotate signing key secret.

        Args:
            key_id: Key ID to rotate
            new_secret: New signing secret

        Returns:
            True if key was rotated successfully
        """
        if key_id not in self.signing_keys:
            logger.error(f"Signing key not found: {key_id}")
            return False

        try:
            if isinstance(new_secret, str):
                new_secret = new_secret.encode("utf-8")

            signing_key = self.signing_keys[key_id]
            old_secret_hash = hashlib.sha256(signing_key.secret).hexdigest()[:8]

            signing_key.secret = new_secret
            signing_key.usage_count = 0  # Reset usage count

            # Clear cache when keys change
            self.signature_cache.clear()

            new_secret_hash = hashlib.sha256(new_secret).hexdigest()[:8]
            logger.info(
                f"Rotated signing key {key_id}: {old_secret_hash} -> {new_secret_hash}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to rotate signing key {key_id}: {e}")
            return False

    def remove_signing_key(self, key_id: str) -> bool:
        """Remove signing key."""
        if key_id in self.signing_keys:
            del self.signing_keys[key_id]
            self.signature_cache.clear()
            logger.info(f"Removed signing key: {key_id}")
            return True
        return False

    def _parse_authorization_header(self, auth_header: str) -> RequestSignature | None:
        """
        Parse Authorization header for request signature.

        Expected format:
        Authorization: Signature keyId="key1", algorithm="hmac-sha256",
                      signature="base64sig", timestamp="1234567890"
        """
        try:
            if not auth_header.startswith("Signature "):
                return None

            # Parse signature parameters
            params_str = auth_header[10:]  # Remove "Signature "
            params = {}

            # Simple parameter parsing (in production, use a proper parser)
            for param in params_str.split(", "):
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value.strip('"')

            # Validate required parameters
            if "keyId" not in params or "signature" not in params:
                return None

            # Parse algorithm
            algorithm_str = params.get("algorithm", "hmac-sha256")
            if algorithm_str.startswith("hmac-"):
                algorithm = SigningAlgorithm(algorithm_str[5:])  # Remove "hmac-" prefix
            else:
                algorithm = SigningAlgorithm(algorithm_str)

            # Parse timestamp
            timestamp = None
            if "timestamp" in params:
                timestamp = float(params["timestamp"])

            # Parse headers to sign
            headers_to_sign = []
            if "headers" in params:
                headers_to_sign = [h.strip() for h in params["headers"].split(" ")]

            return RequestSignature(
                key_id=params["keyId"],
                signature=params["signature"],
                algorithm=algorithm,
                timestamp=timestamp or time.time(),
                nonce=params.get("nonce"),
                headers_to_sign=headers_to_sign or self.default_headers_to_sign,
            )

        except Exception as e:
            logger.error(f"Failed to parse authorization header: {e}")
            return None

    def _build_string_to_sign(
        self, request: Request, signature_info: RequestSignature
    ) -> str:
        """
        Build the string that should be signed.

        Args:
            request: FastAPI request object
            signature_info: Parsed signature information

        Returns:
            String to sign
        """
        parts = []

        # Add HTTP method
        parts.append(f"method: {request.method.upper()}")

        # Add URL path and query
        url_path = request.url.path
        if request.url.query:
            url_path += f"?{request.url.query}"
        parts.append(f"uri: {url_path}")

        # Add specified headers
        for header_name in signature_info.headers_to_sign:
            header_value = request.headers.get(header_name.lower())
            if header_value:
                parts.append(f"{header_name.lower()}: {header_value}")

        # Add timestamp if provided
        if signature_info.timestamp and self.require_timestamp:
            parts.append(f"timestamp: {int(signature_info.timestamp)}")

        # Add nonce if provided
        if signature_info.nonce:
            parts.append(f"nonce: {signature_info.nonce}")

        # Join with newlines
        return "\n".join(parts)

    def _compute_signature(
        self, string_to_sign: str, secret: bytes, algorithm: SigningAlgorithm
    ) -> str:
        """Compute HMAC signature for string."""
        import base64

        # Choose hash function
        if algorithm == SigningAlgorithm.SHA256:
            hash_func = hashlib.sha256
        elif algorithm == SigningAlgorithm.SHA384:
            hash_func = hashlib.sha384
        elif algorithm == SigningAlgorithm.SHA512:
            hash_func = hashlib.sha512
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        # Compute HMAC
        signature = hmac.new(secret, string_to_sign.encode("utf-8"), hash_func)

        # Return base64-encoded signature
        return base64.b64encode(signature.digest()).decode("ascii")

    async def validate_request_signature(
        self, request: Request
    ) -> SignatureValidationResult:
        """
        Validate request signature.

        Args:
            request: FastAPI request object

        Returns:
            Signature validation result
        """
        start_time = time.time()

        try:
            # Get Authorization header
            auth_header = request.headers.get("authorization")
            if not auth_header:
                return SignatureValidationResult(
                    is_valid=False,
                    error_message="Missing Authorization header",
                    validation_time=time.time() - start_time,
                )

            # Parse signature information
            signature_info = self._parse_authorization_header(auth_header)
            if not signature_info:
                return SignatureValidationResult(
                    is_valid=False,
                    error_message="Invalid signature format",
                    validation_time=time.time() - start_time,
                )

            # Check cache first
            cache_key = hashlib.sha256(auth_header.encode()).hexdigest()
            if cache_key in self.signature_cache:
                cached_result = self.signature_cache[cache_key]
                if time.time() - cached_result.timestamp < self.cache_ttl:
                    cached_result.validation_time = time.time() - start_time
                    return cached_result

            # Validate signature
            result = await self._validate_signature(request, signature_info)
            result.validation_time = time.time() - start_time

            # Cache successful validations
            if result.is_valid:
                result.timestamp = time.time()
                self.signature_cache[cache_key] = result

            # Record metrics
            if self.metrics_service:
                self.metrics_service.record_security_event(
                    "signature_validation", "info" if result.is_valid else "warning"
                )

            return result

        except Exception as e:
            logger.error(f"Signature validation error: {e}")
            return SignatureValidationResult(
                is_valid=False,
                error_message=f"Validation error: {str(e)}",
                validation_time=time.time() - start_time,
            )

    async def _validate_signature(
        self, request: Request, signature_info: RequestSignature
    ) -> SignatureValidationResult:
        """Internal signature validation logic."""

        # Check if key exists
        if signature_info.key_id not in self.signing_keys:
            return SignatureValidationResult(
                is_valid=False, error_message=f"Unknown key ID: {signature_info.key_id}"
            )

        signing_key = self.signing_keys[signature_info.key_id]

        # Check if key is active
        if not signing_key.is_active:
            return SignatureValidationResult(
                is_valid=False,
                error_message=f"Inactive key ID: {signature_info.key_id}",
            )

        # Check if key is expired
        if signing_key.expires_at and time.time() > signing_key.expires_at:
            return SignatureValidationResult(
                is_valid=False, error_message=f"Expired key ID: {signature_info.key_id}"
            )

        # Check allowed methods
        if request.method.upper() not in signing_key.allowed_methods:
            return SignatureValidationResult(
                is_valid=False,
                error_message=f"Method {request.method} not allowed for key {signature_info.key_id}",
            )

        # Check allowed paths
        if (
            signing_key.allowed_paths
            and request.url.path not in signing_key.allowed_paths
        ):
            return SignatureValidationResult(
                is_valid=False,
                error_message=f"Path {request.url.path} not allowed for key {signature_info.key_id}",
            )

        # Validate timestamp
        if self.require_timestamp and signature_info.timestamp:
            current_time = time.time()
            time_diff = abs(current_time - signature_info.timestamp)

            if time_diff > self.max_timestamp_age:
                return SignatureValidationResult(
                    is_valid=False, error_message="Request timestamp too old"
                )

            if time_diff > self.clock_skew_tolerance:
                logger.warning(
                    f"Clock skew detected: {time_diff}s for key {signature_info.key_id}"
                )

        # Check for replay attacks
        if signature_info.nonce:
            if signature_info.nonce in self.used_nonces:
                return SignatureValidationResult(
                    is_valid=False, error_message="Nonce already used (replay attack)"
                )
            self.used_nonces.add(signature_info.nonce)

            # Clean old nonces
            if len(self.used_nonces) > 10000:
                # In production, you'd implement proper nonce expiration
                self.used_nonces.clear()

        # Build string to sign
        string_to_sign = self._build_string_to_sign(request, signature_info)

        # Compute expected signature
        expected_signature = self._compute_signature(
            string_to_sign, signing_key.secret, signature_info.algorithm
        )

        # Compare signatures (timing-safe comparison)
        if not hmac.compare_digest(signature_info.signature, expected_signature):
            return SignatureValidationResult(
                is_valid=False, error_message="Invalid signature"
            )

        # Check for signature reuse
        signature_hash = hashlib.sha256(signature_info.signature.encode()).hexdigest()
        if signature_hash in self.used_signatures:
            last_used = self.used_signatures[signature_hash]
            if time.time() - last_used < self.signature_ttl:
                return SignatureValidationResult(
                    is_valid=False,
                    error_message="Signature already used (replay attack)",
                )

        # Record signature usage
        self.used_signatures[signature_hash] = time.time()

        # Clean old signatures
        if len(self.used_signatures) > 10000:
            cutoff_time = time.time() - self.signature_ttl
            self.used_signatures = {
                sig: timestamp
                for sig, timestamp in self.used_signatures.items()
                if timestamp > cutoff_time
            }

        # Update key usage statistics
        signing_key.usage_count += 1
        signing_key.last_used = time.time()

        return SignatureValidationResult(
            is_valid=True,
            key_id=signature_info.key_id,
            algorithm=signature_info.algorithm,
            timestamp=signature_info.timestamp,
        )

    def get_signing_statistics(self) -> dict[str, Any]:
        """Get signing system statistics."""
        stats = {
            "total_keys": len(self.signing_keys),
            "active_keys": sum(
                1 for key in self.signing_keys.values() if key.is_active
            ),
            "expired_keys": sum(
                1
                for key in self.signing_keys.values()
                if key.expires_at and time.time() > key.expires_at
            ),
            "cache_size": len(self.signature_cache),
            "used_nonces": len(self.used_nonces),
            "used_signatures": len(self.used_signatures),
            "key_statistics": {},
        }

        # Per-key statistics
        for key_id, key in self.signing_keys.items():
            stats["key_statistics"][key_id] = {
                "usage_count": key.usage_count,
                "last_used": key.last_used,
                "is_active": key.is_active,
                "expires_at": key.expires_at,
                "client_id": key.client_id,
                "allowed_methods": list(key.allowed_methods),
                "allowed_paths_count": len(key.allowed_paths),
            }

        return stats


class RequestSigningMiddleware:
    """FastAPI middleware for request signing validation."""

    def __init__(
        self,
        request_signing: ProductionRequestSigning,
        exempt_paths: set[str] | None = None,
    ) -> None:
        """Initialize request signing middleware."""
        self.request_signing = request_signing
        self.exempt_paths = exempt_paths or {
            "/health",
            "/docs",
            "/openapi.json",
            "/security/csp-report",
        }

    async def __call__(self, request: Request, call_next) -> Any:
        """Validate request signature before processing."""
        # Skip validation for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # Skip validation for GET requests (optional)
        if request.method == "GET":
            return await call_next(request)

        # Validate signature
        result = await self.request_signing.validate_request_signature(request)

        if not result.is_valid:
            logger.warning(
                f"Invalid signature for {request.method} {request.url.path}: {result.error_message}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid request signature",
            )

        # Add signature info to request state
        request.state.signature_key_id = result.key_id
        request.state.signature_timestamp = result.timestamp

        response = await call_next(request)
        return response


# Dependency for request signature validation
security = HTTPBearer()


def get_request_signing() -> ProductionRequestSigning:
    """Dependency to get request signing instance."""
    # This would be injected or configured in the application
    return ProductionRequestSigning()


async def validate_signature(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request_signing: ProductionRequestSigning = Depends(get_request_signing),
) -> SignatureValidationResult:
    """FastAPI dependency for signature validation."""
    result = await request_signing.validate_request_signature(request)
    if not result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=result.error_message
        )
    return result


def create_production_request_signing(
    secrets_manager: ProductionSecretsManager | None = None,
    production_config: ProductionConfig | None = None,
    metrics_service: MetricsService | None = None,
) -> ProductionRequestSigning:
    """Create production request signing instance."""
    return ProductionRequestSigning(secrets_manager, production_config, metrics_service)


def setup_request_signing_middleware(
    app,
    secrets_manager: ProductionSecretsManager | None = None,
    production_config: ProductionConfig | None = None,
    metrics_service: MetricsService | None = None,
    exempt_paths: set[str] | None = None,
) -> ProductionRequestSigning:
    """Set up request signing middleware for FastAPI application."""
    request_signing = create_production_request_signing(
        secrets_manager, production_config, metrics_service
    )

    # Add middleware
    middleware = RequestSigningMiddleware(request_signing, exempt_paths)
    app.middleware("http")(middleware)

    # Add management endpoints
    @app.get("/admin/signing/stats")
    async def get_signing_stats() -> Any:
        """Get request signing statistics."""
        return request_signing.get_signing_statistics()

    @app.post("/admin/signing/keys")
    async def add_signing_key(
        key_id: str,
        secret: str,
        algorithm: str = "sha256",
        expires_in: int | None = None,
        client_id: str | None = None,
        description: str = "",
    ) -> Any:
        """Add new signing key."""
        try:
            algorithm_enum = SigningAlgorithm(algorithm)
            result = request_signing.add_signing_key(
                key_id=key_id,
                secret=secret,
                algorithm=algorithm_enum,
                expires_in=expires_in,
                client_id=client_id,
                description=description,
            )
            return {"success": result}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.put("/admin/signing/keys/{key_id}/rotate")
    async def rotate_signing_key(key_id: str, new_secret: str) -> Any:
        """Rotate signing key secret."""
        result = request_signing.rotate_signing_key(key_id, new_secret)
        return {"success": result}

    @app.delete("/admin/signing/keys/{key_id}")
    async def remove_signing_key(key_id: str) -> Any:
        """Remove signing key."""
        result = request_signing.remove_signing_key(key_id)
        return {"success": result}

    logger.info("Request signing middleware configured")
    return request_signing
