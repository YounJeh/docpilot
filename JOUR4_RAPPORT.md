# Jour 4 — MCP Server (Cloud Run) + Automations

**Date :** 28 octobre 2025  
**Objectif :** Exposer les tools MCP, déployer sur Cloud Run, sécuriser et planifier le resync automatique

## ✅ Livrables réalisés

### 🎯 Serveur MCP FastAPI

**Fichier principal :** `app.py`

- ✅ **Endpoints MCP complets** :
  - `GET /mcp/tools` - Description des outils disponibles
  - `POST /mcp/search_documents` - Recherche sémantique avec pagination
  - `GET /mcp/list_documents` - Inventaire des documents indexés
  - `POST /sync_sources` - Synchronisation GitHub + Google Drive
  - `POST /webhook/github` - Webhook pour reindex automatique sur push

- ✅ **Authentification robuste** :
  - Header `X-API-KEY` avec validation middleware
  - Signature GitHub webhook avec `X-Hub-Signature-256`
  - Gestion des secrets via Google Secret Manager

- ✅ **Validation et gestion d'erreurs** :
  - Modèles Pydantic pour validation des entrées
  - Gestion centralisée des erreurs avec codes HTTP appropriés
  - Logs structurés avec Loguru

### 🐳 Containerisation et déploiement

**Dockerfile optimisé** avec :
- Build multi-stage pour réduire la taille
- Utilisateur non-root pour la sécurité
- Health check intégré
- Variables d'environnement pour Cloud Run

**Scripts de déploiement** :
- `deploy.sh` - Déploiement automatisé Cloud Run avec Cloud SQL
- `setup-secrets.sh` - Configuration interactive des secrets
- `setup-scheduler.sh` - Cloud Scheduler pour resync automatique
- `quickstart.sh` - Déploiement one-shot interactif

### ☁️ Infrastructure Google Cloud

**Configuration Cloud Run** :
```bash
gcloud run deploy knowledge-copilot \
  --image gcr.io/PROJECT_ID/knowledge-copilot \
  --region=europe-west1 \
  --allow-unauthenticated=false \
  --set-secrets=GH_PAT=GH_PAT:latest,API_TOKEN=API_TOKEN:latest \
  --set-env-vars=PROJECT_ID=PROJECT_ID,EMBED_PROVIDER=vertex \
  --add-cloudsql-instances=PROJECT_ID:europe-west1:kc-postgres
```

**Cloud Scheduler** :
```bash
gcloud scheduler jobs create http kc-sync \
  --schedule="0 */3 * * *" \
  --uri="CLOUD_RUN_URL/sync_sources" \
  --http-method=POST \
  --headers="X-API-KEY=API_TOKEN"
```

**Connecteur Cloud SQL** :
- Connexion Unix socket `/cloudsql/PROJECT_ID:europe-west1:kc-postgres`
- Pas d'IP publique nécessaire
- Authentification via IAM

### 🔐 Sécurité et secrets

**Google Secret Manager** :
- `API_TOKEN` - Clé d'authentification API
- `GH_PAT` - Personal Access Token GitHub
- `GH_WEBHOOK_SECRET` - Secret de validation webhook
- `SQL_PASSWORD` - Mot de passe base de données

**IAM et permissions** :
- Service account avec permissions minimales
- Accès Cloud SQL via `roles/cloudsql.client`
- Vertex AI via `roles/aiplatform.user`
- Storage via `roles/storage.objectAdmin`

### 🔄 Automations

**Resync automatique** :
- **Fréquence** : Toutes les 3 heures via Cloud Scheduler
- **Webhook GitHub** : Reindex immédiat sur push (optionnel)
- **Gestion d'erreurs** : Retry automatique avec backoff exponentiel

**Background tasks** :
- Synchronisation en arrière-plan avec FastAPI BackgroundTasks
- Indexation batch des documents avec gestion d'erreurs
- Logs détaillés pour monitoring

## 🏗️ Architecture déployée

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                  Cloud Run Service                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│
│  │   FastAPI   │ │   MCP API   │ │     Webhook Handler     ││
│  │   Server    │ │  Endpoints  │ │    (GitHub Events)      ││
│  └─────────────┘ └─────────────┘ └─────────────────────────┘│
└─────────────────────────┬───────────────────────────────────┘
                          │ Unix Socket
┌─────────────────────────▼───────────────────────────────────┐
│              Cloud SQL PostgreSQL + pgvector               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  Cloud Scheduler                           │
│           (Trigger sync every 3 hours)                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              External Integrations                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────┐│
│  │   GitHub    │ │ Google      │ │      Vertex AI          ││
│  │   Repos     │ │ Drive       │ │    (Embeddings)         ││
│  └─────────────┘ └─────────────┘ └─────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## 📊 Endpoints exposés

### Endpoints MCP core

| Endpoint | Méthode | Auth | Description |
|----------|---------|------|-------------|
| `/mcp/tools` | GET | ✅ | Descriptif des outils MCP |
| `/mcp/search_documents` | POST | ✅ | Query → top-k results |
| `/mcp/list_documents` | GET | ✅ | Inventaire avec pagination |

### Endpoints de gestion

| Endpoint | Méthode | Auth | Description |
|----------|---------|------|-------------|
| `/sync_sources` | POST | ✅ | Sync GitHub + Drive |
| `/webhook/github` | POST | 🔐* | Auto-reindex sur push |
| `/health` | GET | ❌ | Health check |
| `/` | GET | ❌ | API documentation |

*🔐 Authentification par signature webhook

### Exemple d'utilisation

```bash
# Health check
curl https://service-url/health

# Recherche avec auth
curl -X POST \
  -H "X-API-KEY: $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "limit": 5}' \
  https://service-url/mcp/search_documents

# Synchronisation manuelle
curl -X POST \
  -H "X-API-KEY: $API_TOKEN" \
  https://service-url/sync_sources
```

## 🚀 Instructions de déploiement

### Déploiement rapide (one-shot)

```bash
# Clone et déploiement interactif
git clone <repo> && cd docpilot
./quickstart.sh
```

### Déploiement par étapes

```bash
# 1. Setup des secrets
./setup-secrets.sh --project YOUR_PROJECT_ID

# 2. Déploiement Cloud Run
./deploy.sh --project YOUR_PROJECT_ID --region europe-west

# Tester une requête : 
curl -s -X POST "https://knowledge-copilot-734xlg5n2q-ew.a.run.app/mcp/search_documents" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <API_TOKEN>" \
  -d '{"query": "python configuration", "limit": 3, "similarity_threshold": 0.7}' | python3 -m json.tool

# 3. Configuration du scheduler
./setup-scheduler.sh --project YOUR_PROJECT_ID
```

### Validation locale

```bash
# Tests et validation avant déploiement
./validate.sh
```

## 🔧 Configuration requise

### Variables d'environnement

```bash
# Obligatoires
API_TOKEN=secure-random-token-32chars
PROJECT_ID=your-gcp-project-id
DATABASE_URL=postgresql://postgres@/kcdb?host=/cloudsql/...

# Sources
GH_PAT=ghp_xxxxxxxxxxxx
GH_REPOS=org/repo1,org/repo2
GDRIVE_FOLDER_ID=1AbC2dEfGhIjKlM

# Optionnelles
GH_WEBHOOK_SECRET=webhook-secret
EMBED_MODEL=text-embedding-004
```

### Secrets Google Cloud

Créés automatiquement par `setup-secrets.sh` :
- `API_TOKEN`
- `GH_PAT`
- `GH_WEBHOOK_SECRET`
- `SQL_PASSWORD`

## 📈 Monitoring et observabilité

### Logs centralisés

```bash
# Logs du service
gcloud logs read --service=knowledge-copilot --region=europe-west1

# Logs des sync
gcloud logs read --filter='jsonPayload.message:"sync"'
```

### Métriques disponibles

- Latence des requêtes
- Taux d'erreur
- Utilisation CPU/mémoire
- Nombre de documents indexés
- Fréquence des syncs

### Health checks

- **Endpoint** : `/health`
- **Retour** : Status du service + stats de la DB
- **Fréquence** : Health check automatique Cloud Run

## ⚡ Performance et scalabilité

### Optimisations implémentées

- **Connexion DB** : Pool de connexions async
- **Background sync** : Tasks asynchrones non-bloquantes
- **Caching** : Réutilisation des connexions embeddings
- **Pagination** : Limitation des résultats de recherche

### Limites de scalabilité

- **Cloud Run** : 10 instances max configurées
- **Concurrency** : 80 requêtes simultanées par instance
- **Database** : f1-micro pour tests (scalable vers des instances plus grandes)
- **Memory** : 1Gi par instance

## 💰 Coûts estimés

### Usage modéré (10 syncs/jour, 100 recherches/jour)

- **Cloud Run** : ~5€/mois
- **Cloud SQL f1-micro** : ~10€/mois
- **Vertex AI embeddings** : ~2€/mois
- **Storage/Secrets** : <1€/mois
- **Total** : ~18€/mois

### Optimisations de coût

- Instance Cloud SQL minimal (f1-micro)
- Cloud Run avec scale-to-zero
- Secrets partagés
- Région europe-west1 (coût modéré)

## 🎯 Objectifs atteints

✅ **Service Cloud Run** protégé par API key  
✅ **Resync auto** via Cloud Scheduler (3h)  
✅ **Base de données** reliée proprement via Unix socket  
✅ **Endpoints MCP** complets et conformes  
✅ **Webhook GitHub** optionnel pour reindex instantané  
✅ **Documentation** complète et scripts de déploiement  
✅ **Sécurité** avec Secret Manager et IAM

## 🔮 Évolutions futures possibles

### Améliorations techniques
- Cache Redis pour requêtes fréquentes
- Support multi-tenant
- API versioning
- Rate limiting avancé

### Nouvelles sources
- Confluence/Notion
- Slack/Discord
- Documentation sites
- Base de connaissances existantes

### Interface utilisateur
- Dashboard web de gestion
- Monitoring visuel
- Configuration via UI
- Analytics des recherches

---

**🎉 Livrable Jour 4 complet** : Service Cloud Run prêt pour la production avec tous les endpoints MCP, synchronisation automatique et sécurité enterprise-grade.