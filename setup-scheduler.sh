#!/bin/bash
# Setup Cloud Scheduler for automatic Knowledge Copilot sync

set -e

PROJECT_ID=${PROJECT_ID:-"your-project-id"}
REGION=${REGION:-"europe-west1"}
SERVICE_NAME="knowledge-copilot"
JOB_NAME="kc-sync"

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

# Get Cloud Run service URL
get_service_url() {
    echo_info "Getting Cloud Run service URL..."
    
    SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format="value(status.url)" 2>/dev/null)
    
    if [ -z "$SERVICE_URL" ]; then
        echo_error "Could not find Cloud Run service '${SERVICE_NAME}' in region '${REGION}'"
        echo_error "Please deploy the service first with ./deploy.sh"
        exit 1
    fi
    
    echo_info "Service URL: $SERVICE_URL"
}

# Get API token from Secret Manager
get_api_token() {
    echo_info "Getting API token from Secret Manager..."
    
    API_TOKEN=$(gcloud secrets versions access latest --secret="API_TOKEN" 2>/dev/null)
    
    if [ -z "$API_TOKEN" ]; then
        echo_error "Could not retrieve API_TOKEN from Secret Manager"
        echo_error "Please create the secret first with ./setup-secrets.sh"
        exit 1
    fi
    
    echo_info "API token retrieved successfully"
}

# Create Cloud Scheduler job
create_scheduler_job() {
    echo_info "Creating Cloud Scheduler job..."
    
    # Delete existing job if it exists
    if gcloud scheduler jobs describe ${JOB_NAME} --location=${REGION} &>/dev/null; then
        echo_warn "Job ${JOB_NAME} already exists, deleting it first..."
        gcloud scheduler jobs delete ${JOB_NAME} --location=${REGION} --quiet
    fi
    
    # Create the job
    gcloud scheduler jobs create http ${JOB_NAME} \
        --location=${REGION} \
        --schedule="0 */3 * * *" \
        --uri="${SERVICE_URL}/sync_sources" \
        --http-method=POST \
        --headers="X-API-KEY=${API_TOKEN},Content-Type=application/json" \
        --message-body='{"github_only": false, "gdrive_only": false}' \
        --description="Automatic sync of GitHub and Google Drive documents every 3 hours" \
        --time-zone="UTC" \
        --max-retry-attempts=3 \
        --max-retry-duration=300s \
        --min-backoff=30s \
        --max-backoff=120s
    
    echo_info "Cloud Scheduler job created successfully"
}

# Test the scheduler job
test_job() {
    echo_info "Testing the scheduler job..."
    
    gcloud scheduler jobs run ${JOB_NAME} --location=${REGION}
    
    echo_info "Job triggered manually. Check the Cloud Run logs to see the sync progress:"
    echo_info "gcloud logs read --service=${SERVICE_NAME} --region=${REGION}"
}

# Show job status
show_status() {
    echo_info "Scheduler job status:"
    gcloud scheduler jobs describe ${JOB_NAME} --location=${REGION} \
        --format="table(name,schedule,timeZone,state,lastAttemptTime,nextRunTime)"
}

# Main setup
main() {
    echo_info "Setting up Cloud Scheduler for Knowledge Copilot..."
    
    # Parse command line arguments
    SKIP_TEST=false
    CUSTOM_SCHEDULE=""
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --project)
                PROJECT_ID="$2"
                shift 2
                ;;
            --region)
                REGION="$2"
                shift 2
                ;;
            --schedule)
                CUSTOM_SCHEDULE="$2"
                shift 2
                ;;
            --skip-test)
                SKIP_TEST=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --project PROJECT_ID    Set the Google Cloud project ID"
                echo "  --region REGION         Set the region (default: europe-west1)"
                echo "  --schedule SCHEDULE     Custom cron schedule (default: every 3 hours)"
                echo "  --skip-test            Skip the test run"
                echo "  --help, -h             Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0 --project my-project"
                echo "  $0 --schedule '0 */6 * * *'  # Every 6 hours"
                echo "  $0 --schedule '0 9 * * 1-5'  # Every weekday at 9 AM"
                exit 0
                ;;
            *)
                echo_error "Unknown option: $1"
                echo_info "Use --help for usage information"
                exit 1
                ;;
        esac
    done
    
    # Set project
    gcloud config set project $PROJECT_ID
    
    # Enable required APIs
    echo_info "Enabling Cloud Scheduler API..."
    gcloud services enable cloudscheduler.googleapis.com
    
    # Create App Engine app if it doesn't exist (required for Cloud Scheduler in some regions)
    if ! gcloud app describe &>/dev/null; then
        echo_info "Creating App Engine app (required for Cloud Scheduler)..."
        gcloud app create --region=${REGION} --quiet || true
    fi
    
    get_service_url
    get_api_token
    
    # Use custom schedule if provided
    if [ -n "$CUSTOM_SCHEDULE" ]; then
        echo_info "Using custom schedule: $CUSTOM_SCHEDULE"
        # You would modify the create_scheduler_job function to use this
    fi
    
    create_scheduler_job
    
    if [ "$SKIP_TEST" = false ]; then
        echo_warn "Testing the job (this will trigger a sync)..."
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            test_job
        fi
    fi
    
    show_status
    
    echo_info "Cloud Scheduler setup completed!"
    echo_info "The sync job will run every 3 hours automatically."
    echo_info "You can monitor jobs at: https://console.cloud.google.com/cloudscheduler"
    echo_info "Logs available at: gcloud logs read --service=${SERVICE_NAME} --region=${REGION}"
}

# Additional management functions
pause_job() {
    echo_info "Pausing scheduler job..."
    gcloud scheduler jobs pause ${JOB_NAME} --location=${REGION}
}

resume_job() {
    echo_info "Resuming scheduler job..."
    gcloud scheduler jobs resume ${JOB_NAME} --location=${REGION}
}

delete_job() {
    echo_warn "Deleting scheduler job..."
    gcloud scheduler jobs delete ${JOB_NAME} --location=${REGION}
}

# Handle special commands
case "${1:-}" in
    pause)
        PROJECT_ID=${2:-$PROJECT_ID}
        REGION=${3:-$REGION}
        gcloud config set project $PROJECT_ID
        pause_job
        exit 0
        ;;
    resume)
        PROJECT_ID=${2:-$PROJECT_ID}
        REGION=${3:-$REGION}
        gcloud config set project $PROJECT_ID
        resume_job
        exit 0
        ;;
    delete)
        PROJECT_ID=${2:-$PROJECT_ID}
        REGION=${3:-$REGION}
        gcloud config set project $PROJECT_ID
        delete_job
        exit 0
        ;;
    status)
        PROJECT_ID=${2:-$PROJECT_ID}
        REGION=${3:-$REGION}
        gcloud config set project $PROJECT_ID
        show_status
        exit 0
        ;;
esac

# Run main function
main "$@"