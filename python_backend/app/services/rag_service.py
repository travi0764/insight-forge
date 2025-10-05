"""
RAG (Retrieval-Augmented Generation) service.
Orchestrates PDF processing, vector storage, and LLM querying.
"""
import json
from typing import Dict, Any, List, Optional
import uuid
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.documents import Document

from app.core.logging import get_logger
from app.core.exceptions import (
    RAGError,
    LLMError,
    SessionNotFoundError,
    PDFProcessingError
)
from app.config.settings import get_settings
from app.services.pdf_extractor import PDFExtractor, PDFExtractionResult
from app.services.vector_store import VectorStore

logger = get_logger(__name__)
settings = get_settings()


class RAGService:
    """
    Main RAG service for PDF processing and querying.
    
    Features:
    - PDF upload and comprehensive data extraction
    - Vector store management with ChromaDB
    - Intelligent query routing (visualization vs Q&A)
    - Chart detection and data extraction from images
    - Session management with deduplication
    """
    
    def __init__(self):
        """Initialize RAG service with all components."""
        try:
            # Initialize components
            self.pdf_extractor = PDFExtractor()
            self.vector_store = VectorStore()
            
            # Initialize LLMs
            self.llm = ChatOpenAI(
                model=settings.llm_model,
                api_key=settings.openai_api_key,
                temperature=0.3
            )
            
            self.vision_llm = ChatOpenAI(
                model=settings.vision_model,
                api_key=settings.openai_api_key,
                temperature=0.2
            )
            
            # Initialize prompts
            self._setup_prompts()
            
            # In-memory session cache
            self.sessions: Dict[str, Dict[str, Any]] = {}
            
            logger.info("RAG Service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {str(e)}")
            raise RAGError(
                f"Failed to initialize RAG service: {str(e)}",
                operation="initialization"
            )
    
    def _setup_prompts(self):
        """Setup LLM prompts for different tasks."""
        # Intent classification prompt
        self.intent_prompt = ChatPromptTemplate.from_template(
            """Analyze if this query requires data visualization or is a Q&A question.
            
Query: {query}

If the query asks for charts, graphs, or data visualization, respond with "viz" intent and extract key data points.
If it's a question about content, respond with "qna" intent.

Respond in JSON format:
{{
    "intent": "viz" or "qna",
    "reasoning": "brief explanation",
    "extracted_data": {{
        "data_points": [{{"label": "str", "value": float}}],
        "chart_type": "bar/pie/line/etc"
    }} (only if intent is viz)
}}"""
        )
        
        # Image analysis prompt for chart detection
        self.chart_detection_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert at analyzing images to detect if they are charts or graphs.

Analyze the image and determine:
1. Is this a chart/graph/plot?
2. If yes, what type? (bar, pie, line, scatter, etc.)
3. Extract any visible data points
4. Provide a description

Respond in JSON format:
{{
    "is_chart": true/false,
    "type": "chart type" (if is_chart is true),
    "title": "chart title if visible",
    "data_points": [
        {{"label": "label1", "value": 123}},
        {{"label": "label2", "value": 456}}
    ],
    "description": "detailed description"
}}"""),
            ("user", [
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/{format};base64,{base64_image}"}
                }
            ])
        ])
        
        # Q&A prompt
        self.qa_prompt = ChatPromptTemplate.from_template(
            """You are a helpful assistant answering questions about a PDF document.

Context from the document:
{context}

Question: {query}

Provide a clear, concise answer based on the context. If the context doesn't contain relevant information, say so.

Answer:"""
        )
        
        # Visualization answer prompt
        self.viz_answer_prompt = ChatPromptTemplate.from_template(
            """Based on the document context below, answer the user's query about data visualization.

Context:
{context}

Query: {query}

A chart has been generated based on the extracted data. Provide a brief explanation of what the chart shows.

Answer:"""
        )
    
    async def _analyze_image_for_chart(
        self,
        base64_image: str,
        image_format: str
    ) -> Dict[str, Any]:
        """
        Analyze an image to detect if it's a chart and extract data.
        
        Args:
            base64_image: Base64 encoded image
            image_format: Image format (png, jpeg, etc.)
            
        Returns:
            Analysis result with chart detection and data extraction
        """
        try:
            chain = self.chart_detection_prompt | self.vision_llm | JsonOutputParser()
            result = await chain.ainvoke({
                "base64_image": base64_image,
                "format": image_format
            })
            
            logger.debug(f"Chart analysis: is_chart={result.get('is_chart')}")
            return result
            
        except Exception as e:
            logger.warning(f"Failed to analyze image for chart: {str(e)}")
            return {
                "is_chart": False,
                "description": "Failed to analyze image",
                "error": str(e)
            }
    
    async def upload_and_process_pdf(
        self,
        pdf_path: str
    ) -> Dict[str, Any]:
        """
        Upload and process a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Processing result with session ID and extracted data
        """
        logger.info(f"Processing PDF: {pdf_path}")
        
        try:
            # Check for existing session with same file hash
            file_hash = self.pdf_extractor.compute_file_hash(pdf_path)
            
            # Check if already processed
            for session_id, session_data in self.sessions.items():
                if session_data.get("file_hash") == file_hash:
                    logger.info(f"PDF already processed, reusing session {session_id}")
                    return {
                        "session_id": session_id,
                        "file_hash": file_hash,
                        "total_pages": session_data["extraction_result"].total_pages,
                        "stats": session_data["extraction_result"].to_dict()["stats"],
                        "extracted_charts": [
                            img.to_dict() for img in session_data["extraction_result"].images
                            if img.is_chart
                        ],
                        "extracted_images": [
                            img.to_dict() for img in session_data["extraction_result"].images
                        ],
                        "reused": True
                    }
            
            # Extract all data from PDF
            extraction_result: PDFExtractionResult = await self.pdf_extractor.extract_all(pdf_path)
            
            # Analyze images for charts
            logger.info(f"Analyzing {len(extraction_result.images)} images for charts")
            for image in extraction_result.images:
                chart_analysis = await self._analyze_image_for_chart(
                    image.base64_data,
                    image.format
                )
                
                image.is_chart = chart_analysis.get("is_chart", False)
                image.chart_type = chart_analysis.get("type")
                image.description = chart_analysis.get("description", "")
                image.extracted_data = chart_analysis.get("data_points")
            
            # Create session
            session_id = str(uuid.uuid4())
            
            # Prepare documents for vector store
            documents = []
            
            # Add text documents
            for text in extraction_result.texts:
                doc = Document(
                    page_content=text.content,
                    metadata={
                        "source": "text",
                        "page_number": text.page_number,
                        **text.metadata
                    }
                )
                documents.append(doc)
            
            # Add table documents
            for table in extraction_result.tables:
                rows, columns = table.data.shape
                # Add as markdown
                markdown_content = f"Table {table.table_id}:\n{table.to_markdown()}"
                doc = Document(
                    page_content=markdown_content,
                    metadata={
                        "source": "table",
                        "page_number": table.page_number,
                        "table_id": table.table_id,
                        "table_rows": int(rows),
                        "table_columns": int(columns)
                    }
                )
                documents.append(doc)
                
                # Also add as CSV for better searchability
                csv_content = f"Table {table.table_id} (CSV):\n{table.to_csv_string()}"
                doc_csv = Document(
                    page_content=csv_content,
                    metadata={
                        "source": "table_csv",
                        "page_number": table.page_number,
                        "table_id": table.table_id
                    }
                )
                documents.append(doc_csv)
            
            # Add image/chart documents
            for image in extraction_result.images:
                if image.is_chart and image.description:
                    content = f"Chart {image.image_id}:\n{image.description}"
                    if image.extracted_data:
                        content += f"\nData: {json.dumps(image.extracted_data)}"
                    
                    doc = Document(
                        page_content=content,
                        metadata={
                            "source": "chart",
                            "page_number": image.page_number,
                            "image_id": image.image_id,
                            "chart_type": image.chart_type
                        }
                    )
                    documents.append(doc)
            
            # Add documents to vector store
            logger.info(f"Adding {len(documents)} documents to vector store")
            await self.vector_store.add_documents(session_id, documents)
            
            # Store session data
            self.sessions[session_id] = {
                "file_hash": file_hash,
                "extraction_result": extraction_result,
                "created_at": extraction_result.metadata["extraction_timestamp"]
            }
            
            # Clean up PDF file
            try:
                Path(pdf_path).unlink()
                logger.info(f"Cleaned up temporary PDF file: {pdf_path}")
            except Exception as e:
                logger.warning(f"Failed to delete PDF file: {str(e)}")
            
            return {
                "session_id": session_id,
                "file_hash": file_hash,
                "total_pages": extraction_result.total_pages,
                "stats": extraction_result.to_dict()["stats"],
                "extracted_charts": [
                    img.to_dict() for img in extraction_result.images
                    if img.is_chart
                ],
                "extracted_images": [
                    img.to_dict() for img in extraction_result.images
                ],
                "reused": False
            }
            
        except PDFProcessingError:
            raise
        except Exception as e:
            logger.error(f"Failed to process PDF: {str(e)}")
            raise RAGError(
                f"Failed to process PDF: {str(e)}",
                operation="upload_and_process_pdf"
            )
    
    async def query(
        self,
        query: str,
        session_id: str,
        k: int = 4
    ) -> Dict[str, Any]:
        """
        Query the RAG system.
        
        Args:
            query: User query
            session_id: Session identifier
            k: Number of documents to retrieve
            
        Returns:
            Query response with answer and relevant data
        """
        logger.info(f"Query for session {session_id}: {query}")
        
        # Validate session exists
        if session_id not in self.sessions:
            logger.error(f"Session not found: {session_id}")
            raise SessionNotFoundError(session_id)
        
        try:
            # Retrieve relevant documents
            search_results = await self.vector_store.similarity_search(
                session_id=session_id,
                query=query,
                k=k
            )
            
            context = "\n\n".join([result["content"] for result in search_results])
            
            # Classify intent
            intent_chain = self.intent_prompt | self.llm | JsonOutputParser()
            intent_result = await intent_chain.ainvoke({"query": query})

            intent = intent_result.get("intent", "qna")
            logger.info(f"Query intent classified as: {intent}")

            # Handle based on intent
            if intent == "viz":
                # Visualization query
                extracted = intent_result.get("extracted_data", {})
                
                # Convert data points to text format for analysis
                data_points = extracted.get("data_points", [])
                if data_points:
                    # Format as text: "label1: value1, label2: value2"
                    text_data = ", ".join([
                        f"{point.get('label', 'item')}: {point.get('value', 0)}" 
                        for point in data_points
                    ])
                else:
                    text_data = "No data points extracted"
                
                # Import chart service for chart generation
                from app.services.chart_service import get_chart_service
                
                chart_service = get_chart_service()
                analyzed = await chart_service.analyze_text_data(text_data)
                chart_cfg = chart_service.convert_to_chart_config(analyzed)
                
                answer_prompt = ChatPromptTemplate.from_template(
                    "Based on context: {context}\nAnswer the query: {query}\nA chart has been generated showing the data visualization."
                )
                answer_chain = answer_prompt | self.llm
                answer = await answer_chain.ainvoke({"context": context, "query": query})

                response = {
                    "answer": answer.content,
                    "intent": "viz",
                    "chart_config": chart_cfg,
                    "confidence": analyzed.confidence,
                    "sources": [result["metadata"] for result in search_results]
                }

                return response

            else:
                # Q&A query
                qa_chain = self.qa_prompt | self.llm
                answer_response = await qa_chain.ainvoke({
                    "context": context,
                    "query": query
                })
                
                response = {
                    "answer": answer_response.content,
                    "intent": "qna",
                    "sources": [result["metadata"] for result in search_results]
                }
                
                # If query mentions charts/graphs, include existing charts
                if any(keyword in query.lower() for keyword in ["chart", "graph", "plot", "figure", "visualization"]):
                    session_data = self.sessions[session_id]
                    charts = [
                        img.to_dict() for img in session_data["extraction_result"].images
                        if img.is_chart
                    ]
                    response["existing_charts"] = charts
                
                return response
                
        except SessionNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Query failed: {str(e)}")
            raise RAGError(
                f"Failed to process query: {str(e)}",
                operation="query"
            )
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear a session and its data.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if cleared successfully
        """
        try:
            # Remove from vector store
            self.vector_store.delete_collection(session_id)
            
            # Remove from in-memory cache
            if session_id in self.sessions:
                del self.sessions[session_id]
            
            logger.info(f"Cleared session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear session: {str(e)}")
            return False
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Get statistics for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session statistics
        """
        if session_id not in self.sessions:
            raise SessionNotFoundError(session_id)
        
        session_data = self.sessions[session_id]
        vector_stats = self.vector_store.get_collection_stats(session_id)
        
        return {
            "session_id": session_id,
            "file_hash": session_data["file_hash"],
            "created_at": session_data["created_at"],
            "total_pages": session_data["extraction_result"].total_pages,
            "stats": session_data["extraction_result"].to_dict()["stats"],
            "vector_store": vector_stats
        }
    
    def list_active_sessions(self) -> List[str]:
        """
        List all active session IDs.
        
        Returns:
            List of session IDs
        """
        return list(self.sessions.keys())
    
    async def health_check(self) -> Dict[str, str]:
        """
        Perform health check on all components.
        
        Returns:
            Health status of each component
        """
        health = {}
        
        # Check vector store
        try:
            collections = self.vector_store.list_collections()
            health["vector_store"] = "operational"
        except Exception as e:
            logger.error(f"Vector store health check failed: {str(e)}")
            health["vector_store"] = f"error: {str(e)}"
        
        # Check LLM
        try:
            test_response = await self.llm.ainvoke("test")
            health["llm"] = "operational"
        except Exception as e:
            logger.error(f"LLM health check failed: {str(e)}")
            health["llm"] = f"error: {str(e)}"
        
        # Check embeddings
        try:
            test_embedding = self.vector_store.embeddings.embed_query("test")
            health["embeddings"] = "operational"
        except Exception as e:
            logger.error(f"Embeddings health check failed: {str(e)}")
            health["embeddings"] = f"error: {str(e)}"
        
        return health


# Global RAG service instance
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """Get or create the global RAG service instance."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


def initialize_rag_service():
    """Initialize the RAG service at startup."""
    global _rag_service
    try:
        logger.info("Initializing RAG service...")
        _rag_service = RAGService()
        logger.info("RAG service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {str(e)}")
        raise
