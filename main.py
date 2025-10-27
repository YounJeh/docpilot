"""
DocPilot - RAG System with Vertex AI Embeddings and pgvector
Jour 3: Embeddings & Index implementation
"""

import os
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from loguru import logger
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import RAG service
from knowledge_copilot.rag_service import create_rag_service

# Initialize FastAPI app
app = FastAPI(
    title="DocPilot RAG API",
    description="Document indexing and semantic search with Vertex AI embeddings and pgvector",
    version="1.0.0"
)

# Initialize RAG service
rag_service = None

@app.on_event("startup")
async def startup_event():
    """Initialize RAG service on startup"""
    global rag_service
    try:
        logger.info("Initializing DocPilot RAG service...")
        rag_service = create_rag_service()
        logger.info("DocPilot RAG service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {e}")
        raise


# Pydantic models for API requests/responses
class DocumentIndexRequest(BaseModel):
    content: str
    title: Optional[str] = None
    source: Optional[str] = "api"
    uri: Optional[str] = None
    mime: Optional[str] = "text/plain"
    metadata: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    similarity_threshold: Optional[float] = None
    source_filter: Optional[str] = None


class DocumentIndexResponse(BaseModel):
    document_id: int
    status: str
    message: str


class SearchResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    total_results: int
    search_metadata: Dict[str, Any]


# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "DocPilot RAG API",
        "version": "1.0.0",
        "description": "Document indexing and semantic search with Vertex AI embeddings and pgvector",
        "endpoints": {
            "index_document": "/index",
            "search": "/search", 
            "stats": "/stats",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        if rag_service is None:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
        
        stats = rag_service.get_stats()
        return {
            "status": "healthy",
            "service": "active",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.post("/index", response_model=DocumentIndexResponse)
async def index_document(request: DocumentIndexRequest):
    """
    Index a document for semantic search
    
    Args:
        request: Document indexing request
        
    Returns:
        Document ID and status
    """
    try:
        if rag_service is None:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
        
        logger.info(f"Indexing document: {request.title or 'Untitled'}")
        
        document_id = rag_service.index_document(
            content=request.content,
            title=request.title,
            source=request.source,
            uri=request.uri,
            mime=request.mime,
            metadata=request.metadata
        )
        
        return DocumentIndexResponse(
            document_id=document_id,
            status="success",
            message=f"Document indexed successfully with ID: {document_id}"
        )
        
    except Exception as e:
        logger.error(f"Error indexing document: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to index document: {str(e)}")


@app.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """
    Perform semantic search across indexed documents
    
    Args:
        request: Search request with query and parameters
        
    Returns:
        Search results with similarity scores
    """
    try:
        if rag_service is None:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
        
        logger.info(f"Searching for: '{request.query}'")
        
        results = rag_service.search(
            query=request.query,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            source_filter=request.source_filter
        )
        
        return SearchResponse(
            query=request.query,
            results=results,
            total_results=len(results),
            search_metadata={
                "limit": request.limit,
                "similarity_threshold": request.similarity_threshold,
                "source_filter": request.source_filter
            }
        )
        
    except Exception as e:
        logger.error(f"Error performing search: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/stats")
async def get_stats():
    """Get system statistics"""
    try:
        if rag_service is None:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
        
        stats = rag_service.get_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@app.delete("/documents/{document_id}")
async def delete_document(document_id: int):
    """Delete a document and all its chunks"""
    try:
        if rag_service is None:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
        
        success = rag_service.delete_document(document_id)
        
        if success:
            return {"message": f"Document {document_id} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and index a text file"""
    try:
        if rag_service is None:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
        
        # Read file content
        content = await file.read()
        
        # Decode content (assuming text file)
        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File must be valid UTF-8 text")
        
        # Index the document
        document_id = rag_service.index_document(
            content=text_content,
            title=file.filename,
            source="upload",
            uri=f"upload://{file.filename}",
            mime=file.content_type or "text/plain",
            metadata={
                "filename": file.filename,
                "size": len(content),
                "upload_method": "file_upload"
            }
        )
        
        return {
            "document_id": document_id,
            "filename": file.filename,
            "size": len(content),
            "status": "indexed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


@app.post("/batch-index")
async def batch_index_documents(documents: List[DocumentIndexRequest]):
    """Index multiple documents in batch"""
    try:
        if rag_service is None:
            raise HTTPException(status_code=503, detail="RAG service not initialized")
        
        # Convert requests to document dictionaries
        doc_dicts = [
            {
                "content": doc.content,
                "title": doc.title,
                "source": doc.source,
                "uri": doc.uri,
                "mime": doc.mime,
                "metadata": doc.metadata
            }
            for doc in documents
        ]
        
        document_ids = rag_service.batch_index_documents(doc_dicts)
        
        return {
            "total_documents": len(documents),
            "indexed_documents": len(document_ids),
            "document_ids": document_ids,
            "status": "completed"
        }
        
    except Exception as e:
        logger.error(f"Error in batch indexing: {e}")
        raise HTTPException(status_code=500, detail=f"Batch indexing failed: {str(e)}")


def main():
    """Main function to run the application"""
    import uvicorn
    
    # Configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    logger.info(f"Starting DocPilot RAG API on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
