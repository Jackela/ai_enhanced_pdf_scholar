# AI-Enhanced PDF Scholar

An intelligent document library platform with persistent RAG database and advanced duplicate detection for academic literature management.

## 📖 Project Goal & Motivation

This project aims to create an intelligent platform that streamlines the laborious process of academic literature review. It was conceived to eliminate the constant context-switching and manual copy-pasting required when analyzing academic papers with AI, providing a unified and efficient research environment.

## ✨ Key Features

*   **📚 Document Library Management**: Complete document organization with SQLite database persistence
*   **🔍 Intelligent Duplicate Detection**: File-level and content-level duplicate detection to prevent reprocessing
*   **💾 Persistent RAG Database**: Vector indexes are stored and reused, eliminating the need to reprocess identical content
*   **🏷️ Smart Import System**: Automatic metadata extraction, hash-based deduplication, and integrity verification
*   **📊 Comprehensive Statistics**: Document library analytics, health monitoring, and cleanup tools
*   **🧪 Production-Grade Architecture**: Repository pattern, service layers, and comprehensive test coverage

## 🏗️ Architecture & Technical Highlights

*   **Layered Architecture**: Clean separation with Database → Repository → Service → UI layers following SOLID principles
*   **Thread-Safe Database**: SQLite with connection pooling, transaction management, and migration system
*   **Repository Pattern**: Generic data access layer with specialized repositories for documents and vector indexes
*   **Content Hashing**: MD5-based file and content hashing for intelligent duplicate detection
*   **Decoupled System**: Serves both **PyQt6** desktop and **FastAPI** web interfaces from unified backend
*   **Retrieval-Augmented Generation (RAG)**: **LlamaIndex**-powered RAG with persistent vector storage
*   **Asynchronous Processing**: Non-blocking `QThreads` for responsive user experience
*   **Comprehensive Testing**: Unit tests, integration tests, and performance benchmarks

## 🛠️ Tech Stack

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![PyQt6](https://img.io/badge/PyQt6-41CD52?style=for-the-badge&logo=qt)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)
![LlamaIndex](https://img.shields.io/badge/LlamaIndex-6B45BC?style=for-the-badge)
![PyMuPDF](https://img.shields.io/badge/PyMuPDF-FF6B6B?style=for-the-badge)
![Pytest](https://img.shields.io/badge/pytest-0A9B71?style=for-the-badge&logo=pytest)

## 🚀 Installation & Usage

### Prerequisites

- Python 3.11 or higher
- Git
- Miniconda/Anaconda (recommended)

### 1. Clone the Repository

```bash
git clone https://github.com/Jackela/ai_enhanced_pdf_scholar.git
cd ai_enhanced_pdf_scholar
```

### 2. Create Conda Environment (Recommended)

```bash
# Create isolated environment
conda create -n pdf_scholar python=3.11 -y
conda activate pdf_scholar

# Install dependencies
pip install -r requirements.txt
```

**Alternative: Virtual Environment**

*   **On Windows:**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    ```
*   **On macOS/Linux:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

### 3. Database Setup

The application automatically creates and migrates the SQLite database on first run. No manual setup required!

```bash
# Test database functionality
python test_database_only.py
python test_library_service.py
```

### 4. Set Up API Keys

Refer to `API_KEY_SETUP.md` for instructions on configuring your API keys.

### 5. Run the Application

*   **PyQt6 Desktop App:**
    ```bash
    python main.py
    ```
*   **FastAPI Web App:**
    ```bash
    uvicorn web_main:app --reload
    ```

## 📚 Document Library Features

### Smart Document Import

```python
from src.services.document_library_service import DocumentLibraryService
from src.database.connection import DatabaseConnection

# Initialize service
db = DatabaseConnection("library.db")
library = DocumentLibraryService(db)

# Import document with duplicate detection
doc = library.import_document(
    "path/to/paper.pdf",
    title="Research Paper",
    check_duplicates=True
)
```

### Advanced Search & Organization

```python
# Search documents
results = library.get_documents(search_query="machine learning")

# Get recent documents
recent = library.get_recent_documents(limit=10)

# Find duplicates
duplicates = library.find_duplicate_documents()

# Library statistics
stats = library.get_library_statistics()
```

### Database Features

- **Thread-Safe Operations**: Concurrent access with proper locking
- **Transaction Support**: ACID compliance with automatic rollback
- **Migration System**: Schema versioning and safe upgrades
- **Integrity Verification**: Document and index health checking
- **Cleanup Tools**: Automatic orphaned data removal

## 🧪 Testing

Comprehensive test suite with optimized performance and coverage:

```bash
# Run all tests (optimized)
pytest tests/ -v                  # All tests with parallel execution
pytest tests/ -m unit            # Unit tests only
pytest tests/ -m integration     # Integration tests only
pytest tests/ -m performance     # Performance benchmarks

# Run legacy tests
python test_database_only.py      # Core database functionality
python test_library_service.py    # Repository and service layers
python test_comprehensive.py      # Edge cases and scenarios

# Performance benchmarking
python scripts/benchmark_tests.py # Test performance validation
```

**Test Coverage:**
- ✅ Database connections and migrations
- ✅ Document and vector index repositories  
- ✅ Service layer business logic
- ✅ Duplicate detection algorithms
- ✅ Concurrent operations safety
- ✅ Error handling and edge cases
- ✅ Optimized test performance

**Performance Optimizations:**
- ⚡ Parallel test execution with `pytest-xdist`
- 🔄 Shared database fixtures reducing setup overhead
- 📊 Automatic performance monitoring
- 🚀 CI/CD pipeline optimization

## 🗄️ Database Schema

The system uses a well-designed SQLite schema with proper relationships and indexes:

```sql
-- Core document table
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    file_path TEXT,
    file_hash TEXT UNIQUE NOT NULL,
    file_size INTEGER NOT NULL,
    page_count INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_accessed TEXT,
    metadata TEXT DEFAULT '{}'
);

-- Vector indexes for RAG
CREATE TABLE vector_indexes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    index_path TEXT NOT NULL,
    index_hash TEXT UNIQUE NOT NULL,
    chunk_count INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Document tagging system
CREATE TABLE tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    color TEXT
);

CREATE TABLE document_tags (
    document_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (document_id, tag_id),
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);
```


## 🔧 Development Status

**Current Phase: Database Infrastructure Complete**

✅ **Phase 1 - Database Layer (COMPLETE)**
- Database connection management
- Schema migrations
- Data models and validation

✅ **Phase 2 - Repository & Service Layers (COMPLETE)**
- Repository pattern implementation
- Business logic services
- Duplicate detection system

🚧 **Phase 3 - RAG Integration (IN PROGRESS)**
- Vector index management
- LlamaIndex integration
- Query processing

📋 **Phase 4 - UI Enhancement (PLANNED)**
- Document library interface
- Improved PDF viewer
- Advanced search capabilities

## 📄 License

This project is licensed under the MIT License.

---

**MIT License**

Copyright (c) 2024 Weixuan Kong

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.