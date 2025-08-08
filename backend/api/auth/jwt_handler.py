"""
JWT Token Handler
Manages JWT token creation, validation, and rotation using RS256 algorithm.
"""

import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import BaseModel


class TokenPayload(BaseModel):
    """JWT Token payload structure."""
    sub: str  # Subject (user_id)
    username: str
    role: str
    exp: datetime  # Expiration
    iat: datetime  # Issued at
    jti: str  # JWT ID (unique identifier)
    token_type: str  # "access" or "refresh"
    token_family: Optional[str] = None  # For refresh token rotation
    version: Optional[int] = None  # User's token version


class JWTConfig:
    """JWT Configuration."""
    # Token expiration times
    ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15 minutes
    REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days
    
    # Algorithm
    ALGORITHM = "RS256"
    
    # Issuer and audience
    ISSUER = "ai-pdf-scholar"
    AUDIENCE = "ai-pdf-scholar-api"
    
    # Key paths
    KEYS_DIR = Path.home() / ".ai_pdf_scholar" / "jwt_keys"
    PRIVATE_KEY_PATH = KEYS_DIR / "private_key.pem"
    PUBLIC_KEY_PATH = KEYS_DIR / "public_key.pem"
    
    # Security settings
    MIN_KEY_SIZE = 2048
    KEY_SIZE = 4096  # Use 4096 for production
    
    @classmethod
    def ensure_keys_exist(cls) -> Tuple[bytes, bytes]:
        """
        Ensure RSA key pair exists, generate if not.
        Returns: (private_key_bytes, public_key_bytes)
        """
        cls.KEYS_DIR.mkdir(parents=True, exist_ok=True)
        
        if not cls.PRIVATE_KEY_PATH.exists() or not cls.PUBLIC_KEY_PATH.exists():
            # Generate new RSA key pair
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=cls.KEY_SIZE,
                backend=default_backend()
            )
            
            # Serialize private key
            private_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Get public key
            public_key = private_key.public_key()
            public_key_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            # Save keys with secure permissions
            cls.PRIVATE_KEY_PATH.write_bytes(private_key_bytes)
            cls.PUBLIC_KEY_PATH.write_bytes(public_key_bytes)
            
            # Set restrictive permissions on private key (Unix-like systems)
            if os.name != 'nt':  # Not Windows
                os.chmod(cls.PRIVATE_KEY_PATH, 0o600)
            
            return private_key_bytes, public_key_bytes
        
        # Load existing keys
        private_key_bytes = cls.PRIVATE_KEY_PATH.read_bytes()
        public_key_bytes = cls.PUBLIC_KEY_PATH.read_bytes()
        
        return private_key_bytes, public_key_bytes


class JWTHandler:
    """
    JWT token handler for creating and validating tokens.
    Uses RS256 (RSA with SHA-256) for asymmetric signing.
    """
    
    def __init__(self):
        """Initialize JWT handler with RSA keys."""
        self.private_key, self.public_key = JWTConfig.ensure_keys_exist()
        self.config = JWTConfig()
    
    def create_access_token(
        self,
        user_id: int,
        username: str,
        role: str,
        version: int = 0,
        custom_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new access token.
        
        Args:
            user_id: User's database ID
            username: User's username
            role: User's role
            version: User's token version (for invalidation)
            custom_claims: Additional claims to include
        
        Returns:
            Encoded JWT access token
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=self.config.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "exp": expires,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "token_type": "access",
            "version": version,
            "iss": self.config.ISSUER,
            "aud": self.config.AUDIENCE,
        }
        
        if custom_claims:
            payload.update(custom_claims)
        
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm=self.config.ALGORITHM
        )
        
        return token
    
    def create_refresh_token(
        self,
        user_id: int,
        username: str,
        role: str,
        version: int = 0,
        token_family: Optional[str] = None
    ) -> Tuple[str, str, datetime]:
        """
        Create a new refresh token with rotation support.
        
        Args:
            user_id: User's database ID
            username: User's username
            role: User's role
            version: User's token version
            token_family: Token family ID for rotation tracking
        
        Returns:
            Tuple of (token, jti, expiration_datetime)
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=self.config.REFRESH_TOKEN_EXPIRE_DAYS)
        jti = str(uuid.uuid4())
        
        if not token_family:
            token_family = str(uuid.uuid4())
        
        payload = {
            "sub": str(user_id),
            "username": username,
            "role": role,
            "exp": expires,
            "iat": now,
            "jti": jti,
            "token_type": "refresh",
            "token_family": token_family,
            "version": version,
            "iss": self.config.ISSUER,
            "aud": self.config.AUDIENCE,
        }
        
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm=self.config.ALGORITHM
        )
        
        return token, jti, expires
    
    def decode_token(
        self,
        token: str,
        verify_exp: bool = True,
        token_type: Optional[str] = None
    ) -> Optional[TokenPayload]:
        """
        Decode and validate a JWT token.
        
        Args:
            token: JWT token string
            verify_exp: Whether to verify expiration
            token_type: Expected token type ("access" or "refresh")
        
        Returns:
            TokenPayload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.config.ALGORITHM],
                issuer=self.config.ISSUER,
                audience=self.config.AUDIENCE,
                options={"verify_exp": verify_exp}
            )
            
            # Verify token type if specified
            if token_type and payload.get("token_type") != token_type:
                return None
            
            # Convert datetime fields
            payload["exp"] = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            payload["iat"] = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
            
            return TokenPayload(**payload)
            
        except jwt.ExpiredSignatureError:
            # Token has expired
            return None
        except jwt.InvalidTokenError:
            # Token is invalid
            return None
        except Exception:
            # Any other error
            return None
    
    def verify_token(
        self,
        token: str,
        token_type: str = "access",
        user_version: Optional[int] = None
    ) -> Optional[TokenPayload]:
        """
        Verify a token with additional security checks.
        
        Args:
            token: JWT token string
            token_type: Expected token type
            user_version: Current user token version for validation
        
        Returns:
            TokenPayload if valid, None otherwise
        """
        payload = self.decode_token(token, token_type=token_type)
        
        if not payload:
            return None
        
        # Check token version if provided
        if user_version is not None and payload.version != user_version:
            return None
        
        return payload
    
    def create_email_verification_token(self, user_id: int, email: str) -> str:
        """
        Create a token for email verification.
        
        Args:
            user_id: User's database ID
            email: Email address to verify
        
        Returns:
            Encoded verification token
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=24)  # 24 hours to verify
        
        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": expires,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "token_type": "email_verification",
            "iss": self.config.ISSUER,
            "aud": self.config.AUDIENCE,
        }
        
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm=self.config.ALGORITHM
        )
        
        return token
    
    def create_password_reset_token(self, user_id: int, email: str) -> str:
        """
        Create a token for password reset.
        
        Args:
            user_id: User's database ID
            email: User's email address
        
        Returns:
            Encoded reset token
        """
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=1)  # 1 hour to reset
        
        # Add random salt to make token single-use
        salt = secrets.token_hex(16)
        
        payload = {
            "sub": str(user_id),
            "email": email,
            "exp": expires,
            "iat": now,
            "jti": str(uuid.uuid4()),
            "token_type": "password_reset",
            "salt": salt,
            "iss": self.config.ISSUER,
            "aud": self.config.AUDIENCE,
        }
        
        token = jwt.encode(
            payload,
            self.private_key,
            algorithm=self.config.ALGORITHM
        )
        
        return token
    
    def decode_verification_token(
        self,
        token: str,
        token_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Decode a verification token (email or password reset).
        
        Args:
            token: Verification token
            token_type: Expected token type
        
        Returns:
            Token payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.config.ALGORITHM],
                issuer=self.config.ISSUER,
                audience=self.config.AUDIENCE
            )
            
            if payload.get("token_type") != token_type:
                return None
            
            return payload
            
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
    
    def extract_token_from_header(self, authorization: str) -> Optional[str]:
        """
        Extract token from Authorization header.
        
        Args:
            authorization: Authorization header value
        
        Returns:
            Token string if valid format, None otherwise
        """
        if not authorization:
            return None
        
        parts = authorization.split()
        
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        return parts[1]
    
    def get_token_remaining_time(self, token: str) -> Optional[int]:
        """
        Get remaining time in seconds for a token.
        
        Args:
            token: JWT token string
        
        Returns:
            Remaining seconds if valid, None otherwise
        """
        payload = self.decode_token(token, verify_exp=False)
        
        if not payload:
            return None
        
        now = datetime.now(timezone.utc)
        remaining = (payload.exp - now).total_seconds()
        
        return max(0, int(remaining))


# Global JWT handler instance
jwt_handler = JWTHandler()