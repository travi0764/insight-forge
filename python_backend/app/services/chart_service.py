"""
Chart analysis service for converting text/CSV data to chart configurations.
Handles AI-powered data extraction and chart type recommendations.
"""
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from openai import AsyncOpenAI

from app.core.logging import get_logger
from app.core.exceptions import DataProcessingError, ChartGenerationError
from app.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.openai_api_key)


@dataclass
class DataPoint:
    """Represents a single data point."""
    label: str
    value: float
    unit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class AnalyzedData:
    """Represents analyzed data with chart configuration."""
    title: str
    data_points: List[DataPoint]
    chart_type: str
    confidence: float
    description: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "dataPoints": [dp.to_dict() for dp in self.data_points],
            "chartType": self.chart_type,
            "confidence": self.confidence,
            "description": self.description
        }


class ChartAnalysisService:
    """
    Service for analyzing data and generating chart configurations.
    
    Features:
    - Text-to-chart conversion with AI
    - Multiple dataset detection
    - Chart type recommendation
    - Chart.js configuration generation
    """
    
    def __init__(self):
        """Initialize the chart analysis service."""
        self.client = client
        logger.info("ChartAnalysisService initialized")
    
    async def analyze_text_data(self, input_text: str) -> AnalyzedData:
        """
        Analyze text and extract structured data for visualization.
        
        Args:
            input_text: Text containing data to visualize
            
        Returns:
            AnalyzedData with chart configuration
            
        Raises:
            DataProcessingError: If analysis fails
        """
        logger.info(f"Analyzing text: {input_text[:50]}...")
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a data analysis expert. Analyze the given text and extract structured data for visualization.

Rules:
1. Extract numerical data points with their labels
2. Determine the most appropriate chart type (pie, bar, or line)
3. Provide a confidence score (0-1) for your chart type recommendation
4. Generate a descriptive title
5. For percentages, ensure they add up to 100% if they represent parts of a whole
6. For pie charts, use when data represents parts of a whole
7. For bar charts, use when comparing different categories
8. For line charts, use when showing trends over time

Respond with JSON in this exact format:
{
  "title": "Chart Title",
  "dataPoints": [
    {"label": "Category 1", "value": 25, "unit": "%"},
    {"label": "Category 2", "value": 50, "unit": "%"}
  ],
  "chartType": "pie",
  "confidence": 0.95,
  "description": "Brief description of what the data shows"
}"""
                    },
                    {
                        "role": "user",
                        "content": input_text
                    }
                ],
                response_format={"type": "json_object"}
            )

            result_content = response.choices[0].message.content
            if not result_content:
                raise ValueError("Empty response from AI")

            result = json.loads(result_content)

            # Validate the response structure
            required_keys = ["title", "dataPoints", "chartType", "confidence", "description"]
            if not all(key in result for key in required_keys):
                raise ValueError("Invalid response format from AI")

            # Ensure confidence is between 0 and 1
            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))

            # Create DataPoint objects
            data_points = []
            for dp in result["dataPoints"]:
                data_points.append(DataPoint(
                    label=dp["label"],
                    value=float(dp["value"]),
                    unit=dp.get("unit")
                ))

            analyzed = AnalyzedData(
                title=result["title"],
                data_points=data_points,
                chart_type=result["chartType"],
                confidence=result["confidence"],
                description=result["description"]
            )
            
            logger.info(f"Analysis complete: {analyzed.chart_type} chart with {len(data_points)} points")
            return analyzed
            
        except Exception as e:
            logger.error(f"Error analyzing data: {e}")
            raise DataProcessingError(f"Failed to analyze data: {str(e)}")
    
    async def analyze_multiple_datasets(self, input_text: str) -> Dict[str, Any]:
        """
        Analyze text and identify multiple distinct datasets.
        
        Args:
            input_text: Text containing multiple datasets
            
        Returns:
            Dictionary with multiple datasets
            
        Raises:
            DataProcessingError: If analysis fails
        """
        logger.info(f"Analyzing for multiple datasets: {input_text[:50]}...")
        
        try:
            response = await self.client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a data visualization expert. Analyze the given text and identify ALL DISTINCT datasets that can be visualized separately.

CRITICAL RULES:
1. Look for MULTIPLE DIFFERENT data categories/topics in the input text
2. Each dataset should represent a DIFFERENT concept (e.g., work preferences, revenue growth, device usage, etc.)
3. Extract each dataset as a separate chart with its own title, data points, and best chart type
4. DO NOT create variations of the same dataset - create separate datasets
5. Automatically select the BEST chart type for each dataset:
   - Pie/Doughnut: For parts of a whole (percentages that sum to 100%)
   - Bar: For comparing different categories 
   - Line: For trends over time or sequential data
6. Provide confidence score and reasoning for each chart type selection

Example input: "50% prefer A, 30% prefer B, 20% prefer C. Sales grew from $1M to $3M over 3 years."
Expected output: 2 datasets (preferences pie chart, revenue growth line chart)

Respond with JSON in this exact format:
{
  "datasets": [
    {
      "title": "Work Preference Distribution",
      "dataPoints": [
        {"label": "Remote Work", "value": 65, "unit": "%"},
        {"label": "Office Work", "value": 35, "unit": "%"}
      ],
      "chartType": "pie",
      "confidence": 0.95,
      "description": "Employee work location preferences"
    },
    {
      "title": "Revenue Growth Over Time", 
      "dataPoints": [
        {"label": "2021", "value": 2, "unit": "M"},
        {"label": "2023", "value": 5, "unit": "M"}
      ],
      "chartType": "line",
      "confidence": 0.90,
      "description": "Company revenue growth from 2021 to 2023"
    }
  ],
  "totalAnalyzedDatasets": 2,
  "description": "Analysis found 2 distinct datasets for visualization"
}"""
                    },
                    {
                        "role": "user",
                        "content": input_text
                    }
                ],
                response_format={"type": "json_object"}
            )

            result_content = response.choices[0].message.content
            if not result_content:
                raise ValueError("Empty response from AI")

            result = json.loads(result_content)

            # Validate the response structure
            if "datasets" not in result or not isinstance(result["datasets"], list) or len(result["datasets"]) == 0:
                raise ValueError("Invalid response format from AI - no datasets found")

            datasets = []
            for dataset_data in result["datasets"]:
                # Validate each dataset
                required_keys = ["title", "dataPoints", "chartType", "confidence", "description"]
                if not all(key in dataset_data for key in required_keys):
                    raise ValueError("Invalid dataset structure")

                dataset_data["confidence"] = max(0.0, min(1.0, float(dataset_data["confidence"])))

                data_points = []
                for dp in dataset_data["dataPoints"]:
                    data_points.append(DataPoint(
                        label=dp["label"],
                        value=float(dp["value"]),
                        unit=dp.get("unit")
                    ))

                datasets.append(AnalyzedData(
                    title=dataset_data["title"],
                    data_points=data_points,
                    chart_type=dataset_data["chartType"],
                    confidence=dataset_data["confidence"],
                    description=dataset_data["description"]
                ))

            result["datasets"] = datasets
            result["totalAnalyzedDatasets"] = len(datasets)
            
            logger.info(f"Found {len(datasets)} distinct datasets")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing multiple datasets: {e}")
            raise DataProcessingError(f"Failed to analyze multiple datasets: {str(e)}")
    
    def convert_to_chart_config(self, analyzed_data: AnalyzedData) -> Dict[str, Any]:
        """
        Convert analyzed data to Chart.js configuration.
        
        Args:
            analyzed_data: Analyzed data with chart information
            
        Returns:
            Chart.js configuration dictionary
        """
        labels = [point.label for point in analyzed_data.data_points]
        values = [point.value for point in analyzed_data.data_points]

        colors = [
            '#3b82f6',  # blue
            '#22c55e',  # green
            '#f59e0b',  # amber
            '#a855f7',  # purple
            '#ef4444',  # red
            '#06b6d4',  # cyan
            '#f97316',  # orange
            '#8b5cf6',  # violet
        ]

        background_color = colors[:len(values)]

        base_config = {
            "type": analyzed_data.chart_type,
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": analyzed_data.title,
                    "data": values,
                    "backgroundColor": background_color,
                    "borderWidth": 2,
                    "borderColor": '#ffffff',
                }]
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "title": {
                        "display": True,
                        "text": analyzed_data.title,
                        "font": {
                            "size": 16,
                            "weight": 'bold'
                        }
                    },
                    "legend": {
                        "position": 'bottom',
                        "labels": {
                            "color": '#4B5563',
                            "font": {
                                "size": 14
                            }
                        }
                    }
                },
                "animation": {
                    "duration": 2000,
                    "easing": 'easeInOutQuart'
                }
            }
        }

        # Chart type specific configurations
        if analyzed_data.chart_type == 'bar':
            base_config["options"]["scales"] = {
                "y": {
                    "beginAtZero": True,
                    "grid": {
                        "color": 'rgba(0, 0, 0, 0.1)'
                    }
                },
                "x": {
                    "grid": {
                        "display": False
                    }
                }
            }

        if analyzed_data.chart_type == 'line':
            base_config["data"]["datasets"][0].update({
                "fill": False,
                "borderColor": colors[0],
                "backgroundColor": colors[0],
                "tension": 0.4
            })
            base_config["options"]["scales"] = {
                "y": {
                    "beginAtZero": True,
                    "grid": {
                        "color": 'rgba(0, 0, 0, 0.1)'
                    }
                },
                "x": {
                    "grid": {
                        "display": False
                    }
                }
            }

        return base_config
    
    def convert_multiple_to_configs(self, datasets: List[AnalyzedData]) -> List[Dict[str, Any]]:
        """
        Convert multiple datasets to Chart.js configurations.
        
        Args:
            datasets: List of analyzed datasets
            
        Returns:
            List of Chart.js configurations
        """
        configs = []
        for index, dataset in enumerate(datasets):
            chart_config = self.convert_to_chart_config(dataset)
            chart_config["metadata"] = {
                "confidence": dataset.confidence,
                "reason": dataset.description,
                "rank": index + 1,
                "datasetIndex": index
            }
            configs.append(chart_config)
        
        logger.info(f"Generated {len(configs)} chart configurations")
        return configs


# Global service instance
_chart_service: Optional[ChartAnalysisService] = None


def get_chart_service() -> ChartAnalysisService:
    """Get or create the global chart analysis service instance."""
    global _chart_service
    if _chart_service is None:
        _chart_service = ChartAnalysisService()
    return _chart_service