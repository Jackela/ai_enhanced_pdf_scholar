# Dependency Notes

## Core Dependencies
The main application dependencies are in `requirements.txt`. These are required for basic functionality.

## Optional Dependencies

### Scaling & Monitoring (requirements-scaling.txt)
Optional dependencies for advanced scaling and monitoring features:
- `prometheus-api-client` - Required for Prometheus integration in scaling scripts
- `boto3` - Required for AWS CloudFront CDN integration
- Machine learning libraries (scikit-learn, pandas, numpy) for scaling predictions
- `scikit-learn` is also used by the Smart Cache Manager; if it's missing, caching still works but ML-driven optimizations are disabled with a warning

To install:
```bash
pip install -r requirements-scaling.txt
```

### Development (requirements-dev.txt)
Development tools including linters, formatters, and testing frameworks.

### Production (requirements-prod.txt)
Optimized dependencies for production deployment.

## Import Issues Fixed

### 1. DatabaseMigrator Import
- Location: `src/database/__init__.py`
- Export: `from .modular_migrator import ModularDatabaseMigrator as DatabaseMigrator`

### 2. API Models Consolidation
All API models have been consolidated into `backend/api/models/multi_document_models.py` and properly exported through `backend/api/models/__init__.py`.

### 3. ApplicationMetrics Dependency Issue
The `ApplicationMetrics` class from `backend.services.metrics_service` cannot be used directly as a FastAPI dependency parameter. Created wrapper functions (`get_cache_service_dependency`) that don't expose internal types.

### 4. Optional boto3 Import
Made `boto3` import optional in `backend/services/l3_cdn_cache.py` with proper fallback handling.

## Running the API Server

```bash
# Basic run (without optional dependencies)
python backend/api/main.py

# Or using uvicorn
uvicorn backend.api.main:app --reload
```

## Known Issues
- The metrics collector now skips document-type metrics when the `file_type` column is absent; run the latest migrations if you expect those metrics
- Some scaling scripts require additional dependencies from `requirements-scaling.txt`
