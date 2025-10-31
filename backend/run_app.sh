#!/bin/bash

# ============================================
# SENIORLY VOICE AGENT - LAUNCHER
# ============================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Print banner
echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${GREEN}🎙️  SENIORLY VOICE AGENT${NC}                      ${CYAN}║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo -e "${GREEN}✅ Activating virtual environment...${NC}"
    source venv/bin/activate
else
    echo -e "${YELLOW}⚠️  No virtual environment found. Creating one...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    echo -e "${GREEN}✅ Installing dependencies...${NC}"
    pip install -r requirements.txt > /dev/null 2>&1
fi
echo ""

# Load environment variables
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ ERROR: .env file not found${NC}"
    exit 1
fi

export $(cat .env | grep -v '^#' | xargs)

# Display AI configuration
echo -e "${BLUE}📋 Configuration:${NC}"
echo -e "   AI Voice: ${GREEN}${SPEECH_VOICE_NAME}${NC}"
echo ""

# Main menu
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}How would you like to test the voice agent?${NC}"
echo ""
echo -e "  ${GREEN}1)${NC} Local Testing (Microphone + Speaker)"
echo -e "     ${CYAN}→ Test conversations using your computer${NC}"
echo -e "     ${CYAN}→ No phone calls, no costs${NC}"
echo ""
echo -e "  ${GREEN}2)${NC} Phone Calls via Twilio (Using Azure Endpoint)"
echo -e "     ${CYAN}→ Make real phone calls${NC}"
echo -e "     ${CYAN}→ Requires: ./deploy_to_azure.sh (one-time setup)${NC}"
echo ""
echo -e "  ${RED}3)${NC} Exit"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

read -p "Enter choice [1-3]: " main_choice

case $main_choice in
    1)
        # Local testing with microphone
        echo ""
        echo -e "${GREEN}🎤 Starting local voice testing...${NC}"
        echo ""
        ./venv/bin/python src/main.py --voice
        ;;
    2)
        # Phone calls using Azure endpoint
        echo ""
        if [ ! -f ".azure_endpoint" ]; then
            echo -e "${RED}❌ No Azure endpoint found${NC}"
            echo -e "${YELLOW}Please deploy to Azure first:${NC}"
            echo -e "  ${GREEN}./deploy_to_azure.sh${NC}"
            echo ""
            exit 1
        fi

        WEBHOOK_URL=$(cat .azure_endpoint)
        # Ensure scheme is present (the file may contain only the FQDN)
        if [[ "$WEBHOOK_URL" != http* ]]; then
            WEBHOOK_URL="https://${WEBHOOK_URL}"
        fi
        echo -e "${GREEN}✅ Using Azure endpoint:${NC} ${CYAN}${WEBHOOK_URL}${NC}"
        echo ""

        # Wait for services to warm up
        echo -e "${YELLOW}⏳ Checking if container is ready...${NC}"
        MAX_RETRIES=30
        RETRY_COUNT=0
        HEALTH_URL="${WEBHOOK_URL}/health"

        while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
            HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null || echo "000")

            if [ "$HTTP_CODE" = "200" ]; then
                echo -e "${GREEN}✅ Container is ready! All services initialized.${NC}"
                echo ""
                break
            fi

            RETRY_COUNT=$((RETRY_COUNT + 1))
            echo -e "   Still warming up... ($RETRY_COUNT/$MAX_RETRIES)"
            sleep 2
        done

        if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
            echo -e "${RED}❌ Container failed to become ready after $MAX_RETRIES attempts${NC}"
            echo -e "${YELLOW}Try again in a few minutes or check Azure logs${NC}"
            exit 1
        fi

        # Make call using Azure endpoint
        read -p "Enter phone number to call (e.g., 289-324-2125): " phone_number
        if [ -z "$phone_number" ]; then
            echo -e "${RED}❌ No phone number provided${NC}"
            exit 1
        fi

        read -p "Enter senior's name (default: John): " senior_name
        senior_name=${senior_name:-John}

        echo ""
        echo -e "${YELLOW}📞 Pre-loading senior context...${NC}"
        echo -e "${CYAN}   (This takes 15-30 seconds but eliminates call delay)${NC}"

        # Use the new /initiate-call endpoint that pre-loads context
        RESPONSE=$(curl -s -X POST "${WEBHOOK_URL}/initiate-call" \
            -H "Content-Type: application/json" \
            -d "{\"phone_number\": \"${phone_number}\"}")

        SUCCESS=$(echo "$RESPONSE" | grep -o '"success":\s*true' || echo "")

        if [ -n "$SUCCESS" ]; then
            CALL_SID=$(echo "$RESPONSE" | grep -o '"call_sid":\s*"[^"]*"' | cut -d'"' -f4)
            echo ""
            echo -e "${GREEN}🎉 CALL INITIATED!${NC}"
            echo -e "   ${CYAN}Call SID: ${CALL_SID}${NC}"
            echo -e "   ${CYAN}Context: Pre-loaded (no delay when answered!)${NC}"
            echo ""
            echo -e "${GREEN}📱 Phone should ring shortly!${NC}"
        else
            ERROR=$(echo "$RESPONSE" | grep -o '"error":\s*"[^"]*"' | cut -d'"' -f4)
            echo ""
            echo -e "${RED}❌ CALL FAILED: ${ERROR}${NC}"
            echo ""
        fi
        ;;
    3)
        echo ""
        echo -e "${YELLOW}👋 Goodbye!${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac
