# AI Enhanced PDF Scholar

[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0%2B-green)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-212%20passing-brightgreen)](tests/)

🚀 **An AI-enhanced PDF academic reading tool based on PyQt6, making academic reading more efficient through intelligent conversation**

## ⚠️ Disclaimer

**This is a pure Vibe Coding project!** 🎨

- This project is an experimental tool developed for interest and learning purposes
- Currently **only supports Google Gemini API** (future development plans include other AI services, but not implemented yet)
- Code quality and feature completeness may have limitations
- Please use your own judgment regarding the accuracy of any results produced by this tool
- No responsibility is assumed for any losses or issues caused by using this tool

## ✨ Features

### 🤖 AI-Powered Conversations
- **One-Click AI Q&A**: Select any text in PDF and ask AI for intelligent explanations
- **Context Understanding**: AI comprehends full document context for accurate responses
- **Markdown Rendering**: AI responses support complete Markdown format including code highlighting, lists, tables, etc.

### 🎨 Modern Interface
- **Material Design**: Modern design language with 8 elegant color schemes
- **Fully Responsive**: Intelligently adapts to different screen sizes (tablet to 4K displays)
- **Zero Hardcoding**: All UI parameters configurable, supports personalization
- **Smooth Animations**: 250ms smooth transitions for elegant user experience

### 📖 Powerful PDF Processing
- **High-Quality Rendering**: 150 DPI high-definition PDF display
- **Smart Selection**: Supports both text selection and area screenshot modes
- **Multi-Page Support**: Smooth page navigation and zoom functionality

### 🔧 Technical Advantages
- **Asynchronous Processing**: Multi-threaded architecture, UI never freezes
- **Error Recovery**: Comprehensive error handling and recovery mechanisms
- **High Test Coverage**: 212 test cases ensuring code quality
- **Cross-Platform**: Compatible with Windows, macOS, Linux

## 🚀 Quick Start

### Requirements
- Python 3.12+
- PyQt6 6.9.1+
- Supported OS: Windows 10+, macOS 10.15+, Linux

### Installation

1. **Clone Repository**
```bash
git clone https://github.com/yourusername/ai_enhanced_pdf_scholar.git
cd ai_enhanced_pdf_scholar
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure AI Service**
   - Get [Google Gemini API Key](https://makersuite.google.com/app/apikey)
   - Launch app and click "⚙️ Settings" to configure API key

4. **Start Application**
```bash
python main.py
```

## 📱 Usage

### Basic Operations
1. **Open PDF**: Click "📂 Open PDF" button to select PDF file
2. **Select Text**: Use mouse to select text you want to inquire about in PDF
3. **AI Q&A**: Enter questions in popup dialog or click submit directly
4. **View Responses**: AI responses will display in right panel with Markdown support

### Advanced Features
- **Mode Switching**: Switch between text selection/area screenshot modes in toolbar
- **Responsive Layout**: Drag window edges to adjust interface size, UI auto-adapts
- **Batch Annotations**: Create multiple annotations simultaneously for comparative learning

## 🛠️ Technology Stack

### Core Technologies
- **UI Framework**: PyQt6 - Modern cross-platform GUI framework
- **PDF Processing**: PyMuPDF - High-performance PDF rendering engine
- **AI Service**: Google Gemini - Advanced large language model
- **Markdown**: Python-Markdown - Rich text rendering support

### Architecture Design
- **MVC Pattern**: Clear Model-View-Controller architecture
- **Signal-Slot Mechanism**: Event-driven component communication
- **Responsive Design**: Breakpoint-based layout adaptation system
- **Modular Development**: High cohesion, low coupling component design

## 🧪 Development & Testing

### Run Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific tests
python -m pytest tests/test_modern_ui_features.py -v

# Generate coverage report
python -m pytest tests/ --cov=src --cov-report=html
```

### Test Statistics
- **Total Tests**: 212
- **Test Categories**: Unit tests, Component tests, Integration tests, UI tests, Error scenario tests
- **Coverage**: 100% coverage for core functionality
- **Test Framework**: pytest + pytest-qt (GUI testing)

## 📂 Project Structure

```
ai_enhanced_pdf_scholar/
├── 📄 main.py                    # Main application entry
├── ⚙️ config.py                  # Responsive configuration system
├── 📋 requirements.txt           # Project dependencies
├── 📖 README.md                  # Project documentation (Chinese)
├── 📖 README_EN.md               # Project documentation (English)
├── 📚 PROJECT_DOCS.md            # Technical documentation
├── 📁 src/                       # Core source code
│   ├── 🖼️ pdf_viewer.py          # PDF rendering and interaction
│   ├── 🤖 llm_service.py         # AI service interface
│   ├── 💬 annotation.py          # Smart annotation component
│   ├── 📱 responsive_utils.py    # Responsive UI utilities
│   └── 🔧 ...                    # Other core modules
└── 🧪 tests/                     # Test suite (212 tests)
    ├── 🔬 test_*.py              # Various test files
    └── ⚙️ conftest.py            # Test configuration
```

## 🤝 Contributing

We welcome all forms of contributions!

### How to Contribute
1. **Report Issues**: Found a bug? Create an Issue
2. **Feature Suggestions**: Have new ideas? Create a Feature Request
3. **Code Contributions**: Fork the project and submit Pull Request
4. **Documentation**: Help improve project documentation

### Development Environment
```bash
# Clone development branch
git clone -b develop https://github.com/yourusername/ai_enhanced_pdf_scholar.git

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-qt pytest-cov

# Run tests to ensure environment is working
python -m pytest tests/ -v
```

## 📝 Changelog

### Version 2.0.0 (2025-07-02) - Responsive UI Refactor
- ✅ **Fully Responsive Design**: Eliminated all hardcoding, supports 4 breakpoint adaptation
- ✅ **Markdown Rendering Support**: AI responses support rich text format
- ✅ **Material Design Interface**: Modern visual design
- ✅ **Smart Window Management**: Auto-centering and size adaptation
- ✅ **Enhanced Test Coverage**: Added 22 UI tests, total of 212 tests

### Version 1.0.0 (2025-01-15) - Initial Release
- 🎉 **Core Features Complete**: PDF reading, AI Q&A, smart annotations
- 🎉 **PyQt6 Interface**: Modern desktop application
- 🎉 **Gemini Integration**: Large language model support
- 🎉 **Cross-Platform Support**: Windows, macOS, Linux compatible

## 📄 License

This project is licensed under the [MIT License](LICENSE).

## 🙏 Acknowledgments

Thanks to the following open source projects:
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - Powerful GUI framework
- [PyMuPDF](https://pymupdf.readthedocs.io/) - Excellent PDF processing library
- [Google Gemini](https://deepmind.google/technologies/gemini/) - Advanced AI technology
- [Python-Markdown](https://python-markdown.github.io/) - Markdown rendering engine

---

<div align="center">

**If this project helps you, please give us a ⭐ Star!**

[Report Issues](../../issues) • [Feature Requests](../../issues/new) • [Contribute Code](../../pulls)

</div> 