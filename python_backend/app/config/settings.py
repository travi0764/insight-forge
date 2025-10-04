"""
Configuration management for the application.
Centralized settings with environment variable support.
"""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # API Keys
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    
    # MongoDB Settings
    mongo_uri: Optional[str] = Field(None, env="MONGO_URI")
    mongo_db_name: str = Field("chartai", env="MONGO_DB_NAME")
    mongo_collection_name: str = Field("sessions", env="MONGO_COLLECTION_NAME")
    
    # ChromaDB Settings
    chroma_persist_directory: str = Field(
        "./data/chromadb", 
        env="CHROMA_PERSIST_DIRECTORY"
    )
    use_chroma: bool = Field(True, env="USE_CHROMA")
    
    # PDF Processing Settings
    pdf_extract_images: bool = Field(True, env="PDF_EXTRACT_IMAGES")
    pdf_extract_tables: bool = Field(True, env="PDF_EXTRACT_TABLES")
    pdf_use_ocr: bool = Field(False, env="PDF_USE_OCR")
    max_image_size_mb: int = Field(5, env="MAX_IMAGE_SIZE_MB")
    
    # Text Splitting Settings
    chunk_size: int = Field(1000, env="CHUNK_SIZE")
    chunk_overlap: int = Field(200, env="CHUNK_OVERLAP")
    
    # RAG Settings
    retrieval_k: int = Field(4, env="RETRIEVAL_K")
    llm_model: str = Field("gpt-4-turbo", env="LLM_MODEL")
    vision_model: str = Field("gpt-4o", env="VISION_MODEL")
    embedding_model: str = Field("text-embedding-3-small", env="EMBEDDING_MODEL")
    
    # Server Settings
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(5000, env="PORT")
    debug: bool = Field(False, env="DEBUG")
    
    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str = Field("logs/app.log", env="LOG_FILE")
    
    # Storage Paths
    temp_dir: str = Field("./data/temp", env="TEMP_DIR")
    metadata_dir: str = Field("./data/metadata", env="METADATA_DIR")
    
    @validator("openai_api_key")
    def validate_api_key(cls, v: str) -> str:
        """Validate OpenAI API key is not empty."""
        if not v or v.strip() == "":
            raise ValueError("OPENAI_API_KEY cannot be empty")
        return v
    
    @validator("chunk_size")
    def validate_chunk_size(cls, v: int) -> int:
        """Validate chunk size is reasonable."""
        if v < 100 or v > 5000:
            raise ValueError("chunk_size must be between 100 and 5000")
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings