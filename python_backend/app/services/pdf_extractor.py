"""
Enhanced PDF data extraction service.
Extracts text, tables, images, and charts from PDF files.
"""
import base64
import io
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict
from PIL import Image
import fitz
import pdfplumber
import pandas as pd
import numpy as np

from app.core.logging import get_logger
from app.core.exceptions import (
    PDFProcessingError,
    TableExtractionError,
    ImageExtractionError
)
from app.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class ExtractedText:
    """Represents extracted text content."""
    content: str
    page_number: int
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExtractedTable:
    """Represents extracted table data."""
    data: pd.DataFrame
    page_number: int
    bbox: Tuple[float, float, float, float]  # x0, y0, x1, y1
    table_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self.data.to_dict(orient='records'),
            "columns": self.data.columns.tolist(),
            "page_number": self.page_number,
            "bbox": self.bbox,
            "table_id": self.table_id,
            "shape": self.data.shape
        }
    
    def to_markdown(self) -> str:
        """Convert table to markdown format."""
        return self.data.to_markdown(index=False)
    
    def to_csv_string(self) -> str:
        """Convert table to CSV string."""
        return self.data.to_csv(index=False)


@dataclass
class ExtractedImage:
    """Represents extracted image."""
    base64_data: str
    page_number: int
    image_id: str
    format: str
    width: int
    height: int
    size_bytes: int
    bbox: Optional[Tuple[float, float, float, float]] = None
    is_chart: Optional[bool] = None
    chart_type: Optional[str] = None
    description: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Include base64 with data URI scheme
        data["base64_data"] = f"data:image/{self.format};base64,{self.base64_data}"
        return data


@dataclass
class PDFExtractionResult:
    """Complete PDF extraction result."""
    file_hash: str
    total_pages: int
    texts: List[ExtractedText]
    tables: List[ExtractedTable]
    images: List[ExtractedImage]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_hash": self.file_hash,
            "total_pages": self.total_pages,
            "texts": [t.to_dict() for t in self.texts],
            "tables": [t.to_dict() for t in self.tables],
            "images": [img.to_dict() for img in self.images],
            "metadata": self.metadata,
            "stats": {
                "text_blocks": len(self.texts),
                "tables_extracted": len(self.tables),
                "images_extracted": len(self.images),
                "charts_detected": sum(1 for img in self.images if img.is_chart)
            }
        }


class PDFExtractor:
    """
    Enhanced PDF extractor with comprehensive data extraction capabilities.
    
    Features:
    - Text extraction with structure preservation
    - Table extraction using multiple libraries
    - Image extraction with size filtering
    - Chart/graph detection and data extraction
    """
    
    def __init__(self):
        self.min_image_width = 100
        self.min_image_height = 100
        self.max_image_size_mb = settings.max_image_size_mb
        logger.info("PDFExtractor initialized")
    
    def compute_file_hash(self, file_path: str) -> str:
        """
        Compute SHA-256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hexadecimal hash string
        """
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"Failed to compute file hash: {str(e)}")
            raise PDFProcessingError(f"Failed to compute file hash: {str(e)}")
    
    def extract_text_with_pymupdf(self, pdf_path: str) -> List[ExtractedText]:
        """
        Extract text from PDF using PyMuPDF with structure preservation.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of extracted text blocks
        """
        texts = []
        try:
            doc = fitz.open(pdf_path)
            logger.info(f"Extracting text from {len(doc)} pages")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Extract text blocks with position info
                blocks = page.get_text("dict")["blocks"]
                
                page_text_parts = []
                for block in blocks:
                    if block.get("type") == 0:  # Text block
                        for line in block.get("lines", []):
                            line_text = ""
                            for span in line.get("spans", []):
                                line_text += span.get("text", "")
                            if line_text.strip():
                                page_text_parts.append(line_text.strip())
                
                if page_text_parts:
                    full_text = "\n".join(page_text_parts)
                    texts.append(ExtractedText(
                        content=full_text,
                        page_number=page_num + 1,
                        metadata={
                            "extraction_method": "pymupdf",
                            "block_count": len(blocks),
                            "char_count": len(full_text)
                        }
                    ))
            
            doc.close()
            logger.info(f"Extracted text from {len(texts)} pages")
            return texts
            
        except Exception as e:
            logger.error(f"Text extraction failed: {str(e)}")
            raise PDFProcessingError(f"Failed to extract text: {str(e)}")
    
    def extract_tables_with_pdfplumber(self, pdf_path: str) -> List[ExtractedTable]:
        """
        Extract tables from PDF using pdfplumber.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of extracted tables
        """
        tables = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                logger.info(f"Extracting tables from {len(pdf.pages)} pages")
                
                for page_num, page in enumerate(pdf.pages):
                    # Extract tables with settings for better detection
                    page_tables = page.extract_tables()
                    
                    for table_idx, table_data in enumerate(page_tables):
                        if not table_data or len(table_data) < 2:
                            continue
                        
                        try:
                            # Convert to DataFrame
                            df = pd.DataFrame(table_data[1:], columns=table_data[0])
                            
                            # Clean the dataframe
                            df = df.dropna(how='all').dropna(axis=1, how='all')
                            
                            # Skip if too small
                            if df.shape[0] < 1 or df.shape[1] < 2:
                                continue
                            
                            # Generate table ID
                            table_id = f"table_p{page_num + 1}_t{table_idx + 1}"
                            
                            tables.append(ExtractedTable(
                                data=df,
                                page_number=page_num + 1,
                                bbox=(0, 0, 0, 0),  # pdfplumber doesn't provide bbox easily
                                table_id=table_id
                            ))
                            
                        except Exception as e:
                            logger.warning(f"Failed to process table {table_idx} on page {page_num + 1}: {str(e)}")
                            continue
                
                logger.info(f"Extracted {len(tables)} tables")
                return tables
                
        except Exception as e:
            logger.error(f"Table extraction failed: {str(e)}")
            raise TableExtractionError(f"Failed to extract tables: {str(e)}")
    
    def extract_images_with_pymupdf(self, pdf_path: str) -> List[ExtractedImage]:
        """
        Extract images from PDF using PyMuPDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of extracted images
        """
        images = []
        try:
            doc = fitz.open(pdf_path)
            logger.info(f"Extracting images from {len(doc)} pages")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                image_list = page.get_images(full=True)
                
                for img_idx, img in enumerate(image_list):
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        # Filter by format
                        if image_ext not in ("png", "jpeg", "jpg"):
                            continue
                        
                        # Check image size
                        width = base_image["width"]
                        height = base_image["height"]
                        
                        if width < self.min_image_width or height < self.min_image_height:
                            logger.debug(f"Skipping small image: {width}x{height}")
                            continue
                        
                        # Check file size
                        size_mb = len(image_bytes) / (1024 * 1024)
                        if size_mb > self.max_image_size_mb:
                            logger.warning(f"Image too large: {size_mb:.2f}MB, skipping")
                            continue
                        
                        # Convert to base64
                        base64_str = base64.b64encode(image_bytes).decode('utf-8')
                        
                        # Generate image ID
                        image_id = f"img_p{page_num + 1}_i{img_idx + 1}"
                        
                        images.append(ExtractedImage(
                            base64_data=base64_str,
                            page_number=page_num + 1,
                            image_id=image_id,
                            format=image_ext,
                            width=width,
                            height=height,
                            size_bytes=len(image_bytes),
                            bbox=None  # Could extract bbox if needed
                        ))
                        
                    except Exception as e:
                        logger.warning(f"Failed to extract image {img_idx} from page {page_num + 1}: {str(e)}")
                        continue
            
            doc.close()
            logger.info(f"Extracted {len(images)} images")
            return images
            
        except Exception as e:
            logger.error(f"Image extraction failed: {str(e)}")
            raise ImageExtractionError(f"Failed to extract images: {str(e)}")
    
    async def extract_all(self, pdf_path: str) -> PDFExtractionResult:
        """
        Extract all data from PDF: text, tables, and images.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Complete extraction result
        """
        logger.info(f"Starting comprehensive PDF extraction: {pdf_path}")
        
        try:
            # Validate file exists
            if not Path(pdf_path).exists():
                raise PDFProcessingError(f"PDF file not found: {pdf_path}")
            
            # Compute file hash
            file_hash = self.compute_file_hash(pdf_path)
            logger.info(f"PDF file hash: {file_hash}")
            
            # Get PDF metadata
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            pdf_metadata = doc.metadata
            doc.close()
            
            # Extract text
            texts = self.extract_text_with_pymupdf(pdf_path)
            
            # Extract tables if enabled
            tables = []
            if settings.pdf_extract_tables:
                try:
                    tables = self.extract_tables_with_pdfplumber(pdf_path)
                except Exception as e:
                    logger.warning(f"Table extraction failed, continuing without tables: {str(e)}")
            
            # Extract images if enabled
            images = []
            if settings.pdf_extract_images:
                try:
                    images = self.extract_images_with_pymupdf(pdf_path)
                except Exception as e:
                    logger.warning(f"Image extraction failed, continuing without images: {str(e)}")
            
            # Create result
            result = PDFExtractionResult(
                file_hash=file_hash,
                total_pages=total_pages,
                texts=texts,
                tables=tables,
                images=images,
                metadata={
                    "pdf_metadata": pdf_metadata,
                    "file_path": pdf_path,
                    "extraction_timestamp": pd.Timestamp.now().isoformat()
                }
            )
            
            logger.info(
                f"Extraction complete: {len(texts)} text blocks, "
                f"{len(tables)} tables, {len(images)} images"
            )
            
            return result
            
        except PDFProcessingError:
            raise
        except Exception as e:
            logger.error(f"PDF extraction failed: {str(e)}")
            raise PDFProcessingError(f"Failed to extract PDF data: {str(e)}")