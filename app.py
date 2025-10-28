"""
MCP Server with FastAPI for Knowledge Copilot
Provides MCP endpoints, sync capabilities and webhook support
"""

import os
import json
import hashlib
import hmac
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from loguru import logger

from knowledge_copilot.rag_service import create_rag_service
from knowledge_copilot.connectors.github_sync import sync_github
from knowledge_copilot.connectors.gdrive_sync import sync_drive


# Environment variables
API_TOKEN = os.getenv("API_TOKEN", "")
GH_WEBHOOK_SECRET = os.getenv("GH_WEBHOOK_SECRET", "")
PROJECT_ID = os.getenv("PROJECT_ID", "")

# Build DATABASE_URL with password from secret
SQL_PASSWORD = os.getenv("SQL_PASSWORD", "")
SQL_INSTANCE = os.getenv("SQL_INSTANCE", "kc-postgres")
SQL_DB = os.getenv("SQL_DB", "kcdb") 
SQL_USER = os.getenv("SQL_USER", "postgres")

# Build the database URL with the secret password
if SQL_PASSWORD:
    DATABASE_URL = f"postgresql://{SQL_USER}:{SQL_PASSWORD}@/{SQL_DB}?host=/cloudsql/{PROJECT_ID}:europe-west1:{SQL_INSTANCE}"
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "")

# MCP Service state
rag_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup"""
    global rag_service
    logger.info("Initializing MCP server...")
    
    try:
        rag_service = create_rag_service(
            database_url=DATABASE_URL,
            project_id=PROJECT_ID
        )
        logger.info("RAG service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG service: {e}")
        raise
    
    yield
    
    logger.info("MCP server shutting down...")

# FastAPI app
app = FastAPI(
    title="Knowledge Copilot MCP Server",
    description="MCP server providing document search and sync capabilities",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer(auto_error=False)

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key from Authorization header or X-API-KEY header"""
    if not API_TOKEN:
        return True  # No auth required if not configured
    
    if credentials and credentials.credentials == API_TOKEN:
        return True
    
    raise HTTPException(
        status_code=401,
        detail="Invalid or missing API key"
    )

async def verify_api_key_header(request: Request):
    """Verify API key from X-API-KEY header"""
    if not API_TOKEN:
        return True
    
    api_key = request.headers.get("X-API-KEY")
    if api_key != API_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-API-KEY header"
        )
    return True

def verify_github_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature"""
    if not GH_WEBHOOK_SECRET:
        return True  # No verification if secret not configured
    
    expected_signature = "sha256=" + hmac.new(
        GH_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

# Pydantic models
class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query text")
    limit: Optional[int] = Field(10, ge=1, le=100, description="Maximum number of results")
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum similarity score")
    source_filter: Optional[str] = Field(None, description="Filter by document source")

class SearchResult(BaseModel):
    id: int
    similarity_score: float
    content: str
    metadata: Dict[str, Any]
    document: Dict[str, Any]

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int
    search_metadata: Dict[str, Any]

class DocumentInfo(BaseModel):
    id: int
    title: str
    source: str
    uri: str
    mime_type: str
    metadata: Dict[str, Any]

class ListDocumentsResponse(BaseModel):
    documents: List[DocumentInfo]
    total_count: int
    page: int
    page_size: int

class SyncResponse(BaseModel):
    status: str
    message: str
    github_result: Optional[Dict[str, Any]] = None
    gdrive_result: Optional[Dict[str, Any]] = None
    indexed_documents: int = 0

class MCPTool(BaseModel):
    name: str
    description: str
    inputSchema: Dict[str, Any]

class MCPToolsResponse(BaseModel):
    tools: List[MCPTool]

# MCP Endpoints

@app.get("/mcp/tools", response_model=MCPToolsResponse)
async def get_mcp_tools(_: bool = Depends(verify_api_key)):
    """Get MCP tools description"""
    tools = [
        {
            "name": "search_documents",
            "description": "Search documents using semantic similarity",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (1-100)",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 10
                    },
                    "similarity_threshold": {
                        "type": "number",
                        "description": "Minimum similarity score (0.0-1.0)",
                        "minimum": 0.0,
                        "maximum": 1.0
                    },
                    "source_filter": {
                        "type": "string",
                        "description": "Filter by document source (github, gdrive, upload)"
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "list_documents",
            "description": "List all indexed documents with metadata",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "page": {
                        "type": "integer",
                        "description": "Page number (1-based)",
                        "minimum": 1,
                        "default": 1
                    },
                    "page_size": {
                        "type": "integer", 
                        "description": "Number of documents per page (1-100)",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20
                    },
                    "source_filter": {
                        "type": "string",
                        "description": "Filter by document source"
                    }
                }
            }
        },
        {
            "name": "sync_sources",
            "description": "Sync documents from GitHub and Google Drive",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "github_only": {
                        "type": "boolean",
                        "description": "Sync only GitHub repositories",
                        "default": False
                    },
                    "gdrive_only": {
                        "type": "boolean", 
                        "description": "Sync only Google Drive",
                        "default": False
                    }
                }
            }
        }
    ]
    
    return MCPToolsResponse(tools=tools)

@app.post("/mcp/search_documents", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    _: bool = Depends(verify_api_key)
):
    """Search documents using semantic similarity"""
    try:
        if not rag_service:
            raise HTTPException(status_code=503, detail="RAG service not available")
        
        results = rag_service.search(
            query=request.query,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
            source_filter=request.source_filter
        )
        
        # Transform results to match response model
        search_results = []
        for result in results:
            search_results.append(SearchResult(
                id=result.get("chunk_id", 0),
                similarity_score=result.get("similarity_score", 0.0),
                content=result.get("content", ""),
                metadata=result.get("metadata", {}),
                document=result.get("document", {})
            ))
        
        return SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results),
            search_metadata={
                "similarity_threshold": request.similarity_threshold,
                "source_filter": request.source_filter,
                "limit": request.limit
            }
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/mcp/list_documents", response_model=ListDocumentsResponse) 
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    source_filter: Optional[str] = None,
    _: bool = Depends(verify_api_key)
):
    """List all indexed documents with pagination"""
    try:
        if not rag_service:
            raise HTTPException(status_code=503, detail="RAG service not available")
        
        # Get stats to estimate total count
        stats = rag_service.get_stats()
        total_count = stats.get("documents_count", 0)
        
        # For now, return mock data since we need to implement document listing in RAG service
        # In real implementation, you'd add a list_documents method to RAG service
        documents = []
        
        return ListDocumentsResponse(
            documents=documents,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
        
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")

@app.post("/sync_sources", response_model=SyncResponse)
async def sync_sources(
    background_tasks: BackgroundTasks,
    github_only: bool = False,
    gdrive_only: bool = False,
    _: bool = Depends(verify_api_key_header)
):
    """Sync documents from GitHub and Google Drive"""
    try:
        if not rag_service:
            raise HTTPException(status_code=503, detail="RAG service not available")
        
        def sync_task():
            """Background task for syncing sources"""
            github_result = None
            gdrive_result = None
            indexed_count = 0
            
            try:
                # Sync GitHub if not gdrive_only
                if not gdrive_only:
                    logger.info("Starting GitHub sync...")
                    github_result = sync_github()
                    
                    # Index GitHub documents
                    if github_result and github_result.get("documents"):
                        for doc in github_result["documents"]:
                            try:
                                rag_service.index_document(
                                    content=doc["raw_text"],
                                    source=doc["source"],
                                    uri=doc["uri"],
                                    title=doc["title"],
                                    mime=doc["mime"],
                                    metadata=doc["metadata"]
                                )
                                indexed_count += 1
                            except Exception as e:
                                logger.error(f"Failed to index GitHub doc {doc.get('title', 'unknown')}: {e}")
                
                # Sync Google Drive if not github_only
                if not github_only:
                    logger.info("Starting Google Drive sync...")
                    gdrive_result = sync_drive()
                    
                    # Index Google Drive documents  
                    if gdrive_result and gdrive_result.get("documents"):
                        for doc in gdrive_result["documents"]:
                            try:
                                rag_service.index_document(
                                    content=doc["raw_text"],
                                    source=doc["source"],
                                    uri=doc["uri"],
                                    title=doc["title"],
                                    mime=doc["mime"],
                                    metadata=doc["metadata"]
                                )
                                indexed_count += 1
                            except Exception as e:
                                logger.error(f"Failed to index GDrive doc {doc.get('title', 'unknown')}: {e}")
                
                logger.info(f"Sync completed successfully. Indexed {indexed_count} documents.")
                
            except Exception as e:
                logger.error(f"Sync task failed: {e}")
        
        # Run sync in background
        background_tasks.add_task(sync_task)
        
        return SyncResponse(
            status="started",
            message="Sync process started in background",
            indexed_documents=0
        )
        
    except Exception as e:
        logger.error(f"Sync sources error: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")

@app.post("/webhook/github")
async def github_webhook(request: Request):
    """GitHub webhook endpoint for automatic reindexing"""
    try:
        # Get raw body and signature
        body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")
        
        # Verify signature
        if not verify_github_signature(body, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse webhook payload
        try:
            payload = json.loads(body.decode())
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Handle push events
        event_type = request.headers.get("X-GitHub-Event", "")
        if event_type == "push":
            repo_full_name = payload.get("repository", {}).get("full_name", "")
            ref = payload.get("ref", "")
            
            logger.info(f"GitHub push webhook: {repo_full_name} @ {ref}")
            
            # Trigger resync for this repo (simplified - in production you'd be more selective)
            if rag_service:
                try:
                    # Sync just this repository
                    result = sync_github(repos=[repo_full_name])
                    
                    # Reindex documents (you might want to delete old ones first)
                    indexed_count = 0
                    for doc in result.get("documents", []):
                        rag_service.index_document(
                            content=doc["raw_text"],
                            source=doc["source"],
                            uri=doc["uri"], 
                            title=doc["title"],
                            mime=doc["mime"],
                            metadata=doc["metadata"]
                        )
                        indexed_count += 1
                    
                    logger.info(f"Webhook reindex completed: {indexed_count} documents")
                    
                except Exception as e:
                    logger.error(f"Webhook reindex failed: {e}")
        
        return {"status": "received", "event": event_type}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    status = {
        "status": "healthy",
        "rag_service": rag_service is not None,
        "project_id": PROJECT_ID or "not_configured",
        "auth_enabled": bool(API_TOKEN)
    }
    
    if rag_service:
        try:
            stats = rag_service.get_stats()
            status["document_stats"] = stats
        except Exception as e:
            status["rag_service_error"] = str(e)
    
    return status

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Knowledge Copilot MCP Server",
        "version": "1.0.0",
        "endpoints": {
            "mcp_tools": "/mcp/tools",
            "search": "/mcp/search_documents", 
            "list_docs": "/mcp/list_documents",
            "sync": "/sync_sources",
            "webhook": "/webhook/github",
            "health": "/health"
        },
        "authentication": "X-API-KEY header required" if API_TOKEN else "No authentication required"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)