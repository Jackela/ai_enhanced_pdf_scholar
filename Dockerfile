# ============================================================================
# AI Enhanced PDF Scholar - Multi-stage Docker Build
# Production-ready containerized deployment
# ============================================================================

# ============================================================================
# Stage 1: Frontend Build
# ============================================================================
FROM node:18-alpine AS frontend-builder

LABEL stage=frontend-builder
LABEL description="Build React/TypeScript frontend"

WORKDIR /app/frontend

# Copy package files for dependency installation
COPY frontend/package*.json ./

# Install frontend dependencies
RUN npm ci --only=production --silent

# Copy frontend source code
COPY frontend/ ./

# Build frontend for production
RUN npm run build

# ============================================================================
# Stage 2: Python Dependencies
# ============================================================================
FROM python:3.11-slim AS python-deps

LABEL stage=python-deps
LABEL description="Install Python dependencies"
ARG ENABLE_CACHE_ML=false
ENV ENABLE_CACHE_ML=${ENABLE_CACHE_ML}

# Install system dependencies for PDF processing and build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt requirements-scaling.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    if [ "$ENABLE_CACHE_ML" = "true" ]; then pip install --no-cache-dir -r requirements-scaling.txt; fi

# ============================================================================
# Stage 3: Production Image
# ============================================================================
FROM python:3.11-slim AS production

LABEL maintainer="AI Enhanced PDF Scholar Team"
LABEL version="2.0.0"
LABEL description="AI-powered PDF document management system"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libffi7 \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set work directory
WORKDIR /app

# Copy Python dependencies from deps stage
COPY --from=python-deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ ./src/
COPY backend/ ./backend/
COPY web_main.py ./
COPY config.py ./
COPY pytest.ini ./

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist/

# Create necessary directories
RUN mkdir -p /app/data/documents \
    && mkdir -p /app/data/vector_indexes \
    && mkdir -p /app/data/database \
    && mkdir -p /app/logs

# Set ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Environment variables
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production
ENV DATABASE_PATH=/app/data/database/library.db
ENV VECTOR_STORAGE_DIR=/app/data/vector_indexes
ENV LOG_LEVEL=INFO

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/system/health || exit 1

# Default command
CMD ["python", "web_main.py", "--host", "0.0.0.0", "--port", "8000"]

# ============================================================================
# Development Stage (for development with hot reload)
# ============================================================================
FROM production AS development

LABEL stage=development
LABEL description="Development environment with hot reload"

# Switch back to root to install dev dependencies
USER root

# Install development dependencies
RUN pip install --no-cache-dir pytest pytest-cov pytest-mock playwright

# Install Playwright browsers
RUN playwright install --with-deps chromium

# Switch back to appuser
USER appuser

# Override default command for development
CMD ["python", "web_main.py", "--host", "0.0.0.0", "--port", "8000", "--debug"]

# ============================================================================
# Testing Stage
# ============================================================================
FROM development AS testing

LABEL stage=testing
LABEL description="Testing environment"

# Copy test files
COPY tests/ ./tests/
COPY tests_e2e/ ./tests_e2e/
COPY test_*.py ./

# Default command for testing
CMD ["pytest", "tests/", "-v", "--cov=src", "--cov-report=html", "--cov-report=term-missing"]
