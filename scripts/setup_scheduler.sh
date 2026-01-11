#!/bin/bash
# =============================================================================
# Setup Cloud Scheduler for Gmail Watch Renewal
# =============================================================================
#
# This script creates a Cloud Scheduler job that:
# - Runs every 6 days at midnight UTC
# - Calls POST /renew-watch on your Cloud Run service
# - Uses OIDC authentication for secure access
#
# Why every 6 days?
# - Gmail watches expire after 7 days
# - Renewing on day 6 gives us a 1-day safety buffer
#
# Prerequisites:
# - gcloud CLI installed and authenticated
# - Cloud Run service already deployed
# - Cloud Scheduler API enabled
#
# Usage:
#   ./scripts/setup_scheduler.sh
#
# Environment variables (optional - will prompt if not set):
#   GCP_PROJECT      - Your GCP project ID
#   GCP_REGION       - Region for Cloud Scheduler (default: europe-west1)
#   CLOUD_RUN_URL    - Your Cloud Run service URL
#   SERVICE_ACCOUNT  - Service account for OIDC authentication
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "  Gmail Agent - Cloud Scheduler Setup"
echo "=============================================="
echo ""

# Get project ID
if [ -z "$GCP_PROJECT" ]; then
    GCP_PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$GCP_PROJECT" ]; then
        echo -e "${YELLOW}Enter your GCP project ID:${NC}"
        read GCP_PROJECT
    fi
fi
echo -e "${GREEN}Using project:${NC} $GCP_PROJECT"

# Get region
if [ -z "$GCP_REGION" ]; then
    GCP_REGION="europe-west1"
fi
echo -e "${GREEN}Using region:${NC} $GCP_REGION"

# Get Cloud Run URL
if [ -z "$CLOUD_RUN_URL" ]; then
    echo -e "${YELLOW}Enter your Cloud Run service URL (e.g., https://email-agent-xxx.run.app):${NC}"
    read CLOUD_RUN_URL
fi
echo -e "${GREEN}Using Cloud Run URL:${NC} $CLOUD_RUN_URL"

# Get service account
if [ -z "$SERVICE_ACCOUNT" ]; then
    PROJECT_NUMBER=$(gcloud projects describe $GCP_PROJECT --format='value(projectNumber)' 2>/dev/null)
    SERVICE_ACCOUNT="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
    echo -e "${YELLOW}Using default service account: $SERVICE_ACCOUNT${NC}"
    echo "Press Enter to continue or type a different service account:"
    read CUSTOM_SA
    if [ -n "$CUSTOM_SA" ]; then
        SERVICE_ACCOUNT=$CUSTOM_SA
    fi
fi
echo -e "${GREEN}Using service account:${NC} $SERVICE_ACCOUNT"

# Configuration
JOB_NAME="gmail-watch-renewal"
SCHEDULE="0 0 */6 * *"  # Every 6 days at midnight UTC
WEBHOOK_PATH="/renew-watch"

echo ""
echo "=============================================="
echo "  Step 1: Enable Cloud Scheduler API"
echo "=============================================="
gcloud services enable cloudscheduler.googleapis.com --project=$GCP_PROJECT
echo -e "${GREEN}✓ Cloud Scheduler API enabled${NC}"

echo ""
echo "=============================================="
echo "  Step 2: Create/Update Scheduler Job"
echo "=============================================="
ENDPOINT_URL="${CLOUD_RUN_URL}${WEBHOOK_PATH}"

# Check if job exists
if gcloud scheduler jobs describe $JOB_NAME --location=$GCP_REGION --project=$GCP_PROJECT &>/dev/null; then
    echo -e "${YELLOW}Job '$JOB_NAME' already exists, updating...${NC}"
    gcloud scheduler jobs update http $JOB_NAME \
        --project=$GCP_PROJECT \
        --location=$GCP_REGION \
        --schedule="$SCHEDULE" \
        --uri="$ENDPOINT_URL" \
        --http-method=POST \
        --oidc-service-account-email=$SERVICE_ACCOUNT \
        --oidc-token-audience=$CLOUD_RUN_URL
    echo -e "${GREEN}✓ Updated scheduler job${NC}"
else
    gcloud scheduler jobs create http $JOB_NAME \
        --project=$GCP_PROJECT \
        --location=$GCP_REGION \
        --schedule="$SCHEDULE" \
        --uri="$ENDPOINT_URL" \
        --http-method=POST \
        --oidc-service-account-email=$SERVICE_ACCOUNT \
        --oidc-token-audience=$CLOUD_RUN_URL \
        --time-zone="UTC" \
        --description="Renews Gmail watch every 6 days to keep push notifications active"
    echo -e "${GREEN}✓ Created scheduler job: $JOB_NAME${NC}"
fi

echo ""
echo "=============================================="
echo "  Step 3: Test the Job (Optional)"
echo "=============================================="
echo -e "${YELLOW}Do you want to run the job now to test it? (y/N)${NC}"
read RUN_NOW

if [ "$RUN_NOW" = "y" ] || [ "$RUN_NOW" = "Y" ]; then
    echo "Running job..."
    gcloud scheduler jobs run $JOB_NAME \
        --project=$GCP_PROJECT \
        --location=$GCP_REGION
    echo -e "${GREEN}✓ Job triggered! Check Cloud Run logs for results.${NC}"
else
    echo "Skipping test run."
fi

echo ""
echo "=============================================="
echo "  Setup Complete!"
echo "=============================================="
echo ""
echo "Summary:"
echo "  Job Name:     $JOB_NAME"
echo "  Schedule:     $SCHEDULE (every 6 days at midnight UTC)"
echo "  Endpoint:     $ENDPOINT_URL"
echo "  Auth:         OIDC with $SERVICE_ACCOUNT"
echo ""
echo "Useful commands:"
echo "  View job:     gcloud scheduler jobs describe $JOB_NAME --location=$GCP_REGION"
echo "  Run manually: gcloud scheduler jobs run $JOB_NAME --location=$GCP_REGION"
echo "  View logs:    gcloud logging read 'resource.type=cloud_scheduler_job'"
echo ""
echo "The Gmail watch will now be automatically renewed every 6 days!"
echo ""
