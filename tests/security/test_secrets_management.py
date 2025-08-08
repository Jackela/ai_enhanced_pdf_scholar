"""
Comprehensive Test Suite for Production Secrets Management
Tests encryption, rotation, validation, monitoring, and compliance features.
"""

import asyncio
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.secrets_vault import (
    ProductionSecretsManager,
    SecretEncryptionContext,
    EncryptionAlgorithm,
    SecretValidationError,
    SecretRotationError,
    SecretBackupError,
    validate_prod_secrets,
    validate_secret_strength,
    calculate_entropy,
    generate_secure_secret,
    SecretStrength
)
from backend.services.secrets_validation_service import (
    SecretValidationService,
    ValidationSeverity,
    ComplianceStandard,
    ValidationRule,
    SecretValidationReport
)
from backend.services.secrets_monitoring_service import (
    SecretsMonitoringService,
    AlertSeverity,
    AlertChannel,
    MonitoringMetric,
    Alert,
    AlertRule,
    MetricData,
    AlertingConfig
)


class TestProductionSecretsManager:
    """Test suite for ProductionSecretsManager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def secrets_manager(self, temp_dir):
        """Create ProductionSecretsManager instance for testing."""
        return ProductionSecretsManager(
            master_key_path=temp_dir / "master.key",
            backup_location=temp_dir / "backups",
            encryption_algorithm=EncryptionAlgorithm.AES_256_GCM
        )
    
    def test_secrets_manager_initialization(self, secrets_manager):
        """Test secrets manager initialization."""
        assert secrets_manager is not None
        assert secrets_manager._encryption_algorithm == EncryptionAlgorithm.AES_256_GCM
        assert len(secrets_manager._key_versions) > 0
        assert secrets_manager._current_key_version >= 1
    
    def test_encrypt_decrypt_secret(self, secrets_manager):
        """Test basic secret encryption and decryption."""
        secret_id = "test_secret"
        plaintext = "This is a test secret with special chars: !@#$%^&*()"
        
        # Encrypt
        encrypted_data, context = secrets_manager.encrypt_secret(
            plaintext, secret_id
        )
        
        assert encrypted_data is not None
        assert isinstance(context, SecretEncryptionContext)
        assert context.algorithm == EncryptionAlgorithm.AES_256_GCM
        assert context.checksum is not None
        
        # Decrypt
        decrypted = secrets_manager.decrypt_secret(
            encrypted_data, secret_id, context
        )
        
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_with_additional_data(self, secrets_manager):
        """Test encryption with additional authenticated data."""
        secret_id = "test_secret_aad"
        plaintext = "Secret with AAD"
        additional_data = b"authentication_context_data"
        
        # Encrypt with AAD
        encrypted_data, context = secrets_manager.encrypt_secret(
            plaintext, secret_id, additional_data
        )
        
        # Decrypt with AAD
        decrypted = secrets_manager.decrypt_secret(
            encrypted_data, secret_id, context, additional_data
        )
        
        assert decrypted == plaintext
        
        # Try to decrypt with wrong AAD (should fail)
        with pytest.raises(Exception):
            secrets_manager.decrypt_secret(
                encrypted_data, secret_id, context, b"wrong_aad"
            )
    
    def test_secret_integrity_validation(self, secrets_manager):
        """Test secret integrity validation with checksum."""
        secret_id = "integrity_test"
        plaintext = "Secret for integrity testing"
        
        encrypted_data, context = secrets_manager.encrypt_secret(
            plaintext, secret_id
        )
        
        # Tamper with context checksum
        original_checksum = context.checksum
        context.checksum = "invalid_checksum"
        
        # Should raise validation error
        with pytest.raises(SecretValidationError):
            secrets_manager.decrypt_secret(encrypted_data, secret_id, context)
        
        # Restore correct checksum
        context.checksum = original_checksum
        decrypted = secrets_manager.decrypt_secret(encrypted_data, secret_id, context)
        assert decrypted == plaintext
    
    def test_key_rotation(self, secrets_manager):
        """Test master key rotation."""
        # Get initial key version
        initial_version = secrets_manager._current_key_version
        initial_key_count = len(secrets_manager._key_versions)
        
        # Rotate master key
        new_version = secrets_manager.rotate_key()
        
        assert new_version > initial_version
        assert secrets_manager._current_key_version == new_version
        assert len(secrets_manager._key_versions) == initial_key_count + 1
    
    def test_secret_encryption_with_old_key(self, secrets_manager):
        """Test that secrets encrypted with old keys can still be decrypted."""
        secret_id = "version_test"
        plaintext = "Secret for version testing"
        
        # Encrypt with current key
        encrypted_data, context = secrets_manager.encrypt_secret(
            plaintext, secret_id
        )
        original_version = context.key_version
        
        # Rotate key
        new_version = secrets_manager.rotate_key()
        assert new_version != original_version
        
        # Should still be able to decrypt with old key version
        decrypted = secrets_manager.decrypt_secret(
            encrypted_data, secret_id, context
        )
        assert decrypted == plaintext
    
    def test_backup_and_restore(self, secrets_manager):
        """Test secrets backup and restore functionality."""
        # Create some test secrets
        test_secrets = {
            "secret1": "value1",
            "secret2": "value2_with_special_chars_!@#$",
            "secret3": "value3"
        }
        
        # Encrypt secrets
        encrypted_secrets = {}
        for secret_id, plaintext in test_secrets.items():
            encrypted_data, context = secrets_manager.encrypt_secret(
                plaintext, secret_id
            )
            encrypted_secrets[secret_id] = (encrypted_data, context)
        
        # Create backup
        backup_path = secrets_manager.backup_secrets("test_backup")
        assert backup_path.exists()
        
        # Create new secrets manager instance (simulating restore scenario)
        new_temp_dir = backup_path.parent / "new_instance"
        new_temp_dir.mkdir()
        
        new_secrets_manager = ProductionSecretsManager(
            master_key_path=new_temp_dir / "master.key",
            backup_location=new_temp_dir / "backups"
        )
        
        # Restore from backup
        success = new_secrets_manager.restore_secrets(backup_path)
        assert success
        
        # Verify that restored secrets can be decrypted
        for secret_id, (encrypted_data, context) in encrypted_secrets.items():
            decrypted = new_secrets_manager.decrypt_secret(
                encrypted_data, secret_id, context
            )
            assert decrypted == test_secrets[secret_id]
    
    def test_health_check(self, secrets_manager):
        """Test secrets manager health check."""
        health_status = secrets_manager.health_check()
        
        assert "overall_status" in health_status
        assert "components" in health_status
        assert health_status["overall_status"] == "healthy"
        assert "master_key" in health_status["components"]
        assert "encryption" in health_status["components"]
    
    def test_audit_trail(self, secrets_manager):
        """Test audit trail logging."""
        secret_id = "audit_test"
        plaintext = "Secret for audit testing"
        
        # Perform some operations
        encrypted_data, context = secrets_manager.encrypt_secret(
            plaintext, secret_id
        )
        decrypted = secrets_manager.decrypt_secret(
            encrypted_data, secret_id, context
        )
        
        # Check audit trail
        audit_entries = secrets_manager.get_audit_trail()
        
        # Should have encrypt and decrypt operations
        encrypt_entries = [e for e in audit_entries if e["operation"] == "encrypt"]
        decrypt_entries = [e for e in audit_entries if e["operation"] == "decrypt"]
        
        assert len(encrypt_entries) >= 1
        assert len(decrypt_entries) >= 1
        
        # Check entry structure
        for entry in encrypt_entries + decrypt_entries:
            assert "timestamp" in entry
            assert "operation" in entry
            assert "secret_id" in entry
            assert "success" in entry
    
    @pytest.mark.parametrize("algorithm", [
        EncryptionAlgorithm.AES_256_GCM,
        EncryptionAlgorithm.CHACHA20_POLY1305
    ])
    def test_different_encryption_algorithms(self, temp_dir, algorithm):
        """Test different encryption algorithms."""
        secrets_manager = ProductionSecretsManager(
            master_key_path=temp_dir / f"master_{algorithm.value}.key",
            encryption_algorithm=algorithm
        )
        
        secret_id = f"test_{algorithm.value}"
        plaintext = f"Test secret for {algorithm.value}"
        
        encrypted_data, context = secrets_manager.encrypt_secret(
            plaintext, secret_id
        )
        decrypted = secrets_manager.decrypt_secret(
            encrypted_data, secret_id, context
        )
        
        assert decrypted == plaintext
        assert context.algorithm == algorithm


class TestSecretsValidation:
    """Test suite for secrets validation."""
    
    @pytest.fixture
    def secrets_manager(self):
        """Mock secrets manager for validation testing."""
        return MagicMock(spec=ProductionSecretsManager)
    
    @pytest.fixture
    def validation_service(self, secrets_manager):
        """Create validation service instance."""
        return SecretValidationService(secrets_manager)
    
    @pytest.mark.asyncio
    async def test_validate_strong_secret(self, validation_service):
        """Test validation of a strong secret."""
        secret_name = "strong_password"
        secret_value = "Str0ng_P@ssw0rd_W1th_Sp3c1@l_Ch@rs_123!"
        environment = "production"
        
        report = await validation_service.validate_secret(
            secret_name, secret_value, environment
        )
        
        assert isinstance(report, SecretValidationReport)
        assert report.secret_name == secret_name
        assert report.environment == environment
        assert report.overall_status in ["pass", "warning"]
        assert len(report.validation_results) > 0
    
    @pytest.mark.asyncio
    async def test_validate_weak_secret(self, validation_service):
        """Test validation of a weak secret."""
        secret_name = "weak_password"
        secret_value = "password123"  # Weak password
        environment = "production"
        
        report = await validation_service.validate_secret(
            secret_name, secret_value, environment
        )
        
        assert report.overall_status == "fail"
        
        # Should have validation failures
        failed_results = [r for r in report.validation_results if not r.passed]
        assert len(failed_results) > 0
        
        # Should detect weak patterns
        weak_pattern_results = [
            r for r in failed_results 
            if r.rule_name == "no_weak_patterns"
        ]
        assert len(weak_pattern_results) > 0
    
    @pytest.mark.asyncio
    async def test_validate_environment_secrets(self, validation_service):
        """Test validation of multiple secrets in an environment."""
        secrets_dict = {
            "database_password": "Secure_Database_P@ssw0rd_2024!",
            "jwt_secret": "jwt_signing_key_with_256_bits_of_entropy_xyz123",
            "weak_secret": "password",  # This should fail
            "encryption_key": "encryption_key_with_strong_randomness_abc123"
        }
        environment = "production"
        
        validation_results = await validation_service.validate_environment_secrets(
            secrets_dict, environment
        )
        
        assert len(validation_results) == len(secrets_dict)
        
        # Strong secrets should pass or have warnings
        for secret_name in ["database_password", "jwt_secret", "encryption_key"]:
            report = validation_results[secret_name]
            assert report.overall_status in ["pass", "warning"]
        
        # Weak secret should fail
        weak_report = validation_results["weak_secret"]
        assert weak_report.overall_status == "fail"
    
    @pytest.mark.asyncio
    async def test_compliance_standards_validation(self, validation_service):
        """Test validation against specific compliance standards."""
        secret_name = "compliance_test"
        secret_value = "C0mpl1@nt_S3cr3t_F0r_T3st1ng!"
        environment = "production"
        compliance_standards = [
            ComplianceStandard.NIST_800_53,
            ComplianceStandard.ISO_27001
        ]
        
        report = await validation_service.validate_secret(
            secret_name, secret_value, environment, compliance_standards
        )
        
        assert len(report.compliance_status) == len(compliance_standards)
        
        for standard in compliance_standards:
            assert standard in report.compliance_status
            assert report.compliance_status[standard] in [
                "compliant", "partially_compliant", "non_compliant"
            ]
    
    def test_calculate_entropy(self):
        """Test entropy calculation."""
        # Low entropy
        low_entropy_text = "aaaaaaaaaa"
        low_entropy = calculate_entropy(low_entropy_text)
        assert low_entropy < 10
        
        # High entropy
        high_entropy_text = "R@nd0m_H1gh_3ntr0py_T3xt_!@#$%^&*()"
        high_entropy = calculate_entropy(high_entropy_text)
        assert high_entropy > 50
        
        # Empty string
        assert calculate_entropy("") == 0.0
    
    @pytest.mark.parametrize("secret_type,strength", [
        ("jwt_secret", SecretStrength.HIGH),
        ("database_password", SecretStrength.MEDIUM),
        ("api_key", SecretStrength.HIGH),
        ("encryption_key", SecretStrength.ULTRA)
    ])
    def test_generate_secure_secret(self, secret_type, strength):
        """Test secure secret generation."""
        generated_secret = generate_secure_secret(secret_type, strength)
        
        assert isinstance(generated_secret, str)
        assert len(generated_secret) > 0
        
        # Test entropy of generated secret
        entropy = calculate_entropy(generated_secret)
        
        # Should have reasonable entropy based on strength
        min_entropy = {
            SecretStrength.LOW: 20,
            SecretStrength.MEDIUM: 40,
            SecretStrength.HIGH: 60,
            SecretStrength.ULTRA: 100
        }
        
        assert entropy >= min_entropy[strength]
    
    def test_validate_prod_secrets(self):
        """Test production secrets validation function."""
        secrets_dict = {
            "database_password": "Secure_Database_P@ssw0rd_2024!",
            "jwt_secret": "jwt_signing_key_with_256_bits_entropy_xyz",
            "encryption_key": "encryption_key_strong_randomness_abc123"
        }
        
        validation_result = validate_prod_secrets(secrets_dict, "production")
        
        assert validation_result["overall_status"] in ["passed", "failed"]
        assert "validations" in validation_result
        assert "recommendations" in validation_result
        assert len(validation_result["validations"]) == len(secrets_dict)


class TestSecretsMonitoring:
    """Test suite for secrets monitoring and alerting."""
    
    @pytest.fixture
    def secrets_manager(self):
        """Mock secrets manager for monitoring testing."""
        mock_manager = MagicMock(spec=ProductionSecretsManager)
        mock_manager.health_check.return_value = {
            "overall_status": "healthy",
            "components": {
                "master_key": {"status": "healthy"},
                "encryption": {"status": "healthy"}
            }
        }
        mock_manager.get_audit_trail.return_value = [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "operation": "decrypt",
                "key": "test_secret",
                "success": True
            }
        ]
        return mock_manager
    
    @pytest.fixture
    def validation_service(self, secrets_manager):
        """Mock validation service for monitoring testing."""
        return MagicMock(spec=SecretValidationService)
    
    @pytest.fixture
    def monitoring_service(self, secrets_manager, validation_service):
        """Create monitoring service instance."""
        config = AlertingConfig(
            smtp_host="localhost",
            smtp_port=587,
            from_email="test@example.com"
        )
        return SecretsMonitoringService(
            secrets_manager, validation_service, config
        )
    
    @pytest.mark.asyncio
    async def test_monitoring_service_initialization(self, monitoring_service):
        """Test monitoring service initialization."""
        assert monitoring_service is not None
        assert len(monitoring_service.alert_rules) > 0
        assert monitoring_service.config is not None
    
    @pytest.mark.asyncio
    async def test_metric_collection(self, monitoring_service):
        """Test metric collection."""
        initial_metric_count = len(monitoring_service.metric_history)
        
        await monitoring_service._collect_metrics()
        
        # Should have collected some metrics
        assert len(monitoring_service.metric_history) > initial_metric_count
        
        # Check for expected metric types
        metric_types = [m.metric for m in monitoring_service.metric_history]
        assert MonitoringMetric.ENCRYPTION_HEALTH in metric_types
        assert MonitoringMetric.SECRET_ACCESS_FREQUENCY in metric_types
    
    @pytest.mark.asyncio
    async def test_alert_rule_evaluation(self, monitoring_service):
        """Test alert rule evaluation."""
        # Add a test metric that should trigger an alert
        monitoring_service._record_metric(
            MonitoringMetric.VALIDATION_FAILURES, 10.0  # Above threshold
        )
        
        initial_alert_count = len(monitoring_service.active_alerts)
        
        await monitoring_service._evaluate_alert_rules()
        
        # Should have created an alert
        assert len(monitoring_service.active_alerts) > initial_alert_count
    
    @pytest.mark.asyncio
    async def test_alert_rate_limiting(self, monitoring_service):
        """Test alert rate limiting."""
        # Trigger multiple alerts for the same rule quickly
        for i in range(10):
            monitoring_service._record_metric(
                MonitoringMetric.VALIDATION_FAILURES, 10.0
            )
            await monitoring_service._evaluate_alert_rules()
        
        # Should not create unlimited alerts due to rate limiting
        validation_failure_alerts = [
            alert for alert in monitoring_service.active_alerts.values()
            if alert.rule_name == "validation_failures_spike"
        ]
        
        # Should be limited by rate limiting
        assert len(validation_failure_alerts) <= 2
    
    def test_add_custom_alert_rule(self, monitoring_service):
        """Test adding custom alert rules."""
        custom_rule = AlertRule(
            name="custom_test_rule",
            description="Test custom rule",
            metric=MonitoringMetric.SECRET_ACCESS_COUNT,
            condition="value > threshold",
            threshold=50,
            severity=AlertSeverity.MEDIUM,
            channels=[AlertChannel.LOG]
        )
        
        initial_rule_count = len(monitoring_service.alert_rules)
        monitoring_service.add_alert_rule(custom_rule)
        
        assert len(monitoring_service.alert_rules) == initial_rule_count + 1
        assert "custom_test_rule" in monitoring_service.alert_rules
    
    def test_get_monitoring_status(self, monitoring_service):
        """Test monitoring status retrieval."""
        status = monitoring_service.get_monitoring_status()
        
        assert "monitoring_active" in status
        assert "alert_rules_count" in status
        assert "active_alerts_count" in status
        assert "metrics_count" in status
        
        assert status["alert_rules_count"] > 0
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, monitoring_service):
        """Test starting and stopping monitoring tasks."""
        # Start monitoring
        await monitoring_service.start_monitoring()
        
        status = monitoring_service.get_monitoring_status()
        assert status["monitoring_active"]
        
        # Stop monitoring
        await monitoring_service.stop_monitoring()
        
        # Give tasks time to cancel
        await asyncio.sleep(0.1)
        
        status = monitoring_service.get_monitoring_status()
        assert not status["monitoring_active"]
    
    def test_alert_creation(self, monitoring_service):
        """Test alert creation and management."""
        # Create test alert rule
        test_rule = AlertRule(
            name="test_alert_rule",
            description="Test alert for unit testing",
            metric=MonitoringMetric.SECRET_ACCESS_COUNT,
            condition="value > threshold",
            threshold=5,
            severity=AlertSeverity.MEDIUM,
            channels=[AlertChannel.LOG]
        )
        
        # Create test metric
        test_metric = MetricData(
            metric=MonitoringMetric.SECRET_ACCESS_COUNT,
            value=10.0
        )
        
        initial_alert_count = len(monitoring_service.active_alerts)
        
        # This would normally be called by the monitoring loop
        # but we can test it directly
        asyncio.run(monitoring_service._create_alert(test_rule, test_metric))
        
        assert len(monitoring_service.active_alerts) == initial_alert_count + 1
    
    def test_metric_history_cleanup(self, monitoring_service):
        """Test metric history cleanup functionality."""
        # Add old metrics
        old_time = datetime.utcnow() - timedelta(days=10)
        old_metric = MetricData(
            metric=MonitoringMetric.SECRET_ACCESS_COUNT,
            value=5.0,
            timestamp=old_time
        )
        monitoring_service.metric_history.append(old_metric)
        
        # Add recent metric
        recent_metric = MetricData(
            metric=MonitoringMetric.SECRET_ACCESS_COUNT,
            value=3.0
        )
        monitoring_service.metric_history.append(recent_metric)
        
        initial_count = len(monitoring_service.metric_history)
        
        # Run cleanup
        asyncio.run(monitoring_service._cleanup_old_data())
        
        # Should have removed old metrics
        assert len(monitoring_service.metric_history) < initial_count
        
        # Recent metric should still be there
        assert recent_metric in monitoring_service.metric_history


class TestIntegrationScenarios:
    """Integration tests for complete secrets management workflows."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def full_secrets_system(self, temp_dir):
        """Create complete secrets management system."""
        secrets_manager = ProductionSecretsManager(
            master_key_path=temp_dir / "master.key",
            backup_location=temp_dir / "backups"
        )
        validation_service = SecretValidationService(secrets_manager)
        monitoring_service = SecretsMonitoringService(
            secrets_manager, validation_service
        )
        
        return {
            "secrets_manager": secrets_manager,
            "validation_service": validation_service,
            "monitoring_service": monitoring_service
        }
    
    @pytest.mark.asyncio
    async def test_complete_secret_lifecycle(self, full_secrets_system):
        """Test complete secret lifecycle: create, validate, rotate, monitor."""
        secrets_manager = full_secrets_system["secrets_manager"]
        validation_service = full_secrets_system["validation_service"]
        monitoring_service = full_secrets_system["monitoring_service"]
        
        # 1. Create and encrypt a secret
        secret_id = "lifecycle_test_secret"
        original_secret = "Original_Secret_Value_2024!"
        
        encrypted_data, context = secrets_manager.encrypt_secret(
            original_secret, secret_id
        )
        
        # 2. Validate the secret
        validation_report = await validation_service.validate_secret(
            secret_id, original_secret, "production"
        )
        assert validation_report.overall_status in ["pass", "warning"]
        
        # 3. Start monitoring
        await monitoring_service.start_monitoring()
        
        # 4. Perform some operations that will be monitored
        decrypted = secrets_manager.decrypt_secret(
            encrypted_data, secret_id, context
        )
        assert decrypted == original_secret
        
        # 5. Rotate the secret
        new_secret = "New_Rotated_Secret_Value_2024!"
        new_encrypted_data, new_context = secrets_manager.encrypt_secret(
            new_secret, secret_id
        )
        
        # 6. Verify old and new secrets work
        assert secrets_manager.decrypt_secret(
            encrypted_data, secret_id, context
        ) == original_secret
        
        assert secrets_manager.decrypt_secret(
            new_encrypted_data, secret_id, new_context
        ) == new_secret
        
        # 7. Create backup
        backup_path = secrets_manager.backup_secrets("lifecycle_test")
        assert backup_path.exists()
        
        # 8. Stop monitoring
        await monitoring_service.stop_monitoring()
        
        # 9. Verify audit trail
        audit_entries = secrets_manager.get_audit_trail()
        assert len(audit_entries) > 0
        
        encrypt_operations = [e for e in audit_entries if e["operation"] == "encrypt"]
        decrypt_operations = [e for e in audit_entries if e["operation"] == "decrypt"]
        
        assert len(encrypt_operations) >= 2  # Original + rotated
        assert len(decrypt_operations) >= 2  # Original + rotated
    
    @pytest.mark.asyncio
    async def test_compliance_monitoring_workflow(self, full_secrets_system):
        """Test compliance monitoring workflow."""
        validation_service = full_secrets_system["validation_service"]
        monitoring_service = full_secrets_system["monitoring_service"]
        
        # Test secrets with different compliance levels
        test_secrets = {
            "compliant_secret": "C0mpl1@nt_S3cr3t_2024_W1th_Str0ng_3ntr0py!",
            "weak_secret": "password123",  # Should fail compliance
            "medium_secret": "MediumSecret2024"
        }
        
        # Validate all secrets
        validation_results = await validation_service.validate_environment_secrets(
            test_secrets, "production", [ComplianceStandard.NIST_800_53]
        )
        
        # Generate compliance report
        compliance_report = validation_service.generate_compliance_report(
            validation_results, "production", [ComplianceStandard.NIST_800_53]
        )
        
        assert "summary" in compliance_report
        assert "standards_compliance" in compliance_report
        assert "recommendations" in compliance_report
        
        # Check that weak secret triggered compliance issues
        weak_secret_report = validation_results["weak_secret"]
        assert weak_secret_report.overall_status == "fail"
        
        # Start monitoring to track compliance
        await monitoring_service.start_monitoring()
        
        # Simulate compliance metrics
        monitoring_service._record_metric(
            MonitoringMetric.COMPLIANCE_STATUS,
            0.7  # Below threshold, should trigger alert
        )
        
        await monitoring_service._evaluate_alert_rules()
        
        # Should have compliance violation alert
        compliance_alerts = [
            alert for alert in monitoring_service.active_alerts.values()
            if alert.rule_name == "compliance_violation"
        ]
        assert len(compliance_alerts) > 0
        
        await monitoring_service.stop_monitoring()
    
    def test_disaster_recovery_scenario(self, full_secrets_system, temp_dir):
        """Test disaster recovery scenario."""
        secrets_manager = full_secrets_system["secrets_manager"]
        
        # Create test secrets
        test_secrets = {
            "db_password": "Database_P@ssw0rd_2024!",
            "api_key": "API_K3y_W1th_Str0ng_R@nd0mn3ss",
            "jwt_secret": "JWT_S1gn1ng_K3y_F0r_Pr0duct10n"
        }
        
        # Encrypt all secrets
        encrypted_secrets = {}
        for secret_id, plaintext in test_secrets.items():
            encrypted_data, context = secrets_manager.encrypt_secret(
                plaintext, secret_id
            )
            encrypted_secrets[secret_id] = (encrypted_data, context)
        
        # Create backup
        backup_path = secrets_manager.backup_secrets("disaster_recovery_test")
        
        # Simulate disaster: create new secrets manager instance
        disaster_recovery_dir = temp_dir / "disaster_recovery"
        disaster_recovery_dir.mkdir()
        
        new_secrets_manager = ProductionSecretsManager(
            master_key_path=disaster_recovery_dir / "master.key",
            backup_location=disaster_recovery_dir / "backups"
        )
        
        # Restore from backup
        restore_success = new_secrets_manager.restore_secrets(backup_path)
        assert restore_success
        
        # Verify all secrets can be decrypted with restored manager
        for secret_id, (encrypted_data, context) in encrypted_secrets.items():
            decrypted = new_secrets_manager.decrypt_secret(
                encrypted_data, secret_id, context
            )
            assert decrypted == test_secrets[secret_id]
        
        # Verify health after recovery
        health_status = new_secrets_manager.health_check()
        assert health_status["overall_status"] == "healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])