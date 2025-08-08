# AI Enhanced PDF Scholar - Getting Started Guide

## Table of Contents

1. [Welcome](#welcome)
2. [Quick Setup](#quick-setup)
3. [First Steps](#first-steps)
4. [Basic Features](#basic-features)
5. [Common Tasks](#common-tasks)
6. [Troubleshooting](#troubleshooting)
7. [Next Steps](#next-steps)

## Welcome

Welcome to AI Enhanced PDF Scholar! This guide will help you get started quickly with our comprehensive PDF document management and AI-powered research platform.

### What You Can Do

- **📁 Document Management**: Upload, organize, and search your PDF collection
- **🧠 AI-Powered Q&A**: Ask questions about your documents using RAG technology
- **📚 Citation Extraction**: Automatically extract and organize academic citations
- **🔗 Citation Networks**: Visualize relationships between papers
- **📊 Library Analytics**: Get insights into your document collection

## Quick Setup

### System Requirements

- **Operating System**: Windows 10/11, macOS 10.15+, or Linux
- **Python**: 3.11 or higher
- **RAM**: 8GB minimum (16GB recommended)
- **Storage**: 2GB free space for application + space for your documents
- **Internet**: Required for AI features (Google Gemini API)

### Installation Steps

#### Option 1: Quick Start (Recommended)

```bash
# Clone the repository
git clone https://github.com/Jackela/ai-enhanced-pdf-scholar.git
cd ai-enhanced-pdf-scholar

# Install dependencies
pip install -r requirements.txt

# Initialize the system
python -m src.database.migrations

# Start the application
python web_main.py
```

#### Option 2: Development Setup

```bash
# Clone and setup development environment
git clone https://github.com/Jackela/ai-enhanced-pdf-scholar.git
cd ai-enhanced-pdf-scholar

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies
pip install -r requirements-dev.txt

# Run tests to verify setup
pytest

# Start in development mode
python web_main.py --debug
```

### Configuration

1. **Open your browser** and navigate to `http://localhost:8000`
2. **Configure AI Features** (Optional but recommended):
   - Go to Settings → API Configuration
   - Add your Google Gemini API key
   - Enable RAG features for AI-powered document analysis

## First Steps

### Step 1: Upload Your First Document

1. **Navigate to the Library** section
2. **Click "Upload Document"** or drag-and-drop a PDF file
3. **Add metadata** (title, tags) if desired
4. **Wait for processing** - The system will:
   - Extract text content
   - Generate content hash for duplicate detection
   - Create searchable metadata

### Step 2: Explore Your Document

Once uploaded, you can:
- **View document details** by clicking on it
- **Download** the original file
- **Check integrity** to verify the file is accessible
- **Build vector index** for AI features (requires API key)

### Step 3: Try AI Features (Optional)

If you configured the Gemini API key:
1. **Select a document** from your library
2. **Click "Ask AI"** or use the RAG Query interface
3. **Ask questions** like:
   - "What is the main topic of this paper?"
   - "Summarize the key findings"
   - "What methodology was used?"

## Basic Features

### Document Management

#### Upload Documents
- **Supported formats**: PDF only
- **File size limit**: 100MB per file
- **Duplicate detection**: Automatic based on content hash
- **Batch upload**: Multiple files at once

#### Organization
- **Search**: Full-text search across all documents
- **Sorting**: By date, size, title, or last accessed
- **Filtering**: Show/hide documents with missing files
- **Metadata**: Custom tags and descriptions

### AI-Powered Features

#### RAG (Retrieval-Augmented Generation)
- **Smart Q&A**: Ask natural language questions about documents
- **Context-aware**: Uses document content to provide accurate answers
- **Source citations**: Shows which parts of the document informed the answer

#### Citation Management
- **Auto-extraction**: Finds academic references in your documents
- **Smart parsing**: Identifies authors, titles, years, journals
- **Export formats**: BibTeX, EndNote, CSV, JSON
- **Network analysis**: Visualizes citation relationships

### System Features

#### Performance
- **Fast indexing**: Optimized document processing
- **Caching**: Smart caching for faster repeated queries
- **Concurrent processing**: Handle multiple operations simultaneously

#### Data Safety
- **Local storage**: All data stays on your machine
- **Backup**: Easy backup and restore procedures
- **Integrity checks**: Verify document and index health

## Common Tasks

### Task 1: Building a Research Library

```bash
# 1. Upload multiple documents
# Use the web interface or API:
curl -X POST "http://localhost:8000/api/documents/upload" \
     -F "file=@research_paper_1.pdf" \
     -F "title=Research Paper 1"

# 2. Build vector indexes for AI features
curl -X POST "http://localhost:8000/api/rag/build-index" \
     -H "Content-Type: application/json" \
     -d '{"document_id": 1, "force_rebuild": false}'

# 3. Search your library
curl "http://localhost:8000/api/library/search?q=machine+learning&limit=10"
```

### Task 2: Extracting Citations

1. **Select a document** with academic references
2. **Go to Citations** → "Extract Citations"
3. **Review extracted citations** - verify accuracy
4. **Export citations** in your preferred format
5. **Explore citation networks** to find related papers

### Task 3: AI-Powered Research

```python
# Example: Using the Python API client
import requests

# Ask questions about your document
response = requests.post("http://localhost:8000/api/rag/query", json={
    "query": "What are the main contributions of this paper?",
    "document_id": 1
})

result = response.json()
print(f"Answer: {result['answer']}")
print(f"Sources: {len(result['sources'])} relevant passages")
```

### Task 4: Managing Your Library

```bash
# Get library statistics
curl "http://localhost:8000/api/library/stats"

# Find duplicate documents
curl "http://localhost:8000/api/library/duplicates"

# Clean up library (remove orphaned indexes)
curl -X POST "http://localhost:8000/api/library/cleanup"

# Optimize performance
curl -X POST "http://localhost:8000/api/library/optimize"
```

## Troubleshooting

### Common Issues

#### "RAG Service Not Available"
**Problem**: AI features aren't working
**Solution**: 
1. Go to Settings → API Configuration
2. Add your Google Gemini API key
3. Save and restart the application

#### "Document Upload Failed"
**Problem**: Can't upload PDF files
**Solutions**:
- Check file size (must be < 100MB)
- Ensure file is not corrupted
- Verify sufficient disk space
- Try uploading one file at a time

#### "Vector Index Build Failed"
**Problem**: Can't build AI indexes
**Solutions**:
- Verify API key is configured
- Check internet connection
- Ensure document is readable
- Try rebuilding with `force_rebuild: true`

#### Slow Performance
**Problem**: System is running slowly
**Solutions**:
1. **Check system resources**: Close other applications
2. **Optimize library**: Use the cleanup and optimize functions
3. **Reduce concurrent operations**: Limit simultaneous uploads/queries
4. **Check disk space**: Ensure adequate free space

### Getting Help

#### System Health Check
```bash
# Check overall system status
curl "http://localhost:8000/api/system/health"

# Get detailed system information
curl "http://localhost:8000/api/system/info"

# Check storage usage
curl "http://localhost:8000/api/system/storage"
```

#### Log Analysis
- **Application logs**: Check `app_debug.log` for detailed error messages
- **System logs**: Use the monitoring dashboard for system metrics
- **Performance logs**: Check `logs/` directory for performance data

#### Support Resources
- **Documentation**: See `docs/` directory for detailed guides
- **API Reference**: Visit `http://localhost:8000/api/docs` for interactive API docs
- **GitHub Issues**: Report bugs and request features
- **Community Forums**: Connect with other users

## Next Steps

### Explore Advanced Features

1. **📖 Read the [Advanced Features Guide](advanced-features.md)**
   - Learn about advanced search and filtering
   - Master citation network analysis
   - Explore batch processing capabilities

2. **⚙️ Configure Advanced Settings**
   - Set up custom storage locations
   - Configure performance optimization
   - Enable advanced logging and monitoring

3. **🔧 API Integration**
   - Build custom integrations using our REST API
   - Automate document processing workflows
   - Create custom analytics dashboards

4. **📊 Analytics and Insights**
   - Use the library statistics dashboard
   - Analyze your research patterns
   - Export data for external analysis

### Integration Options

#### Jupyter Notebooks
```python
# Example integration for research workflows
from ai_pdf_scholar import PDFScholarClient

client = PDFScholarClient("http://localhost:8000")
documents = client.get_documents()

for doc in documents:
    if doc.has_vector_index:
        answer = client.rag_query(
            "Summarize this document", 
            doc.id
        )
        print(f"{doc.title}: {answer}")
```

#### Automation Scripts
```bash
#!/bin/bash
# Automated document processing pipeline

# Upload all PDFs in a directory
for file in *.pdf; do
    curl -X POST "http://localhost:8000/api/documents/upload" \
         -F "file=@$file"
done

# Build indexes for all documents
curl -X POST "http://localhost:8000/api/rag/build-indexes-all"

# Generate library report
curl "http://localhost:8000/api/library/stats" > library_report.json
```

### Performance Optimization

#### For Large Libraries (1000+ documents)
- Enable database optimization
- Use selective indexing
- Configure caching settings
- Consider hardware upgrades

#### For Heavy AI Usage
- Use batch processing for multiple queries
- Implement query caching
- Consider GPU acceleration (future feature)
- Monitor API usage and costs

## Conclusion

You're now ready to start using AI Enhanced PDF Scholar! This guide covered the basics to get you started quickly. For more advanced features and detailed configuration options, explore the other documentation sections:

- **[Advanced Features Guide](advanced-features.md)** - Power user features
- **[API Documentation](../api/complete-api-reference.md)** - Developer integration
- **[Troubleshooting Guide](../operations/troubleshooting-guide.md)** - Detailed problem solving

Happy researching! 📚🧠✨

---

**Last Updated**: 2025-08-09
**Version**: 2.1.0
**Estimated Reading Time**: 15 minutes