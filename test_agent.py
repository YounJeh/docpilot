#!/usr/bin/env python3
"""
Test script for DocPilot Agent
Jour 5: Agent + CLI/mini-UI & Qualité
"""

import asyncio
import os
import sys
from pathlib import Path

# Add current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from knowledge_copilot.agent import create_agent, SearchFilter
from knowledge_copilot.observability import setup_observability_logging


async def test_agent():
    """Test the DocPilot agent"""
    
    # Setup logging
    setup_observability_logging("INFO", "test_agent.log")
    
    print("🚁 Test de l'agent DocPilot")
    print("=" * 50)
    
    # Configuration
    mcp_url = os.getenv("MCP_URL", "http://localhost:8000")
    llm_provider = os.getenv("LLM_PROVIDER", "openai")
    
    print(f"MCP URL: {mcp_url}")
    print(f"LLM Provider: {llm_provider}")
    print()
    
    try:
        # Create agent
        print("🔧 Création de l'agent...")
        agent = create_agent(
            mcp_url=mcp_url,
            llm_provider=llm_provider,
            project_id=os.getenv("PROJECT_ID"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )
        print("✅ Agent créé avec succès")
        
        # Health check
        print("\n🏥 Vérification de l'état du système...")
        health = await agent.health_check()
        print(f"État: {health.get('status', 'unknown')}")
        
        if health.get("status") != "healthy":
            print("❌ Le système n'est pas en bonne santé")
            if "error" in health:
                print(f"Erreur: {health['error']}")
            return
        
        print("✅ Système opérationnel")
        
        # Test questions
        test_questions = [
            {
                "question": "Comment déployer une application sur Cloud Run ?",
                "filters": SearchFilter(source="github", top_k=5)
            },
            {
                "question": "Configuration Docker pour Python",
                "filters": SearchFilter(mime="text/markdown", top_k=3)
            },
            {
                "question": "API endpoints disponibles",
                "filters": SearchFilter(top_k=7, similarity_threshold=0.6)
            }
        ]
        
        print(f"\n🧪 Test avec {len(test_questions)} questions...")
        
        for i, test in enumerate(test_questions, 1):
            print(f"\n--- Test {i}/{len(test_questions)} ---")
            print(f"Question: {test['question']}")
            print(f"Filtres: source={test['filters'].source}, mime={test['filters'].mime}, top_k={test['filters'].top_k}")
            
            # Ask question
            response = await agent.ask(test["question"], test["filters"])
            
            # Display results
            print(f"\nRéponse ({response.response_time:.3f}s):")
            print(f"Trace ID: {response.trace_id}")
            print(f"Chunks scannés: {response.chunks_scanned}")
            print(f"Sources trouvées: {len(response.sources)}")
            print(f"Fallback utilisé: {'Oui' if response.fallback_used else 'Non'}")
            
            # Show answer preview
            answer_preview = response.answer[:200] + "..." if len(response.answer) > 200 else response.answer
            print(f"Réponse: {answer_preview}")
            
            # Show top sources
            if response.sources:
                print("\nTop 3 sources:")
                for j, source in enumerate(response.sources[:3], 1):
                    print(f"  {j}. {source['title'][:60]}... (sim: {source['similarity_score']:.3f})")
        
        # Show observability stats
        print("\n📊 Statistiques de session:")
        stats = agent.get_observability_stats()
        session_stats = stats["session_stats"]
        
        print(f"Total requêtes: {session_stats['total_requests']}")
        print(f"Requêtes réussies: {session_stats['successful_requests']}")
        print(f"Requêtes échouées: {session_stats['failed_requests']}")
        
        if session_stats['total_requests'] > 0:
            print(f"Temps moyen de réponse: {session_stats.get('avg_response_time', 0):.3f}s")
            print(f"Temps moyen de recherche: {session_stats.get('avg_search_time', 0):.3f}s")
            print(f"Temps moyen LLM: {session_stats.get('avg_llm_time', 0):.3f}s")
            print(f"Chunks moyens scannés: {session_stats.get('avg_chunks_scanned', 0):.1f}")
            print(f"Taux de succès: {session_stats.get('success_rate', 0):.1%}")
            print(f"Taux de fallback: {session_stats.get('fallback_rate', 0):.1%}")
        
        # Close agent
        await agent.close()
        print("\n✅ Tests terminés avec succès!")
        
    except Exception as e:
        print(f"\n❌ Erreur durant le test: {e}")
        import traceback
        traceback.print_exc()


async def test_cli_integration():
    """Test CLI integration"""
    print("\n🖥️  Test d'intégration CLI")
    print("=" * 50)
    
    # Test CLI commands (simulation)
    cli_commands = [
        'docpilot ask "Comment déployer sur Cloud Run ?" --source github --top-k 5',
        'docpilot ask "Configuration Docker" --mime text/markdown --format json',
        'docpilot health --verbose'
    ]
    
    print("Commandes CLI à tester:")
    for cmd in cli_commands:
        print(f"  {cmd}")
    
    print("\n💡 Pour tester réellement, exécutez:")
    print("  python cli.py ask \"Votre question\" --help")


def main():
    """Main test function"""
    print("🚁 DocPilot - Suite de tests complète")
    print("=" * 50)
    
    # Check environment
    print("🔍 Vérification de l'environnement...")
    
    required_vars = ["MCP_URL"]
    optional_vars = ["OPENAI_API_KEY", "PROJECT_ID", "LLM_PROVIDER"]
    
    print("\nVariables d'environnement requises:")
    for var in required_vars:
        value = os.getenv(var)
        status = "✅" if value else "❌"
        print(f"  {status} {var}: {'Définie' if value else 'Non définie'}")
    
    print("\nVariables d'environnement optionnelles:")
    for var in optional_vars:
        value = os.getenv(var)
        status = "✅" if value else "⚠️"
        print(f"  {status} {var}: {'Définie' if value else 'Non définie'}")
    
    # Check if MCP_URL is set
    if not os.getenv("MCP_URL"):
        print("\n❌ MCP_URL non définie. Définissez-la avant de continuer:")
        print("  export MCP_URL=http://localhost:8000")
        return
    
    # Check LLM configuration
    llm_provider = os.getenv("LLM_PROVIDER", "openai")
    if llm_provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        print("\n❌ OPENAI_API_KEY non définie pour le provider OpenAI")
        print("  export OPENAI_API_KEY=your_key_here")
        return
    
    if llm_provider == "vertex" and not os.getenv("PROJECT_ID"):
        print("\n❌ PROJECT_ID non défini pour le provider Vertex AI")
        print("  export PROJECT_ID=your_project_id")
        return
    
    print("\n✅ Configuration valide, démarrage des tests...")
    
    # Run async tests
    asyncio.run(test_agent())
    
    # Run CLI integration test
    asyncio.run(test_cli_integration())
    
    print("\n🎉 Tous les tests terminés!")
    print("\nPour utiliser DocPilot:")
    print("  📱 CLI: python cli.py ask \"Votre question\"")
    print("  🌐 Web: streamlit run streamlit_app.py")


if __name__ == "__main__":
    main()