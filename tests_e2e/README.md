# End-to-End Testing Documentation

## 📋 Overview

This directory contains comprehensive end-to-end (E2E) tests for the AI Enhanced PDF Scholar application. The tests cover complete user workflows, from document upload to RAG querying, including security, performance, and cross-browser compatibility testing.

## 🏗️ Test Architecture

```
tests_e2e/
├── fixtures/                 # Reusable test fixtures
│   ├── __init__.py
│   ├── browser_fixtures.py   # Browser setup and utilities
│   ├── data_fixtures.py      # Test data generation
│   ├── api_fixtures.py       # API client fixtures
│   └── database_fixtures.py  # Database setup and seeding
├── utils/                    # Test utilities
│   └── test_helpers.py       # Common helper functions
├── test_complete_document_workflow.py  # Document lifecycle tests
├── test_library_management.py          # Library feature tests
├── test_rag_query_workflow.py          # RAG functionality tests
├── test_security_workflows.py          # Security testing
├── test_performance_and_load.py        # Performance tests
├── conftest.py              # Pytest configuration
├── pytest.ini               # Pytest settings
├── run_e2e_tests.py        # Test runner script
└── README.md               # This file
```

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements-test.txt
pip install playwright pytest-playwright

# Install browsers
playwright install chromium firefox webkit
playwright install-deps
```

### Running Tests

```bash
# Run all E2E tests
python tests_e2e/run_e2e_tests.py all

# Run specific test suite
python tests_e2e/run_e2e_tests.py smoke
python tests_e2e/run_e2e_tests.py security
python tests_e2e/run_e2e_tests.py performance

# Run tests in parallel
python tests_e2e/run_e2e_tests.py all --parallel

# Run with visible browser
python tests_e2e/run_e2e_tests.py all --headed

# Run specific test file
pytest tests_e2e/test_complete_document_workflow.py -v

# Run tests with specific marker
pytest tests_e2e -m "critical and not slow"
```

## 📦 Test Suites

### Core Test Suites

| Suite | Description | Markers | Duration |
|-------|-------------|---------|----------|
| **smoke** | Basic functionality tests | `smoke` | ~5 min |
| **critical** | Critical path tests | `critical` | ~10 min |
| **workflow** | Complete user workflows | `workflow` | ~15 min |
| **library** | Document library features | `library` | ~10 min |
| **rag** | RAG query functionality | `rag` | ~12 min |
| **security** | Security and vulnerability tests | `security` | ~20 min |
| **performance** | Performance and load tests | `performance` | ~25 min |
| **regression** | Regression test suite | `regression` | ~30 min |

### Test Categories

#### 1. Document Workflow Tests
- **Upload**: Single and batch document uploads
- **Processing**: Document processing and indexing
- **Citations**: Citation extraction and management
- **Download**: Document retrieval and export
- **Error Handling**: Recovery from processing failures

#### 2. Library Management Tests
- **Search**: Full-text and metadata search
- **Filtering**: Multi-criteria filtering
- **Sorting**: Various sorting options
- **Bulk Operations**: Select, delete, export
- **Pagination**: Large dataset handling
- **Preview**: Document preview and details

#### 3. RAG Query Tests
- **Simple Queries**: Basic Q&A functionality
- **Multi-turn**: Conversation context retention
- **Advanced Options**: Temperature, tokens, filters
- **Performance**: Query response times
- **Error Handling**: Invalid queries, timeouts
- **Source Attribution**: Citation verification

#### 4. Security Tests
- **XSS Prevention**: Cross-site scripting protection
- **SQL Injection**: Database query safety
- **Path Traversal**: File system security
- **Authentication**: Login, session management
- **Authorization**: Role-based access control
- **File Upload**: Malicious file prevention
- **CSRF Protection**: Request forgery prevention
- **Input Validation**: Comprehensive sanitization

#### 5. Performance Tests
- **Page Load**: Initial and cached load times
- **Concurrent Users**: Multi-user simulation
- **API Performance**: Endpoint response times
- **File Upload**: Large file handling
- **RAG Queries**: Complex query performance
- **Stress Testing**: Sustained load handling
- **Memory Leaks**: Long-running stability

## 🛠️ Test Fixtures

### Browser Fixtures
```python
# Basic page fixture
def test_example(page):
    page.goto("http://localhost:8000")

# Multi-browser testing
@pytest.mark.parametrize('browser_config', ['desktop_chrome', 'mobile_iphone'])
def test_responsive(browser_context):
    ...

# Page helper utilities
def test_with_helper(page, page_helper):
    page_helper.wait_for_text("Loading complete")
    metrics = page_helper.measure_performance()
```

### Data Fixtures
```python
# Test PDF files
def test_upload(test_pdf_files):
    upload_file(test_pdf_files["standard"])

# User data
def test_auth(test_user_data):
    login(test_user_data["admin"])

# Security payloads
def test_security(security_test_payloads):
    test_xss(security_test_payloads["xss"])
```

### API Fixtures
```python
# API client
def test_api(api_client):
    response = api_client.get("/api/documents")

# Authenticated client
def test_protected(authenticated_api_client):
    response = authenticated_api_client.post("/api/documents", json=data)
```

### Database Fixtures
```python
# Clean database
def test_with_db(test_database):
    test_database.seed_users(10)

# Pre-seeded database
def test_with_data(seeded_database):
    stats = seeded_database.get_statistics()
```

## 📊 Test Reporting

### HTML Reports
Reports are generated in `tests_e2e/reports/` directory:
- `report_<suite>_<timestamp>.html` - Detailed HTML report
- `junit_<timestamp>.xml` - JUnit XML for CI integration
- `summary_<timestamp>.json` - JSON summary

### Coverage Reports
Coverage reports are generated in `tests_e2e/coverage/`:
- `index.html` - HTML coverage report
- `coverage.xml` - XML for CI integration

### Visual Regression
Screenshots and diffs stored in:
- `tests_e2e/visual_baselines/` - Baseline images
- `tests_e2e/screenshots/` - Current captures
- `tests_e2e/videos/` - Test execution videos

## 🔧 Configuration

### pytest.ini Settings
```ini
# Parallel execution
-n auto  # Auto-detect CPU cores
-n 4     # Use 4 workers

# Timeout settings
timeout = 300  # 5 minutes default
timeout_method = thread

# Screenshot on failure
playwright_screenshot = only-on-failure

# Video recording
playwright_video = retain-on-failure
```

### Environment Variables
```bash
# Backend server
export BASE_URL=http://localhost:8000

# Browser settings
export PYTEST_BROWSER=chromium  # or firefox, webkit
export HEADED=false             # Show browser window

# Test data
export TEST_USER_EMAIL=test@example.com
export TEST_USER_PASSWORD=Test123!@#

# Performance thresholds
export MAX_PAGE_LOAD_TIME=3000  # milliseconds
export MAX_API_RESPONSE_TIME=1000
```

## 🔄 CI/CD Integration

### GitHub Actions
The workflow file `.github/workflows/e2e-tests.yml` runs:
- **On Push**: Smoke tests on main/develop
- **On PR**: Critical + Security tests
- **Nightly**: Full regression suite
- **Manual**: Configurable test suite

### Test Stages
1. **Quick Validation** (PR) - 10 min
   - Critical path tests
   - Basic security checks

2. **Standard Testing** (Push) - 20 min
   - Smoke tests
   - Core workflows
   - Cross-browser basics

3. **Comprehensive** (Nightly) - 60 min
   - All test suites
   - Performance benchmarks
   - Visual regression
   - Security scanning

## 🏃 Performance Benchmarks

### Target Metrics
| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| Page Load (cold) | < 1s | < 2s | < 3s |
| Page Load (warm) | < 0.5s | < 1s | < 1.5s |
| API Response | < 100ms | < 200ms | < 500ms |
| File Upload (10MB) | < 5s | < 10s | < 15s |
| RAG Query (simple) | < 1s | < 2s | < 3s |
| RAG Query (complex) | < 3s | < 5s | < 10s |

### Load Testing Targets
- **Concurrent Users**: Support 50+ simultaneous users
- **Requests/Second**: Handle 100+ RPS
- **Success Rate**: Maintain >99% under normal load
- **Response Time**: P95 < 1 second

## 🐛 Debugging

### Enable Debug Mode
```bash
# Verbose output
pytest tests_e2e -vvv

# Show print statements
pytest tests_e2e -s

# Stop on first failure
pytest tests_e2e -x

# Debug with pdb
pytest tests_e2e --pdb
```

### Playwright Inspector
```bash
# Launch with inspector
PWDEBUG=1 pytest tests_e2e/test_example.py

# Use page.pause() in tests
def test_debug(page):
    page.goto("/")
    page.pause()  # Opens inspector
```

### Trace Viewer
```bash
# Enable tracing
pytest tests_e2e --tracing

# View trace
playwright show-trace tests_e2e/traces/test_name.zip
```

## 📝 Writing New Tests

### Test Structure Template
```python
import pytest
from playwright.sync_api import Page, expect
from fixtures import *

class TestFeatureName:
    """Test suite for specific feature."""

    @pytest.mark.e2e
    @pytest.mark.smoke  # Add appropriate markers
    def test_feature_scenario(
        self,
        page: Page,
        page_helper,
        api_client,
        test_data
    ):
        """Test specific scenario."""
        # Arrange
        page.goto("/feature")

        # Act
        page.click('[data-testid="action-button"]')

        # Assert
        expect(page.locator('[data-testid="result"]')).to_be_visible()

        # Cleanup (if needed)
        api_client.delete("/api/resource/123")
```

### Best Practices
1. **Use data-testid**: Reliable element selection
2. **Wait intelligently**: Use expect() with timeout
3. **Clean up**: Remove test data after tests
4. **Isolate tests**: Each test should be independent
5. **Mock external**: Mock third-party services
6. **Document intent**: Clear test descriptions
7. **Performance aware**: Monitor test duration

## 🔍 Troubleshooting

### Common Issues

#### 1. Browser Installation
```bash
# Reinstall browsers
playwright install --force
playwright install-deps
```

#### 2. Port Already in Use
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9  # Linux/Mac
netstat -ano | findstr :8000   # Windows
```

#### 3. Timeout Issues
```python
# Increase timeout for slow operations
page.set_default_timeout(60000)  # 60 seconds

# Or per operation
page.click(selector, timeout=30000)
```

#### 4. Flaky Tests
```python
# Add retries for flaky tests
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_occasionally_fails():
    ...
```

## 📚 Additional Resources

- [Playwright Documentation](https://playwright.dev/python/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Test Best Practices](https://testautomationu.applitools.com/)
- [CI/CD with GitHub Actions](https://docs.github.com/en/actions)

## 🤝 Contributing

When adding new E2E tests:
1. Follow the existing test structure
2. Add appropriate markers
3. Update this documentation
4. Ensure tests pass locally
5. Check CI/CD pipeline passes
6. Add performance benchmarks if applicable

---

**Last Updated**: 2025-01-20
**Maintainer**: AI Enhanced PDF Scholar Team
**Version**: 2.0.0