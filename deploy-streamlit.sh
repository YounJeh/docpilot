#!/bin/bash
set -e

# DocPilot Streamlit Deployment Script for Google Cloud Run
# Usage: ./deploy-streamlit.sh [PROJECT_ID] [MCP_SERVICE_URL]

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID=${1:-$(gcloud config get-value project)}
MCP_SERVICE_URL=${2:-""}
REGION=${REGION:-"us-central1"}
SERVICE_NAME="docpilot-streamlit"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo -e "${BLUE}🚁 DocPilot Streamlit Deployment Script${NC}"
echo "=================================================="

# Validate inputs
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Error: PROJECT_ID is required${NC}"
    echo "Usage: $0 [PROJECT_ID] [MCP_SERVICE_URL]"
    exit 1
fi

if [ -z "$MCP_SERVICE_URL" ]; then
    echo -e "${YELLOW}⚠️  Warning: MCP_SERVICE_URL not provided${NC}"
    echo "You'll need to set it manually in Cloud Run environment variables"
fi

echo -e "${BLUE}📋 Configuration:${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service Name: $SERVICE_NAME"
echo "  Image: $IMAGE_NAME"
echo "  MCP URL: ${MCP_SERVICE_URL:-'Not set'}"

# Check if logged in to gcloud
echo -e "\n${BLUE}🔐 Checking Google Cloud authentication...${NC}"
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${RED}❌ Not logged in to Google Cloud${NC}"
    echo "Run: gcloud auth login"
    exit 1
fi

# Set project
echo -e "\n${BLUE}📌 Setting project...${NC}"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "\n${BLUE}🔧 Enabling required APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    artifactregistry.googleapis.com \
    aiplatform.googleapis.com

# Create service account if it doesn't exist
echo -e "\n${BLUE}👤 Setting up service account...${NC}"
SA_EMAIL="docpilot-sa@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe $SA_EMAIL >/dev/null 2>&1; then
    echo "Creating service account..."
    gcloud iam service-accounts create docpilot-sa \
        --display-name="DocPilot Service Account" \
        --description="Service account for DocPilot application"
fi

# Grant necessary permissions
echo -e "\n${BLUE}🔑 Granting permissions...${NC}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/monitoring.metricWriter"

# Build and push Docker image
echo -e "\n${BLUE}🏗️  Building Docker image...${NC}"
docker build -f Dockerfile.streamlit -t $IMAGE_NAME .

echo -e "\n${BLUE}📤 Pushing image to Container Registry...${NC}"
docker push $IMAGE_NAME

# Prepare Cloud Run service YAML
echo -e "\n${BLUE}📝 Preparing Cloud Run configuration...${NC}"
cp cloud-run-streamlit.yaml cloud-run-streamlit-deploy.yaml
sed -i.bak "s/PROJECT_ID/$PROJECT_ID/g" cloud-run-streamlit-deploy.yaml

if [ -n "$MCP_SERVICE_URL" ]; then
    sed -i.bak "s|MCP_SERVICE_URL|$MCP_SERVICE_URL|g" cloud-run-streamlit-deploy.yaml
else
    sed -i.bak "s|MCP_SERVICE_URL|http://localhost:8000|g" cloud-run-streamlit-deploy.yaml
fi

# Deploy to Cloud Run
echo -e "\n${BLUE}🚀 Deploying to Cloud Run...${NC}"
gcloud run services replace cloud-run-streamlit-deploy.yaml --region=$REGION

# Make service publicly accessible
echo -e "\n${BLUE}🌐 Making service publicly accessible...${NC}"
gcloud run services add-iam-policy-binding $SERVICE_NAME \
    --region=$REGION \
    --member="allUsers" \
    --role="roles/run.invoker"

# Get service URL
echo -e "\n${BLUE}📍 Getting service URL...${NC}"
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

# Clean up temporary files
rm -f cloud-run-streamlit-deploy.yaml cloud-run-streamlit-deploy.yaml.bak

echo -e "\n${GREEN}✅ Deployment completed successfully!${NC}"
echo "=================================================="
echo -e "${GREEN}🌐 Service URL: $SERVICE_URL${NC}"
echo -e "${BLUE}📊 Monitor logs: gcloud run services logs tail $SERVICE_NAME --region=$REGION${NC}"
echo -e "${BLUE}⚙️  Manage service: https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME${NC}"

if [ -z "$MCP_SERVICE_URL" ]; then
    echo -e "\n${YELLOW}⚠️  Don't forget to:${NC}"
    echo "1. Set the MCP_URL environment variable in Cloud Run console"
    echo "2. Make sure your MCP service is accessible from Cloud Run"
fi

echo -e "\n${GREEN}🎉 DocPilot Streamlit is now live!${NC}"