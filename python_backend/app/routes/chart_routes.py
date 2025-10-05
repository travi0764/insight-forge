"""
API routes for chart analysis and data visualization.
Handles text-to-chart, CSV parsing, and multi-dataset analysis.
"""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field, validator

from app.core.logging import get_logger
from app.core.exceptions import DataProcessingError, ValidationError
from app.services.chart_service import get_chart_service
from app.services.csv_service import parse_csv_data

logger = get_logger(__name__)
router = APIRouter(prefix="/api/chart", tags=["Chart Analysis"])


# Request Models
class AnalyzeDataRequest(BaseModel):
    """Request model for analyzing data."""
    text: str = Field(..., min_length=1, description="Text input is required")
    chart_type: Optional[str] = Field("auto", description="Chart type: auto, pie, bar, line")
    
    @validator('text')
    def validate_text(cls, v: str) -> str:
        """Validate text is not empty after stripping."""
        if not v.strip():
            raise ValueError("Text cannot be empty")
        return v.strip()
    
    @validator('chart_type')
    def validate_chart_type(cls, v: str) -> str:
        """Validate chart type."""
        valid_types = ["auto", "pie", "bar", "line", "doughnut", "area"]
        if v.lower() not in valid_types:
            raise ValueError(f"Invalid chart type. Must be one of: {', '.join(valid_types)}")
        return v.lower()


class AnalyzeMultiRequest(BaseModel):
    """Request model for multi-chart analysis."""
    text: str = Field(..., min_length=1, description="Text input is required")
    max_charts: Optional[int] = Field(5, ge=2, le=10, description="Maximum number of charts")
    
    @validator('text')
    def validate_text(cls, v: str) -> str:
        """Validate text is not empty after stripping."""
        if not v.strip():
            raise ValueError("Text cannot be empty")
        return v.strip()


class ParseCSVRequest(BaseModel):
    """Request model for parsing CSV."""
    csv_content: str = Field(..., min_length=1, description="CSV content is required")
    
    @validator('csv_content')
    def validate_csv(cls, v: str) -> str:
        """Validate CSV content."""
        if not v.strip():
            raise ValueError("CSV content cannot be empty")
        # Check for at least one comma or newline (basic CSV structure)
        if ',' not in v and '\n' not in v:
            raise ValueError("Invalid CSV format")
        return v.strip()


# Routes
@router.post(
    "/analyze-data",
    status_code=status.HTTP_200_OK,
    summary="Analyze text data and generate chart",
    description="Convert text data into structured chart configuration with AI-powered analysis."
)
async def analyze_data(req: AnalyzeDataRequest = Body(...)):
    """
    Analyze text data and generate chart configuration.
    
    Example input:
    ```json
    {
        "text": "Sales: Apple 30%, Samsung 25%, Others 45%",
        "chart_type": "auto"
    }
    ```
    
    Args:
        req: Request with text and optional chart type
        
    Returns:
        Chart configuration with analyzed data
        
    Raises:
        HTTPException: If analysis fails
    """
    logger.info(f"Analyzing data: {req.text[:50]}...")
    logger.debug(f"Requested chart type: {req.chart_type}")
    
    try:
        # Get chart service instance
        chart_service = get_chart_service()
        
        # Analyze the text using service method
        analyzed = await chart_service.analyze_text_data(req.text)
        
        # Override chart type if specified and not auto
        if req.chart_type != "auto":
            analyzed.chart_type = req.chart_type
        
        # Convert to chart configuration using service method
        chart_config = chart_service.convert_to_chart_config(analyzed)
        
        logger.info(f"Analysis complete: chart_type={analyzed.chart_type}, confidence={analyzed.confidence}")
        
        return {
            "success": True,
            "data": {
                "analyzedData": analyzed.to_dict(),
                "chartConfig": chart_config,
                "confidence": {
                    analyzed.chart_type: analyzed.confidence,
                    "auto": 1.0
                }
            }
        }
        
    except ValueError as e:
        logger.error(f"Validation error in analyze_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error in analyze_data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ANALYSIS_ERROR", "message": f"Failed to analyze data: {str(e)}"}
        )


@router.post(
    "/parse-csv",
    status_code=status.HTTP_200_OK,
    summary="Parse CSV and generate chart",
    description="Parse CSV content and convert to chart configuration."
)
async def parse_csv_route(req: ParseCSVRequest = Body(...)):
    """
    Parse CSV content and generate chart configuration.
    
    Example input:
    ```json
    {
        "csv_content": "Category,Value\\nApple,30\\nSamsung,25\\nOthers,45"
    }
    ```
    
    Args:
        req: Request with CSV content
        
    Returns:
        Parsed CSV data with chart configuration
        
    Raises:
        HTTPException: If parsing fails
    """
    logger.info("Parsing CSV data")
    
    try:
        # Get chart service instance
        chart_service = get_chart_service()
        
        # Parse CSV using csv_service function
        parsed = parse_csv_data(req.csv_content)
        
        # Convert parsed data to text format for analysis
        text_data = ", ".join([
            f"{point.label}: {point.value}" 
            for point in parsed.data_points
        ])
        
        if not text_data:
            raise ValueError("No valid data points found in CSV")
        
        # Analyze the data using chart service
        analyzed = await chart_service.analyze_text_data(text_data)
        
        # Convert to chart configuration using service method
        chart_config = chart_service.convert_to_chart_config(analyzed)
        
        logger.info(f"CSV parsed successfully: {len(parsed.data_points)} data points")
        
        return {
            "success": True,
            "data": {
                "parsedCSV": parsed.to_dict(),
                "analyzedData": analyzed.to_dict(),
                "chartConfig": chart_config,
                "confidence": {
                    analyzed.chart_type: analyzed.confidence,
                    "auto": 1.0
                }
            }
        }
        
    except ValueError as e:
        logger.error(f"CSV parsing validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "CSV_VALIDATION_ERROR", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error in parse_csv: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "CSV_PARSING_ERROR", "message": f"Failed to parse CSV: {str(e)}"}
        )


@router.post(
    "/analyze-data-multi",
    status_code=status.HTTP_200_OK,
    summary="Analyze text for multiple charts",
    description="Identify and generate multiple distinct chart configurations from text data."
)
async def analyze_data_multi(req: AnalyzeMultiRequest = Body(...)):
    """
    Analyze text data and generate multiple chart configurations.
    
    This endpoint identifies multiple distinct datasets in the input text
    and generates separate charts for each.
    
    Example input:
    ```json
    {
        "text": "Sales by region: North 40%, South 35%, East 25%. Revenue growth: Q1 $1M, Q2 $1.5M, Q3 $2M",
        "max_charts": 5
    }
    ```
    
    Args:
        req: Request with text and maximum number of charts
        
    Returns:
        Multiple chart configurations
        
    Raises:
        HTTPException: If analysis fails
    """
    logger.info(f"Multi-chart analysis: {req.text[:50]}...")
    
    try:
        # Get chart service instance
        chart_service = get_chart_service()
        
        # Analyze for multiple datasets using service method
        multi_dataset_analysis = await chart_service.analyze_multiple_datasets(req.text)
        
        datasets = multi_dataset_analysis["datasets"]
        
        # Limit the number of datasets if specified
        if req.max_charts and len(datasets) > req.max_charts:
            datasets = datasets[:req.max_charts]
            logger.info(f"Limited to {req.max_charts} charts")
        
        # Convert datasets to chart configurations using service method
        chart_configs = chart_service.convert_multiple_to_configs(datasets)
        
        # Create compatible structure for frontend
        multi_chart_analysis = {
            "title": "Multi-Dataset Analysis",
            "description": multi_dataset_analysis.get("description", ""),
            "chartVariations": [
                {
                    "chartType": dataset.chart_type,
                    "confidence": dataset.confidence,
                    "reason": dataset.description,
                    "title": dataset.title
                } 
                for dataset in datasets
            ]
        }
        
        logger.info(f"Multi-chart analysis complete: {len(chart_configs)} charts generated")
        
        return {
            "success": True,
            "data": {
                "multiChartAnalysis": multi_chart_analysis,
                "chartConfigs": chart_configs,
                "totalCharts": len(chart_configs)
            }
        }
        
    except ValueError as e:
        logger.error(f"Validation error in analyze_data_multi: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "VALIDATION_ERROR", "message": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error in analyze_data_multi: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "MULTI_ANALYSIS_ERROR", "message": f"Failed to analyze data: {str(e)}"}
        )


@router.get(
    "/chart-types",
    status_code=status.HTTP_200_OK,
    summary="Get supported chart types",
    description="List all supported chart types and their descriptions."
)
async def get_chart_types():
    """
    Get list of supported chart types.
    
    Returns:
        List of chart types with descriptions
    """
    return {
        "success": True,
        "chartTypes": [
            {
                "type": "pie",
                "name": "Pie Chart",
                "description": "Best for showing parts of a whole (percentages)",
                "useCases": ["Market share", "Budget allocation", "Survey results"]
            },
            {
                "type": "bar",
                "name": "Bar Chart",
                "description": "Best for comparing categories",
                "useCases": ["Sales by product", "Regional comparison", "Rankings"]
            },
            {
                "type": "line",
                "name": "Line Chart",
                "description": "Best for showing trends over time",
                "useCases": ["Revenue growth", "Stock prices", "Temperature changes"]
            },
            {
                "type": "doughnut",
                "name": "Doughnut Chart",
                "description": "Similar to pie chart with center hollow",
                "useCases": ["Market share", "Budget allocation", "Composition"]
            },
            {
                "type": "area",
                "name": "Area Chart",
                "description": "Line chart with filled area below",
                "useCases": ["Cumulative totals", "Volume over time", "Stacked data"]
            }
        ]
    }