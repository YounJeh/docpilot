#!/bin/bash
# Deploy Knowledge Copilot MCP Server to Google Cloud Run

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-"your-project-id"}
REGION=${REGION:-"europe-west1"}
SERVICE_NAME="knowledge-copilot"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    echo_info "Checking prerequisites..."
    
    if ! command -v gcloud &> /dev/null; then
        echo_error "gcloud CLI not found. Please install Google Cloud SDK."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        echo_error "Docker not found. Please install Docker."
        exit 1
    fi
    
    # Check if authenticated
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        echo_error "Not authenticated with gcloud. Please run 'gcloud auth login'"
        exit 1
    fi
    
    # Set project
    gcloud config set project ${PROJECT_ID}
    echo_info "Using project: ${PROJECT_ID}"
}

# Enable required APIs
enable_apis() {
    echo_info "Enabling required Google Cloud APIs..."
    
    gcloud services enable cloudbuild.googleapis.com
    gcloud services enable run.googleapis.com
    gcloud services enable secretmanager.googleapis.com
    gcloud services enable sqladmin.googleapis.com
    gcloud services enable cloudscheduler.googleapis.com
    gcloud services enable aiplatform.googleapis.com
    
    echo_info "APIs enabled successfully"
}

# Build and push Docker image
build_image() {
    echo_info "Building and pushing Docker image..."
    
    # Build with Cloud Build for better performance
    gcloud builds submit --tag ${IMAGE_NAME} .
    
    echo_info "Image built and pushed: ${IMAGE_NAME}"
}

# Deploy to Cloud Run
deploy_service() {
    echo_info "Deploying to Cloud Run..."
    
    # Get SQL instance connection name
    SQL_INSTANCE_CONN="${PROJECT_ID}:${REGION}:kc-postgres"
    
    # Deploy with all configurations
    gcloud run deploy ${SERVICE_NAME} \
        --image ${IMAGE_NAME} \
        --region ${REGION} \
        --no-allow-unauthenticated \
        --platform managed \
        --memory 1Gi \
        --cpu 1 \
        --max-instances 10 \
        --min-instances 1 \
        --port 8080 \
        --timeout 900 \
        --concurrency 80 \
        --set-secrets="API_TOKEN=API_TOKEN:latest,GH_PAT=GH_PAT:latest,GH_WEBHOOK_SECRET=GH_WEBHOOK_SECRET:latest,SQL_PASSWORD=SQL_PASSWORD:latest" \
        --set-env-vars="PROJECT_ID=${PROJECT_ID}" \
        --set-env-vars="GCS_BUCKET=knowledge-copilot-cache-${PROJECT_ID}" \
        --set-env-vars="SQL_INSTANCE=kc-postgres" \
        --set-env-vars="SQL_DB=kcdb" \
        --set-env-vars="SQL_USER=postgres" \
        --set-env-vars="EMBED_PROVIDER=vertex" \
        --set-env-vars="EMBED_MODEL=text-embedding-004" \
        --add-cloudsql-instances ${SQL_INSTANCE_CONN}
    
    echo_info "Service deployed successfully"
}

# Set IAM permissions
set_permissions() {
    echo_info "Setting up IAM permissions..."
    
    # Get service account for Cloud Run
    SERVICE_ACCOUNT=$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format="value(spec.template.spec.serviceAccountName)")
    
    if [ -z "$SERVICE_ACCOUNT" ]; then
        SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"
        echo_warn "Using default service account: $SERVICE_ACCOUNT"
    fi
    
    # Grant necessary permissions
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SERVICE_ACCOUNT}" \
        --role="roles/cloudsql.client"
    
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SERVICE_ACCOUNT}" \
        --role="roles/aiplatform.user"
    
    gcloud projects add-iam-policy-binding ${PROJECT_ID} \
        --member="serviceAccount:${SERVICE_ACCOUNT}" \
        --role="roles/storage.objectAdmin"
    
    echo_info "IAM permissions configured"
}

# Get service URL
get_service_url() {
    SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format="value(status.url)")
    echo_info "Service URL: ${SERVICE_URL}"
    echo_info "Health check: ${SERVICE_URL}/health"
    echo_info "MCP tools: ${SERVICE_URL}/mcp/tools"
}

# Main deployment flow
main() {
    echo_info "Starting deployment of Knowledge Copilot MCP Server..."
    
    # Parse command line arguments
    SKIP_BUILD=false
    SKIP_APIS=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --skip-apis)
                SKIP_APIS=true
                shift
                ;;
            --project)
                PROJECT_ID="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            *)
                echo_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    check_prerequisites
    
    if [ "$SKIP_APIS" = false ]; then
        enable_apis
    fi
    
    if [ "$SKIP_BUILD" = false ]; then
        build_image
    fi
    
    deploy_service
    set_permissions
    get_service_url
    
    echo_info "Deployment completed successfully!"
    echo_warn "Don't forget to:"
    echo_warn "1. Create secrets in Secret Manager (API_TOKEN, GH_PAT, GH_WEBHOOK_SECRET)"
    echo_warn "2. Set up Cloud Scheduler job for automatic sync"
    echo_warn "3. Configure GitHub webhooks if needed"
}

# Run main function
main "$@"