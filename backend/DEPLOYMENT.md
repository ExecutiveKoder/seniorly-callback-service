# Deployment Guide

## Two Ways to Test/Use the Voice Agent

### 1. 🎤 Local Testing (Microphone + Speaker)

**Use Case:** Test conversations locally without making real phone calls

```bash
python src/main.py
```

**Features:**
- Talk using your computer's microphone
- Hear responses through speakers
- No phone calls, no telephony costs
- Perfect for testing conversation flow and AI responses
- Completely local (no deployment needed)

**Options:**
1. Voice conversation (microphone/speaker)
2. Text conversation (type messages)
3. View conversation history
4. Test Azure service connections

---

### 2. 📞 Real Phone Calls (Twilio)

**Use Case:** Make actual phone calls to seniors

There are **two options** for running Twilio:

#### Option A: Deploy to Azure (Production)

**Best for:** 24/7 automated calling, no local server needed

**Steps:**
```bash
# 1. Deploy to Azure Container Apps (one-time setup)
./deploy_to_azure.sh

# 2. Make calls using Azure endpoint
./run_app.sh
```

**Advantages:**
- ✅ Runs 24/7 in the cloud
- ✅ No local server needed
- ✅ No ngrok required
- ✅ Permanent public URL
- ✅ Scalable and reliable

**What happens:**
1. `deploy_to_azure.sh` builds Docker image and pushes to Azure
2. Azure Container Apps gets a permanent public URL
3. `run_app.sh` detects Azure endpoint and uses it
4. Make calls anytime - server is always running

---

#### Option B: Local Server + ngrok (Development/Testing)

**Best for:** Quick testing before Azure deployment

**Steps:**
```bash
# 1. Install ngrok (one-time)
brew install ngrok

# 2. Run local server + make calls
./run_app.sh
```

**Advantages:**
- ✅ Quick setup for testing
- ✅ See logs in real-time
- ✅ Iterate quickly during development

**Disadvantages:**
- ❌ Must keep terminal open
- ❌ Requires ngrok running
- ❌ Not suitable for 24/7 operation
- ❌ Local machine must be online

---

## Recommended Workflow

### Phase 1: Initial Development
```bash
# Test conversations locally (no phone)
python src/main.py
# Select option 1 (voice) or 2 (text)
```

### Phase 2: Phone Call Testing
```bash
# Quick test with ngrok
brew install ngrok
./run_app.sh
```

### Phase 3: Production Deployment
```bash
# Deploy to Azure for 24/7 operation
./deploy_to_azure.sh

# Make calls using Azure endpoint
./run_app.sh
```

---

## Architecture Comparison

### Local Testing (Microphone)
```
Your Computer
├── Microphone → Azure Speech STT
├── Azure OpenAI GPT-5
└── Azure Speech TTS → Speaker
```

### Twilio + ngrok (Local Server)
```
Phone Call
    ↓
Twilio
    ↓
ngrok tunnel → Your Computer (WebSocket Server)
    ↓
Azure Speech Services (Jason's voice)
Azure OpenAI GPT-5
```

### Twilio + Azure (Production)
```
Phone Call
    ↓
Twilio
    ↓
Azure Container Apps (WebSocket Server) [24/7]
    ↓
Azure Speech Services (Jason's voice)
Azure OpenAI GPT-5
Azure Cosmos DB (conversation storage)
```

---

## Cost Comparison

### Local Testing (Microphone)
- Azure OpenAI: ~$0.10-0.15 per 5-min conversation
- Azure Speech: ~$0.13 per 5-min conversation
- **Total: ~$0.25 per test**

### Twilio Calls (Either ngrok or Azure)
- Twilio calling: ~$0.013/min = ~$0.065 per 5-min call
- Azure OpenAI: ~$0.10-0.15 per 5-min call
- Azure Speech: ~$0.13 per 5-min call
- Azure Container Apps: ~$0.01 per call (if deployed)
- **Total: ~$0.30-0.35 per call**

---

## Deployment Commands

### Deploy to Azure
```bash
./deploy_to_azure.sh
```

This script:
1. Builds Docker image from Dockerfile
2. Pushes to Azure Container Registry
3. Updates Azure Container Apps
4. Injects environment variables from .env
5. Enables external ingress on port 5000
6. Saves public URL to `.azure_endpoint`

### Make Calls
```bash
./run_app.sh
```

This script:
1. Checks if `.azure_endpoint` exists
   - If yes: Uses Azure URL (no ngrok needed)
   - If no: Starts ngrok for local testing
2. Starts WebSocket server (if using ngrok)
3. Presents interactive menu for calls

### Remove Azure Endpoint (Force ngrok)
```bash
rm .azure_endpoint
./run_app.sh  # Will use ngrok
```

---

## Troubleshooting

### "ngrok is not installed"
```bash
# Option 1: Deploy to Azure (no ngrok needed)
./deploy_to_azure.sh

# Option 2: Install ngrok
brew install ngrok
```

### "No Azure endpoint found"
```bash
# Deploy to Azure first
./deploy_to_azure.sh
```

### Test Local Voice Without Phones
```bash
# Use microphone/speaker mode
python src/main.py
# Select option 1
```

---

## Summary

- **Local testing:** `python src/main.py` (microphone + speaker)
- **Phone calls (dev):** `brew install ngrok && ./run_app.sh`
- **Phone calls (prod):** `./deploy_to_azure.sh && ./run_app.sh`
