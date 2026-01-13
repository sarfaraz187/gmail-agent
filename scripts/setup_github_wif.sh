#!/bin/bash
# Setup Workload Identity Federation for GitHub Actions
#
# This script creates the necessary GCP resources to allow GitHub Actions
# to authenticate with GCP without using service account keys.
#
# Run this script once to set up the trust relationship.

set -e

# Configuration - Update these values
PROJECT_ID="ai-agents-484013"
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
REGION="europe-west1"
POOL_NAME="github-actions-pool"
PROVIDER_NAME="github-actions-provider"
SERVICE_ACCOUNT_NAME="github-actions-deployer"
GITHUB_REPO="sarfaraz187/Google-Email-Agent"  # Your GitHub repo

echo "=== Setting up Workload Identity Federation ==="
echo "Project ID: $PROJECT_ID"
echo "Project Number: $PROJECT_NUMBER"
echo "GitHub Repo: $GITHUB_REPO"
echo ""

# Enable required APIs
echo "1. Enabling required APIs..."
gcloud services enable iamcredentials.googleapis.com --project=$PROJECT_ID
gcloud services enable iam.googleapis.com --project=$PROJECT_ID

# Create Workload Identity Pool
echo "2. Creating Workload Identity Pool..."
gcloud iam workload-identity-pools create $POOL_NAME \
  --project=$PROJECT_ID \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  --description="Pool for GitHub Actions authentication" \
  2>/dev/null || echo "Pool already exists, continuing..."

# Create Workload Identity Provider
echo "3. Creating Workload Identity Provider..."
gcloud iam workload-identity-pools providers create-oidc $PROVIDER_NAME \
  --project=$PROJECT_ID \
  --location="global" \
  --workload-identity-pool=$POOL_NAME \
  --display-name="GitHub Actions Provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner" \
  --attribute-condition="assertion.repository_owner == '${GITHUB_REPO%%/*}'" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  2>/dev/null || echo "Provider already exists, continuing..."

# Create Service Account for GitHub Actions
echo "4. Creating Service Account..."
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
  --project=$PROJECT_ID \
  --display-name="GitHub Actions Deployer" \
  --description="Service account for GitHub Actions CI/CD" \
  2>/dev/null || echo "Service account already exists, continuing..."

SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# Grant necessary roles to Service Account
echo "5. Granting roles to Service Account..."

# Cloud Run Admin - to deploy services
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/run.admin" \
  --quiet

# Artifact Registry Writer - to push images
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/artifactregistry.writer" \
  --quiet

# Service Account User - to act as service accounts
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/iam.serviceAccountUser" \
  --quiet

# Allow GitHub Actions to impersonate the Service Account
echo "6. Binding Workload Identity to Service Account..."
gcloud iam service-accounts add-iam-policy-binding $SERVICE_ACCOUNT_EMAIL \
  --project=$PROJECT_ID \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/attribute.repository/${GITHUB_REPO}"

# Output the values needed for GitHub
echo ""
echo "=== SETUP COMPLETE ==="
echo ""
echo "Add these as GitHub Repository Variables (Settings > Secrets and variables > Actions > Variables):"
echo ""
echo "WIF_PROVIDER:"
echo "projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_NAME}/providers/${PROVIDER_NAME}"
echo ""
echo "WIF_SERVICE_ACCOUNT:"
echo "$SERVICE_ACCOUNT_EMAIL"
echo ""
