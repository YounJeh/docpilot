#!/usr/bin/env python3
"""
Script d'insertion des embeddings pour DocPilot
Synchronise et indexe les documents depuis Google Drive et GitHub
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import typer
from loguru import logger
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Ajouter le chemin du projet pour les imports
sys.path.append(str(Path(__file__).parent))

# Import des services
from knowledge_copilot.rag_service import create_rag_service
from knowledge_copilot.connectors.gdrive_sync import sync_drive
from knowledge_copilot.connectors.github_sync import sync_github

app = typer.Typer(help="Script d'insertion d'embeddings DocPilot")


def setup_logger(log_level: str = "INFO") -> None:
    """Configure le logger"""
    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )


def validate_environment() -> Dict[str, str]:
    """Valide les variables d'environnement requises"""
    required_vars = {
        "PROJECT_ID": "Google Cloud Project ID",
        "GDRIVE_FOLDER_ID": "Google Drive folder ID (optionnel)",
        "GH_REPOS": "Liste des repos GitHub (optionnel)",
    }
    
    missing_vars = []
    env_vars = {}
    
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value and var in ["PROJECT_ID"]:  # Variables obligatoires
            missing_vars.append(f"{var} ({description})")
        else:
            env_vars[var] = value or ""
    
    if missing_vars:
        logger.error(f"Variables d'environnement manquantes: {', '.join(missing_vars)}")
        raise typer.Exit(1)
    
    # Variables optionnelles avec valeurs par défaut
    env_vars.update({
        "GDRIVE_FOLDER_ID": os.getenv("GDRIVE_FOLDER_ID", ""),
        "GH_REPOS": os.getenv("GH_REPOS", ""),
        "GH_DEFAULT_BRANCH": os.getenv("GH_DEFAULT_BRANCH", "main"),
        "MAX_FILE_MB": os.getenv("MAX_FILE_MB", "10"),
    })
    
    return env_vars


def sync_gdrive_documents(
    folder_id: Optional[str] = None,
    max_tokens: int = 1000,
    overlap_tokens: int = 100
) -> Dict[str, Any]:
    """Synchronise les documents depuis Google Drive"""
    if not folder_id:
        folder_id = os.getenv("GDRIVE_FOLDER_ID")
        
    if not folder_id:
        logger.warning("GDRIVE_FOLDER_ID non défini, skipping Google Drive sync")
        return {"documents": [], "chunks": [], "documents_count": 0, "chunks_count": 0}
    
    logger.info(f"Synchronisation Google Drive (folder: {folder_id})")
    
    try:
        result = sync_drive(
            folder_id=folder_id,
            max_tokens=max_tokens,
            overlap=overlap_tokens
        )
        
        logger.info(
            f"Google Drive sync terminée: {result['documents_count']} documents, "
            f"{result['chunks_count']} chunks"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors de la synchronisation Google Drive: {e}")
        raise


def sync_github_repositories(
    repos: Optional[List[str]] = None,
    branch: Optional[str] = None,
    max_tokens: int = 1000,
    overlap_tokens: int = 100
) -> Dict[str, Any]:
    """Synchronise les documents depuis les repositories GitHub"""
    if not repos:
        repos_str = os.getenv("GH_REPOS", "")
        repos = [r.strip() for r in repos_str.split(",") if r.strip()] if repos_str else []
    
    if not repos:
        logger.warning("GH_REPOS non défini, skipping GitHub sync")
        return {"documents": [], "chunks": [], "documents_count": 0, "chunks_count": 0}
    
    branch = branch or os.getenv("GH_DEFAULT_BRANCH", "main")
    
    logger.info(f"Synchronisation GitHub (repos: {repos}, branch: {branch})")
    
    try:
        result = sync_github(repos=repos, branch=branch)
        
        logger.info(
            f"GitHub sync terminée: {result['documents_count']} documents, "
            f"{result['chunks_count']} chunks"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Erreur lors de la synchronisation GitHub: {e}")
        raise


def insert_documents_to_rag(
    rag_service,
    documents: List[Dict[str, Any]],
    batch_size: int = 5
) -> List[int]:
    """Insert les documents dans le service RAG"""
    if not documents:
        logger.info("Aucun document à insérer")
        return []
    
    logger.info(f"Insertion de {len(documents)} documents en batches de {batch_size}")
    
    try:
        # Préparer les documents pour l'insertion
        doc_list = []
        for doc in documents:
            doc_data = {
                "content": doc["raw_text"],
                "source": doc["source"],
                "uri": doc["uri"],
                "title": doc["title"],
                "mime": doc["mime"],
                "metadata": {
                    **doc.get("metadata", {}),
                    "content_hash": doc["content_hash"],
                    "inserted_at": datetime.utcnow().isoformat() + "Z"
                }
            }
            doc_list.append(doc_data)
        
        # Insertion par batches
        document_ids = rag_service.batch_index_documents(
            documents=doc_list,
            batch_size=batch_size
        )
        
        logger.info(f"Insertion terminée: {len(document_ids)} documents indexés")
        return document_ids
        
    except Exception as e:
        logger.error(f"Erreur lors de l'insertion des documents: {e}")
        raise


@app.command()
def run(
    gdrive_folder_id: Optional[str] = typer.Option(None, "--gdrive-folder", help="Google Drive folder ID"),
    github_repos: Optional[str] = typer.Option(None, "--github-repos", help="Repos GitHub séparés par des virgules"),
    github_branch: Optional[str] = typer.Option(None, "--github-branch", help="Branche GitHub à utiliser"),
    batch_size: int = typer.Option(5, "--batch-size", help="Taille des batches pour l'insertion"),
    max_tokens: int = typer.Option(1000, "--max-tokens", help="Taille max des chunks en tokens"),
    overlap_tokens: int = typer.Option(100, "--overlap-tokens", help="Overlap entre les chunks"),
    log_level: str = typer.Option("INFO", "--log-level", help="Niveau de log"),
    save_preview: Optional[str] = typer.Option(None, "--save-preview", help="Sauvegarder un aperçu JSON"),
    sources: str = typer.Option("all", "--sources", help="Sources à synchroniser: all, gdrive, github")
):
    """
    Lance la synchronisation et l'insertion des embeddings
    
    Sources disponibles:
    - all: Synchronise Google Drive et GitHub
    - gdrive: Synchronise uniquement Google Drive  
    - github: Synchronise uniquement GitHub
    """
    setup_logger(log_level)
    
    logger.info("=== DocPilot - Insertion d'embeddings ===")
    
    # Validation de l'environnement
    try:
        env_vars = validate_environment()
        logger.info("Variables d'environnement validées")
    except Exception as e:
        logger.error(f"Erreur de validation: {e}")
        raise typer.Exit(1)
    
    # Initialisation du service RAG
    try:
        logger.info("Initialisation du service RAG...")
        rag_service = create_rag_service(project_id=env_vars["PROJECT_ID"])
        logger.info("Service RAG initialisé avec succès")
    except Exception as e:
        logger.error(f"Erreur d'initialisation du service RAG: {e}")
        raise typer.Exit(1)
    
    # Collecte des documents
    all_documents = []
    sync_results = {}
    
    # Google Drive
    if sources in ["all", "gdrive"]:
        try:
            gdrive_result = sync_gdrive_documents(
                folder_id=gdrive_folder_id,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens
            )
            all_documents.extend(gdrive_result["documents"])
            sync_results["gdrive"] = gdrive_result
        except Exception as e:
            logger.error(f"Échec sync Google Drive: {e}")
            if sources == "gdrive":
                raise typer.Exit(1)
    
    # GitHub
    if sources in ["all", "github"]:
        try:
            repos_list = None
            if github_repos:
                repos_list = [r.strip() for r in github_repos.split(",")]
            
            github_result = sync_github_repositories(
                repos=repos_list,
                branch=github_branch,
                max_tokens=max_tokens,
                overlap_tokens=overlap_tokens
            )
            all_documents.extend(github_result["documents"])
            sync_results["github"] = github_result
        except Exception as e:
            logger.error(f"Échec sync GitHub: {e}")
            if sources == "github":
                raise typer.Exit(1)
    
    # Résumé de la collecte
    total_docs = len(all_documents)
    logger.info(f"Documents collectés: {total_docs}")
    
    if total_docs == 0:
        logger.warning("Aucun document à traiter")
        return
    
    # Déduplication par content_hash
    seen_hashes = set()
    unique_documents = []
    for doc in all_documents:
        if doc["content_hash"] not in seen_hashes:
            seen_hashes.add(doc["content_hash"])
            unique_documents.append(doc)
    
    dedup_count = total_docs - len(unique_documents)
    if dedup_count > 0:
        logger.info(f"Déduplication: {dedup_count} documents dupliqués supprimés")
    
    # Insertion dans RAG
    try:
        start_time = time.time()
        document_ids = insert_documents_to_rag(
            rag_service=rag_service,
            documents=unique_documents,
            batch_size=batch_size
        )
        
        duration = time.time() - start_time
        logger.info(f"Insertion terminée en {duration:.2f}s")
        
        # Statistiques finales
        stats = rag_service.get_stats()
        logger.info(f"Statistiques RAG: {stats}")
        
    except Exception as e:
        logger.error(f"Erreur lors de l'insertion: {e}")
        raise typer.Exit(1)
    
    # Sauvegarde de l'aperçu si demandé
    if save_preview:
        preview_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "sync_results": sync_results,
            "total_documents_collected": total_docs,
            "unique_documents_inserted": len(unique_documents),
            "document_ids": document_ids,
            "rag_stats": stats,
            "parameters": {
                "sources": sources,
                "batch_size": batch_size,
                "max_tokens": max_tokens,
                "overlap_tokens": overlap_tokens,
                "gdrive_folder_id": gdrive_folder_id,
                "github_repos": github_repos,
                "github_branch": github_branch,
            }
        }
        
        Path(save_preview).write_text(
            json.dumps(preview_data, ensure_ascii=False, indent=2)
        )
        logger.info(f"Aperçu sauvegardé: {save_preview}")
    
    logger.info("=== Insertion d'embeddings terminée avec succès ===")


@app.command()
def stats():
    """Affiche les statistiques du système RAG"""
    setup_logger()
    
    try:
        env_vars = validate_environment()
        rag_service = create_rag_service(project_id=env_vars["PROJECT_ID"])
        
        stats = rag_service.get_stats()
        
        logger.info("=== Statistiques DocPilot RAG ===")
        for key, value in stats.items():
            logger.info(f"{key}: {value}")
            
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats: {e}")
        raise typer.Exit(1)


@app.command()
def test_search(
    query: str = typer.Argument(..., help="Requête de recherche"),
    limit: int = typer.Option(5, "--limit", help="Nombre de résultats"),
    threshold: Optional[float] = typer.Option(None, "--threshold", help="Seuil de similarité")
):
    """Test de recherche sémantique"""
    setup_logger()
    
    try:
        env_vars = validate_environment()
        rag_service = create_rag_service(project_id=env_vars["PROJECT_ID"])
        
        logger.info(f"Recherche: '{query}'")
        
        results = rag_service.search(
            query=query,
            limit=limit,
            similarity_threshold=threshold
        )
        
        logger.info(f"Trouvé {len(results)} résultats:")
        
        for i, result in enumerate(results, 1):
            logger.info(f"\n--- Résultat {i} ---")
            logger.info(f"Score: {result.get('similarity_score', 0):.3f}")
            logger.info(f"Source: {result['document']['source']}")
            logger.info(f"Titre: {result['document']['title']}")
            logger.info(f"Texte: {result['text'][:200]}...")
            
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {e}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()