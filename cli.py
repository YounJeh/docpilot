"""
DocPilot CLI - Interface en ligne de commande pour l'agent
Jour 5: Agent + CLI/mini-UI & Qualité
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown
from loguru import logger

# Add current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from knowledge_copilot.agent import create_agent, SearchFilter

# Initialize Typer app and Rich console
app = typer.Typer(
    name="docpilot",
    help="DocPilot - Assistant conversationnel pour votre documentation GitHub/Drive",
    add_completion=False
)
console = Console()

# Global configuration
CONFIG = {
    "mcp_url": "http://localhost:8000",
    "llm_provider": "vertex",
    "project_id": None,
    "openai_api_key": None,
    "verbose": False
}


def setup_logging(verbose: bool = False):
    """Configure logging"""
    if verbose:
        logger.remove()
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="DEBUG"
        )
    else:
        logger.remove()
        logger.add(sys.stderr, level="WARNING")


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question à poser à l'assistant"),
    source: Optional[str] = typer.Option(
        None, 
        "--source", "-s",
        help="Filtrer par source (github|gdrive)"
    ),
    repo: Optional[str] = typer.Option(
        None,
        "--repo", "-r", 
        help="Filtrer par repository GitHub spécifique"
    ),
    mime: Optional[str] = typer.Option(
        None,
        "--mime", "-m",
        help="Filtrer par type MIME (ex: text/markdown, application/pdf)"
    ),
    top_k: int = typer.Option(
        10,
        "--top-k", "-k",
        help="Nombre maximum de chunks à récupérer",
        min=1,
        max=50
    ),
    threshold: float = typer.Option(
        0.7,
        "--threshold", "-t",
        help="Seuil de similarité minimum",
        min=0.0,
        max=1.0
    ),
    mcp_url: Optional[str] = typer.Option(
        None,
        "--mcp-url",
        help="URL du service MCP",
        envvar="MCP_URL"
    ),
    llm_provider: str = typer.Option(
        "vertex",
        "--llm",
        help="Fournisseur LLM (vertex|openai)"
    ),
    project_id: Optional[str] = typer.Option(
        None,
        "--project-id",
        help="Project ID Google Cloud (pour Vertex AI)",
        envvar="PROJECT_ID"
    ),
    openai_key: Optional[str] = typer.Option(
        None,
        "--openai-key",
        help="Clé API OpenAI",
        envvar="OPENAI_API_KEY"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Mode verbose avec logs détaillés"
    ),
    format_output: str = typer.Option(
        "rich",
        "--format", "-f",
        help="Format de sortie (rich|json|plain)"
    )
):
    """Poser une question à l'assistant DocPilot"""
    
    # Setup logging
    setup_logging(verbose)
    
    # Update configuration
    CONFIG.update({
        "mcp_url": mcp_url or CONFIG["mcp_url"],
        "llm_provider": llm_provider,
        "project_id": project_id or CONFIG["project_id"],
        "openai_api_key": openai_key or CONFIG["openai_api_key"],
        "verbose": verbose
    })
    
    # Create search filters
    filters = SearchFilter(
        source=source,
        repo=repo,
        mime=mime,
        top_k=top_k,
        similarity_threshold=threshold
    )
    
    # Run the async query
    asyncio.run(_process_question(question, filters, format_output))


async def _process_question(question: str, filters: SearchFilter, format_output: str):
    """Process question asynchronously"""
    
    try:
        # Create agent
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("Initialisation de l'agent...", total=None)
            
            agent = create_agent(
                mcp_url=CONFIG["mcp_url"],
                llm_provider=CONFIG["llm_provider"],
                project_id=CONFIG["project_id"],
                openai_api_key=CONFIG["openai_api_key"]
            )
            
            progress.update(task, description="Traitement de la question...")
            
            # Ask the question
            response = await agent.ask(question, filters)
            
            progress.update(task, description="Formatage de la réponse...")
            
        # Display results based on format
        if format_output == "json":
            import json
            result = {
                "question": question,
                "answer": response.answer,
                "sources": response.sources,
                "metadata": {
                    "trace_id": response.trace_id,
                    "response_time": response.response_time,
                    "chunks_scanned": response.chunks_scanned,
                    "fallback_used": response.fallback_used
                }
            }
            console.print(json.dumps(result, indent=2, ensure_ascii=False))
            
        elif format_output == "plain":
            console.print(f"Question: {question}")
            console.print(f"Réponse: {response.answer}")
            console.print(f"Sources: {len(response.sources)} documents")
            console.print(f"Temps: {response.response_time:.3f}s")
            
        else:  # rich format (default)
            _display_rich_response(question, response, filters)
            
        # Close agent
        await agent.close()
        
    except Exception as e:
        console.print(f"[red]Erreur: {e}[/red]")
        if CONFIG["verbose"]:
            import traceback
            console.print(traceback.format_exc())
        raise typer.Exit(1)


def _display_rich_response(question: str, response, filters: SearchFilter):
    """Display response with rich formatting"""
    
    # Question panel
    console.print(Panel(
        f"[bold cyan]Question:[/bold cyan] {question}",
        title="DocPilot Assistant",
        border_style="cyan"
    ))
    
    # Response panel
    answer_content = response.answer
    if response.fallback_used:
        answer_content = f"[yellow]{answer_content}[/yellow]"
    
    console.print(Panel(
        Markdown(answer_content),
        title="Réponse",
        border_style="green" if not response.fallback_used else "yellow"
    ))
    
    # Sources table
    if response.sources:
        sources_table = Table(title="Sources", show_header=True, header_style="bold magenta")
        sources_table.add_column("#", style="dim", width=3)
        sources_table.add_column("Titre", style="bold")
        sources_table.add_column("Source", justify="center")
        sources_table.add_column("Similarité", justify="right")
        sources_table.add_column("URI", style="dim")
        
        for source in response.sources:
            sources_table.add_row(
                str(source["index"]),
                source["title"][:50] + "..." if len(source["title"]) > 50 else source["title"],
                source["source"],
                f"{source['similarity_score']:.3f}",
                source["uri"][:60] + "..." if len(source["uri"]) > 60 else source["uri"]
            )
        
        console.print(sources_table)
    
    # Metadata panel
    metadata_content = f"""[bold]Trace ID:[/bold] {response.trace_id}
[bold]Temps de réponse:[/bold] {response.response_time:.3f}s
[bold]Chunks analysés:[/bold] {response.chunks_scanned}
[bold]Top-k demandé:[/bold] {filters.top_k}
[bold]Seuil similarité:[/bold] {filters.similarity_threshold}
[bold]Fallback utilisé:[/bold] {'Oui' if response.fallback_used else 'Non'}"""
    
    if filters.source:
        metadata_content += f"\n[bold]Filtre source:[/bold] {filters.source}"
    if filters.repo:
        metadata_content += f"\n[bold]Filtre repo:[/bold] {filters.repo}"
    if filters.mime:
        metadata_content += f"\n[bold]Filtre MIME:[/bold] {filters.mime}"
    
    console.print(Panel(
        metadata_content,
        title="Métadonnées",
        border_style="dim"
    ))


@app.command()
def health(
    mcp_url: Optional[str] = typer.Option(
        None,
        "--mcp-url",
        help="URL du service MCP",
        envvar="MCP_URL"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Mode verbose"
    )
):
    """Vérifier l'état de santé du système"""
    
    setup_logging(verbose)
    
    CONFIG["mcp_url"] = mcp_url or CONFIG["mcp_url"]
    
    asyncio.run(_check_health())


async def _check_health():
    """Check system health asynchronously"""
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            progress.add_task("Vérification de l'état du système...", total=None)
            
            agent = create_agent(
                mcp_url=CONFIG["mcp_url"],
                llm_provider="vertex",  # Use vertex for health check
                project_id=CONFIG["project_id"] or "dummy"
            )
            
            health_status = await agent.health_check()
            await agent.close()
        
        # Display health status
        if health_status["status"] == "healthy":
            console.print("[green]✓ Système en bonne santé[/green]")
        else:
            console.print("[red]✗ Problème détecté[/red]")
        
        # Health details table
        health_table = Table(title="État du système", show_header=True)
        health_table.add_column("Service", style="bold")
        health_table.add_column("État")
        health_table.add_column("Détails", style="dim")
        
        # MCP service status
        mcp_status = health_status.get("mcp_service", {})
        mcp_health = mcp_status.get("status", "unknown")
        mcp_color = "green" if mcp_health == "healthy" else "red"
        
        health_table.add_row(
            "Service MCP",
            f"[{mcp_color}]{mcp_health}[/{mcp_color}]",
            CONFIG["mcp_url"]
        )
        
        # Agent status
        agent_status = health_status.get("agent", "unknown")
        agent_color = "green" if agent_status == "ready" else "red"
        
        health_table.add_row(
            "Agent DocPilot",
            f"[{agent_color}]{agent_status}[/{agent_color}]",
            f"LLM: {CONFIG['llm_provider']}"
        )
        
        console.print(health_table)
        
        # Show additional MCP stats if available
        if "stats" in mcp_status:
            stats = mcp_status["stats"]
            console.print(Panel(
                f"Documents indexés: {stats.get('total_documents', 'N/A')}\n"
                f"Chunks totaux: {stats.get('total_chunks', 'N/A')}\n"
                f"Base de données: {stats.get('database_info', {}).get('status', 'N/A')}",
                title="Statistiques MCP",
                border_style="blue"
            ))
        
    except Exception as e:
        console.print(f"[red]Erreur lors de la vérification: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def config(
    mcp_url: Optional[str] = typer.Option(None, help="URL du service MCP"),
    llm_provider: Optional[str] = typer.Option(None, help="Fournisseur LLM"),
    project_id: Optional[str] = typer.Option(None, help="Project ID Google Cloud"),
    show: bool = typer.Option(False, "--show", help="Afficher la configuration actuelle")
):
    """Configurer ou afficher la configuration"""
    
    if show:
        # Display current config
        config_table = Table(title="Configuration DocPilot", show_header=True)
        config_table.add_column("Paramètre", style="bold")
        config_table.add_column("Valeur", style="cyan")
        config_table.add_column("Source", style="dim")
        
        config_table.add_row(
            "MCP URL",
            CONFIG["mcp_url"],
            "MCP_URL env var" if os.getenv("MCP_URL") else "default"
        )
        
        config_table.add_row(
            "LLM Provider",
            CONFIG["llm_provider"],
            "default"
        )
        
        project_id_value = CONFIG["project_id"] or os.getenv("PROJECT_ID", "Non défini")
        config_table.add_row(
            "Project ID",
            project_id_value,
            "PROJECT_ID env var" if os.getenv("PROJECT_ID") else "not set"
        )
        
        openai_status = "Définie" if (CONFIG["openai_api_key"] or os.getenv("OPENAI_API_KEY")) else "Non définie"
        config_table.add_row(
            "OpenAI API Key",
            openai_status,
            "OPENAI_API_KEY env var" if os.getenv("OPENAI_API_KEY") else "not set"
        )
        
        console.print(config_table)
        
        # Show usage examples
        console.print(Panel(
            """[bold]Exemples d'utilisation:[/bold]

[cyan]# Question simple[/cyan]
docpilot ask "Comment déployer sur Cloud Run ?"

[cyan]# Avec filtres[/cyan]
docpilot ask "Configuration Docker" --source github --top-k 5

[cyan]# Filtrage par repository[/cyan]
docpilot ask "API endpoints" --repo myproject --mime text/markdown

[cyan]# Utiliser Vertex AI[/cyan]
docpilot ask "Machine learning" --llm vertex --project-id my-project

[cyan]# Format JSON pour intégration[/cyan]
docpilot ask "Installation" --format json""",
            title="Guide d'utilisation",
            border_style="blue"
        ))
    
    else:
        console.print("[yellow]Configuration interactive non implémentée.[/yellow]")
        console.print("Utilisez les variables d'environnement ou les options de ligne de commande.")


if __name__ == "__main__":
    app()