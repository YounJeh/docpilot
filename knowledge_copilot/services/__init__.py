"""
Database service for document indexing and vector search using pgvector
"""

import os
import hashlib
from typing import List, Dict, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from loguru import logger

from ..models import Base, Document, Chunk
from ..utils.embeddings import VertexAIEmbeddings, create_embeddings_service
from ..utils.chunking import chunk_text


class DatabaseService:
    """Service for managing documents and vector search with pgvector"""
    
    def __init__(
        self,
        database_url: str,
        embeddings_service: Optional[VertexAIEmbeddings] = None
    ):
        """
        Initialize database service
        
        Args:
            database_url: PostgreSQL connection URL
            embeddings_service: Optional embeddings service instance
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Initialize embeddings service
        self.embeddings_service = embeddings_service or create_embeddings_service()
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize database with tables and pgvector extension"""
        try:
            with self.engine.connect() as conn:
                # Enable pgvector extension
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
                logger.info("Enabled pgvector extension")
            
            # Create tables
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created/verified")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def _calculate_content_hash(self, content: str) -> str:
        """Calculate SHA256 hash of content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def index_document(
        self,
        content: str,
        source: Optional[str] = None,
        uri: Optional[str] = None,
        title: Optional[str] = None,
        mime: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> int:
        """
        Index a document with its chunks and embeddings
        
        Args:
            content: Document text content
            source: Document source (e.g., "github", "gdrive")
            uri: Document URI/identifier
            title: Document title
            mime: MIME type
            metadata: Additional metadata
        
        Returns:
            Document ID
        """
        content_hash = self._calculate_content_hash(content)
        
        with self.SessionLocal() as db:
            try:
                # Check if document already exists
                existing_doc = db.query(Document).filter(
                    Document.content_hash == content_hash
                ).first()
                
                if existing_doc:
                    logger.info(f"Document already indexed: {existing_doc.id}")
                    return existing_doc.id
                
                # Create new document
                document = Document(
                    source=source,
                    uri=uri,
                    title=title,
                    mime=mime,
                    content_hash=content_hash
                )
                
                db.add(document)
                db.flush()  # Get the document ID
                
                # Chunk the document
                chunks = chunk_text(content)
                logger.info(f"Split document into {len(chunks)} chunks")
                
                # Process chunks in batches for efficiency
                batch_size = 10
                for i in range(0, len(chunks), batch_size):
                    batch_chunks = chunks[i:i + batch_size]
                    batch_texts = [chunk['text'] for chunk in batch_chunks]
                    
                    # Generate embeddings for batch
                    embeddings = self.embeddings_service.get_embeddings(batch_texts)
                    
                    # Create chunk objects
                    for j, chunk_data in enumerate(batch_chunks):
                        chunk_metadata = {
                            **(metadata or {}),
                            **chunk_data.get('metadata', {}),
                            'chunk_index': chunk_data.get('index', i + j)
                        }
                        
                        chunk = Chunk(
                            doc_id=document.id,
                            text=chunk_data['text'],
                            embedding=embeddings[j],
                            chunk_metadata=chunk_metadata
                        )
                        db.add(chunk)
                
                db.commit()
                logger.info(f"Successfully indexed document {document.id} with {len(chunks)} chunks")
                return document.id
                
            except IntegrityError as e:
                db.rollback()
                logger.error(f"Document already exists: {e}")
                raise
            except Exception as e:
                db.rollback()
                logger.error(f"Error indexing document: {e}")
                raise
    
    def search(
        self,
        query: str,
        limit: int = 10,
        similarity_threshold: Optional[float] = None
    ) -> List[Dict]:
        """
        Perform semantic search using vector similarity
        
        Args:
            query: Search query text
            limit: Maximum number of results
            similarity_threshold: Optional similarity threshold
        
        Returns:
            List of search results with metadata
        """
        try:
            # Generate embedding for query
            query_embedding = self.embeddings_service.get_embedding(query)
            
            # Convert embedding to string format for pgvector
            embedding_str = f"[{','.join(map(str, query_embedding))}]"
            
            with self.SessionLocal() as db:
                # Build search query with vector similarity using formatted string
                sql_query = f"""
                    SELECT 
                        c.id,
                        c.text,
                        c.chunk_metadata,
                        d.source,
                        d.uri,
                        d.title,
                        d.mime,
                        (c.embedding <-> '{embedding_str}'::vector) as distance
                    FROM chunks c
                    JOIN documents d ON c.doc_id = d.id
                    ORDER BY c.embedding <-> '{embedding_str}'::vector
                    LIMIT {limit}
                """
                
                # Execute search
                results = db.execute(text(sql_query)).fetchall()
                
                # Format results
                search_results = []
                for row in results:
                    # Skip results above similarity threshold if specified
                    if similarity_threshold and row.distance > similarity_threshold:
                        continue
                    
                    result = {
                        "chunk_id": row.id,
                        "text": row.text,
                        "metadata": row.chunk_metadata or {},
                        "document": {
                            "source": row.source,
                            "uri": row.uri,
                            "title": row.title,
                            "mime": row.mime
                        },
                        "similarity_score": 1.0 - row.distance,  # Convert distance to similarity
                        "distance": row.distance
                    }
                    search_results.append(result)
                
                logger.info(f"Found {len(search_results)} results for query: '{query[:50]}...'")
                return search_results
                
        except Exception as e:
            logger.error(f"Error performing search: {e}")
            raise
    
    def get_document_stats(self) -> Dict:
        """Get database statistics"""
        with self.SessionLocal() as db:
            doc_count = db.query(Document).count()
            chunk_count = db.query(Chunk).count()
            
            return {
                "documents": doc_count,
                "chunks": chunk_count
            }
    
    def delete_document(self, document_id: int) -> bool:
        """
        Delete a document and all its chunks
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            True if deleted, False if not found
        """
        with self.SessionLocal() as db:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                return False
            
            db.delete(document)  # Cascading delete will remove chunks
            db.commit()
            logger.info(f"Deleted document {document_id}")
            return True


def create_database_service(
    database_url: Optional[str] = None,
    embeddings_service: Optional[VertexAIEmbeddings] = None
) -> DatabaseService:
    """
    Factory function to create database service with environment variables
    
    Args:
        database_url: PostgreSQL connection URL
        embeddings_service: Optional embeddings service instance
    
    Returns:
        Configured DatabaseService instance
    """
    if not database_url:
        # Priorité à DATABASE_URL pour connexion locale
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            # Build database URL from environment variables
            sql_instance = os.getenv("SQL_INSTANCE")
            sql_db = os.getenv("SQL_DB", "kcdb")
            sql_user = os.getenv("SQL_USER", "postgres")
            sql_password = os.getenv("SQL_PASSWORD")
            
            if sql_instance and sql_password:
                # Cloud SQL format
                database_url = f"postgresql://{sql_user}:{sql_password}@/{sql_db}?host=/cloudsql/{sql_instance}"
            else:
                # Local PostgreSQL
                host = os.getenv("DB_HOST", "localhost")
                port = os.getenv("DB_PORT", "5432")
                database_url = f"postgresql://{sql_user}:{sql_password}@{host}:{port}/{sql_db}"
    
    return DatabaseService(
        database_url=database_url,
        embeddings_service=embeddings_service
    )