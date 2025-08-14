# Enterprise-Grade Secrets Management System

## Overview

The AI Enhanced PDF Scholar now includes a comprehensive, enterprise-grade secrets management system that provides secure storage, rotation, and access control for all sensitive configuration data including API keys, database credentials, JWT keys, and more.

## Features

### 🔐 Multiple Provider Support
- **HashiCorp Vault**: Enterprise-grade secrets management for production
- **AWS Secrets Manager**: Cloud-native secrets storage with AWS integration
- **Local Encrypted Storage**: Secure development environment with AES-256 encryption
- **Environment Variables**: Fallback support for legacy deployments

### 🔄 Automatic Secret Rotation
- Configurable rotation intervals per secret
- Zero-downtime rotation for JWT keys
- Automatic expiration handling
- Rotation audit logging

### 📊 Comprehensive Audit Logging
- All secret operations logged with timestamps
- Success/failure tracking
- Provider usage monitoring
- Security event recording

### 🚀 Zero-Downtime Migration
- Automatic discovery of existing secrets
- Non-destructive migration process
- Rollback capabilities
- Backward compatibility maintained

### 🛡️ Security Features
- AES-256 encryption for local storage
- TLS for all network communications
- Least privilege access patterns
- Secret versioning and rollback
- Automatic secret expiration

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Application                        │
├─────────────────────────────────────────────────────┤
│              Secrets Integration Layer               │
│  (Backward Compatibility + Monkey Patching)          │
├─────────────────────────────────────────────────────┤
│              Enhanced Configuration                  │
│         (Type-safe configuration objects)            │
├─────────────────────────────────────────────────────┤
│               Secrets Manager                        │
│    (Caching + Rotation + Audit + Fallback)          │
├──────────────┬──────────────┬──────────────────────┤
│    Vault     │     AWS      │   Local Encrypted    │
│   Provider   │   Provider   │     Provider         │
└──────────────┴──────────────┴──────────────────────┘
```

## Quick Start

### 1. Development Setup (Local Encrypted Storage)

```python
# Initialize with local encrypted storage (default for development)
from backend.core.secrets_integration import initialize_secrets_integration

# This will:
# - Set up local encrypted storage
# - Auto-migrate existing secrets
# - Apply backward compatibility patches
initialize_secrets_integration()
```

### 2. Production Setup (HashiCorp Vault)

```bash
# Set environment variables
export SECRET_PROVIDER=vault
export VAULT_URL=https://vault.example.com
export VAULT_TOKEN=your-vault-token
export VAULT_NAMESPACE=your-namespace  # Optional
export ENVIRONMENT=production
```

```python
from backend.core.secrets import SecretProvider
from backend.core.secrets_integration import initialize_secrets_integration

# Initialize with Vault
initialize_secrets_integration(
    provider=SecretProvider.VAULT,
    auto_migrate=True,
    monkey_patch=True
)
```

### 3. AWS Secrets Manager Setup

```bash
# Set environment variables
export SECRET_PROVIDER=aws_secrets_manager
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export ENVIRONMENT=staging
```

```python
from backend.core.secrets import SecretProvider
from backend.core.secrets_integration import initialize_secrets_integration

# Initialize with AWS
initialize_secrets_integration(
    provider=SecretProvider.AWS_SECRETS_MANAGER,
    auto_migrate=True,
    monkey_patch=True
)
```

## Migration Guide

### Automatic Migration

The system can automatically discover and migrate secrets from:
- Environment variables
- `config.py` file
- `settings.json` file
- JWT key files
- `.env` files

Run the migration script:

```bash
# Dry run (no changes made)
python -m backend.core.secrets_migration --provider local

# Live migration to local encrypted storage
python -m backend.core.secrets_migration --provider local --live

# Live migration to Vault with cleanup
python -m backend.core.secrets_migration --provider vault --live --cleanup

# Migration with custom rotation interval
python -m backend.core.secrets_migration --provider aws --live --rotation-days 30
```

### Manual Migration

```python
from backend.core.secrets import SecretsManager, SecretType

secrets_manager = SecretsManager()

# Store individual secrets
secrets_manager.set_secret(
    key="api_key_gemini",
    value="your-api-key",
    secret_type=SecretType.API_KEY,
    rotation_interval_days=90,
    description="Google Gemini API key"
)

# Store database credentials
secrets_manager.set_secret(
    key="database_url",
    value="postgresql://user:pass@localhost/db",
    secret_type=SecretType.DATABASE_URL,
    expires_in_days=365,
    tags={"environment": "production", "service": "postgres"}
)
```

## Usage in Application Code

### Using the Enhanced Configuration

```python
from backend.core.enhanced_config import get_config

config = get_config()

# Access configuration with type safety
db_url = config.get_database_url()
redis_url = config.get_redis_url()
gemini_key = config.get_api_key("gemini")

# Check environment
if config.is_production():
    # Production-specific logic
    pass

# Validate configuration
errors = config.validate_secrets()
if errors:
    logger.warning(f"Configuration issues: {errors}")
```

### Direct Secret Access

```python
from backend.core.secrets import get_secrets_manager

secrets = get_secrets_manager()

# Get a secret with caching
api_key = secrets.get_secret("api_key_openai")

# Get without cache (force fresh retrieval)
db_password = secrets.get_secret("db_password", use_cache=False)

# Get specific version
old_key = secrets.get_secret("api_key", version="2")
```

### Secret Rotation

```python
from backend.core.secrets_integration import check_and_rotate_secrets

# Check and rotate secrets that need it
rotated = check_and_rotate_secrets()

# Manual rotation
secrets_manager.rotate_secret("api_key_gemini", "new-api-key-value")
```

## Secret Types

| Type | Usage | Example Keys |
|------|-------|--------------|
| `DATABASE_URL` | Database connections | `database_url`, `db_replica_url` |
| `API_KEY` | External API keys | `api_key_gemini`, `api_key_openai` |
| `JWT_PRIVATE_KEY` | JWT signing keys | `jwt_private_key` |
| `JWT_PUBLIC_KEY` | JWT verification keys | `jwt_public_key` |
| `REDIS_URL` | Redis connections | `redis_url`, `redis_cache_url` |
| `SMTP_PASSWORD` | Email credentials | `smtp_password` |
| `ENCRYPTION_KEY` | Data encryption | `encryption_key`, `backup_key` |
| `OAUTH_SECRET` | OAuth client secrets | `google_oauth_secret` |
| `WEBHOOK_SECRET` | Webhook verification | `github_webhook_secret` |
| `SIGNING_KEY` | General signing | `app_secret_key` |

## Security Best Practices

### 1. Environment-Specific Secrets
```python
# Use different secrets per environment
config = SecretConfig(
    environment="production",  # or "staging", "development"
    vault_path_prefix="ai_pdf_scholar"
)
```

### 2. Secret Rotation Schedule
```python
# Set appropriate rotation intervals
secrets_manager.set_secret(
    key="api_key",
    value="...",
    secret_type=SecretType.API_KEY,
    rotation_interval_days=90  # Rotate every 90 days
)
```

### 3. Audit Logging
```python
# Review audit logs
from datetime import datetime, timedelta

logs = secrets_manager.get_audit_log(
    start_time=datetime.utcnow() - timedelta(days=7),
    operation="get"
)
```

### 4. Health Monitoring
```python
from backend.core.secrets_integration import get_secret_health_status

health = get_secret_health_status()
print(f"Providers: {health['providers']}")
print(f"Secrets configured: {health['secrets']['total']}")
print(f"Rotation needed: {health['rotation_needed']}")
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy with Secrets

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v2

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v1
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: us-east-1

    - name: Deploy with secrets from AWS
      env:
        SECRET_PROVIDER: aws_secrets_manager
        ENVIRONMENT: production
      run: |
        python -m backend.core.secrets_integration
        python manage.py deploy
```

### Docker Integration

```dockerfile
FROM python:3.9

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application
COPY . /app
WORKDIR /app

# Set secrets provider
ENV SECRET_PROVIDER=vault
ENV VAULT_URL=https://vault.example.com

# Run with secrets management
CMD ["python", "-c", "from backend.core.secrets_integration import initialize_secrets_integration; initialize_secrets_integration()", "&&", "uvicorn", "main:app"]
```

## Troubleshooting

### Common Issues

1. **Secrets not found**
   ```python
   # Check provider health
   health = secrets_manager.health_check()
   print(f"Provider status: {health}")
   ```

2. **Permission denied**
   ```python
   # Verify authentication
   if provider == "vault":
       print(f"Vault authenticated: {secrets_manager._providers['vault'].client.is_authenticated()}")
   ```

3. **Migration failures**
   ```bash
   # Run with verbose logging
   python -m backend.core.secrets_migration --verbose --provider local
   ```

### Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Initialize with debug info
from backend.core.secrets import SecretConfig

config = SecretConfig(
    enable_audit_logging=True,
    cache_enabled=False  # Disable cache for debugging
)
```

## API Reference

### SecretsManager

```python
class SecretsManager:
    def get_secret(key: str, secret_type: Optional[SecretType] = None,
                   use_cache: bool = True, version: Optional[str] = None) -> Optional[str]

    def set_secret(key: str, value: str, secret_type: SecretType,
                   rotation_interval_days: Optional[int] = None,
                   expires_in_days: Optional[int] = None) -> bool

    def rotate_secret(key: str, new_value: str) -> bool

    def delete_secret(key: str) -> bool

    def list_secrets(prefix: Optional[str] = None) -> List[str]

    def check_rotation_needed() -> List[Tuple[str, SecretMetadata]]

    def get_audit_log(start_time: Optional[datetime] = None,
                      end_time: Optional[datetime] = None,
                      operation: Optional[str] = None) -> List[Dict]
```

### ApplicationConfig

```python
class ApplicationConfig:
    @classmethod
    def from_env(cls, secrets_manager: Optional[SecretsManager] = None) -> ApplicationConfig

    def get_database_url() -> str

    def get_redis_url() -> Optional[str]

    def get_api_key(service: str) -> Optional[str]

    def validate_secrets() -> List[str]

    def is_production() -> bool

    def is_development() -> bool
```

## Performance Considerations

### Caching Strategy
- Default cache TTL: 300 seconds (5 minutes)
- Cache can be disabled for sensitive operations
- Provider health checks cached for 60 seconds

### Network Optimization
- Connection pooling for Vault and AWS
- Retry logic with exponential backoff
- Fallback to local providers on network failure

### Resource Usage
- Local encrypted storage: ~1MB per 1000 secrets
- Memory cache: ~100KB for typical application
- Audit log retention: 30 days default

## Compliance and Standards

The secrets management system helps meet various compliance requirements:

- **GDPR**: Encryption at rest and in transit
- **PCI DSS**: Key rotation and access control
- **SOC 2**: Audit logging and monitoring
- **HIPAA**: Encryption and access controls
- **ISO 27001**: Security controls and procedures

## Future Enhancements

- [ ] Hardware Security Module (HSM) integration
- [ ] Multi-cloud provider support (Azure Key Vault, GCP Secret Manager)
- [ ] Secret sharing with Shamir's algorithm
- [ ] Automated security scanning
- [ ] GraphQL API for secret management
- [ ] Web UI for secret administration
- [ ] Kubernetes secrets integration
- [ ] Certificate management
- [ ] Dynamic secret generation
- [ ] Secret usage analytics

## Support

For issues or questions about the secrets management system:

1. Check the troubleshooting section above
2. Review audit logs for error details
3. Enable debug logging for more information
4. Contact the security team for production issues

## License

This secrets management system is part of the AI Enhanced PDF Scholar project and follows the same licensing terms.