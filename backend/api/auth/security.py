"""
JWT Security Module
Implements JWT token generation, verification, and password hashing with enterprise security.
"""

import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from pathlib import Path

import bcrypt
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

# Security configuration
class SecurityConfig:
    """Security configuration constants."""
    
    # JWT Configuration
    ALGORITHM = "RS256"  # Using RSA for asymmetric encryption
    ACCESS_TOKEN_EXPIRE_MINUTES = 15
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    REFRESH_TOKEN_ROTATION = True  # Enable token rotation for security
    
    # Password hashing
    BCRYPT_SALT_ROUNDS = 12
    
    # Token claims
    ISSUER = "ai-pdf-scholar"
    AUDIENCE = "ai-pdf-scholar-api"
    
    # Key paths
    KEYS_DIR = Path.home() / ".ai_pdf_scholar" / "keys"
    PRIVATE_KEY_PATH = KEYS_DIR / "jwt_private.pem"
    PUBLIC_KEY_PATH = KEYS_DIR / "jwt_public.pem"
    
    # Rate limiting
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30
    
    # Session security
    REQUIRE_HTTPS = os.getenv("REQUIRE_HTTPS", "true").lower() == "true"
    SECURE_COOKIE = os.getenv("SECURE_COOKIE", "true").lower() == "true"
    SAME_SITE_POLICY = "strict"


class KeyManager:
    """Manages RSA key pairs for JWT signing."""
    
    def __init__(self):
        """Initialize key manager and ensure keys exist."""
        self.config = SecurityConfig()
        self._ensure_keys_exist()
        self._load_keys()
    
    def _ensure_keys_exist(self):
        """Generate RSA key pair if not exists."""
        self.config.KEYS_DIR.mkdir(parents=True, exist_ok=True)
        
        if not self.config.PRIVATE_KEY_PATH.exists() or not self.config.PUBLIC_KEY_PATH.exists():
            self._generate_key_pair()
    
    def _generate_key_pair(self):
        """Generate new RSA key pair for JWT signing."""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        # Save private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        self.config.PRIVATE_KEY_PATH.write_bytes(private_pem)
        self.config.PRIVATE_KEY_PATH.chmod(0o600)  # Restrict access to owner only
        
        # Save public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.config.PUBLIC_KEY_PATH.write_bytes(public_pem)
        self.config.PUBLIC_KEY_PATH.chmod(0o644)  # Public key can be read by others
    
    def _load_keys(self):
        """Load RSA keys from files."""
        self.private_key = self.config.PRIVATE_KEY_PATH.read_text()
        self.public_key = self.config.PUBLIC_KEY_PATH.read_text()
    
    def get_private_key(self) -> str:
        """Get private key for signing."""
        return self.private_key
    
    def get_public_key(self) -> str:
        """Get public key for verification."""
        return self.public_key


# Initialize key manager (singleton)
_key_manager = None

def get_key_manager() -> KeyManager:
    """Get or create key manager instance."""
    global _key_manager
    if _key_manager is None:
        _key_manager = KeyManager()
    return _key_manager


# Password hashing functions

def hash_password(password: str) -> str:
    """
    Hash password using bcrypt with salt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
    """
    salt = bcrypt.gensalt(rounds=SecurityConfig.BCRYPT_SALT_ROUNDS)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False


# Token generation and verification

def create_access_token(
    user_id: int,
    username: str,
    role: str,
    additional_claims: Optional[Dict[str, Any]] = None
) -> Tuple[str, datetime]:
    """
    Create JWT access token.
    
    Args:
        user_id: User ID
        username: Username
        role: User role
        additional_claims: Additional JWT claims
        
    Returns:
        Tuple of (token, expiry_datetime)
    """
    key_manager = get_key_manager()
    
    # Calculate expiry
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=SecurityConfig.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    
    # Build payload
    payload = {
        "sub": str(user_id),  # Subject (user ID)
        "username": username,
        "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "iss": SecurityConfig.ISSUER,
        "aud": SecurityConfig.AUDIENCE,
        "jti": secrets.token_urlsafe(16),  # JWT ID for tracking
    }
    
    # Add additional claims if provided
    if additional_claims:
        payload.update(additional_claims)
    
    # Create token
    token = jwt.encode(
        payload,
        key_manager.get_private_key(),
        algorithm=SecurityConfig.ALGORITHM
    )
    
    return token, expire


def create_refresh_token(
    user_id: int,
    token_family: Optional[str] = None,
    device_info: Optional[str] = None
) -> Tuple[str, str, datetime]:
    """
    Create JWT refresh token with rotation support.
    
    Args:
        user_id: User ID
        token_family: Token family ID for rotation tracking
        device_info: Device/client information
        
    Returns:
        Tuple of (token, token_family, expiry_datetime)
    """
    key_manager = get_key_manager()
    
    # Generate token family if not provided (for new login)
    if token_family is None:
        token_family = secrets.token_urlsafe(16)
    
    # Calculate expiry
    expire = datetime.now(timezone.utc) + timedelta(
        days=SecurityConfig.REFRESH_TOKEN_EXPIRE_DAYS
    )
    
    # Build payload
    jti = secrets.token_urlsafe(16)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "family": token_family,
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "iss": SecurityConfig.ISSUER,
        "aud": SecurityConfig.AUDIENCE,
        "jti": jti,
    }
    
    if device_info:
        payload["device"] = device_info
    
    # Create token
    token = jwt.encode(
        payload,
        key_manager.get_private_key(),
        algorithm=SecurityConfig.ALGORITHM
    )
    
    return token, jti, expire


def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token string
        token_type: Expected token type ("access" or "refresh")
        
    Returns:
        Decoded token payload if valid, None otherwise
    """
    key_manager = get_key_manager()
    
    try:
        # Decode and verify token
        payload = jwt.decode(
            token,
            key_manager.get_public_key(),
            algorithms=[SecurityConfig.ALGORITHM],
            audience=SecurityConfig.AUDIENCE,
            issuer=SecurityConfig.ISSUER,
            options={"require": ["exp", "iat", "sub", "type", "jti"]}
        )
        
        # Verify token type
        if payload.get("type") != token_type:
            return None
        
        return payload
        
    except jwt.ExpiredSignatureError:
        # Token has expired
        return None
    except jwt.InvalidTokenError:
        # Token is invalid
        return None
    except Exception:
        # Any other error
        return None


def decode_token_unsafe(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode JWT token without verification (for debugging/logging only).
    WARNING: Never use this for authentication!
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload without verification
    """
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return None


# Security utility functions

def generate_secure_token(length: int = 32) -> str:
    """
    Generate cryptographically secure random token.
    
    Args:
        length: Token length in bytes
        
    Returns:
        URL-safe token string
    """
    return secrets.token_urlsafe(length)


def generate_password_reset_token(user_id: int, email: str) -> str:
    """
    Generate password reset token.
    
    Args:
        user_id: User ID
        email: User email
        
    Returns:
        Password reset token
    """
    key_manager = get_key_manager()
    
    # Token expires in 1 hour
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "password_reset",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16),
    }
    
    return jwt.encode(
        payload,
        key_manager.get_private_key(),
        algorithm=SecurityConfig.ALGORITHM
    )


def verify_password_reset_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify password reset token.
    
    Args:
        token: Password reset token
        
    Returns:
        Token payload if valid, None otherwise
    """
    payload = verify_token(token, token_type="password_reset")
    if payload and payload.get("type") == "password_reset":
        return payload
    return None


def generate_email_verification_token(user_id: int, email: str) -> str:
    """
    Generate email verification token.
    
    Args:
        user_id: User ID
        email: User email
        
    Returns:
        Email verification token
    """
    key_manager = get_key_manager()
    
    # Token expires in 24 hours
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    
    payload = {
        "sub": str(user_id),
        "email": email,
        "type": "email_verification",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16),
    }
    
    return jwt.encode(
        payload,
        key_manager.get_private_key(),
        algorithm=SecurityConfig.ALGORITHM
    )


def verify_email_verification_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify email verification token.
    
    Args:
        token: Email verification token
        
    Returns:
        Token payload if valid, None otherwise
    """
    payload = verify_token(token, token_type="email_verification")
    if payload and payload.get("type") == "email_verification":
        return payload
    return None


def hash_token(token: str) -> str:
    """
    Hash token for storage (e.g., refresh tokens in database).
    
    Args:
        token: Token to hash
        
    Returns:
        SHA-256 hash of token
    """
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_compare(val1: str, val2: str) -> bool:
    """
    Constant time string comparison to prevent timing attacks.
    
    Args:
        val1: First value
        val2: Second value
        
    Returns:
        True if values match, False otherwise
    """
    return secrets.compare_digest(val1, val2)