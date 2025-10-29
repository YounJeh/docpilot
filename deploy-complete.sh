#!/bin/bash
set -e

# DocPilot Complete Deployment Script for Google Cloud
# Usage: ./deploy-complete.sh [PROJECT_ID]

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ID=${1:-$(gcloud config get-value project)}
REGION=${REGION:-"us-central1"}

echo -e "${BLUE}🚁 DocPilot Complete Deployment${NC}"
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

# Step 1: Setup GCP Project
echo -e "\n${BLUE}🏗️  Step 1: Setting up GCP project...${NC}"
./setup-gcp-project.sh $PROJECT_ID

# Step 2: Deploy MCP Service (if not already deployed)
echo -e "\n${BLUE}🔧 Step 2: Checking MCP service...${NC}"
MCP_SERVICE_NAME="docpilot-mcp"
MCP_SERVICE_URL=""

# Check if MCP service exists
if gcloud run services describe $MCP_SERVICE_NAME --region=$REGION >/dev/null 2>&1; then
    echo "MCP service already deployed"
    MCP_SERVICE_URL=$(gcloud run services describe $MCP_SERVICE_NAME --region=$REGION --format="value(status.url)")
    echo "MCP Service URL: $MCP_SERVICE_URL"
else
    echo -e "${YELLOW}⚠️  MCP service not found. Deploying...${NC}"
    
    # Deploy MCP service using existing deployment script
    if [ -f "./deploy.sh" ]; then
        ./deploy.sh
        MCP_SERVICE_URL=$(gcloud run services describe $MCP_SERVICE_NAME --region=$REGION --format="value(status.url)")
    else
        echo -e "${YELLOW}⚠️  MCP deployment script not found. You'll need to deploy it manually.${NC}"
        echo "Using placeholder URL for now..."
        MCP_SERVICE_URL="https://your-mcp-service-url"
    fi
fi

# Update MCP URL secret
if [ -n "$MCP_SERVICE_URL" ] && [ "$MCP_SERVICE_URL" != "https://your-mcp-service-url" ]; then
    echo -e "\n${BLUE}🔐 Updating MCP URL secret...${NC}"
    echo -n "$MCP_SERVICE_URL" | gcloud secrets versions add mcp-url --data-file=-
fi

# Step 3: Deploy Streamlit App
echo -e "\n${BLUE}🌐 Step 3: Deploying Streamlit app...${NC}"
./deploy-streamlit.sh $PROJECT_ID $MCP_SERVICE_URL

# Step 4: Get service URLs
echo -e "\n${BLUE}📍 Step 4: Getting service information...${NC}"
STREAMLIT_SERVICE_URL=$(gcloud run services describe docpilot-streamlit --region=$REGION --format="value(status.url)")

# Step 5: Final configuration
echo -e "\n${BLUE}⚙️  Step 5: Final configuration...${NC}"

# Set up logging
echo "Setting up logging..."
gcloud logging sinks create docpilot-logs \
    bigquery.googleapis.com/projects/$PROJECT_ID/datasets/docpilot_logs \
    --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name=("docpilot-streamlit" OR "docpilot-mcp")' \
    --quiet || echo "Logging sink already exists"

# Set up monitoring
echo "Setting up monitoring..."
gcloud alpha monitoring policies create --policy-from-file=monitoring-policy.yaml --quiet || echo "Monitoring policy creation skipped"

# Output final information
echo -e "\n${GREEN}🎉 DocPilot deployment completed successfully!${NC}"
echo "=================================================="
echo -e "${GREEN}📱 Applications:${NC}"
echo "  🌐 Streamlit UI: $STREAMLIT_SERVICE_URL"
echo "  🔧 MCP Service: $MCP_SERVICE_URL"

echo -e "\n${BLUE}📊 Management Links:${NC}"
echo "  📈 Cloud Run Console: https://console.cloud.google.com/run?project=$PROJECT_ID"
echo "  📝 Logs: https://console.cloud.google.com/logs/query?project=$PROJECT_ID"
echo "  🤖 Vertex AI: https://console.cloud.google.com/vertex-ai?project=$PROJECT_ID"
echo "  🔐 Secret Manager: https://console.cloud.google.com/security/secret-manager?project=$PROJECT_ID"

echo -e "\n${BLUE}🔧 Commands for monitoring:${NC}"
echo "  📊 Streamlit logs: gcloud run services logs tail docpilot-streamlit --region=$REGION"
echo "  🔧 MCP logs: gcloud run services logs tail $MCP_SERVICE_NAME --region=$REGION"

echo -e "\n${BLUE}🚀 Getting started:${NC}"
echo "1. Visit the Streamlit app: $STREAMLIT_SERVICE_URL"
echo "2. Configure your Project ID in the sidebar"
echo "3. Start asking questions about your documentation!"

if [ "$MCP_SERVICE_URL" = "https://your-mcp-service-url" ]; then
    echo -e "\n${YELLOW}⚠️  Important:${NC}"
    echo "Don't forget to deploy your MCP service and update the MCP_URL environment variable"
    echo "in the Streamlit Cloud Run service."
fi

echo -e "\n${GREEN}✅ All services are now live and ready to use!${NC}"