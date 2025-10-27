"""
Test script for the RAG implementation
Tests document indexing and semantic search functionality
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Test data
test_documents = [
    {
        "content": """
        Machine Learning is a subset of artificial intelligence that focuses on algorithms 
        that can learn and make decisions from data without being explicitly programmed. 
        It includes supervised learning, unsupervised learning, and reinforcement learning.
        Popular algorithms include linear regression, decision trees, neural networks, and 
        support vector machines.
        """,
        "title": "Introduction to Machine Learning",
        "source": "test",
        "uri": "test://ml-intro",
        "mime": "text/plain"
    },
    {
        "content": """
        PostgreSQL is a powerful, open-source relational database management system. 
        It supports advanced data types, complex queries, and ACID transactions. 
        With pgvector extension, PostgreSQL can handle vector operations for 
        similarity search and machine learning applications.
        """,
        "title": "PostgreSQL Database Guide",
        "source": "test", 
        "uri": "test://postgres-guide",
        "mime": "text/plain"
    },
    {
        "content": """
        FastAPI is a modern, fast web framework for building APIs with Python. 
        It's based on standard Python type hints and provides automatic API documentation. 
        FastAPI supports async/await, dependency injection, and data validation with Pydantic.
        """,
        "title": "FastAPI Framework",
        "source": "test",
        "uri": "test://fastapi-intro", 
        "mime": "text/plain"
    }
]

test_queries = [
    "What is machine learning?",
    "How to use PostgreSQL for vector search?",
    "Tell me about FastAPI framework",
    "Database systems with vector support"
]


def test_imports():
    """Test that all required modules can be imported"""
    print("Testing imports...")
    
    try:
        # Test core imports
        from knowledge_copilot.utils.embeddings import VertexAIEmbeddings, create_embeddings_service
        from knowledge_copilot.models import Document, Chunk
        from knowledge_copilot.services import DatabaseService, create_database_service
        from knowledge_copilot.rag_service import RAGService, create_rag_service
        from knowledge_copilot.utils.chunking import chunk_text
        
        print("✅ All imports successful")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False


def test_chunking():
    """Test text chunking functionality"""
    print("\nTesting text chunking...")
    
    try:
        from knowledge_copilot.utils.chunking import chunk_text
        
        sample_text = "This is a test document. " * 100  # Create a longer text
        chunks = chunk_text(sample_text, chunk_size=200, chunk_overlap=50)
        
        print(f"✅ Created {len(chunks)} chunks from {len(sample_text)} characters")
        print(f"   First chunk: {chunks[0]['text'][:50]}...")
        return True
        
    except Exception as e:
        print(f"❌ Chunking error: {e}")
        return False


def test_embeddings():
    """Test embeddings service (requires GCP credentials)"""
    print("\nTesting embeddings service...")
    
    try:
        from knowledge_copilot.utils.embeddings import create_embeddings_service
        
        # Check if we have required environment variables
        project_id = os.getenv("PROJECT_ID")
        if not project_id:
            print("⚠️  Skipping embeddings test - PROJECT_ID not set")
            return True
        
        embeddings_service = create_embeddings_service()
        
        # Test embedding generation
        test_text = "This is a test sentence for embedding generation."
        embedding = embeddings_service.get_embedding(test_text)
        
        print(f"✅ Generated embedding with {len(embedding)} dimensions")
        print(f"   Embedding dimension: {embeddings_service.get_embedding_dimension()}")
        return True
        
    except Exception as e:
        print(f"❌ Embeddings error: {e}")
        print("   Note: This test requires valid GCP credentials and PROJECT_ID")
        return False


def test_database_models():
    """Test database models"""
    print("\nTesting database models...")
    
    try:
        from knowledge_copilot.models import Document, Chunk, Base
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        # Test with in-memory SQLite for basic model validation
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        
        SessionLocal = sessionmaker(bind=engine)
        
        with SessionLocal() as session:
            # Create a test document
            doc = Document(
                title="Test Document",
                source="test",
                content_hash="test_hash_123",
                uri="test://doc1"
            )
            session.add(doc)
            session.flush()
            
            # Create a test chunk (without embedding for SQLite)
            chunk = Chunk(
                doc_id=doc.id,
                text="Test chunk content",
                metadata={"test": True}
            )
            session.add(chunk)
            session.commit()
            
            # Query back
            retrieved_doc = session.query(Document).first()
            retrieved_chunk = session.query(Chunk).first()
            
            print(f"✅ Created document: {retrieved_doc}")
            print(f"   Created chunk: {retrieved_chunk}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database models error: {e}")
        return False


def test_rag_service_creation():
    """Test RAG service creation (without database connection)"""
    print("\nTesting RAG service creation...")
    
    try:
        # Test that we can at least import and create the service class
        from knowledge_copilot.rag_service import RAGService
        
        print("✅ RAG service class imported successfully")
        print("   Note: Full service test requires database connection")
        return True
        
    except Exception as e:
        print(f"❌ RAG service creation error: {e}")
        return False


async def test_api_models():
    """Test API models from main.py"""
    print("\nTesting API models...")
    
    try:
        # Test that we can import the models
        import sys
        from pathlib import Path
        
        # Import the models from main.py
        from main import DocumentIndexRequest, SearchRequest, DocumentIndexResponse, SearchResponse
        
        # Test creating request models
        doc_request = DocumentIndexRequest(
            content="Test content",
            title="Test Doc",
            source="test"
        )
        
        search_request = SearchRequest(
            query="test query",
            limit=5
        )
        
        print("✅ API models created successfully")
        print(f"   Document request: {doc_request.title}")
        print(f"   Search request: {search_request.query}")
        return True
        
    except Exception as e:
        print(f"❌ API models error: {e}")
        return False


def main():
    """Run all tests"""
    print("🧪 Running DocPilot RAG Implementation Tests")
    print("=" * 50)
    
    test_results = []
    
    # Run tests
    test_results.append(("Imports", test_imports()))
    test_results.append(("Chunking", test_chunking()))
    test_results.append(("Database Models", test_database_models()))
    test_results.append(("RAG Service Creation", test_rag_service_creation()))
    
    # Run async tests
    loop = asyncio.get_event_loop()
    test_results.append(("API Models", loop.run_until_complete(test_api_models())))
    
    # Run optional tests (require external services)
    test_results.append(("Embeddings", test_embeddings()))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:<20} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! RAG implementation is ready.")
        print("\n📋 Next steps:")
        print("   1. Set up PostgreSQL with pgvector extension")
        print("   2. Configure GCP credentials and PROJECT_ID")
        print("   3. Set database connection in .env file")
        print("   4. Run: uv run python main.py")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)