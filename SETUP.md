# AI Enhanced PDF Scholar - Development Setup Guide

## 🚀 Quick Start for Developers

This guide will get you up and running with the AI Enhanced PDF Scholar development environment in under 15 minutes.

## 📋 Prerequisites

### Required Software
- **Python 3.11+** - Modern Python with async support
- **Node.js 18+** - For frontend development and build tools
- **Git 2.30+** - Version control
- **VS Code** (recommended) - With Python and TypeScript extensions

### System Requirements
- **Operating System**: Windows 10+, macOS 10.15+, or Linux (Ubuntu 20.04+)
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 2GB free space for dependencies and data
- **Network**: Stable internet connection for API access

### Optional Tools
- **Docker Desktop** - For containerized development (optional)
- **PostgreSQL** - For production database (SQLite used by default)
- **Redis** - For advanced caching (optional)

## 🛠️ Development Environment Setup

### 1. Repository Setup

```bash
# Clone the repository
git clone <repository-url>
cd ai_enhanced_pdf_scholar

# Create a development branch
git checkout -b feature/your-feature-name
```

### 2. Python Environment Setup

#### Option A: Using Virtual Environment (Recommended)
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

#### Option B: Using Conda
```bash
# Create conda environment
conda create -n pdf_scholar python=3.11
conda activate pdf_scholar

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Frontend Environment Setup

```bash
# Navigate to frontend directory
cd frontend

# Install Node.js dependencies
npm install

# Or using Yarn
yarn install

# Return to project root
cd ..
```

### 4. Environment Configuration

#### Create Environment File
```bash
# Copy example environment file
cp .env.example .env

# Edit with your settings
# Windows
notepad .env

# macOS/Linux
nano .env
```

#### Required Environment Variables
```env
# API Configuration
GOOGLE_API_KEY=your_google_gemini_api_key_here
API_HOST=localhost
API_PORT=8000

# Database Configuration
DATABASE_URL=sqlite:///./data/documents.db
DATABASE_POOL_SIZE=20

# Frontend Configuration
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

# Development Settings
DEBUG=true
LOG_LEVEL=INFO
ENVIRONMENT=development

# Optional: Advanced Features
ENABLE_CACHING=true
CACHE_TTL=3600
MAX_UPLOAD_SIZE=100MB
```

#### Getting API Keys

##### Google Gemini API Key
1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Create a new API key
4. Copy the key to your `.env` file
5. **Note**: Free tier includes generous usage limits

### 5. Database Initialization

```bash
# Initialize database with latest schema
python -m src.database.migrations

# Verify database setup
python -c "from src.database.connection import DatabaseConnection; print('Database OK')"
```

### 6. Development Server Startup

#### Backend Server
```bash
# Start FastAPI development server
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Alternative: Using Python directly
python -m src.main

# Server will be available at: http://localhost:8000
# API documentation at: http://localhost:8000/docs
```

#### Frontend Server
```bash
# In a new terminal, navigate to frontend
cd frontend

# Start Vite development server
npm run dev

# Or using Yarn
yarn dev

# Frontend will be available at: http://localhost:3000
```

### 7. Verification Steps

#### Test Backend
```bash
# Test API health
curl http://localhost:8000/api/system/health

# Expected response:
# {"status": "healthy", "timestamp": "2025-01-21T..."}
```

#### Test Frontend
1. Open http://localhost:3000 in your browser
2. Verify the interface loads correctly
3. Check browser console for any errors
4. Try uploading a sample PDF document

#### Run Test Suite
```bash
# Run Python tests
pytest tests/unit -v

# Run JavaScript tests
cd frontend && npm run test

# Run full test suite
npm run test:all
```

## 🔧 IDE Configuration

### Visual Studio Code Setup

#### Recommended Extensions
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.black-formatter",
    "charliermarsh.ruff",
    "ms-python.mypy-type-checker",
    "bradlc.vscode-tailwindcss",
    "esbenp.prettier-vscode",
    "ms-vscode.vscode-typescript-next"
  ]
}
```

#### VS Code Settings
```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.ruffEnabled": true,
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "[typescript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  }
}
```

#### Python Debugging Configuration
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI Debug",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/src/main.py",
      "console": "integratedTerminal",
      "justMyCode": false,
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    },
    {
      "name": "Pytest Debug",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/unit", "-v"],
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

### PyCharm Configuration

#### Project Setup
1. Open project in PyCharm
2. Configure Python interpreter to use your virtual environment
3. Mark `src` directory as "Sources Root"
4. Configure code style to use Black formatter
5. Enable Ruff for linting

#### Run Configurations
```python
# FastAPI Server
# Script path: src/main.py
# Environment variables: Load from .env
# Python interpreter: Project venv

# Pytest Runner
# Target: tests/unit
# Additional arguments: -v --cov=src
# Environment variables: Load from .env
```

## 🧪 Development Workflow

### Code Quality Setup

#### Pre-commit Hooks (Recommended)
```bash
# Install pre-commit
pip install pre-commit

# Setup git hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

#### Manual Quality Checks
```bash
# Python code formatting
black src tests

# Python linting
ruff check src tests

# Type checking
mypy src

# Frontend formatting
cd frontend && npm run format

# Frontend linting
cd frontend && npm run lint
```

### Testing Strategy

#### Backend Testing
```bash
# Unit tests only
pytest tests/unit -v

# With coverage report
pytest tests/unit --cov=src --cov-report=html

# Integration tests
pytest tests/integration -v

# Performance tests
pytest tests/performance -v --benchmark-only
```

#### Frontend Testing
```bash
cd frontend

# Unit tests
npm run test:unit

# Integration tests
npm run test:integration

# E2E tests
npm run test:e2e

# All tests
npm run test
```

#### Database Testing
```bash
# Test database migrations
python -m src.database.migrations --test

# Test repository layer
pytest tests/repositories -v

# Test database performance
pytest tests/performance/test_database.py
```

### Development Database

#### Reset Database
```bash
# Backup current database
cp data/documents.db data/documents.backup.db

# Reset to clean state
rm data/documents.db
python -m src.database.migrations

# Restore from backup if needed
cp data/documents.backup.db data/documents.db
```

#### Sample Data Setup
```bash
# Load sample documents (optional)
python scripts/load_sample_data.py

# Generate test citations
python scripts/generate_test_citations.py

# Create performance test data
python scripts/create_benchmark_data.py
```

## 🐳 Docker Development (Optional)

### Docker Compose Setup

#### Development Compose File
```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - ./src:/app/src
      - ./data:/app/data
    environment:
      - DEBUG=true
      - DATABASE_URL=sqlite:///./data/documents.db
    
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports:
      - "3000:3000"
    volumes:
      - ./frontend/src:/app/src
    environment:
      - VITE_API_URL=http://localhost:8000
```

#### Docker Development Commands
```bash
# Build and start services
docker-compose -f docker-compose.dev.yml up --build

# Start in background
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Stop services
docker-compose -f docker-compose.dev.yml down
```

## 🔍 Debugging and Troubleshooting

### Common Setup Issues

#### Python Environment Issues
```bash
# Issue: Import errors
# Solution: Ensure PYTHONPATH includes project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Issue: Package conflicts
# Solution: Create fresh virtual environment
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Issue: PyMuPDF installation problems
# Solution: Install system dependencies (Linux)
sudo apt-get install libmupdf-dev
pip install --no-binary :all: PyMuPDF
```

#### Database Issues
```bash
# Issue: Database locked errors
# Solution: Close all connections and restart
python -c "from src.database.connection import DatabaseConnection; DatabaseConnection.close_all_connections()"

# Issue: Migration failures
# Solution: Reset database and re-run migrations
rm data/documents.db
python -m src.database.migrations

# Issue: Permission errors
# Solution: Fix file permissions
chmod 755 data/
chmod 644 data/documents.db
```

#### Frontend Issues
```bash
# Issue: Node modules conflicts
# Solution: Clear and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install

# Issue: Port already in use
# Solution: Kill existing processes
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# macOS/Linux
lsof -ti:3000 | xargs kill -9

# Issue: Build failures
# Solution: Clear cache and rebuild
npm run clean
npm run build
```

#### API Key Issues
```bash
# Issue: Invalid API key errors
# Solution: Verify key format and permissions
python -c "import os; print('API Key:', os.getenv('GOOGLE_API_KEY', 'NOT SET'))"

# Issue: Rate limiting
# Solution: Implement backoff strategy or upgrade plan
# Check API usage in Google Console
```

### Performance Debugging

#### Backend Performance
```bash
# Profile API endpoints
python -m cProfile -o profile.stats src/main.py

# Memory usage analysis
python -m memory_profiler src/services/document_service.py

# Database query analysis
# Enable SQL logging in database connection
```

#### Frontend Performance
```bash
cd frontend

# Bundle analysis
npm run build:analyze

# Performance profiling
npm run dev:profile

# Lighthouse audit
npx lighthouse http://localhost:3000 --output html
```

### Debugging Tools

#### Backend Debugging
```python
# Add debugging breakpoints
import pdb; pdb.set_trace()

# Or using ipdb for enhanced debugging
import ipdb; ipdb.set_trace()

# Async debugging
import asyncio
asyncio.get_event_loop().set_debug(True)
```

#### Database Debugging
```python
# Enable SQL query logging
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Database connection debugging
from src.database.connection import DatabaseConnection
db = DatabaseConnection("./data/documents.db")
db.execute("PRAGMA table_info(documents)")
```

#### Frontend Debugging
```javascript
// React Developer Tools
// Available in browser extension

// Redux DevTools (if using Redux)
// Install browser extension

// Console debugging
console.log('Debug info:', data);
console.trace('Call stack');

// Performance debugging
console.time('operation');
// ... code ...
console.timeEnd('operation');
```

## 📈 Performance Optimization

### Development Performance

#### Python Optimization
```bash
# Use faster package installations
pip install --use-pep517 --no-build-isolation

# Enable bytecode caching
export PYTHONDONTWRITEBYTECODE=0

# Use faster test runner
pytest -x --ff tests/unit  # Stop on first failure, run failed tests first
```

#### Frontend Optimization
```bash
cd frontend

# Use faster package manager
npm install --prefer-offline

# Enable hot module replacement
npm run dev:hmr

# Parallel type checking
npm run type-check:watch
```

#### Database Optimization
```sql
-- Optimize SQLite for development
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 131072;  -- 512MB cache
PRAGMA temp_store = MEMORY;
```

### Resource Monitoring

#### System Resources
```bash
# Monitor CPU and memory usage
top -p $(pgrep -f "uvicorn\|node")

# Monitor disk I/O
iotop -p $(pgrep -f "uvicorn\|node")

# Monitor network usage
nethogs
```

#### Application Metrics
```bash
# Backend metrics
curl http://localhost:8000/api/system/metrics

# Database metrics
python scripts/database_stats.py

# Cache hit rates
python scripts/cache_analysis.py
```

## 🚀 Advanced Development Setup

### Multi-Service Development

#### Microservices Setup (Future)
```bash
# Citation service (separate process)
python -m src.services.citation_service --port 8001

# RAG service (separate process)  
python -m src.services.rag_service --port 8002

# Main API server
uvicorn src.main:app --port 8000
```

#### External Services
```bash
# Redis for caching (optional)
docker run -d -p 6379:6379 redis:alpine

# PostgreSQL for production testing
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=dev postgres:13
```

### Development Tools Integration

#### AI Development Tools
```bash
# Install AI development dependencies
pip install jupyter notebook ipython

# Start Jupyter for data exploration
jupyter notebook notebooks/

# Interactive Python with project context
ipython -c "from src.services.rag_service import RAGService; rag = RAGService()"
```

#### API Development
```bash
# API testing with HTTPie
pip install httpie

# Test endpoints
http GET localhost:8000/api/documents
http POST localhost:8000/api/documents/upload Content-Type:multipart/form-data file@test.pdf

# OpenAPI client generation
openapi-generator-cli generate -i http://localhost:8000/openapi.json -g python-aiohttp
```

## 📚 Learning Resources

### Project-Specific Documentation
- **[PROJECT_DOCS.md](PROJECT_DOCS.md)** - Complete architecture overview
- **[API_ENDPOINTS.md](API_ENDPOINTS.md)** - API reference and examples
- **[TESTING.md](TESTING.md)** - Testing strategy and guidelines
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Contribution guidelines

### Technology Documentation
- **[FastAPI Documentation](https://fastapi.tiangolo.com/)** - Backend framework
- **[React Documentation](https://react.dev/)** - Frontend framework
- **[LlamaIndex Documentation](https://docs.llamaindex.ai/)** - RAG framework
- **[SQLite Documentation](https://sqlite.org/docs.html)** - Database engine

### Development Best Practices
- **[Python Type Hints](https://docs.python.org/3/library/typing.html)** - Type safety
- **[Modern JavaScript](https://developer.mozilla.org/en-US/docs/Web/JavaScript)** - Frontend development
- **[Git Workflow](https://docs.github.com/en/get-started/quickstart/github-flow)** - Version control
- **[Testing Best Practices](https://docs.pytest.org/en/stable/best_practices.html)** - Test strategy

---

## 🤝 Getting Help

### Development Support
- **GitHub Issues** - Bug reports and feature requests
- **Discussion Forum** - Development questions and ideas
- **Code Review** - Pull request feedback and guidance
- **Documentation** - Comprehensive guides and references

### Quick Support Checklist
- ✅ Check this setup guide for common issues
- ✅ Review error messages and logs carefully
- ✅ Search existing GitHub issues
- ✅ Include environment details when reporting issues
- ✅ Provide minimal reproduction cases

---

*This setup guide is regularly updated. For the latest version, check the project repository.*

*Last Updated: 2025-01-21*
*Version: 2.1.0*