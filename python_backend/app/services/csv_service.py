"""
CSV parsing service for converting CSV data to structured format.
"""
import csv
from io import StringIO
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

from app.core.logging import get_logger
from app.core.exceptions import ValidationError

logger = get_logger(__name__)


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
class ParsedCSV:
    """Represents parsed CSV data."""
    headers: List[str]
    rows: List[List[Any]]
    data_points: List[DataPoint]
    detected_columns: Dict[str, Optional[str]]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "headers": self.headers,
            "rows": self.rows,
            "dataPoints": [dp.to_dict() for dp in self.data_points],
            "detectedColumns": self.detected_columns
        }


def detect_columns(headers: List[str], data: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    """
    Detect label and value columns in CSV data.
    
    Args:
        headers: List of CSV headers
        data: Parsed CSV rows as dictionaries
        
    Returns:
        Dictionary with 'label' and 'value' column names
    """
    label_keywords = ['label', 'name', 'category', 'item', 'product', 'brand', 'type']
    value_keywords = ['value', 'amount', 'count', 'number', 'percentage', 'percent', 'quantity', 'total']

    label_column: Optional[str] = None
    value_column: Optional[str] = None

    # Find label column
    for header in headers:
        lower_header = header.lower().strip()
        if any(keyword in lower_header for keyword in label_keywords):
            label_column = header
            break

    # Fallback: Use first non-numeric column as label
    if not label_column and data:
        for header in headers:
            first_value = data[0].get(header, '')
            if isinstance(first_value, str):
                # Check if it's not a numeric string
                try:
                    float(str(first_value).replace(',', ''))
                except (ValueError, AttributeError):
                    label_column = header
                    break

    # Find value column
    for header in headers:
        lower_header = header.lower().strip()
        if any(keyword in lower_header for keyword in value_keywords):
            value_column = header
            break

    # Fallback: Use first numeric column as value
    if not value_column and data:
        for header in headers:
            first_value = data[0].get(header, '')
            try:
                # Try to convert to float
                float(str(first_value).replace(',', ''))
                value_column = header
                break
            except (ValueError, AttributeError, TypeError):
                continue

    logger.debug(f"Detected columns: label={label_column}, value={value_column}")
    return {
        'label': label_column,
        'value': value_column
    }


def parse_csv_data(csv_content: str) -> ParsedCSV:
    """
    Parse CSV content into structured data for visualization.
    
    Args:
        csv_content: Raw CSV content as a string
        
    Returns:
        ParsedCSV object containing headers, rows, and data points
        
    Raises:
        ValidationError: If CSV parsing fails or no valid data is found
    """
    logger.info("Parsing CSV data")
    
    try:
        # Use StringIO to treat string as file-like object for csv.DictReader
        reader = csv.DictReader(StringIO(csv_content), skipinitialspace=True)
        data = list(reader)
        
        # Get headers (fieldnames) or default to empty list
        headers = reader.fieldnames or []
        if not headers:
            raise ValueError("No headers found in CSV")

        # Validate that we have data
        if not data:
            raise ValueError("No data rows found in CSV")

        logger.debug(f"CSV headers: {headers}")
        logger.debug(f"CSV rows: {len(data)}")

        # Detect label and value columns
        detected_columns = detect_columns(headers, data)

        # Convert rows to data points
        data_points = []
        for index, row in enumerate(data):
            label = row.get(detected_columns['label'] or '', f"Row {index + 1}")
            
            try:
                value_str = row.get(detected_columns['value'] or '', '0')
                # Remove commas and convert to float
                value_str = str(value_str).replace(',', '').strip()
                value = float(value_str)
            except (ValueError, TypeError, AttributeError):
                logger.warning(f"Could not parse value in row {index + 1}: {value_str}")
                value = 0.0  # Default to 0 for non-numeric values
            
            # Only include valid data points (non-zero values)
            if value != 0:
                data_points.append(DataPoint(
                    label=str(label).strip(),
                    value=value,
                    unit=None  # Unit detection can be added if needed
                ))

        # Convert data to rows (list of lists) for consistency
        rows = [list(row.values()) for row in data]

        # Ensure we have valid data points
        if not data_points:
            raise ValueError("No valid data points found in CSV")

        logger.info(f"Parsed {len(data_points)} data points from CSV")
        
        return ParsedCSV(
            headers=headers,
            rows=rows,
            data_points=data_points,
            detected_columns=detected_columns
        )

    except ValueError as e:
        logger.error(f"CSV validation error: {str(e)}")
        raise ValidationError(f"CSV validation failed: {str(e)}", field="csv_content")
    
    except Exception as e:
        logger.error(f"CSV parsing error: {str(e)}")
        raise ValidationError(f"Failed to parse CSV file: {str(e)}", field="csv_content")