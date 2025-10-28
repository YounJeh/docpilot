# Knowledge Copilot MCP Server - Déploiement Cloud Run

Ce guide vous accompagne dans le déploiement du serveur MCP Knowledge Copilot sur Google Cloud Run avec toutes les automations.

## 🏗️ Architecture

- **Service Cloud Run** : API MCP avec FastAPI
- **Cloud SQL PostgreSQL** : Base de données vectorielle avec pgvector
- **Secret Manager** : Gestion sécurisée des clés API
- **Cloud Scheduler** : Resync automatique toutes les 3 heures
- **Vertex AI** : Embeddings avec text-embedding-004

## 🚀 Déploiement rapide

### 1. Prérequis

```bash
# Installer Google Cloud SDK
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# S'authentifier
gcloud auth login
gcloud auth application-default login

# Installer Docker
# Suivre les instructions sur https://docs.docker.com/get-docker/
```

### 2. Configuration initiale

```bash
# Définir les variables d'environnement
export PROJECT_ID="your-gcp-project-id"
export REGION="europe-west1"

# Définir le projet par défaut
gcloud config set project $PROJECT_ID
```

### 3. Setup des secrets

```bash
# Créer les secrets nécessaires
./setup-secrets.sh --project $PROJECT_ID
```

Vous serez invité à entrer :
- **API_TOKEN** : Token sécurisé pour l'authentification (générez avec `openssl rand -base64 32`)
- **GH_PAT** : GitHub Personal Access Token avec accès aux repos
- **GH_WEBHOOK_SECRET** : Secret pour les webhooks GitHub (optionnel)
- **SQL_PASSWORD** : Mot de passe pour PostgreSQL

### 4. Déploiement

```bash
# Déployer le service complet
./deploy.sh --project $PROJECT_ID --region $REGION
```

### 5. Configuration du resync automatique

```bash
# Configurer Cloud Scheduler pour resync toutes les 3 heures
./setup-scheduler.sh --project $PROJECT_ID --region $REGION
```

## 📝 Configuration détaillée

### Variables d'environnement

Copiez `.env.example` vers `.env` et configurez :

```bash
cp .env.example .env
# Éditez .env avec vos valeurs
```

### Base de données Cloud SQL

Si vous n'avez pas encore de base PostgreSQL :

```bash
# Créer une instance Cloud SQL
gcloud sql instances create kc-postgres \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=$REGION \
    --storage-type=SSD \
    --storage-size=20GB

# Créer la base de données
gcloud sql databases create kcdb --instance=kc-postgres

# Définir le mot de passe root
gcloud sql users set-password postgres \
    --instance=kc-postgres \
    --password="your-secure-password"

# Activer les extensions nécessaires
gcloud sql connect kc-postgres --user=postgres
```

Puis dans psql :
```sql
\c kcdb
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### Configuration GitHub

1. **Personal Access Token** :
   - Allez sur GitHub → Settings → Developer settings → Personal access tokens
   - Créez un token avec les scopes : `repo`, `read:org`

2. **Webhooks** (optionnel) :
   - Dans votre repo → Settings → Webhooks
   - URL : `https://your-service-url/webhook/github`
   - Content type : `application/json`
   - Secret : votre `GH_WEBHOOK_SECRET`
   - Events : `push`

### Configuration Google Drive

1. **Service Account** :
```bash
# Créer un service account
gcloud iam service-accounts create knowledge-copilot \
    --display-name="Knowledge Copilot Service Account"

# Télécharger la clé
gcloud iam service-accounts keys create kc-drive-sa.json \
    --iam-account=knowledge-copilot@$PROJECT_ID.iam.gserviceaccount.com
```

2. **Partage Drive** :
   - Partagez votre dossier Google Drive avec l'email du service account
   - Récupérez l'ID du dossier depuis l'URL

## 🔧 Utilisation

### Endpoints MCP

Une fois déployé, votre service expose :

- `GET /mcp/tools` : Description des outils MCP
- `POST /mcp/search_documents` : Recherche sémantique
- `GET /mcp/list_documents` : Liste des documents indexés
- `POST /sync_sources` : Synchronisation manuelle
- `POST /webhook/github` : Webhook GitHub
- `GET /health` : Health check

### Authentification

Toutes les requêtes nécessitent l'en-tête :
```
X-API-KEY: your-api-token
```

### Exemples d'utilisation

```bash
# Health check
curl -H "X-API-KEY: $API_TOKEN" \
  https://your-service-url/health

# Recherche de documents
curl -X POST \
  -H "X-API-KEY: $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "limit": 5}' \
  https://your-service-url/mcp/search_documents

# Déclencher une synchronisation
curl -X POST \
  -H "X-API-KEY: $API_TOKEN" \
  https://your-service-url/sync_sources
```

## 🔍 Monitoring et logs

```bash
# Voir les logs du service
gcloud logs read --service=knowledge-copilot --region=$REGION

# Voir les métriques Cloud Run
gcloud monitoring metrics list --filter="metric.type:run.googleapis.com"

# Status du job Cloud Scheduler
./setup-scheduler.sh status $PROJECT_ID $REGION
```

## 🛠️ Maintenance

### Mise à jour du service

```bash
# Rebuild et redéployer
./deploy.sh --project $PROJECT_ID --region $REGION

# Ou juste rebuild si vous avez modifié le code
./deploy.sh --skip-apis --project $PROJECT_ID
```

### Gestion du scheduler

```bash
# Pause le resync automatique
./setup-scheduler.sh pause $PROJECT_ID $REGION

# Reprendre le resync
./setup-scheduler.sh resume $PROJECT_ID $REGION

# Changer la fréquence (exemple : toutes les 6 heures)
./setup-scheduler.sh --schedule "0 */6 * * *" --project $PROJECT_ID
```

### Gestion des secrets

```bash
# Mettre à jour un secret
echo "new-api-token" | gcloud secrets versions add API_TOKEN --data-file=-

# Lister les secrets
gcloud secrets list

# Voir les versions d'un secret
gcloud secrets versions list API_TOKEN
```

## 🚨 Sécurité

- **API Token** : Utilisez un token long et aléatoire (32+ caractères)
- **Cloud Run** : Service non exposé publiquement par défaut
- **IAM** : Permissions minimales avec des service accounts dédiés
- **Secrets** : Toutes les clés sensibles sont dans Secret Manager
- **Cloud SQL** : Connexion via Unix socket (pas d'IP publique)

## 📊 Coûts estimés

Pour un usage modéré (quelques sync par jour) :
- **Cloud Run** : ~5-10€/mois
- **Cloud SQL f1-micro** : ~10€/mois  
- **Vertex AI embeddings** : ~2-5€/mois selon le volume
- **Secret Manager** : <1€/mois
- **Cloud Scheduler** : Gratuit

## 🐛 Troubleshooting

### Erreurs courantes

1. **Secrets non trouvés** :
```bash
# Vérifier que les secrets existent
gcloud secrets list | grep -E "(API_TOKEN|GH_PAT)"
```

2. **Connexion DB échouée** :
```bash
# Tester la connexion Cloud SQL
gcloud sql connect kc-postgres --user=postgres
```

3. **Service inaccessible** :
```bash
# Vérifier le status du service
gcloud run services describe knowledge-copilot --region=$REGION
```

4. **Sync échoué** :
```bash
# Vérifier les logs détaillés
gcloud logs read --service=knowledge-copilot --region=$REGION --limit=50
```

### Debug local

Pour tester localement avant déploiement :

```bash
# Installer les dépendances
pip install -e .

# Configurer les variables d'environnement locales
cp .env.example .env
# Éditer .env avec DATABASE_URL local

# Lancer le serveur
uvicorn app:app --reload --port 8080
```

## 📞 Support

- **Logs** : `gcloud logs read --service=knowledge-copilot`
- **Monitoring** : Google Cloud Console → Cloud Run
- **Status** : `curl https://your-service-url/health`

## 🔄 Évolutions futures

- Support d'autres sources (Notion, Confluence, etc.)
- Interface web pour la gestion
- Métriques personnalisées
- Cache Redis pour les requêtes fréquentes
- Support multi-tenant