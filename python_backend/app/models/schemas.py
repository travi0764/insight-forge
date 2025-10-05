"""
Pydantic models for request/response validation.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime


# Request Models
class QueryRequest(BaseModel):
    """Request model for PDF querying."""
    query: str = Field(..., min_length=1, max_length=1000, description="Question about the PDF")
    session_id: str = Field(..., min_length=1, description="Session ID from PDF upload")
    k: Optional[int] = Field(4, ge=1, le=20, description="Number of results to retrieve")
    
    @validator('query')
    def validate_query(cls, v: str) -> str:
        """Validate query is not empty after stripping."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


# Response Models
class ExtractedTextResponse(BaseModel):
    """Response model for extracted text."""
    content: str
    page_number: int
    metadata: Dict[str, Any]
    char_count: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "Sample text from page 1...",
                "page_number": 1,
                "metadata": {"extraction_method": "pymupdf"},
                "char_count": 256
            }
        }


class ExtractedTableResponse(BaseModel):
    """Response model for extracted table."""
    data: List[Dict[str, Any]]
    columns: List[str]
    page_number: int
    table_id: str
    shape: tuple
    
    class Config:
        json_schema_extra = {
            "example": {
                "data": [{"col1": "val1", "col2": "val2"}],
                "columns": ["col1", "col2"],
                "page_number": 1,
                "table_id": "table_p1_t1",
                "shape": (2, 2)
            }
        }


class ExtractedImageResponse(BaseModel):
    """Response model for extracted image."""
    base64_data: str
    page_number: int
    image_id: str
    format: str
    width: int
    height: int
    size_bytes: int
    is_chart: Optional[bool] = None
    chart_type: Optional[str] = None
    description: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "base64_data": "data:image/png;base64,iVBORw0KG...",
                "page_number": 1,
                "image_id": "img_p1_i1",
                "format": "png",
                "width": 800,
                "height": 600,
                "size_bytes": 102400,
                "is_chart": True,
                "chart_type": "bar",
                "description": "Sales chart showing quarterly revenue"
            }
        }


class PDFUploadResponse(BaseModel):
    """Response model for PDF upload."""
    success: bool
    session_id: str
    file_hash: str
    total_pages: int
    stats: Dict[str, int]
    extracted_charts: List[ExtractedImageResponse]
    extracted_images: List[ExtractedImageResponse]
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_id": "abc123",
                "file_hash": "sha256hash",
                "total_pages": 10,
                "stats": {
                    "text_blocks": 45,
                    "tables_extracted": 3,
                    "images_extracted": 8,
                    "charts_detected": 2
                },
                "extracted_charts": [],
                "message": "PDF processed successfully"
            }
        }


class QueryResponse(BaseModel):
    """Response model for query."""
    success: bool
    answer: str
    intent: str
    sources: Optional[List[Dict[str, Any]]] = None
    chart_config: Optional[Dict[str, Any]] = None
    confidence: Optional[float] = None
    existing_charts: Optional[List[ExtractedImageResponse]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "answer": "According to the document...",
                "intent": "qna",
                "sources": [{"source": "page_1", "score": 0.95}]
            }
        }


class ErrorResponse(BaseModel):
    """Response model for errors."""
    success: bool = False
    error: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "PDF_PROCESSING_ERROR",
                "message": "Failed to process PDF file",
                "details": {"extraction_type": "table"},
                "timestamp": "2025-01-15T10:30:00"
            }
        }


class SessionStatsResponse(BaseModel):
    """Response model for session statistics."""
    session_id: str
    document_count: int
    collection_name: str
    created_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "abc123",
                "document_count": 156,
                "collection_name": "session_abc123",
                "created_at": "2025-01-15T10:00:00"
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    timestamp: str
    version: str = "1.0.0"
    services: Dict[str, str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-01-15T10:30:00",
                "version": "1.0.0",
                "services": {
                    "vector_store": "operational",
                    "llm": "operational",
                    "embeddings": "operational"
                }
            }
        }