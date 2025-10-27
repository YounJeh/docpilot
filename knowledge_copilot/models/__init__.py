"""
SQLAlchemy models for documents and chunks with pgvector support
"""

from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

Base = declarative_base()


class Document(Base):
    """Document model for storing document metadata"""
    
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(Text, nullable=True)  # e.g., "github", "gdrive", etc.
    uri = Column(Text, nullable=True)     # unique identifier for the document
    title = Column(Text, nullable=True)   # document title/name
    mime = Column(Text, nullable=True)    # MIME type
    content_hash = Column(Text, unique=True, nullable=False)  # SHA256 hash of content
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationship to chunks
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document(id={self.id}, title='{self.title}', source='{self.source}')>"


class Chunk(Base):
    """Chunk model for storing text chunks with embeddings"""
    
    __tablename__ = "chunks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)   # chunk text content
    
    # Vector embedding - adjust dimension based on model
    # text-embedding-004 uses 768 dimensions
    embedding = Column(Vector(768), nullable=True)
    
    # Metadata as JSON
    chunk_metadata = Column(JSONB, nullable=True)
    
    # Relationship to document
    document = relationship("Document", back_populates="chunks")
    
    def __repr__(self):
        return f"<Chunk(id={self.id}, doc_id={self.doc_id}, text_preview='{self.text[:50]}...')>"


# Index for HNSW vector similarity search
# HNSW is recommended for pgvector >= 0.5
vector_index = Index(
    "chunks_embedding_hnsw_idx",
    Chunk.embedding,
    postgresql_using="hnsw",
    postgresql_with={"m": 16, "ef_construction": 64},
    postgresql_ops={"embedding": "vector_l2_ops"}
)