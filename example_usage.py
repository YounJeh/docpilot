#!/usr/bin/env python3
"""
Exemple d'utilisation pratique de DocPilot Agent
Jour 5: Agent + CLI/mini-UI & Qualité
"""

import asyncio
import os
from pathlib import Path
import sys

# Add current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from knowledge_copilot.agent import create_agent, SearchFilter


async def demo_basic_usage():
    """Démonstration d'utilisation basique"""
    print("🚁 DocPilot Agent - Démonstration d'utilisation")
    print("=" * 60)
    
    # Configuration
    mcp_url = os.getenv("MCP_URL", "http://localhost:8000")
    
    # Créer l'agent
    agent = create_agent(
        mcp_url=mcp_url,
        llm_provider="openai",  # ou "vertex"
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        project_id=os.getenv("PROJECT_ID")
    )
    
    print(f"🔗 Connecté au service MCP: {mcp_url}")
    
    # Vérifier l'état du système
    health = await agent.health_check()
    print(f"🏥 État du système: {health.get('status', 'unknown')}")
    
    if health.get("status") != "healthy":
        print("❌ Le système n'est pas opérationnel. Vérifiez votre service MCP.")
        return
    
    # Exemple 1: Question simple
    print(f"\n📝 Exemple 1: Question simple")
    print("-" * 30)
    
    response = await agent.ask("Comment déployer une application sur Cloud Run ?")
    
    print(f"Question: Comment déployer une application sur Cloud Run ?")
    print(f"Réponse ({response.response_time:.3f}s):")
    print(f"  {response.answer[:200]}...")
    print(f"  📄 {len(response.sources)} sources trouvées")
    print(f"  🔍 {response.chunks_scanned} chunks analysés")
    print(f"  🆔 Trace ID: {response.trace_id}")
    
    # Exemple 2: Avec filtres
    print(f"\n📝 Exemple 2: Avec filtres GitHub")
    print("-" * 30)
    
    filters = SearchFilter(
        source="github",
        mime="text/markdown",
        top_k=5,
        similarity_threshold=0.7
    )
    
    response = await agent.ask("Configuration Docker", filters)
    
    print(f"Question: Configuration Docker")
    print(f"Filtres: source=github, mime=text/markdown, top_k=5")
    print(f"Réponse ({response.response_time:.3f}s):")
    print(f"  {response.answer[:200]}...")
    print(f"  📄 {len(response.sources)} sources trouvées")
    
    if response.sources:
        print("  🏷️  Top sources:")
        for i, source in enumerate(response.sources[:3], 1):
            print(f"    {i}. {source['title'][:50]}... (sim: {source['similarity_score']:.3f})")
    
    # Exemple 3: Repository spécifique
    print(f"\n📝 Exemple 3: Repository spécifique")
    print("-" * 30)
    
    filters = SearchFilter(
        repo="docpilot",  # Remplacez par un repo réel
        top_k=10
    )
    
    response = await agent.ask("API endpoints disponibles", filters)
    
    print(f"Question: API endpoints disponibles")
    print(f"Filtres: repo=docpilot, top_k=10")
    print(f"Réponse ({response.response_time:.3f}s):")
    print(f"  Fallback utilisé: {'Oui' if response.fallback_used else 'Non'}")
    
    if not response.fallback_used:
        print(f"  {response.answer[:200]}...")
    else:
        print(f"  {response.answer}")
    
    # Statistiques de session
    print(f"\n📊 Statistiques de session")
    print("-" * 30)
    
    stats = agent.get_observability_stats()
    session_stats = stats["session_stats"]
    
    print(f"Total requêtes: {session_stats['total_requests']}")
    print(f"Requêtes réussies: {session_stats['successful_requests']}")
    print(f"Temps moyen de réponse: {session_stats.get('avg_response_time', 0):.3f}s")
    print(f"Temps moyen de recherche: {session_stats.get('avg_search_time', 0):.3f}s")
    print(f"Temps moyen LLM: {session_stats.get('avg_llm_time', 0):.3f}s")
    print(f"Taux de succès: {session_stats.get('success_rate', 0):.1%}")
    print(f"Taux de fallback: {session_stats.get('fallback_rate', 0):.1%}")
    
    # Historique des requêtes récentes
    if stats["recent_requests"]:
        print(f"\n🕐 Requêtes récentes:")
        for req in stats["recent_requests"]:
            print(f"  • {req['question']} ({req['response_time']:.3f}s)")
    
    # Nettoyage
    await agent.close()
    print(f"\n✅ Démonstration terminée!")


async def demo_conversation_flow():
    """Démonstration d'un flux de conversation"""
    print(f"\n🗣️  Simulation d'une conversation")
    print("=" * 60)
    
    agent = create_agent(
        mcp_url=os.getenv("MCP_URL", "http://localhost:8000"),
        llm_provider="openai",
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Conversation simulée
    conversation = [
        {
            "user": "Comment déployer sur Cloud Run ?",
            "filters": SearchFilter(source="github", top_k=5)
        },
        {
            "user": "Quels sont les prérequis Docker ?",
            "filters": SearchFilter(mime="text/markdown", top_k=3)
        },
        {
            "user": "Comment configurer les variables d'environnement ?",
            "filters": SearchFilter(top_k=7)
        }
    ]
    
    print(f"Simulation d'une conversation avec {len(conversation)} messages:")
    
    for i, turn in enumerate(conversation, 1):
        print(f"\n--- Tour {i} ---")
        print(f"👤 Utilisateur: {turn['user']}")
        
        response = await agent.ask(turn["user"], turn["filters"])
        
        print(f"🤖 Assistant ({response.response_time:.3f}s): ", end="")
        
        if response.fallback_used:
            print("⚠️  Informations insuffisantes")
        else:
            answer_preview = response.answer[:150] + "..." if len(response.answer) > 150 else response.answer
            print(f"{answer_preview}")
        
        print(f"   📊 {response.chunks_scanned} chunks | {len(response.sources)} sources")
    
    await agent.close()


def demo_cli_examples():
    """Exemples d'utilisation CLI"""
    print(f"\n🖥️  Exemples CLI")
    print("=" * 60)
    
    examples = [
        {
            "description": "Question basique",
            "command": 'python cli.py ask "Comment déployer sur Cloud Run ?"'
        },
        {
            "description": "Filtrage par source GitHub",
            "command": 'python cli.py ask "Configuration Docker" --source github --top-k 5'
        },
        {
            "description": "Filtrage par type de fichier",
            "command": 'python cli.py ask "API documentation" --mime text/markdown --threshold 0.8'
        },
        {
            "description": "Repository spécifique",
            "command": 'python cli.py ask "Installation guide" --repo my-project'
        },
        {
            "description": "Format JSON",
            "command": 'python cli.py ask "Deployment process" --format json'
        },
        {
            "description": "Utilisation de Vertex AI",
            "command": 'python cli.py ask "ML pipeline" --llm vertex --project-id my-gcp-project'
        },
        {
            "description": "Vérification de santé",
            "command": 'python cli.py health --verbose'
        }
    ]
    
    for example in examples:
        print(f"\n💡 {example['description']}:")
        print(f"   {example['command']}")
    
    print(f"\n🌐 Interface web:")
    print(f"   streamlit run streamlit_app.py")


def main():
    """Point d'entrée principal"""
    print("🚁 DocPilot Agent - Exemples d'utilisation complète")
    print("=" * 70)
    
    # Vérification de la configuration
    if not os.getenv("MCP_URL"):
        print("❌ Variable MCP_URL non définie!")
        print("   export MCP_URL=http://localhost:8000")
        return
    
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("PROJECT_ID"):
        print("❌ Aucune clé LLM configurée!")
        print("   Pour OpenAI: export OPENAI_API_KEY=your_key")
        print("   Pour Vertex: export PROJECT_ID=your_project")
        return
    
    print("✅ Configuration détectée, démarrage des exemples...")
    
    # Exécuter les démonstrations
    asyncio.run(demo_basic_usage())
    asyncio.run(demo_conversation_flow())
    demo_cli_examples()
    
    print(f"\n🎉 Tous les exemples terminés!")
    print(f"\nPour utiliser DocPilot:")
    print(f"  📱 CLI: python cli.py ask \"Votre question\"")
    print(f"  🌐 Web: streamlit run streamlit_app.py")
    print(f"  🧪 Tests: python test_agent.py")


if __name__ == "__main__":
    main()