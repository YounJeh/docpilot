# DocPilot - Script d'insertion d'embeddings

Ce document explique comment utiliser le script `insert_embeddings.py` pour synchroniser et indexer des documents depuis Google Drive et GitHub dans le système RAG DocPilot.

## Prérequis

1. **Configuration de l'environnement** : Créer un fichier `.env` avec les variables suivantes :

```env
# GCP
PROJECT_ID=votre-project-id
REGION=europe-west1

# Base de données locale (via proxy Cloud SQL)
DATABASE_URL=postgresql://postgres:password@localhost:5432/kcdb

# Cloud SQL (si direct)
SQL_INSTANCE=project:region:instance
SQL_DB=kcdb
SQL_USER=postgres
SQL_PASSWORD=votre-password

# GitHub
GH_PAT=votre-github-token
GH_REPOS=org/repo1,org/repo2
GH_DEFAULT_BRANCH=main
MAX_FILE_MB=2

# Google Drive
GDRIVE_FOLDER_ID=votre-folder-id

# Embeddings
EMBED_PROVIDER=vertex
EMBED_MODEL=text-embedding-004
```

2. **Base de données** : S'assurer que PostgreSQL avec l'extension pgvector est configuré
3. **Authentification GCP** : Avoir un service account ou être authentifié via `gcloud auth`

## Utilisation

### 1. Vérifier les statistiques

```bash
uv run python insert_embeddings.py stats
```

Affiche le nombre de documents et chunks actuellement indexés.

### 2. Test de recherche

```bash
uv run python insert_embeddings.py test-search "votre requête" --limit 5
```

Teste la recherche sémantique sur les documents indexés.

### 3. Synchronisation complète

```bash
# Synchroniser depuis toutes les sources
uv run python insert_embeddings.py run

# Synchroniser depuis GitHub uniquement
uv run python insert_embeddings.py run --sources github

# Synchroniser depuis Google Drive uniquement  
uv run python insert_embeddings.py run --sources gdrive

# Avec paramètres personnalisés
uv run python insert_embeddings.py run \
  --sources all \
  --batch-size 3 \
  --max-tokens 1500 \
  --overlap-tokens 150 \
  --save-preview sync_results.json
```

### Options disponibles

- `--sources` : Sources à synchroniser (`all`, `gdrive`, `github`)
- `--batch-size` : Taille des batches pour l'insertion (défaut: 5)
- `--max-tokens` : Taille max des chunks en tokens (défaut: 1000)
- `--overlap-tokens` : Overlap entre chunks (défaut: 100)
- `--gdrive-folder` : ID du dossier Google Drive spécifique
- `--github-repos` : Repos GitHub (format: "org/repo1,org/repo2")
- `--github-branch` : Branche GitHub (défaut: main)
- `--save-preview` : Fichier pour sauvegarder un aperçu des résultats
- `--log-level` : Niveau de log (DEBUG, INFO, WARNING, ERROR)

## Fonctionnement

### Sources supportées

#### Google Drive
- Synchronise récursivement un dossier Google Drive
- Supporte : Google Docs, Google Slides (via PDF), fichiers texte, Markdown, PDF
- Ignore : Images, vidéos, fichiers binaires
- Limite de taille configurable via `MAX_FILE_MB`

#### GitHub
- Clone en shallow les repos spécifiés
- Extrait : Markdown, commentaires Python, cellules Markdown des notebooks Jupyter
- Ignore : Fichiers binaires, dossiers système (.git, node_modules, etc.)

### Traitement

1. **Extraction** : Le contenu textuel est extrait selon le type de fichier
2. **Chunking** : Le texte est découpé en chunks avec overlap pour préserver le contexte
3. **Déduplication** : Les documents identiques (même hash SHA256) sont ignorés
4. **Embeddings** : Chaque chunk est converti en embedding via Vertex AI
5. **Indexation** : Les embeddings sont stockés dans PostgreSQL avec pgvector

### Recherche

La recherche utilise la similarité cosinus entre l'embedding de la requête et ceux des chunks stockés. Les résultats sont triés par score de similarité décroissant.

## Exemples pratiques

### Indexer un nouveau projet GitHub

```bash
# Ajouter le repo à GH_REPOS dans .env ou utiliser --github-repos
uv run python insert_embeddings.py run \
  --sources github \
  --github-repos "username/new-project" \
  --batch-size 2
```

### Recherche dans la documentation

```bash
# Chercher des informations sur l'API
uv run python insert_embeddings.py test-search "API documentation authentication" --limit 5

# Chercher du code Python
uv run python insert_embeddings.py test-search "python class method" --limit 3
```

### Synchronisation complète avec sauvegarde

```bash
uv run python insert_embeddings.py run \
  --sources all \
  --batch-size 3 \
  --save-preview daily_sync_$(date +%Y%m%d).json \
  --log-level INFO
```

## Monitoring et maintenance

### Vérifier l'état du système

```bash
# Stats globales
uv run python insert_embeddings.py stats

# Test de connectivité
uv run python insert_embeddings.py test-search "test" --limit 1
```

### Gestion de la base de données

```bash
# Se connecter à Cloud SQL
gcloud beta sql connect instance-name --user=postgres --database=kcdb

# Vérifier les tables
\dt

# Statistiques de stockage
SELECT 
  COUNT(*) as documents,
  (SELECT COUNT(*) FROM chunks) as chunks,
  pg_size_pretty(pg_total_relation_size('chunks')) as chunks_size
FROM documents;
```

## Résolution de problèmes

### Erreur de connexion à la base de données

1. Vérifier que le proxy Cloud SQL est démarré :
   ```bash
   cloud_sql_proxy -instances=project:region:instance=tcp:5432 &
   ```

2. Tester la connexion :
   ```bash
   psql postgresql://user:pass@localhost:5432/dbname
   ```

### Erreur d'authentification GCP

```bash
# Authentifier l'application par défaut
gcloud auth application-default login

# Vérifier le project actif
gcloud config get-value project
```

### Erreur de quota Vertex AI

Les embeddings Vertex AI ont des quotas. En cas de dépassement :
- Réduire `--batch-size`
- Ajouter des pauses entre les batches
- Vérifier les quotas dans la console GCP

### Mémoire insuffisante

Pour de gros volumes :
- Réduire `--batch-size`
- Réduire `--max-tokens`
- Traiter par sources séparément

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Google Drive   │    │     GitHub       │    │   Documents     │
│   Connector     │    │   Connector      │    │   Locaux        │
└─────────┬───────┘    └────────┬─────────┘    └─────────┬───────┘
          │                     │                        │
          └─────────────────────┼────────────────────────┘
                                │
                    ┌───────────▼──────────┐
                    │   Insert Embeddings  │
                    │       Script         │
                    └───────────┬──────────┘
                                │
                    ┌───────────▼──────────┐
                    │     RAG Service      │
                    │   - Chunking         │
                    │   - Embeddings       │
                    │   - Indexation       │
                    └───────────┬──────────┘
                                │
                    ┌───────────▼──────────┐
                    │   PostgreSQL         │
                    │   + pgvector         │
                    └──────────────────────┘
```

Le script `insert_embeddings.py` orchestre l'ensemble du processus de synchronisation, traitement et indexation pour créer une base de connaissances searchable sémantiquement.