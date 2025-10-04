"""
Vector store management using ChromaDB.
Handles document embedding, storage, and retrieval.
"""
from typing import List, Dict, Any, Optional
import uuid
from pathlib import Path
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from app.core.logging import get_logger
from app.core.exceptions import VectorStoreError, EmbeddingError
from app.config.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class VectorStore:
    """
    ChromaDB-based vector store for document embeddings.
    
    Features:
    - Persistent storage
    - Collection management per session
    - Efficient similarity search
    - Metadata filtering
    """
    
    def __init__(self, persist_directory: Optional[str] = None):
        """
        Initialize ChromaDB vector store.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = persist_directory or settings.chroma_persist_directory
        
        # Create persist directory
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
        
        try:
            # Initialize ChromaDB client with persistence
            self.client = chromadb.Client(ChromaSettings(
                persist_directory=self.persist_directory,
                anonymized_telemetry=False
            ))
            
            # Initialize OpenAI embeddings
            self.embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
                openai_api_key=settings.openai_api_key
            )
            
            # Initialize text splitter
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
            )
            
            logger.info(f"ChromaDB initialized at {self.persist_directory}")
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {str(e)}")
            raise VectorStoreError(
                f"Failed to initialize vector store: {str(e)}",
                operation="initialization"
            )
    
    def get_or_create_collection(self, session_id: str) -> chromadb.Collection:
        """
        Get or create a collection for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            ChromaDB collection
        """
        try:
            # Collection name must be alphanumeric + underscores/hyphens
            collection_name = f"session_{session_id.replace('-', '_')}"
            
            collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"session_id": session_id}
            )
            
            logger.debug(f"Collection {collection_name} ready")
            return collection
            
        except Exception as e:
            logger.error(f"Failed to get/create collection: {str(e)}")
            raise VectorStoreError(
                f"Failed to access collection for session {session_id}: {str(e)}",
                operation="get_or_create_collection"
            )
    
    def delete_collection(self, session_id: str) -> bool:
        """
        Delete a collection for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        try:
            collection_name = f"session_{session_id.replace('-', '_')}"
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection {collection_name}")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to delete collection: {str(e)}")
            return False
    
    async def add_documents(
        self,
        session_id: str,
        documents: List[Document],
        batch_size: int = 100
    ) -> int:
        """
        Add documents to the vector store.
        
        Args:
            session_id: Session identifier
            documents: List of documents to add
            batch_size: Number of documents to process in each batch
            
        Returns:
            Number of documents added
        """
        if not documents:
            logger.warning("No documents to add")
            return 0
        
        try:
            collection = self.get_or_create_collection(session_id)
            
            # Split documents into chunks
            splits = self.text_splitter.split_documents(documents)
            logger.info(f"Split {len(documents)} documents into {len(splits)} chunks")
            
            # Process in batches
            total_added = 0
            for i in range(0, len(splits), batch_size):
                batch = splits[i:i + batch_size]
                
                # Prepare data for ChromaDB
                texts = [doc.page_content for doc in batch]
                metadatas = [doc.metadata for doc in batch]
                ids = [str(uuid.uuid4()) for _ in batch]
                
                # Generate embeddings
                try:
                    embeddings = self.embeddings.embed_documents(texts)
                except Exception as e:
                    logger.error(f"Failed to generate embeddings: {str(e)}")
                    raise EmbeddingError(f"Failed to generate embeddings: {str(e)}")
                
                # Add to collection
                collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas
                )
                
                total_added += len(batch)
                logger.debug(f"Added batch {i // batch_size + 1}: {len(batch)} chunks")
            
            logger.info(f"Added {total_added} chunks to collection {session_id}")
            return total_added
            
        except EmbeddingError:
            raise
        except Exception as e:
            logger.error(f"Failed to add documents: {str(e)}")
            raise VectorStoreError(
                f"Failed to add documents: {str(e)}",
                operation="add_documents"
            )
    
    async def similarity_search(
        self,
        session_id: str,
        query: str,
        k: int = 4,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform similarity search in the vector store.
        
        Args:
            session_id: Session identifier
            query: Search query
            k: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of search results with content and metadata
        """
        try:
            collection = self.get_or_create_collection(session_id)
            
            # Generate query embedding
            try:
                query_embedding = self.embeddings.embed_query(query)
            except Exception as e:
                logger.error(f"Failed to embed query: {str(e)}")
                raise EmbeddingError(f"Failed to embed query: {str(e)}")
            
            # Perform search
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                where=filter_metadata
            )
            
            # Format results
            formatted_results = []
            if results['documents'] and len(results['documents']) > 0:
                for i in range(len(results['documents'][0])):
                    formatted_results.append({
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': results['distances'][0][i] if results['distances'] else None
                    })
            
            logger.info(f"Found {len(formatted_results)} results for query")
            return formatted_results
            
        except EmbeddingError:
            raise
        except Exception as e:
            logger.error(f"Similarity search failed: {str(e)}")
            raise VectorStoreError(
                f"Similarity search failed: {str(e)}",
                operation="similarity_search"
            )
    
    def get_collection_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Get statistics for a collection.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Collection statistics
        """
        try:
            collection = self.get_or_create_collection(session_id)
            count = collection.count()
            
            return {
                "session_id": session_id,
                "document_count": count,
                "collection_name": collection.name
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {str(e)}")
            return {
                "session_id": session_id,
                "document_count": 0,
                "error": str(e)
            }
    
    def list_collections(self) -> List[str]:
        """
        List all collections in the vector store.
        
        Returns:
            List of collection names
        """
        try:
            collections = self.client.list_collections()
            return [col.name for col in collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {str(e)}")
            return []