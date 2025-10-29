#!/bin/bash
set -e

# DocPilot GCP Project Setup Script
# Usage: ./setup-gcp-project.sh [PROJECT_ID]

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ID=${1:-$(gcloud config get-value project)}
REGION=${REGION:-"us-central1"}

echo -e "${BLUE}🚁 DocPilot GCP Project Setup${NC}"
echo "=================================="

# Validate PROJECT_ID
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Error: PROJECT_ID is required${NC}"
    echo "Usage: $0 [PROJECT_ID]"
    exit 1
fi

echo -e "${BLUE}📋 Configuration:${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"

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
APIs=(
    "aiplatform.googleapis.com"
    "cloudbuild.googleapis.com"
    "run.googleapis.com"
    "containerregistry.googleapis.com"
    "artifactregistry.googleapis.com"
    "compute.googleapis.com"
    "storage.googleapis.com"
    "logging.googleapis.com"
    "monitoring.googleapis.com"
    "secretmanager.googleapis.com"
)

for api in "${APIs[@]}"; do
    echo "Enabling $api..."
    gcloud services enable $api
done

# Create Artifact Registry repository
echo -e "\n${BLUE}📦 Setting up Artifact Registry...${NC}"
REPO_NAME="docpilot-repo"
if ! gcloud artifacts repositories describe $REPO_NAME --location=$REGION >/dev/null 2>&1; then
    echo "Creating Artifact Registry repository..."
    gcloud artifacts repositories create $REPO_NAME \
        --repository-format=docker \
        --location=$REGION \
        --description="DocPilot container images"
else
    echo "Artifact Registry repository already exists"
fi

# Configure Docker for Artifact Registry
echo -e "\n${BLUE}🐳 Configuring Docker for Artifact Registry...${NC}"
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Create service accounts
echo -e "\n${BLUE}👤 Creating service accounts...${NC}"

# DocPilot main service account
SA_NAME="docpilot-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe $SA_EMAIL >/dev/null 2>&1; then
    echo "Creating DocPilot service account..."
    gcloud iam service-accounts create $SA_NAME \
        --display-name="DocPilot Service Account" \
        --description="Main service account for DocPilot application"
else
    echo "DocPilot service account already exists"
fi

# Grant necessary roles
echo -e "\n${BLUE}🔑 Granting IAM roles...${NC}"
ROLES=(
    "roles/aiplatform.user"
    "roles/logging.logWriter"
    "roles/monitoring.metricWriter"
    "roles/storage.objectViewer"
    "roles/secretmanager.secretAccessor"
)

for role in "${ROLES[@]}"; do
    echo "Granting $role to $SA_EMAIL..."
    gcloud projects add-iam-policy-binding $PROJECT_ID \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$role"
done

# Create secrets for configuration
echo -e "\n${BLUE}🔐 Setting up Secret Manager...${NC}"

# Create secret for MCP URL if it doesn't exist
if ! gcloud secrets describe mcp-url >/dev/null 2>&1; then
    echo "Creating MCP URL secret..."
    echo -n "http://localhost:8000" | gcloud secrets create mcp-url --data-file=-
else
    echo "MCP URL secret already exists"
fi

# Set default region
echo -e "\n${BLUE}🌍 Setting default region...${NC}"
gcloud config set run/region $REGION
gcloud config set compute/region $REGION

# Create bucket for logs and artifacts (optional)
echo -e "\n${BLUE}🪣 Creating storage bucket...${NC}"
BUCKET_NAME="${PROJECT_ID}-docpilot-storage"
if ! gsutil ls gs://$BUCKET_NAME >/dev/null 2>&1; then
    echo "Creating storage bucket..."
    gsutil mb -l $REGION gs://$BUCKET_NAME
    
    # Set lifecycle rule to delete old logs
    cat > lifecycle.json << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 30}
      }
    ]
  }
}
EOF
    gsutil lifecycle set lifecycle.json gs://$BUCKET_NAME
    rm lifecycle.json
else
    echo "Storage bucket already exists"
fi

# Output configuration
echo -e "\n${GREEN}✅ GCP Project setup completed!${NC}"
echo "=================================="
echo -e "${BLUE}📋 Configuration Summary:${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  Region: $REGION"
echo "  Service Account: $SA_EMAIL"
echo "  Artifact Registry: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
echo "  Storage Bucket: gs://$BUCKET_NAME"

echo -e "\n${BLUE}🚀 Next Steps:${NC}"
echo "1. Deploy your MCP service first"
echo "2. Update the MCP URL secret:"
echo "   echo -n 'YOUR_MCP_SERVICE_URL' | gcloud secrets versions add mcp-url --data-file=-"
echo "3. Deploy the Streamlit app:"
echo "   ./deploy-streamlit.sh $PROJECT_ID YOUR_MCP_SERVICE_URL"

echo -e "\n${GREEN}🎉 Project is ready for DocPilot deployment!${NC}"