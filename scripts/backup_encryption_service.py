#!/usr/bin/env python3
"""
Backup Encryption Service
Implements AES-256-GCM encryption for backup files with automatic key rotation,
key derivation, and secure key management integration.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import secrets
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import aiofiles
from cryptography.fernet import Fernet, MultiFernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

# Add backend to path for imports
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.core.secrets import get_secrets_manager
from backend.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class EncryptionAlgorithm(str, Enum):
    """Supported encryption algorithms."""
    AES_256_GCM = "AES-256-GCM"
    FERNET = "FERNET"
    RSA_OAEP = "RSA-OAEP"


class KeyDerivationAlgorithm(str, Enum):
    """Key derivation algorithms."""
    PBKDF2_SHA256 = "PBKDF2-SHA256"
    SCRYPT = "SCRYPT"


@dataclass
class EncryptionMetadata:
    """Metadata for encrypted backup files."""
    algorithm: EncryptionAlgorithm
    key_id: str
    key_version: int
    nonce: str
    authentication_tag: str
    key_derivation: KeyDerivationAlgorithm
    salt: str
    iterations: int
    created_at: datetime
    file_size_original: int
    file_size_encrypted: int
    checksum_original: str
    checksum_encrypted: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EncryptionKey:
    """Encryption key with metadata."""
    key_id: str
    algorithm: EncryptionAlgorithm
    key_data: bytes
    version: int
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class BackupEncryptionService:
    """Service for encrypting and decrypting backup files."""
    
    def __init__(self, metrics_service: Optional[MetricsService] = None):
        """Initialize backup encryption service."""
        self.metrics_service = metrics_service or MetricsService()
        self.secrets_manager = get_secrets_manager()
        self.encryption_keys: Dict[str, EncryptionKey] = {}
        self.key_rotation_interval = timedelta(days=30)
        self.backup_encryption_path = Path("/var/backups/encryption")
        
        # Ensure encryption directory exists
        self.backup_encryption_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize master key
        self.master_key = self._get_or_create_master_key()
        
    def _get_or_create_master_key(self) -> bytes:
        """Get or create master encryption key."""
        try:
            # Try to get master key from secrets manager
            master_key = self.secrets_manager.get_secret("BACKUP_MASTER_KEY")
            if master_key:
                return base64.b64decode(master_key)
        except Exception as e:
            logger.warning(f"Could not retrieve master key from secrets manager: {e}")
        
        # Generate new master key
        master_key = secrets.token_bytes(32)  # 256-bit key
        master_key_b64 = base64.b64encode(master_key).decode()
        
        try:
            # Store in secrets manager
            self.secrets_manager.set_secret("BACKUP_MASTER_KEY", master_key_b64)
            logger.info("Generated and stored new master key")
        except Exception as e:
            logger.error(f"Failed to store master key: {e}")
        
        return master_key
    
    def _derive_key(
        self,
        password: bytes,
        salt: bytes,
        algorithm: KeyDerivationAlgorithm = KeyDerivationAlgorithm.PBKDF2_SHA256,
        iterations: int = 100000
    ) -> bytes:
        """Derive encryption key from password and salt."""
        if algorithm == KeyDerivationAlgorithm.PBKDF2_SHA256:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,  # 256-bit key
                salt=salt,
                iterations=iterations,
                backend=default_backend()
            )
            return kdf.derive(password)
        
        elif algorithm == KeyDerivationAlgorithm.SCRYPT:
            kdf = Scrypt(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                n=2**14,  # CPU/memory cost parameter
                r=8,      # Block size
                p=1,      # Parallelization parameter
                backend=default_backend()
            )
            return kdf.derive(password)
        
        else:
            raise ValueError(f"Unsupported key derivation algorithm: {algorithm}")
    
    async def generate_encryption_key(
        self,
        key_id: str,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
        expires_after: Optional[timedelta] = None
    ) -> EncryptionKey:
        """Generate a new encryption key."""
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            key_data = secrets.token_bytes(32)  # 256-bit key
        elif algorithm == EncryptionAlgorithm.FERNET:
            key_data = Fernet.generate_key()
        elif algorithm == EncryptionAlgorithm.RSA_OAEP:
            # Generate RSA key pair
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            key_data = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        else:
            raise ValueError(f"Unsupported encryption algorithm: {algorithm}")
        
        expires_at = None
        if expires_after:
            expires_at = datetime.utcnow() + expires_after
        
        encryption_key = EncryptionKey(
            key_id=key_id,
            algorithm=algorithm,
            key_data=key_data,
            version=1,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            is_active=True
        )
        
        # Store key
        self.encryption_keys[key_id] = encryption_key
        
        # Persist key to secrets manager (encrypted with master key)
        await self._persist_encryption_key(encryption_key)
        
        # Update metrics
        await self.metrics_service.record_counter(
            "backup_encryption_key_generated",
            tags={"key_id": key_id, "algorithm": algorithm.value}
        )
        
        logger.info(f"Generated encryption key: {key_id} ({algorithm.value})")
        return encryption_key
    
    async def _persist_encryption_key(self, key: EncryptionKey):
        """Persist encryption key to secure storage."""
        # Encrypt key with master key
        aesgcm = AESGCM(self.master_key)
        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
        
        key_metadata = {
            "key_id": key.key_id,
            "algorithm": key.algorithm.value,
            "version": key.version,
            "created_at": key.created_at.isoformat(),
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
            "is_active": key.is_active,
            "metadata": key.metadata
        }
        
        plaintext = json.dumps({
            "key_data": base64.b64encode(key.key_data).decode(),
            "metadata": key_metadata
        }).encode()
        
        encrypted_key = aesgcm.encrypt(nonce, plaintext, None)
        
        # Store in file system as backup
        key_file = self.backup_encryption_path / f"{key.key_id}.key"
        async with aiofiles.open(key_file, 'wb') as f:
            # Write nonce + encrypted key
            await f.write(nonce + encrypted_key)
        
        # Store in secrets manager
        try:
            encrypted_key_b64 = base64.b64encode(nonce + encrypted_key).decode()
            self.secrets_manager.set_secret(f"BACKUP_KEY_{key.key_id}", encrypted_key_b64)
        except Exception as e:
            logger.warning(f"Failed to store key in secrets manager: {e}")
    
    async def load_encryption_key(self, key_id: str) -> Optional[EncryptionKey]:
        """Load encryption key from storage."""
        if key_id in self.encryption_keys:
            return self.encryption_keys[key_id]
        
        # Try to load from secrets manager first
        encrypted_key_data = None
        try:
            encrypted_key_b64 = self.secrets_manager.get_secret(f"BACKUP_KEY_{key_id}")
            if encrypted_key_b64:
                encrypted_key_data = base64.b64decode(encrypted_key_b64)
        except Exception as e:
            logger.warning(f"Could not load key from secrets manager: {e}")
        
        # Fallback to file system
        if not encrypted_key_data:
            key_file = self.backup_encryption_path / f"{key_id}.key"
            if key_file.exists():
                async with aiofiles.open(key_file, 'rb') as f:
                    encrypted_key_data = await f.read()
        
        if not encrypted_key_data:
            return None
        
        # Decrypt key
        try:
            nonce = encrypted_key_data[:12]
            encrypted_key = encrypted_key_data[12:]
            
            aesgcm = AESGCM(self.master_key)
            decrypted_data = aesgcm.decrypt(nonce, encrypted_key, None)
            
            key_json = json.loads(decrypted_data.decode())
            key_data = base64.b64decode(key_json["key_data"])
            metadata = key_json["metadata"]
            
            encryption_key = EncryptionKey(
                key_id=metadata["key_id"],
                algorithm=EncryptionAlgorithm(metadata["algorithm"]),
                key_data=key_data,
                version=metadata["version"],
                created_at=datetime.fromisoformat(metadata["created_at"]),
                expires_at=datetime.fromisoformat(metadata["expires_at"]) if metadata["expires_at"] else None,
                is_active=metadata["is_active"],
                metadata=metadata.get("metadata", {})
            )
            
            self.encryption_keys[key_id] = encryption_key
            return encryption_key
            
        except Exception as e:
            logger.error(f"Failed to decrypt key {key_id}: {e}")
            return None
    
    async def encrypt_file(
        self,
        input_file: Union[str, Path],
        output_file: Union[str, Path],
        key_id: str,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.AES_256_GCM,
        compression: bool = True
    ) -> EncryptionMetadata:
        """Encrypt a backup file."""
        start_time = time.time()
        input_path = Path(input_file)
        output_path = Path(output_file)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Get or generate encryption key
        encryption_key = await self.load_encryption_key(key_id)
        if not encryption_key:
            encryption_key = await self.generate_encryption_key(
                key_id, algorithm, expires_after=self.key_rotation_interval
            )
        
        # Calculate original file checksum
        original_checksum = await self._calculate_checksum(input_path)
        original_size = input_path.stat().st_size
        
        # Encrypt file
        if algorithm == EncryptionAlgorithm.AES_256_GCM:
            metadata = await self._encrypt_aes_gcm(
                input_path, output_path, encryption_key, compression
            )
        elif algorithm == EncryptionAlgorithm.FERNET:
            metadata = await self._encrypt_fernet(
                input_path, output_path, encryption_key, compression
            )
        else:
            raise ValueError(f"Unsupported encryption algorithm: {algorithm}")
        
        # Calculate encrypted file checksum
        encrypted_checksum = await self._calculate_checksum(output_path)
        encrypted_size = output_path.stat().st_size
        
        # Create metadata
        encryption_metadata = EncryptionMetadata(
            algorithm=algorithm,
            key_id=key_id,
            key_version=encryption_key.version,
            nonce=metadata["nonce"],
            authentication_tag=metadata.get("authentication_tag", ""),
            key_derivation=KeyDerivationAlgorithm.PBKDF2_SHA256,
            salt=metadata.get("salt", ""),
            iterations=metadata.get("iterations", 0),
            created_at=datetime.utcnow(),
            file_size_original=original_size,
            file_size_encrypted=encrypted_size,
            checksum_original=original_checksum,
            checksum_encrypted=encrypted_checksum
        )
        
        # Save metadata
        metadata_file = output_path.with_suffix(output_path.suffix + '.meta')
        await self._save_encryption_metadata(metadata_file, encryption_metadata)
        
        # Update metrics
        await self.metrics_service.record_counter(
            "backup_file_encrypted",
            tags={"key_id": key_id, "algorithm": algorithm.value}
        )
        
        await self.metrics_service.record_histogram(
            "backup_encryption_duration",
            time.time() - start_time,
            tags={"algorithm": algorithm.value}
        )
        
        await self.metrics_service.record_gauge(
            "backup_encryption_ratio",
            encrypted_size / original_size if original_size > 0 else 1,
            tags={"algorithm": algorithm.value}
        )
        
        logger.info(f"Encrypted file: {input_path} -> {output_path} (ratio: {encrypted_size/original_size:.2f})")
        return encryption_metadata
    
    async def decrypt_file(
        self,
        input_file: Union[str, Path],
        output_file: Union[str, Path],
        metadata_file: Optional[Union[str, Path]] = None
    ) -> bool:
        """Decrypt a backup file."""
        start_time = time.time()
        input_path = Path(input_file)
        output_path = Path(output_file)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")
        
        # Load metadata
        if metadata_file is None:
            metadata_file = input_path.with_suffix(input_path.suffix + '.meta')
        
        metadata = await self._load_encryption_metadata(Path(metadata_file))
        if not metadata:
            raise ValueError("Could not load encryption metadata")
        
        # Load encryption key
        encryption_key = await self.load_encryption_key(metadata.key_id)
        if not encryption_key:
            raise ValueError(f"Encryption key not found: {metadata.key_id}")
        
        # Decrypt file
        success = False
        if metadata.algorithm == EncryptionAlgorithm.AES_256_GCM:
            success = await self._decrypt_aes_gcm(input_path, output_path, encryption_key, metadata)
        elif metadata.algorithm == EncryptionAlgorithm.FERNET:
            success = await self._decrypt_fernet(input_path, output_path, encryption_key, metadata)
        
        if success:
            # Verify checksum
            decrypted_checksum = await self._calculate_checksum(output_path)
            if decrypted_checksum != metadata.checksum_original:
                logger.error("Checksum verification failed after decryption")
                return False
            
            # Update metrics
            await self.metrics_service.record_counter(
                "backup_file_decrypted",
                tags={"key_id": metadata.key_id, "algorithm": metadata.algorithm.value}
            )
            
            await self.metrics_service.record_histogram(
                "backup_decryption_duration",
                time.time() - start_time,
                tags={"algorithm": metadata.algorithm.value}
            )
            
            logger.info(f"Decrypted file: {input_path} -> {output_path}")
            return True
        
        return False
    
    async def _encrypt_aes_gcm(
        self,
        input_path: Path,
        output_path: Path,
        key: EncryptionKey,
        compression: bool
    ) -> Dict[str, Any]:
        """Encrypt file using AES-256-GCM."""
        aesgcm = AESGCM(key.key_data)
        nonce = secrets.token_bytes(12)  # 96-bit nonce
        
        # Read and encrypt file
        async with aiofiles.open(input_path, 'rb') as infile:
            plaintext = await infile.read()
        
        # Optional compression
        if compression:
            import zlib
            plaintext = zlib.compress(plaintext, level=6)
        
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        
        # Write encrypted file
        async with aiofiles.open(output_path, 'wb') as outfile:
            await outfile.write(nonce + ciphertext)
        
        return {
            "nonce": base64.b64encode(nonce).decode(),
            "compression": compression
        }
    
    async def _decrypt_aes_gcm(
        self,
        input_path: Path,
        output_path: Path,
        key: EncryptionKey,
        metadata: EncryptionMetadata
    ) -> bool:
        """Decrypt file using AES-256-GCM."""
        try:
            aesgcm = AESGCM(key.key_data)
            
            # Read encrypted file
            async with aiofiles.open(input_path, 'rb') as infile:
                encrypted_data = await infile.read()
            
            nonce = encrypted_data[:12]
            ciphertext = encrypted_data[12:]
            
            # Decrypt
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            
            # Decompress if needed
            compression = metadata.metadata.get("compression", False)
            if compression:
                import zlib
                plaintext = zlib.decompress(plaintext)
            
            # Write decrypted file
            async with aiofiles.open(output_path, 'wb') as outfile:
                await outfile.write(plaintext)
            
            return True
            
        except Exception as e:
            logger.error(f"AES-GCM decryption failed: {e}")
            return False
    
    async def _encrypt_fernet(
        self,
        input_path: Path,
        output_path: Path,
        key: EncryptionKey,
        compression: bool
    ) -> Dict[str, Any]:
        """Encrypt file using Fernet."""
        fernet = Fernet(key.key_data)
        
        # Read file
        async with aiofiles.open(input_path, 'rb') as infile:
            plaintext = await infile.read()
        
        # Optional compression
        if compression:
            import zlib
            plaintext = zlib.compress(plaintext, level=6)
        
        # Encrypt
        ciphertext = fernet.encrypt(plaintext)
        
        # Write encrypted file
        async with aiofiles.open(output_path, 'wb') as outfile:
            await outfile.write(ciphertext)
        
        return {
            "nonce": "",  # Fernet includes nonce/IV internally
            "compression": compression
        }
    
    async def _decrypt_fernet(
        self,
        input_path: Path,
        output_path: Path,
        key: EncryptionKey,
        metadata: EncryptionMetadata
    ) -> bool:
        """Decrypt file using Fernet."""
        try:
            fernet = Fernet(key.key_data)
            
            # Read encrypted file
            async with aiofiles.open(input_path, 'rb') as infile:
                ciphertext = await infile.read()
            
            # Decrypt
            plaintext = fernet.decrypt(ciphertext)
            
            # Decompress if needed
            compression = metadata.metadata.get("compression", False)
            if compression:
                import zlib
                plaintext = zlib.decompress(plaintext)
            
            # Write decrypted file
            async with aiofiles.open(output_path, 'wb') as outfile:
                await outfile.write(plaintext)
            
            return True
            
        except Exception as e:
            logger.error(f"Fernet decryption failed: {e}")
            return False
    
    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of file."""
        hash_sha256 = hashlib.sha256()
        
        async with aiofiles.open(file_path, 'rb') as f:
            while chunk := await f.read(8192):
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    async def _save_encryption_metadata(self, metadata_file: Path, metadata: EncryptionMetadata):
        """Save encryption metadata to file."""
        metadata_dict = {
            "algorithm": metadata.algorithm.value,
            "key_id": metadata.key_id,
            "key_version": metadata.key_version,
            "nonce": metadata.nonce,
            "authentication_tag": metadata.authentication_tag,
            "key_derivation": metadata.key_derivation.value,
            "salt": metadata.salt,
            "iterations": metadata.iterations,
            "created_at": metadata.created_at.isoformat(),
            "file_size_original": metadata.file_size_original,
            "file_size_encrypted": metadata.file_size_encrypted,
            "checksum_original": metadata.checksum_original,
            "checksum_encrypted": metadata.checksum_encrypted,
            "metadata": metadata.metadata
        }
        
        async with aiofiles.open(metadata_file, 'w') as f:
            await f.write(json.dumps(metadata_dict, indent=2))
    
    async def _load_encryption_metadata(self, metadata_file: Path) -> Optional[EncryptionMetadata]:
        """Load encryption metadata from file."""
        if not metadata_file.exists():
            return None
        
        try:
            async with aiofiles.open(metadata_file, 'r') as f:
                metadata_dict = json.loads(await f.read())
            
            return EncryptionMetadata(
                algorithm=EncryptionAlgorithm(metadata_dict["algorithm"]),
                key_id=metadata_dict["key_id"],
                key_version=metadata_dict["key_version"],
                nonce=metadata_dict["nonce"],
                authentication_tag=metadata_dict["authentication_tag"],
                key_derivation=KeyDerivationAlgorithm(metadata_dict["key_derivation"]),
                salt=metadata_dict["salt"],
                iterations=metadata_dict["iterations"],
                created_at=datetime.fromisoformat(metadata_dict["created_at"]),
                file_size_original=metadata_dict["file_size_original"],
                file_size_encrypted=metadata_dict["file_size_encrypted"],
                checksum_original=metadata_dict["checksum_original"],
                checksum_encrypted=metadata_dict["checksum_encrypted"],
                metadata=metadata_dict.get("metadata", {})
            )
            
        except Exception as e:
            logger.error(f"Failed to load encryption metadata: {e}")
            return None
    
    async def rotate_keys(self, key_age_threshold: Optional[timedelta] = None) -> int:
        """Rotate encryption keys based on age threshold."""
        if not key_age_threshold:
            key_age_threshold = self.key_rotation_interval
        
        rotated_count = 0
        now = datetime.utcnow()
        
        for key_id, key in list(self.encryption_keys.items()):
            if key.is_active and (now - key.created_at) > key_age_threshold:
                # Create new version of the key
                new_key = await self.generate_encryption_key(
                    f"{key_id}_v{key.version + 1}",
                    key.algorithm,
                    expires_after=self.key_rotation_interval
                )
                
                # Mark old key as inactive
                key.is_active = False
                await self._persist_encryption_key(key)
                
                rotated_count += 1
                logger.info(f"Rotated key: {key_id} -> {new_key.key_id}")
        
        if rotated_count > 0:
            await self.metrics_service.record_counter(
                "backup_encryption_keys_rotated",
                value=rotated_count
            )
        
        return rotated_count
    
    def get_status(self) -> Dict[str, Any]:
        """Get encryption service status."""
        now = datetime.utcnow()
        
        active_keys = [k for k in self.encryption_keys.values() if k.is_active]
        expired_keys = [
            k for k in self.encryption_keys.values() 
            if k.expires_at and k.expires_at < now
        ]
        
        return {
            "total_keys": len(self.encryption_keys),
            "active_keys": len(active_keys),
            "expired_keys": len(expired_keys),
            "key_rotation_interval_days": self.key_rotation_interval.days,
            "algorithms_supported": [alg.value for alg in EncryptionAlgorithm],
            "master_key_present": bool(self.master_key)
        }


# Example usage
async def main():
    """Example usage of backup encryption service."""
    service = BackupEncryptionService()
    
    # Test encryption/decryption
    test_file = Path("/tmp/test_backup.txt")
    encrypted_file = Path("/tmp/test_backup.txt.enc")
    decrypted_file = Path("/tmp/test_backup_decrypted.txt")
    
    # Create test file
    async with aiofiles.open(test_file, 'w') as f:
        await f.write("This is a test backup file for encryption.")
    
    # Encrypt
    metadata = await service.encrypt_file(test_file, encrypted_file, "test_key")
    print(f"Encrypted: {metadata}")
    
    # Decrypt
    success = await service.decrypt_file(encrypted_file, decrypted_file)
    print(f"Decryption success: {success}")
    
    # Verify content
    async with aiofiles.open(decrypted_file, 'r') as f:
        content = await f.read()
        print(f"Decrypted content: {content}")
    
    # Status
    status = service.get_status()
    print(f"Service status: {status}")


if __name__ == "__main__":
    asyncio.run(main())