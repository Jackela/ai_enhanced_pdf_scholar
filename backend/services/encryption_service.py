"""
Data Encryption Service
Comprehensive encryption for data at rest and in transit.
"""

import base64
import hashlib
import json
import logging
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from backend.services.secrets_manager import SecretsManagerService

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# Encryption Models
# ============================================================================

class EncryptionKey(Base):
    """Model for encryption key management."""
    __tablename__ = 'encryption_keys'

    id = Column(Integer, primary_key=True)
    key_id = Column(String(100), unique=True, nullable=False)
    key_type = Column(String(50), nullable=False)  # 'master', 'field', 'file'
    algorithm = Column(String(50), nullable=False)  # 'AES-256-GCM', 'RSA-2048', etc.
    encrypted_key = Column(Text, nullable=False)  # Key encrypted with master key
    key_version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    rotated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    metadata = Column(Text, nullable=True)  # JSON metadata


class EncryptedField(Base):
    """Model for field-level encryption tracking."""
    __tablename__ = 'encrypted_fields'

    id = Column(Integer, primary_key=True)
    table_name = Column(String(100), nullable=False)
    column_name = Column(String(100), nullable=False)
    record_id = Column(String(100), nullable=False)
    encryption_key_id = Column(String(100), nullable=False)
    encryption_metadata = Column(Text, nullable=True)  # Nonce, IV, etc.
    encrypted_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# Encryption Service
# ============================================================================

class EncryptionService:
    """
    Comprehensive encryption service for data protection.
    Implements AES-256-GCM for symmetric encryption and RSA-2048 for asymmetric.
    """

    def __init__(
        self,
        db: Session,
        secrets_manager: SecretsManagerService | None = None,
        key_rotation_days: int = 90
    ):
        """Initialize encryption service."""
        self.db = db
        self.secrets_manager = secrets_manager or SecretsManagerService()
        self.key_rotation_days = key_rotation_days
        self._key_cache: dict[str, bytes] = {}
        self._master_key: bytes | None = None

        # Initialize master key
        self._initialize_master_key()

    def _initialize_master_key(self):
        """Initialize or retrieve master encryption key."""
        try:
            # Try to get master key from secrets manager
            master_key_b64 = self.secrets_manager.get_secret("encryption/master_key")
            if master_key_b64:
                self._master_key = base64.b64decode(master_key_b64)
            else:
                # Generate new master key
                self._master_key = Fernet.generate_key()
                self.secrets_manager.set_secret(
                    "encryption/master_key",
                    base64.b64encode(self._master_key).decode('utf-8')
                )
                logger.info("Generated new master encryption key")
        except Exception as e:
            logger.error(f"Failed to initialize master key: {e}")
            # Fallback to environment variable
            env_key = os.getenv("MASTER_ENCRYPTION_KEY")
            if env_key:
                self._master_key = base64.b64decode(env_key)
            else:
                raise RuntimeError("No master encryption key available")

    # ========================================================================
    # Symmetric Encryption (AES-256-GCM)
    # ========================================================================

    def encrypt_data(
        self,
        data: Union[str, bytes, dict],
        key_id: str | None = None,
        additional_data: bytes | None = None
    ) -> tuple[bytes, dict[str, Any]]:
        """
        Encrypt data using AES-256-GCM.

        Args:
            data: Data to encrypt
            key_id: Optional specific key to use
            additional_data: Additional authenticated data (AAD)

        Returns:
            Tuple of (encrypted_data, metadata)
        """
        # Convert data to bytes
        if isinstance(data, str):
            plaintext = data.encode('utf-8')
        elif isinstance(data, dict):
            plaintext = json.dumps(data).encode('utf-8')
        else:
            plaintext = data

        # Get or generate encryption key
        if key_id:
            key = self._get_encryption_key(key_id)
        else:
            key = self._generate_data_key()
            key_id = self._store_data_key(key)

        # Generate nonce
        nonce = os.urandom(12)  # 96-bit nonce for GCM

        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # Add additional authenticated data if provided
        if additional_data:
            encryptor.authenticate_additional_data(additional_data)

        # Encrypt data
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()

        # Get authentication tag
        tag = encryptor.tag

        # Combine nonce + tag + ciphertext
        encrypted_data = nonce + tag + ciphertext

        # Create metadata
        metadata = {
            "key_id": key_id,
            "algorithm": "AES-256-GCM",
            "nonce_size": 12,
            "tag_size": 16,
            "timestamp": datetime.utcnow().isoformat(),
            "has_aad": additional_data is not None
        }

        return encrypted_data, metadata

    def decrypt_data(
        self,
        encrypted_data: bytes,
        metadata: dict[str, Any],
        additional_data: bytes | None = None
    ) -> Union[str, bytes, dict]:
        """
        Decrypt data encrypted with AES-256-GCM.

        Args:
            encrypted_data: Encrypted data
            metadata: Encryption metadata
            additional_data: Additional authenticated data (AAD)

        Returns:
            Decrypted data
        """
        # Extract components
        nonce_size = metadata.get("nonce_size", 12)
        tag_size = metadata.get("tag_size", 16)

        nonce = encrypted_data[:nonce_size]
        tag = encrypted_data[nonce_size:nonce_size + tag_size]
        ciphertext = encrypted_data[nonce_size + tag_size:]

        # Get decryption key
        key_id = metadata["key_id"]
        key = self._get_encryption_key(key_id)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(nonce, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()

        # Add additional authenticated data if provided
        if additional_data and metadata.get("has_aad"):
            decryptor.authenticate_additional_data(additional_data)

        # Decrypt data
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        # Try to decode as string or JSON
        try:
            text = plaintext.decode('utf-8')
            # Try to parse as JSON
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text
        except UnicodeDecodeError:
            return plaintext

    # ========================================================================
    # Field-Level Encryption
    # ========================================================================

    def encrypt_field(
        self,
        value: Any,
        table_name: str,
        column_name: str,
        record_id: str
    ) -> str:
        """
        Encrypt a database field value.

        Args:
            value: Field value to encrypt
            table_name: Database table name
            column_name: Column name
            record_id: Record identifier

        Returns:
            Base64-encoded encrypted value
        """
        # Generate field-specific key ID
        key_id = f"field_{table_name}_{column_name}"

        # Encrypt the value
        encrypted_data, metadata = self.encrypt_data(value, key_id)

        # Store encryption metadata
        field_record = EncryptedField(
            table_name=table_name,
            column_name=column_name,
            record_id=record_id,
            encryption_key_id=key_id,
            encryption_metadata=json.dumps(metadata)
        )
        self.db.add(field_record)
        self.db.commit()

        # Return base64-encoded encrypted data
        return base64.b64encode(encrypted_data).decode('utf-8')

    def decrypt_field(
        self,
        encrypted_value: str,
        table_name: str,
        column_name: str,
        record_id: str
    ) -> Any:
        """
        Decrypt a database field value.

        Args:
            encrypted_value: Base64-encoded encrypted value
            table_name: Database table name
            column_name: Column name
            record_id: Record identifier

        Returns:
            Decrypted value
        """
        # Decode from base64
        encrypted_data = base64.b64decode(encrypted_value)

        # Get encryption metadata
        field_record = self.db.query(EncryptedField).filter_by(
            table_name=table_name,
            column_name=column_name,
            record_id=record_id
        ).first()

        if not field_record:
            raise ValueError(f"No encryption metadata found for {table_name}.{column_name}:{record_id}")

        metadata = json.loads(field_record.encryption_metadata)

        # Decrypt the value
        return self.decrypt_data(encrypted_data, metadata)

    # ========================================================================
    # File Encryption
    # ========================================================================

    def encrypt_file(
        self,
        input_path: Path,
        output_path: Path | None = None,
        chunk_size: int = 64 * 1024  # 64KB chunks
    ) -> tuple[Path, dict[str, Any]]:
        """
        Encrypt a file using streaming encryption.

        Args:
            input_path: Path to input file
            output_path: Optional output path (defaults to input_path.enc)
            chunk_size: Size of chunks for streaming

        Returns:
            Tuple of (output_path, metadata)
        """
        if output_path is None:
            output_path = Path(str(input_path) + '.enc')

        # Generate file encryption key
        key = self._generate_data_key()
        key_id = self._store_data_key(key, key_type='file')

        # Generate nonce
        nonce = os.urandom(12)

        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(nonce),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        # Calculate file hash for integrity
        file_hash = hashlib.sha256()

        # Encrypt file
        with open(input_path, 'rb') as infile, open(output_path, 'wb') as outfile:
            # Write nonce at the beginning
            outfile.write(nonce)

            # Reserve space for tag (will write later)
            tag_position = outfile.tell()
            outfile.write(b'\x00' * 16)

            # Encrypt file contents
            while True:
                chunk = infile.read(chunk_size)
                if not chunk:
                    break

                file_hash.update(chunk)
                encrypted_chunk = encryptor.update(chunk)
                outfile.write(encrypted_chunk)

            # Finalize encryption
            encryptor.finalize()

            # Write authentication tag
            outfile.seek(tag_position)
            outfile.write(encryptor.tag)

        # Create metadata
        metadata = {
            "key_id": key_id,
            "algorithm": "AES-256-GCM",
            "file_size": input_path.stat().st_size,
            "encrypted_size": output_path.stat().st_size,
            "file_hash": file_hash.hexdigest(),
            "timestamp": datetime.utcnow().isoformat()
        }

        # Store metadata
        metadata_path = Path(str(output_path) + '.meta')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Encrypted file: {input_path} -> {output_path}")

        return output_path, metadata

    def decrypt_file(
        self,
        input_path: Path,
        output_path: Path | None = None,
        chunk_size: int = 64 * 1024
    ) -> Path:
        """
        Decrypt a file encrypted with encrypt_file.

        Args:
            input_path: Path to encrypted file
            output_path: Optional output path
            chunk_size: Size of chunks for streaming

        Returns:
            Path to decrypted file
        """
        if output_path is None:
            if str(input_path).endswith('.enc'):
                output_path = Path(str(input_path)[:-4])
            else:
                output_path = Path(str(input_path) + '.dec')

        # Load metadata
        metadata_path = Path(str(input_path) + '.meta')
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

        with open(metadata_path) as f:
            metadata = json.load(f)

        # Get decryption key
        key = self._get_encryption_key(metadata["key_id"])

        # Read encrypted file
        with open(input_path, 'rb') as infile:
            # Read nonce
            nonce = infile.read(12)

            # Read tag
            tag = infile.read(16)

            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(nonce, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()

            # Decrypt file contents
            file_hash = hashlib.sha256()

            with open(output_path, 'wb') as outfile:
                while True:
                    chunk = infile.read(chunk_size)
                    if not chunk:
                        break

                    decrypted_chunk = decryptor.update(chunk)
                    file_hash.update(decrypted_chunk)
                    outfile.write(decrypted_chunk)

                # Finalize decryption
                decryptor.finalize()

        # Verify file integrity
        if file_hash.hexdigest() != metadata["file_hash"]:
            output_path.unlink()  # Delete corrupted file
            raise ValueError("File integrity check failed")

        logger.info(f"Decrypted file: {input_path} -> {output_path}")

        return output_path

    # ========================================================================
    # Asymmetric Encryption (RSA)
    # ========================================================================

    def generate_key_pair(self, key_size: int = 2048) -> tuple[bytes, bytes]:
        """
        Generate RSA key pair.

        Args:
            key_size: RSA key size in bits

        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
            backend=default_backend()
        )

        # Serialize private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )

        # Serialize public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return private_pem, public_pem

    def encrypt_with_public_key(self, data: bytes, public_key_pem: bytes) -> bytes:
        """
        Encrypt data with RSA public key.

        Args:
            data: Data to encrypt
            public_key_pem: PEM-encoded public key

        Returns:
            Encrypted data
        """
        public_key = serialization.load_pem_public_key(
            public_key_pem,
            backend=default_backend()
        )

        encrypted = public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return encrypted

    def decrypt_with_private_key(self, encrypted_data: bytes, private_key_pem: bytes) -> bytes:
        """
        Decrypt data with RSA private key.

        Args:
            encrypted_data: Encrypted data
            private_key_pem: PEM-encoded private key

        Returns:
            Decrypted data
        """
        private_key = serialization.load_pem_private_key(
            private_key_pem,
            password=None,
            backend=default_backend()
        )

        decrypted = private_key.decrypt(
            encrypted_data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return decrypted

    # ========================================================================
    # Key Management
    # ========================================================================

    def _generate_data_key(self, key_type: str = 'field') -> bytes:
        """Generate a new data encryption key."""
        return Fernet.generate_key()

    def _store_data_key(self, key: bytes, key_type: str = 'field') -> str:
        """Store a data key encrypted with master key."""
        # Generate key ID
        key_id = f"{key_type}_{secrets.token_urlsafe(16)}"

        # Encrypt key with master key
        fernet = Fernet(self._master_key)
        encrypted_key = fernet.encrypt(key)

        # Store in database
        key_record = EncryptionKey(
            key_id=key_id,
            key_type=key_type,
            algorithm='AES-256-GCM',
            encrypted_key=base64.b64encode(encrypted_key).decode('utf-8'),
            key_version=1,
            is_active=True
        )
        self.db.add(key_record)
        self.db.commit()

        # Cache the key
        self._key_cache[key_id] = key

        return key_id

    def _get_encryption_key(self, key_id: str) -> bytes:
        """Retrieve and decrypt an encryption key."""
        # Check cache
        if key_id in self._key_cache:
            return self._key_cache[key_id]

        # Get from database
        key_record = self.db.query(EncryptionKey).filter_by(
            key_id=key_id,
            is_active=True
        ).first()

        if not key_record:
            raise ValueError(f"Encryption key not found: {key_id}")

        # Decrypt key with master key
        fernet = Fernet(self._master_key)
        encrypted_key = base64.b64decode(key_record.encrypted_key)
        key = fernet.decrypt(encrypted_key)

        # Cache the key
        self._key_cache[key_id] = key

        return key

    def rotate_keys(self, force: bool = False) -> dict[str, int]:
        """
        Rotate encryption keys based on age.

        Args:
            force: Force rotation regardless of age

        Returns:
            Dictionary with rotation statistics
        """
        stats = {"rotated": 0, "skipped": 0, "failed": 0}

        # Get keys that need rotation
        cutoff_date = datetime.utcnow() - timedelta(days=self.key_rotation_days)

        query = self.db.query(EncryptionKey).filter(
            EncryptionKey.is_active == True
        )

        if not force:
            query = query.filter(
                (EncryptionKey.rotated_at == None) |
                (EncryptionKey.rotated_at < cutoff_date)
            )

        keys_to_rotate = query.all()

        for key_record in keys_to_rotate:
            try:
                # Generate new key
                new_key = self._generate_data_key(key_record.key_type)

                # Create new key record
                new_key_record = EncryptionKey(
                    key_id=f"{key_record.key_id}_v{key_record.key_version + 1}",
                    key_type=key_record.key_type,
                    algorithm=key_record.algorithm,
                    encrypted_key=base64.b64encode(
                        Fernet(self._master_key).encrypt(new_key)
                    ).decode('utf-8'),
                    key_version=key_record.key_version + 1,
                    is_active=True
                )
                self.db.add(new_key_record)

                # Deactivate old key
                key_record.is_active = False
                key_record.rotated_at = datetime.utcnow()

                stats["rotated"] += 1

                logger.info(f"Rotated key: {key_record.key_id}")
            except Exception as e:
                logger.error(f"Failed to rotate key {key_record.key_id}: {e}")
                stats["failed"] += 1

        self.db.commit()

        return stats

    # ========================================================================
    # Database Encryption
    # ========================================================================

    def enable_database_encryption(self, db_path: Path) -> bool:
        """
        Enable transparent database encryption (TDE) for SQLite.

        Args:
            db_path: Path to SQLite database

        Returns:
            Success status
        """
        try:
            import sqlite3

            # Connect to database
            conn = sqlite3.connect(str(db_path))

            # Enable encryption using SQLCipher commands
            # Note: This requires SQLCipher-enabled SQLite
            conn.execute(f"PRAGMA key = '{self._master_key.hex()}'")
            conn.execute("PRAGMA cipher_page_size = 4096")
            conn.execute("PRAGMA kdf_iter = 256000")
            conn.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA256")
            conn.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA256")

            conn.close()

            logger.info(f"Enabled database encryption for: {db_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to enable database encryption: {e}")
            return False


# ============================================================================
# TLS Configuration
# ============================================================================

class TLSConfiguration:
    """
    TLS/SSL configuration for secure communication.
    """

    def __init__(self, cert_path: Path | None = None, key_path: Path | None = None):
        """Initialize TLS configuration."""
        self.cert_path = cert_path or Path("certs/server.crt")
        self.key_path = key_path or Path("certs/server.key")
        self.ca_path = Path("certs/ca.crt")

    def generate_self_signed_cert(self, common_name: str = "localhost") -> tuple[Path, Path]:
        """
        Generate self-signed certificate for development.

        Args:
            common_name: Common name for certificate

        Returns:
            Tuple of (cert_path, key_path)
        """
        from cryptography import x509
        from cryptography.x509.oid import NameOID

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Generate certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "AI PDF Scholar"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])

        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName("127.0.0.1"),
                x509.DNSName("::1"),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256(), default_backend())

        # Create certs directory
        self.cert_path.parent.mkdir(exist_ok=True)

        # Write private key
        with open(self.key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))

        # Write certificate
        with open(self.cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        logger.info(f"Generated self-signed certificate: {self.cert_path}")

        return self.cert_path, self.key_path

    def get_ssl_context(self):
        """
        Get SSL context for server.

        Returns:
            SSL context
        """
        import ssl

        # Create SSL context
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

        # Load certificate and key
        if not self.cert_path.exists() or not self.key_path.exists():
            # Generate self-signed cert for development
            self.generate_self_signed_cert()

        context.load_cert_chain(str(self.cert_path), str(self.key_path))

        # Set secure ciphers
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')

        # Require TLS 1.2 or higher
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        return context


# ============================================================================
# Secure Communication Channel
# ============================================================================

class SecureChannel:
    """
    Secure communication channel with end-to-end encryption.
    """

    def __init__(self, encryption_service: EncryptionService):
        """Initialize secure channel."""
        self.encryption_service = encryption_service
        self.session_keys: dict[str, bytes] = {}

    def establish_session(self, client_id: str, client_public_key: bytes) -> dict[str, Any]:
        """
        Establish secure session with client.

        Args:
            client_id: Client identifier
            client_public_key: Client's public key

        Returns:
            Session establishment response
        """
        # Generate session key
        session_key = Fernet.generate_key()

        # Encrypt session key with client's public key
        encrypted_session_key = self.encryption_service.encrypt_with_public_key(
            session_key,
            client_public_key
        )

        # Store session key
        self.session_keys[client_id] = session_key

        # Generate server key pair for this session
        server_private, server_public = self.encryption_service.generate_key_pair()

        return {
            "session_id": secrets.token_urlsafe(32),
            "encrypted_session_key": base64.b64encode(encrypted_session_key).decode('utf-8'),
            "server_public_key": server_public.decode('utf-8'),
            "timestamp": datetime.utcnow().isoformat()
        }

    def encrypt_message(self, client_id: str, message: Any) -> str:
        """
        Encrypt message for client.

        Args:
            client_id: Client identifier
            message: Message to encrypt

        Returns:
            Base64-encoded encrypted message
        """
        if client_id not in self.session_keys:
            raise ValueError(f"No session established for client: {client_id}")

        # Use session key to encrypt
        fernet = Fernet(self.session_keys[client_id])

        # Serialize message
        if isinstance(message, (dict, list)):
            plaintext = json.dumps(message).encode('utf-8')
        else:
            plaintext = str(message).encode('utf-8')

        # Encrypt
        encrypted = fernet.encrypt(plaintext)

        return base64.b64encode(encrypted).decode('utf-8')

    def decrypt_message(self, client_id: str, encrypted_message: str) -> Any:
        """
        Decrypt message from client.

        Args:
            client_id: Client identifier
            encrypted_message: Base64-encoded encrypted message

        Returns:
            Decrypted message
        """
        if client_id not in self.session_keys:
            raise ValueError(f"No session established for client: {client_id}")

        # Use session key to decrypt
        fernet = Fernet(self.session_keys[client_id])

        # Decode and decrypt
        encrypted = base64.b64decode(encrypted_message)
        plaintext = fernet.decrypt(encrypted)

        # Try to parse as JSON
        try:
            return json.loads(plaintext.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return plaintext.decode('utf-8')


if __name__ == "__main__":
    # Example usage
    pass
