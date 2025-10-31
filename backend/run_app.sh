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
echo -e "  ${GREEN}3)${NC} Phone Calls via Twilio (Local + ngrok)"
echo -e "     ${CYAN}→ Development/testing mode${NC}"
echo -e "     ${CYAN}→ Requires: brew install ngrok${NC}"
echo ""
echo -e "  ${RED}4)${NC} Exit"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"
echo ""

read -p "Enter choice [1-4]: " main_choice

case $main_choice in
    1)
        # Local testing with microphone
        echo ""
        echo -e "${GREEN}🎤 Starting local voice testing...${NC}"
        echo ""
        python src/main.py --voice
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
        echo -e "${GREEN}✅ Using Azure endpoint:${NC} ${CYAN}${WEBHOOK_URL}${NC}"
        echo ""

        # Make call using Azure endpoint
        read -p "Enter phone number to call (e.g., 289-324-2125): " phone_number
        if [ -z "$phone_number" ]; then
            echo -e "${RED}❌ No phone number provided${NC}"
            exit 1
        fi

        read -p "Enter senior's name (default: John): " senior_name
        senior_name=${senior_name:-John}

        echo ""
        echo -e "${YELLOW}📞 Calling ${phone_number}...${NC}"

        python - <<EOF
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from src.config import config
from src.services.twilio_service import TwilioService

destination = "${phone_number}".replace("-", "").replace(" ", "")
if not destination.startswith("+"):
    destination = f"+1{destination}"

twilio_service = TwilioService(
    account_sid=config.TWILIO_ACCOUNT_SID,
    auth_token=config.TWILIO_AUTH_TOKEN,
    phone_number=config.TWILIO_PHONE_NUMBER
)

result = twilio_service.initiate_outbound_call(
    destination_phone=destination,
    webhook_url="${WEBHOOK_URL}/voice",
    senior_name="${senior_name}"
)

if result['success']:
    print(f"\n🎉 CALL INITIATED!")
    print(f"   Call SID: {result['call_sid']}")
    print(f"   Status: {result['status']}")
    print(f"\n📱 Phone should ring shortly!")
else:
    print(f"\n❌ CALL FAILED: {result['error']}\n")
EOF
        ;;
    3)
        # Phone calls using ngrok
        echo ""
        if ! command -v ngrok &> /dev/null; then
            echo -e "${RED}❌ ngrok is not installed${NC}"
            echo -e "${YELLOW}Please install:${NC} ${GREEN}brew install ngrok${NC}"
            exit 1
        fi

        # Start local server with ngrok
        WEBHOOK_PORT=5000
        NGROK_PID_FILE="/tmp/voice_agent_ngrok.pid"
        SERVER_PID_FILE="/tmp/voice_agent_server.pid"

        cleanup() {
            echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"
            [ -f "$NGROK_PID_FILE" ] && kill $(cat "$NGROK_PID_FILE") 2>/dev/null || true
            [ -f "$SERVER_PID_FILE" ] && kill $(cat "$SERVER_PID_FILE") 2>/dev/null || true
            lsof -ti:$WEBHOOK_PORT | xargs kill -9 2>/dev/null || true
            rm -f "$NGROK_PID_FILE" "$SERVER_PID_FILE"
        }

        trap cleanup EXIT INT TERM

        echo -e "${YELLOW}🚀 Starting WebSocket server...${NC}"
        python3 twilio_websocket_server.py > /tmp/voice_agent_server.log 2>&1 &
        echo $! > "$SERVER_PID_FILE"
        sleep 3

        echo -e "${YELLOW}🌐 Starting ngrok tunnel...${NC}"
        ngrok http $WEBHOOK_PORT --log=stdout > /tmp/voice_agent_ngrok.log 2>&1 &
        echo $! > "$NGROK_PID_FILE"
        sleep 4

        WEBHOOK_URL=$(curl -s http://localhost:4040/api/tunnels | python -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || echo "")

        if [ -z "$WEBHOOK_URL" ]; then
            echo -e "${RED}❌ Failed to get ngrok URL${NC}"
            exit 1
        fi

        echo -e "${GREEN}✅ Server ready at:${NC} ${CYAN}${WEBHOOK_URL}${NC}"
        echo ""

        while true; do
            echo -e "${BLUE}Options:${NC}"
            echo -e "  ${GREEN}1)${NC} Make a call"
            echo -e "  ${GREEN}2)${NC} View logs"
            echo -e "  ${RED}3)${NC} Exit"
            echo ""
            read -p "Choice: " choice

            case $choice in
                1)
                    read -p "Phone number: " phone
                    if [ -z "$phone" ]; then
                        echo -e "${RED}❌ No phone number${NC}"
                        continue
                    fi
                    read -p "Name (default: John): " name
                    name=${name:-John}

                    python - <<PYTHON_EOF
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from src.config import config
from src.services.twilio_service import TwilioService

dest = "${phone}".replace("-", "").replace(" ", "")
if not dest.startswith("+"):
    dest = f"+1{dest}"

svc = TwilioService(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN, config.TWILIO_PHONE_NUMBER)
result = svc.initiate_outbound_call(dest, "${WEBHOOK_URL}/voice", "${name}")

if result["success"]:
    print(f"\n🎉 Call initiated: {result['call_sid']}\n")
else:
    print(f"\n❌ Failed: {result['error']}\n")
PYTHON_EOF
                    ;;
                2)
                    tail -f /tmp/voice_agent_server.log
                    ;;
                3)
                    exit 0
                    ;;
            esac
        done
        ;;
    4)
        echo ""
        echo -e "${YELLOW}👋 Goodbye!${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac
