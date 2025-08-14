"""
Comprehensive Audit Logging Service
Production-ready audit trail system for compliance and security monitoring.
"""

import hashlib
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime, Boolean,
    ForeignKey, Index, JSON, create_engine, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

Base = declarative_base()


# ============================================================================
# Audit Log Models
# ============================================================================

class AuditEventType(str, Enum):
    """Types of audit events."""
    # Authentication events
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_REGISTER = "user.register"
    PASSWORD_CHANGE = "user.password_change"
    PASSWORD_RESET = "user.password_reset"
    MFA_ENABLE = "user.mfa_enable"
    MFA_DISABLE = "user.mfa_disable"

    # Authorization events
    PERMISSION_GRANTED = "auth.permission_granted"
    PERMISSION_DENIED = "auth.permission_denied"
    ROLE_ASSIGNED = "auth.role_assigned"
    ROLE_REVOKED = "auth.role_revoked"

    # Data access events
    DATA_READ = "data.read"
    DATA_CREATE = "data.create"
    DATA_UPDATE = "data.update"
    DATA_DELETE = "data.delete"
    DATA_EXPORT = "data.export"
    DATA_IMPORT = "data.import"

    # Document events
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_DOWNLOAD = "document.download"
    DOCUMENT_VIEW = "document.view"
    DOCUMENT_DELETE = "document.delete"
    DOCUMENT_SHARE = "document.share"

    # System events
    SYSTEM_START = "system.start"
    SYSTEM_STOP = "system.stop"
    CONFIG_CHANGE = "system.config_change"
    BACKUP_CREATE = "system.backup_create"
    BACKUP_RESTORE = "system.backup_restore"

    # Security events
    SECURITY_ALERT = "security.alert"
    INTRUSION_ATTEMPT = "security.intrusion_attempt"
    BRUTE_FORCE = "security.brute_force"
    SQL_INJECTION = "security.sql_injection"
    XSS_ATTEMPT = "security.xss_attempt"

    # Compliance events
    CONSENT_GIVEN = "compliance.consent_given"
    CONSENT_WITHDRAWN = "compliance.consent_withdrawn"
    DATA_REQUEST = "compliance.data_request"
    DATA_DELETION = "compliance.data_deletion"
    AUDIT_ACCESS = "compliance.audit_access"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditLog(Base):
    """Main audit log table."""
    __tablename__ = 'audit_logs'

    # Primary fields
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default=AuditSeverity.INFO)

    # Actor information
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    service_account = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True, index=True)  # Support IPv6
    user_agent = Column(String(500), nullable=True)

    # Target information
    resource_type = Column(String(100), nullable=True, index=True)
    resource_id = Column(String(100), nullable=True, index=True)
    resource_name = Column(String(255), nullable=True)

    # Event details
    action = Column(String(100), nullable=False)
    result = Column(String(20), nullable=False)  # 'success', 'failure', 'partial'
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

    # Additional context
    metadata = Column(JSON, nullable=True)  # Flexible JSON field for extra data
    request_id = Column(String(36), nullable=True, index=True)
    session_id = Column(String(36), nullable=True, index=True)
    correlation_id = Column(String(36), nullable=True, index=True)

    # Performance metrics
    duration_ms = Column(Float, nullable=True)
    bytes_transferred = Column(Integer, nullable=True)

    # Compliance fields
    legal_basis = Column(String(100), nullable=True)  # GDPR legal basis
    data_categories = Column(JSON, nullable=True)  # Categories of data accessed
    purposes = Column(JSON, nullable=True)  # Purposes for data processing

    # Integrity fields
    checksum = Column(String(64), nullable=True)  # SHA-256 hash of the log entry
    signature = Column(Text, nullable=True)  # Digital signature for tamper detection

    # Indexes for common queries
    __table_args__ = (
        Index('idx_timestamp_event', 'timestamp', 'event_type'),
        Index('idx_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_resource', 'resource_type', 'resource_id'),
        Index('idx_session', 'session_id', 'timestamp'),
    )


class AuditLogArchive(Base):
    """Archive table for old audit logs."""
    __tablename__ = 'audit_logs_archive'

    # Same structure as AuditLog but for archived records
    id = Column(String(36), primary_key=True)
    archived_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    original_timestamp = Column(DateTime, nullable=False)
    data = Column(JSON, nullable=False)  # Complete original record as JSON
    retention_period = Column(Integer, nullable=True)  # Days to retain
    deletion_scheduled = Column(DateTime, nullable=True)


class AuditLogAlert(Base):
    """Alerts generated from audit log analysis."""
    __tablename__ = 'audit_log_alerts'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    alert_type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)

    # Related audit logs
    audit_log_ids = Column(JSON, nullable=True)  # List of related audit log IDs

    # Alert status
    status = Column(String(20), nullable=False, default='new')  # new, acknowledged, resolved
    acknowledged_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Alert details
    metadata = Column(JSON, nullable=True)
    recommendations = Column(Text, nullable=True)


# ============================================================================
# Audit Logging Service
# ============================================================================

class AuditLogger:
    """
    Comprehensive audit logging service with buffering, compression, and analysis.
    """

    def __init__(
        self,
        db_url: Optional[str] = None,
        buffer_size: int = 1000,
        flush_interval: int = 5,
        enable_compression: bool = True,
        enable_encryption: bool = True,
        enable_alerts: bool = True
    ):
        """Initialize audit logger."""
        self.db_url = db_url or os.getenv("AUDIT_DB_URL", "sqlite:///audit.db")
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.enable_compression = enable_compression
        self.enable_encryption = enable_encryption
        self.enable_alerts = enable_alerts

        # Initialize database
        self._init_database()

        # Initialize buffer
        self.buffer = deque(maxlen=buffer_size)
        self.buffer_lock = threading.Lock()

        # Start background flusher
        self.flush_thread = threading.Thread(target=self._flush_worker, daemon=True)
        self.flush_thread.start()

        # Alert patterns
        self.alert_patterns = self._init_alert_patterns()

    def _init_database(self):
        """Initialize audit database."""
        # Create engine with connection pooling
        self.engine = create_engine(
            self.db_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=3600
        )

        # Create tables
        Base.metadata.create_all(self.engine)

        # Create session factory
        self.SessionFactory = sessionmaker(bind=self.engine)

        # Setup database triggers for integrity
        self._setup_database_triggers()

    def _setup_database_triggers(self):
        """Setup database triggers for audit log integrity."""
        @event.listens_for(AuditLog, 'before_insert')
        def generate_checksum(mapper, connection, target):
            """Generate checksum for audit log entry."""
            # Create checksum from critical fields
            checksum_data = f"{target.timestamp}{target.event_type}{target.user_id}{target.action}{target.result}"
            target.checksum = hashlib.sha256(checksum_data.encode()).hexdigest()

    def _init_alert_patterns(self) -> List[Dict]:
        """Initialize alert detection patterns."""
        return [
            {
                "name": "Multiple Failed Logins",
                "condition": lambda logs: self._detect_failed_logins(logs),
                "severity": AuditSeverity.WARNING,
                "threshold": 5,
                "window": 300  # 5 minutes
            },
            {
                "name": "Privilege Escalation",
                "condition": lambda logs: self._detect_privilege_escalation(logs),
                "severity": AuditSeverity.CRITICAL,
                "threshold": 1,
                "window": 60
            },
            {
                "name": "Mass Data Export",
                "condition": lambda logs: self._detect_mass_export(logs),
                "severity": AuditSeverity.WARNING,
                "threshold": 100,
                "window": 3600  # 1 hour
            },
            {
                "name": "SQL Injection Attempt",
                "condition": lambda logs: self._detect_sql_injection(logs),
                "severity": AuditSeverity.CRITICAL,
                "threshold": 1,
                "window": 60
            },
            {
                "name": "Unauthorized Access Pattern",
                "condition": lambda logs: self._detect_unauthorized_pattern(logs),
                "severity": AuditSeverity.ERROR,
                "threshold": 10,
                "window": 600
            }
        ]

    # ========================================================================
    # Core Logging Methods
    # ========================================================================

    def log(
        self,
        event_type: AuditEventType,
        action: str,
        result: str = "success",
        user_id: Optional[int] = None,
        user_email: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Log an audit event.

        Returns:
            Audit log ID
        """
        # Create audit log entry
        log_entry = AuditLog(
            event_type=event_type,
            action=action,
            result=result,
            user_id=user_id,
            user_email=user_email,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
            severity=severity,
            request_id=request_id,
            session_id=session_id,
            correlation_id=correlation_id,
            duration_ms=duration_ms,
            error_code=error_code,
            error_message=error_message
        )

        # Add to buffer
        with self.buffer_lock:
            self.buffer.append(log_entry)

        # Check if immediate flush needed
        if severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]:
            self._flush_buffer()

        # Check for alerts
        if self.enable_alerts:
            self._check_alerts([log_entry])

        return log_entry.id

    def log_login(
        self,
        user_id: int,
        user_email: str,
        success: bool,
        ip_address: str,
        user_agent: Optional[str] = None,
        mfa_used: bool = False,
        **kwargs
    ):
        """Log user login attempt."""
        self.log(
            event_type=AuditEventType.USER_LOGIN,
            action="login",
            result="success" if success else "failure",
            user_id=user_id if success else None,
            user_email=user_email,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"mfa_used": mfa_used},
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
            **kwargs
        )

    def log_data_access(
        self,
        user_id: int,
        resource_type: str,
        resource_id: str,
        action: str,
        fields_accessed: Optional[List[str]] = None,
        **kwargs
    ):
        """Log data access event."""
        self.log(
            event_type=AuditEventType.DATA_READ,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata={"fields_accessed": fields_accessed},
            **kwargs
        )

    def log_security_event(
        self,
        event_type: AuditEventType,
        description: str,
        ip_address: str,
        severity: AuditSeverity = AuditSeverity.ERROR,
        **kwargs
    ):
        """Log security-related event."""
        self.log(
            event_type=event_type,
            action="security_event",
            result="detected",
            ip_address=ip_address,
            metadata={"description": description},
            severity=severity,
            **kwargs
        )

    def log_compliance_event(
        self,
        event_type: AuditEventType,
        user_id: int,
        action: str,
        legal_basis: Optional[str] = None,
        data_categories: Optional[List[str]] = None,
        purposes: Optional[List[str]] = None,
        **kwargs
    ):
        """Log compliance-related event."""
        log_entry = self.log(
            event_type=event_type,
            action=action,
            user_id=user_id,
            legal_basis=legal_basis,
            data_categories=data_categories,
            purposes=purposes,
            **kwargs
        )

        # Additional compliance tracking
        if event_type == AuditEventType.DATA_DELETION:
            self._track_data_deletion(user_id, kwargs.get("resource_id"))

        return log_entry

    # ========================================================================
    # Buffer Management
    # ========================================================================

    def _flush_worker(self):
        """Background worker to flush buffer periodically."""
        while True:
            time.sleep(self.flush_interval)
            self._flush_buffer()

    def _flush_buffer(self):
        """Flush buffer to database."""
        if not self.buffer:
            return

        with self.buffer_lock:
            entries = list(self.buffer)
            self.buffer.clear()

        if not entries:
            return

        try:
            session = self.SessionFactory()

            # Bulk insert
            session.bulk_save_objects(entries)
            session.commit()

            logger.info(f"Flushed {len(entries)} audit log entries")

        except Exception as e:
            logger.error(f"Failed to flush audit buffer: {e}")
            # Re-add to buffer for retry
            with self.buffer_lock:
                self.buffer.extend(entries)
        finally:
            session.close()

    def flush(self):
        """Force flush the buffer."""
        self._flush_buffer()

    # ========================================================================
    # Alert Detection
    # ========================================================================

    def _check_alerts(self, logs: List[AuditLog]):
        """Check for alert conditions."""
        if not self.enable_alerts:
            return

        for pattern in self.alert_patterns:
            if pattern["condition"](logs):
                self._create_alert(pattern, logs)

    def _detect_failed_logins(self, logs: List[AuditLog]) -> bool:
        """Detect multiple failed login attempts."""
        failed_logins = [
            log for log in logs
            if log.event_type == AuditEventType.USER_LOGIN and log.result == "failure"
        ]
        return len(failed_logins) >= 5

    def _detect_privilege_escalation(self, logs: List[AuditLog]) -> bool:
        """Detect potential privilege escalation."""
        escalation_events = [
            log for log in logs
            if log.event_type in [
                AuditEventType.ROLE_ASSIGNED,
                AuditEventType.PERMISSION_GRANTED
            ] and log.metadata and log.metadata.get("elevated_privileges")
        ]
        return len(escalation_events) > 0

    def _detect_mass_export(self, logs: List[AuditLog]) -> bool:
        """Detect mass data export."""
        export_events = [
            log for log in logs
            if log.event_type == AuditEventType.DATA_EXPORT
        ]

        if not export_events:
            return False

        # Calculate total exported records
        total_records = sum(
            log.metadata.get("record_count", 0) for log in export_events
            if log.metadata
        )

        return total_records > 1000

    def _detect_sql_injection(self, logs: List[AuditLog]) -> bool:
        """Detect SQL injection attempts."""
        sql_patterns = ["' OR '1'='1", "'; DROP TABLE", "UNION SELECT", "/*", "*/"]

        for log in logs:
            if log.metadata:
                # Check for SQL patterns in metadata
                metadata_str = json.dumps(log.metadata)
                if any(pattern in metadata_str for pattern in sql_patterns):
                    return True

        return False

    def _detect_unauthorized_pattern(self, logs: List[AuditLog]) -> bool:
        """Detect unauthorized access patterns."""
        denied_events = [
            log for log in logs
            if log.event_type == AuditEventType.PERMISSION_DENIED
        ]
        return len(denied_events) >= 10

    def _create_alert(self, pattern: Dict, logs: List[AuditLog]):
        """Create an alert from detected pattern."""
        session = self.SessionFactory()

        try:
            alert = AuditLogAlert(
                alert_type=pattern["name"],
                severity=pattern["severity"],
                description=f"Detected: {pattern['name']}",
                audit_log_ids=[log.id for log in logs],
                metadata={
                    "pattern": pattern["name"],
                    "threshold": pattern["threshold"],
                    "window": pattern["window"]
                },
                recommendations=self._get_alert_recommendations(pattern["name"])
            )

            session.add(alert)
            session.commit()

            # Send notification (implement based on your notification system)
            self._send_alert_notification(alert)

            logger.warning(f"Alert created: {pattern['name']}")

        except Exception as e:
            logger.error(f"Failed to create alert: {e}")
        finally:
            session.close()

    def _get_alert_recommendations(self, alert_type: str) -> str:
        """Get recommendations for an alert type."""
        recommendations = {
            "Multiple Failed Logins": "1. Check if this is a brute force attack\n2. Consider blocking the IP\n3. Enable MFA for the account",
            "Privilege Escalation": "1. Review the privilege change\n2. Verify authorization\n3. Check for compromised account",
            "Mass Data Export": "1. Verify the export is authorized\n2. Check for data exfiltration\n3. Review user permissions",
            "SQL Injection Attempt": "1. Block the source IP immediately\n2. Review application logs\n3. Check for vulnerabilities",
            "Unauthorized Access Pattern": "1. Review user permissions\n2. Check for misconfiguration\n3. Investigate access attempts"
        }
        return recommendations.get(alert_type, "Review the alert and take appropriate action")

    def _send_alert_notification(self, alert: AuditLogAlert):
        """Send alert notification."""
        # Implement based on your notification system
        # E.g., send email, Slack message, PagerDuty alert, etc.
        pass

    # ========================================================================
    # Query and Analysis
    # ========================================================================

    def query(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        severity: Optional[AuditSeverity] = None,
        limit: int = 1000
    ) -> List[AuditLog]:
        """Query audit logs."""
        session = self.SessionFactory()

        try:
            query = session.query(AuditLog)

            if start_date:
                query = query.filter(AuditLog.timestamp >= start_date)

            if end_date:
                query = query.filter(AuditLog.timestamp <= end_date)

            if event_types:
                query = query.filter(AuditLog.event_type.in_(event_types))

            if user_id:
                query = query.filter(AuditLog.user_id == user_id)

            if resource_type:
                query = query.filter(AuditLog.resource_type == resource_type)

            if resource_id:
                query = query.filter(AuditLog.resource_id == resource_id)

            if severity:
                query = query.filter(AuditLog.severity == severity)

            return query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

        finally:
            session.close()

    def get_user_activity(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get user activity summary."""
        start_date = datetime.utcnow() - timedelta(days=days)

        logs = self.query(
            start_date=start_date,
            user_id=user_id
        )

        return {
            "total_events": len(logs),
            "login_count": sum(1 for log in logs if log.event_type == AuditEventType.USER_LOGIN),
            "data_access_count": sum(1 for log in logs if log.event_type == AuditEventType.DATA_READ),
            "failed_attempts": sum(1 for log in logs if log.result == "failure"),
            "last_activity": max((log.timestamp for log in logs), default=None)
        }

    def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime,
        compliance_type: str = "GDPR"
    ) -> Dict[str, Any]:
        """Generate compliance report."""
        logs = self.query(
            start_date=start_date,
            end_date=end_date,
            event_types=[
                AuditEventType.CONSENT_GIVEN,
                AuditEventType.CONSENT_WITHDRAWN,
                AuditEventType.DATA_REQUEST,
                AuditEventType.DATA_DELETION
            ]
        )

        report = {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "compliance_type": compliance_type,
            "summary": {
                "consent_given": sum(1 for log in logs if log.event_type == AuditEventType.CONSENT_GIVEN),
                "consent_withdrawn": sum(1 for log in logs if log.event_type == AuditEventType.CONSENT_WITHDRAWN),
                "data_requests": sum(1 for log in logs if log.event_type == AuditEventType.DATA_REQUEST),
                "data_deletions": sum(1 for log in logs if log.event_type == AuditEventType.DATA_DELETION)
            },
            "details": []
        }

        for log in logs:
            report["details"].append({
                "timestamp": log.timestamp.isoformat(),
                "event": log.event_type,
                "user": log.user_email,
                "legal_basis": log.legal_basis,
                "result": log.result
            })

        return report

    # ========================================================================
    # Archive and Retention
    # ========================================================================

    def archive_old_logs(self, days: int = 90) -> int:
        """Archive logs older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        session = self.SessionFactory()

        try:
            # Get logs to archive
            old_logs = session.query(AuditLog).filter(
                AuditLog.timestamp < cutoff_date
            ).all()

            if not old_logs:
                return 0

            # Archive logs
            for log in old_logs:
                archive_entry = AuditLogArchive(
                    id=log.id,
                    original_timestamp=log.timestamp,
                    data=self._serialize_log(log),
                    retention_period=days * 2  # Keep archives for double the period
                )
                session.add(archive_entry)
                session.delete(log)

            session.commit()

            logger.info(f"Archived {len(old_logs)} audit logs")
            return len(old_logs)

        except Exception as e:
            logger.error(f"Failed to archive logs: {e}")
            session.rollback()
            return 0
        finally:
            session.close()

    def _serialize_log(self, log: AuditLog) -> Dict:
        """Serialize audit log to dictionary."""
        return {
            "id": log.id,
            "timestamp": log.timestamp.isoformat(),
            "event_type": log.event_type,
            "severity": log.severity,
            "user_id": log.user_id,
            "user_email": log.user_email,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "action": log.action,
            "result": log.result,
            "metadata": log.metadata,
            "ip_address": log.ip_address,
            "checksum": log.checksum
        }

    def _track_data_deletion(self, user_id: int, resource_id: Optional[str]):
        """Track data deletion for compliance."""
        # Implement based on your compliance requirements
        pass


# ============================================================================
# Audit Context Manager
# ============================================================================

class AuditContext:
    """Context manager for auditing operations."""

    def __init__(
        self,
        audit_logger: AuditLogger,
        event_type: AuditEventType,
        action: str,
        user_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs
    ):
        """Initialize audit context."""
        self.audit_logger = audit_logger
        self.event_type = event_type
        self.action = action
        self.user_id = user_id
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.kwargs = kwargs
        self.start_time = None
        self.log_id = None

    def __enter__(self):
        """Enter audit context."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit audit context and log the event."""
        duration_ms = (time.time() - self.start_time) * 1000 if self.start_time else None

        result = "failure" if exc_type else "success"
        error_code = None
        error_message = None

        if exc_type:
            error_code = exc_type.__name__
            error_message = str(exc_val)

        self.log_id = self.audit_logger.log(
            event_type=self.event_type,
            action=self.action,
            result=result,
            user_id=self.user_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            duration_ms=duration_ms,
            error_code=error_code,
            error_message=error_message,
            **self.kwargs
        )


if __name__ == "__main__":
    # Example usage
    pass