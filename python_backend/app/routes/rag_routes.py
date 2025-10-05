"""
API routes for RAG functionality.
"""
import os
import tempfile
from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, Body, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.core.exceptions import (
    ChartAIException,
    SessionNotFoundError,
    PDFProcessingError,
    ValidationError
)
from app.models.schemas import (
    QueryRequest,
    PDFUploadResponse,
    QueryResponse,
    ErrorResponse,
    SessionStatsResponse,
    HealthResponse
)
from app.services.rag_service import get_rag_service

logger = get_logger(__name__)
router = APIRouter(prefix="/api/rag", tags=["RAG"])


@router.post(
    "/upload-pdf",
    response_model=PDFUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload and process a PDF file",
    description="Upload a PDF file for extraction and indexing. Extracts text, tables, images, and charts."
)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload and process a PDF file.
    
    Args:
        file: PDF file to upload
        
    Returns:
        Processing result with session ID and extracted data
        
    Raises:
        HTTPException: If processing fails
    """
    logger.info(f"Received PDF upload: {file.filename}")
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported"
        )
    
    # Validate file size (e.g., max 50MB)
    max_size_mb = 50
    temp_file_path = None
    
    try:
        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            
            # Check file size
            size_mb = len(content) / (1024 * 1024)
            if size_mb > max_size_mb:
                raise ValidationError(
                    f"File too large: {size_mb:.2f}MB (max: {max_size_mb}MB)",
                    field="file"
                )
            
            tmp.write(content)
            temp_file_path = tmp.name
        
        logger.info(f"Saved PDF to temporary file: {temp_file_path}")
        
        # Process PDF
        rag_service = get_rag_service()
        result = await rag_service.upload_and_process_pdf(temp_file_path)
        
        # Build response
        response = PDFUploadResponse(
            success=True,
            session_id=result["session_id"],
            file_hash=result["file_hash"],
            total_pages=result["total_pages"],
            stats=result["stats"],
            extracted_charts=result["extracted_charts"],
            extracted_images=result["extracted_images"],
            message="PDF uploaded and processed successfully" +
                    (" (reused existing session)" if result.get("reused") else "")
        )
        
        logger.info(f"PDF processed successfully: session_id={result['session_id']}")
        return response
        
    except ValidationError as e:
        logger.warning(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict()
        )
    
    except PDFProcessingError as e:
        logger.error(f"PDF processing error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.to_dict()
        )
    
    except Exception as e:
        logger.error(f"Unexpected error during PDF upload: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": str(e)}
        )
    
    finally:
        # Clean up temporary file if it wasn't deleted by the service
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.debug(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {str(e)}")


@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query a processed PDF",
    description="Ask questions about a previously uploaded PDF or request data visualizations."
)
async def query_pdf(request: QueryRequest = Body(...)):
    """
    Query a processed PDF.
    
    Args:
        request: Query request with question and session ID
        
    Returns:
        Query response with answer and relevant data
        
    Raises:
        HTTPException: If query fails
    """
    logger.info(f"Query request: session_id={request.session_id}, query={request.query[:50]}...")
    
    try:
        rag_service = get_rag_service()
        result = await rag_service.query(
            query=request.query,
            session_id=request.session_id,
            k=request.k
        )
        
        response = QueryResponse(
            success=True,
            **result
        )
        
        logger.info(f"Query completed: intent={result['intent']}")
        return response
        
    except SessionNotFoundError as e:
        logger.warning(f"Session not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()
        )
    
    except ChartAIException as e:
        logger.error(f"Query error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=e.to_dict()
        )
    
    except Exception as e:
        logger.error(f"Unexpected error during query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": str(e)}
        )


@router.get(
    "/session/{session_id}/stats",
    response_model=SessionStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get session statistics",
    description="Retrieve statistics for a specific session."
)
async def get_session_stats(session_id: str):
    """
    Get statistics for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session statistics
        
    Raises:
        HTTPException: If session not found
    """
    logger.info(f"Getting stats for session: {session_id}")
    
    try:
        rag_service = get_rag_service()
        stats = rag_service.get_session_stats(session_id)
        
        return SessionStatsResponse(**stats)
        
    except SessionNotFoundError as e:
        logger.warning(f"Session not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict()
        )
    
    except Exception as e:
        logger.error(f"Failed to get session stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": str(e)}
        )


@router.delete(
    "/session/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Clear a session",
    description="Delete a session and all its associated data."
)
async def clear_session(session_id: str):
    """
    Clear a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If clearing fails
    """
    logger.info(f"Clearing session: {session_id}")
    
    try:
        rag_service = get_rag_service()
        success = rag_service.clear_session(session_id)
        
        if success:
            return {
                "success": True,
                "message": f"Session {session_id} cleared successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "CLEAR_FAILED", "message": "Failed to clear session"}
            )
        
    except Exception as e:
        logger.error(f"Failed to clear session: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": str(e)}
        )


@router.get(
    "/sessions",
    status_code=status.HTTP_200_OK,
    summary="List all active sessions",
    description="Get a list of all active session IDs."
)
async def list_sessions():
    """
    List all active sessions.
    
    Returns:
        List of session IDs
    """
    logger.info("Listing all sessions")
    
    try:
        rag_service = get_rag_service()
        sessions = rag_service.list_active_sessions()
        
        return {
            "success": True,
            "sessions": sessions,
            "count": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"Failed to list sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR", "message": str(e)}
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Check the health status of the RAG service and its components."
)
async def health_check():
    """
    Perform health check on RAG service.
    
    Returns:
        Health status
    """
    logger.info("Health check requested")
    
    try:
        rag_service = get_rag_service()
        services_health = await rag_service.health_check()
        
        # Determine overall status
        overall_status = "healthy" if all(
            status == "operational" for status in services_health.values()
        ) else "degraded"
        
        return HealthResponse(
            status=overall_status,
            timestamp=datetime.now().isoformat(),
            services=services_health
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.now().isoformat(),
            services={"error": str(e)}
        )


# Note: Exception handlers are defined in main.py at the app level