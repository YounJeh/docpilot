"""
RAG (Retrieval-Augmented Generation) service
Integrates document indexing and semantic search
"""

from typing import List, Dict, Optional, Any
from loguru import logger

from .services import DatabaseService, create_database_service
from .utils.embeddings import VertexAIEmbeddings, create_embeddings_service


class RAGService:
    """
    RAG service that provides document indexing and semantic search capabilities
    """
    
    def __init__(
        self,
        database_service: Optional[DatabaseService] = None,
        embeddings_service: Optional[VertexAIEmbeddings] = None
    ):
        """
        Initialize RAG service
        
        Args:
            database_service: Optional database service instance
            embeddings_service: Optional embeddings service instance
        """
        self.embeddings_service = embeddings_service or create_embeddings_service()
        self.database_service = database_service or create_database_service(
            embeddings_service=self.embeddings_service
        )
        
        logger.info("RAG service initialized")
    
    def index_document(
        self,
        content: str,
        source: Optional[str] = None,
        uri: Optional[str] = None,
        title: Optional[str] = None,
        mime: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Index a document for semantic search
        
        Args:
            content: Document text content
            source: Document source (e.g., "github", "gdrive", "upload")
            uri: Document URI/identifier
            title: Document title
            mime: MIME type
            metadata: Additional metadata
        
        Returns:
            Document ID
        """
        try:
            logger.info(f"Indexing document: {title or uri or 'Untitled'}")
            
            # Add source info to metadata
            doc_metadata = {
                **(metadata or {}),
                "indexed_by": "rag_service",
                "embedding_model": self.embeddings_service.model_name,
                "embedding_dimension": self.embeddings_service.get_embedding_dimension()
            }
            
            document_id = self.database_service.index_document(
                content=content,
                source=source,
                uri=uri,
                title=title,
                mime=mime,
                metadata=doc_metadata
            )
            
            logger.info(f"Successfully indexed document with ID: {document_id}")
            return document_id
            
        except Exception as e:
            logger.error(f"Error indexing document: {e}")
            raise
    
    def search(
        self,
        query: str,
        limit: int = 10,
        similarity_threshold: Optional[float] = None,
        source_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search across indexed documents
        
        Args:
            query: Search query text
            limit: Maximum number of results
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
            source_filter: Optional filter by document source
        
        Returns:
            List of search results with similarity scores and metadata
        """
        try:
            logger.info(f"Searching for: '{query}' (limit: {limit})")
            
            # Perform vector search
            results = self.database_service.search(
                query=query,
                limit=limit,
                similarity_threshold=similarity_threshold
            )
            
            # Apply source filter if specified
            if source_filter:
                results = [
                    result for result in results
                    if result.get("document", {}).get("source") == source_filter
                ]
            
            # Add query context to results
            for result in results:
                result["query"] = query
                result["search_metadata"] = {
                    "similarity_threshold": similarity_threshold,
                    "source_filter": source_filter,
                    "total_results": len(results)
                }
            
            logger.info(f"Found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            raise
    
    def get_document_by_id(self, document_id: int) -> Optional[Dict[str, Any]]:
        """
        Get document metadata by ID
        
        Args:
            document_id: Document ID
            
        Returns:
            Document metadata or None if not found
        """
        try:
            # This would require a method in DatabaseService to get document by ID
            # For now, we'll return basic info
            return {"id": document_id, "status": "found"}
            
        except Exception as e:
            logger.error(f"Error getting document {document_id}: {e}")
            return None
    
    def delete_document(self, document_id: int) -> bool:
        """
        Delete a document and all its chunks
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        try:
            result = self.database_service.delete_document(document_id)
            if result:
                logger.info(f"Deleted document {document_id}")
            else:
                logger.warning(f"Document {document_id} not found")
            return result
            
        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about indexed documents
        
        Returns:
            Statistics dictionary
        """
        try:
            db_stats = self.database_service.get_document_stats()
            
            stats = {
                **db_stats,
                "embedding_model": self.embeddings_service.model_name,
                "embedding_dimension": self.embeddings_service.get_embedding_dimension(),
                "service_status": "active"
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}
    
    def batch_index_documents(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 5
    ) -> List[int]:
        """
        Index multiple documents in batches
        
        Args:
            documents: List of document dictionaries with 'content' and optional metadata
            batch_size: Number of documents to process in each batch
            
        Returns:
            List of document IDs
        """
        document_ids = []
        
        for i in range(0, len(documents), batch_size):
            batch = documents[i:i + batch_size]
            
            logger.info(f"Processing batch {i // batch_size + 1}: {len(batch)} documents")
            
            for doc in batch:
                try:
                    doc_id = self.index_document(
                        content=doc["content"],
                        source=doc.get("source"),
                        uri=doc.get("uri"),
                        title=doc.get("title"),
                        mime=doc.get("mime"),
                        metadata=doc.get("metadata")
                    )
                    document_ids.append(doc_id)
                    
                except Exception as e:
                    logger.error(f"Error indexing document in batch: {e}")
                    # Continue with next document
                    continue
        
        logger.info(f"Batch indexing completed: {len(document_ids)} documents indexed")
        return document_ids


def create_rag_service(
    database_url: Optional[str] = None,
    project_id: Optional[str] = None,
    region: Optional[str] = None
) -> RAGService:
    """
    Factory function to create RAG service with default configuration
    
    Args:
        database_url: PostgreSQL connection URL
        project_id: GCP project ID
        region: GCP region
        
    Returns:
        Configured RAGService instance
    """
    embeddings_service = create_embeddings_service(
        project_id=project_id,
        region=region
    )
    
    database_service = create_database_service(
        database_url=database_url,
        embeddings_service=embeddings_service
    )
    
    return RAGService(
        database_service=database_service,
        embeddings_service=embeddings_service
    )