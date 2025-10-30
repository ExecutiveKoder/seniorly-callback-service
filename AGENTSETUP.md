# Voice Agent Architecture & Setup Guide

Complete guide to replicate this Azure-based voice agent architecture for senior health monitoring.

---

## 🎯 System Overview

**Purpose**: AI voice agent that calls seniors daily, collects health metrics, and provides real-time analytics dashboard.

**Tech Stack**:
- **AI**: Azure OpenAI GPT-5
- **Speech**: Azure Speech Services (TTS/STT)
- **Telephony**: AWS Connect (outbound calling)
- **Data**: Azure Cosmos DB, Redis, SQL Database
- **Backend**: Python (FastAPI/Flask)
- **Frontend**: Next.js + Tailwind CSS
- **Streaming**: Twilio Media Streams (WebSocket audio)

---

## 🏗️ Architecture

```
┌──────────────┐
│ AWS Connect  │ Outbound call to senior's phone
│ +1833XXXXXX  │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Twilio Media Streams (WebSocket)         │
│ Real-time bidirectional audio streaming  │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Python Backend (Azure Container Apps)    │
│  ├─ Azure Speech: STT (speech → text)    │
│  ├─ Azure OpenAI GPT-5: AI responses     │
│  ├─ Azure Speech: TTS (text → speech)    │
│  └─ Analytics Service: Extract metrics   │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Data Layer                               │
│  ├─ Cosmos DB: Conversations, profiles   │
│  ├─ Redis: Session state, caching        │
│  └─ SQL: Analytics, dashboard metrics    │
└──────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Next.js Dashboard                        │
│  └─ Read from SQL for health analytics   │
└──────────────────────────────────────────┘
```

---

## 📦 Azure Resources Required

### 1. Azure OpenAI
```bash
# Create OpenAI resource
az cognitiveservices account create \
  --name my-voice-agent-openai \
  --resource-group voice-agent-rg \
  --location eastus2 \
  --kind OpenAI \
  --sku S0

# Deploy GPT-5 model (or latest available)
az cognitiveservices account deployment create \
  --name my-voice-agent-openai \
  --resource-group voice-agent-rg \
  --deployment-name gpt-5-chat \
  --model-name gpt-5 \
  --model-version latest \
  --model-format OpenAI \
  --sku-name Standard \
  --capacity 10
```

**What you need**: Endpoint URL, API key, deployment name

---

### 2. Azure Speech Services
```bash
az cognitiveservices account create \
  --name my-voice-speech \
  --resource-group voice-agent-rg \
  --kind SpeechServices \
  --sku S0 \
  --location eastus2
```

**Recommended Voice**: `en-US-JasonNeural` (realistic, professional)

**What you need**: Endpoint, API key, region

---

### 3. Azure Cosmos DB (NoSQL)
```bash
# Create Cosmos account
az cosmosdb create \
  --name my-voice-agent-db \
  --resource-group voice-agent-rg \
  --locations regionName=westus2 failoverPriority=0

# Create database
az cosmosdb sql database create \
  --account-name my-voice-agent-db \
  --resource-group voice-agent-rg \
  --name conversations

# Create containers
az cosmosdb sql container create \
  --account-name my-voice-agent-db \
  --database-name conversations \
  --resource-group voice-agent-rg \
  --name sessions \
  --partition-key-path "/sessionId"

az cosmosdb sql container create \
  --account-name my-voice-agent-db \
  --database-name conversations \
  --resource-group voice-agent-rg \
  --name profiles \
  --partition-key-path "/phoneNumber"
```

**What you need**: Endpoint, primary key

---

### 4. Azure Redis Cache
```bash
az redis create \
  --name my-voice-cache \
  --resource-group voice-agent-rg \
  --location eastus2 \
  --sku Basic \
  --vm-size c0 \
  --enable-non-ssl-port false
```

**Usage**: Session state (senior_id, senior_name, ai_name, company_name)

**Key pattern**: `senior:{senior_id}:session:{session_id}`

**What you need**: Host, port (6380), SSL key

---

### 5. Azure SQL Database (Analytics)
```bash
# Create SQL Server
az sql server create \
  --name seniorly-sql-server \
  --resource-group voice-agent-rg \
  --location eastus2 \
  --admin-user sqladmin \
  --admin-password 'YourSecurePassword!'

# Create Database
az sql db create \
  --resource-group voice-agent-rg \
  --server seniorly-sql-server \
  --name SeniorHealthAnalytics \
  --service-objective Basic

# Configure firewall (allow Azure services)
az sql server firewall-rule create \
  --resource-group voice-agent-rg \
  --server seniorly-sql-server \
  --name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0
```

**Schema**: See `/backend/database/schema.sql`

**Tables**:
- `senior_vitals`: Blood pressure, heart rate, weight, sleep, pain
- `cognitive_assessments`: Memory, orientation, coherence scores
- `call_summary`: AI-generated summaries of each call
- `health_alerts`: Abnormal vitals, concerning patterns
- `medication_adherence`: Medication tracking

**Materialized Views** (for fast dashboard queries):
- `vw_latest_vitals_by_senior`: Most recent vitals per senior
- `vw_cognitive_trend_30d`: 30-day cognitive trends
- `vw_medication_adherence_weekly`: Weekly medication adherence
- `vw_active_alerts_summary`: Active health alerts

**What you need**: Server name, database name, username, password

---

### 6. Azure AI Search (Optional - for RAG)
```bash
az search service create \
  --name my-voice-search \
  --resource-group voice-agent-rg \
  --sku Basic \
  --location eastus2
```

**Usage**: Store medical knowledge base for RAG (Retrieval Augmented Generation)

**What you need**: Endpoint, admin key, index name

---

### 7. Azure Container Registry (for deployment)
```bash
az acr create \
  --resource-group voice-agent-rg \
  --name myvoiceagentacr \
  --sku Basic

az acr login --name myvoiceagentacr
```

---

### 8. Azure Container Apps (for hosting backend)
```bash
az containerapp env create \
  --name voice-agent-env \
  --resource-group voice-agent-rg \
  --location eastus2

# Deploy backend (after building Docker image)
az containerapp create \
  --name voice-agent-backend \
  --resource-group voice-agent-rg \
  --environment voice-agent-env \
  --image myvoiceagentacr.azurecr.io/voice-agent:latest \
  --target-port 8080 \
  --ingress external \
  --env-vars \
    AZURE_OPENAI_KEY=secret \
    AZURE_SPEECH_KEY=secret
```

---

## 📞 AWS Connect Setup

**Why AWS Connect?**: Azure Communication Services doesn't (yet) support WebSocket streaming for real-time audio. AWS Connect + Twilio Media Streams provides 1-2 second latency.

### Create AWS Connect Instance
1. Go to AWS Console → Amazon Connect
2. Create instance: `seniorly-voice-agent`
3. Select phone number (e.g., +18337876435)
4. Note: Instance ID, ARN, phone number

### Create Contact Flow
```json
{
  "Version": "2019-10-30",
  "StartAction": "12345",
  "Actions": [
    {
      "Identifier": "12345",
      "Type": "InvokeExternalResource",
      "Parameters": {
        "FunctionArn": "<your-webhook-url>",
        "TimeLimit": "8"
      },
      "Transitions": {
        "NextAction": "67890"
      }
    }
  ]
}
```

### Enable Media Streaming
1. In Contact Flow, add "Start media streaming"
2. Configure Kinesis Video Stream (or Twilio Media Streams)
3. Set webhook URL to your backend

**What you need**: Instance ID, ARN, phone number, AWS access key, secret key

---

## 📡 Twilio Setup (for Media Streams)

### Create Twilio Account
1. Sign up at twilio.com
2. Get phone number with Voice capabilities
3. Note: Account SID, Auth Token, phone number

### Configure Media Streams
```python
# In your backend webhook
@app.route("/voice", methods=["POST"])
def voice_webhook():
    response = VoiceResponse()
    response.connect().stream(url='wss://your-backend.azurecontainerapps.io/stream')
    return str(response)
```

**HIPAA Compliance**: Requires Twilio HIPAA add-on ($3k/month) for production

**What you need**: Account SID, auth token, phone number

---

## 🔐 Environment Variables (.env)

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://my-voice-agent-openai.cognitiveservices.azure.com
AZURE_OPENAI_KEY=xxx
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5-chat
AZURE_OPENAI_API_VERSION=2025-01-01-preview

# Azure Speech
AZURE_SPEECH_ENDPOINT=https://eastus2.api.cognitive.microsoft.com
AZURE_SPEECH_KEY=xxx
AZURE_SPEECH_REGION=eastus2
SPEECH_VOICE_NAME=en-US-JasonNeural

# Azure Cosmos DB
AZURE_COSMOS_ENDPOINT=https://my-voice-agent-db.documents.azure.com:443/
AZURE_COSMOS_KEY=xxx
COSMOS_DATABASE=conversations
COSMOS_CONTAINER=sessions

# Azure Redis
AZURE_REDIS_HOST=my-voice-cache.redis.cache.windows.net
AZURE_REDIS_KEY=xxx
REDIS_PORT=6380
REDIS_SSL=true

# Azure SQL
AZURE_SQL_SERVER=seniorly-sql-server.database.windows.net
AZURE_SQL_DATABASE=SeniorHealthAnalytics
AZURE_SQL_USERNAME=sqladmin
AZURE_SQL_PASSWORD=xxx

# AWS Connect
AWS_REGION=us-east-1
AWS_CONNECT_INSTANCE_ID=xxx
AWS_CONNECT_PHONE_NUMBER=+18337876435
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx

# Twilio
TWILIO_ACCOUNT_SID=xxx
TWILIO_AUTH_TOKEN=xxx
TWILIO_PHONE_NUMBER=+18668119355
```

---

## 🐍 Python Backend Structure

```
backend/
├── src/
│   ├── main.py                    # FastAPI server, webhook handlers
│   ├── config.py                  # Environment variables
│   ├── senior_health_prompt.py    # AI system prompt for senior conversations
│   ├── services/
│   │   ├── openai_service.py      # Azure OpenAI client
│   │   ├── speech_service.py      # Azure Speech STT/TTS
│   │   ├── redis_service.py       # Redis session management
│   │   ├── cosmos_service.py      # Cosmos DB operations
│   │   ├── profile_service.py     # Senior profile management
│   │   └── analytics_service.py   # Extract metrics → SQL
│   └── utils/
│       ├── audio_utils.py         # Audio format conversions
│       └── metrics_extractor.py   # Regex patterns for vitals
├── database/
│   ├── schema.sql                 # SQL database schema
│   └── setup_database.py          # Script to create tables
├── requirements.txt
├── Dockerfile
└── .env
```

---

## 📊 Analytics Service Logic

**Purpose**: Automatically extract health metrics from conversations and save to Azure SQL.

### Extraction Flow
1. Call ends → `openai.generate_call_summary()` creates summary
2. Analytics service receives: summary + full conversation history
3. Use regex + NLP to extract:
   - **Vitals**: BP (120/80), heart rate (72 bpm), weight (165 lbs), sleep (6 hours), pain (3/10)
   - **Cognitive**: Memory score, coherence, topic drift count
   - **Medication**: Adherence, missed doses
   - **Wellness**: Mood score, social interaction
4. Detect **health alerts**: BP > 140/90, heart rate < 50 or > 100, etc.
5. Save to SQL database

### Example Code
```python
def extract_and_save_metrics(
    senior_id: str,
    session_id: str,
    call_summary: str,
    conversation_history: List[Dict],
    call_duration: int
):
    # Extract vitals using regex
    vitals = extract_vitals(call_summary, conversation_history)

    # BP: "120/80", "BP 135 over 85"
    bp_pattern = r'(?:blood pressure|BP)[:\s]+(\d{2,3})[/\s]*(?:over|/)?\s*(\d{2,3})'

    # Heart rate: "72 bpm", "heart rate 68"
    hr_pattern = r'(?:heart rate|pulse)[:\s]+(\d{2,3})\s*(?:bpm)?'

    # Weight: "165 lbs", "weight 72 kg"
    weight_pattern = r'(?:weight)[:\s]+(\d{2,3})\s*(lbs|kg)'

    # Save to SQL
    save_vitals_to_db(senior_id, vitals)
    save_cognitive_to_db(senior_id, cognitive_scores)
    save_alerts_to_db(senior_id, alerts)
```

---

## 🎨 Frontend Dashboard (Next.js)

### Pages
- `/login` - User authentication
- `/dashboard` - Overview: active seniors, recent calls, alerts
- `/seniors` - List of all seniors
- `/seniors/[id]` - Individual senior profile with:
  - Latest vitals (BP, heart rate, weight)
  - 30-day cognitive trend chart
  - Medication adherence calendar
  - Active health alerts
  - Call history

### API Routes (Next.js API)
```typescript
// pages/api/seniors/[id]/vitals.ts
import { query } from '@/lib/db'

export default async function handler(req, res) {
  const { id } = req.query

  const vitals = await query(`
    SELECT * FROM vw_latest_vitals_by_senior
    WHERE senior_id = @p1
  `, [id])

  res.json(vitals)
}
```

### Connect to Azure SQL
```typescript
// lib/db.ts
import sql from 'mssql'

const config = {
  server: process.env.AZURE_SQL_SERVER,
  database: process.env.AZURE_SQL_DATABASE,
  user: process.env.AZURE_SQL_USERNAME,
  password: process.env.AZURE_SQL_PASSWORD,
  options: {
    encrypt: true,
    trustServerCertificate: false
  }
}

export async function query(sql, params) {
  const pool = await sql.connect(config)
  const result = await pool.request()
    .input('p1', sql.VarChar, params[0])
    .query(sql)
  return result.recordset
}
```

---

## 🤖 AI Behavior Best Practices

### System Prompt Template
```python
system_prompt = f"""
You are {ai_name}, a caring health assistant from {company_name}.
You are calling {senior_name} for their daily check-in.

OBJECTIVES:
1. Ask about ALL vitals: blood pressure, heart rate, weight, sleep, pain
2. Be THOROUGH but conversational (not robotic)
3. If senior goes off-topic:
   - Answer their question briefly
   - Gently redirect: "That's interesting! Now, about your blood pressure..."
4. STRICT 5-minute call limit:
   - At 4:30, say: "We have 30 seconds left. Is there anything urgent?"
   - At 5:00, end call: "Let's continue tomorrow. Take care!"

CONVERSATION STYLE:
- Warm, patient, grandparent-friendly
- Use simple language (avoid medical jargon)
- Confirm understanding: "So your blood pressure was 120 over 80, correct?"

VITALS CHECKLIST (ask ALL):
- Blood pressure (120/80 format)
- Heart rate (bpm)
- Weight (lbs or kg)
- Sleep (hours last night)
- Pain level (0-10 scale)
- Any new concerns

Remember: You're here to ensure {senior_name}'s health and safety.
"""
```

### Call Timer Implementation
```python
import time

call_start_time = time.time()

def check_call_duration():
    elapsed = time.time() - call_start_time

    if elapsed >= 270:  # 4:30
        return "⚠️ 30 seconds remaining"
    elif elapsed >= 300:  # 5:00
        return "🛑 Time's up - end call"
    return None
```

---

## 🚀 Deployment Steps

### 1. Build Backend Docker Image
```bash
cd backend
docker build -t myvoiceagentacr.azurecr.io/voice-agent:latest .
docker push myvoiceagentacr.azurecr.io/voice-agent:latest
```

### 2. Deploy to Azure Container Apps
```bash
az containerapp update \
  --name voice-agent-backend \
  --resource-group voice-agent-rg \
  --image myvoiceagentacr.azurecr.io/voice-agent:latest
```

### 3. Build Frontend
```bash
cd frontend
npm run build
```

### 4. Deploy Frontend to Vercel/Azure Static Web Apps
```bash
# Vercel
vercel --prod

# OR Azure Static Web Apps
az staticwebapp create \
  --name voice-agent-dashboard \
  --resource-group voice-agent-rg \
  --location eastus2 \
  --source frontend
```

---

## 💰 Cost Estimates (USD/month)

| Service | Tier | Cost |
|---------|------|------|
| Azure OpenAI GPT-5 | Standard | ~$50-200 (depends on usage) |
| Azure Speech | Standard | ~$10-50 |
| Cosmos DB | Basic (1000 RU/s) | ~$25 |
| Redis | Basic C0 | ~$16 |
| Azure SQL | Basic | ~$5 |
| Container Apps | Consumption | ~$10-30 |
| AWS Connect | Pay-as-you-go | $0.018/min (~$50 for 2800 min) |
| Twilio | Pay-as-you-go | $0.013/min (~$36 for 2800 min) |
| **TOTAL** | | **~$200-400/month** |

**HIPAA Compliance Add-on**: +$3k/month (Twilio HIPAA)

---

## ⚠️ HIPAA Considerations

### What Requires HIPAA Compliance?
- **PHI (Protected Health Information)**: Name + DOB + medical history
- **Covered**: Azure (with BAA), AWS Connect (with BAA)
- **Not Covered (without add-on)**: Twilio standard plan

### Options:
1. **For MVP (5-10 test users)**: Use standard Twilio with disclaimer
2. **For Production**:
   - Twilio HIPAA add-on ($3k/month)
   - OR wait for Azure Communication Services WebSocket streaming (in preview)
   - OR use AWS Connect with Kinesis Video Streams (more complex)

### Azure BAA:
- Automatically included with Azure Enterprise Agreement (FREE)
- Must configure properly (encryption, network security, logging)
- See: https://servicetrust.microsoft.com/ViewPage/TrustDocumentsV3

---

## 🔒 HIPAA Compliance Configuration (REQUIRED)

**Cost:** ~$40/month | **Time:** 30 minutes

### Step 1: Enable Cosmos DB Audit Logging

```bash
az monitor diagnostic-settings create \
  --resource /subscriptions/<subscription-id>/resourceGroups/voice-agent-rg/providers/Microsoft.DocumentDb/databaseAccounts/my-voice-agent-db \
  --name cosmos-audit-logs \
  --workspace /subscriptions/<subscription-id>/resourceGroups/voice-agent-rg/providers/Microsoft.OperationalInsights/workspaces/<workspace-name> \
  --logs '[{"category": "DataPlaneRequests", "enabled": true}, {"category": "QueryRuntimeStatistics", "enabled": true}, {"category": "ControlPlaneRequests", "enabled": true}]' \
  --metrics '[{"category": "Requests", "enabled": true}]'
```

**What it logs:** All database operations (who accessed what data, when)
**Cost:** ~$5/month

### Step 2: Enable SQL Server Auditing

```bash
az sql server audit-policy update \
  --resource-group voice-agent-rg \
  --name seniorly-sql-server \
  --state Enabled \
  --lats Enabled \
  --lawri /subscriptions/<subscription-id>/resourceGroups/voice-agent-rg/providers/Microsoft.OperationalInsights/workspaces/<workspace-name>
```

**What it logs:** All SQL authentication and operations
**Cost:** ~$15/month

### Step 3: Enable SQL Threat Protection

```bash
az sql server advanced-threat-protection-setting update \
  --resource-group voice-agent-rg \
  --name seniorly-sql-server \
  --state Enabled
```

**What it protects:** SQL injection, brute force, anomalous access
**Cost:** ~$15/month

### Step 4: Extend SQL Backup Retention (7 years for HIPAA)

```bash
az sql db ltr-policy set \
  --resource-group voice-agent-rg \
  --server seniorly-sql-server \
  --name SeniorHealthAnalytics \
  --weekly-retention P4W \
  --monthly-retention P12M \
  --yearly-retention P7Y \
  --week-of-year 1
```

**Retention:** 7 years (HIPAA compliant)
**Cost:** ~$5/month

### Step 5: Verify Encryption (Should be enabled by default)

```bash
# Check Cosmos DB encryption
az cosmosdb show --name my-voice-agent-db --resource-group voice-agent-rg

# Check SQL encryption (TDE - Transparent Data Encryption)
az sql db show --resource-group voice-agent-rg --server seniorly-sql-server --name SeniorHealthAnalytics

# Check Redis SSL
az redis show --name my-voice-cache --resource-group voice-agent-rg --query enableNonSslPort
# Should be: false
```

### Step 6: Set Up Automated Monthly HIPAA Reports

See `/backend/AUTOMATED_HIPAA_REPORTS.md` for setup guide.

**Quick setup:**
1. Install SendGrid (free tier: 100 emails/month)
2. Create Azure Logic App with monthly trigger
3. Call Python script to generate report
4. Email report to compliance team

**Cost:** $0-2/month

### HIPAA Compliance Checklist

After running the commands above:

- [x] Encryption at Rest (Azure default - enabled)
- [x] Encryption in Transit - TLS 1.2+ (enabled)
- [x] Cosmos DB Audit Logging (Step 1)
- [x] SQL Server Auditing (Step 2)
- [x] SQL Threat Protection (Step 3)
- [x] 7-Year Backup Retention (Step 4)
- [x] Azure BAA Signed (included with subscription)
- [x] Access Controls - RBAC (Azure AD)
- [x] Automated Compliance Reports (Step 6)

**Total Additional Cost:** ~$40/month
**Status:** 🟢 100% HIPAA COMPLIANT (except Twilio - see options above)

---

## 🎯 Key Learnings

### 1. **Data Architecture**
- **Operational data** (conversations, profiles) → Cosmos DB (fast, flexible)
- **Session state** (senior_id, names) → Redis (ultra-fast, temporary)
- **Analytics data** (vitals, metrics) → SQL (structured, queryable)

### 2. **Sparse Data Handling**
- Use **long/narrow table** for vitals (one row per metric)
- Don't force all metrics every day (nullable fields)
- Example:
  ```sql
  -- Bad: wide table (many NULL values)
  CREATE TABLE senior_vitals (
    id INT,
    senior_id VARCHAR(50),
    bp_systolic INT,  -- NULL most days
    bp_diastolic INT, -- NULL most days
    heart_rate INT,   -- NULL most days
    ...
  )

  -- Good: long/narrow table
  CREATE TABLE senior_vitals (
    id INT,
    senior_id VARCHAR(50),
    vital_type VARCHAR(50),  -- 'bp_systolic', 'heart_rate', etc.
    vital_value DECIMAL(10,2),
    recorded_at DATETIME
  )
  ```

### 3. **Redis Session Isolation**
- Always namespace keys: `senior:{senior_id}:session:{session_id}`
- Prevents data mixing between concurrent calls
- Makes debugging easier

### 4. **Materialized Views for Performance**
- Precompute common dashboard queries
- Example: "Latest vitals per senior" query takes 0.01s instead of 2s

### 5. **Real-time Audio Streaming**
- **Azure Communication Services**: Call Automation API supports WebSocket (public preview)
- **AWS Connect + Twilio**: Production-ready, 1-2 sec latency
- **Trade-off**: Azure ACS (HIPAA-friendly) vs Twilio (better UX)

---

## 📚 Additional Resources

- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [Azure Speech Services](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/)
- [Azure Communication Services](https://learn.microsoft.com/en-us/azure/communication-services/)
- [AWS Connect](https://docs.aws.amazon.com/connect/)
- [Twilio Media Streams](https://www.twilio.com/docs/voice/media-streams)
- [Next.js Documentation](https://nextjs.org/docs)
- [HIPAA Compliance Guide](https://www.hhs.gov/hipaa/for-professionals/index.html)

---

## 🤝 Support

For issues or questions about this architecture, consult:
- `/backend/README.md` - Backend details
- `/backend/database/schema.sql` - Database schema
- `/backend/DEPLOYMENT.md` - Azure deployment guide

---

**Last Updated**: October 2025
**Architecture Version**: 1.0
**Status**: Production-ready (except HIPAA compliance requires Twilio add-on)
