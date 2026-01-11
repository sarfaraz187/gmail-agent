#!/bin/bash
# =============================================================================
# Setup Firestore for History Tracking
# =============================================================================
#
# This script:
# 1. Enables the Firestore API
# 2. Creates a Firestore database in Native mode
#
# We use Firestore to store the last processed Gmail historyId,
# ensuring we don't miss emails between push notifications.
#
# Prerequisites:
# - gcloud CLI installed and authenticated
#
# Usage:
#   ./scripts/setup_firestore.sh
#
# Environment variables (optional):
#   GCP_PROJECT  - Your GCP project ID
#   GCP_REGION   - Region for Firestore (default: europe-west1)
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=============================================="
echo "  Gmail Agent - Firestore Setup"
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

echo ""
echo "=============================================="
echo "  Step 1: Enable Firestore API"
echo "=============================================="
gcloud services enable firestore.googleapis.com --project=$GCP_PROJECT
echo -e "${GREEN}✓ Firestore API enabled${NC}"

echo ""
echo "=============================================="
echo "  Step 2: Create Firestore Database"
echo "=============================================="

# Check if database already exists
if gcloud firestore databases describe --project=$GCP_PROJECT &>/dev/null; then
    echo -e "${YELLOW}Firestore database already exists${NC}"
else
    echo "Creating Firestore database in Native mode..."
    gcloud firestore databases create \
        --project=$GCP_PROJECT \
        --location=$GCP_REGION \
        --type=firestore-native
    echo -e "${GREEN}✓ Created Firestore database${NC}"
fi

echo ""
echo "=============================================="
echo "  Setup Complete!"
echo "=============================================="
echo ""
echo "Firestore is ready for storing Gmail history IDs."
echo ""
echo "The agent will automatically create the collection"
echo "'email_agent_state' when it first runs."
echo ""
