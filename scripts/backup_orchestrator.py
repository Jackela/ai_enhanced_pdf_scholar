#!/usr/bin/env python3
"""
Enterprise Multi-Tier Backup Orchestrator
Implements automated backup with 7 daily, 4 weekly, 12 monthly, 7 yearly retention policy.
Supports PostgreSQL, Redis, file system, and vector indexes with 15-minute intervals.
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiofiles
import boto3
import psutil
from botocore.exceptions import ClientError

# Add backend to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from backend.core.secrets import get_secrets_manager, SecretType
from backend.services.health_check_service import HealthCheckService
from backend.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class BackupTier(str, Enum):
    """Backup tier classifications."""
    CRITICAL = "critical"      # Every 15 minutes
    HIGH = "high"              # Hourly  
    MEDIUM = "medium"          # Daily
    LOW = "low"                # Weekly


class BackupType(str, Enum):
    """Types of backups."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    LOG = "log"


class BackupStatus(str, Enum):
    """Backup operation status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class StorageProvider(str, Enum):
    """Backup storage providers."""
    LOCAL = "local"
    AWS_S3 = "aws_s3"
    AZURE_BLOB = "azure_blob"
    GCP_STORAGE = "gcp_storage"


@dataclass
class BackupConfig:
    """Configuration for backup orchestration."""
    # Backup intervals (in minutes)
    critical_interval: int = 15
    high_interval: int = 60
    medium_interval: int = 1440  # 24 hours
    low_interval: int = 10080    # 7 days
    
    # Retention policies
    daily_retention: int = 7
    weekly_retention: int = 4
    monthly_retention: int = 12
    yearly_retention: int = 7
    
    # Storage configuration
    primary_storage: StorageProvider = StorageProvider.LOCAL
    secondary_storage: Optional[StorageProvider] = StorageProvider.AWS_S3
    backup_base_path: str = "/var/backups/ai_pdf_scholar"
    s3_bucket: Optional[str] = None
    s3_region: str = "us-east-1"
    
    # Compression and encryption
    enable_compression: bool = True
    enable_encryption: bool = True
    compression_level: int = 6
    
    # Performance settings
    max_concurrent_backups: int = 3
    backup_timeout_minutes: int = 60
    verification_enabled: bool = True
    
    # Health monitoring
    send_notifications: bool = True
    health_check_interval: int = 300  # 5 minutes


@dataclass
class BackupMetadata:
    """Metadata for a backup."""
    backup_id: str
    backup_type: BackupType
    tier: BackupTier
    source_type: str
    source_path: str
    backup_path: str
    storage_provider: StorageProvider
    size_bytes: int
    checksum: str
    created_at: datetime
    expires_at: datetime
    status: BackupStatus
    compression_ratio: float = 0.0
    verification_status: bool = False
    tags: Dict[str, str] = field(default_factory=dict)
    error_message: Optional[str] = None


class BackupSource:
    """Base class for backup sources."""
    
    def __init__(self, name: str, tier: BackupTier, source_path: str):
        self.name = name
        self.tier = tier
        self.source_path = source_path
        self.last_backup: Optional[datetime] = None
        self.last_backup_size: int = 0
    
    async def create_backup(self, backup_path: str, backup_type: BackupType) -> Tuple[bool, Optional[str]]:
        """Create a backup of this source. Returns (success, error_message)."""
        raise NotImplementedError
    
    async def verify_backup(self, backup_path: str) -> bool:
        """Verify the integrity of a backup."""
        return os.path.exists(backup_path)
    
    def should_backup(self, interval_minutes: int) -> bool:
        """Check if this source should be backed up based on interval."""
        if not self.last_backup:
            return True
        
        elapsed = (datetime.utcnow() - self.last_backup).total_seconds() / 60
        return elapsed >= interval_minutes


class PostgreSQLBackupSource(BackupSource):
    """PostgreSQL database backup source."""
    
    def __init__(self, name: str, tier: BackupTier, connection_url: str):
        super().__init__(name, tier, connection_url)
        self.connection_url = connection_url
        self._parse_connection()
    
    def _parse_connection(self):
        """Parse PostgreSQL connection URL."""
        parsed = urlparse(self.connection_url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 5432
        self.database = parsed.path.lstrip('/')
        self.username = parsed.username
        self.password = parsed.password
    
    async def create_backup(self, backup_path: str, backup_type: BackupType) -> Tuple[bool, Optional[str]]:
        """Create PostgreSQL backup using pg_dump."""
        try:
            # Prepare environment
            env = os.environ.copy()
            if self.password:
                env['PGPASSWORD'] = self.password
            
            # Build pg_dump command
            cmd = [
                'pg_dump',
                '--host', self.host,
                '--port', str(self.port),
                '--username', self.username,
                '--dbname', self.database,
                '--format', 'custom',
                '--compress', '9',
                '--verbose',
                '--file', backup_path
            ]
            
            if backup_type == BackupType.INCREMENTAL:
                # For incremental, we'll use WAL-based backup
                cmd.extend(['--create', '--clean'])
            
            # Execute backup
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.last_backup = datetime.utcnow()
                if os.path.exists(backup_path):
                    self.last_backup_size = os.path.getsize(backup_path)
                return True, None
            else:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown pg_dump error"
                return False, f"pg_dump failed: {error_msg}"
        
        except Exception as e:
            return False, f"PostgreSQL backup failed: {str(e)}"
    
    async def verify_backup(self, backup_path: str) -> bool:
        """Verify PostgreSQL backup using pg_restore --list."""
        try:
            if not os.path.exists(backup_path):
                return False
            
            # Use pg_restore to list contents
            cmd = ['pg_restore', '--list', backup_path]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # If pg_restore can list the backup, it's valid
            return process.returncode == 0 and len(stdout) > 0
        
        except Exception as e:
            logger.error(f"PostgreSQL backup verification failed: {e}")
            return False


class RedisBackupSource(BackupSource):
    """Redis backup source."""
    
    def __init__(self, name: str, tier: BackupTier, connection_url: str):
        super().__init__(name, tier, connection_url)
        self.connection_url = connection_url
        self._parse_connection()
    
    def _parse_connection(self):
        """Parse Redis connection URL."""
        parsed = urlparse(self.connection_url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 6379
        self.password = parsed.password
        self.database = int(parsed.path.lstrip('/')) if parsed.path.lstrip('/') else 0
    
    async def create_backup(self, backup_path: str, backup_type: BackupType) -> Tuple[bool, Optional[str]]:
        """Create Redis backup using BGSAVE or RDB copy."""
        try:
            import redis
            
            # Connect to Redis
            redis_client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.database,
                password=self.password,
                decode_responses=False
            )
            
            # Test connection
            redis_client.ping()
            
            if backup_type == BackupType.FULL:
                # Trigger background save
                result = redis_client.bgsave()
                
                # Wait for background save to complete
                while redis_client.info()['bgsave_in_progress']:
                    await asyncio.sleep(1)
                
                # Copy RDB file
                redis_info = redis_client.info()
                rdb_path = redis_info.get('rdb_filename', 'dump.rdb')
                rdb_dir = redis_info.get('dir', '/var/lib/redis')
                source_rdb = os.path.join(rdb_dir, rdb_path)
                
                if os.path.exists(source_rdb):
                    shutil.copy2(source_rdb, backup_path)
                    self.last_backup = datetime.utcnow()
                    self.last_backup_size = os.path.getsize(backup_path)
                    return True, None
                else:
                    return False, f"Redis RDB file not found at {source_rdb}"
            
            else:
                # For incremental/differential, save all keys to JSON
                all_keys = redis_client.keys('*')
                backup_data = {}
                
                for key in all_keys:
                    key_type = redis_client.type(key)
                    
                    if key_type == b'string':
                        backup_data[key.decode()] = redis_client.get(key).decode()
                    elif key_type == b'hash':
                        backup_data[key.decode()] = {
                            k.decode(): v.decode() 
                            for k, v in redis_client.hgetall(key).items()
                        }
                    elif key_type == b'list':
                        backup_data[key.decode()] = [
                            item.decode() for item in redis_client.lrange(key, 0, -1)
                        ]
                    elif key_type == b'set':
                        backup_data[key.decode()] = [
                            item.decode() for item in redis_client.smembers(key)
                        ]
                
                # Save to JSON file
                async with aiofiles.open(backup_path, 'w') as f:
                    await f.write(json.dumps(backup_data, indent=2))
                
                self.last_backup = datetime.utcnow()
                self.last_backup_size = os.path.getsize(backup_path)
                return True, None
        
        except Exception as e:
            return False, f"Redis backup failed: {str(e)}"


class FileSystemBackupSource(BackupSource):
    """File system backup source."""
    
    def __init__(self, name: str, tier: BackupTier, source_path: str, exclude_patterns: Optional[List[str]] = None):
        super().__init__(name, tier, source_path)
        self.exclude_patterns = exclude_patterns or []
    
    async def create_backup(self, backup_path: str, backup_type: BackupType) -> Tuple[bool, Optional[str]]:
        """Create file system backup using tar with compression."""
        try:
            # Ensure source path exists
            if not os.path.exists(self.source_path):
                return False, f"Source path does not exist: {self.source_path}"
            
            # Build tar command
            cmd = ['tar', '-czf', backup_path, '-C', os.path.dirname(self.source_path)]
            
            # Add exclusions
            for pattern in self.exclude_patterns:
                cmd.extend(['--exclude', pattern])
            
            # Add source directory
            cmd.append(os.path.basename(self.source_path))
            
            # Execute backup
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                self.last_backup = datetime.utcnow()
                if os.path.exists(backup_path):
                    self.last_backup_size = os.path.getsize(backup_path)
                return True, None
            else:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown tar error"
                return False, f"File system backup failed: {error_msg}"
        
        except Exception as e:
            return False, f"File system backup failed: {str(e)}"
    
    async def verify_backup(self, backup_path: str) -> bool:
        """Verify file system backup using tar -tf."""
        try:
            if not os.path.exists(backup_path):
                return False
            
            # List archive contents
            cmd = ['tar', '-tzf', backup_path]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # If tar can list the archive, it's valid
            return process.returncode == 0 and len(stdout) > 0
        
        except Exception as e:
            logger.error(f"File system backup verification failed: {e}")
            return False


class S3StorageProvider:
    """AWS S3 storage provider for backups."""
    
    def __init__(self, bucket: str, region: str = "us-east-1", prefix: str = ""):
        self.bucket = bucket
        self.region = region
        self.prefix = prefix
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of S3 client."""
        if self._client is None:
            self._client = boto3.client('s3', region_name=self.region)
        return self._client
    
    async def upload_backup(self, local_path: str, remote_key: str) -> bool:
        """Upload backup to S3."""
        try:
            full_key = f"{self.prefix}/{remote_key}".strip('/')
            
            # Upload with server-side encryption
            self.client.upload_file(
                local_path,
                self.bucket,
                full_key,
                ExtraArgs={
                    'ServerSideEncryption': 'AES256',
                    'StorageClass': 'STANDARD_IA'  # Infrequent Access for backups
                }
            )
            
            return True
        
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return False
    
    async def download_backup(self, remote_key: str, local_path: str) -> bool:
        """Download backup from S3."""
        try:
            full_key = f"{self.prefix}/{remote_key}".strip('/')
            
            self.client.download_file(
                self.bucket,
                full_key,
                local_path
            )
            
            return True
        
        except Exception as e:
            logger.error(f"S3 download failed: {e}")
            return False
    
    async def list_backups(self, prefix_filter: str = "") -> List[str]:
        """List backups in S3."""
        try:
            full_prefix = f"{self.prefix}/{prefix_filter}".strip('/')
            
            response = self.client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=full_prefix
            )
            
            keys = []
            if 'Contents' in response:
                keys = [obj['Key'] for obj in response['Contents']]
            
            return keys
        
        except Exception as e:
            logger.error(f"S3 list failed: {e}")
            return []
    
    async def delete_backup(self, remote_key: str) -> bool:
        """Delete backup from S3."""
        try:
            full_key = f"{self.prefix}/{remote_key}".strip('/')
            
            self.client.delete_object(
                Bucket=self.bucket,
                Key=full_key
            )
            
            return True
        
        except Exception as e:
            logger.error(f"S3 delete failed: {e}")
            return False


class BackupOrchestrator:
    """Main backup orchestration system."""
    
    def __init__(self, config: Optional[BackupConfig] = None):
        """Initialize backup orchestrator."""
        self.config = config or BackupConfig()
        self.sources: List[BackupSource] = []
        self.storage_providers: Dict[StorageProvider, Any] = {}
        self.backup_metadata: Dict[str, BackupMetadata] = {}
        self.running = False
        self.backup_semaphore = asyncio.Semaphore(self.config.max_concurrent_backups)
        
        # Initialize logging
        self._setup_logging()
        
        # Initialize services
        self.secrets_manager = get_secrets_manager()
        self.health_service = HealthCheckService()
        self.metrics_service = MetricsService()
        
        # Initialize storage providers
        self._initialize_storage_providers()
        
        # Create backup directories
        self._create_backup_directories()
    
    def _setup_logging(self):
        """Configure logging for backup operations."""
        log_path = Path(self.config.backup_base_path) / "logs"
        log_path.mkdir(parents=True, exist_ok=True)
        
        handler = logging.FileHandler(log_path / "backup_orchestrator.log")
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    def _initialize_storage_providers(self):
        """Initialize backup storage providers."""
        # Local storage (always available)
        self.storage_providers[StorageProvider.LOCAL] = True
        
        # AWS S3 storage
        if self.config.secondary_storage == StorageProvider.AWS_S3 and self.config.s3_bucket:
            try:
                s3_provider = S3StorageProvider(
                    bucket=self.config.s3_bucket,
                    region=self.config.s3_region,
                    prefix=f"ai_pdf_scholar_backups"
                )
                self.storage_providers[StorageProvider.AWS_S3] = s3_provider
                logger.info("Initialized S3 storage provider")
            except Exception as e:
                logger.error(f"Failed to initialize S3 storage: {e}")
    
    def _create_backup_directories(self):
        """Create necessary backup directory structure."""
        base_path = Path(self.config.backup_base_path)
        
        directories = [
            base_path,
            base_path / "daily",
            base_path / "weekly", 
            base_path / "monthly",
            base_path / "yearly",
            base_path / "logs",
            base_path / "temp"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def register_source(self, source: BackupSource):
        """Register a backup source."""
        self.sources.append(source)
        logger.info(f"Registered backup source: {source.name} (tier: {source.tier.value})")
    
    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of a file."""
        hash_sha256 = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        
        return hash_sha256.hexdigest()
    
    def _get_retention_period(self, backup_type: str) -> timedelta:
        """Get retention period based on backup type."""
        retention_map = {
            "daily": timedelta(days=self.config.daily_retention),
            "weekly": timedelta(weeks=self.config.weekly_retention),
            "monthly": timedelta(days=self.config.monthly_retention * 30),
            "yearly": timedelta(days=self.config.yearly_retention * 365)
        }
        return retention_map.get(backup_type, timedelta(days=7))
    
    async def create_backup(
        self,
        source: BackupSource,
        backup_type: BackupType = BackupType.FULL,
        retention_type: str = "daily"
    ) -> Optional[BackupMetadata]:
        """Create a backup for a specific source."""
        async with self.backup_semaphore:
            start_time = time.time()
            backup_id = f"{source.name}_{backup_type.value}_{int(start_time)}"
            
            try:
                # Determine backup path
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                filename = f"{source.name}_{backup_type.value}_{timestamp}"
                
                if source.name.startswith('postgres'):
                    filename += ".dump"
                elif source.name.startswith('redis'):
                    filename += ".rdb" if backup_type == BackupType.FULL else ".json"
                else:
                    filename += ".tar.gz"
                
                backup_path = os.path.join(
                    self.config.backup_base_path,
                    retention_type,
                    filename
                )
                
                # Create backup metadata
                metadata = BackupMetadata(
                    backup_id=backup_id,
                    backup_type=backup_type,
                    tier=source.tier,
                    source_type=type(source).__name__,
                    source_path=source.source_path,
                    backup_path=backup_path,
                    storage_provider=StorageProvider.LOCAL,
                    size_bytes=0,
                    checksum="",
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + self._get_retention_period(retention_type),
                    status=BackupStatus.RUNNING
                )
                
                # Create the backup
                success, error_msg = await source.create_backup(backup_path, backup_type)
                
                if success and os.path.exists(backup_path):
                    # Update metadata with actual file info
                    metadata.size_bytes = os.path.getsize(backup_path)
                    metadata.checksum = self._calculate_checksum(backup_path)
                    metadata.status = BackupStatus.COMPLETED
                    
                    # Calculate compression ratio for compressed backups
                    if source.source_path and os.path.exists(source.source_path):
                        if os.path.isdir(source.source_path):
                            # Calculate directory size
                            original_size = sum(
                                os.path.getsize(os.path.join(dirpath, filename))
                                for dirpath, dirnames, filenames in os.walk(source.source_path)
                                for filename in filenames
                            )
                        else:
                            original_size = os.path.getsize(source.source_path)
                        
                        if original_size > 0:
                            metadata.compression_ratio = metadata.size_bytes / original_size
                    
                    # Verify backup if enabled
                    if self.config.verification_enabled:
                        metadata.verification_status = await source.verify_backup(backup_path)
                        if not metadata.verification_status:
                            logger.warning(f"Backup verification failed for {backup_id}")
                    
                    # Upload to secondary storage if configured
                    if StorageProvider.AWS_S3 in self.storage_providers:
                        s3_provider = self.storage_providers[StorageProvider.AWS_S3]
                        s3_key = f"{retention_type}/{filename}"
                        
                        upload_success = await s3_provider.upload_backup(backup_path, s3_key)
                        if upload_success:
                            logger.info(f"Backup uploaded to S3: {s3_key}")
                        else:
                            logger.warning(f"Failed to upload backup to S3: {s3_key}")
                    
                    # Store metadata
                    self.backup_metadata[backup_id] = metadata
                    
                    # Update metrics
                    await self.metrics_service.record_counter(
                        "backup_completed",
                        tags={"source": source.name, "type": backup_type.value}
                    )
                    
                    await self.metrics_service.record_histogram(
                        "backup_duration_seconds",
                        time.time() - start_time,
                        tags={"source": source.name, "type": backup_type.value}
                    )
                    
                    await self.metrics_service.record_gauge(
                        "backup_size_bytes",
                        metadata.size_bytes,
                        tags={"source": source.name, "type": backup_type.value}
                    )
                    
                    logger.info(f"Backup completed successfully: {backup_id} ({metadata.size_bytes} bytes)")
                    return metadata
                
                else:
                    # Backup failed
                    metadata.status = BackupStatus.FAILED
                    metadata.error_message = error_msg
                    self.backup_metadata[backup_id] = metadata
                    
                    # Update failure metrics
                    await self.metrics_service.record_counter(
                        "backup_failed",
                        tags={"source": source.name, "type": backup_type.value}
                    )
                    
                    logger.error(f"Backup failed: {backup_id} - {error_msg}")
                    return metadata
            
            except Exception as e:
                # Handle unexpected errors
                error_msg = f"Unexpected backup error: {str(e)}"
                
                metadata = BackupMetadata(
                    backup_id=backup_id,
                    backup_type=backup_type,
                    tier=source.tier,
                    source_type=type(source).__name__,
                    source_path=source.source_path,
                    backup_path="",
                    storage_provider=StorageProvider.LOCAL,
                    size_bytes=0,
                    checksum="",
                    created_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + self._get_retention_period(retention_type),
                    status=BackupStatus.FAILED,
                    error_message=error_msg
                )
                
                self.backup_metadata[backup_id] = metadata
                logger.error(f"Backup error: {backup_id} - {error_msg}")
                return metadata
    
    async def cleanup_expired_backups(self):
        """Clean up expired backups based on retention policies."""
        now = datetime.utcnow()
        cleaned_count = 0
        
        for backup_id, metadata in list(self.backup_metadata.items()):
            if now > metadata.expires_at:
                # Remove local file
                if os.path.exists(metadata.backup_path):
                    try:
                        os.remove(metadata.backup_path)
                        cleaned_count += 1
                        logger.info(f"Cleaned up expired backup: {backup_id}")
                    except Exception as e:
                        logger.error(f"Failed to remove backup file {metadata.backup_path}: {e}")
                
                # Remove from S3 if applicable
                if metadata.storage_provider == StorageProvider.AWS_S3:
                    s3_provider = self.storage_providers.get(StorageProvider.AWS_S3)
                    if s3_provider:
                        s3_key = os.path.basename(metadata.backup_path)
                        await s3_provider.delete_backup(s3_key)
                
                # Remove metadata
                metadata.status = BackupStatus.EXPIRED
                del self.backup_metadata[backup_id]
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired backups")
    
    async def backup_cycle(self):
        """Execute one backup cycle for all sources."""
        now = datetime.utcnow()
        cycle_start = time.time()
        
        # Determine what needs backing up based on intervals
        for source in self.sources:
            try:
                # Check if backup is needed based on tier
                interval_minutes = {
                    BackupTier.CRITICAL: self.config.critical_interval,
                    BackupTier.HIGH: self.config.high_interval,
                    BackupTier.MEDIUM: self.config.medium_interval,
                    BackupTier.LOW: self.config.low_interval
                }.get(source.tier, self.config.medium_interval)
                
                if source.should_backup(interval_minutes):
                    # Determine backup type and retention
                    if source.tier in [BackupTier.CRITICAL, BackupTier.HIGH]:
                        backup_type = BackupType.INCREMENTAL
                        retention_type = "daily"
                    else:
                        backup_type = BackupType.FULL
                        retention_type = "daily"
                    
                    # Create weekly backup on Sundays
                    if now.weekday() == 6:  # Sunday
                        retention_type = "weekly"
                        backup_type = BackupType.FULL
                    
                    # Create monthly backup on 1st of month
                    if now.day == 1:
                        retention_type = "monthly"
                        backup_type = BackupType.FULL
                    
                    # Create yearly backup on Jan 1st
                    if now.month == 1 and now.day == 1:
                        retention_type = "yearly"
                        backup_type = BackupType.FULL
                    
                    logger.info(f"Starting backup: {source.name} ({backup_type.value}, {retention_type})")
                    
                    # Create the backup
                    metadata = await self.create_backup(source, backup_type, retention_type)
                    
                    if metadata and metadata.status == BackupStatus.COMPLETED:
                        logger.info(f"Backup successful: {source.name}")
                    else:
                        logger.error(f"Backup failed: {source.name}")
            
            except Exception as e:
                logger.error(f"Error backing up {source.name}: {e}")
        
        # Clean up expired backups
        await self.cleanup_expired_backups()
        
        # Log cycle completion
        cycle_duration = time.time() - cycle_start
        logger.info(f"Backup cycle completed in {cycle_duration:.2f} seconds")
    
    async def start_orchestrator(self):
        """Start the backup orchestration service."""
        logger.info("Starting backup orchestrator")
        self.running = True
        
        while self.running:
            try:
                await self.backup_cycle()
                
                # Wait for next cycle (minimum 1 minute)
                sleep_time = max(60, min(self.config.critical_interval * 60, 300))
                await asyncio.sleep(sleep_time)
            
            except Exception as e:
                logger.error(f"Error in backup orchestrator main loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    def stop_orchestrator(self):
        """Stop the backup orchestrator."""
        logger.info("Stopping backup orchestrator")
        self.running = False
    
    def get_backup_status(self) -> Dict[str, Any]:
        """Get current backup status."""
        now = datetime.utcnow()
        
        # Count backups by status
        status_counts = {}
        for metadata in self.backup_metadata.values():
            status_counts[metadata.status.value] = status_counts.get(metadata.status.value, 0) + 1
        
        # Count backups by tier
        tier_counts = {}
        for metadata in self.backup_metadata.values():
            tier_counts[metadata.tier.value] = tier_counts.get(metadata.tier.value, 0) + 1
        
        # Calculate total backup size
        total_size = sum(metadata.size_bytes for metadata in self.backup_metadata.values())
        
        # Count recent backups (last 24 hours)
        recent_backups = len([
            m for m in self.backup_metadata.values() 
            if (now - m.created_at).total_seconds() < 86400
        ])
        
        return {
            "orchestrator_running": self.running,
            "total_backups": len(self.backup_metadata),
            "recent_backups_24h": recent_backups,
            "total_backup_size_bytes": total_size,
            "status_counts": status_counts,
            "tier_counts": tier_counts,
            "registered_sources": len(self.sources),
            "storage_providers": list(self.storage_providers.keys()),
            "last_cleanup": now.isoformat()
        }


async def main():
    """Main entry point for backup orchestrator."""
    # Load configuration
    config = BackupConfig()
    
    # Initialize orchestrator
    orchestrator = BackupOrchestrator(config)
    
    # Get database connection from secrets
    secrets_manager = get_secrets_manager()
    db_url = secrets_manager.get_database_url()
    redis_url = secrets_manager.get_redis_url()
    
    # Register backup sources
    if db_url:
        postgres_source = PostgreSQLBackupSource(
            name="postgres_main",
            tier=BackupTier.CRITICAL,
            connection_url=db_url
        )
        orchestrator.register_source(postgres_source)
    
    if redis_url:
        redis_source = RedisBackupSource(
            name="redis_cache",
            tier=BackupTier.HIGH,
            connection_url=redis_url
        )
        orchestrator.register_source(redis_source)
    
    # Register file system sources
    data_paths = [
        ("documents", "/app/data/documents", BackupTier.HIGH),
        ("vector_indexes", "/app/data/vector_indexes", BackupTier.HIGH),
        ("uploads", "/app/uploads", BackupTier.MEDIUM),
        ("logs", "/app/logs", BackupTier.LOW)
    ]
    
    for name, path, tier in data_paths:
        if os.path.exists(path):
            fs_source = FileSystemBackupSource(
                name=name,
                tier=tier,
                source_path=path,
                exclude_patterns=["*.tmp", "*.lock", "__pycache__"]
            )
            orchestrator.register_source(fs_source)
    
    # Start orchestrator
    try:
        await orchestrator.start_orchestrator()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        orchestrator.stop_orchestrator()
        logger.info("Backup orchestrator stopped")


if __name__ == "__main__":
    asyncio.run(main())