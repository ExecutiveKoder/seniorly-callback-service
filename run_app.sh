#!/bin/bash

# ============================================
# SENIORLY VOICE AGENT - AUTOMATED LAUNCHER
# ============================================
# Automatically starts WebSocket server, ngrok tunnel, and call interface
# No manual setup required!

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
WEBHOOK_PORT=5000
NGROK_PID_FILE="/tmp/voice_agent_ngrok.pid"
SERVER_PID_FILE="/tmp/voice_agent_server.pid"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up...${NC}"

    # Kill ngrok
    if [ -f "$NGROK_PID_FILE" ]; then
        NGROK_PID=$(cat "$NGROK_PID_FILE")
        if ps -p $NGROK_PID > /dev/null 2>&1; then
            kill $NGROK_PID 2>/dev/null || true
            echo -e "${GREEN}✅ Stopped ngrok${NC}"
        fi
        rm -f "$NGROK_PID_FILE"
    fi

    # Kill webhook server
    if [ -f "$SERVER_PID_FILE" ]; then
        SERVER_PID=$(cat "$SERVER_PID_FILE")
        if ps -p $SERVER_PID > /dev/null 2>&1; then
            kill $SERVER_PID 2>/dev/null || true
            echo -e "${GREEN}✅ Stopped webhook server${NC}"
        fi
        rm -f "$SERVER_PID_FILE"
    fi

    # Kill any remaining processes on port 5000
    lsof -ti:$WEBHOOK_PORT | xargs kill -9 2>/dev/null || true
}

# Register cleanup on exit
trap cleanup EXIT INT TERM

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo -e "${RED}❌ ERROR: ngrok is not installed${NC}"
    echo -e "${YELLOW}Please install ngrok:${NC}"
    echo -e "  brew install ngrok"
    echo -e "  OR download from: https://ngrok.com/download"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ ERROR: Python 3 is not installed${NC}"
    exit 1
fi

# Print banner
echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║${NC}  ${GREEN}🎙️  SENIORLY VOICE AGENT - AUTOMATED LAUNCHER${NC}  ${CYAN}║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Load environment variables
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ ERROR: .env file not found${NC}"
    exit 1
fi

# Source environment variables
export $(cat .env | grep -v '^#' | xargs)

# Display AI configuration
echo -e "${BLUE}📋 Configuration:${NC}"
echo -e "   AI Voice: ${GREEN}${SPEECH_VOICE_NAME}${NC}"
echo -e "   Phone: ${GREEN}${TWILIO_PHONE_NUMBER}${NC}"
echo -e "   Port: ${GREEN}${WEBHOOK_PORT}${NC}"
echo ""

# Step 1: Start WebSocket server in background
echo -e "${YELLOW}🚀 Step 1/3: Starting WebSocket server...${NC}"
python3 twilio_websocket_server.py > /tmp/voice_agent_server.log 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > "$SERVER_PID_FILE"

# Wait for server to start
sleep 3

# Check if server is running
if ! ps -p $SERVER_PID > /dev/null 2>&1; then
    echo -e "${RED}❌ Failed to start webhook server${NC}"
    echo -e "${YELLOW}Check logs: tail -f /tmp/voice_agent_server.log${NC}"
    exit 1
fi

echo -e "${GREEN}✅ WebSocket server started (PID: $SERVER_PID)${NC}"
echo ""

# Step 2: Determine webhook URL (Azure or ngrok)
echo -e "${YELLOW}🌐 Step 2/3: Setting up webhook URL...${NC}"

# Check if Azure endpoint exists
if [ -f ".azure_endpoint" ]; then
    WEBHOOK_URL=$(cat .azure_endpoint)
    echo -e "${GREEN}✅ Using Azure Container Apps endpoint${NC}"
    echo -e "   Public URL: ${CYAN}${WEBHOOK_URL}${NC}"
    echo -e "${BLUE}   (No ngrok needed - running on Azure!)${NC}"
    USE_AZURE=true
else
    # Fall back to ngrok for local testing
    if ! command -v ngrok &> /dev/null; then
        echo -e "${RED}❌ ERROR: No Azure endpoint found and ngrok not installed${NC}"
        echo -e "${YELLOW}Please either:${NC}"
        echo -e "  1. Deploy to Azure: ${GREEN}./deploy_to_azure.sh${NC}"
        echo -e "  2. Install ngrok: ${GREEN}brew install ngrok${NC}"
        exit 1
    fi

    echo -e "${BLUE}ℹ️  Using ngrok (local testing mode)${NC}"
    ngrok http $WEBHOOK_PORT --log=stdout > /tmp/voice_agent_ngrok.log 2>&1 &
    NGROK_PID=$!
    echo $NGROK_PID > "$NGROK_PID_FILE"

    # Wait for ngrok to start and get the URL
    sleep 4

    # Extract ngrok URL
    WEBHOOK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || echo "")

    if [ -z "$WEBHOOK_URL" ]; then
        echo -e "${RED}❌ Failed to get ngrok URL${NC}"
        echo -e "${YELLOW}Check logs: tail -f /tmp/voice_agent_ngrok.log${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Ngrok tunnel started${NC}"
    echo -e "   Public URL: ${CYAN}${WEBHOOK_URL}${NC}"
    USE_AZURE=false
fi
echo ""

# Step 3: Launch interactive call menu
echo -e "${YELLOW}📞 Step 3/3: Ready to make calls!${NC}"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""

# Interactive menu
while true; do
    echo -e "${BLUE}What would you like to do?${NC}"
    echo -e "  ${GREEN}1)${NC} Make an outbound call"
    echo -e "  ${GREEN}2)${NC} View server logs"
    echo -e "  ${GREEN}3)${NC} View ngrok logs"
    echo -e "  ${RED}4)${NC} Exit"
    echo ""
    read -p "Enter choice [1-4]: " choice

    case $choice in
        1)
            # Make a call
            echo ""
            read -p "Enter phone number to call (e.g., 289-324-2125): " phone_number

            if [ -z "$phone_number" ]; then
                echo -e "${RED}❌ No phone number provided${NC}"
                echo ""
                continue
            fi

            read -p "Enter senior's name (default: John): " senior_name
            senior_name=${senior_name:-John}

            echo ""
            echo -e "${YELLOW}📞 Initiating call to ${phone_number} for ${senior_name}...${NC}"
            echo ""

            # Call the Python script with ngrok URL
            python3 - <<EOF
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from src.config import config
from src.services.twilio_service import TwilioService

# Format phone number
destination = "${phone_number}".replace("-", "").replace(" ", "")
if not destination.startswith("+"):
    destination = f"+1{destination}"

# Initialize Twilio service
twilio_service = TwilioService(
    account_sid=config.TWILIO_ACCOUNT_SID,
    auth_token=config.TWILIO_AUTH_TOKEN,
    phone_number=config.TWILIO_PHONE_NUMBER
)

# Make the call
result = twilio_service.initiate_outbound_call(
    destination_phone=destination,
    webhook_url="${WEBHOOK_URL}/voice",
    senior_name="${senior_name}"
)

if result['success']:
    print(f"\\n🎉 CALL INITIATED!")
    print(f"   Call SID: {result['call_sid']}")
    print(f"   Status: {result['status']}")
    print(f"\\n📱 Phone should ring shortly!")
    print(f"🔊 You'll hear {config.get_ai_name()}'s voice via Azure Speech Services\\n")
else:
    print(f"\\n❌ CALL FAILED: {result['error']}\\n")
EOF
            ;;
        2)
            # View server logs
            echo ""
            echo -e "${CYAN}📄 Server Logs (Press Ctrl+C to return to menu):${NC}"
            echo ""
            tail -f /tmp/voice_agent_server.log || true
            echo ""
            ;;
        3)
            # View ngrok logs
            echo ""
            echo -e "${CYAN}📄 Ngrok Logs (Press Ctrl+C to return to menu):${NC}"
            echo ""
            tail -f /tmp/voice_agent_ngrok.log || true
            echo ""
            ;;
        4)
            # Exit
            echo ""
            echo -e "${YELLOW}👋 Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice. Please enter 1-4.${NC}"
            echo ""
            ;;
    esac
done
