"""
DocPilot Observability - Logs structurés et métriques
Jour 5: Agent + CLI/mini-UI & Qualité
"""

import time
import uuid
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from loguru import logger


@dataclass
class RequestMetrics:
    """Metrics for a request"""
    trace_id: str
    timestamp: str
    question: str
    response_time: float
    search_time: float
    llm_time: float
    chunks_scanned: int
    chunks_used: int
    top_k_requested: int
    similarity_threshold: float
    source_filter: Optional[str]
    repo_filter: Optional[str]
    mime_filter: Optional[str]
    llm_provider: str
    fallback_used: bool
    error: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class StructuredLogger:
    """Structured logger for DocPilot using loguru"""
    
    def __init__(self, service_name: str = "docpilot-agent"):
        self.service_name = service_name
    
    def log_request_start(self, trace_id: str, question: str, filters: Dict[str, Any]):
        """Log request start"""
        logger.info(
            "Request started",
            extra={
                "event": "request_started",
                "service": self.service_name,
                "trace_id": trace_id,
                "question": question,
                "filters": filters,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    def log_search_complete(self, trace_id: str, chunks_found: int, search_time: float):
        """Log search completion"""
        logger.info(
            "Search completed",
            extra={
                "event": "search_completed",
                "service": self.service_name,
                "trace_id": trace_id,
                "chunks_found": chunks_found,
                "search_time_seconds": search_time,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    def log_llm_complete(self, trace_id: str, llm_time: float, provider: str):
        """Log LLM completion"""
        logger.info(
            "LLM completed",
            extra={
                "event": "llm_completed",
                "service": self.service_name,
                "trace_id": trace_id,
                "llm_time_seconds": llm_time,
                "provider": provider,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    def log_request_complete(self, metrics: RequestMetrics):
        """Log request completion with full metrics"""
        logger.info(
            "Request completed",
            extra={
                "event": "request_completed",
                "service": self.service_name,
                **asdict(metrics)
            }
        )
    
    def log_error(self, trace_id: str, error: str, error_type: str):
        """Log error"""
        logger.error(
            "Request error",
            extra={
                "event": "request_error",
                "service": self.service_name,
                "trace_id": trace_id,
                "error": error,
                "error_type": error_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    
    def log_health_check(self, status: str, details: Dict[str, Any]):
        """Log health check"""
        logger.info(
            "Health check",
            extra={
                "event": "health_check",
                "service": self.service_name,
                "status": status,
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


class MetricsCollector:
    """Collect and aggregate metrics"""
    
    def __init__(self):
        self.metrics = []
        self.session_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "total_search_time": 0.0,
            "total_llm_time": 0.0,
            "total_chunks_scanned": 0,
            "fallback_count": 0,
            "error_types": {},
            "sources_used": {},
            "llm_providers_used": {},
            "start_time": datetime.now(timezone.utc).isoformat()
        }
    
    def record_request(self, metrics: RequestMetrics):
        """Record request metrics"""
        self.metrics.append(metrics)
        
        # Update session stats
        self.session_stats["total_requests"] += 1
        
        if metrics.error:
            self.session_stats["failed_requests"] += 1
            error_type = type(metrics.error).__name__ if hasattr(metrics.error, '__class__') else "Unknown"
            self.session_stats["error_types"][error_type] = self.session_stats["error_types"].get(error_type, 0) + 1
        else:
            self.session_stats["successful_requests"] += 1
        
        self.session_stats["total_response_time"] += metrics.response_time
        self.session_stats["total_search_time"] += metrics.search_time
        self.session_stats["total_llm_time"] += metrics.llm_time
        self.session_stats["total_chunks_scanned"] += metrics.chunks_scanned
        
        if metrics.fallback_used:
            self.session_stats["fallback_count"] += 1
        
        # Track source usage
        if metrics.source_filter:
            self.session_stats["sources_used"][metrics.source_filter] = \
                self.session_stats["sources_used"].get(metrics.source_filter, 0) + 1
        
        # Track LLM provider usage
        self.session_stats["llm_providers_used"][metrics.llm_provider] = \
            self.session_stats["llm_providers_used"].get(metrics.llm_provider, 0) + 1
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session statistics"""
        stats = self.session_stats.copy()
        
        # Calculate averages
        if stats["total_requests"] > 0:
            stats["avg_response_time"] = stats["total_response_time"] / stats["total_requests"]
            stats["avg_search_time"] = stats["total_search_time"] / stats["total_requests"]
            stats["avg_llm_time"] = stats["total_llm_time"] / stats["total_requests"]
            stats["avg_chunks_scanned"] = stats["total_chunks_scanned"] / stats["total_requests"]
            stats["success_rate"] = stats["successful_requests"] / stats["total_requests"]
            stats["fallback_rate"] = stats["fallback_count"] / stats["total_requests"]
        
        return stats
    
    def get_recent_metrics(self, limit: int = 10) -> list:
        """Get recent metrics"""
        return self.metrics[-limit:] if self.metrics else []


class ObservabilityMixin:
    """Mixin to add observability to the agent"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.structured_logger = StructuredLogger()
        self.metrics_collector = MetricsCollector()
        self.session_id = str(uuid.uuid4())
    
    def _start_request_logging(self, trace_id: str, question: str, filters) -> Dict[str, Optional[float]]:
        """Start request logging and return timing context"""
        # Log request start
        filter_dict = {
            "source": getattr(filters, 'source', None),
            "repo": getattr(filters, 'repo', None),
            "mime": getattr(filters, 'mime', None),
            "top_k": getattr(filters, 'top_k', 10),
            "similarity_threshold": getattr(filters, 'similarity_threshold', 0.7)
        }
        
        self.structured_logger.log_request_start(trace_id, question, filter_dict)
        
        return {
            "start_time": time.time(),
            "search_start": None,
            "search_end": None,
            "llm_start": None,
            "llm_end": None
        }
    
    def _log_search_timing(self, trace_id: str, timing_context: Dict[str, Optional[float]], chunks_found: int):
        """Log search timing"""
        timing_context["search_end"] = time.time()
        search_start = timing_context.get("search_start", 0.0) or 0.0
        search_end = timing_context.get("search_end", 0.0) or 0.0
        search_time = search_end - search_start
        
        self.structured_logger.log_search_complete(trace_id, chunks_found, search_time)
        
        return search_time
    
    def _log_llm_timing(self, trace_id: str, timing_context: Dict[str, Optional[float]], provider: str):
        """Log LLM timing"""
        timing_context["llm_end"] = time.time()
        llm_start = timing_context.get("llm_start", 0.0) or 0.0
        llm_end = timing_context.get("llm_end", 0.0) or 0.0
        llm_time = llm_end - llm_start
        
        self.structured_logger.log_llm_complete(trace_id, llm_time, provider)
        
        return llm_time
    
    def _complete_request_logging(
        self,
        trace_id: str,
        timing_context: Dict[str, Optional[float]],
        question: str,
        filters,
        response,
        search_time: float,
        llm_time: float,
        error: Optional[str] = None
    ):
        """Complete request logging"""
        start_time = timing_context.get("start_time", 0.0) or 0.0
        total_time = time.time() - start_time
        
        # Create metrics object
        metrics = RequestMetrics(
            trace_id=trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            question=question,
            response_time=total_time,
            search_time=search_time,
            llm_time=llm_time,
            chunks_scanned=getattr(response, 'chunks_scanned', 0) if response else 0,
            chunks_used=len(getattr(response, 'sources', [])) if response else 0,
            top_k_requested=getattr(filters, 'top_k', 10),
            similarity_threshold=getattr(filters, 'similarity_threshold', 0.7),
            source_filter=getattr(filters, 'source', None),
            repo_filter=getattr(filters, 'repo', None),
            mime_filter=getattr(filters, 'mime', None),
            llm_provider=getattr(self, 'llm_provider', 'unknown'),
            fallback_used=getattr(response, 'fallback_used', True) if response else True,
            error=error,
            session_id=self.session_id
        )
        
        # Log completion
        self.structured_logger.log_request_complete(metrics)
        
        # Record metrics
        self.metrics_collector.record_request(metrics)
        
        return metrics
    
    def get_observability_stats(self) -> Dict[str, Any]:
        """Get observability statistics"""
        return {
            "session_id": self.session_id,
            "session_stats": self.metrics_collector.get_session_stats(),
            "recent_requests": [
                {
                    "trace_id": m.trace_id,
                    "question": m.question[:50] + "..." if len(m.question) > 50 else m.question,
                    "response_time": m.response_time,
                    "chunks_scanned": m.chunks_scanned,
                    "fallback_used": m.fallback_used,
                    "timestamp": m.timestamp
                }
                for m in self.metrics_collector.get_recent_metrics(5)
            ]
        }


def setup_observability_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """Setup observability logging configuration"""
    
    # Configure loguru for application logs
    logger.remove()
    
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    # Console logging
    logger.add(
        lambda msg: print(msg, end=""),
        format=log_format,
        level=log_level,
        colorize=True
    )
    
    # File logging if specified
    if log_file:
        logger.add(
            log_file,
            format=log_format,
            level=log_level,
            rotation="100 MB",
            retention="7 days",
            compression="gzip"
        )
    
    # Structured logging to separate file
    if log_file:
        structured_log_file = log_file.replace(".log", "_structured.jsonl")
        logger.add(
            structured_log_file,
            format="{message}",
            level=log_level,
            serialize=True,
            rotation="100 MB",
            retention="7 days"
        )