# Knowledge Copilot MCP Server

🚀 Un serveur MCP (Model Context Protocol) basé sur FastAPI qui fournit des capacités de recherche sémantique et de synchronisation pour vos documents GitHub et Google Drive.

## ✨ Fonctionnalités

- **🔍 Recherche sémantique** : Recherche vectorielle avec Vertex AI embeddings
- **🔄 Sync automatique** : Synchronisation programmée avec GitHub et Google Drive  
- **🛡️ Sécurisé** : Authentification API key et gestion des secrets avec Google Secret Manager
- **☁️ Cloud Native** : Déployé sur Google Cloud Run avec Cloud SQL PostgreSQL
- **🔗 MCP Compatible** : Endpoints conformes au protocole MCP
- **📊 Monitoring** : Logs centralisés et health checks

## 🚀 Déploiement rapide

```bash
# Clone le projet
git clone <your-repo>
cd docpilot

# Déploiement interactif
./quickstart.sh

# Ou déploiement automatisé
PROJECT_ID=your-project ./quickstart.sh --auto
```

## 📋 Prérequis

- **Google Cloud SDK** avec authentification active
- **Docker** pour la containerisation
- **Projet GCP** avec facturation activée
- **GitHub Personal Access Token** pour accès aux repos
- **Service Account Google** pour Google Drive (optionnel)

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub Repos  │    │  Google Drive   │    │   MCP Client    │
│                 │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
         ┌─────────────────────────▼─────────────────────────┐
         │            Cloud Run (FastAPI)                   │
         │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐│
         │  │     Sync    │  │   Search    │  │   Webhook   ││
         │  │   Service   │  │   Service   │  │   Handler   ││
         │  └─────────────┘  └─────────────┘  └─────────────┘│
         └─────────────────────────┬─────────────────────────┘
                                   │
         ┌─────────────────────────▼─────────────────────────┐
         │           Cloud SQL PostgreSQL + pgvector        │
         └───────────────────────────────────────────────────┘
```

## 🔧 Configuration

### Variables d'environnement

```bash
# Authentication
API_TOKEN=your-secure-api-token
GH_PAT=your-github-personal-access-token
GH_WEBHOOK_SECRET=your-webhook-secret

# Google Cloud
PROJECT_ID=your-gcp-project-id
DATABASE_URL=postgresql://user:pass@/db?host=/cloudsql/instance

# Embeddings
EMBED_PROVIDER=vertex
EMBED_MODEL=text-embedding-004

# Sources
GH_REPOS=org/repo1,org/repo2
GDRIVE_FOLDER_ID=your-drive-folder-id
```

### Endpoints MCP

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/mcp/tools` | GET | Description des outils MCP |
| `/mcp/search_documents` | POST | Recherche sémantique |
| `/mcp/list_documents` | GET | Liste des documents indexés |
| `/sync_sources` | POST | Synchronisation manuelle |
| `/webhook/github` | POST | Webhook GitHub |
| `/health` | GET | Health check |

### Authentification

Toutes les requêtes nécessitent l'en-tête :
```
X-API-KEY: your-api-token
```

## 📖 Utilisation

### Recherche de documents

```bash
curl -X POST \
  -H "X-API-KEY: $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning algorithms",
    "limit": 10,
    "similarity_threshold": 0.7
  }' \
  https://your-service-url/mcp/search_documents
```

### Synchronisation manuelle

```bash
curl -X POST \
  -H "X-API-KEY: $API_TOKEN" \
  https://your-service-url/sync_sources
```

## 🛠️ Scripts de gestion

| Script | Description |
|--------|-------------|
| `quickstart.sh` | Déploiement interactif complet |
| `deploy.sh` | Déploiement Cloud Run |
| `setup-secrets.sh` | Configuration des secrets |
| `setup-scheduler.sh` | Configuration du resync automatique |
| `validate.sh` | Validation locale avant déploiement |

## 📊 Monitoring

```bash
# Logs du service
gcloud logs read --service=knowledge-copilot --region=europe-west1

# Status du scheduler
./setup-scheduler.sh status

# Health check
curl -H "X-API-KEY: $API_TOKEN" https://your-service-url/health
```

## 🔄 Resync automatique

Le système synchronise automatiquement vos sources :
- **Fréquence** : Toutes les 3 heures par défaut
- **Webhook GitHub** : Resync immédiat sur push (optionnel)
- **Gestion** : Cloud Scheduler

```bash
# Modifier la fréquence (toutes les 6 heures)
./setup-scheduler.sh --schedule "0 */6 * * *"

# Pause/reprise
./setup-scheduler.sh pause
./setup-scheduler.sh resume
```

## 🛡️ Sécurité

- ✅ **API Key** obligatoire pour tous les endpoints
- ✅ **Secrets** gérés par Google Secret Manager  
- ✅ **Cloud SQL** accessible uniquement via Unix socket
- ✅ **IAM** avec permissions minimales
- ✅ **Webhook** avec validation de signature GitHub

## 💰 Coûts estimés

Pour un usage modéré (quelques syncs par jour) :
- **Cloud Run** : ~5-10€/mois
- **Cloud SQL f1-micro** : ~10€/mois
- **Vertex AI embeddings** : ~2-5€/mois
- **Total** : ~20€/mois

## 📚 Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Guide de déploiement détaillé
- [API Examples](examples/) - Exemples d'utilisation des endpoints
- [Troubleshooting](DEPLOYMENT.md#troubleshooting) - Résolution des problèmes courants

## 🤝 Contribution

```bash
# Setup développement local
git clone <repo>
cd docpilot
pip install -e .

# Validation avant commit
./validate.sh

# Tests
python -m pytest test_mcp_server.py -v
```

## 📄 Licence

MIT License - voir [LICENSE](LICENSE) pour les détails.