# Configuration Migration Guide

## Overview

This guide documents the migration from scattered configuration files to a unified configuration management system. The new system provides:

- **Single Source of Truth**: All configuration in one place
- **Type Safety**: Full type checking and validation
- **Environment Awareness**: Environment-specific defaults and validation
- **Security Focus**: Built-in security validation and best practices

## Configuration Mapping

### Old → New Mapping

| Old File/Location | New Location | Notes |
|-------------------|--------------|-------|
| `backend/api/cors_config.py` | `ApplicationConfig.cors` | Unified with other config |
| `backend/api/rate_limit_config.py` | `ApplicationConfig.rate_limiting` | Type-safe with validation |
| Scattered env vars | Environment-specific defaults | Centralized loading |

## Usage Examples

### Before (Scattered Configs)

```python
# In different files
from backend.api.cors_config import get_cors_config
from backend.api.rate_limit_config import get_rate_limit_config

cors_config = get_cors_config()
rate_config = get_rate_limit_config()
```

### After (Unified Config)

```python
from backend.config import get_application_config

config = get_application_config()

# All settings available in one place
cors_settings = config.cors
rate_limit_settings = config.rate_limiting
database_settings = config.database
security_settings = config.security
```

## Environment Variables

### Required Environment Variables

| Variable | Description | Default | Required In |
|----------|-------------|---------|-------------|
| `ENVIRONMENT` | Application environment | development | All |
| `CORS_ORIGINS` | Allowed CORS origins | localhost in dev | Production |
| `GOOGLE_API_KEY` | Google Gemini API key | None | Production |
| `DATABASE_URL` | Database connection URL | SQLite | Production |
| `SECRET_KEY` | Application secret key | None | Production |

### Optional Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection for rate limiting | None |
| `LOG_LEVEL` | Logging level | INFO/DEBUG |
| `DB_POOL_SIZE` | Database connection pool size | 20 |
| `MAX_FILE_SIZE_MB` | Maximum upload file size | 100 |

## Migration Steps

### Step 1: Install Unified Config

1. Import the new configuration system:

```python
from backend.config import get_application_config, configure_logging

# Get configuration
config = get_application_config()

# Configure logging
configure_logging(config)
```

### Step 2: Update FastAPI Integration

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_application_config

app = FastAPI()
config = get_application_config()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors.allow_origins,
    allow_credentials=config.cors.allow_credentials,
    allow_methods=config.cors.allow_methods,
    allow_headers=config.cors.allow_headers,
    expose_headers=config.cors.expose_headers,
    max_age=config.cors.max_age
)
```

### Step 3: Update Rate Limiting

```python
from backend.config import get_application_config
from backend.api.middleware.rate_limiting import RateLimitMiddleware

config = get_application_config()
rate_config = config.rate_limiting

# Configure rate limiting middleware
app.add_middleware(
    RateLimitMiddleware,
    enabled=rate_config.enabled,
    default_limit=rate_config.default_limit,
    endpoint_limits=rate_config.endpoint_limits,
    redis_url=rate_config.redis_url
)
```

## Environment-Specific Configuration

### Development Environment

```bash
export ENVIRONMENT=development
export CORS_ORIGINS="http://localhost:3000,http://localhost:8000"
export DEBUG=true
export LOG_LEVEL=DEBUG
```

### Production Environment

```bash
export ENVIRONMENT=production
export CORS_ORIGINS="https://yourdomain.com,https://app.yourdomain.com"
export GOOGLE_API_KEY="your_actual_api_key"
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
export SECRET_KEY="your_secure_secret_key_32_chars_min"
export REDIS_URL="redis://localhost:6379"
export ENABLE_HTTPS=true
```

### Testing Environment

```bash
export ENVIRONMENT=testing
export DATABASE_URL="sqlite:///:memory:"
export RATE_LIMIT_DISABLE=true
export LOG_LEVEL=WARNING
```

## Security Improvements

### Automatic Validation

The new system automatically validates:

- **Production CORS**: No wildcards or localhost origins
- **HTTPS Enforcement**: Required in production
- **API Key Format**: Service-specific validation
- **Secret Strength**: Minimum length and complexity
- **Rate Limiting**: Enabled in production

### Security Checks

```python
from backend.config import get_application_config

config = get_application_config()

# Validate throws ConfigValidationError if critical issues found
try:
    config.validate()
except ConfigValidationError as e:
    logger.error(f"Configuration validation failed: {e}")
    for issue in e.issues:
        logger.error(f"  - {issue}")
```

## Testing Configuration

### Unit Tests

```python
import pytest
from backend.config import ApplicationConfig, Environment
from backend.config.validation import ConfigValidationError

def test_production_security():
    config = ApplicationConfig(environment=Environment.PRODUCTION)
    config.cors.allow_origins = ["*"]  # Should fail

    with pytest.raises(ConfigValidationError):
        config.validate()

def test_development_config():
    config = ApplicationConfig(environment=Environment.DEVELOPMENT)
    config.cors.allow_origins = ["http://localhost:3000"]

    # Should not raise
    config.validate()
```

### Test Configuration

```python
from backend.config import reset_configuration, get_application_config

def setup_test_config():
    """Setup test configuration."""
    reset_configuration()
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["RATE_LIMIT_DISABLE"] = "true"

    config = get_application_config()
    return config
```

## Backward Compatibility

### Legacy Support

For gradual migration, legacy functions are still available:

```python
# Still works (deprecated)
from backend.api.cors_config import get_cors_config

# Preferred new approach
from backend.config import get_application_config
config = get_application_config()
```

### Migration Timeline

1. **Phase 1**: New system available alongside old
2. **Phase 2**: Update all imports to use new system
3. **Phase 3**: Remove old configuration files
4. **Phase 4**: Full validation enforcement

## Benefits

### Developer Experience

- **Single Import**: All configuration from one module
- **Type Safety**: Full IDE support and type checking
- **Documentation**: Clear structure and validation rules
- **Testing**: Easy to mock and test different configurations

### Security

- **Automatic Validation**: Environment-specific security checks
- **Secret Management**: Built-in validation for API keys and secrets
- **Production Hardening**: Strict validation in production environments
- **Audit Trail**: Clear logging of configuration issues

### Maintainability

- **Single Source**: No more scattered configuration files
- **Consistent Patterns**: Same approach across all settings
- **Environment Parity**: Same structure across all environments
- **Easy Updates**: Central location for configuration changes

## Troubleshooting

### Common Issues

1. **Missing Environment Variables in Production**
   ```
   Error: Critical configuration issues found
   Solution: Set required environment variables
   ```

2. **CORS Configuration Issues**
   ```
   Error: Wildcard origins not allowed in production
   Solution: Set specific CORS_ORIGINS for your domains
   ```

3. **Invalid API Keys**
   ```
   Error: Invalid Google API key format
   Solution: Check API key format and service type
   ```

### Debug Commands

```bash
# Check current configuration
python -c "
from backend.config import get_application_config
config = get_application_config()
print(config.to_dict())
"

# Validate configuration
python -c "
from backend.config import get_application_config
try:
    config = get_application_config()
    config.validate()
    print('Configuration valid')
except Exception as e:
    print(f'Configuration error: {e}')
"
```

## Migration Checklist

- [ ] Install new configuration system
- [ ] Update FastAPI app initialization
- [ ] Update middleware configuration
- [ ] Set environment variables
- [ ] Test in development environment
- [ ] Test in staging environment
- [ ] Deploy to production
- [ ] Remove old configuration files
- [ ] Update documentation

---

**Note**: This migration provides immediate benefits in terms of type safety, validation, and maintainability while maintaining backward compatibility during the transition period.