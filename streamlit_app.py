"""
DocPilot Streamlit UI - Interface web pour l'agent
Jour 5: Agent + CLI/mini-UI & Qualité
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any
import streamlit as st
from datetime import datetime

# Add current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from knowledge_copilot.agent import create_agent, SearchFilter


# Page configuration
st.set_page_config(
    page_title="DocPilot Assistant",
    page_icon="🚁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        text-align: center;
        padding: 1rem 0;
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 2.5rem;
        font-weight: bold;
    }
    
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
    
    .source-card {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .fallback-warning {
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state"""
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []
    if "agent_config" not in st.session_state:
        st.session_state.agent_config = {
            "mcp_url": os.getenv("MCP_URL", "http://localhost:8000"),
            "llm_provider": "vertex",
            "project_id": os.getenv("PROJECT_ID"),
            "openai_api_key": os.getenv("OPENAI_API_KEY")
        }


def sidebar_configuration():
    """Sidebar for configuration and filters"""
    st.sidebar.markdown("## ⚙️ Configuration")
    
    # Service configuration
    st.sidebar.subheader("Service MCP")
    mcp_url = st.sidebar.text_input(
        "URL du service MCP",
        value=st.session_state.agent_config["mcp_url"],
        help="URL de l'API MCP (ex: http://localhost:8000)"
    )
    
    # LLM configuration
    st.sidebar.subheader("Modèle de langage")
    llm_provider = st.sidebar.selectbox(
        "Fournisseur LLM",
        ["vertex", "openai"],
        index=0 if st.session_state.agent_config["llm_provider"] == "vertex" else 1
    )
    
    # Provider-specific settings
    if llm_provider == "vertex":
        project_id = st.sidebar.text_input(
            "Project ID Google Cloud",
            value=st.session_state.agent_config["project_id"] or "",
            help="Votre Project ID Google Cloud"
        )
        st.session_state.agent_config["project_id"] = project_id
    elif llm_provider == "openai":
        openai_key = st.sidebar.text_input(
            "Clé API OpenAI",
            value=st.session_state.agent_config["openai_api_key"] or "",
            type="password",
            help="Votre clé API OpenAI"
        )
        st.session_state.agent_config["openai_api_key"] = openai_key
    
    # Update session state
    st.session_state.agent_config.update({
        "mcp_url": mcp_url,
        "llm_provider": llm_provider
    })
    
    st.sidebar.markdown("---")
    
    # Search filters
    st.sidebar.subheader("🔍 Filtres de recherche")
    
    source_filter = st.sidebar.selectbox(
        "Source",
        ["Toutes", "github", "gdrive"],
        help="Filtrer par source de documents"
    )
    
    repo_filter = st.sidebar.text_input(
        "Repository",
        placeholder="ex: mon-repo",
        help="Filtrer par repository GitHub spécifique"
    )
    
    mime_filter = st.sidebar.selectbox(
        "Type de fichier",
        ["Tous", "text/markdown", "text/plain", "application/pdf", "text/html"],
        help="Filtrer par type MIME"
    )
    
    # Search parameters
    st.sidebar.subheader("📊 Paramètres de recherche")
    
    top_k = st.sidebar.slider(
        "Nombre de chunks (top-k)",
        min_value=1,
        max_value=50,
        value=10,
        help="Nombre maximum de chunks à récupérer"
    )
    
    similarity_threshold = st.sidebar.slider(
        "Seuil de similarité",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.05,
        help="Seuil minimum de similarité"
    )
    
    # Create filter object
    filters = SearchFilter(
        source=source_filter if source_filter != "Toutes" else None,
        repo=repo_filter if repo_filter else None,
        mime=mime_filter if mime_filter != "Tous" else None,
        top_k=top_k,
        similarity_threshold=similarity_threshold
    )
    
    return filters


async def process_question_async(question: str, filters: SearchFilter) -> Dict[str, Any]:
    """Process question asynchronously"""
    try:
        # Create agent
        agent = create_agent(
            mcp_url=st.session_state.agent_config["mcp_url"],
            llm_provider=st.session_state.agent_config["llm_provider"],
            project_id=st.session_state.agent_config["project_id"],
            openai_api_key=st.session_state.agent_config["openai_api_key"]
        )
        
        # Process question
        response = await agent.ask(question, filters)
        
        # Close agent
        await agent.close()
        
        return {
            "success": True,
            "response": response,
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "response": None,
            "error": str(e)
        }


def display_response(response, filters: SearchFilter):
    """Display agent response with rich formatting"""
    
    # Response metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h4>⏱️ Temps de réponse</h4>
            <h2>{response.response_time:.3f}s</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h4>📄 Chunks analysés</h4>
            <h2>{response.chunks_scanned}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h4>🎯 Top-k demandé</h4>
            <h2>{filters.top_k}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        fallback_color = "#ff7f0e" if response.fallback_used else "#2ca02c"
        fallback_text = "Oui" if response.fallback_used else "Non"
        st.markdown(f"""
        <div class="metric-card">
            <h4>⚠️ Fallback</h4>
            <h2 style="color: {fallback_color}">{fallback_text}</h2>
        </div>
        """, unsafe_allow_html=True)
    
    # Fallback warning
    if response.fallback_used:
        st.markdown("""
        <div class="fallback-warning">
            <h4>⚠️ Information limitée</h4>
            <p>L'assistant n'a pas trouvé suffisamment d'informations pertinentes dans la documentation pour répondre de manière complète à votre question.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Main response
    st.markdown("### 💬 Réponse")
    st.markdown(response.answer)
    
    # Sources
    if response.sources:
        st.markdown("### 📚 Sources")
        
        for i, source in enumerate(response.sources):
            with st.expander(f"📄 {source['title'][:80]}... (Similarité: {source['similarity_score']:.3f})"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"**Titre:** {source['title']}")
                    st.markdown(f"**URI:** `{source['uri']}`")
                    if source['repo']:
                        st.markdown(f"**Repository:** `{source['repo']}`")
                    if source['path']:
                        st.markdown(f"**Chemin:** `{source['path']}`")
                
                with col2:
                    st.markdown(f"**Source:** `{source['source']}`")
                    st.markdown(f"**Type MIME:** `{source['mime']}`")
                    st.markdown(f"**Similarité:** `{source['similarity_score']:.3f}`")
                    st.markdown(f"**Chunk ID:** `{source['chunk_id']}`")
    
    # Technical details
    with st.expander("🔧 Détails techniques"):
        st.json({
            "trace_id": response.trace_id,
            "response_time": response.response_time,
            "chunks_scanned": response.chunks_scanned,
            "fallback_used": response.fallback_used,
            "filters": {
                "source": filters.source,
                "repo": filters.repo,
                "mime": filters.mime,
                "top_k": filters.top_k,
                "similarity_threshold": filters.similarity_threshold
            }
        })


def display_conversation_history():
    """Display conversation history"""
    if st.session_state.conversation_history:
        st.markdown("### 📜 Historique des conversations")
        
        for i, entry in enumerate(reversed(st.session_state.conversation_history[-5:])):  # Last 5
            with st.expander(f"💬 {entry['question'][:50]}... ({entry['timestamp']})"):
                st.markdown(f"**Question:** {entry['question']}")
                st.markdown(f"**Réponse:** {entry['answer']}")
                st.markdown(f"**Sources:** {len(entry['sources'])} documents")
                st.markdown(f"**Temps:** {entry['response_time']:.3f}s")


async def health_check_async():
    """Check system health"""
    try:
        agent = create_agent(
            mcp_url=st.session_state.agent_config["mcp_url"],
            llm_provider="vertex",  # Use vertex by default for health check
            project_id=st.session_state.agent_config["project_id"] or os.getenv("PROJECT_ID", "dummy")
        )
        
        health = await agent.health_check()
        await agent.close()
        return health
        
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def main():
    """Main Streamlit application"""
    
    # Initialize session state
    initialize_session_state()
    
    # Header
    st.markdown('<h1 class="main-header">🚁 DocPilot Assistant</h1>', unsafe_allow_html=True)
    st.markdown("*Assistant conversationnel pour votre documentation GitHub et Google Drive*")
    
    # Sidebar configuration
    filters = sidebar_configuration()
    
    # Health check section
    with st.sidebar:
        st.markdown("---")
        st.subheader("🏥 État du système")
        
        if st.button("🔄 Vérifier l'état"):
            with st.spinner("Vérification..."):
                health = asyncio.run(health_check_async())
                
                if health["status"] == "healthy":
                    st.success("✅ Système opérationnel")
                else:
                    st.error(f"❌ Problème détecté: {health.get('error', 'Erreur inconnue')}")
    
    # Main interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Question input
        st.markdown("### 💭 Posez votre question")
        question = st.text_area(
            "Question",
            placeholder="Exemple: Comment déployer une application sur Cloud Run ?",
            height=100,
            label_visibility="collapsed"
        )
        
        # Action buttons
        col_ask, col_clear = st.columns([1, 1])
        
        with col_ask:
            ask_button = st.button("🚀 Poser la question", type="primary", use_container_width=True)
        
        with col_clear:
            if st.button("🗑️ Effacer l'historique", use_container_width=True):
                st.session_state.conversation_history = []
                st.success("Historique effacé!")
                st.rerun()
    
    with col2:
        # Example questions
        st.markdown("### 💡 Questions d'exemple")
        example_questions = [
            "Comment packager un modèle pour Cloud Run ?",
            "Configuration Docker pour Python",
            "API endpoints disponibles",
            "Installation des dépendances",
            "Déploiement avec CI/CD"
        ]
        
        for eq in example_questions:
            if st.button(f"💬 {eq[:30]}...", key=f"example_{hash(eq)}", use_container_width=True):
                question = eq
                ask_button = True
    
    # Process question
    if ask_button and question.strip():
        with st.spinner("🤔 Traitement de votre question..."):
            # Process question
            result = asyncio.run(process_question_async(question, filters))
            
            if result["success"]:
                response = result["response"]
                
                # Display response
                st.markdown("---")
                display_response(response, filters)
                
                # Add to conversation history
                st.session_state.conversation_history.append({
                    "question": question,
                    "answer": response.answer,
                    "sources": response.sources,
                    "response_time": response.response_time,
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "trace_id": response.trace_id
                })
                
            else:
                st.error(f"❌ Erreur: {result['error']}")
    
    elif ask_button:
        st.warning("⚠️ Veuillez saisir une question.")
    
    # Conversation history
    if st.session_state.conversation_history:
        st.markdown("---")
        display_conversation_history()
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #666; padding: 1rem;">
        DocPilot v1.0 - Assistant RAG avec Vertex AI et pgvector<br>
        🔗 <a href="https://github.com" target="_blank">GitHub</a> | 
        📧 <a href="mailto:support@docpilot.ai">Support</a> |
        📖 <a href="/docs" target="_blank">Documentation</a>
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()