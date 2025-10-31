# Voice Agent Architecture & Setup Guide

Complete guide to replicate this Azure-based voice agent architecture for senior health monitoring.

---

## 🎯 System Overview

**Purpose**: AI voice agent that calls seniors daily, collects health metrics, and provides real-time analytics dashboard.

**Tech Stack**:
- **AI**: Azure OpenAI GPT-5
- **Speech**: Azure Speech Services (TTS/STT)
- **Telephony**: Twilio (outbound calling + Media Streams)
- **Data**: Azure Cosmos DB, Redis, PostgreSQL
- **Backend**: Python (FastAPI)
- **Frontend**: Next.js + Tailwind CSS
- **Deployment**: Azure Container Apps

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────┐
│ Call Initiation                          │
│ POST /initiate-call                      │
│  ├─ Pre-load context (15-30s)            │
│  ├─ Cache senior profile & history       │
│  └─ Place Twilio outbound call           │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Twilio Media Streams (WebSocket)         │
│ Real-time bidirectional audio streaming  │
│ wss://.../media-stream                   │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Python Backend (Azure Container Apps)    │
│  ├─ Min Replicas: 1 (no cold starts)     │
│  ├─ Adaptive VAD (learns ambient noise)  │
│  ├─ Azure Speech: STT (speech → text)    │
│  ├─ Azure OpenAI GPT-5: AI responses     │
│  ├─ TTS Normalization (natural tone)     │
│  ├─ Azure Speech: TTS (text → speech)    │
│  └─ Analytics Service: Extract metrics   │
└──────┬───────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Data Layer                               │
│  ├─ Cosmos DB: Conversations, profiles   │
│  ├─ Redis: Session state, caching        │
│  └─ PostgreSQL: Analytics, vitals        │
└──────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│ Next.js Dashboard                        │
│  └─ Real-time health metrics & alerts    │
└──────────────────────────────────────────┘
```

**Key Features:**
- ✅ **Pre-loaded Context**: Load senior history BEFORE calling (eliminates 30s delay)
- ✅ **Azure Speech Streaming STT (Local Parity)**: Feeds Twilio audio to Azure Speech; Azure’s VAD handles turn‑taking and noise isolation
- ✅ **Natural TTS**: Normalizes overly enthusiastic AI responses for calm speech
- ✅ **No Cold Starts**: Min replicas = 1, always warm
- ✅ **Optional Custom VAD**: WebRTC VAD with tunable thresholds (enable only if needed)

---

## 📁 Complete Project Structure

**Root directory:** `callback-voice-agent/`

```
callback-voice-agent/
├── backend/                     # Python voice agent backend
│   ├── src/                     # Application source code
│   ├── services/                # Business logic services (17 services)
│   ├── database/                # PostgreSQL schemas
│   ├── scripts/                 # Utility scripts
│   ├── requirements.txt         # Python dependencies
│   ├── Dockerfile               # Container definition
│   ├── .env                     # Environment variables (local)
│   └── .azure_endpoint          # Deployed Azure URL
│
├── frontend/                    # Next.js dashboard (optional)
│   ├── src/
│   │   ├── app/                 # Next.js 13+ App Router pages
│   │   ├── components/          # React components
│   │   ├── lib/                 # Database & utilities
│   │   └── types/               # TypeScript type definitions
│   ├── package.json
│   └── .env.local
│
├── AGENTSETUP.md               # This file - complete setup guide
└── README.md                   # Project overview

```

**When creating a new voice agent:**
1. Create `backend/` folder with the structure shown in "Python Backend Structure" section
2. Optionally create `frontend/` folder with the structure shown in "Frontend Dashboard" section
3. Copy environment variables from this guide to `backend/.env`
4. Install dependencies: `cd backend && pip install -r requirements.txt`
5. Run setup scripts: `python database/setup_database_postgres.py`
6. Deploy: `az containerapp up` (see deployment section)

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

**Recommended Voice**: `en-US-SaraNeural` (warm, empathetic, female voice for senior health check-ins)

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

### 5. Azure PostgreSQL Database (Analytics)
```bash
# Register PostgreSQL provider (one-time)
az provider register --namespace Microsoft.DBforPostgreSQL

# Create PostgreSQL Flexible Server
az postgres flexible-server create \
  --resource-group voice-agent-rg \
  --name seniorly-postgres-server \
  --location centralus \
  --admin-user pgadmin \
  --admin-password 'YOUR_64_CHAR_SECURE_PASSWORD' \
  --sku-name Standard_B2s \
  --tier Burstable \
  --storage-size 32 \
  --version 16 \
  --public-access 0.0.0.0-255.255.255.255 \
  --yes

# Create database
az postgres flexible-server db create \
  --resource-group voice-agent-rg \
  --server-name seniorly-postgres-server \
  --database-name SeniorHealthAnalytics

# Run the auto-firewall update script (updates your IP automatically)
./backend/scripts/update_postgres_firewall.sh

# Optional: Set up cron job to run firewall script daily
# (crontab -e) Add: 0 9 * * * /path/to/update_postgres_firewall.sh
```

**Schema**: See `/backend/database/schema_postgres.sql`

**Setup**: Run `python backend/database/setup_database_postgres.py` to create tables

**Tables**:
- `senior_vitals`: Blood pressure, heart rate, weight, sleep, pain
- `cognitive_assessments`: Memory, orientation, coherence scores (includes 4-dimension cognitive testing)
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

### Container Apps Deployment Notes

- Enable external ingress on port 5000 and set `--min-replicas 1` to avoid cold starts.
- Build AMD64 images for Azure (`docker buildx build --platform linux/amd64 …`).
- Keep the app warm by pinging `/health` every 1–5 minutes (optional).
- The launcher `run_app.sh` auto-prepends `https://` to `.azure_endpoint` if it contains only the FQDN.

### VAD Tuning Notes
- Local‑mode parity (recommended): set `VAD_USE_WEBRTC=false` to rely fully on Azure Speech VAD.
- If the agent struggles to hear with custom VAD: try `VAD_AGGRESSIVENESS=1` or lower `VAD_ON_MIN_VOICED` to 7.
- If it hears background/TV with custom VAD: try `VAD_AGGRESSIVENESS=3` or raise `VAD_ON_MIN_VOICED` to 9.
- Prompt timing: adjust `VAD_PROMPT_GRACE_SECONDS` (after TTS) and `VAD_SILENCE_CHUNKS_TO_PROMPT` (silence before prompt).

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

# WebRTC Voice Activity Detection (VAD) and Latency (recommended defaults)
VAD_USE_WEBRTC=true
VAD_AGGRESSIVENESS=2
VAD_ON_WINDOW_FRAMES=10
VAD_ON_MIN_VOICED=8
VAD_OFF_CONSEC_UNVOICED=15
VAD_CHUNK_BYTES=4000
VAD_COOLDOWN_MS=600
VAD_PROMPT_GRACE_SECONDS=5
VAD_SILENCE_CHUNKS_TO_PROMPT=10
VAD_MIN_THRESHOLD=0.006
VAD_AMBIENT_MULTIPLIER=1.5
VAD_AMBIENT_LEARNING_CHUNKS=2
VAD_DEBUG=true
```

---

## 🐍 Python Backend Structure

**Location:** `callback-voice-agent/backend/`

```
backend/
├── src/
│   ├── main.py                           # FastAPI server, Twilio webhook handlers
│   ├── config.py                         # Load environment variables from .env
│   ├── senior_health_prompt.py           # AI system prompt (personality, instructions)
│   │
│   ├── services/
│   │   ├── openai_service.py             # Azure OpenAI GPT-5 client
│   │   ├── speech_service.py             # Azure Speech STT/TTS
│   │   ├── twilio_service.py             # Twilio call initiation
│   │   ├── data_service.py               # Combined data layer (Cosmos + Redis + Search)
│   │   ├── cosmos_service.py             # Cosmos DB: conversations, profiles
│   │   ├── redis_service.py              # Redis: session state, caching
│   │   ├── profile_service.py            # Senior profile CRUD operations
│   │   ├── identity_verification_service.py  # Name + DOB verification
│   │   ├── conversation_context_service.py   # Build dynamic context from history
│   │   ├── safety_service.py             # Detect concerning patterns (health alerts)
│   │   ├── cost_tracking_service.py      # Track API usage costs
│   │   ├── analytics_sync_service.py     # Extract metrics → PostgreSQL (real-time)
│   │   ├── reminders_service.py          # Manage appointments/reminders
│   │   ├── call_flow_service.py          # Structured call todos (NEW)
│   │   ├── research_service.py           # Find doctors/resources (NEW)
│   │   ├── email_service.py              # Send emails via Azure Communication (NEW)
│   │   └── async_tasks_service.py        # Background task queue (NEW)
│   │
│   └── utils/
│       ├── audio_utils.py                # Audio format conversions (mulaw, PCM)
│       └── cognitive_tests.py            # Cognitive assessment patterns
│
├── database/
│   ├── schema_postgres.sql               # PostgreSQL analytics schema
│   ├── add_reminders_table.sql           # Reminders table
│   ├── add_activity_falls_conditions_tables.sql  # Activity/falls/conditions
│   └── setup_database_postgres.py        # Create all tables
│
├── scripts/
│   ├── migrate_cosmos_to_postgres.py     # One-time data migration
│   ├── query_sql_database.py             # Query PostgreSQL analytics
│   └── update_postgres_firewall.sh       # Auto-update firewall IP (cron job)
│
├── twilio_websocket_server.py            # WebSocket server for Twilio Media Streams
├── run_app.sh                             # Testing launcher (local/Twilio/ngrok)
├── requirements.txt                       # Python dependencies
├── Dockerfile                             # Container image definition
├── .env                                   # Environment variables (DO NOT COMMIT)
├── .azure_endpoint                        # Deployed Azure URL
└── venv/                                  # Virtual environment (local only)
```

### Key Files Explained:

**`src/main.py`**:
- FastAPI server with `/voice` webhook endpoint
- Handles Twilio call initiation and WebSocket connections
- Orchestrates all services (OpenAI, Speech, Database)

**`src/senior_health_prompt.py`**:
- Complete AI personality and instructions
- Conversation flow guidance (reminders, research, health checks)
- Safety guardrails and exit handling

**`src/services/`**:
- Each service encapsulates one responsibility
- `data_service.py` is the main entry point (combines Cosmos + Redis + Search)
- `analytics_sync_service.py` runs after each call to extract health metrics

**`database/`**:
- SQL files define PostgreSQL schema
- `setup_database_postgres.py` creates tables automatically

**`scripts/`**:
- Utility scripts for database management
- `update_postgres_firewall.sh` runs via cron every 4 hours

**`twilio_websocket_server.py`**:
- Standalone WebSocket server for bidirectional audio streaming
- Handles mulaw audio encoding/decoding

---

## 📦 Python Dependencies (requirements.txt)

```txt
# Azure SDK packages
azure-cognitiveservices-speech==1.46.0
openai==2.6.1
azure-cosmos==4.14.0
azure-search-documents==11.6.0
redis==7.0.1
azure-keyvault-secrets==4.9.0
azure-identity==1.20.0

# Web framework for webhooks
fastapi==0.115.6
uvicorn[standard]==0.34.0

# Telephony
twilio==9.8.5

# Utilities
python-dotenv==1.2.1
pydantic==2.12.3
pydantic-settings==2.7.0
psycopg2-binary==2.9.10
dateparser==1.2.0

# AWS SDK (for Kinesis Video Streams with Connect integration)
boto3==1.35.0

# Audio processing
av==16.0.1
soundfile==0.13.1
numpy==2.3.4
```

**Key Dependencies:**
- **azure-cognitiveservices-speech**: Azure Speech STT/TTS
- **openai**: Azure OpenAI GPT-5 client
- **azure-cosmos**: Cosmos DB NoSQL storage
- **redis**: Session state management
- **psycopg2-binary**: PostgreSQL database client (analytics)
- **twilio**: Telephony and Media Streams
- **fastapi + uvicorn**: Web server for webhooks
- **dateparser**: Parse appointment dates from natural language

**Installation:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
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

**Location:** `callback-voice-agent/frontend/` (if exists)

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx                    # Root layout
│   │   ├── page.tsx                      # Home page (redirect to dashboard)
│   │   ├── login/
│   │   │   └── page.tsx                  # Authentication page
│   │   ├── dashboard/
│   │   │   └── page.tsx                  # Main dashboard overview
│   │   ├── seniors/
│   │   │   ├── page.tsx                  # List all seniors
│   │   │   └── [id]/
│   │   │       ├── page.tsx              # Senior profile detail
│   │   │       ├── vitals/page.tsx       # Vitals history
│   │   │       ├── cognitive/page.tsx    # Cognitive trends
│   │   │       └── calls/page.tsx        # Call history
│   │   └── api/
│   │       ├── seniors/
│   │       │   ├── route.ts              # GET /api/seniors (list)
│   │       │   └── [id]/
│   │       │       ├── route.ts          # GET /api/seniors/:id
│   │       │       ├── vitals/route.ts   # GET vitals for senior
│   │       │       └── cognitive/route.ts # GET cognitive scores
│   │       └── auth/
│   │           └── [...nextauth]/route.ts # NextAuth.js endpoints
│   │
│   ├── components/
│   │   ├── ui/                           # Shadcn UI components
│   │   │   ├── button.tsx
│   │   │   ├── card.tsx
│   │   │   ├── chart.tsx
│   │   │   └── table.tsx
│   │   ├── SeniorCard.tsx                # Senior overview card
│   │   ├── VitalsChart.tsx               # Line chart for vitals
│   │   ├── CognitiveScoreCard.tsx        # Cognitive score display
│   │   ├── AlertBanner.tsx               # Health alert notifications
│   │   └── CallHistoryTable.tsx          # Table of past calls
│   │
│   ├── lib/
│   │   ├── db.ts                         # PostgreSQL connection
│   │   ├── auth.ts                       # NextAuth configuration
│   │   └── utils.ts                      # Utility functions
│   │
│   └── types/
│       ├── senior.ts                     # Senior profile types
│       ├── vitals.ts                     # Vitals data types
│       └── api.ts                        # API response types
│
├── public/
│   ├── logo.svg
│   └── favicon.ico
│
├── .env.local                            # Environment variables (DO NOT COMMIT)
├── next.config.js                        # Next.js configuration
├── tailwind.config.ts                    # Tailwind CSS config
├── tsconfig.json                         # TypeScript config
└── package.json                          # Dependencies
```

### Key Pages

**`/dashboard`** - Overview page showing:
- Total active seniors
- Recent calls (last 24 hours)
- Active health alerts (high BP, missed medications)
- Upcoming appointments/reminders

**`/seniors`** - List all seniors with search/filter:
- Name, age, last call date
- Latest vital signs
- Active alerts badge
- Quick actions (call now, view profile)

**`/seniors/[id]`** - Individual senior profile:
- Latest vitals (BP, heart rate, weight, sleep)
- 30-day cognitive trend chart
- Medication adherence calendar
- Active health alerts
- Call history with summaries

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

## 🌐 API Endpoints

**Base URL**: `https://voice-agent-backend.grayriver-5405228a.eastus2.azurecontainerapps.io`

### Health Check
```bash
GET /health
```
Returns service status and readiness of all components (Speech, OpenAI, Data, Agent).

### Initiate Call (Pre-loaded Context)
```bash
POST /initiate-call
Content-Type: application/json

{
  "phone_number": "289-324-2125"
}
```

**Flow:**
1. Loads senior profile and call history from Cosmos DB (15-30 seconds)
2. Caches context in memory (preloaded_context dictionary)
3. Places Twilio outbound call
4. When senior answers, greeting plays immediately (no delay!)

**Response:**
```json
{
  "success": true,
  "call_sid": "CAxxxx...",
  "message": "Call initiated successfully (context pre-loaded)"
}
```

### Voice Webhook (Twilio)
```bash
POST /voice
```
Handles incoming Twilio call events and returns TwiML to start Media Stream WebSocket.

### Media Stream (WebSocket)
```bash
WSS /media-stream
```
Real-time bidirectional audio streaming with Twilio. Handles:
- Audio chunk reception (mulaw PCM, 8kHz)
- Adaptive VAD (learns ambient noise in first 6 seconds)
- STT → GPT-5 → TTS pipeline
- TTS text normalization (removes CAPS, multiple !!!)

---

## 🚀 Deployment Steps

### Quick Deploy Script
```bash
cd backend
./deploy_to_azure.sh
```

This script handles:
- Building Docker image for linux/amd64
- Pushing to Azure Container Registry
- Updating Container App with new image
- Setting min replicas = 1 (no cold starts)

### Manual Deployment

#### 1. Build Backend Docker Image (linux/amd64)
```bash
cd backend
docker buildx build --platform linux/amd64 --load \
  -t myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:latest .
```

#### 2. Push to Azure Container Registry
```bash
az acr login --name myvoiceagentacr
docker push myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:latest
```

#### 3. Deploy to Azure Container Apps
```bash
az containerapp update \
  --name voice-agent-backend \
  --resource-group voice-agent-rg \
  --image myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:latest \
  --min-replicas 1 \
  --max-replicas 3
```

**Important**: Always set `--min-replicas 1` to avoid cold starts!

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
| Azure PostgreSQL | Flexible Server | ~$15 |
| Container Apps | Consumption | ~$10-30 |
| Twilio (Telephony) | Pay-as-you-go | $0.013/min (~$36 for 2800 min) |
| **TOTAL** | | **~$160-370/month** |

**HIPAA Compliance Add-on**: +$3k/month (Twilio HIPAA)

---

## ⚠️ HIPAA Considerations

### What Requires HIPAA Compliance?
- **PHI (Protected Health Information)**: Name + DOB + medical history
- **Covered**: Azure services (with BAA), Twilio (with HIPAA add-on)
- **Not Covered (without add-on)**: Twilio standard plan

### Current Setup:
- **Telephony**: Twilio Media Streams (currently using standard plan)
- **All Processing**: Azure (HIPAA-compliant with BAA)
- **Storage**: Azure Cosmos DB + PostgreSQL (HIPAA-compliant)

### Options:
1. **For MVP (5-10 test users)**: Use standard Twilio with disclaimer
2. **For Production**:
   - Twilio HIPAA add-on ($3k/month)
   - OR wait for Azure Communication Services WebSocket streaming (in preview)

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

---

## 📋 Testing Checklist

Before deploying to production, verify:

### 1. Local Testing
```bash
cd backend
source venv/bin/activate
./run_app.sh local
```
- [ ] WebSocket server starts successfully
- [ ] Environment variables loaded correctly
- [ ] All services initialize (OpenAI, Speech, Redis, Cosmos, PostgreSQL)

### 2. Database Connectivity
```bash
# Test PostgreSQL connection
./venv/bin/python backend/scripts/query_sql_database.py

# Test Redis connection
redis-cli -h <your-redis-host> -p 6380 --tls -a <your-key> PING

# Test Cosmos DB connection
az cosmosdb show --name my-voice-agent-db --resource-group voice-agent-rg
```
- [ ] PostgreSQL tables created
- [ ] Redis connection successful
- [ ] Cosmos DB containers exist

### 3. Twilio Integration Testing
```bash
# Start server with ngrok
./run_app.sh ngrok

# Configure Twilio webhook to ngrok URL
# Make test call
python -c "from src.services.twilio_service import TwilioService; TwilioService().initiate_call('+1234567890')"
```
- [ ] ngrok tunnel established
- [ ] Twilio webhook receives requests
- [ ] Audio streams bidirectionally
- [ ] Speech recognition works
- [ ] AI responses generated
- [ ] TTS audio plays correctly

### 4. Azure Deployment Testing
```bash
# Deploy to Azure Container Apps
cd backend
docker build -t myvoiceagentacr.azurecr.io/voice-agent:latest .
docker push myvoiceagentacr.azurecr.io/voice-agent:latest
az containerapp update --name voice-agent-backend --resource-group voice-agent-rg --image myvoiceagentacr.azurecr.io/voice-agent:latest

# Update Twilio webhook to Azure URL
# Make test call
```
- [ ] Container builds successfully
- [ ] Container pushes to ACR
- [ ] Container Apps deployment succeeds
- [ ] Public URL accessible
- [ ] Twilio webhook configured with production URL
- [ ] End-to-end call completes successfully

### 5. Data Verification
```bash
# After test call, verify data saved
./venv/bin/python backend/scripts/query_sql_database.py
```
- [ ] Conversation saved to Cosmos DB
- [ ] Session state cleared from Redis
- [ ] Vitals extracted to PostgreSQL
- [ ] Call summary generated
- [ ] Health alerts created (if applicable)
- [ ] Reminders loaded and mentioned
- [ ] Cognitive scores calculated

### 6. Frontend Dashboard (if deployed)
- [ ] Dashboard loads successfully
- [ ] Senior profiles displayed
- [ ] Vitals charts render correctly
- [ ] Cognitive trends visible
- [ ] Health alerts shown
- [ ] Call history populated

---

## 🔄 Continuous Monitoring

### Set Up Automated Firewall Updates
```bash
# Add to crontab (runs every 4 hours)
crontab -e

# Add this line:
0 */4 * * * /Users/satssehgal/Documents/Code/callback-voice-agent/backend/scripts/update_postgres_firewall.sh
```

### Set Up Health Monitoring
```bash
# Azure Monitor alerts for:
# - Container Apps crashes
# - OpenAI API errors
# - Speech Service failures
# - Database connection issues

az monitor metrics alert create \
  --name container-app-errors \
  --resource-group voice-agent-rg \
  --scopes /subscriptions/<subscription-id>/resourceGroups/voice-agent-rg/providers/Microsoft.App/containerApps/voice-agent-backend \
  --condition "count Errors > 10" \
  --window-size 5m \
  --evaluation-frequency 1m
```

---

## 📖 Quick Reference

### Common Commands

**Start local server:**
```bash
cd backend
source venv/bin/activate
./run_app.sh local
```

**Start with ngrok (for Twilio testing):**
```bash
./run_app.sh ngrok
```

**Query database:**
```bash
./venv/bin/python backend/scripts/query_sql_database.py
```

**Deploy to Azure:**
```bash
cd backend
docker build -t myvoiceagentacr.azurecr.io/voice-agent:latest .
docker push myvoiceagentacr.azurecr.io/voice-agent:latest
az containerapp update --name voice-agent-backend --resource-group voice-agent-rg --image myvoiceagentacr.azurecr.io/voice-agent:latest
```

**Update PostgreSQL firewall:**
```bash
./backend/scripts/update_postgres_firewall.sh
```

### Useful Azure CLI Commands

**Get Container App logs:**
```bash
az containerapp logs show \
  --name voice-agent-backend \
  --resource-group voice-agent-rg \
  --follow
```

**Get Container App URL:**
```bash
az containerapp show \
  --name voice-agent-backend \
  --resource-group voice-agent-rg \
  --query properties.configuration.ingress.fqdn
```

**Restart Container App:**
```bash
az containerapp revision restart \
  --name voice-agent-backend \
  --resource-group voice-agent-rg
```

### Environment Variables Reference

**Required Variables:**
- `AZURE_OPENAI_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT_NAME`
- `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`
- `AZURE_COSMOS_KEY`, `AZURE_COSMOS_ENDPOINT`
- `AZURE_REDIS_HOST`, `AZURE_REDIS_KEY`
- `AZURE_POSTGRES_SERVER`, `AZURE_POSTGRES_DATABASE`, `AZURE_POSTGRES_USERNAME`, `AZURE_POSTGRES_PASSWORD`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`

**Optional Variables:**
- `SPEECH_VOICE_NAME` (default: `en-US-JasonNeural`)
- `REDIS_PORT` (default: `6380`)
- `REDIS_SSL` (default: `true`)

---

## 🐛 Troubleshooting

### Issue: PostgreSQL connection timeout
**Solution:** Run firewall update script
```bash
./backend/scripts/update_postgres_firewall.sh
```

### Issue: Redis connection refused
**Solution:** Verify SSL enabled and port 6380
```bash
az redis show --name my-voice-cache --resource-group voice-agent-rg --query enableNonSslPort
# Should return: false
```

### Issue: Twilio webhook not receiving requests
**Solution:** Verify webhook URL configured correctly
```bash
# Check Twilio console: Voice > Phone Numbers > [Your Number] > Voice Configuration
# Webhook URL should be: https://<your-azure-url>/voice
```

### Issue: Audio not streaming
**Solution:** Check WebSocket connection logs
```bash
# Look for "WebSocket connected" in logs
az containerapp logs show --name voice-agent-backend --resource-group voice-agent-rg --follow
```

### Issue: GPT-5 responses slow
**Solution:** Increase deployment capacity
```bash
az cognitiveservices account deployment update \
  --name my-voice-agent-openai \
  --resource-group voice-agent-rg \
  --deployment-name gpt-5-chat \
  --capacity 20  # Increase from 10 to 20
```

---

## 📞 Production Readiness Checklist

Before launching to production:

- [ ] All environment variables configured in Azure Container Apps
- [ ] HIPAA compliance configuration completed (audit logging, threat protection)
- [ ] Twilio HIPAA add-on purchased and configured
- [ ] Azure BAA signed
- [ ] PostgreSQL firewall cron job set up
- [ ] Azure Monitor alerts configured
- [ ] Container Apps scaling rules configured
- [ ] Backup and disaster recovery plan in place
- [ ] End-to-end testing completed with 10+ test calls
- [ ] Frontend dashboard deployed (if using)
- [ ] User training completed (caregivers, administrators)

---

## 📚 Related Documentation

- **`claude.md`**: Comprehensive technical documentation
- **`backend/README.md`**: Backend-specific details
- **`backend/database/schema_postgres.sql`**: Full database schema
- **`backend/src/senior_health_prompt.py`**: AI personality and instructions
- **Azure OpenAI Docs**: https://learn.microsoft.com/en-us/azure/ai-services/openai/
- **Azure Speech Docs**: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/
- **Twilio Media Streams**: https://www.twilio.com/docs/voice/media-streams

---

**Last Updated**: October 2025
**Architecture Version**: 1.0
**Status**: Production-ready (HIPAA-compliant with Twilio add-on)

**System Ready for Testing**: ✅ Yes - Follow the Testing Checklist above
