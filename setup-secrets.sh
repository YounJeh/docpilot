#!/bin/bash
# Setup Google Cloud Secrets for Knowledge Copilot

set -e

PROJECT_ID=${PROJECT_ID:-"your-project-id"}
REGION=${REGION:-"europe-west1"}

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

# Create or update secrets
create_secret() {
    local secret_name=$1
    local secret_value=$2
    local description=$3
    
    echo_info "Creating/updating secret: $secret_name"
    
    # Check if secret exists
    if gcloud secrets describe $secret_name --project=$PROJECT_ID &>/dev/null; then
        echo_warn "Secret $secret_name already exists, creating new version..."
        echo -n "$secret_value" | gcloud secrets versions add $secret_name --data-file=-
    else
        echo_info "Creating new secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets create $secret_name \
            --data-file=- \
            --replication-policy="automatic" \
            --labels="service=knowledge-copilot"
    fi
}

# Main setup
main() {
    echo_info "Setting up Google Cloud Secrets for Knowledge Copilot..."
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --project)
                PROJECT_ID="$2"
                shift 2
                ;;
            *)
                echo_error "Unknown option: $1"
                echo_info "Usage: $0 [--project PROJECT_ID]"
                exit 1
                ;;
        esac
    done
    
    # Set project
    gcloud config set project $PROJECT_ID
    
    # Enable Secret Manager API
    echo_info "Enabling Secret Manager API..."
    gcloud services enable secretmanager.googleapis.com
    
    # Interactive secret creation
    echo_info "You will be prompted to enter values for each secret."
    echo_warn "Press Enter to skip a secret if you want to set it later."
    echo ""
    
    # API Token
    echo -n "Enter API_TOKEN (secure random string for API authentication): "
    read -s api_token
    echo
    if [ -n "$api_token" ]; then
        create_secret "API_TOKEN" "$api_token" "API token for MCP server authentication"
    else
        echo_warn "Skipped API_TOKEN - you can create it later"
    fi
    
    # GitHub PAT
    echo -n "Enter GH_PAT (GitHub Personal Access Token): "
    read -s gh_pat
    echo
    if [ -n "$gh_pat" ]; then
        create_secret "GH_PAT" "$gh_pat" "GitHub Personal Access Token for repository access"
    else
        echo_warn "Skipped GH_PAT - you can create it later"
    fi
    
    # GitHub Webhook Secret
    echo -n "Enter GH_WEBHOOK_SECRET (GitHub webhook secret): "
    read -s gh_webhook_secret
    echo
    if [ -n "$gh_webhook_secret" ]; then
        create_secret "GH_WEBHOOK_SECRET" "$gh_webhook_secret" "GitHub webhook secret for signature verification"
    else
        echo_warn "Skipped GH_WEBHOOK_SECRET - you can create it later"
    fi
    
    # Database password
    echo -n "Enter database password for PostgreSQL: "
    read -s db_password
    echo
    if [ -n "$db_password" ]; then
        create_secret "SQL_PASSWORD" "$db_password" "PostgreSQL database password"
    else
        echo_warn "Skipped SQL_PASSWORD - you can create it later"
    fi
    
    echo_info "Secrets setup completed!"
    echo_info "You can view your secrets with: gcloud secrets list"
    echo_info "You can update a secret with: echo 'new-value' | gcloud secrets versions add SECRET_NAME --data-file=-"
}

# Generate random token helper
generate_token() {
    echo_info "Generating secure random token..."
    openssl rand -base64 32
}

# Show usage if requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: $0 [--project PROJECT_ID]"
    echo ""
    echo "This script sets up Google Cloud Secrets for the Knowledge Copilot MCP server."
    echo ""
    echo "Options:"
    echo "  --project PROJECT_ID    Set the Google Cloud project ID"
    echo "  --help, -h             Show this help message"
    echo ""
    echo "You can generate a secure random token with:"
    echo "  openssl rand -base64 32"
    exit 0
fi

# Run main function
main "$@"