# ChartAI Backend - Production-Ready RAG System

## Overview

A production-grade RAG (Retrieval-Augmented Generation) system for comprehensive PDF data extraction and intelligent querying. Built with FastAPI, ChromaDB, and OpenAI.

### Key Features

- **Comprehensive PDF Extraction**: Text, tables, images, and charts
- **Advanced Table Detection**: Using pdfplumber for accurate table extraction
- **Chart Recognition**: AI-powered chart/graph detection and data extraction
- **Vector Search**: ChromaDB for efficient semantic search
- **Session Management**: File deduplication and session caching
- **Production Ready**: Proper logging, error handling, and type safety

## Architecture

```
python_backend/
├── app/
│   ├── config/
│   │   └── settings.py           # Configuration management
│   ├── core/
│   │   ├── logging.py            # Centralized logging
│   │   └── exceptions.py         # Custom exceptions
│   ├── models/
│   │   └── schemas.py            # Pydantic models
│   ├── services/
│   │   ├── pdf_extractor.py      # PDF data extraction
│   │   ├── vector_store.py       # ChromaDB integration
│   │   └── rag_service.py        # Main RAG orchestration
│   ├── routes/
│   │   └── rag_routes.py         # API endpoints
│   └── main.py                   # FastAPI application
├── data/                         # Generated directories
│   ├── chromadb/                 # ChromaDB storage
│   ├── temp/                     # Temporary files
│   └── metadata/                 # Session metadata
├── logs/                         # Application logs
├── requirements.txt
├── .env
└── README.md
```

## Installation

### Prerequisites

- Python 3.9+
- OpenAI API key
- (Optional) MongoDB Atlas account
- Tesseract OCR (if using OCR feature)

### Step 1: Clone and Setup

```bash
# Clone the repository
cd python_backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Unix/MacOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Install System Dependencies

#### For Table Extraction (Camelot)
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk ghostscript

# MacOS
brew install ghostscript tcl-tk

# Windows
# Download and install Ghostscript from https://www.ghostscript.com/download/gsdnld.html
```

#### For OCR (Optional)
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr

# MacOS
brew install tesseract

# Windows
# Download from https://github.com/UB-Mannheim/tesseract/wiki
```

### Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your OpenAI API key
OPENAI_API_KEY=sk-your-actual-api-key-here
```

### Step 4: Run the Application

```bash
# Development mode with auto-reload
python -m app.main

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

The API will be available at:
- API: `http://localhost:5000`
- Swagger Docs: `http://localhost:5000/api/docs`
- ReDoc: `http://localhost:5000/api/redoc`

## API Endpoints

### 1. Upload PDF
```http
POST /api/rag/upload-pdf
Content-Type: multipart/form-data

file: <PDF file>
```

**Response:**
```json
{
  "success": true,
  "session_id": "abc-123-def-456",
  "file_hash": "sha256hash...",
  "total_pages": 10,
  "stats": {
    "text_blocks": 45,
    "tables_extracted": 3,
    "images_extracted": 8,
    "charts_detected": 2
  },
  "extracted_charts": [...],
  "message": "PDF uploaded and processed successfully"
}
```

### 2. Query PDF
```http
POST /api/rag/query
Content-Type: application/json

{
  "query": "What are the key findings in this report?",
  "session_id": "abc-123-def-456",
  "k": 4
}
```

**Response:**
```json
{
  "success": true,
  "answer": "According to the document...",
  "intent": "qna",
  "sources": [
    {"source": "text", "page_number": 1}
  ]
}
```

### 3. Get Session Stats
```http
GET /api/rag/session/{session_id}/stats
```

### 4. Clear Session
```http
DELETE /api/rag/session/{session_id}
```

### 5. List Sessions
```http
GET /api/rag/sessions
```

### 6. Health Check
```http
GET /api/rag/health
```

## Configuration Options

### PDF Processing
- `PDF_EXTRACT_IMAGES`: Enable/disable image extraction (default: true)
- `PDF_EXTRACT_TABLES`: Enable/disable table extraction (default: true)
- `PDF_USE_OCR`: Enable OCR for scanned PDFs (default: false)
- `MAX_IMAGE_SIZE_MB`: Maximum image size to extract (default: 5)

### Vector Store
- `CHROMA_PERSIST_DIRECTORY`: ChromaDB storage location
- `CHUNK_SIZE`: Text chunk size for embeddings (default: 1000)
- `CHUNK_OVERLAP`: Overlap between chunks (default: 200)

### RAG Settings
- `RETRIEVAL_K`: Number of documents to retrieve (default: 4)
- `LLM_MODEL`: OpenAI model for text generation (default: gpt-4-turbo)
- `VISION_MODEL`: OpenAI model for image analysis (default: gpt-4o)
- `EMBEDDING_MODEL`: Embedding model (default: text-embedding-3-small)

## Features in Detail

### 1. Comprehensive PDF Extraction

The system extracts multiple data types from PDFs:

**Text Extraction:**
- Uses PyMuPDF for structure-preserving text extraction
- Maintains paragraph and block structure
- Extracts metadata about each text block

**Table Extraction:**
- Uses pdfplumber for accurate table detection
- Converts tables to pandas DataFrames
- Supports both markdown and CSV formats
- Handles complex table structures

**Image Extraction:**
- Extracts all images with size filtering
- Supports PNG and JPEG formats
- Base64 encoding for API responses

**Chart Detection:**
- AI-powered chart/graph recognition
- Automatic data point extraction
- Classification by chart type (bar, pie, line, etc.)

### 2. Vector Store with ChromaDB

- **Persistent Storage**: All embeddings saved to disk
- **Session Isolation**: Separate collections per session
- **Efficient Search**: Fast similarity search with metadata filtering
- **Scalable**: Handles large documents with chunking

### 3. Intelligent Query Routing

The system automatically determines query intent:

**Q&A Intent:**
- Standard question answering
- Context-aware responses
- Source attribution

**Visualization Intent:**
- Detects requests for charts/graphs
- Extracts data from query
- Generates chart configurations
- Returns Chart.js configs

### 4. Session Management

- **File Deduplication**: SHA-256 hash-based duplicate detection
- **Session Caching**: In-memory cache for fast access
- **Metadata Persistence**: ChromaDB + optional MongoDB

## Production Considerations

### Logging

Logs are saved to `logs/app.log` with the following format:
```
2025-01-15 10:30:00 | INFO | pdf_extractor.py:123 | Extracted 45 text blocks
```

Configure log level in `.env`:
```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Error Handling

All errors are properly typed and return consistent JSON:
```json
{
  "error": "PDF_PROCESSING_ERROR",
  "message": "Failed to extract tables",
  "details": {
    "extraction_type": "table"
  }
}
```

### Performance Optimization

1. **Batch Processing**: Documents added in batches of 100
2. **Caching**: In-memory session cache
3. **File Deduplication**: Avoid reprocessing same files
4. **Lazy Loading**: Collections loaded on demand

### Security

- Input validation with Pydantic
- File size limits (default: 50MB)
- File type validation
- Temporary file cleanup
- No arbitrary code execution

## Troubleshooting

### Issue: ChromaDB persistence errors
**Solution:** Ensure the data directory has write permissions
```bash
mkdir -p data/chromadb
chmod -R 755 data/
```

### Issue: PDF extraction fails
**Solution:** Check if Ghostscript is installed for Camelot
```bash
gs --version
```

### Issue: Out of memory errors
**Solution:** Reduce chunk size or process fewer documents
```bash
CHUNK_SIZE=500
RETRIEVAL_K=2
```

### Issue: OpenAI rate limits
**Solution:** Add retry logic or use a higher tier API key

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

### Code Quality
```bash
# Format code
black app/

# Lint
flake8 app/

# Type checking
mypy app/
```

## Migration from Old Code

If migrating from your old codebase:

1. **Vector Store**: FAISS → ChromaDB
   - Automatic migration on first run
   - No manual intervention needed

2. **PDF Extraction**: Unstructured → Multi-library approach
   - Better table extraction
   - More comprehensive image extraction
   - Chart detection added

3. **Session Storage**: MongoDB/JSON → ChromaDB + optional MongoDB
   - More efficient storage
   - Better query performance

## Next Steps

1. **Add Video Generation**: Integrate Manim or similar for MP4 export
2. **Add Authentication**: JWT tokens for API access
3. **Add Rate Limiting**: Prevent abuse
4. **Add Caching**: Redis for response caching
5. **Add Monitoring**: Prometheus metrics
6. **Add Testing**: Unit and integration tests

## Support

For issues or questions:
- Check the logs in `logs/app.log`
- Review API docs at `/api/docs`
- Check environment variables in `.env`

## License

<!-- [Your License Here] -->