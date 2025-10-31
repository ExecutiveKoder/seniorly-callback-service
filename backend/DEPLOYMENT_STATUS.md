# Voice Agent Deployment Status

**Last Updated:** October 31, 2025
**Version:** 2.5 (Multi-layer noise filtering)
**Status:** ✅ DEPLOYED TO PRODUCTION

---

## 🚀 What's Deployed

### Production URL
```
https://voice-agent-backend.grayriver-5405228a.eastus2.azurecontainerapps.io
```

### Current Image
```
myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:latest
Tag: v2.5-noise-filtering
Revision: voice-agent-backend--0000016
```

### Features Live in Production
✅ **Multi-layer noise filtering** (5 layers)
- Volume threshold (RMS 0.05)
- Zero-crossing rate detection
- Dynamic range analysis
- Spectral centroid frequency check
- Sustained speech requirement (2 chunks)

✅ **Service warmup on startup**
- Azure Speech TTS warmup
- Azure OpenAI warmup
- Reduces first-call latency

✅ **Cold start mitigation**
- Min replicas: 1 (always running)
- Azure Logic App keepalive (pings /health every 2 minutes)
- Container stays warm and ready

---

## 📊 Infrastructure

### Container App Configuration
| Setting | Value |
|---------|-------|
| Name | voice-agent-backend |
| Resource Group | voice-agent-rg |
| Region | East US 2 |
| Min Replicas | 1 |
| Max Replicas | 3 |
| CPU | 0.5 cores |
| Memory | 1 GB |
| Port | 5000 |

### Azure Services
- **Azure Container Apps**: `voice-agent-backend`
- **Azure Container Registry**: `myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io`
- **Azure Logic App**: `voice-agent-keepalive` (keepalive pings)
- **Azure Speech**: `en-US-SaraNeural` voice
- **Azure OpenAI**: GPT-5 chat model
- **Azure Cosmos DB**: Conversations + profiles
- **Azure Redis**: Session state
- **Azure PostgreSQL**: Analytics

---

## 🔍 Health Check

```bash
# Check if service is healthy
curl https://voice-agent-backend.grayriver-5405228a.eastus2.azurecontainerapps.io/health

# Expected response:
{
  "status": "healthy",
  "services": {
    "agent": "ready",
    "speech": "ready",
    "openai": "ready",
    "data": "ready"
  }
}
```

---

## 🔄 Deployment Process

### Quick Deploy (Latest Code)
```bash
# 1. Build Docker image
cd backend
docker build --platform linux/amd64 --load -t myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:latest .

# 2. Push to Azure Container Registry
az acr login --name myvoiceagentacr
docker push myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:latest

# 3. Update Container App (auto-pulls latest)
az containerapp update \
  --name voice-agent-backend \
  --resource-group voice-agent-rg \
  --image myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:latest
```

### Deploy Specific Version
```bash
# Tag with version
docker tag myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:latest \
           myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:v2.5

# Push version tag
docker push myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:v2.5

# Deploy specific version
az containerapp update \
  --name voice-agent-backend \
  --resource-group voice-agent-rg \
  --image myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:v2.5
```

---

## 📝 Recent Changes

### v2.5 (October 31, 2025)
- **Multi-layer noise filtering**: 5-layer VAD system to reject background noise
- **Sustained speech detection**: Requires 2 consecutive chunks (~4s) before processing
- **Detailed logging**: Shows why audio is rejected (volume, ZCR, dynamic range, frequency)
- **Azure Logic App keepalive**: Pings /health every 2 minutes to prevent cold starts

### v2.4 (October 30, 2025)
- Service warmup on startup (Speech + OpenAI)
- Health check endpoint improvements
- Reverted to stable WebSocket initialization

---

## 🐛 Troubleshooting

### Container won't start
```bash
# Check logs
az containerapp logs show --name voice-agent-backend --resource-group voice-agent-rg --tail 100
```

### Health check failing
```bash
# Check specific service
curl https://voice-agent-backend.grayriver-5405228a.eastus2.azurecontainerapps.io/health | jq
```

### Image pull errors
```bash
# Verify ACR credentials
az containerapp show --name voice-agent-backend --resource-group voice-agent-rg \
  --query "properties.configuration.registries"

# Re-add credentials if needed
az acr credential show --name myvoiceagentacr
az containerapp registry set \
  --name voice-agent-backend \
  --resource-group voice-agent-rg \
  --server myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io \
  --username myvoiceagentacr \
  --password <password>
```

### Cold starts still happening
```bash
# Verify Logic App is running
az logic workflow show --name voice-agent-keepalive --resource-group voice-agent-rg \
  --query "{Name:name, State:state}"

# Check run history
az logic workflow run list --resource-group voice-agent-rg --name voice-agent-keepalive
```

---

## 💰 Cost Estimate

| Service | Monthly Cost |
|---------|-------------|
| Container Apps (1 min replica) | ~$30 |
| Logic App (43,200 runs/month) | ~$0 (free tier) |
| Container Registry | ~$5 |
| **Total Infrastructure** | **~$35/month** |

*Does not include Azure Speech, OpenAI, Cosmos, Redis, PostgreSQL*

---

## 🔐 Security

- ✅ All connections use HTTPS/TLS 1.2+
- ✅ ACR credentials stored as Container App secrets
- ✅ Environment variables for sensitive keys
- ✅ No hard-coded credentials in code
- ✅ Redis uses SSL (port 6380)
- ✅ PostgreSQL enforces SSL connections

---

## 📞 Contact

**Deployed by:** Claude Code
**Repository:** https://github.com/ExecutiveKoder/seniorly-callback-service
**Azure Subscription:** Microsoft Azure Sponsorship
**Resource Group:** voice-agent-rg
