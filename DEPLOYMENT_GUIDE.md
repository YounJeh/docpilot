# 🚁 DocPilot - Guide de Déploiement Google Cloud

## Vue d'ensemble

Ce guide vous accompagne pour déployer DocPilot sur Google Cloud Platform avec Vertex AI comme fournisseur LLM par défaut.

## 🎯 Architecture de déploiement

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Streamlit UI   │────│   MCP Service   │────│   PostgreSQL    │
│  (Cloud Run)    │    │  (Cloud Run)    │    │  (Cloud SQL)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                        ┌─────────────────┐
                        │   Vertex AI     │
                        │  (Gemini Pro)   │
                        └─────────────────┘
```

## 🚀 Déploiement rapide (Automatique)

### Prérequis

1. **Google Cloud CLI installé et configuré**
   ```bash
   # Installer gcloud CLI
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   
   # Se connecter
   gcloud auth login
   gcloud auth application-default login
   ```

2. **Docker installé**
   ```bash
   # Sur macOS avec Homebrew
   brew install docker
   ```

3. **Project ID Google Cloud**
   ```bash
   # Créer un nouveau projet ou utiliser un existant
   export PROJECT_ID="your-project-id"
   gcloud config set project $PROJECT_ID
   ```

### Déploiement automatique

```bash
# Déploiement complet en une commande
./deploy-complete.sh $PROJECT_ID
```

Ce script va :
- ✅ Configurer le projet GCP
- ✅ Activer les APIs nécessaires
- ✅ Créer les comptes de service
- ✅ Déployer le service MCP
- ✅ Déployer l'interface Streamlit
- ✅ Configurer les permissions

## 🔧 Déploiement manuel (Étape par étape)

### 1. Configuration du projet GCP

```bash
# Configurer le projet
./setup-gcp-project.sh $PROJECT_ID
```

### 2. Déployer le service MCP

```bash
# Si vous avez déjà le service MCP configuré
./deploy.sh

# Ou récupérer l'URL du service existant
MCP_URL=$(gcloud run services describe docpilot-mcp --region=us-central1 --format="value(status.url)")
```

### 3. Déployer l'interface Streamlit

```bash
# Déployer Streamlit avec l'URL MCP
./deploy-streamlit.sh $PROJECT_ID $MCP_URL
```

## ⚙️ Configuration

### Variables d'environnement automatiques

Le déploiement configure automatiquement :

- `PROJECT_ID` : Votre project ID Google Cloud
- `MCP_URL` : URL du service MCP déployé
- `GOOGLE_CLOUD_PROJECT` : Project ID pour Vertex AI
- `ENVIRONMENT` : "production"

### Configuration manuelle (optionnelle)

```bash
# Mettre à jour l'URL MCP si nécessaire
echo -n "https://your-mcp-service-url" | gcloud secrets versions add mcp-url --data-file=-

# Mettre à jour les variables d'environnement Cloud Run
gcloud run services update docpilot-streamlit \
    --region=us-central1 \
    --set-env-vars="MCP_URL=https://your-new-mcp-url"
```

## 🔍 Vérification du déploiement

### 1. Tester les services

```bash
# Vérifier le service MCP
curl https://your-mcp-service-url/health

# Vérifier Streamlit (health check automatique)
curl https://your-streamlit-service-url/_stcore/health
```

### 2. Accéder à l'interface

1. Récupérer l'URL Streamlit :
   ```bash
   gcloud run services describe docpilot-streamlit --region=us-central1 --format="value(status.url)"
   ```

2. Ouvrir l'URL dans votre navigateur

3. Dans la sidebar, vérifier que :
   - **Project ID** est automatiquement renseigné
   - **Fournisseur LLM** est sur "vertex"
   - **État du système** est "opérationnel"

### 3. Test complet

1. Poser une question test : "Comment déployer sur Cloud Run ?"
2. Vérifier que la réponse utilise Vertex AI
3. Contrôler les métriques (temps de réponse, chunks analysés)

## 📊 Surveillance et logs

### Logs en temps réel

```bash
# Logs Streamlit
gcloud run services logs tail docpilot-streamlit --region=us-central1

# Logs MCP
gcloud run services logs tail docpilot-mcp --region=us-central1
```

### Console Cloud

- **Cloud Run** : https://console.cloud.google.com/run
- **Logs** : https://console.cloud.google.com/logs
- **Vertex AI** : https://console.cloud.google.com/vertex-ai
- **Secret Manager** : https://console.cloud.google.com/security/secret-manager

## 🔧 Gestion des services

### Redéploiement

```bash
# Redéployer Streamlit seulement
./deploy-streamlit.sh $PROJECT_ID $MCP_URL

# Redéploiement complet
./deploy-complete.sh $PROJECT_ID
```

### Mise à l'échelle

```bash
# Configurer l'auto-scaling
gcloud run services update docpilot-streamlit \
    --region=us-central1 \
    --min-instances=1 \
    --max-instances=10 \
    --concurrency=80
```

### Mise à jour de configuration

```bash
# Mettre à jour les variables d'environnement
gcloud run services update docpilot-streamlit \
    --region=us-central1 \
    --set-env-vars="NEW_VAR=value"

# Redémarrer le service
gcloud run services update docpilot-streamlit \
    --region=us-central1 \
    --tag=latest
```

## 🐛 Dépannage

### Problèmes courants

**1. Erreur d'authentification Vertex AI**
```bash
# Vérifier les permissions du service account
gcloud projects get-iam-policy $PROJECT_ID --filter="bindings.members:serviceAccount:docpilot-sa@$PROJECT_ID.iam.gserviceaccount.com"
```

**2. Service MCP inaccessible**
```bash
# Vérifier l'état du service MCP
gcloud run services describe docpilot-mcp --region=us-central1
```

**3. Erreurs de déploiement Docker**
```bash
# Reconstruire l'image
docker build -f Dockerfile.streamlit -t gcr.io/$PROJECT_ID/docpilot-streamlit .
docker push gcr.io/$PROJECT_ID/docpilot-streamlit
```

### Logs de debug

```bash
# Activer les logs détaillés
gcloud run services update docpilot-streamlit \
    --region=us-central1 \
    --set-env-vars="LOG_LEVEL=DEBUG"
```

## 💰 Coûts estimés

### Utilisation typique (100 requêtes/jour)

- **Cloud Run Streamlit** : ~$5-10/mois
- **Cloud Run MCP** : ~$5-10/mois  
- **Vertex AI (Gemini)** : ~$10-20/mois
- **Cloud SQL** : ~$10-15/mois
- **Stockage/Réseau** : ~$1-5/mois

**Total estimé** : $30-60/mois

### Optimisation des coûts

```bash
# Réduire les instances minimales
gcloud run services update docpilot-streamlit \
    --region=us-central1 \
    --min-instances=0

# Utiliser des instances plus petites
gcloud run services update docpilot-streamlit \
    --region=us-central1 \
    --memory=1Gi \
    --cpu=1
```

## 🔒 Sécurité

### Bonnes pratiques appliquées

- ✅ **Service accounts dédiés** avec permissions minimales
- ✅ **Secrets Manager** pour les configurations sensibles
- ✅ **HTTPS obligatoire** sur tous les services
- ✅ **Authentification IAM** pour l'accès aux APIs
- ✅ **Logs d'audit** automatiques

### Configuration avancée (optionnelle)

```bash
# Restreindre l'accès à certains utilisateurs
gcloud run services remove-iam-policy-binding docpilot-streamlit \
    --region=us-central1 \
    --member="allUsers" \
    --role="roles/run.invoker"

gcloud run services add-iam-policy-binding docpilot-streamlit \
    --region=us-central1 \
    --member="user:your-email@domain.com" \
    --role="roles/run.invoker"
```

## 🎉 Prochaines étapes

Une fois le déploiement terminé :

1. **Indexer vos documents** via le service MCP
2. **Tester différents types de questions**
3. **Configurer des alertes** de monitoring
4. **Partager l'URL** avec votre équipe

---

**🚁 DocPilot est maintenant prêt sur Google Cloud !**

Pour toute question : consultez les logs ou ouvrez une issue GitHub.