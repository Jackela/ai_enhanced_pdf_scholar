# 🛠️ Developer Guide - AI Enhanced PDF Scholar

## 🎯 Overview

This comprehensive guide helps developers understand, set up, and contribute to the **AI Enhanced PDF Scholar** platform. Whether you're setting up a development environment, understanding the architecture, or implementing new features, this guide provides the essential information you need.

## 📚 Table of Contents

- [🚀 Quick Start](#-quick-start)
- [🏗️ Architecture Overview](#-architecture-overview)
- [🔧 Development Environment](#-development-environment)
- [📁 Project Structure](#-project-structure)
- [🔄 Development Workflow](#-development-workflow)
- [🧪 Testing Strategy](#-testing-strategy)
- [📊 Performance Optimization](#-performance-optimization)
- [🔒 Security Implementation](#-security-implementation)
- [📡 API Development](#-api-development)
- [🖥️ Frontend Development](#-frontend-development)
- [🗄️ Database Management](#-database-management)
- [🚀 Deployment Guide](#-deployment-guide)
- [🔍 Debugging & Troubleshooting](#-debugging--troubleshooting)

---

## 🚀 Quick Start

### Prerequisites Checklist
- [ ] **Python 3.11+** installed with pip
- [ ] **Conda** (recommended for environment management)
- [ ] **Node.js 18+** with npm or pnpm
- [ ] **Git** for version control
- [ ] **Google Gemini API Key** for RAG functionality
- [ ] **Redis** (optional, for production caching)
- [ ] **VS Code** or **PyCharm** (recommended IDEs)

### 5-Minute Setup
```bash
# 1. Clone and setup repository
git clone https://github.com/Jackela/ai_enhanced_pdf_scholar.git
cd ai_enhanced_pdf_scholar

# 2. Create Python environment
conda create -n pdf_scholar_dev python=3.11 -y
conda activate pdf_scholar_dev

# 3. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 4. Setup frontend
cd frontend && npm install && cd ..

# 5. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 6. Initialize database
python scripts/init_dev_database.py

# 7. Run tests to verify setup
python scripts/test_runner.py --quick

# 8. Start development servers
# Terminal 1: Backend
uvicorn web_main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

### Verification Checklist
- [ ] Backend API: http://localhost:8000/api/docs
- [ ] Frontend App: http://localhost:5173
- [ ] Health Check: http://localhost:8000/api/system/health
- [ ] Tests Pass: `python scripts/test_runner.py --quick`

---

## 🏗️ Architecture Overview

### High-Level Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        A[React + TypeScript]
        B[Tailwind CSS]
        C[Security Hooks]
    end

    subgraph "API Layer"
        D[FastAPI]
        E[JWT Auth]
        F[Rate Limiting]
        G[CORS Security]
    end

    subgraph "Service Layer"
        H[RAG Services]
        I[Citation Services]
        J[Document Services]
        K[Security Services]
    end

    subgraph "Repository Layer"
        L[Document Repo]
        M[Citation Repo]
        N[User Repo]
    end

    subgraph "Data Layer"
        O[SQLite/PostgreSQL]
        P[Vector Indexes]
        Q[File Storage]
    end

    subgraph "External Services"
        R[Google Gemini API]
        S[Redis Cache]
    end

    A --> D
    D --> H
    H --> L
    L --> O
    H --> R
    D --> S
```

### Core Design Principles

#### SOLID Principles Implementation
1. **Single Responsibility Principle (SRP)**
   ```python
   # Each service has a single, well-defined responsibility
   class CitationExtractionService:
       """Responsible only for extracting citations from documents."""

   class CitationFormattingService:
       """Responsible only for formatting citations in different styles."""
   ```

2. **Open/Closed Principle (OCP)**
   ```python
   # Extensible through interfaces without modifying existing code
   class ICitationParser(ABC):
       @abstractmethod
       def parse(self, text: str) -> List[Citation]:
           pass

   class APACitationParser(ICitationParser):
       def parse(self, text: str) -> List[Citation]:
           # APA-specific implementation

   class MLACitationParser(ICitationParser):
       def parse(self, text: str) -> List[Citation]:
           # MLA-specific implementation
   ```

3. **Liskov Substitution Principle (LSP)**
   ```python
   # All repository implementations are substitutable
   def process_documents(repo: IDocumentRepository):
       # Works with any repository implementation
       documents = repo.get_all()
       for doc in documents:
           repo.update_status(doc.id, "processed")
   ```

4. **Interface Segregation Principle (ISP)**
   ```python
   # Clients depend only on interfaces they use
   class IReadableRepository(ABC):
       @abstractmethod
       def get_by_id(self, id: int) -> Optional[T]:
           pass

   class IWritableRepository(ABC):
       @abstractmethod
       def save(self, entity: T) -> T:
           pass
   ```

5. **Dependency Inversion Principle (DIP)**
   ```python
   # High-level modules depend on abstractions
   class DocumentService:
       def __init__(
           self,
           repo: IDocumentRepository,  # Abstraction
           indexer: IDocumentIndexer   # Abstraction
       ):
           self.repo = repo
           self.indexer = indexer
   ```

### Modular RAG Architecture

#### Service Decomposition
```python
class RAGCoordinator:
    """Orchestrates RAG operations across specialized services."""

    def __init__(
        self,
        index_builder: IRAGIndexBuilder,
        query_engine: IRAGQueryEngine,
        recovery_service: IRAGRecoveryService,
        file_manager: IRAGFileManager
    ):
        # Dependency injection for loose coupling

class RAGIndexBuilder:
    """Specialized service for building and managing vector indexes."""

class RAGQueryEngine:
    """Optimized service for executing RAG queries."""

class RAGRecoveryService:
    """Service for detecting and recovering from index corruption."""

class RAGFileManager:
    """Service for managing RAG-related file operations."""
```

---

## 🔧 Development Environment

### IDE Configuration

#### VS Code Setup
Install recommended extensions:
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.black-formatter",
    "ms-python.pylint",
    "ms-python.mypy-type-checker",
    "bradlc.vscode-tailwindcss",
    "esbenp.prettier-vscode",
    "dbaeumer.vscode-eslint"
  ]
}
```

Settings configuration (`.vscode/settings.json`):
```json
{
  "python.defaultInterpreterPath": "./venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.pylintEnabled": true,
  "python.formatting.provider": "black",
  "typescript.preferences.importModuleSpecifier": "relative",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  },
  "tailwindCSS.includeLanguages": {
    "typescript": "javascript",
    "typescriptreact": "javascript"
  }
}
```

#### PyCharm Setup
1. Configure Python interpreter to use Conda environment
2. Enable type checking with MyPy
3. Configure code style to use Black formatter
4. Set up test runner for pytest

### Environment Variables

#### Development Configuration (`.env.development`)
```bash
# Core Configuration
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Database
DATABASE_URL=sqlite:///./pdf_scholar_dev.db
TEST_DATABASE_URL=sqlite:///:memory:

# API Keys
GOOGLE_API_KEY=your_gemini_api_key_here

# CORS (Development)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8000

# Optional: Redis for caching
REDIS_URL=redis://localhost:6379/0

# File Storage
UPLOAD_DIRECTORY=./uploads
MAX_FILE_SIZE=100MB

# Security (Development)
SECRET_KEY=development-secret-key-change-in-production
JWT_ALGORITHM=RS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Rate Limiting (Relaxed for development)
RATE_LIMIT_REQUESTS_PER_MINUTE=1000
RATE_LIMIT_GLOBAL_REQUESTS_PER_HOUR=10000

# Performance
ENABLE_QUERY_CACHING=true
CACHE_TTL_SECONDS=3600
MAX_CONCURRENT_UPLOADS=10
```

#### Production Configuration (`.env.production`)
```bash
# Core Configuration
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database (PostgreSQL recommended for production)
DATABASE_URL=postgresql://user:password@localhost:5432/pdf_scholar
REDIS_URL=redis://localhost:6379/0

# API Keys (Use secure key management)
GOOGLE_API_KEY=${GOOGLE_API_KEY}

# CORS (Restrict to your domain)
CORS_ORIGINS=https://yourapp.com,https://api.yourapp.com

# Security (Use strong secrets)
SECRET_KEY=${JWT_SECRET_KEY}
JWT_PRIVATE_KEY_PATH=/etc/ssl/private/jwt_private.pem
JWT_PUBLIC_KEY_PATH=/etc/ssl/certs/jwt_public.pem

# Rate Limiting (Production values)
RATE_LIMIT_REQUESTS_PER_MINUTE=100
RATE_LIMIT_GLOBAL_REQUESTS_PER_HOUR=1000

# Performance
ENABLE_QUERY_CACHING=true
CACHE_TTL_SECONDS=3600
MAX_CONCURRENT_UPLOADS=5
```

### Docker Development Environment

#### Docker Compose for Development
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
      - .:/app
      - ./uploads:/app/uploads
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=postgresql://postgres:password@db:5432/pdf_scholar_dev
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: pdf_scholar_dev
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

Usage:
```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f backend

# Run tests in container
docker-compose -f docker-compose.dev.yml exec backend python scripts/test_runner.py --unit

# Cleanup
docker-compose -f docker-compose.dev.yml down -v
```

---

## 📁 Project Structure

### Backend Structure
```
backend/
├── api/                        # FastAPI application
│   ├── auth/                   # Authentication routes and middleware
│   │   ├── __init__.py
│   │   ├── routes.py          # Auth endpoints
│   │   └── rbac.py            # Role-based access control
│   ├── middleware/             # Custom middleware
│   │   ├── __init__.py
│   │   ├── error_handling.py  # Global error handling
│   │   ├── rate_limiting.py   # Rate limiting middleware
│   │   └── security_headers.py # Security headers
│   ├── routes/                 # API route modules
│   │   ├── __init__.py
│   │   ├── documents.py       # Document management
│   │   ├── rag.py             # RAG operations
│   │   ├── citations.py       # Citation analysis
│   │   └── system.py          # System endpoints
│   ├── models.py               # Pydantic request/response models
│   ├── dependencies.py        # FastAPI dependency injection
│   ├── main.py                 # FastAPI app initialization
│   └── websocket_manager.py   # WebSocket connection management
├── services/                   # Business logic services
│   ├── __init__.py
│   ├── streaming_upload_service.py
│   ├── security_service.py
│   ├── encryption_service.py
│   └── metrics_service.py
├── config/                     # Configuration management
│   ├── __init__.py
│   ├── settings.py            # Application settings
│   ├── database.py            # Database configuration
│   └── logging.py             # Logging configuration
└── database/                   # Database layer
    ├── __init__.py
    ├── models.py              # Database models
    ├── migrations.py          # Database migrations
    └── repositories.py        # Data access layer
```

### Frontend Structure
```
frontend/
├── src/
│   ├── components/            # React components
│   │   ├── ui/               # Reusable UI components
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Modal.tsx
│   │   │   └── SecureMessage.tsx
│   │   ├── features/         # Feature-specific components
│   │   │   ├── DocumentUpload.tsx
│   │   │   ├── RAGQuery.tsx
│   │   │   └── CitationViewer.tsx
│   │   └── layout/           # Layout components
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── Layout.tsx
│   ├── hooks/                # Custom React hooks
│   │   ├── useAuth.ts
│   │   ├── useRAG.ts
│   │   ├── useSecurity.ts
│   │   └── useWebSocket.ts
│   ├── services/             # API and external services
│   │   ├── api.ts           # Main API client
│   │   ├── auth.ts          # Authentication service
│   │   ├── documents.ts     # Document operations
│   │   └── websocket.ts     # WebSocket client
│   ├── utils/                # Utility functions
│   │   ├── security.ts      # XSS protection utilities
│   │   ├── validation.ts    # Form validation
│   │   └── formatting.ts    # Data formatting
│   ├── types/                # TypeScript type definitions
│   │   ├── api.ts          # API types
│   │   ├── document.ts     # Document types
│   │   └── user.ts         # User types
│   ├── styles/               # Styling
│   │   ├── globals.css     # Global styles
│   │   └── components.css  # Component styles
│   ├── App.tsx              # Main application component
│   ├── main.tsx            # Application entry point
│   └── vite-env.d.ts       # Vite type definitions
├── public/                   # Static assets
├── tests/                    # Frontend tests
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── e2e/               # End-to-end tests
├── package.json
├── tsconfig.json
├── tailwind.config.js
├── vite.config.ts
└── vitest.config.ts
```

### Core Source Structure
```
src/
├── controllers/              # Application controllers
│   ├── __init__.py
│   ├── library_controller.py # Document library operations
│   └── base_controller.py   # Base controller class
├── services/                 # Business logic services
│   ├── __init__.py
│   ├── enhanced_rag_service.py # Main RAG service
│   ├── rag/                 # Modular RAG services
│   │   ├── __init__.py
│   │   ├── coordinator.py   # RAG orchestration
│   │   ├── index_builder.py # Vector index building
│   │   ├── query_engine.py  # Query execution
│   │   ├── recovery_service.py # Index recovery
│   │   └── file_manager.py  # File operations
│   ├── citation_service.py  # Citation analysis
│   ├── document_library_service.py # Document management
│   └── security_service.py  # Security utilities
├── database/                # Data layer
│   ├── __init__.py
│   ├── connection.py        # Database connection management
│   ├── models.py           # SQLAlchemy models
│   ├── repositories.py     # Repository pattern implementation
│   └── migrations.py       # Database migrations
└── utils/                   # Utility modules
    ├── __init__.py
    ├── file_utils.py       # File operations
    ├── security_utils.py   # Security helpers
    └── performance_utils.py # Performance utilities
```

### Configuration Files
```
.
├── .env.example              # Environment template
├── .gitignore               # Git ignore rules
├── .pre-commit-config.yaml  # Pre-commit hooks
├── pytest.ini              # Pytest configuration
├── pyproject.toml           # Python project configuration
├── requirements.txt         # Python dependencies
├── requirements-dev.txt     # Development dependencies
├── docker-compose.yml       # Production Docker setup
├── docker-compose.dev.yml   # Development Docker setup
├── Dockerfile              # Production Docker image
├── Dockerfile.dev          # Development Docker image
└── web_main.py            # Application entry point
```

---

## 🔄 Development Workflow

### Feature Development Process

#### 1. Planning Phase
```bash
# Create feature branch
git checkout -b feature/advanced-citation-network-analysis

# Document the feature in GitHub issue
# Include:
# - User stories
# - Acceptance criteria
# - Technical specifications
# - Security considerations
# - Performance requirements
```

#### 2. Implementation Phase

##### Backend Development
```python
# 1. Define data models
@dataclass
class CitationNetwork:
    """Represents a citation network with nodes and relationships."""
    root_document_id: int
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]
    metadata: NetworkMetadata

# 2. Create repository interface
class ICitationNetworkRepository(ABC):
    @abstractmethod
    def build_network(self, document_id: int, max_depth: int) -> CitationNetwork:
        pass

# 3. Implement service
class CitationNetworkService:
    def __init__(self, repo: ICitationNetworkRepository):
        self.repo = repo

    def analyze_network(self, document_id: int, config: NetworkConfig) -> NetworkAnalysis:
        """Analyze citation relationships and generate insights."""
        network = self.repo.build_network(document_id, config.max_depth)
        return self._compute_network_metrics(network)

# 4. Add API endpoint
@router.post("/citations/network/analyze")
async def analyze_citation_network(
    request: NetworkAnalysisRequest,
    service: CitationNetworkService = Depends(get_citation_network_service)
) -> NetworkAnalysisResponse:
    """Analyze citation network and return insights."""
    try:
        analysis = service.analyze_network(request.document_id, request.config)
        return NetworkAnalysisResponse(
            success=True,
            data=analysis,
            message="Network analysis completed successfully"
        )
    except Exception as e:
        logger.error(f"Network analysis failed: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")
```

##### Frontend Development
```typescript
// 1. Define types
interface CitationNetwork {
  rootDocumentId: number
  nodes: NetworkNode[]
  edges: NetworkEdge[]
  metadata: NetworkMetadata
}

interface NetworkNode {
  id: string
  title: string
  type: 'document' | 'citation'
  metadata: NodeMetadata
}

// 2. Create API service
class CitationNetworkAPI {
  async analyzeNetwork(documentId: number, config: NetworkConfig): Promise<NetworkAnalysis> {
    const response = await fetch(`${this.baseUrl}/api/citations/network/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.token}`
      },
      body: JSON.stringify({ document_id: documentId, config })
    })

    if (!response.ok) {
      throw new APIError(`Network analysis failed: ${response.statusText}`)
    }

    return response.json()
  }
}

// 3. Create React hook
export const useCitationNetwork = () => {
  const [network, setNetwork] = useState<CitationNetwork | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const analyzeNetwork = useCallback(async (documentId: number, config: NetworkConfig) => {
    setLoading(true)
    setError(null)

    try {
      const api = new CitationNetworkAPI()
      const analysis = await api.analyzeNetwork(documentId, config)
      setNetwork(analysis.network)
    } catch (err) {
      setError(err as Error)
    } finally {
      setLoading(false)
    }
  }, [])

  return { network, loading, error, analyzeNetwork }
}

// 4. Create component
export const CitationNetworkViewer: React.FC<{documentId: number}> = ({documentId}) => {
  const { network, loading, error, analyzeNetwork } = useCitationNetwork()

  useEffect(() => {
    analyzeNetwork(documentId, { maxDepth: 3, minConfidence: 0.7 })
  }, [documentId, analyzeNetwork])

  if (loading) return <LoadingSpinner />
  if (error) return <ErrorDisplay error={error} />
  if (!network) return <EmptyState />

  return (
    <div className="citation-network-viewer">
      <NetworkVisualization network={network} />
      <NetworkMetrics metadata={network.metadata} />
    </div>
  )
}
```

#### 3. Testing Phase
```bash
# Write comprehensive tests
python -m pytest tests/unit/test_citation_network_service.py -v
python -m pytest tests/integration/test_citation_network_api.py -v

# Frontend tests
cd frontend
npm test -- CitationNetworkViewer.test.tsx
npm run test:e2e -- citation-network.spec.ts

# Security testing
python scripts/test_security.py --feature citation_network

# Performance testing
python scripts/benchmark_citation_network.py
```

#### 4. Code Review Checklist
- [ ] **Functionality**: Feature works as specified
- [ ] **Code Quality**: Clean, readable, maintainable code
- [ ] **Architecture**: Follows SOLID principles
- [ ] **Security**: No security vulnerabilities introduced
- [ ] **Performance**: No significant performance regression
- [ ] **Testing**: Comprehensive test coverage
- [ ] **Documentation**: Code comments and API documentation
- [ ] **Error Handling**: Proper error handling and logging

### Daily Development Tasks

#### Morning Routine
```bash
# Update local repository
git checkout main
git pull upstream main

# Check for dependency updates
pip list --outdated
cd frontend && npm outdated

# Run health checks
python scripts/system_health_check.py
python scripts/test_runner.py --quick

# Review overnight CI/CD results
gh pr checks --verbose
```

#### Development Session
```bash
# Start development environment
python scripts/start_dev_environment.py

# This script:
# 1. Activates conda environment
# 2. Starts backend server with hot reload
# 3. Starts frontend dev server
# 4. Opens browser tabs for development
# 5. Starts log monitoring
```

#### End of Day Routine
```bash
# Run complete test suite
python scripts/comprehensive_test_suite.py

# Code quality check
python scripts/code_quality_check.py

# Commit and push changes
git add .
git commit -m "feat: implement citation network visualization"
git push origin feature/citation-network-viz

# Update documentation if needed
python scripts/update_documentation.py --auto
```

---

## 🧪 Testing Strategy

### Test Pyramid Structure

#### Unit Tests (Base Layer - 70%)
**Purpose**: Test individual components in isolation

```python
# Example: Citation service unit test
class TestCitationExtractionService:
    @pytest.fixture
    def service(self):
        mock_repo = Mock(spec=ICitationRepository)
        mock_parser = Mock(spec=ICitationParser)
        return CitationExtractionService(mock_repo, mock_parser)

    def test_extract_citations_with_confidence_threshold(self, service):
        """Test citation extraction respects confidence threshold."""
        # Given
        document_text = "Sample citation: Smith, J. (2023). Test paper."
        service.parser.parse.return_value = [
            Citation(text="Smith, J. (2023)", confidence=0.95),
            Citation(text="Low confidence citation", confidence=0.3)
        ]

        # When
        result = service.extract_citations(document_text, confidence_threshold=0.8)

        # Then
        assert len(result.citations) == 1
        assert result.citations[0].confidence >= 0.8

    def test_extract_citations_handles_empty_document(self, service):
        """Test extraction handles empty document gracefully."""
        # Given/When
        result = service.extract_citations("", confidence_threshold=0.8)

        # Then
        assert len(result.citations) == 0
        assert result.success is True
```

#### Integration Tests (Middle Layer - 20%)
**Purpose**: Test component interactions and API endpoints

```python
# Example: API integration test
class TestDocumentUploadAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    @pytest.fixture
    def auth_token(self, client):
        response = client.post("/api/auth/login", json={
            "username": "test@example.com",
            "password": "testpass"
        })
        return response.json()["data"]["access_token"]

    def test_upload_and_process_document(self, client, auth_token, sample_pdf):
        """Test complete document upload and processing workflow."""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Upload document
        with open(sample_pdf, "rb") as f:
            response = client.post(
                "/api/documents",
                files={"file": ("test.pdf", f, "application/pdf")},
                data={"extract_metadata": "true"},
                headers=headers
            )

        assert response.status_code == 201
        document_data = response.json()["data"]
        assert document_data["title"] is not None

        # Verify document is accessible
        doc_id = document_data["id"]
        response = client.get(f"/api/documents/{doc_id}", headers=headers)
        assert response.status_code == 200

        # Verify RAG indexing
        response = client.post(
            f"/api/rag/index/{doc_id}",
            headers=headers
        )
        assert response.status_code == 200
```

#### End-to-End Tests (Top Layer - 10%)
**Purpose**: Test complete user workflows

```typescript
// Example: E2E test with Playwright
import { test, expect } from '@playwright/test'

test('complete document analysis workflow', async ({ page }) => {
  // Login
  await page.goto('/login')
  await page.fill('[data-testid=username]', 'test@example.com')
  await page.fill('[data-testid=password]', 'testpass')
  await page.click('[data-testid=login-button]')

  // Upload document
  await page.goto('/documents')
  const fileChooser = await page.waitForEvent('filechooser')
  await page.click('[data-testid=upload-button]')
  await fileChooser.setFiles('tests/fixtures/sample_research_paper.pdf')

  // Wait for upload to complete
  await page.waitForSelector('[data-testid=upload-success]')

  // Query document with RAG
  await page.click('[data-testid=query-document-button]')
  await page.fill('[data-testid=query-input]', 'What are the main findings?')
  await page.click('[data-testid=submit-query-button]')

  // Verify response
  await page.waitForSelector('[data-testid=rag-response]')
  const response = await page.textContent('[data-testid=rag-response]')
  expect(response).toContain('findings')

  // Extract citations
  await page.click('[data-testid=extract-citations-button]')
  await page.waitForSelector('[data-testid=citations-list]')

  const citationCount = await page.locator('[data-testid=citation-item]').count()
  expect(citationCount).toBeGreaterThan(0)
})
```

### Test Configuration & Execution

#### Pytest Configuration (`pytest.ini`)
```ini
[tool:pytest]
minversion = 7.0
addopts =
    -v
    --strict-markers
    --strict-config
    --tb=short
    --disable-warnings
    --cov=src
    --cov=backend
    --cov-report=html:htmlcov
    --cov-report=term-missing
    --cov-fail-under=85
testpaths = tests
markers =
    unit: Unit tests
    integration: Integration tests
    security: Security tests
    performance: Performance tests
    slow: Slow running tests
    api: API tests
    frontend: Frontend tests
```

#### Test Execution Scripts
```python
# scripts/test_runner.py - Optimized test execution
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time

class TestRunner:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent

    def run_quick_tests(self):
        """Run smoke tests for rapid feedback (3-7 seconds)."""
        print("🚀 Running quick smoke tests...")
        start_time = time.time()

        cmd = [
            sys.executable, "-m", "pytest",
            "-m", "unit and not slow",
            "-x", "--tb=short", "--no-cov",
            "-q", "--disable-warnings",
            f"--rootdir={self.project_root}"
        ]

        result = subprocess.run(cmd, cwd=self.project_root)
        elapsed = time.time() - start_time
        print(f"✅ Quick tests completed in {elapsed:.2f}s")
        return result.returncode == 0

    def run_unit_tests(self):
        """Run comprehensive unit test suite."""
        print("🔬 Running unit tests...")
        cmd = [
            sys.executable, "-m", "pytest",
            "-m", "unit",
            "--cov=src", "--cov=backend",
            f"--rootdir={self.project_root}"
        ]
        result = subprocess.run(cmd, cwd=self.project_root)
        return result.returncode == 0

    def run_integration_tests(self):
        """Run integration tests with database."""
        print("🔗 Running integration tests...")
        cmd = [
            sys.executable, "-m", "pytest",
            "-m", "integration",
            "--tb=short",
            f"--rootdir={self.project_root}"
        ]
        result = subprocess.run(cmd, cwd=self.project_root)
        return result.returncode == 0

    def run_security_tests(self):
        """Run security-focused tests."""
        print("🔒 Running security tests...")
        cmd = [
            sys.executable, "-m", "pytest",
            "-m", "security",
            "tests/security/",
            f"--rootdir={self.project_root}"
        ]
        result = subprocess.run(cmd, cwd=self.project_root)
        return result.returncode == 0

    def run_performance_tests(self):
        """Run performance benchmarks."""
        print("⚡ Running performance tests...")
        cmd = [
            sys.executable, "-m", "pytest",
            "-m", "performance",
            "--tb=short",
            f"--rootdir={self.project_root}"
        ]
        result = subprocess.run(cmd, cwd=self.project_root)
        return result.returncode == 0

if __name__ == "__main__":
    runner = TestRunner()

    if "--quick" in sys.argv:
        runner.run_quick_tests()
    elif "--unit" in sys.argv:
        runner.run_unit_tests()
    elif "--integration" in sys.argv:
        runner.run_integration_tests()
    elif "--security" in sys.argv:
        runner.run_security_tests()
    elif "--performance" in sys.argv:
        runner.run_performance_tests()
    else:
        print("Usage: python scripts/test_runner.py [--quick|--unit|--integration|--security|--performance]")
```

### Mock and Fixture Strategies

#### Database Fixtures
```python
# tests/conftest.py - Shared test fixtures
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base
from src.database.connection import DatabaseConnection

@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield DatabaseConnection.from_session(session)

    session.close()

@pytest.fixture
def sample_documents(test_db):
    """Create sample documents for testing."""
    documents = [
        DocumentModel(
            title="AI Research Paper",
            file_path="ai_research.pdf",
            content_hash="abc123",
            mime_type="application/pdf"
        ),
        DocumentModel(
            title="Machine Learning Survey",
            file_path="ml_survey.pdf",
            content_hash="def456",
            mime_type="application/pdf"
        )
    ]

    for doc in documents:
        test_db.session.add(doc)
    test_db.session.commit()

    return documents
```

#### API Mocking
```python
# Mock external API calls
@pytest.fixture
def mock_gemini_api():
    """Mock Google Gemini API responses."""
    with patch('src.services.enhanced_rag_service.gemini') as mock:
        mock.generate_content.return_value.text = "Mocked AI response"
        yield mock

@pytest.fixture
def mock_file_operations():
    """Mock file system operations."""
    with patch('pathlib.Path.exists') as mock_exists, \
         patch('pathlib.Path.unlink') as mock_unlink, \
         patch('shutil.copy2') as mock_copy:

        mock_exists.return_value = True
        yield {
            'exists': mock_exists,
            'unlink': mock_unlink,
            'copy': mock_copy
        }
```

---

## 📊 Performance Optimization

### Performance Monitoring

#### Application Performance Monitoring (APM)
```python
# backend/services/metrics_service.py
import time
import psutil
from typing import Dict, Any
from dataclasses import dataclass, asdict

@dataclass
class PerformanceMetrics:
    """System performance metrics."""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    active_connections: int
    response_time_avg: float
    request_rate: float
    error_rate: float

class MetricsCollector:
    def __init__(self):
        self.request_times = []
        self.request_count = 0
        self.error_count = 0
        self.start_time = time.time()

    def record_request(self, response_time: float, is_error: bool = False):
        """Record request metrics."""
        self.request_times.append(response_time)
        self.request_count += 1
        if is_error:
            self.error_count += 1

        # Keep only last 1000 requests
        if len(self.request_times) > 1000:
            self.request_times = self.request_times[-1000:]

    def get_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        uptime = time.time() - self.start_time

        return PerformanceMetrics(
            cpu_usage=psutil.cpu_percent(),
            memory_usage=psutil.virtual_memory().percent,
            disk_usage=psutil.disk_usage('/').percent,
            active_connections=len(psutil.net_connections()),
            response_time_avg=sum(self.request_times) / len(self.request_times) if self.request_times else 0,
            request_rate=self.request_count / uptime if uptime > 0 else 0,
            error_rate=self.error_count / self.request_count if self.request_count > 0 else 0
        )

# Middleware for automatic metrics collection
from fastapi import Request, Response
import time

async def performance_middleware(request: Request, call_next):
    """Middleware to collect performance metrics."""
    start_time = time.time()

    try:
        response = await call_next(request)
        processing_time = time.time() - start_time

        # Record successful request
        metrics_collector.record_request(processing_time, is_error=False)

        # Add performance headers
        response.headers["X-Processing-Time"] = str(processing_time)
        return response

    except Exception as e:
        processing_time = time.time() - start_time
        metrics_collector.record_request(processing_time, is_error=True)
        raise
```

#### Database Performance Optimization
```python
# Query optimization strategies
from sqlalchemy import text
from sqlalchemy.orm import joinedload, selectinload

class OptimizedDocumentRepository:
    def __init__(self, db_session):
        self.session = db_session

    def get_documents_with_citations(self, limit: int = 50):
        """Optimized query with eager loading."""
        return self.session.query(DocumentModel)\
            .options(
                selectinload(DocumentModel.citations),  # Avoid N+1 queries
                joinedload(DocumentModel.metadata)      # Single JOIN
            )\
            .limit(limit)\
            .all()

    def search_documents_optimized(self, query: str):
        """Full-text search with database optimization."""
        # Use database-specific full-text search
        sql = text("""
            SELECT d.*, ts_rank(to_tsvector('english', d.title || ' ' || d.content),
                               plainto_tsquery('english', :query)) as rank
            FROM documents d
            WHERE to_tsvector('english', d.title || ' ' || d.content) @@
                  plainto_tsquery('english', :query)
            ORDER BY rank DESC
            LIMIT 50
        """)
        return self.session.execute(sql, {"query": query}).fetchall()

    def get_document_statistics_cached(self):
        """Cached statistics query."""
        cache_key = "document_statistics"

        # Try cache first
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        # Calculate statistics
        stats = self.session.execute(text("""
            SELECT
                COUNT(*) as total_documents,
                SUM(file_size) as total_size,
                COUNT(DISTINCT mime_type) as file_types,
                AVG(CASE WHEN created_at > NOW() - INTERVAL '30 days' THEN 1 ELSE 0 END) as recent_activity
            FROM documents
        """)).fetchone()

        result = dict(stats)

        # Cache for 1 hour
        redis_client.setex(cache_key, 3600, json.dumps(result))
        return result
```

#### Caching Strategies
```python
# Multi-layer caching implementation
import redis
from functools import wraps
import hashlib
import json
from typing import Any, Optional

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis_client = redis.from_url(redis_url)
        self.local_cache = {}  # In-memory cache for frequent data

    def cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate consistent cache key."""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.sha256(key_data.encode()).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """Get from multi-layer cache."""
        # Try local cache first (fastest)
        if key in self.local_cache:
            return self.local_cache[key]

        # Try Redis cache
        cached = self.redis_client.get(key)
        if cached:
            data = json.loads(cached)
            # Store in local cache for next time
            self.local_cache[key] = data
            return data

        return None

    def set(self, key: str, value: Any, ttl: int = 3600):
        """Set in multi-layer cache."""
        serialized = json.dumps(value)

        # Store in Redis with TTL
        self.redis_client.setex(key, ttl, serialized)

        # Store in local cache
        self.local_cache[key] = value

        # Limit local cache size
        if len(self.local_cache) > 1000:
            # Remove oldest entries
            for old_key in list(self.local_cache.keys())[:100]:
                del self.local_cache[old_key]

# Cache decorator
def cache_result(prefix: str, ttl: int = 3600):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = cache_manager.cache_key(prefix, *args, **kwargs)

            # Try to get from cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            return result

        return wrapper
    return decorator

# Usage example
@cache_result("rag_query", ttl=1800)  # Cache for 30 minutes
def query_document_cached(document_id: int, query: str) -> dict:
    """Cached RAG query execution."""
    return enhanced_rag_service.query_document(document_id, query)
```

### Performance Benchmarking

#### Benchmark Test Suite
```python
# scripts/benchmark_suite.py
import time
import statistics
from typing import List, Dict, Callable
from concurrent.futures import ThreadPoolExecutor
import asyncio

class PerformanceBenchmark:
    def __init__(self):
        self.results = {}

    def benchmark_function(self, name: str, func: Callable, iterations: int = 100):
        """Benchmark a function's execution time."""
        times = []

        for _ in range(iterations):
            start = time.perf_counter()
            try:
                func()
                end = time.perf_counter()
                times.append(end - start)
            except Exception as e:
                print(f"Error in {name}: {e}")
                continue

        if times:
            self.results[name] = {
                'mean': statistics.mean(times),
                'median': statistics.median(times),
                'min': min(times),
                'max': max(times),
                'std_dev': statistics.stdev(times) if len(times) > 1 else 0,
                'iterations': len(times)
            }

    def benchmark_concurrent(self, name: str, func: Callable, workers: int = 10, tasks_per_worker: int = 10):
        """Benchmark concurrent execution."""
        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = []
            for _ in range(workers * tasks_per_worker):
                future = executor.submit(func)
                futures.append(future)

            # Wait for all to complete
            completed = 0
            errors = 0
            for future in futures:
                try:
                    future.result()
                    completed += 1
                except Exception:
                    errors += 1

        total_time = time.perf_counter() - start_time

        self.results[name] = {
            'total_time': total_time,
            'completed': completed,
            'errors': errors,
            'throughput': completed / total_time if total_time > 0 else 0,
            'workers': workers
        }

    def print_results(self):
        """Print benchmark results in a formatted table."""
        print("\n" + "="*80)
        print("PERFORMANCE BENCHMARK RESULTS")
        print("="*80)

        for name, result in self.results.items():
            print(f"\n{name}:")
            if 'mean' in result:
                print(f"  Mean time:     {result['mean']*1000:.2f}ms")
                print(f"  Median time:   {result['median']*1000:.2f}ms")
                print(f"  Min time:      {result['min']*1000:.2f}ms")
                print(f"  Max time:      {result['max']*1000:.2f}ms")
                print(f"  Std deviation: {result['std_dev']*1000:.2f}ms")
                print(f"  Iterations:    {result['iterations']}")
            elif 'throughput' in result:
                print(f"  Total time:    {result['total_time']:.2f}s")
                print(f"  Completed:     {result['completed']}")
                print(f"  Errors:        {result['errors']}")
                print(f"  Throughput:    {result['throughput']:.2f} ops/sec")
                print(f"  Workers:       {result['workers']}")

# Example benchmarks
def run_document_benchmarks():
    """Run document processing benchmarks."""
    benchmark = PerformanceBenchmark()

    # Benchmark document upload
    def upload_test_document():
        # Mock document upload
        time.sleep(0.1)  # Simulate processing time
        return True

    benchmark.benchmark_function("Document Upload", upload_test_document, iterations=50)

    # Benchmark RAG queries
    def rag_query_test():
        # Mock RAG query
        time.sleep(0.2)  # Simulate query processing
        return "Mock response"

    benchmark.benchmark_function("RAG Query", rag_query_test, iterations=20)

    # Benchmark concurrent operations
    def concurrent_query_test():
        time.sleep(0.1)  # Simulate work
        return True

    benchmark.benchmark_concurrent("Concurrent Queries", concurrent_query_test, workers=5, tasks_per_worker=10)

    benchmark.print_results()

if __name__ == "__main__":
    run_document_benchmarks()
```

---

## 🔒 Security Implementation

### Authentication & Authorization

#### JWT Implementation
```python
# backend/auth/jwt_manager.py
import jwt
from datetime import datetime, timedelta
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from typing import Dict, Any, Optional
import uuid

class JWTManager:
    def __init__(self, private_key_path: str, public_key_path: str):
        """Initialize JWT manager with RSA keys."""
        self.private_key = self._load_private_key(private_key_path)
        self.public_key = self._load_public_key(public_key_path)
        self.algorithm = "RS256"

    def _load_private_key(self, path: str):
        """Load RSA private key."""
        with open(path, 'rb') as key_file:
            return serialization.load_pem_private_key(
                key_file.read(),
                password=None  # Use environment variable for password in production
            )

    def _load_public_key(self, path: str):
        """Load RSA public key."""
        with open(path, 'rb') as key_file:
            return serialization.load_pem_public_key(key_file.read())

    def create_access_token(self, user_id: int, permissions: List[str]) -> str:
        """Create access token with minimal payload."""
        now = datetime.utcnow()
        payload = {
            "sub": str(user_id),           # Subject (user ID)
            "permissions": permissions,     # User permissions
            "type": "access",              # Token type
            "exp": now + timedelta(minutes=15),  # Short expiration
            "iat": now,                    # Issued at
            "jti": str(uuid.uuid4())       # JWT ID for revocation
        }

        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: int) -> str:
        """Create refresh token with longer expiration."""
        now = datetime.utcnow()
        payload = {
            "sub": str(user_id),
            "type": "refresh",
            "exp": now + timedelta(days=7),
            "iat": now,
            "jti": str(uuid.uuid4())
        }

        return jwt.encode(payload, self.private_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify and decode token."""
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=[self.algorithm],
                options={"require": ["sub", "exp", "iat"]}
            )

            # Additional validation
            if payload.get("type") not in ["access", "refresh"]:
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def is_token_revoked(self, jti: str) -> bool:
        """Check if token is revoked (implement with Redis/database)."""
        # Implementation depends on your revocation strategy
        # Could use Redis set, database table, etc.
        return redis_client.sismember("revoked_tokens", jti)

    def revoke_token(self, jti: str, expiration: datetime):
        """Revoke token until its natural expiration."""
        # Store revoked token ID with TTL matching token expiration
        ttl = int((expiration - datetime.utcnow()).total_seconds())
        if ttl > 0:
            redis_client.setex(f"revoked_token:{jti}", ttl, "true")
```

#### Role-Based Access Control (RBAC)
```python
# backend/auth/rbac.py
from enum import Enum
from typing import List, Set
from functools import wraps
from fastapi import HTTPException, Depends

class Permission(Enum):
    """System permissions."""
    READ_DOCUMENTS = "documents:read"
    WRITE_DOCUMENTS = "documents:write"
    DELETE_DOCUMENTS = "documents:delete"
    MANAGE_USERS = "users:manage"
    VIEW_ANALYTICS = "analytics:view"
    SYSTEM_ADMIN = "system:admin"

class Role(Enum):
    """User roles with associated permissions."""
    GUEST = "guest"
    USER = "user"
    RESEARCHER = "researcher"
    ADMIN = "admin"

# Role-permission mapping
ROLE_PERMISSIONS = {
    Role.GUEST: {Permission.READ_DOCUMENTS},
    Role.USER: {
        Permission.READ_DOCUMENTS,
        Permission.WRITE_DOCUMENTS
    },
    Role.RESEARCHER: {
        Permission.READ_DOCUMENTS,
        Permission.WRITE_DOCUMENTS,
        Permission.VIEW_ANALYTICS
    },
    Role.ADMIN: {
        Permission.READ_DOCUMENTS,
        Permission.WRITE_DOCUMENTS,
        Permission.DELETE_DOCUMENTS,
        Permission.MANAGE_USERS,
        Permission.VIEW_ANALYTICS,
        Permission.SYSTEM_ADMIN
    }
}

class RBACManager:
    def __init__(self):
        self.role_permissions = ROLE_PERMISSIONS

    def get_user_permissions(self, roles: List[Role]) -> Set[Permission]:
        """Get combined permissions for user roles."""
        permissions = set()
        for role in roles:
            permissions.update(self.role_permissions.get(role, set()))
        return permissions

    def has_permission(self, user_roles: List[Role], required_permission: Permission) -> bool:
        """Check if user has required permission."""
        user_permissions = self.get_user_permissions(user_roles)
        return required_permission in user_permissions

# FastAPI dependency for permission checking
def require_permission(permission: Permission):
    """FastAPI dependency to require specific permission."""
    def permission_checker(current_user: dict = Depends(get_current_user)):
        user_roles = [Role(role) for role in current_user.get("roles", [])]

        if not rbac_manager.has_permission(user_roles, permission):
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {permission.value}"
            )

        return current_user

    return permission_checker

# Usage in API endpoints
@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    current_user: dict = Depends(require_permission(Permission.DELETE_DOCUMENTS))
):
    """Delete document - requires delete permission."""
    # Implementation here
    pass
```

### Input Validation & Sanitization

#### Comprehensive Input Validation
```python
# backend/api/validation.py
from pydantic import BaseModel, validator, Field
from typing import Optional, List
import re
import html
from pathlib import Path

class SecureDocumentUpload(BaseModel):
    """Secure document upload validation."""
    title: Optional[str] = Field(None, max_length=200)
    tags: List[str] = Field(default_factory=list, max_items=10)
    extract_metadata: bool = True
    check_duplicates: bool = True

    @validator('title')
    def validate_title(cls, v):
        if v is not None:
            # Sanitize HTML and limit length
            sanitized = html.escape(v.strip())
            if not sanitized:
                raise ValueError("Title cannot be empty")

            # Check for suspicious patterns
            dangerous_patterns = [
                r'<script.*?</script>',
                r'javascript:',
                r'vbscript:',
                r'on\w+\s*='
            ]

            for pattern in dangerous_patterns:
                if re.search(pattern, sanitized, re.IGNORECASE):
                    raise ValueError("Title contains potentially dangerous content")

            return sanitized
        return v

    @validator('tags')
    def validate_tags(cls, v):
        if not v:
            return []

        sanitized_tags = []
        for tag in v:
            if not isinstance(tag, str):
                continue

            # Clean and validate tag
            clean_tag = re.sub(r'[^a-zA-Z0-9\-_\s]', '', tag.strip())
            if len(clean_tag) > 50:
                raise ValueError(f"Tag too long: {clean_tag[:20]}...")

            if clean_tag and clean_tag not in sanitized_tags:
                sanitized_tags.append(clean_tag)

        return sanitized_tags[:10]  # Limit to 10 tags

class SecureFileValidator:
    """Comprehensive file validation."""

    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'text/markdown'
    }

    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.scr', '.vbs', '.js', '.jar',
        '.com', '.pif', '.msi', '.dll', '.sh'
    }

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

    @classmethod
    def validate_file(cls, file: UploadFile) -> dict:
        """Comprehensive file validation."""
        errors = []
        warnings = []

        # Check file size
        if hasattr(file.file, 'seek'):
            file.file.seek(0, 2)  # Seek to end
            size = file.file.tell()
            file.file.seek(0)  # Reset to beginning

            if size > cls.MAX_FILE_SIZE:
                errors.append(f"File too large: {size} bytes (max: {cls.MAX_FILE_SIZE})")

        # Check MIME type
        if file.content_type not in cls.ALLOWED_MIME_TYPES:
            errors.append(f"File type not allowed: {file.content_type}")

        # Check file extension
        file_path = Path(file.filename or "")
        extension = file_path.suffix.lower()

        if extension in cls.DANGEROUS_EXTENSIONS:
            errors.append(f"Dangerous file extension: {extension}")

        # Check filename for suspicious patterns
        if file.filename:
            # Sanitize filename
            safe_filename = re.sub(r'[^a-zA-Z0-9.\-_]', '_', file.filename)
            if safe_filename != file.filename:
                warnings.append("Filename contains special characters - will be sanitized")

            # Check for double extensions
            if file.filename.count('.') > 1:
                warnings.append("Multiple extensions detected")

        # Basic content validation (magic number check)
        if file.content_type == 'application/pdf':
            header = file.file.read(5)
            file.file.seek(0)
            if not header.startswith(b'%PDF-'):
                errors.append("Invalid PDF file - header mismatch")

        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'safe_filename': safe_filename if file.filename else None
        }
```

### XSS Protection Implementation

#### Frontend Security Hooks
```typescript
// frontend/src/hooks/useSecurity.ts
import { useMemo, useCallback, useState, useEffect } from 'react'
import DOMPurify from 'dompurify'

interface XSSDetectionResult {
  isDetected: boolean
  patterns: string[]
  severity: 'low' | 'medium' | 'high' | 'critical'
}

interface SecurityConfig {
  allowMarkdown?: boolean
  allowImages?: boolean
  allowLinks?: boolean
  allowTables?: boolean
  stripAllHTML?: boolean
}

export function useXSSDetection(content: string): XSSDetectionResult {
  return useMemo(() => {
    const dangerousPatterns = [
      { pattern: /<script[^>]*>/gi, name: 'Script Tags', severity: 'critical' },
      { pattern: /javascript:/gi, name: 'JavaScript URLs', severity: 'critical' },
      { pattern: /vbscript:/gi, name: 'VBScript URLs', severity: 'critical' },
      { pattern: /on\w+\s*=/gi, name: 'Event Handlers', severity: 'high' },
      { pattern: /<iframe[^>]*>/gi, name: 'IFrame Tags', severity: 'medium' },
      { pattern: /expression\s*\(/gi, name: 'CSS Expression', severity: 'high' }
    ] as const

    const detectedPatterns: string[] = []
    let highestSeverity: 'low' | 'medium' | 'high' | 'critical' = 'low'

    // Check for HTML entity encoded patterns
    const decodedContent = content
      .replace(/&#(\d+);/g, (_, dec) => String.fromCharCode(parseInt(dec, 10)))
      .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
      .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')

    dangerousPatterns.forEach(({ pattern, name, severity }) => {
      if (pattern.test(content) || pattern.test(decodedContent)) {
        detectedPatterns.push(name)

        const severityLevels = { low: 1, medium: 2, high: 3, critical: 4 }
        if (severityLevels[severity] > severityLevels[highestSeverity]) {
          highestSeverity = severity
        }
      }
    })

    return {
      isDetected: detectedPatterns.length > 0,
      patterns: detectedPatterns,
      severity: highestSeverity
    }
  }, [content])
}

export function useSafeContent(
  content: string,
  config: SecurityConfig = {}
) {
  const xssDetection = useXSSDetection(content)

  const sanitizedContent = useMemo(() => {
    if (config.stripAllHTML) {
      return content.replace(/<[^>]*>/g, '')
    }

    const dompurifyConfig: any = {
      ALLOWED_TAGS: ['b', 'i', 'u', 'em', 'strong', 'br', 'p'],
      ALLOWED_ATTR: ['class'],
      KEEP_CONTENT: true,
      ALLOW_DATA_ATTR: false
    }

    if (config.allowLinks) {
      dompurifyConfig.ALLOWED_TAGS.push('a')
      dompurifyConfig.ALLOWED_ATTR.push('href', 'target', 'rel')
    }

    if (config.allowImages) {
      dompurifyConfig.ALLOWED_TAGS.push('img')
      dompurifyConfig.ALLOWED_ATTR.push('src', 'alt', 'width', 'height')
    }

    return DOMPurify.sanitize(content, dompurifyConfig)
  }, [content, config])

  return {
    sanitizedContent: xssDetection.isDetected ? content.replace(/<[^>]*>/g, '') : sanitizedContent,
    hasXSSRisk: xssDetection.isDetected,
    xssInfo: xssDetection
  }
}

// Usage in components
export function SafeContent({ content, allowMarkdown = false }: { content: string, allowMarkdown?: boolean }) {
  const { sanitizedContent, hasXSSRisk, xssInfo } = useSafeContent(content, {
    allowMarkdown,
    allowLinks: allowMarkdown,
    allowImages: false
  })

  if (hasXSSRisk) {
    return (
      <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
        <strong>⚠️ Security Warning:</strong> Potentially unsafe content detected
        <details className="mt-2">
          <summary>Details</summary>
          <ul>
            {xssInfo.patterns.map(pattern => (
              <li key={pattern}>• {pattern}</li>
            ))}
          </ul>
          <p>Severity: <span className="font-bold">{xssInfo.severity}</span></p>
        </details>
      </div>
    )
  }

  return (
    <div
      dangerouslySetInnerHTML={{ __html: sanitizedContent }}
      className="safe-content"
    />
  )
}
```

---

This comprehensive developer guide provides the essential knowledge and tools needed to effectively develop and contribute to the AI Enhanced PDF Scholar platform. The guide covers everything from environment setup to advanced security implementation, ensuring developers can work efficiently and securely.

Would you like me to continue with the remaining sections (API Development, Frontend Development, Database Management, Deployment Guide, and Debugging & Troubleshooting)?