"""
DocPilot Agent - RAG-powered conversational agent
Jour 5: Agent + CLI/mini-UI & Qualité
"""

import os
import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import httpx
import openai
from google.cloud import aiplatform
from loguru import logger

from .observability import ObservabilityMixin


@dataclass
class AgentResponse:
    """Agent response with metadata"""
    answer: str
    sources: List[Dict[str, Any]]
    trace_id: str
    response_time: float
    chunks_scanned: int
    confidence: Optional[float] = None
    fallback_used: bool = False


@dataclass
class SearchFilter:
    """Search filters for the MCP service"""
    source: Optional[str] = None  # github|gdrive
    repo: Optional[str] = None
    mime: Optional[str] = None
    top_k: int = 10
    similarity_threshold: float = 0.7


class MCPClient:
    """Client for MCP service communication"""
    
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def search_documents(
        self, 
        query: str, 
        filters: SearchFilter
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Search documents via MCP service"""
        search_payload = {
            "query": query,
            "limit": filters.top_k,
            "similarity_threshold": filters.similarity_threshold
        }
        
        if filters.source:
            search_payload["source_filter"] = filters.source
        
        try:
            response = await self.client.post(
                f"{self.base_url}/search",
                json=search_payload
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("results", []), data.get("search_metadata", {})
            
        except httpx.RequestError as e:
            logger.error(f"MCP request error: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"MCP HTTP error: {e.response.status_code} - {e.response.text}")
            raise
    
    async def get_health(self) -> Dict[str, Any]:
        """Check MCP service health"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


class LLMProvider:
    """Abstract LLM provider interface"""
    
    async def generate_response(
        self, 
        prompt: str, 
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> str:
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider"""
    
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.model = model
    
    async def generate_response(
        self, 
        prompt: str, 
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un assistant expert qui répond uniquement en utilisant le contexte fourni. Si le contexte ne contient pas d'informations pertinentes, réponds 'Je ne trouve pas d'informations pertinentes dans la documentation pour répondre à cette question.'"
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise


class VertexAIProvider(LLMProvider):
    """Vertex AI LLM provider"""
    
    def __init__(self, project_id: str, location: str = "us-central1", model: str = "gemini-1.5-flash"):
        aiplatform.init(project=project_id, location=location)
        self.model_name = model
        self.project_id = project_id
        self.location = location
    
    async def generate_response(
        self, 
        prompt: str, 
        max_tokens: int = 1000,
        temperature: float = 0.1
    ) -> str:
        try:
            from vertexai.generative_models import GenerativeModel, GenerationConfig
            
            model = GenerativeModel(self.model_name)
            
            generation_config = GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature
            )
            
            system_instruction = """Tu es un assistant expert qui répond uniquement en utilisant le contexte fourni. 
Si le contexte ne contient pas d'informations pertinentes, réponds exactement: 
'Je ne trouve pas d'informations pertinentes dans la documentation pour répondre à cette question.'

Format tes réponses avec des citations claires des sources."""
            
            full_prompt = f"{system_instruction}\n\n{prompt}"
            
            response = await model.generate_content_async(
                full_prompt,
                generation_config=generation_config
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Vertex AI error: {e}")
            raise


class DocPilotAgent(ObservabilityMixin):
    """Main agent class for DocPilot"""
    
    def __init__(
        self,
        mcp_url: str,
        llm_provider: LLMProvider,
        min_context_chunks: int = 2,
        max_context_length: int = 8000
    ):
        super().__init__()
        self.mcp_client = MCPClient(mcp_url)
        self.llm_provider = llm_provider
        self.llm_provider_name = getattr(llm_provider, '__class__.__name__', 'unknown')
        self.min_context_chunks = min_context_chunks
        self.max_context_length = max_context_length
    
    def _build_rag_prompt(
        self, 
        question: str, 
        search_results: List[Dict[str, Any]]
    ) -> str:
        """Build RAG prompt with context and question"""
        
        # Build context from search results
        context_parts = []
        total_length = 0
        
        for i, result in enumerate(search_results):
            # Extract chunk content and metadata
            content = result.get("content", "")
            metadata = result.get("metadata", {})
            title = metadata.get("title", "")
            uri = metadata.get("uri", "")
            similarity = result.get("similarity_score", 0.0)
            
            # Format source info
            source_info = f"[Source {i+1}]"
            if title:
                source_info += f" {title}"
            if uri:
                source_info += f" ({uri})"
            source_info += f" - Similarité: {similarity:.3f}"
            
            chunk_text = f"{source_info}\n{content}\n"
            
            # Check length limit
            if total_length + len(chunk_text) > self.max_context_length:
                break
                
            context_parts.append(chunk_text)
            total_length += len(chunk_text)
        
        context = "\n---\n".join(context_parts)
        
        # Build the complete prompt
        prompt = f"""Contexte documentaire:
{context}

Question: {question}

Instructions:
- Réponds uniquement en utilisant les informations du contexte fourni ci-dessus
- Cite explicitement les sources en mentionnant [Source X] dans ta réponse
- Si le contexte ne contient pas d'informations suffisantes, réponds: "Je ne trouve pas d'informations pertinentes dans la documentation pour répondre à cette question."
- Sois précis et factuel
- Structure ta réponse clairement

Réponse:"""
        
        return prompt
    
    def _extract_sources(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract and format source information"""
        sources = []
        
        for i, result in enumerate(search_results):
            metadata = result.get("metadata", {})
            source_info = {
                "index": i + 1,
                "title": metadata.get("title", "Document sans titre"),
                "source": metadata.get("source", "unknown"),
                "uri": metadata.get("uri", ""),
                "repo": metadata.get("repo", ""),
                "path": metadata.get("path", ""),
                "mime": metadata.get("mime", ""),
                "similarity_score": result.get("similarity_score", 0.0),
                "chunk_id": result.get("chunk_id", "")
            }
            sources.append(source_info)
        
        return sources
    
    async def ask(
        self, 
        question: str, 
        filters: Optional[SearchFilter] = None
    ) -> AgentResponse:
        """Main method to ask a question and get an AI response with observability"""
        
        # Generate trace ID for this request
        trace_id = str(uuid.uuid4())
        
        # Use default filters if none provided
        if filters is None:
            filters = SearchFilter()
        
        # Start request logging
        timing_context = self._start_request_logging(trace_id, question, filters)
        
        logger.info(f"[{trace_id}] Processing question: {question}")
        
        try:
            # Search for relevant documents
            timing_context["search_start"] = time.time()
            search_results, search_metadata = await self.mcp_client.search_documents(
                question, filters
            )
            search_time = self._log_search_timing(trace_id, timing_context, len(search_results))
            
            chunks_scanned = len(search_results)
            logger.info(f"[{trace_id}] Found {chunks_scanned} relevant chunks in {search_time:.3f}s")
            
            # Check if we have enough context
            if chunks_scanned < self.min_context_chunks:
                logger.warning(f"[{trace_id}] Insufficient context: {chunks_scanned} chunks < {self.min_context_chunks} minimum")
                
                response = AgentResponse(
                    answer="Je ne trouve pas suffisamment d'informations pertinentes dans la documentation pour répondre à cette question.",
                    sources=[],
                    trace_id=trace_id,
                    response_time=0.0,  # Will be set in complete_request_logging
                    chunks_scanned=chunks_scanned,
                    fallback_used=True
                )
                
                # Complete logging
                self._complete_request_logging(
                    trace_id, timing_context, question, filters, response, 
                    search_time, 0.0
                )
                
                response.response_time = (timing_context.get("start_time", 0.0) or 0.0) and (time.time() - (timing_context.get("start_time", 0.0) or 0.0)) or 0.0
                return response
            
            # Build RAG prompt
            prompt = self._build_rag_prompt(question, search_results)
            logger.debug(f"[{trace_id}] Built RAG prompt with {len(prompt)} characters")
            
            # Generate response using LLM
            timing_context["llm_start"] = time.time()
            ai_response = await self.llm_provider.generate_response(prompt)
            llm_time = self._log_llm_timing(trace_id, timing_context, self.llm_provider_name)
            
            logger.info(f"[{trace_id}] Generated response in {llm_time:.3f}s")
            
            # Extract sources
            sources = self._extract_sources(search_results)
            
            # Check if fallback was used (LLM said it doesn't know)
            fallback_phrases = [
                "je ne trouve pas",
                "je ne sais pas",
                "informations insuffisantes",
                "pas d'informations pertinentes"
            ]
            fallback_used = any(phrase in ai_response.lower() for phrase in fallback_phrases)
            
            response = AgentResponse(
                answer=ai_response,
                sources=sources,
                trace_id=trace_id,
                response_time=0.0,  # Will be set in complete_request_logging
                chunks_scanned=chunks_scanned,
                fallback_used=fallback_used
            )
            
            # Complete logging
            self._complete_request_logging(
                trace_id, timing_context, question, filters, response, 
                search_time, llm_time
            )
            
            # Set final response time
            start_time = timing_context.get("start_time", 0.0) or 0.0
            response.response_time = time.time() - start_time
            
            logger.info(f"[{trace_id}] Complete response generated in {response.response_time:.3f}s (search: {search_time:.3f}s, LLM: {llm_time:.3f}s)")
            
            return response
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{trace_id}] Error processing question: {error_msg}")
            
            # Log error
            self.structured_logger.log_error(trace_id, error_msg, type(e).__name__)
            
            response = AgentResponse(
                answer=f"Une erreur s'est produite lors du traitement de votre question: {error_msg}",
                sources=[],
                trace_id=trace_id,
                response_time=0.0,
                chunks_scanned=0,
                fallback_used=True
            )
            
            # Complete logging with error
            self._complete_request_logging(
                trace_id, timing_context, question, filters, response, 
                0.0, 0.0, error_msg
            )
            
            # Set final response time
            start_time = timing_context.get("start_time", 0.0) or 0.0
            response.response_time = time.time() - start_time
            
            return response
    
    async def health_check(self) -> Dict[str, Any]:
        """Check system health"""
        try:
            mcp_health = await self.mcp_client.get_health()
            return {
                "status": "healthy",
                "mcp_service": mcp_health,
                "agent": "ready"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "agent": "error"
            }
    
    async def close(self):
        """Close resources"""
        await self.mcp_client.close()


def create_agent(
    mcp_url: str,
    llm_provider: str = "vertex",
    project_id: Optional[str] = None,
    openai_api_key: Optional[str] = None,
    **kwargs
) -> DocPilotAgent:
    """Factory function to create agent with specified LLM provider"""
    
    # Create LLM provider
    if llm_provider.lower() == "vertex":
        if not project_id:
            project_id = os.getenv("PROJECT_ID")
        if not project_id:
            raise ValueError("Project ID required for Vertex AI")
            
        llm = VertexAIProvider(project_id)
        
    elif llm_provider.lower() == "openai":
        if not openai_api_key:
            openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError("OpenAI API key required")
        
        llm = OpenAIProvider(openai_api_key)
        
    else:
        raise ValueError(f"Unsupported LLM provider: {llm_provider}")
    
    return DocPilotAgent(mcp_url, llm, **kwargs)