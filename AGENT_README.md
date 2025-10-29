# DocPilot Agent - Assistant Conversationnel RAG

## Jour 5 : Agent + CLI/mini-UI & Qualité

DocPilot Agent est un assistant conversationnel intelligent qui utilise votre documentation GitHub et Google Drive pour répondre à vos questions. Il consomme le service MCP (Model Context Protocol) pour effectuer des recherches sémantiques et utilise des LLM (OpenAI ou Vertex AI) pour générer des réponses contextualisées.

## 🚀 Fonctionnalités

### 🤖 Agent Conversationnel
- **Recherche sémantique** : Utilise le service MCP pour rechercher dans vos documents
- **Prompt RAG** : Construit des prompts enrichis avec le contexte pertinent
- **Citations** : Fournit des sources avec liens vers les documents originaux
- **Fallback intelligent** : Répond "je ne sais pas" quand l'information n'est pas disponible
- **Support multi-LLM** : Compatible OpenAI et Vertex AI

### 🔧 Interfaces d'utilisation
- **CLI moderne** : Interface en ligne de commande avec Typer et Rich
- **Interface web** : Application Streamlit intuitive
- **Filtres avancés** : Par source (GitHub/Drive), repository, type MIME
- **Paramètres configurables** : top-k, seuil de similarité

### 📊 Observabilité & Qualité
- **Logs structurés** : Avec trace_id, latences, métriques détaillées
- **Métriques temps réel** : Temps de réponse, chunks analysés, taux de succès
- **Gestion d'erreurs** : Fallback gracieux avec logging des erreurs
- **Session tracking** : Suivi des conversations et statistiques

## 📦 Installation

```bash
# Cloner le repository
git clone <your-repo>
cd docpilot

# Installer les dépendances avec uv
uv sync

# Ou avec pip
pip install -e .
```

## ⚙️ Configuration

### Variables d'environnement

```bash
# Service MCP (requis)
export MCP_URL="http://localhost:8000"

# Pour OpenAI (par défaut)
export OPENAI_API_KEY="your_openai_api_key"

# Pour Vertex AI
export PROJECT_ID="your_gcp_project_id"
export LLM_PROVIDER="vertex"

# Optionnel : logs
export LOG_LEVEL="INFO"
```

### Fichier .env
Créez un fichier `.env` dans le répertoire racine :

```env
MCP_URL=http://localhost:8000
OPENAI_API_KEY=your_openai_api_key
PROJECT_ID=your_gcp_project_id
LLM_PROVIDER=openai
```

## 🖥️ Utilisation CLI

### Commandes de base

```bash
# Question simple
python cli.py ask "Comment déployer une application sur Cloud Run ?"

# Avec filtres
python cli.py ask "Configuration Docker" --source github --top-k 5

# Filtrage par type de fichier
python cli.py ask "API endpoints" --mime text/markdown --threshold 0.8

# Filtrage par repository
python cli.py ask "Installation" --repo mon-projet --top-k 10

# Format JSON pour intégration
python cli.py ask "Documentation" --format json

# Utiliser Vertex AI
python cli.py ask "Machine learning" --llm vertex --project-id my-project
```

### Options disponibles

```bash
# Afficher l'aide
python cli.py ask --help

# Vérifier l'état du système
python cli.py health

# Configuration actuelle
python cli.py config --show
```

### Exemples complets

```bash
# Recherche dans GitHub uniquement
python cli.py ask "Comment configurer le CI/CD ?" \
  --source github \
  --top-k 5 \
  --threshold 0.7 \
  --verbose

# Recherche dans Google Drive
python cli.py ask "Processus d'onboarding" \
  --source gdrive \
  --mime application/pdf \
  --top-k 3

# Recherche spécifique à un repository
python cli.py ask "API documentation" \
  --repo my-api-project \
  --mime text/markdown \
  --format json
```

## 🌐 Interface Web Streamlit

### Lancement

```bash
# Démarrer l'interface web
streamlit run streamlit_app.py

# Avec port personnalisé
streamlit run streamlit_app.py --server.port 8501
```

### Fonctionnalités

- **Interface intuitive** : Questions/réponses en temps réel
- **Filtres visuels** : Configuration par interface graphique
- **Métriques en direct** : Temps de réponse, chunks analysés
- **Historique** : Conversations précédentes
- **Export** : Possibilité d'exporter les réponses
- **Health check** : Vérification de l'état du système

## 🧪 Tests

### Test complet du système

```bash
# Exécuter la suite de tests
python test_agent.py
```

### Tests manuels

```bash
# Test de santé du système
python cli.py health --verbose

# Test avec questions d'exemple
python cli.py ask "Comment déployer sur Cloud Run ?" --source github
python cli.py ask "Configuration Docker" --mime text/markdown
python cli.py ask "API endpoints" --top-k 7
```

## 📊 Observabilité

### Logs structurés

L'agent génère des logs structurés avec :
- **trace_id** : Identifiant unique par requête
- **Timings** : Latences détaillées (search, LLM, total)
- **Métriques** : Chunks scannés, sources utilisées
- **Filtres** : Paramètres de recherche appliqués
- **Erreurs** : Gestion et logging des erreurs

### Métriques de session

```python
# Accès aux statistiques via l'API
stats = agent.get_observability_stats()
print(f"Taux de succès: {stats['session_stats']['success_rate']:.1%}")
print(f"Temps moyen: {stats['session_stats']['avg_response_time']:.3f}s")
```

### Exemple de logs

```json
{
  "timestamp": "2024-10-28T10:30:00Z",
  "event": "request_completed",
  "trace_id": "abc123-def456",
  "question": "Comment déployer sur Cloud Run ?",
  "response_time": 2.456,
  "search_time": 0.123,
  "llm_time": 2.100,
  "chunks_scanned": 8,
  "fallback_used": false,
  "source_filter": "github",
  "top_k_requested": 10
}
```

## 🔧 Architecture

### Composants principaux

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLI/Web UI    │────│  DocPilot Agent │────│   MCP Service   │
│   (Interface)   │    │     (Core)      │    │   (Backend)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │
                        ┌──────┴──────┐
                        │             │
                  ┌─────────┐   ┌─────────┐
                  │ OpenAI  │   │ Vertex  │
                  │   API   │   │   AI    │
                  └─────────┘   └─────────┘
```

### Flux de traitement

1. **Réception** : Question utilisateur via CLI/Web
2. **Filtrage** : Application des filtres de recherche
3. **Recherche** : Appel au service MCP pour recherche sémantique
4. **Contextualisation** : Construction du prompt RAG
5. **Génération** : Appel au LLM pour génération de réponse
6. **Post-traitement** : Extraction des sources et formatage
7. **Logging** : Enregistrement des métriques et traces

## 🛠️ Développement

### Structure du projet

```
docpilot/
├── knowledge_copilot/
│   ├── agent.py              # Agent principal
│   ├── observability.py      # Logs et métriques
│   └── __init__.py
├── cli.py                    # Interface CLI
├── streamlit_app.py          # Interface web
├── test_agent.py             # Tests
├── main.py                   # API MCP (existant)
└── pyproject.toml            # Configuration
```

### Ajout de nouvelles fonctionnalités

```python
# Exemple : nouveau provider LLM
class CustomLLMProvider(LLMProvider):
    async def generate_response(self, prompt: str) -> str:
        # Votre implémentation
        pass

# Utilisation
agent = create_agent(
    mcp_url="http://localhost:8000",
    llm_provider=CustomLLMProvider()
)
```

## 📈 Performance

### Optimisations

- **Cache** : Mise en cache des embeddings et résultats
- **Parallélisation** : Recherche et traitement parallèles
- **Streaming** : Réponses progressives pour les longues requêtes
- **Pagination** : Gestion efficace des gros volumes

### Métriques typiques

- **Temps de recherche** : 100-500ms
- **Temps LLM** : 1-3s (selon le modèle)
- **Temps total** : 1.5-4s
- **Précision** : 85-95% (selon la qualité des documents)

## 🔒 Sécurité

### Bonnes pratiques

- **Variables d'environnement** : Clés API sécurisées
- **Validation** : Validation des entrées utilisateur
- **Rate limiting** : Protection contre l'abus
- **Logging** : Pas de données sensibles dans les logs

## 📚 Exemples d'usage

### Cas d'usage typiques

1. **Documentation technique**
   ```bash
   python cli.py ask "Comment configurer SSL/TLS ?" --source github
   ```

2. **Procédures métier**
   ```bash
   python cli.py ask "Processus d'approbation budget" --source gdrive
   ```

3. **API Reference**
   ```bash
   python cli.py ask "Endpoint authentification" --mime text/markdown
   ```

4. **Troubleshooting**
   ```bash
   python cli.py ask "Erreur 500 API" --repo production-logs
   ```

## 🐛 Dépannage

### Problèmes courants

**Service MCP inaccessible**
```bash
# Vérifier l'état
python cli.py health

# Vérifier la connectivité
curl http://localhost:8000/health
```

**Erreurs d'authentification LLM**
```bash
# Vérifier les variables d'environnement
echo $OPENAI_API_KEY
echo $PROJECT_ID
```

**Pas de résultats pertinents**
```bash
# Réduire le seuil de similarité
python cli.py ask "votre question" --threshold 0.5

# Augmenter le top-k
python cli.py ask "votre question" --top-k 20
```

## 🤝 Contribution

Pour contribuer au projet :

1. Fork le repository
2. Créer une branche feature
3. Ajouter des tests pour les nouvelles fonctionnalités
4. Vérifier que tous les tests passent
5. Créer une Pull Request

## 📄 Licence

MIT License - Voir le fichier LICENSE pour plus de détails.

---

**DocPilot v1.0** - Assistant RAG avec Vertex AI et pgvector  
🚁 *Votre copilote pour naviguer dans votre documentation*