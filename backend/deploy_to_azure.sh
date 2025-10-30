#!/bin/bash

# ============================================
# DEPLOY TWILIO WEBSOCKET SERVER TO AZURE
# ============================================
# Builds Docker image and deploys to Azure Container Apps
# Creates permanent public endpoint (no ngrok needed!)

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Load environment variables
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ ERROR: .env file not found${NC}"
    exit 1
fi

export $(cat .env | grep -v '^#' | xargs)

# Configuration from .env
RESOURCE_GROUP="${RESOURCE_GROUP:-voice-agent-rg}"
ACR_NAME="${ACR_USERNAME:-myvoiceagentacr}"
ACR_LOGIN_SERVER="${ACR_LOGIN_SERVER}"
CONTAINER_APP_NAME="voice-agent-app"
CONTAINER_APP_ENV="voice-agent-env"
IMAGE_NAME="twilio-websocket-server"
IMAGE_TAG="latest"

# Print banner
echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${GREEN}🚀 DEPLOYING TO AZURE CONTAINER APPS${NC}           ${CYAN}║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📋 Configuration:${NC}"
echo -e "   Resource Group: ${GREEN}${RESOURCE_GROUP}${NC}"
echo -e "   Container Registry: ${GREEN}${ACR_LOGIN_SERVER}${NC}"
echo -e "   Container App: ${GREEN}${CONTAINER_APP_NAME}${NC}"
echo -e "   Image: ${GREEN}${IMAGE_NAME}:${IMAGE_TAG}${NC}"
echo ""

# Step 1: Build Docker image
echo -e "${YELLOW}🔨 Step 1/5: Building Docker image...${NC}"
docker build --load -t ${IMAGE_NAME}:${IMAGE_TAG} .

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker build failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker image built successfully${NC}"
echo ""

# Step 2: Login to Azure Container Registry
echo -e "${YELLOW}🔐 Step 2/5: Logging into Azure Container Registry...${NC}"
echo $ACR_PASSWORD | docker login $ACR_LOGIN_SERVER --username $ACR_USERNAME --password-stdin

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ ACR login failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Logged into ACR${NC}"
echo ""

# Step 3: Tag and push image
echo -e "${YELLOW}📤 Step 3/5: Pushing image to Azure Container Registry...${NC}"
FULL_IMAGE_NAME="${ACR_LOGIN_SERVER}/${IMAGE_NAME}:${IMAGE_TAG}"
docker tag ${IMAGE_NAME}:${IMAGE_TAG} ${FULL_IMAGE_NAME}
docker push ${FULL_IMAGE_NAME}

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Docker push failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Image pushed to ACR${NC}"
echo ""

# Step 4: Update Container App with environment variables
echo -e "${YELLOW}⚙️  Step 4/5: Deploying to Container App...${NC}"

az containerapp update \
    --name ${CONTAINER_APP_NAME} \
    --resource-group ${RESOURCE_GROUP} \
    --image ${FULL_IMAGE_NAME} \
    --set-env-vars \
        AZURE_OPENAI_KEY="${AZURE_OPENAI_KEY}" \
        AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT}" \
        AZURE_OPENAI_DEPLOYMENT_NAME="${AZURE_OPENAI_DEPLOYMENT_NAME}" \
        AZURE_OPENAI_API_VERSION="${AZURE_OPENAI_API_VERSION}" \
        AZURE_SPEECH_KEY="${AZURE_SPEECH_KEY}" \
        AZURE_SPEECH_REGION="${AZURE_SPEECH_REGION}" \
        SPEECH_VOICE_NAME="${SPEECH_VOICE_NAME}" \
        AZURE_COSMOS_ENDPOINT="${AZURE_COSMOS_ENDPOINT}" \
        AZURE_COSMOS_KEY="${AZURE_COSMOS_KEY}" \
        COSMOS_DATABASE="${COSMOS_DATABASE}" \
        COSMOS_CONTAINER="${COSMOS_CONTAINER}" \
        AZURE_REDIS_HOST="${AZURE_REDIS_HOST}" \
        AZURE_REDIS_KEY="${AZURE_REDIS_KEY}" \
        REDIS_PORT="${REDIS_PORT}" \
        REDIS_SSL="${REDIS_SSL}" \
    --min-replicas 1 \
    --max-replicas 3 \
    --target-port 5000 \
    --ingress external \
    --query properties.configuration.ingress.fqdn \
    --output tsv > /tmp/container_app_url.txt

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Container App update failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Container App updated${NC}"
echo ""

# Step 5: Get the public URL
echo -e "${YELLOW}🌐 Step 5/5: Getting public endpoint...${NC}"
CONTAINER_APP_URL=$(cat /tmp/container_app_url.txt)

if [ -z "$CONTAINER_APP_URL" ]; then
    echo -e "${YELLOW}⚠️  Getting URL from az command...${NC}"
    CONTAINER_APP_URL=$(az containerapp show \
        --name ${CONTAINER_APP_NAME} \
        --resource-group ${RESOURCE_GROUP} \
        --query properties.configuration.ingress.fqdn \
        --output tsv)
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ DEPLOYMENT SUCCESSFUL!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${CYAN}🌐 Public Endpoint:${NC}"
echo -e "   ${YELLOW}https://${CONTAINER_APP_URL}${NC}"
echo ""
echo -e "${CYAN}📋 WebSocket URL for Twilio:${NC}"
echo -e "   ${YELLOW}wss://${CONTAINER_APP_URL}/media-stream${NC}"
echo ""
echo -e "${CYAN}📋 Voice Webhook URL for Twilio:${NC}"
echo -e "   ${YELLOW}https://${CONTAINER_APP_URL}/voice${NC}"
echo ""
echo -e "${BLUE}🎯 Next Steps:${NC}"
echo -e "   1. Update Twilio to use this webhook URL"
echo -e "   2. Run: ${GREEN}./run_app.sh${NC} to make calls"
echo -e "   3. No more ngrok needed!"
echo ""
echo -e "${YELLOW}💡 Tip: Save this URL - it's permanent!${NC}"
echo ""

# Save URL to file for run_app.sh to use
echo "https://${CONTAINER_APP_URL}" > .azure_endpoint

echo -e "${GREEN}✅ Endpoint saved to .azure_endpoint${NC}"
echo ""
