#!/bin/bash
# =============================================================================
# Setup Pub/Sub for Gmail Push Notifications
# =============================================================================
#
# This script creates:
# 1. Pub/Sub topic for Gmail notifications
# 2. IAM binding to allow Gmail to publish to the topic
# 3. Push subscription to deliver messages to Cloud Run
#
# Prerequisites:
# - gcloud CLI installed and authenticated
# - Cloud Run service already deployed
# - Pub/Sub API enabled
#
# Usage:
#   ./scripts/setup_pubsub.sh
#
# Environment variables (optional - will prompt if not set):
#   GCP_PROJECT      - Your GCP project ID
#   CLOUD_RUN_URL    - Your Cloud Run service URL
#   SERVICE_ACCOUNT  - Service account for push authentication
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "  Gmail Agent - Pub/Sub Setup"
echo "=============================================="
echo ""

# Get project ID
if [ -z "$GCP_PROJECT" ]; then
    # Try to get from gcloud config
    GCP_PROJECT=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$GCP_PROJECT" ]; then
        echo -e "${YELLOW}Enter your GCP project ID:${NC}"
        read GCP_PROJECT
    fi
fi
echo -e "${GREEN}Using project:${NC} $GCP_PROJECT"

# Get Cloud Run URL
if [ -z "$CLOUD_RUN_URL" ]; then
    echo -e "${YELLOW}Enter your Cloud Run service URL (e.g., https://email-agent-xxx.run.app):${NC}"
    read CLOUD_RUN_URL
fi
echo -e "${GREEN}Using Cloud Run URL:${NC} $CLOUD_RUN_URL"

# Get service account
if [ -z "$SERVICE_ACCOUNT" ]; then
    # Try to get default compute service account
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
TOPIC_NAME="gmail-agent"
SUBSCRIPTION_NAME="gmail-agent-sub"
WEBHOOK_PATH="/webhook/gmail"

echo ""
echo "=============================================="
echo "  Step 1: Enable Pub/Sub API"
echo "=============================================="
gcloud services enable pubsub.googleapis.com --project=$GCP_PROJECT
echo -e "${GREEN}✓ Pub/Sub API enabled${NC}"

echo ""
echo "=============================================="
echo "  Step 2: Create Pub/Sub Topic"
echo "=============================================="
if gcloud pubsub topics describe $TOPIC_NAME --project=$GCP_PROJECT &>/dev/null; then
    echo -e "${YELLOW}Topic '$TOPIC_NAME' already exists${NC}"
else
    gcloud pubsub topics create $TOPIC_NAME --project=$GCP_PROJECT
    echo -e "${GREEN}✓ Created topic: $TOPIC_NAME${NC}"
fi

echo ""
echo "=============================================="
echo "  Step 3: Grant Gmail Publish Permission"
echo "=============================================="
# Gmail uses this special service account to publish
GMAIL_SA="serviceAccount:gmail-api-push@system.gserviceaccount.com"

gcloud pubsub topics add-iam-policy-binding $TOPIC_NAME \
    --project=$GCP_PROJECT \
    --member="$GMAIL_SA" \
    --role="roles/pubsub.publisher" \
    --quiet

echo -e "${GREEN}✓ Granted Gmail permission to publish${NC}"

echo ""
echo "=============================================="
echo "  Step 4: Create Push Subscription"
echo "=============================================="
PUSH_ENDPOINT="${CLOUD_RUN_URL}${WEBHOOK_PATH}"

if gcloud pubsub subscriptions describe $SUBSCRIPTION_NAME --project=$GCP_PROJECT &>/dev/null; then
    echo -e "${YELLOW}Subscription '$SUBSCRIPTION_NAME' already exists${NC}"
    echo "Updating push endpoint..."
    gcloud pubsub subscriptions update $SUBSCRIPTION_NAME \
        --project=$GCP_PROJECT \
        --push-endpoint="$PUSH_ENDPOINT" \
        --push-auth-service-account=$SERVICE_ACCOUNT
else
    gcloud pubsub subscriptions create $SUBSCRIPTION_NAME \
        --project=$GCP_PROJECT \
        --topic=$TOPIC_NAME \
        --push-endpoint="$PUSH_ENDPOINT" \
        --push-auth-service-account=$SERVICE_ACCOUNT \
        --ack-deadline=60 \
        --message-retention-duration=1h
    echo -e "${GREEN}✓ Created subscription: $SUBSCRIPTION_NAME${NC}"
fi

echo ""
echo "=============================================="
echo "  Setup Complete!"
echo "=============================================="
echo ""
echo "Summary:"
echo "  Topic:        projects/$GCP_PROJECT/topics/$TOPIC_NAME"
echo "  Subscription: projects/$GCP_PROJECT/subscriptions/$SUBSCRIPTION_NAME"
echo "  Push URL:     $PUSH_ENDPOINT"
echo ""
echo "Next steps:"
echo "  1. Run ./scripts/setup_scheduler.sh to set up watch renewal"
echo "  2. Call POST /renew-watch to start the Gmail watch"
echo ""
