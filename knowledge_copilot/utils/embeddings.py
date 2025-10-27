"""
Embeddings service using Vertex AI text-embedding-004 model
"""

import os
from typing import List, Optional
from google.oauth2 import service_account
import vertexai
from vertexai.language_models import TextEmbeddingModel
from loguru import logger


class VertexAIEmbeddings:
    """Vertex AI embeddings service using text-embedding-004 model"""
    
    def __init__(
        self,
        project_id: str,
        region: str = "europe-west1",
        model_name: str = "text-embedding-004",
        credentials_path: Optional[str] = None
    ):
        self.project_id = project_id
        self.region = region
        self.model_name = model_name
        self.credentials_path = credentials_path
        
        # Initialize Vertex AI
        self._initialize_vertex_ai()
        
        # Load the embedding model
        self.model = TextEmbeddingModel.from_pretrained(self.model_name)
        logger.info(f"Initialized Vertex AI embeddings with model: {self.model_name}")
    
    def _initialize_vertex_ai(self):
        """Initialize Vertex AI with credentials"""
        if self.credentials_path and os.path.exists(self.credentials_path):
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path
            )
            vertexai.init(
                project=self.project_id,
                location=self.region,
                credentials=credentials
            )
            logger.info("Initialized Vertex AI with service account credentials")
        else:
            # Use default credentials (gcloud auth)
            vertexai.init(project=self.project_id, location=self.region)
            logger.info("Initialized Vertex AI with default credentials")
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for a list of texts
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (list of floats)
        """
        try:
            # Get embeddings using the model
            embeddings_response = self.model.get_embeddings(texts)
            
            # Extract the embedding values
            embeddings = [embedding.values for embedding in embeddings_response]
            
            logger.debug(f"Generated embeddings for {len(texts)} texts")
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding for a single text
        
        Args:
            text: Text string to embed
            
        Returns:
            Embedding vector as list of floats
        """
        embeddings = self.get_embeddings([text])
        return embeddings[0]
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embeddings for this model
        
        Returns:
            Embedding dimension (768 for text-embedding-004)
        """
        # text-embedding-004 returns 768-dimensional embeddings
        return 768


def create_embeddings_service(
    project_id: Optional[str] = None,
    region: Optional[str] = None,
    credentials_path: Optional[str] = None
) -> VertexAIEmbeddings:
    """
    Factory function to create embeddings service with environment variables
    
    Args:
        project_id: GCP project ID (defaults to PROJECT_ID env var)
        region: GCP region (defaults to REGION env var)
        credentials_path: Path to service account credentials (optional)
    
    Returns:
        Configured VertexAIEmbeddings instance
    """
    project_id = project_id or os.getenv("PROJECT_ID")
    region = region or os.getenv("REGION", "europe-west1")
    
    if not project_id:
        raise ValueError("PROJECT_ID must be provided or set as environment variable")
    
    # Use service account credentials if available
    if not credentials_path:
        # Look for service account file in current directory
        possible_paths = [
            "kc-drive-sa.json",
            "../kc-drive-sa.json",
            "../../kc-drive-sa.json"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                credentials_path = path
                break
    
    return VertexAIEmbeddings(
        project_id=project_id,
        region=region,
        credentials_path=credentials_path
    )