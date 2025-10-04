"""
Custom exception classes for better error handling and API responses.
All exceptions inherit from ChartAIException for consistent error handling.
"""
from typing import Optional, Dict, Any


class ChartAIException(Exception):
    """Base exception for all application errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize base exception.
        
        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            details: Additional error details
        """
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for API responses.
        
        Returns:
            Dictionary with error information
        """
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details
        }
    
    def __str__(self) -> str:
        """String representation of the exception."""
        return f"{self.error_code}: {self.message}"


# PDF Processing Exceptions
class PDFProcessingError(ChartAIException):
    """Raised when PDF processing fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="PDF_PROCESSING_ERROR",
            details=details
        )


class PDFExtractionError(PDFProcessingError):
    """Raised when data extraction from PDF fails."""
    
    def __init__(self, message: str, extraction_type: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["extraction_type"] = extraction_type
        super().__init__(message=message, details=details)


class TableExtractionError(PDFExtractionError):
    """Raised when table extraction fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            extraction_type="table",
            details=details
        )


class ImageExtractionError(PDFExtractionError):
    """Raised when image extraction fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            extraction_type="image",
            details=details
        )


class TextExtractionError(PDFExtractionError):
    """Raised when text extraction fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            extraction_type="text",
            details=details
        )


# Vector Store Exceptions
class VectorStoreError(ChartAIException):
    """Raised when vector store operations fail."""
    
    def __init__(self, message: str, operation: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["operation"] = operation
        super().__init__(
            message=message,
            error_code="VECTOR_STORE_ERROR",
            details=details
        )


class CollectionError(VectorStoreError):
    """Raised when collection operations fail."""
    
    def __init__(self, message: str, collection_name: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if collection_name:
            details["collection_name"] = collection_name
        super().__init__(
            message=message,
            operation="collection_management",
            details=details
        )


# Session Management Exceptions
class SessionError(ChartAIException):
    """Raised when session operations fail."""
    
    def __init__(self, message: str, session_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if session_id:
            details["session_id"] = session_id
        super().__init__(
            message=message,
            error_code="SESSION_ERROR",
            details=details
        )


class SessionNotFoundError(SessionError):
    """Raised when session is not found."""
    
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session not found: {session_id}",
            session_id=session_id
        )
        self.error_code = "SESSION_NOT_FOUND"


class SessionExpiredError(SessionError):
    """Raised when session has expired."""
    
    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session has expired: {session_id}",
            session_id=session_id
        )
        self.error_code = "SESSION_EXPIRED"


# RAG System Exceptions
class RAGError(ChartAIException):
    """Raised when RAG operations fail."""
    
    def __init__(self, message: str, operation: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["operation"] = operation
        super().__init__(
            message=message,
            error_code="RAG_ERROR",
            details=details
        )


class EmbeddingError(RAGError):
    """Raised when embedding generation fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            operation="embedding",
            details=details
        )


class LLMError(RAGError):
    """Raised when LLM operations fail."""
    
    def __init__(self, message: str, model: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if model:
            details["model"] = model
        super().__init__(
            message=message,
            operation="llm_generation",
            details=details
        )


class RetrievalError(RAGError):
    """Raised when document retrieval fails."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            operation="document_retrieval",
            details=details
        )


# Validation Exceptions
class ValidationError(ChartAIException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details=details
        )


class FileValidationError(ValidationError):
    """Raised when file validation fails."""
    
    def __init__(self, message: str, filename: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if filename:
            details["filename"] = filename
        super().__init__(
            message=message,
            field="file",
            details=details
        )


# Configuration Exceptions
class ConfigurationError(ChartAIException):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, config_key: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details=details
        )


class MissingConfigError(ConfigurationError):
    """Raised when required configuration is missing."""
    
    def __init__(self, config_key: str):
        super().__init__(
            message=f"Required configuration missing: {config_key}",
            config_key=config_key
        )


# Storage Exceptions
class StorageError(ChartAIException):
    """Raised when storage operations fail."""
    
    def __init__(self, message: str, storage_type: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["storage_type"] = storage_type
        super().__init__(
            message=message,
            error_code="STORAGE_ERROR",
            details=details
        )


class FileSystemError(StorageError):
    """Raised when file system operations fail."""
    
    def __init__(self, message: str, path: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if path:
            details["path"] = path
        super().__init__(
            message=message,
            storage_type="filesystem",
            details=details
        )


class DatabaseError(StorageError):
    """Raised when database operations fail."""
    
    def __init__(self, message: str, database: str = "unknown", details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["database"] = database
        super().__init__(
            message=message,
            storage_type="database",
            details=details
        )


# API Exceptions
class APIError(ChartAIException):
    """Raised when external API calls fail."""
    
    def __init__(self, message: str, api_name: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["api_name"] = api_name
        super().__init__(
            message=message,
            error_code="API_ERROR",
            details=details
        )


class OpenAIAPIError(APIError):
    """Raised when OpenAI API calls fail."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            api_name="OpenAI",
            details=details
        )


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""
    
    def __init__(self, api_name: str, retry_after: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(
            message=f"Rate limit exceeded for {api_name}",
            api_name=api_name,
            details=details
        )
        self.error_code = "RATE_LIMIT_ERROR"


# Data Processing Exceptions
class DataProcessingError(ChartAIException):
    """Raised when data processing fails."""
    
    def __init__(self, message: str, data_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if data_type:
            details["data_type"] = data_type
        super().__init__(
            message=message,
            error_code="DATA_PROCESSING_ERROR",
            details=details
        )


class ChartGenerationError(DataProcessingError):
    """Raised when chart generation fails."""
    
    def __init__(self, message: str, chart_type: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        if chart_type:
            details["chart_type"] = chart_type
        super().__init__(
            message=message,
            data_type="chart",
            details=details
        )