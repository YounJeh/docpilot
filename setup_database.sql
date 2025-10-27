-- PostgreSQL setup script for DocPilot RAG system
-- Creates database, enables pgvector extension, and creates tables

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    source TEXT,
    uri TEXT,
    title TEXT,
    mime TEXT,
    content_hash TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Create chunks table with vector embeddings
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    doc_id INT REFERENCES documents(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    embedding VECTOR(768),  -- 768 dimensions for text-embedding-004
    chunk_metadata JSONB
);

-- Create HNSW index for vector similarity search
-- HNSW is recommended for pgvector >= 0.5
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx 
ON chunks USING hnsw (embedding vector_l2_ops)
WITH (m = 16, ef_construction = 64);

-- Alternative: IVFFlat index (if HNSW not available)
-- CREATE INDEX chunks_embedding_ivfflat_idx 
-- ON chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);

-- Create additional indexes for performance
CREATE INDEX IF NOT EXISTS documents_content_hash_idx ON documents(content_hash);
CREATE INDEX IF NOT EXISTS documents_source_idx ON documents(source);
CREATE INDEX IF NOT EXISTS chunks_doc_id_idx ON chunks(doc_id);

-- Verify setup
SELECT 'pgvector extension enabled' as status;
SELECT table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name IN ('documents', 'chunks') 
ORDER BY table_name, ordinal_position;