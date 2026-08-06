#!/bin/bash
# Setup script for Google Cloud Storage video bucket
# Run this once to configure GCS for video generation

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${1:-project-e6d513b1-db45-4ab3-9a1}"
BUCKET_NAME="${2:-project-e6d513b1-video-outputs}"
LOCATION="${3:-us-central1}"

echo -e "${YELLOW}🎬 Setting up Google Cloud Storage for Video Generation${NC}"
echo "Project ID: $PROJECT_ID"
echo "Bucket Name: $BUCKET_NAME"
echo "Location: $LOCATION"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Please install Google Cloud SDK.${NC}"
    exit 1
fi

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${RED}❌ Not authenticated. Run: gcloud auth login${NC}"
    exit 1
fi

echo -e "${GREEN}✓ gcloud authenticated${NC}"
echo ""

# Step 1: Create GCS bucket
echo -e "${YELLOW}1. Creating GCS bucket...${NC}"
if gsutil ls "gs://$BUCKET_NAME" &> /dev/null; then
    echo -e "${GREEN}✓ Bucket already exists${NC}"
else
    gsutil mb -p "$PROJECT_ID" -c STANDARD -l "$LOCATION" "gs://$BUCKET_NAME"
    echo -e "${GREEN}✓ Bucket created${NC}"
fi
echo ""

# Step 2: Set bucket versioning (optional, for recovery)
echo -e "${YELLOW}2. Enabling versioning (optional)...${NC}"
gsutil versioning set on "gs://$BUCKET_NAME"
echo -e "${GREEN}✓ Versioning enabled${NC}"
echo ""

# Step 3: Set lifecycle policy (delete old videos after 30 days)
echo -e "${YELLOW}3. Setting lifecycle policy (auto-delete after 30 days)...${NC}"
cat > /tmp/lifecycle.json << 'EOF'
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
gsutil lifecycle set /tmp/lifecycle.json "gs://$BUCKET_NAME"
rm /tmp/lifecycle.json
echo -e "${GREEN}✓ Lifecycle policy set${NC}"
echo ""

# Step 4: Provision Vertex AI service identity
echo -e "${YELLOW}4. Provisioning Vertex AI Service Identity...${NC}"
gcloud beta services identity create \
    --service=aiplatform.googleapis.com \
    --project="$PROJECT_ID"
echo -e "${GREEN}✓ Service identity created${NC}"
echo ""

# Step 5: Grant storage permissions
echo -e "${YELLOW}5. Granting storage permissions to Vertex AI...${NC}"
SERVICE_ACCOUNT="service-$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')@gcp-sa-aiplatform.iam.gserviceaccount.com"

# Add storage.objectAdmin role
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/storage.objectAdmin" \
    --condition=None \
    --quiet

echo -e "${GREEN}✓ Permissions granted to: $SERVICE_ACCOUNT${NC}"
echo ""

# Step 6: Verify setup
echo -e "${YELLOW}6. Verifying setup...${NC}"
gsutil ls "gs://$BUCKET_NAME"
echo -e "${GREEN}✓ Setup verification complete${NC}"
echo ""

# Step 7: Display configuration
echo -e "${GREEN}✓ GCS Setup Complete!${NC}"
echo ""
echo "Update your .env file with:"
echo "  VERTEX_VIDEO_OUTPUT_GCS_URI=gs://$BUCKET_NAME/"
echo "  GCS_BUCKET_NAME=$BUCKET_NAME"
echo ""
echo "Next steps:"
echo "  1. Update backend/.env with the values above"
echo "  2. Restart backend server"
echo "  3. Run: python demo_video_generation.py"
