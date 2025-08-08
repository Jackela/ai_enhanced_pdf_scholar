"""
Enterprise-Grade Secrets Management System
Manages all sensitive configuration including API keys, database credentials, JWT keys, etc.
Supports HashiCorp Vault, AWS Secrets Manager, and encrypted local storage.
"""

import base64
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import hvac
from boto3 import client as boto3_client
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from pydantic import BaseModel, Field, SecretStr, field_validator

logger = logging.getLogger(__name__)


class SecretType(str, Enum):
    """Types of secrets managed by the system."""
    DATABASE_URL = "database_url"
    API_KEY = "api_key"
    JWT_PRIVATE_KEY = "jwt_private_key"
    JWT_PUBLIC_KEY = "jwt_public_key"
    REDIS_URL = "redis_url"
    SMTP_PASSWORD = "smtp_password"
    ENCRYPTION_KEY = "encryption_key"
    OAUTH_SECRET = "oauth_secret"
    WEBHOOK_SECRET = "webhook_secret"
    SIGNING_KEY = "signing_key"


class SecretProvider(str, Enum):
    """Available secret storage providers."""
    VAULT = "vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"
    LOCAL_ENCRYPTED = "local_encrypted"
    ENVIRONMENT = "environment"


@dataclass
class SecretMetadata:
    """Metadata for a secret."""
    name: str
    type: SecretType
    version: int = 1
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    rotation_interval_days: Optional[int] = None
    last_rotated: Optional[datetime] = None
    tags: Dict[str, str] = field(default_factory=dict)
    description: Optional[str] = None


class SecretConfig(BaseModel):
    """Configuration for the secrets management system."""
    # Provider configuration
    primary_provider: SecretProvider = SecretProvider.LOCAL_ENCRYPTED
    fallback_providers: List[SecretProvider] = Field(default_factory=list)
    
    # Environment configuration
    environment: str = Field(default="development")
    application_name: str = Field(default="ai_pdf_scholar")
    
    # Vault configuration
    vault_url: Optional[str] = Field(default=None)
    vault_token: Optional[SecretStr] = Field(default=None)
    vault_namespace: Optional[str] = Field(default=None)
    vault_mount_point: str = Field(default="secret")
    vault_path_prefix: str = Field(default="ai_pdf_scholar")
    
    # AWS Secrets Manager configuration
    aws_region: str = Field(default="us-east-1")
    aws_access_key_id: Optional[SecretStr] = Field(default=None)
    aws_secret_access_key: Optional[SecretStr] = Field(default=None)
    aws_secret_prefix: str = Field(default="ai-pdf-scholar")
    
    # Local encrypted storage configuration
    local_storage_path: Path = Field(default=Path.home() / ".ai_pdf_scholar" / "secrets")
    local_encryption_key_path: Path = Field(default=Path.home() / ".ai_pdf_scholar" / "master.key")
    
    # Security settings
    enable_audit_logging: bool = Field(default=True)
    enable_secret_rotation: bool = Field(default=True)
    rotation_check_interval_hours: int = Field(default=24)
    secret_ttl_days: int = Field(default=90)
    
    # Performance settings
    cache_enabled: bool = Field(default=True)
    cache_ttl_seconds: int = Field(default=300)
    max_retry_attempts: int = Field(default=3)
    retry_delay_seconds: int = Field(default=1)
    
    @field_validator('environment')
    def validate_environment(cls, v):
        allowed = ['development', 'staging', 'production', 'test']
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @classmethod
    def from_env(cls) -> "SecretConfig":
        """Create configuration from environment variables."""
        config = {}
        
        # Provider selection
        if provider := os.getenv("SECRET_PROVIDER"):
            config["primary_provider"] = SecretProvider(provider)
        
        # Environment
        if env := os.getenv("ENVIRONMENT"):
            config["environment"] = env
        
        # Vault configuration
        if vault_url := os.getenv("VAULT_URL"):
            config["vault_url"] = vault_url
        if vault_token := os.getenv("VAULT_TOKEN"):
            config["vault_token"] = SecretStr(vault_token)
        if vault_namespace := os.getenv("VAULT_NAMESPACE"):
            config["vault_namespace"] = vault_namespace
        
        # AWS configuration
        if aws_region := os.getenv("AWS_DEFAULT_REGION"):
            config["aws_region"] = aws_region
        if aws_key := os.getenv("AWS_ACCESS_KEY_ID"):
            config["aws_access_key_id"] = SecretStr(aws_key)
        if aws_secret := os.getenv("AWS_SECRET_ACCESS_KEY"):
            config["aws_secret_access_key"] = SecretStr(aws_secret)
        
        return cls(**config)


class SecretProviderInterface(ABC):
    """Abstract interface for secret storage providers."""
    
    @abstractmethod
    def get_secret(self, key: str, version: Optional[str] = None) -> Optional[str]:
        """Retrieve a secret value."""
        pass
    
    @abstractmethod
    def set_secret(self, key: str, value: str, metadata: Optional[SecretMetadata] = None) -> bool:
        """Store a secret value."""
        pass
    
    @abstractmethod
    def delete_secret(self, key: str) -> bool:
        """Delete a secret."""
        pass
    
    @abstractmethod
    def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
        """List available secret keys."""
        pass
    
    @abstractmethod
    def rotate_secret(self, key: str, new_value: str) -> bool:
        """Rotate a secret to a new value."""
        pass
    
    @abstractmethod
    def get_secret_metadata(self, key: str) -> Optional[SecretMetadata]:
        """Get metadata for a secret."""
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if the provider is healthy and accessible."""
        pass


class VaultProvider(SecretProviderInterface):
    """HashiCorp Vault secret provider."""
    
    def __init__(self, config: SecretConfig):
        self.config = config
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Vault."""
        try:
            self.client = hvac.Client(
                url=self.config.vault_url,
                token=self.config.vault_token.get_secret_value() if self.config.vault_token else None,
                namespace=self.config.vault_namespace
            )
            
            if not self.client.is_authenticated():
                raise ConnectionError("Failed to authenticate with Vault")
            
            logger.info("Successfully connected to HashiCorp Vault")
        except Exception as e:
            logger.error(f"Failed to connect to Vault: {e}")
            raise
    
    def _get_secret_path(self, key: str) -> str:
        """Construct the full path for a secret in Vault."""
        env = self.config.environment
        prefix = self.config.vault_path_prefix
        return f"{prefix}/{env}/{key}"
    
    def get_secret(self, key: str, version: Optional[str] = None) -> Optional[str]:
        """Retrieve a secret from Vault."""
        try:
            path = self._get_secret_path(key)
            
            # Read secret from KV v2 engine
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                version=version,
                mount_point=self.config.vault_mount_point
            )
            
            if response and 'data' in response and 'data' in response['data']:
                return response['data']['data'].get('value')
            
            return None
        except Exception as e:
            logger.error(f"Failed to get secret from Vault: {e}")
            return None
    
    def set_secret(self, key: str, value: str, metadata: Optional[SecretMetadata] = None) -> bool:
        """Store a secret in Vault."""
        try:
            path = self._get_secret_path(key)
            
            secret_data = {'value': value}
            if metadata:
                secret_data['metadata'] = {
                    'type': metadata.type.value,
                    'version': metadata.version,
                    'created_at': metadata.created_at.isoformat(),
                    'updated_at': metadata.updated_at.isoformat(),
                    'expires_at': metadata.expires_at.isoformat() if metadata.expires_at else None,
                    'tags': json.dumps(metadata.tags),
                    'description': metadata.description
                }
            
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=secret_data,
                mount_point=self.config.vault_mount_point
            )
            
            logger.info(f"Successfully stored secret in Vault: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to store secret in Vault: {e}")
            return False
    
    def delete_secret(self, key: str) -> bool:
        """Delete a secret from Vault."""
        try:
            path = self._get_secret_path(key)
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path,
                mount_point=self.config.vault_mount_point
            )
            logger.info(f"Successfully deleted secret from Vault: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret from Vault: {e}")
            return False
    
    def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
        """List secrets in Vault."""
        try:
            base_path = f"{self.config.vault_path_prefix}/{self.config.environment}"
            if prefix:
                base_path = f"{base_path}/{prefix}"
            
            response = self.client.secrets.kv.v2.list_secrets(
                path=base_path,
                mount_point=self.config.vault_mount_point
            )
            
            if response and 'data' in response and 'keys' in response['data']:
                return response['data']['keys']
            
            return []
        except Exception as e:
            logger.error(f"Failed to list secrets from Vault: {e}")
            return []
    
    def rotate_secret(self, key: str, new_value: str) -> bool:
        """Rotate a secret in Vault."""
        # Vault handles versioning automatically
        return self.set_secret(key, new_value)
    
    def get_secret_metadata(self, key: str) -> Optional[SecretMetadata]:
        """Get metadata for a secret from Vault."""
        try:
            path = self._get_secret_path(key)
            response = self.client.secrets.kv.v2.read_secret_metadata(
                path=path,
                mount_point=self.config.vault_mount_point
            )
            
            if response and 'data' in response:
                # Parse metadata from custom_metadata if available
                custom_metadata = response['data'].get('custom_metadata', {})
                return SecretMetadata(
                    name=key,
                    type=SecretType(custom_metadata.get('type', SecretType.API_KEY.value)),
                    version=response['data'].get('current_version', 1),
                    created_at=datetime.fromisoformat(response['data'].get('created_time', datetime.utcnow().isoformat())),
                    updated_at=datetime.fromisoformat(response['data'].get('updated_time', datetime.utcnow().isoformat()))
                )
            
            return None
        except Exception as e:
            logger.error(f"Failed to get secret metadata from Vault: {e}")
            return None
    
    def health_check(self) -> bool:
        """Check Vault health."""
        try:
            return self.client.is_authenticated() and self.client.sys.is_initialized()
        except Exception as e:
            logger.error(f"Vault health check failed: {e}")
            return False


class AWSSecretsManagerProvider(SecretProviderInterface):
    """AWS Secrets Manager provider."""
    
    def __init__(self, config: SecretConfig):
        self.config = config
        self.client = self._create_client()
    
    def _create_client(self):
        """Create AWS Secrets Manager client."""
        try:
            if self.config.aws_access_key_id and self.config.aws_secret_access_key:
                return boto3_client(
                    'secretsmanager',
                    region_name=self.config.aws_region,
                    aws_access_key_id=self.config.aws_access_key_id.get_secret_value(),
                    aws_secret_access_key=self.config.aws_secret_access_key.get_secret_value()
                )
            else:
                # Use default credentials (IAM role, environment, etc.)
                return boto3_client('secretsmanager', region_name=self.config.aws_region)
        except Exception as e:
            logger.error(f"Failed to create AWS Secrets Manager client: {e}")
            raise
    
    def _get_secret_name(self, key: str) -> str:
        """Construct the full secret name for AWS."""
        return f"{self.config.aws_secret_prefix}/{self.config.environment}/{key}"
    
    def get_secret(self, key: str, version: Optional[str] = None) -> Optional[str]:
        """Retrieve a secret from AWS Secrets Manager."""
        try:
            secret_name = self._get_secret_name(key)
            
            kwargs = {'SecretId': secret_name}
            if version:
                kwargs['VersionId'] = version
            
            response = self.client.get_secret_value(**kwargs)
            
            if 'SecretString' in response:
                secret_data = json.loads(response['SecretString'])
                return secret_data.get('value')
            elif 'SecretBinary' in response:
                return base64.b64decode(response['SecretBinary']).decode('utf-8')
            
            return None
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.debug(f"Secret not found in AWS: {key}")
            else:
                logger.error(f"Failed to get secret from AWS: {e}")
            return None
    
    def set_secret(self, key: str, value: str, metadata: Optional[SecretMetadata] = None) -> bool:
        """Store a secret in AWS Secrets Manager."""
        try:
            secret_name = self._get_secret_name(key)
            
            secret_data = {'value': value}
            if metadata:
                secret_data['metadata'] = {
                    'type': metadata.type.value,
                    'version': metadata.version,
                    'created_at': metadata.created_at.isoformat(),
                    'expires_at': metadata.expires_at.isoformat() if metadata.expires_at else None
                }
            
            # Try to update existing secret first
            try:
                self.client.update_secret(
                    SecretId=secret_name,
                    SecretString=json.dumps(secret_data)
                )
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    # Create new secret
                    tags = []
                    if metadata and metadata.tags:
                        tags = [{'Key': k, 'Value': v} for k, v in metadata.tags.items()]
                    
                    self.client.create_secret(
                        Name=secret_name,
                        SecretString=json.dumps(secret_data),
                        Tags=tags,
                        Description=metadata.description if metadata else None
                    )
                else:
                    raise
            
            logger.info(f"Successfully stored secret in AWS: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to store secret in AWS: {e}")
            return False
    
    def delete_secret(self, key: str) -> bool:
        """Delete a secret from AWS Secrets Manager."""
        try:
            secret_name = self._get_secret_name(key)
            self.client.delete_secret(
                SecretId=secret_name,
                ForceDeleteWithoutRecovery=False  # Allow recovery within grace period
            )
            logger.info(f"Successfully deleted secret from AWS: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret from AWS: {e}")
            return False
    
    def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
        """List secrets in AWS Secrets Manager."""
        try:
            base_prefix = f"{self.config.aws_secret_prefix}/{self.config.environment}"
            if prefix:
                base_prefix = f"{base_prefix}/{prefix}"
            
            secrets = []
            paginator = self.client.get_paginator('list_secrets')
            
            for page in paginator.paginate():
                for secret in page['SecretList']:
                    if secret['Name'].startswith(base_prefix):
                        # Extract the key part from the full name
                        key = secret['Name'].replace(f"{base_prefix}/", "")
                        secrets.append(key)
            
            return secrets
        except Exception as e:
            logger.error(f"Failed to list secrets from AWS: {e}")
            return []
    
    def rotate_secret(self, key: str, new_value: str) -> bool:
        """Rotate a secret in AWS Secrets Manager."""
        try:
            secret_name = self._get_secret_name(key)
            
            # Put new version of secret
            self.client.put_secret_value(
                SecretId=secret_name,
                SecretString=json.dumps({'value': new_value})
            )
            
            logger.info(f"Successfully rotated secret in AWS: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to rotate secret in AWS: {e}")
            return False
    
    def get_secret_metadata(self, key: str) -> Optional[SecretMetadata]:
        """Get metadata for a secret from AWS."""
        try:
            secret_name = self._get_secret_name(key)
            response = self.client.describe_secret(SecretId=secret_name)
            
            tags = {tag['Key']: tag['Value'] for tag in response.get('Tags', [])}
            
            return SecretMetadata(
                name=key,
                type=SecretType.API_KEY,  # Default, can be enhanced with tags
                version=len(response.get('VersionIdsToStages', {})),
                created_at=response.get('CreatedDate', datetime.utcnow()),
                updated_at=response.get('LastChangedDate', datetime.utcnow()),
                last_rotated=response.get('LastRotatedDate'),
                tags=tags,
                description=response.get('Description')
            )
        except Exception as e:
            logger.error(f"Failed to get secret metadata from AWS: {e}")
            return None
    
    def health_check(self) -> bool:
        """Check AWS Secrets Manager health."""
        try:
            # Try to list secrets with limit 1
            self.client.list_secrets(MaxResults=1)
            return True
        except Exception as e:
            logger.error(f"AWS Secrets Manager health check failed: {e}")
            return False


class LocalEncryptedProvider(SecretProviderInterface):
    """Local encrypted file storage provider for development."""
    
    def __init__(self, config: SecretConfig):
        self.config = config
        self.storage_path = config.local_storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._master_key = self._get_or_create_master_key()
        self._fernet = Fernet(self._master_key)
        self._secrets_file = self.storage_path / f"{config.environment}_secrets.enc"
        self._metadata_file = self.storage_path / f"{config.environment}_metadata.json"
    
    def _get_or_create_master_key(self) -> bytes:
        """Get or create the master encryption key."""
        key_path = self.config.local_encryption_key_path
        key_path.parent.mkdir(parents=True, exist_ok=True)
        
        if key_path.exists():
            with open(key_path, 'rb') as f:
                key = f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            with open(key_path, 'wb') as f:
                f.write(key)
            
            # Set restrictive permissions (Unix-like systems)
            if os.name != 'nt':
                os.chmod(key_path, 0o600)
            
            logger.info("Generated new master encryption key")
        
        return key
    
    def _load_secrets(self) -> Dict[str, str]:
        """Load and decrypt secrets from file."""
        if not self._secrets_file.exists():
            return {}
        
        try:
            with open(self._secrets_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self._fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to load secrets: {e}")
            return {}
    
    def _save_secrets(self, secrets: Dict[str, str]) -> bool:
        """Encrypt and save secrets to file."""
        try:
            json_data = json.dumps(secrets, indent=2)
            encrypted_data = self._fernet.encrypt(json_data.encode('utf-8'))
            
            with open(self._secrets_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Set restrictive permissions (Unix-like systems)
            if os.name != 'nt':
                os.chmod(self._secrets_file, 0o600)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save secrets: {e}")
            return False
    
    def _load_metadata(self) -> Dict[str, Dict]:
        """Load metadata from file."""
        if not self._metadata_file.exists():
            return {}
        
        try:
            with open(self._metadata_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return {}
    
    def _save_metadata(self, metadata: Dict[str, Dict]) -> bool:
        """Save metadata to file."""
        try:
            with open(self._metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
            
            # Set restrictive permissions (Unix-like systems)
            if os.name != 'nt':
                os.chmod(self._metadata_file, 0o600)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")
            return False
    
    def get_secret(self, key: str, version: Optional[str] = None) -> Optional[str]:
        """Retrieve a secret from encrypted local storage."""
        secrets = self._load_secrets()
        return secrets.get(key)
    
    def set_secret(self, key: str, value: str, metadata: Optional[SecretMetadata] = None) -> bool:
        """Store a secret in encrypted local storage."""
        secrets = self._load_secrets()
        secrets[key] = value
        
        if metadata:
            all_metadata = self._load_metadata()
            all_metadata[key] = {
                'type': metadata.type.value,
                'version': metadata.version,
                'created_at': metadata.created_at.isoformat(),
                'updated_at': metadata.updated_at.isoformat(),
                'expires_at': metadata.expires_at.isoformat() if metadata.expires_at else None,
                'rotation_interval_days': metadata.rotation_interval_days,
                'last_rotated': metadata.last_rotated.isoformat() if metadata.last_rotated else None,
                'tags': metadata.tags,
                'description': metadata.description
            }
            self._save_metadata(all_metadata)
        
        success = self._save_secrets(secrets)
        if success:
            logger.info(f"Successfully stored secret locally: {key}")
        return success
    
    def delete_secret(self, key: str) -> bool:
        """Delete a secret from local storage."""
        secrets = self._load_secrets()
        if key in secrets:
            del secrets[key]
            
            # Also delete metadata
            metadata = self._load_metadata()
            if key in metadata:
                del metadata[key]
                self._save_metadata(metadata)
            
            success = self._save_secrets(secrets)
            if success:
                logger.info(f"Successfully deleted secret locally: {key}")
            return success
        return False
    
    def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
        """List secrets in local storage."""
        secrets = self._load_secrets()
        keys = list(secrets.keys())
        
        if prefix:
            keys = [k for k in keys if k.startswith(prefix)]
        
        return keys
    
    def rotate_secret(self, key: str, new_value: str) -> bool:
        """Rotate a secret in local storage."""
        metadata_dict = self._load_metadata()
        if key in metadata_dict:
            metadata_dict[key]['version'] = metadata_dict[key].get('version', 1) + 1
            metadata_dict[key]['updated_at'] = datetime.utcnow().isoformat()
            metadata_dict[key]['last_rotated'] = datetime.utcnow().isoformat()
            self._save_metadata(metadata_dict)
        
        return self.set_secret(key, new_value)
    
    def get_secret_metadata(self, key: str) -> Optional[SecretMetadata]:
        """Get metadata for a secret."""
        metadata_dict = self._load_metadata()
        if key in metadata_dict:
            meta = metadata_dict[key]
            return SecretMetadata(
                name=key,
                type=SecretType(meta.get('type', SecretType.API_KEY.value)),
                version=meta.get('version', 1),
                created_at=datetime.fromisoformat(meta['created_at']) if meta.get('created_at') else datetime.utcnow(),
                updated_at=datetime.fromisoformat(meta['updated_at']) if meta.get('updated_at') else datetime.utcnow(),
                expires_at=datetime.fromisoformat(meta['expires_at']) if meta.get('expires_at') else None,
                rotation_interval_days=meta.get('rotation_interval_days'),
                last_rotated=datetime.fromisoformat(meta['last_rotated']) if meta.get('last_rotated') else None,
                tags=meta.get('tags', {}),
                description=meta.get('description')
            )
        return None
    
    def health_check(self) -> bool:
        """Check local storage health."""
        try:
            # Test encryption/decryption
            test_data = b"health_check_test"
            encrypted = self._fernet.encrypt(test_data)
            decrypted = self._fernet.decrypt(encrypted)
            return decrypted == test_data
        except Exception as e:
            logger.error(f"Local storage health check failed: {e}")
            return False


class SecretsManager:
    """
    Main secrets management class that coordinates between providers.
    Implements caching, rotation, audit logging, and fallback mechanisms.
    """
    
    def __init__(self, config: Optional[SecretConfig] = None):
        """Initialize the secrets manager."""
        self.config = config or SecretConfig.from_env()
        self._providers: Dict[SecretProvider, SecretProviderInterface] = {}
        self._cache: Dict[str, Tuple[str, datetime]] = {}
        self._audit_log: List[Dict] = []
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize configured secret providers."""
        # Initialize primary provider
        self._providers[self.config.primary_provider] = self._create_provider(
            self.config.primary_provider
        )
        
        # Initialize fallback providers
        for provider_type in self.config.fallback_providers:
            if provider_type not in self._providers:
                try:
                    self._providers[provider_type] = self._create_provider(provider_type)
                except Exception as e:
                    logger.warning(f"Failed to initialize fallback provider {provider_type}: {e}")
    
    def _create_provider(self, provider_type: SecretProvider) -> SecretProviderInterface:
        """Create a provider instance based on type."""
        if provider_type == SecretProvider.VAULT:
            return VaultProvider(self.config)
        elif provider_type == SecretProvider.AWS_SECRETS_MANAGER:
            return AWSSecretsManagerProvider(self.config)
        elif provider_type == SecretProvider.LOCAL_ENCRYPTED:
            return LocalEncryptedProvider(self.config)
        else:
            # Environment provider (simple fallback)
            raise NotImplementedError(f"Provider {provider_type} not implemented")
    
    def _audit_log_operation(
        self,
        operation: str,
        key: str,
        success: bool,
        provider: Optional[SecretProvider] = None,
        error: Optional[str] = None
    ):
        """Log an operation for audit purposes."""
        if self.config.enable_audit_logging:
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'operation': operation,
                'key': key,
                'success': success,
                'provider': provider.value if provider else None,
                'environment': self.config.environment,
                'error': error
            }
            self._audit_log.append(log_entry)
            
            # Also log to standard logger
            if success:
                logger.info(f"Secret operation: {operation} on {key} succeeded")
            else:
                logger.error(f"Secret operation: {operation} on {key} failed: {error}")
    
    def _get_from_cache(self, key: str) -> Optional[str]:
        """Get a secret from cache if available and not expired."""
        if not self.config.cache_enabled:
            return None
        
        if key in self._cache:
            value, cached_at = self._cache[key]
            if (datetime.utcnow() - cached_at).total_seconds() < self.config.cache_ttl_seconds:
                return value
            else:
                del self._cache[key]
        
        return None
    
    def _set_cache(self, key: str, value: str):
        """Store a secret in cache."""
        if self.config.cache_enabled:
            self._cache[key] = (value, datetime.utcnow())
    
    def get_secret(
        self,
        key: str,
        secret_type: Optional[SecretType] = None,
        use_cache: bool = True,
        version: Optional[str] = None
    ) -> Optional[str]:
        """
        Retrieve a secret with fallback support.
        
        Args:
            key: Secret key
            secret_type: Type of secret (for validation)
            use_cache: Whether to use cache
            version: Specific version to retrieve
        
        Returns:
            Secret value or None if not found
        """
        # Check cache first
        if use_cache:
            cached_value = self._get_from_cache(key)
            if cached_value:
                return cached_value
        
        # Try primary provider
        primary_provider = self._providers.get(self.config.primary_provider)
        if primary_provider and primary_provider.health_check():
            value = primary_provider.get_secret(key, version)
            if value:
                self._set_cache(key, value)
                self._audit_log_operation('get', key, True, self.config.primary_provider)
                return value
        
        # Try fallback providers
        for provider_type, provider in self._providers.items():
            if provider_type == self.config.primary_provider:
                continue
            
            if provider.health_check():
                value = provider.get_secret(key, version)
                if value:
                    self._set_cache(key, value)
                    self._audit_log_operation('get', key, True, provider_type)
                    logger.warning(f"Retrieved secret from fallback provider: {provider_type}")
                    return value
        
        # Try environment variables as last resort
        env_key = f"{self.config.application_name.upper()}_{key.upper()}"
        env_value = os.getenv(env_key)
        if env_value:
            self._set_cache(key, env_value)
            self._audit_log_operation('get', key, True, SecretProvider.ENVIRONMENT)
            return env_value
        
        self._audit_log_operation('get', key, False, error="Secret not found in any provider")
        return None
    
    def set_secret(
        self,
        key: str,
        value: str,
        secret_type: SecretType,
        rotation_interval_days: Optional[int] = None,
        expires_in_days: Optional[int] = None,
        tags: Optional[Dict[str, str]] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Store a secret in the primary provider.
        
        Args:
            key: Secret key
            value: Secret value
            secret_type: Type of secret
            rotation_interval_days: Auto-rotation interval
            expires_in_days: Expiration time
            tags: Additional tags
            description: Secret description
        
        Returns:
            True if successful
        """
        metadata = SecretMetadata(
            name=key,
            type=secret_type,
            rotation_interval_days=rotation_interval_days,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None,
            tags=tags or {},
            description=description
        )
        
        primary_provider = self._providers.get(self.config.primary_provider)
        if primary_provider:
            success = primary_provider.set_secret(key, value, metadata)
            self._audit_log_operation('set', key, success, self.config.primary_provider)
            
            if success:
                # Clear cache for this key
                if key in self._cache:
                    del self._cache[key]
            
            return success
        
        self._audit_log_operation('set', key, False, error="Primary provider not available")
        return False
    
    def rotate_secret(self, key: str, new_value: str) -> bool:
        """
        Rotate a secret to a new value.
        
        Args:
            key: Secret key
            new_value: New secret value
        
        Returns:
            True if successful
        """
        primary_provider = self._providers.get(self.config.primary_provider)
        if primary_provider:
            success = primary_provider.rotate_secret(key, new_value)
            self._audit_log_operation('rotate', key, success, self.config.primary_provider)
            
            if success:
                # Clear cache for this key
                if key in self._cache:
                    del self._cache[key]
            
            return success
        
        self._audit_log_operation('rotate', key, False, error="Primary provider not available")
        return False
    
    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret from all providers.
        
        Args:
            key: Secret key
        
        Returns:
            True if deleted from at least one provider
        """
        deleted = False
        
        for provider_type, provider in self._providers.items():
            if provider.health_check():
                if provider.delete_secret(key):
                    deleted = True
                    self._audit_log_operation('delete', key, True, provider_type)
        
        # Clear cache
        if key in self._cache:
            del self._cache[key]
        
        if not deleted:
            self._audit_log_operation('delete', key, False, error="Failed to delete from any provider")
        
        return deleted
    
    def list_secrets(self, prefix: Optional[str] = None) -> List[str]:
        """
        List all available secrets.
        
        Args:
            prefix: Optional prefix filter
        
        Returns:
            List of secret keys
        """
        all_secrets = set()
        
        for provider_type, provider in self._providers.items():
            if provider.health_check():
                secrets = provider.list_secrets(prefix)
                all_secrets.update(secrets)
        
        return sorted(list(all_secrets))
    
    def check_rotation_needed(self) -> List[Tuple[str, SecretMetadata]]:
        """
        Check which secrets need rotation.
        
        Returns:
            List of (key, metadata) tuples for secrets needing rotation
        """
        secrets_to_rotate = []
        
        for key in self.list_secrets():
            metadata = self.get_secret_metadata(key)
            if metadata and metadata.rotation_interval_days:
                if metadata.last_rotated:
                    days_since_rotation = (datetime.utcnow() - metadata.last_rotated).days
                    if days_since_rotation >= metadata.rotation_interval_days:
                        secrets_to_rotate.append((key, metadata))
                else:
                    # Never rotated, check creation date
                    days_since_creation = (datetime.utcnow() - metadata.created_at).days
                    if days_since_creation >= metadata.rotation_interval_days:
                        secrets_to_rotate.append((key, metadata))
        
        return secrets_to_rotate
    
    def get_secret_metadata(self, key: str) -> Optional[SecretMetadata]:
        """
        Get metadata for a secret.
        
        Args:
            key: Secret key
        
        Returns:
            Secret metadata or None
        """
        primary_provider = self._providers.get(self.config.primary_provider)
        if primary_provider and primary_provider.health_check():
            return primary_provider.get_secret_metadata(key)
        
        # Try fallback providers
        for provider_type, provider in self._providers.items():
            if provider_type == self.config.primary_provider:
                continue
            
            if provider.health_check():
                metadata = provider.get_secret_metadata(key)
                if metadata:
                    return metadata
        
        return None
    
    def health_check(self) -> Dict[str, bool]:
        """
        Check health of all providers.
        
        Returns:
            Dictionary of provider health status
        """
        health = {}
        
        for provider_type, provider in self._providers.items():
            health[provider_type.value] = provider.health_check()
        
        return health
    
    def get_audit_log(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        operation: Optional[str] = None
    ) -> List[Dict]:
        """
        Get audit log entries.
        
        Args:
            start_time: Filter by start time
            end_time: Filter by end time
            operation: Filter by operation type
        
        Returns:
            List of audit log entries
        """
        logs = self._audit_log
        
        if start_time:
            logs = [l for l in logs if datetime.fromisoformat(l['timestamp']) >= start_time]
        
        if end_time:
            logs = [l for l in logs if datetime.fromisoformat(l['timestamp']) <= end_time]
        
        if operation:
            logs = [l for l in logs if l['operation'] == operation]
        
        return logs
    
    # Convenience methods for specific secret types
    
    def get_database_url(self) -> Optional[str]:
        """Get database connection URL."""
        return self.get_secret("database_url", SecretType.DATABASE_URL)
    
    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a specific service."""
        return self.get_secret(f"api_key_{service}", SecretType.API_KEY)
    
    def get_jwt_keys(self) -> Tuple[Optional[str], Optional[str]]:
        """Get JWT private and public keys."""
        private_key = self.get_secret("jwt_private_key", SecretType.JWT_PRIVATE_KEY)
        public_key = self.get_secret("jwt_public_key", SecretType.JWT_PUBLIC_KEY)
        return private_key, public_key
    
    def get_redis_url(self) -> Optional[str]:
        """Get Redis connection URL."""
        return self.get_secret("redis_url", SecretType.REDIS_URL)
    
    def get_smtp_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Get SMTP username and password."""
        username = self.get_secret("smtp_username")
        password = self.get_secret("smtp_password", SecretType.SMTP_PASSWORD)
        return username, password


# Global instance for easy access
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Get or create the global secrets manager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def initialize_secrets_manager(config: Optional[SecretConfig] = None) -> SecretsManager:
    """Initialize the global secrets manager with configuration."""
    global _secrets_manager
    _secrets_manager = SecretsManager(config)
    return _secrets_manager