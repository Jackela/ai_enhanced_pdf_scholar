# 🎓 AI Enhanced PDF Scholar
### Stop Reading, Start Understanding.

**AI Enhanced PDF Scholar is an intelligent platform that transforms your academic research workflow. Instead of drowning in a sea of PDFs, you can now have a conversation with your documents, uncover hidden connections, and focus on what truly matters: generating new insights.**

---

## The Problem: Information Overload is Slowing Down Research

University students, academics, and corporate researchers all face the same challenge: an ever-growing mountain of research papers. The traditional workflow is broken and inefficient:
- **Fragmented Tools:** Juggling PDF readers, note-takers, citation managers, and separate AI tools.
- **Manual Searching:** Endlessly scrolling and using `Ctrl+F` to find specific pieces of information.
- **Lost Context:** Losing track of where information came from, making citations a nightmare.

This manual, time-consuming process is a major bottleneck, leaving less time for critical thinking and analysis.

## The Solution: Your Unified, Intelligent Research Hub

AI Enhanced PDF Scholar brings the power of cutting-edge AI directly to your research library. We provide a single, secure platform to:

- **Centralize Your Knowledge:** Upload all your documents into one clean, searchable library.
- **Ask, Don't Search:** Interact with your papers using natural language. Get direct answers, summaries, and insights in seconds.
- **Discover Connections:** Automatically analyze citation networks to understand how research evolves.

Our mission is to help you move from tedious searching to accelerated understanding.

---

## Designed For...

- **University & College Students:** Perfect for writing literature reviews, essays, and dissertations.
- **Academic Researchers & Professors:** Ideal for staying current, preparing lectures, and guiding student research.
- **Corporate R&D Professionals:** A powerful tool for market research, competitive analysis, and internal knowledge management.

---

## Key Features & Benefits

| Feature | Your Benefit |
| :--- | :--- |
| 💬 **Chat with Your Documents** | Instantly get answers and summaries from your PDFs. Stop skimming and start learning. |
| 🔗 **Untangle Research Connections** | Automatically extract citations and visualize the network to see how ideas connect and identify key papers. |
| 🔒 **Secure & Private by Design** | Your research is yours alone. All documents are stored securely and are never used to train public models. |
| ⚡️ **Quick & Easy Setup** | Get started in minutes. A clean, intuitive interface means you spend your time on research, not on learning a new tool. |
| 📊 **Smart Document Library** | Organize, search, and manage your research documents with intelligent tagging and duplicate detection. |
| 🔄 **Real-time Collaboration** | WebSocket-based live updates for seamless multi-user experiences. |
| 📈 **Performance Monitoring** | Built-in metrics and health checks to ensure optimal system performance. |
| 🛡️ **Enterprise Security** | Role-based access control (RBAC), rate limiting, and comprehensive audit logging. |

---

## API Reference

The platform provides a comprehensive REST API with 80+ endpoints:

| Endpoint Group | Description | Status |
|---------------|-------------|--------|
| `/api/system/*` | Health checks, configuration, and system management | ✅ Implemented |
| `/api/documents/*` | Document upload, download, preview, and management | ✅ Implemented |
| `/api/library/*` | Library statistics, duplicates detection, and cleanup | ✅ Implemented |
| `/api/queries/*` | RAG query execution and history | ✅ Implemented |
| `/api/indexes/*` | Vector index management for AI search | ✅ Implemented |
| `/api/citations/*` | Citation extraction, search, and network analysis | ✅ Implemented |
| `/api/multi-document/*` | Multi-document collections and cross-document queries | ✅ Implemented |
| `/api/settings/*` | Application settings and API key management | ✅ Implemented |
| `/api/auth/*` | Authentication and user management | ✅ Implemented |
| `/ws/*` | WebSocket endpoints for real-time updates | ✅ Implemented |

**Full API Documentation:** See [API_ENDPOINTS.md](./API_ENDPOINTS.md) for complete endpoint reference.

---

## Product Demo

See AI Enhanced PDF Scholar in action!

*A picture is worth a thousand words. Here we would include high-quality screenshots or GIFs showcasing the core user flow.*

![Screenshot of the main dashboard showing an organized library of papers.](https://via.placeholder.com/800x450.png?text=Dashboard:+Your+Research+Library)
*Caption: Your entire research library, organized and ready for analysis.*

![GIF showing a user typing a question and the AI providing a direct answer with sources.](https://via.placeholder.com/800x450.png?text=GIF:+Chat+with+your+documents)
*Caption: Ask a question and get a direct answer, complete with citations from your documents.*

---

## How to Get Started

Ready to revolutionize your research process?

[**🚀 View Live Demo**](https://your-live-demo-url.com) &nbsp;&nbsp; | &nbsp;&nbsp; [**📖 Read the Docs**](./docs/README.md) &nbsp;&nbsp; | &nbsp;&nbsp; [**🛠️ Developer Quick Start**](#-developer-quick-start)

---

## Technical Stack

For those interested, AI Enhanced PDF Scholar is built with a modern, robust technology stack:
- **Backend:** Python 3.11+, FastAPI, LlamaIndex, Pydantic 2.x
- **Frontend:** React 18, TypeScript, Vite, TailwindCSS, Zustand
- **Database:** PostgreSQL (production) / SQLite (development)
- **Cache:** Redis (optional), in-memory LRU cache
- **AI/ML:** Google Gemini API, OpenAI, custom embeddings
- **DevOps:** Docker, Docker Compose, GitHub Actions

---

## 🛠️ Developer Quick Start

The codebase ships with a single `/api` surface (unified API design) and a comprehensive test harness. Developers can get started with the minimal workflow below.

### Prerequisites
- Python 3.11+, Node.js 18+, Git
- Google Gemini API Key (optional, for AI features)

### 1. Installation & Setup
```bash
# Clone, install deps
git clone https://github.com/Jackela/ai_enhanced_pdf_scholar.git
cd ai_enhanced_pdf_scholar
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..

# Configure API Key (optional)
export GOOGLE_API_KEY="your_gemini_api_key_here"
```

### Optional: Enable Smart Cache ML profile
Smart-cache ML optimizations stay in graceful-degradation mode unless the ML profile is installed:

```bash
# Option A: install the scaling requirements bundle
pip install -r requirements-scaling.txt

# Option B: install the poetry/setuptools extra
pip install ".[cache-ml]"

# Enable ML caching (default is true, set false to skip)
export CACHE_ML_OPTIMIZATIONS_ENABLED=true
```

### Optional: Tune preview/thumbnail settings
Document previews are enabled by default. Configure them via environment variables:

```bash
export PREVIEWS_ENABLED=true
export PREVIEW_CACHE_DIR="$HOME/.ai_pdf_scholar/previews"
export PREVIEW_MAX_WIDTH=1024
export PREVIEW_MIN_WIDTH=200
export PREVIEW_THUMBNAIL_WIDTH=256
export PREVIEW_CACHE_TTL_SECONDS=3600
```

Set `PREVIEWS_ENABLED=false` if you want to disable the preview endpoints entirely.

### 2. Launch The App
```bash
# Run backend (Terminal 1)
source .venv/bin/activate
uvicorn web_main:app --reload --port 8000

# Run frontend (Terminal 2)
cd frontend
npm run dev
```
> Access the app at `http://localhost:5173` and the API docs at `http://localhost:8000/docs`.

### 3. Test Harness
```bash
# Backend contract tests
source .venv/bin/activate
PYTEST_ADDOPTS="--no-cov" pytest

# Frontend unit tests
cd frontend
npm run test -- --run
```

### 4. CI Parity Workflow
Use `docs/CI_PARITY.md` as the source of truth for mirroring GitHub Actions locally. During development run `make lint-staged` to check only the files you touched, and run `make ci-local` before pushing so Ruff, MyPy, backend pytest, and frontend Vitest all match the CI pipeline.

### 5. Docker Deployment
```bash
# Development environment
docker-compose --profile dev up --build

# Production environment
docker-compose --profile prod up -d --build

# Run tests
docker-compose --profile test up --build
```

For detailed deployment instructions, see [DEPLOYMENT.md](./DEPLOYMENT.md).

---

## Project Structure

```
ai_enhanced_pdf_scholar/
├── backend/              # FastAPI backend application
│   ├── api/             # API routes, middleware, models
│   ├── services/        # Business logic services
│   ├── core/            # Core utilities (config, secrets)
│   └── database/        # Database configuration
├── frontend/            # React + TypeScript frontend
│   ├── src/            # Source code
│   ├── public/         # Static assets
│   └── tests/          # Frontend tests
├── src/                # Legacy source code (migrating to backend/)
│   ├── services/       # RAG services, document processing
│   └── database/       # Database models and migrations
├── tests/              # Backend test suite
├── tests_e2e/          # End-to-end tests
├── docs/               # Documentation
├── scripts/            # Utility scripts
├── docker-compose.yml  # Docker orchestration
├── Dockerfile         # Container definition
└── requirements*.txt  # Python dependencies
```

---

## Documentation

- **[API Endpoints](./API_ENDPOINTS.md)** - Complete REST API reference
- **[Deployment Guide](./DEPLOYMENT.md)** - Production deployment instructions
- **[Changelog](./CHANGELOG.md)** - Version history and release notes
- **[Setup Guide](./SETUP.md)** - Detailed development environment setup
- **[Testing Guide](./TESTING.md)** - Testing strategies and best practices
- **[Contributing](./CONTRIBUTING.md)** - Contribution guidelines

---

## Roadmap

See what's coming next in our [Product Roadmap](./ROADMAP.md).

### Recently Completed (v2.1.0)
- ✅ Citation network analysis and visualization
- ✅ Enterprise security framework with RBAC
- ✅ Real-time performance monitoring
- ✅ Multi-document RAG collections
- ✅ Advanced cache management (L1/L2/L3)
- ✅ WebSocket support for live updates

### Coming Soon (v2.2.0)
- 🔄 Multi-language document support
- 🔄 Advanced analytics dashboard
- 🔄 Collaborative annotations
- 🔄 Mobile app companion

---

## License

[MIT License](./LICENSE)

---

*This project was created to showcase product management and software engineering skills.*
