#!/usr/bin/env python3
"""
Script de test simple pour valider les composants d'insertion d'embeddings
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Charger l'environnement
load_dotenv()

# Ajouter le chemin du projet
sys.path.append(str(Path(__file__).parent))

def test_environment():
    """Test des variables d'environnement"""
    print("=== Test des variables d'environnement ===")
    
    required = ["PROJECT_ID"]
    optional = ["GDRIVE_FOLDER_ID", "GH_REPOS", "GOOGLE_APPLICATION_CREDENTIALS"]
    
    for var in required:
        value = os.getenv(var)
        print(f"✓ {var}: {'✓ Défini' if value else '✗ MANQUANT'}")
    
    for var in optional:
        value = os.getenv(var)
        print(f"○ {var}: {'✓ Défini' if value else '○ Non défini'}")

def test_imports():
    """Test des imports"""
    print("\n=== Test des imports ===")
    
    try:
        from knowledge_copilot.rag_service import create_rag_service
        print("✓ RAG service import - OK")
    except Exception as e:
        print(f"✗ RAG service import - ERREUR: {e}")
        return False
    
    try:
        from knowledge_copilot.connectors.gdrive_sync import sync_drive
        print("✓ Google Drive sync import - OK")
    except Exception as e:
        print(f"✗ Google Drive sync import - ERREUR: {e}")
        return False
    
    try:
        from knowledge_copilot.connectors.github_sync import sync_github
        print("✓ GitHub sync import - OK")
    except Exception as e:
        print(f"✗ GitHub sync import - ERREUR: {e}")
        return False
    
    return True

def test_rag_service():
    """Test d'initialisation du service RAG"""
    print("\n=== Test du service RAG ===")
    
    project_id = os.getenv("PROJECT_ID")
    if not project_id:
        print("✗ PROJECT_ID manquant, impossible de tester le service RAG")
        return False
    
    try:
        from knowledge_copilot.rag_service import create_rag_service
        rag_service = create_rag_service(project_id=project_id)
        print("✓ Service RAG initialisé avec succès")
        
        # Test des stats
        stats = rag_service.get_stats()
        print(f"✓ Stats RAG: {stats}")
        return True
        
    except Exception as e:
        print(f"✗ Erreur d'initialisation du service RAG: {e}")
        return False

def simple_insert_workflow():
    """Test d'insertion simple"""
    print("\n=== Test d'insertion simple ===")
    
    project_id = os.getenv("PROJECT_ID")
    if not project_id:
        print("✗ PROJECT_ID manquant")
        return False
    
    try:
        from knowledge_copilot.rag_service import create_rag_service
        
        # Initialiser le service
        rag_service = create_rag_service(project_id=project_id)
        
        # Document de test
        test_doc = {
            "content": "Ceci est un document de test pour valider l'insertion d'embeddings dans DocPilot. Il contient du texte simple pour tester le chunking et l'indexation.",
            "source": "test",
            "uri": "test://simple_doc",
            "title": "Document de test",
            "mime": "text/plain",
            "metadata": {"test": True, "created_by": "test_script"}
        }
        
        # Insertion
        doc_id = rag_service.index_document(**test_doc)
        print(f"✓ Document de test inséré avec ID: {doc_id}")
        
        # Test de recherche
        results = rag_service.search("document test", limit=3)
        print(f"✓ Recherche effectuée, {len(results)} résultats trouvés")
        
        if results:
            print(f"  Premier résultat: score={results[0].get('similarity_score', 0):.3f}")
        
        return True
        
    except Exception as e:
        print(f"✗ Erreur lors du test d'insertion: {e}")
        return False

def main():
    """Fonction principale de test"""
    print("DocPilot - Test des composants d'insertion d'embeddings")
    print("=" * 60)
    
    # Tests séquentiels
    test_environment()
    
    if not test_imports():
        print("\n❌ Échec des imports - arrêt des tests")
        return 1
    
    if not test_rag_service():
        print("\n❌ Échec du test RAG service")
        return 1
    
    if not simple_insert_workflow():
        print("\n❌ Échec du test d'insertion")
        return 1
    
    print("\n✅ Tous les tests sont passés avec succès!")
    print("\nVous pouvez maintenant utiliser le script insert_embeddings.py")
    return 0

if __name__ == "__main__":
    exit(main())