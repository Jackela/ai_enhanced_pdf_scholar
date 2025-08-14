"""
Security Headers Middleware
Comprehensive security headers implementation for enterprise production environments.
Provides defense-in-depth with CSP, HSTS, and other critical security headers.
"""

import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.api.auth.dependencies import get_admin_user
from backend.api.auth.models import UserModel

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security.headers")


class Environment(str, Enum):
    """Application environment types."""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class CSPDirective(str, Enum):
    """Content Security Policy directives."""
    DEFAULT_SRC = "default-src"
    SCRIPT_SRC = "script-src"
    STYLE_SRC = "style-src"
    IMG_SRC = "img-src"
    FONT_SRC = "font-src"
    CONNECT_SRC = "connect-src"
    MEDIA_SRC = "media-src"
    OBJECT_SRC = "object-src"
    FRAME_SRC = "frame-src"
    FRAME_ANCESTORS = "frame-ancestors"
    BASE_URI = "base-uri"
    FORM_ACTION = "form-action"
    MANIFEST_SRC = "manifest-src"
    WORKER_SRC = "worker-src"
    CHILD_SRC = "child-src"
    PREFETCH_SRC = "prefetch-src"
    SCRIPT_SRC_ELEM = "script-src-elem"
    SCRIPT_SRC_ATTR = "script-src-attr"
    STYLE_SRC_ELEM = "style-src-elem"
    STYLE_SRC_ATTR = "style-src-attr"
    REPORT_URI = "report-uri"
    REPORT_TO = "report-to"
    REQUIRE_TRUSTED_TYPES = "require-trusted-types-for"
    TRUSTED_TYPES = "trusted-types"
    UPGRADE_INSECURE_REQUESTS = "upgrade-insecure-requests"
    BLOCK_ALL_MIXED_CONTENT = "block-all-mixed-content"


class CSPSource:
    """Common CSP source values."""
    SELF = "'self'"
    NONE = "'none'"
    UNSAFE_INLINE = "'unsafe-inline'"
    UNSAFE_EVAL = "'unsafe-eval'"
    UNSAFE_HASHES = "'unsafe-hashes'"
    STRICT_DYNAMIC = "'strict-dynamic'"
    REPORT_SAMPLE = "'report-sample'"
    DATA = "data:"
    BLOB = "blob:"
    FILESYSTEM = "filesystem:"
    HTTPS = "https:"
    WSS = "wss:"

    @staticmethod
    def nonce(value: str) -> str:
        """Generate nonce source."""
        return f"'nonce-{value}'"

    @staticmethod
    def sha256(hash_value: str) -> str:
        """Generate SHA256 hash source."""
        return f"'sha256-{hash_value}'"


class SecurityHeadersConfig:
    """Configuration for security headers."""

    def __init__(self, environment: Optional[Environment] = None):
        """Initialize security headers configuration."""
        self.environment = environment or self._detect_environment()
        self.nonce_enabled = self.environment != Environment.DEVELOPMENT
        self.csp_report_only = self.environment in [Environment.DEVELOPMENT, Environment.STAGING]
        self.strict_transport_security_enabled = self.environment in [Environment.STAGING, Environment.PRODUCTION]
        self.enable_reporting = self.environment != Environment.TESTING

        # Load configuration from environment
        self._load_from_environment()

    def _detect_environment(self) -> Environment:
        """Detect current environment from environment variables."""
        env_value = os.getenv("ENVIRONMENT", "development").lower()

        env_mapping = {
            "dev": Environment.DEVELOPMENT,
            "development": Environment.DEVELOPMENT,
            "test": Environment.TESTING,
            "testing": Environment.TESTING,
            "stage": Environment.STAGING,
            "staging": Environment.STAGING,
            "prod": Environment.PRODUCTION,
            "production": Environment.PRODUCTION,
        }

        return env_mapping.get(env_value, Environment.DEVELOPMENT)

    def _load_from_environment(self) -> None:
        """Load configuration from environment variables."""
        # CSP configuration
        self.csp_enabled = os.getenv("CSP_ENABLED", "true").lower() == "true"
        self.csp_report_uri = os.getenv("CSP_REPORT_URI", "/api/security/csp-report")
        self.csp_report_to_group = os.getenv("CSP_REPORT_TO_GROUP", "csp-endpoint")

        # HSTS configuration
        self.hsts_max_age = int(os.getenv("HSTS_MAX_AGE", "31536000"))  # 1 year default
        self.hsts_include_subdomains = os.getenv("HSTS_INCLUDE_SUBDOMAINS", "true").lower() == "true"
        self.hsts_preload = os.getenv("HSTS_PRELOAD", "false").lower() == "true"

        # Frame options
        self.frame_options = os.getenv("X_FRAME_OPTIONS", "DENY")

        # Referrer policy
        self.referrer_policy = os.getenv("REFERRER_POLICY", "strict-origin-when-cross-origin")

        # Permissions policy
        self.permissions_policy_enabled = os.getenv("PERMISSIONS_POLICY_ENABLED", "true").lower() == "true"

        # Cookie security
        self.secure_cookies = self.environment in [Environment.STAGING, Environment.PRODUCTION]
        self.cookie_samesite = os.getenv("COOKIE_SAMESITE", "lax" if self.environment == Environment.DEVELOPMENT else "strict")

        # Certificate transparency
        self.expect_ct_enabled = self.environment == Environment.PRODUCTION
        self.expect_ct_max_age = int(os.getenv("EXPECT_CT_MAX_AGE", "86400"))  # 24 hours
        self.expect_ct_enforce = os.getenv("EXPECT_CT_ENFORCE", "false").lower() == "true"
        self.expect_ct_report_uri = os.getenv("EXPECT_CT_REPORT_URI", "/api/security/ct-report")

        # Cross-origin policies
        self.cross_origin_embedder_policy = os.getenv("COEP", "require-corp" if self.environment == Environment.PRODUCTION else "unsafe-none")
        self.cross_origin_opener_policy = os.getenv("COOP", "same-origin-allow-popups")
        self.cross_origin_resource_policy = os.getenv("CORP", "same-site")

    def get_csp_policy(self, nonce: Optional[str] = None) -> Dict[CSPDirective, List[str]]:
        """Get Content Security Policy configuration for current environment."""
        if self.environment == Environment.DEVELOPMENT:
            return self._get_development_csp(nonce)
        elif self.environment == Environment.TESTING:
            return self._get_testing_csp(nonce)
        elif self.environment == Environment.STAGING:
            return self._get_staging_csp(nonce)
        else:  # PRODUCTION
            return self._get_production_csp(nonce)

    def _get_development_csp(self, nonce: Optional[str] = None) -> Dict[CSPDirective, List[str]]:
        """Get CSP for development environment (relaxed for debugging)."""
        policy = {
            CSPDirective.DEFAULT_SRC: [CSPSource.SELF],
            CSPDirective.SCRIPT_SRC: [
                CSPSource.SELF,
                CSPSource.UNSAFE_INLINE,  # Allow for dev tools
                CSPSource.UNSAFE_EVAL,    # Allow for hot reload
                "http://localhost:*",
                "http://127.0.0.1:*",
                "https://cdn.jsdelivr.net",  # For libraries
            ],
            CSPDirective.STYLE_SRC: [
                CSPSource.SELF,
                CSPSource.UNSAFE_INLINE,  # Allow for dev tools
                "https://fonts.googleapis.com",
                "https://cdn.jsdelivr.net",
            ],
            CSPDirective.IMG_SRC: [
                CSPSource.SELF,
                CSPSource.DATA,
                CSPSource.BLOB,
                "http://localhost:*",
                "http://127.0.0.1:*",
            ],
            CSPDirective.FONT_SRC: [
                CSPSource.SELF,
                CSPSource.DATA,
                "https://fonts.gstatic.com",
            ],
            CSPDirective.CONNECT_SRC: [
                CSPSource.SELF,
                "http://localhost:*",
                "http://127.0.0.1:*",
                "ws://localhost:*",
                "ws://127.0.0.1:*",
                "https://*.googleapis.com",  # For AI services
            ],
            CSPDirective.FRAME_ANCESTORS: [CSPSource.NONE],
            CSPDirective.BASE_URI: [CSPSource.SELF],
            CSPDirective.FORM_ACTION: [CSPSource.SELF],
        }

        if self.enable_reporting:
            policy[CSPDirective.REPORT_URI] = [self.csp_report_uri]

        return policy

    def _get_testing_csp(self, nonce: Optional[str] = None) -> Dict[CSPDirective, List[str]]:
        """Get CSP for testing environment."""
        policy = {
            CSPDirective.DEFAULT_SRC: [CSPSource.SELF],
            CSPDirective.SCRIPT_SRC: [
                CSPSource.SELF,
                CSPSource.nonce(nonce) if nonce else CSPSource.UNSAFE_INLINE,
            ],
            CSPDirective.STYLE_SRC: [
                CSPSource.SELF,
                CSPSource.nonce(nonce) if nonce else CSPSource.UNSAFE_INLINE,
            ],
            CSPDirective.IMG_SRC: [CSPSource.SELF, CSPSource.DATA],
            CSPDirective.FONT_SRC: [CSPSource.SELF],
            CSPDirective.CONNECT_SRC: [CSPSource.SELF],
            CSPDirective.FRAME_ANCESTORS: [CSPSource.NONE],
            CSPDirective.BASE_URI: [CSPSource.SELF],
            CSPDirective.FORM_ACTION: [CSPSource.SELF],
        }

        return policy

    def _get_staging_csp(self, nonce: Optional[str] = None) -> Dict[CSPDirective, List[str]]:
        """Get CSP for staging environment (production-like but with reporting)."""
        policy = {
            CSPDirective.DEFAULT_SRC: [CSPSource.NONE],
            CSPDirective.SCRIPT_SRC: [
                CSPSource.SELF,
                CSPSource.nonce(nonce) if nonce else "",
                "https://cdn.jsdelivr.net",
            ],
            CSPDirective.STYLE_SRC: [
                CSPSource.SELF,
                CSPSource.nonce(nonce) if nonce else "",
                "https://fonts.googleapis.com",
            ],
            CSPDirective.IMG_SRC: [
                CSPSource.SELF,
                CSPSource.DATA,
                CSPSource.HTTPS,
            ],
            CSPDirective.FONT_SRC: [
                CSPSource.SELF,
                "https://fonts.gstatic.com",
            ],
            CSPDirective.CONNECT_SRC: [
                CSPSource.SELF,
                CSPSource.HTTPS,
                CSPSource.WSS,
            ],
            CSPDirective.MEDIA_SRC: [CSPSource.SELF],
            CSPDirective.OBJECT_SRC: [CSPSource.NONE],
            CSPDirective.FRAME_SRC: [CSPSource.NONE],
            CSPDirective.FRAME_ANCESTORS: [CSPSource.NONE],
            CSPDirective.BASE_URI: [CSPSource.SELF],
            CSPDirective.FORM_ACTION: [CSPSource.SELF],
            CSPDirective.MANIFEST_SRC: [CSPSource.SELF],
            CSPDirective.WORKER_SRC: [CSPSource.SELF],
            CSPDirective.UPGRADE_INSECURE_REQUESTS: [""],
        }

        if self.enable_reporting:
            policy[CSPDirective.REPORT_URI] = [self.csp_report_uri]
            policy[CSPDirective.REPORT_TO] = [self.csp_report_to_group]

        # Remove empty nonce if not provided
        if nonce is None:
            policy[CSPDirective.SCRIPT_SRC] = [s for s in policy[CSPDirective.SCRIPT_SRC] if s]
            policy[CSPDirective.STYLE_SRC] = [s for s in policy[CSPDirective.STYLE_SRC] if s]

        return policy

    def _get_production_csp(self, nonce: Optional[str] = None) -> Dict[CSPDirective, List[str]]:
        """Get CSP for production environment (maximum security)."""
        policy = {
            CSPDirective.DEFAULT_SRC: [CSPSource.NONE],
            CSPDirective.SCRIPT_SRC: [
                CSPSource.SELF,
                CSPSource.nonce(nonce) if nonce else "",
                CSPSource.STRICT_DYNAMIC,
            ],
            CSPDirective.STYLE_SRC: [
                CSPSource.SELF,
                CSPSource.nonce(nonce) if nonce else "",
            ],
            CSPDirective.IMG_SRC: [
                CSPSource.SELF,
                CSPSource.DATA,
                CSPSource.HTTPS,
            ],
            CSPDirective.FONT_SRC: [
                CSPSource.SELF,
                "https://fonts.gstatic.com",
            ],
            CSPDirective.CONNECT_SRC: [
                CSPSource.SELF,
                CSPSource.HTTPS,
                CSPSource.WSS,
            ],
            CSPDirective.MEDIA_SRC: [CSPSource.SELF],
            CSPDirective.OBJECT_SRC: [CSPSource.NONE],
            CSPDirective.FRAME_SRC: [CSPSource.NONE],
            CSPDirective.FRAME_ANCESTORS: [CSPSource.NONE],
            CSPDirective.BASE_URI: [CSPSource.NONE],
            CSPDirective.FORM_ACTION: [CSPSource.SELF],
            CSPDirective.MANIFEST_SRC: [CSPSource.SELF],
            CSPDirective.WORKER_SRC: [CSPSource.SELF],
            CSPDirective.CHILD_SRC: [CSPSource.SELF],
            CSPDirective.PREFETCH_SRC: [CSPSource.SELF],
            CSPDirective.UPGRADE_INSECURE_REQUESTS: [""],
            CSPDirective.BLOCK_ALL_MIXED_CONTENT: [""],
        }

        # Add Trusted Types for XSS protection
        if os.getenv("CSP_TRUSTED_TYPES", "false").lower() == "true":
            policy[CSPDirective.REQUIRE_TRUSTED_TYPES] = ["'script'"]
            policy[CSPDirective.TRUSTED_TYPES] = ["default", "dompurify"]

        if self.enable_reporting:
            policy[CSPDirective.REPORT_URI] = [self.csp_report_uri]
            policy[CSPDirective.REPORT_TO] = [self.csp_report_to_group]

        # Remove empty nonce if not provided
        if nonce is None:
            policy[CSPDirective.SCRIPT_SRC] = [s for s in policy[CSPDirective.SCRIPT_SRC] if s]
            policy[CSPDirective.STYLE_SRC] = [s for s in policy[CSPDirective.STYLE_SRC] if s]

        return policy

    def get_permissions_policy(self) -> Dict[str, List[str]]:
        """Get Permissions Policy (Feature Policy) configuration."""
        if self.environment == Environment.DEVELOPMENT:
            # Relaxed for development
            return {
                "accelerometer": ["*"],
                "ambient-light-sensor": ["*"],
                "autoplay": ["*"],
                "battery": ["*"],
                "camera": ["self"],
                "display-capture": ["self"],
                "document-domain": ["*"],
                "encrypted-media": ["*"],
                "fullscreen": ["*"],
                "geolocation": ["self"],
                "gyroscope": ["*"],
                "magnetometer": ["*"],
                "microphone": ["self"],
                "midi": ["*"],
                "payment": ["self"],
                "picture-in-picture": ["*"],
                "publickey-credentials-get": ["self"],
                "screen-wake-lock": ["*"],
                "sync-xhr": ["*"],
                "usb": ["self"],
                "web-share": ["self"],
                "xr-spatial-tracking": ["self"],
            }
        else:
            # Restrictive for staging/production
            return {
                "accelerometer": [],
                "ambient-light-sensor": [],
                "autoplay": ["self"],
                "battery": [],
                "camera": [],
                "display-capture": [],
                "document-domain": [],
                "encrypted-media": ["self"],
                "fullscreen": ["self"],
                "geolocation": [],
                "gyroscope": [],
                "magnetometer": [],
                "microphone": [],
                "midi": [],
                "payment": [],
                "picture-in-picture": ["self"],
                "publickey-credentials-get": ["self"],
                "screen-wake-lock": [],
                "sync-xhr": [],
                "usb": [],
                "web-share": [],
                "xr-spatial-tracking": [],
            }


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add comprehensive security headers to responses."""

    def __init__(self, app: ASGIApp, config: Optional[SecurityHeadersConfig] = None):
        """Initialize security headers middleware."""
        super().__init__(app)
        self.config = config or SecurityHeadersConfig()
        self._csp_violations: List[Dict[str, Any]] = []
        self._ct_violations: List[Dict[str, Any]] = []

        logger.info(f"Security headers middleware initialized for {self.config.environment.value} environment")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response."""
        # Generate nonce for this request if enabled
        nonce = None
        if self.config.nonce_enabled and self.config.csp_enabled:
            nonce = self._generate_nonce()
            # Store nonce in request state for use in templates
            request.state.csp_nonce = nonce

        # Process the request
        response = await call_next(request)

        # Add security headers
        self._add_security_headers(response, request, nonce)

        return response

    def _generate_nonce(self) -> str:
        """Generate a cryptographically secure nonce."""
        return secrets.token_urlsafe(32)

    def _add_security_headers(self, response: Response, request: Request, nonce: Optional[str] = None) -> None:
        """Add all security headers to the response."""
        # Content Security Policy
        if self.config.csp_enabled:
            self._add_csp_header(response, nonce)

        # HTTP Strict Transport Security (HSTS)
        if self.config.strict_transport_security_enabled:
            self._add_hsts_header(response)

        # X-Frame-Options
        response.headers["X-Frame-Options"] = self.config.frame_options

        # X-Content-Type-Options
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-XSS-Protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer-Policy
        response.headers["Referrer-Policy"] = self.config.referrer_policy

        # Permissions-Policy (Feature-Policy)
        if self.config.permissions_policy_enabled:
            self._add_permissions_policy_header(response)

        # Certificate Transparency
        if self.config.expect_ct_enabled:
            self._add_expect_ct_header(response)

        # Cross-Origin policies
        self._add_cross_origin_headers(response)

        # Report-To header for reporting API
        if self.config.enable_reporting:
            self._add_report_to_header(response)

        # Clear-Site-Data for logout endpoints
        if request.url.path in ["/api/auth/logout", "/api/auth/signout"]:
            response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'

        # Security.txt support
        if request.url.path == "/.well-known/security.txt":
            self._add_security_txt_headers(response)

        # Add custom security headers for API responses
        if request.url.path.startswith("/api/"):
            response.headers["X-API-Version"] = "2.0.0"
            response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", self._generate_request_id())

    def _add_csp_header(self, response: Response, nonce: Optional[str] = None) -> None:
        """Add Content Security Policy header."""
        policy = self.config.get_csp_policy(nonce)

        # Build CSP string
        csp_parts = []
        for directive, sources in policy.items():
            if sources:
                sources_str = " ".join(s for s in sources if s)  # Filter out empty strings
                if sources_str:  # Only add if there are actual sources
                    csp_parts.append(f"{directive.value} {sources_str}")
                else:
                    csp_parts.append(directive.value)

        csp_string = "; ".join(csp_parts)

        # Use Report-Only mode if configured
        if self.config.csp_report_only:
            response.headers["Content-Security-Policy-Report-Only"] = csp_string
        else:
            response.headers["Content-Security-Policy"] = csp_string

    def _add_hsts_header(self, response: Response) -> None:
        """Add HTTP Strict Transport Security header."""
        hsts_parts = [f"max-age={self.config.hsts_max_age}"]

        if self.config.hsts_include_subdomains:
            hsts_parts.append("includeSubDomains")

        if self.config.hsts_preload:
            hsts_parts.append("preload")

        response.headers["Strict-Transport-Security"] = "; ".join(hsts_parts)

    def _add_permissions_policy_header(self, response: Response) -> None:
        """Add Permissions-Policy header."""
        policy = self.config.get_permissions_policy()

        policy_parts = []
        for feature, allowlist in policy.items():
            if not allowlist:
                policy_parts.append(f"{feature}=()")
            elif allowlist == ["*"]:
                policy_parts.append(f"{feature}=*")
            else:
                origins = " ".join(f'"{origin}"' if origin != "self" else origin for origin in allowlist)
                policy_parts.append(f"{feature}=({origins})")

        response.headers["Permissions-Policy"] = ", ".join(policy_parts)

    def _add_expect_ct_header(self, response: Response) -> None:
        """Add Expect-CT header for Certificate Transparency."""
        ct_parts = [f"max-age={self.config.expect_ct_max_age}"]

        if self.config.expect_ct_enforce:
            ct_parts.append("enforce")

        if self.config.expect_ct_report_uri:
            ct_parts.append(f'report-uri="{self.config.expect_ct_report_uri}"')

        response.headers["Expect-CT"] = ", ".join(ct_parts)

    def _add_cross_origin_headers(self, response: Response) -> None:
        """Add Cross-Origin headers."""
        response.headers["Cross-Origin-Embedder-Policy"] = self.config.cross_origin_embedder_policy
        response.headers["Cross-Origin-Opener-Policy"] = self.config.cross_origin_opener_policy
        response.headers["Cross-Origin-Resource-Policy"] = self.config.cross_origin_resource_policy

    def _add_report_to_header(self, response: Response) -> None:
        """Add Report-To header for Reporting API."""
        report_endpoints = [
            {
                "group": self.config.csp_report_to_group,
                "max_age": 86400,
                "endpoints": [{"url": self.config.csp_report_uri}],
                "include_subdomains": True,
            }
        ]

        if self.config.expect_ct_enabled and self.config.expect_ct_report_uri:
            report_endpoints.append({
                "group": "ct-endpoint",
                "max_age": 86400,
                "endpoints": [{"url": self.config.expect_ct_report_uri}],
                "include_subdomains": True,
            })

        response.headers["Report-To"] = json.dumps(report_endpoints)

    def _add_security_txt_headers(self, response: Response) -> None:
        """Add headers for security.txt responses."""
        response.headers["Content-Type"] = "text/plain; charset=utf-8"
        response.headers["Cache-Control"] = "max-age=86400"  # Cache for 24 hours

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        return secrets.token_hex(16)

    def _set_secure_cookie_attributes(self, response: Response) -> None:
        """Set secure attributes for cookies."""
        if not self.config.secure_cookies:
            return

        # Parse and modify Set-Cookie headers
        set_cookie_headers = response.headers.getlist("set-cookie")
        if not set_cookie_headers:
            return

        new_cookies = []
        for cookie_header in set_cookie_headers:
            cookie_parts = cookie_header.split(";")
            cookie_name_value = cookie_parts[0]

            # Parse existing attributes
            attributes = {}
            for part in cookie_parts[1:]:
                if "=" in part:
                    key, value = part.strip().split("=", 1)
                    attributes[key.lower()] = value
                else:
                    attributes[part.strip().lower()] = True

            # Add security attributes
            attributes["secure"] = True
            attributes["httponly"] = True
            attributes["samesite"] = self.config.cookie_samesite

            # Use cookie prefixes for additional security
            if cookie_name_value.startswith("session") or cookie_name_value.startswith("auth"):
                if "domain" not in attributes:
                    # Use __Host- prefix (requires Secure, no Domain, Path=/)
                    cookie_name_value = f"__Host-{cookie_name_value}"
                    attributes["path"] = "/"
                    attributes.pop("domain", None)
                else:
                    # Use __Secure- prefix (requires Secure)
                    cookie_name_value = f"__Secure-{cookie_name_value}"

            # Rebuild cookie header
            new_cookie = cookie_name_value
            for key, value in attributes.items():
                if value is True:
                    new_cookie += f"; {key.capitalize()}"
                else:
                    new_cookie += f"; {key.capitalize()}={value}"

            new_cookies.append(new_cookie)

        # Replace Set-Cookie headers
        del response.headers["set-cookie"]
        for cookie in new_cookies:
            response.headers.append("set-cookie", cookie)


class CSPViolationReport:
    """CSP violation report handler."""

    def __init__(self, max_reports: int = 1000):
        """Initialize CSP violation report handler."""
        self.max_reports = max_reports
        self.reports: List[Dict[str, Any]] = []
        self.report_counts: Dict[str, int] = {}

    def add_report(self, report: Dict[str, Any]) -> None:
        """Add a CSP violation report."""
        # Extract key fields for deduplication
        blocked_uri = report.get("blocked-uri", "")
        violated_directive = report.get("violated-directive", "")
        document_uri = report.get("document-uri", "")

        # Create a unique key for this type of violation
        violation_key = f"{document_uri}|{violated_directive}|{blocked_uri}"

        # Track violation counts
        self.report_counts[violation_key] = self.report_counts.get(violation_key, 0) + 1

        # Store report with metadata
        report["timestamp"] = datetime.utcnow().isoformat()
        report["count"] = self.report_counts[violation_key]

        # Add to reports list (with size limit)
        self.reports.append(report)
        if len(self.reports) > self.max_reports:
            self.reports.pop(0)

        # Log the violation
        security_logger.warning(
            f"CSP Violation: {violated_directive} blocked {blocked_uri} on {document_uri}"
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of CSP violations."""
        if not self.reports:
            return {"total_reports": 0, "unique_violations": 0, "top_violations": []}

        # Sort violations by count
        sorted_violations = sorted(
            self.report_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Get top violations
        top_violations = []
        for violation_key, count in sorted_violations[:10]:
            document_uri, directive, blocked_uri = violation_key.split("|")
            top_violations.append({
                "document_uri": document_uri,
                "violated_directive": directive,
                "blocked_uri": blocked_uri,
                "count": count,
            })

        return {
            "total_reports": len(self.reports),
            "unique_violations": len(self.report_counts),
            "top_violations": top_violations,
            "recent_reports": self.reports[-10:],  # Last 10 reports
        }


# Global CSP violation handler
csp_violation_handler = CSPViolationReport()


async def handle_csp_report(request: Request) -> JSONResponse:
    """Handle CSP violation reports."""
    try:
        # Parse the CSP report
        body = await request.body()
        report_data = json.loads(body)

        # Extract the CSP report (may be nested)
        csp_report = report_data.get("csp-report", report_data)

        # Add to violation handler
        csp_violation_handler.add_report(csp_report)

        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content=None
        )
    except Exception as e:
        logger.error(f"Failed to process CSP report: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid CSP report"}
        )


async def handle_ct_report(request: Request) -> JSONResponse:
    """Handle Certificate Transparency reports."""
    try:
        # Parse the CT report
        body = await request.body()
        report_data = json.loads(body)

        # Log the CT violation
        security_logger.warning(f"CT Violation: {report_data}")

        return JSONResponse(
            status_code=status.HTTP_204_NO_CONTENT,
            content=None
        )
    except Exception as e:
        logger.error(f"Failed to process CT report: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid CT report"}
        )


def create_security_txt_content() -> str:
    """Create content for security.txt file."""
    expires = (datetime.utcnow() + timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    return f"""# Security Policy
# This security.txt file is compliant with RFC 9116

Contact: mailto:security@example.com
Expires: {expires}
Encryption: https://example.com/pgp-key.txt
Acknowledgments: https://example.com/security/acknowledgments
Preferred-Languages: en, zh
Canonical: https://example.com/.well-known/security.txt
Policy: https://example.com/security-policy

# Bug Bounty Program
# We appreciate responsible disclosure of security vulnerabilities.
# Please report security issues to our security team.
"""


def setup_security_headers(app: FastAPI, config: Optional[SecurityHeadersConfig] = None) -> None:
    """Setup security headers middleware and endpoints."""
    # Add security headers middleware
    config = config or SecurityHeadersConfig()
    app.add_middleware(SecurityHeadersMiddleware, config=config)

    # Add CSP report endpoint
    @app.post("/api/security/csp-report", include_in_schema=False)
    async def csp_report_endpoint(request: Request) -> JSONResponse:
        """Endpoint to receive CSP violation reports."""
        return await handle_csp_report(request)

    # Add CT report endpoint
    @app.post("/api/security/ct-report", include_in_schema=False)
    async def ct_report_endpoint(request: Request) -> JSONResponse:
        """Endpoint to receive Certificate Transparency reports."""
        return await handle_ct_report(request)

    # Add CSP violations summary endpoint (admin only)
    @app.get("/api/admin/security/csp-violations", include_in_schema=False)
    async def get_csp_violations(
        _admin_user: UserModel = Depends(get_admin_user)
    ) -> JSONResponse:
        """Get summary of CSP violations (admin endpoint)."""
        try:
            summary = csp_violation_handler.get_summary()
            return JSONResponse(content=summary)
        except Exception as e:
            logger.error(f"Failed to get CSP violations summary: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve CSP violations summary"
            )

    # Add security.txt endpoint
    @app.get("/.well-known/security.txt", include_in_schema=False)
    async def security_txt() -> Response:
        """Serve security.txt file."""
        content = create_security_txt_content()
        return Response(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={
                "Cache-Control": "max-age=86400",
            }
        )

    logger.info(f"Security headers configured for {config.environment.value} environment")
    if config.csp_enabled:
        logger.info(f"CSP {'Report-Only' if config.csp_report_only else 'Enforcing'} mode enabled")
    if config.strict_transport_security_enabled:
        logger.info(f"HSTS enabled with max-age={config.hsts_max_age}")