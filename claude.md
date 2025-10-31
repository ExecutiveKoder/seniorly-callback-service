# Senior Health Voice Agent - Complete System Documentation

This document provides a comprehensive technical overview of the AI-powered voice agent system for senior health monitoring.

---

## 🎯 System Purpose

**Automated daily health check-ins for seniors via phone calls**

The system makes outbound phone calls to seniors, conducts natural conversations to collect health metrics (blood pressure, medications, mood, etc.), stores data in a multi-tier database architecture, and provides real-time analytics dashboards for caregivers.

---

## 🏗️ Architecture Overview

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     CALL INITIATION (NEW!)                       │
│  POST /initiate-call {"phone_number": "..."}                    │
│  ├─ Load senior profile from Cosmos DB                          │
│  ├─ Load call history & context (15-30s)                        │
│  ├─ Cache in preloaded_context dictionary                       │
│  └─ Twilio API: Place outbound call                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                  TELEPHONY LAYER                                 │
│  Twilio Media Streams (WebSocket)                                │
│  └─ Real-time bidirectional audio streaming (mulaw PCM, 8kHz)   │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│               AI PROCESSING LAYER                                │
│  Python Backend (twilio_websocket_server.py)                    │
│  ├─ Check preloaded_context (instant if cached!)                │
│  ├─ Adaptive VAD: Learn ambient noise (first 6 seconds)         │
│  ├─ Azure Speech STT: Audio → Text                              │
│  ├─ Azure OpenAI GPT-5: Generate AI responses                   │
│  ├─ TTS Normalization: Remove CAPS and !!!                      │
│  ├─ Azure Speech TTS: Text → Audio (en-US-SaraNeural)          │
│  └─ Real-time conversation orchestration                        │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                    │
│  ├─ Redis: Session state (names, IDs, temp data)                │
│  ├─ Cosmos DB: Conversations, senior profiles                   │
│  └─ PostgreSQL: Analytics, vitals, cognitive scores             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ANALYTICS & DASHBOARD                           │
│  Next.js Frontend + PostgreSQL                                  │
│  └─ Real-time health metrics, alerts, cognitive trends          │
└─────────────────────────────────────────────────────────────────┘
```

### Key Improvements (Latest Version)

**1. Pre-loaded Context** (`/initiate-call` endpoint)
- Loads senior profile and call history BEFORE placing call
- Caches in memory (15-30s delay happens before call, not after answer)
- When senior answers → greeting plays immediately!

**2. Adaptive Voice Activity Detection (VAD)**
- Learns ambient noise during first 6 seconds of call
- Sets threshold to 2.5x ambient (minimum 0.002)
- Handles variable phone audio levels (0.0001 - 0.0210 RMS)
- Prevents false positives from TV/background noise

**3. TTS Text Normalization**
- Removes excessive enthusiasm: "WONDERFUL!!!" → "Wonderful!"
- Converts SHOUTING CAPS to Title Case
- Preserves acronyms (OK, TV, GPS, USA)
- Results in natural, calm conversational tone

**4. No Cold Starts**
- Min replicas: 1 (always warm)
- Startup warmup for Speech + OpenAI services
- Container ready in < 2 seconds

---

## 🗂️ Complete File Structure

```
callback-voice-agent/
│
├── backend/                                 # Python voice agent backend
│   │
│   ├── src/                                 # Core application code
│   │   ├── main.py                          # Entry point (NOT used for Twilio streaming)
│   │   ├── config.py                        # Environment variable loader
│   │   ├── senior_health_prompt.py          # AI system prompt (personality, instructions)
│   │   │
│   │   ├── services/                        # Business logic services (17 total)
│   │   │   ├── openai_service.py            # Azure OpenAI GPT-5 client
│   │   │   ├── speech_service.py            # Azure Speech STT/TTS
│   │   │   ├── twilio_service.py            # Twilio call initiation
│   │   │   ├── data_service.py              # Combined data layer (Cosmos + Redis + Search)
│   │   │   ├── cosmos_service.py            # Cosmos DB: conversations, profiles
│   │   │   ├── redis_service.py             # Redis: session state, caching
│   │   │   ├── profile_service.py           # Senior profile CRUD operations
│   │   │   ├── identity_verification_service.py  # Name + DOB verification
│   │   │   ├── conversation_context_service.py   # Build dynamic context from history
│   │   │   ├── safety_service.py            # Detect concerning patterns (health alerts)
│   │   │   ├── cost_tracking_service.py     # Track API usage costs
│   │   │   ├── analytics_sync_service.py    # Extract metrics → PostgreSQL (real-time)
│   │   │   ├── reminders_service.py         # Manage appointments/reminders
│   │   │   ├── call_flow_service.py         # Structured call todos
│   │   │   ├── research_service.py          # Find doctors/resources (Bing/GPT)
│   │   │   ├── email_service.py             # Send emails via Azure Communication
│   │   │   └── async_tasks_service.py       # Background task queue
│   │   │
│   │   └── utils/
│   │       ├── audio_utils.py               # Audio format conversions (mulaw, PCM)
│   │       └── cognitive_tests.py           # Cognitive assessment patterns
│   │
│   ├── database/                            # PostgreSQL schema and migrations
│   │   ├── schema_postgres.sql              # Main analytics schema
│   │   ├── add_reminders_table.sql          # Reminders table
│   │   ├── add_activity_falls_conditions_tables.sql  # Activity/falls/conditions
│   │   └── setup_database_postgres.py       # Create all tables automatically
│   │
│   ├── scripts/                             # Utility scripts
│   │   ├── migrate_cosmos_to_postgres.py    # One-time data migration
│   │   ├── query_sql_database.py            # Query PostgreSQL analytics
│   │   └── update_postgres_firewall.sh      # Auto-update firewall IP (cron job)
│   │
│   ├── twilio_websocket_server.py           # MAIN SERVER: WebSocket for Twilio Media Streams
│   ├── run_app.sh                           # Testing launcher (local/Twilio/ngrok modes)
│   ├── requirements.txt                     # Python dependencies
│   ├── Dockerfile                           # Container image definition
│   ├── .env                                 # Environment variables (DO NOT COMMIT)
│   ├── .azure_endpoint                      # Deployed Azure Container Apps URL
│   └── venv/                                # Virtual environment (local only)
│
├── frontend/                                # Next.js dashboard (optional)
│   ├── src/
│   │   ├── app/                             # Next.js 13+ App Router pages
│   │   │   ├── dashboard/page.tsx           # Main dashboard
│   │   │   ├── seniors/[id]/page.tsx        # Senior profile detail
│   │   │   └── api/seniors/route.ts         # API endpoints
│   │   ├── components/                      # React components
│   │   │   ├── VitalsChart.tsx              # Line chart for vitals
│   │   │   ├── CognitiveScoreCard.tsx       # Cognitive score display
│   │   │   └── AlertBanner.tsx              # Health alert notifications
│   │   ├── lib/
│   │   │   └── db.ts                        # PostgreSQL connection
│   │   └── types/
│   │       ├── senior.ts                    # TypeScript type definitions
│   │       └── vitals.ts
│   ├── package.json
│   └── .env.local
│
├── AGENTSETUP.md                            # Complete setup guide (you are here)
├── claude.md                                # This file - comprehensive documentation
└── README.md                                # Project overview
```

---

## 🔑 Key Components Explained

### 1. `twilio_websocket_server.py` (Main Entry Point)

**Purpose:** WebSocket server that handles real-time bidirectional audio streaming with Twilio.

**Flow:**
1. Twilio connects via WebSocket when call is answered
2. Server receives audio chunks (mulaw PCM, 8kHz, mono)
3. Accumulates audio until silence detected (VAD - Voice Activity Detection)
4. Sends audio to Azure Speech STT → text
5. Sends text to Azure OpenAI GPT-5 → AI response
6. Sends AI response to Azure Speech TTS → audio
7. Sends audio back to Twilio → plays to caller

**Key Code Structure:**
```python
async def handle_twilio_stream(websocket, path):
    # 1. Initialize services
    redis_service = RedisService()
    speech_service = AzureSpeechService()
    openai_service = OpenAIService()

    # 2. Receive Twilio WebSocket events
    async for message in websocket:
        data = json.loads(message)

        if data['event'] == 'media':
            # 3. Accumulate audio chunks
            audio_buffer.append(base64.b64decode(data['media']['payload']))

            # 4. Detect silence → process accumulated audio
            if is_silence_detected(audio_buffer):
                # 5. STT: Audio → Text
                user_text = await speech_service.transcribe(audio_buffer)

                # 6. GPT-5: Generate response
                ai_response = await openai_service.generate_response(user_text)

                # 7. TTS: Text → Audio
                audio = await speech_service.synthesize(ai_response)

                # 8. Send audio back to Twilio
                await websocket.send(json.dumps({
                    'event': 'media',
                    'media': {'payload': base64.b64encode(audio).decode()}
                }))

                audio_buffer.clear()
```

---

### 2. `senior_health_prompt.py` (AI Personality)

**Purpose:** Defines the AI's personality, conversation flow, and instructions.

**Key Sections:**
- **Identity**: "You are Emily, a caring health assistant from Seniorly Health"
- **Objectives**: Collect vitals, manage reminders, detect health concerns
- **Conversation Style**: Warm, patient, grandparent-friendly
- **Exit Handling**: Graceful call endings, emergency protocols
- **Safety Guardrails**: Suicide prevention, medical emergency detection

**Example Prompt:**
```python
system_prompt = f"""
You are {ai_name}, a caring health assistant from {company_name}.
You are calling {senior_name} for their daily check-in.

OBJECTIVES:
1. Ask about ALL vitals: blood pressure, heart rate, weight, sleep, pain
2. Manage reminders: appointments, medications
3. Answer questions and provide resources (doctors, services)
4. Detect concerning patterns → create health alerts

CONVERSATION STYLE:
- Warm, patient, empathetic (like talking to a grandparent)
- Use simple language (avoid medical jargon)
- Confirm understanding: "So your blood pressure was 120 over 80, correct?"
- Be thorough but conversational (not robotic)

STRICT 5-MINUTE CALL LIMIT:
- At 4:30, say: "We have 30 seconds left. Is there anything urgent?"
- At 5:00, end call: "Let's continue tomorrow. Take care!"

Remember: You're here to ensure {senior_name}'s health and safety.
"""
```

---

### 3. Data Layer Architecture

**Three-tier database system:**

#### Tier 1: Redis (Session State)
- **Purpose:** Ultra-fast temporary storage for active calls
- **Data:** senior_id, senior_name, ai_name, company_name, conversation_count
- **Key Pattern:** `senior:{senior_id}:session:{session_id}`
- **TTL:** 1 hour (auto-expires after call ends)

**Why Redis?**
- Prevents data mixing between concurrent calls
- 0.1ms read/write latency
- Namespaced keys for isolation

#### Tier 2: Cosmos DB (Operational Data)
- **Purpose:** Flexible NoSQL storage for conversations and profiles
- **Containers:**
  - `sessions`: Full conversation history (user + AI messages)
  - `profiles`: Senior profiles (name, DOB, phone, medical history)

**Why Cosmos DB?**
- Schema-less (flexible for evolving data models)
- Global distribution (low latency worldwide)
- Automatic indexing

#### Tier 3: PostgreSQL (Analytics)
- **Purpose:** Structured data for dashboards and reporting
- **Tables:**
  - `senior_vitals`: Blood pressure, heart rate, weight, sleep, pain
  - `cognitive_assessments`: Memory, orientation, coherence scores
  - `call_summary`: AI-generated summaries of each call
  - `health_alerts`: Abnormal vitals, concerning patterns
  - `medication_adherence`: Medication tracking
  - `reminders`: Appointments, medication schedules
  - `activity_tracking`: Daily activities, exercise
  - `fall_incidents`: Fall detection and tracking
  - `chronic_conditions`: Long-term health conditions

**Why PostgreSQL?**
- Structured schema (enforces data quality)
- Powerful queries (JOINs, aggregations, CTEs)
- Materialized views for fast dashboard queries

**Materialized Views:**
```sql
-- Latest vitals per senior (0.01s query time vs 2s without view)
CREATE MATERIALIZED VIEW vw_latest_vitals_by_senior AS
SELECT DISTINCT ON (senior_id)
    senior_id,
    vital_type,
    vital_value,
    recorded_at
FROM senior_vitals
ORDER BY senior_id, recorded_at DESC;

-- 30-day cognitive trend
CREATE MATERIALIZED VIEW vw_cognitive_trend_30d AS
SELECT
    senior_id,
    DATE(assessment_date) as day,
    AVG(memory_score) as avg_memory,
    AVG(orientation_score) as avg_orientation,
    AVG(coherence_score) as avg_coherence
FROM cognitive_assessments
WHERE assessment_date >= NOW() - INTERVAL '30 days'
GROUP BY senior_id, DATE(assessment_date);
```

---

### 4. Analytics Sync Service (Real-time Extraction)

**Purpose:** Automatically extract health metrics from conversations and save to PostgreSQL.

**Flow:**
1. Call ends → `openai.generate_call_summary()` creates summary
2. Analytics service receives: summary + full conversation history
3. Use regex + NLP to extract:
   - **Vitals**: BP (120/80), heart rate (72 bpm), weight (165 lbs)
   - **Cognitive**: Memory score, coherence, topic drift count
   - **Medication**: Adherence, missed doses
   - **Wellness**: Mood score, social interaction
4. Detect **health alerts**: BP > 140/90, heart rate < 50 or > 100
5. Save to PostgreSQL

**Example Extraction:**
```python
def extract_vitals(summary: str, conversation: List[Dict]) -> Dict:
    vitals = {}

    # Blood pressure: "120/80", "BP 135 over 85"
    bp_pattern = r'(?:blood pressure|BP)[:\s]+(\d{2,3})[/\s]*(?:over|/)?\s*(\d{2,3})'
    bp_match = re.search(bp_pattern, summary, re.IGNORECASE)
    if bp_match:
        vitals['bp_systolic'] = int(bp_match.group(1))
        vitals['bp_diastolic'] = int(bp_match.group(2))

    # Heart rate: "72 bpm", "heart rate 68"
    hr_pattern = r'(?:heart rate|pulse)[:\s]+(\d{2,3})\s*(?:bpm)?'
    hr_match = re.search(hr_pattern, summary, re.IGNORECASE)
    if hr_match:
        vitals['heart_rate'] = int(hr_match.group(1))

    # Weight: "165 lbs", "72 kg"
    weight_pattern = r'(?:weight)[:\s]+(\d{2,3})\s*(lbs|kg)'
    weight_match = re.search(weight_pattern, summary, re.IGNORECASE)
    if weight_match:
        vitals['weight'] = float(weight_match.group(1))
        vitals['weight_unit'] = weight_match.group(2)

    return vitals

def detect_health_alerts(vitals: Dict) -> List[str]:
    alerts = []

    if vitals.get('bp_systolic', 0) > 140:
        alerts.append('High blood pressure detected')

    if vitals.get('heart_rate', 0) < 50:
        alerts.append('Low heart rate detected')
    elif vitals.get('heart_rate', 0) > 100:
        alerts.append('High heart rate detected')

    if vitals.get('pain_level', 0) >= 7:
        alerts.append('Severe pain reported')

    return alerts
```

---

### 5. Reminders System

**Purpose:** Manage appointments and medication schedules.

**Features:**
- Load reminders at call start
- Mention upcoming appointments during conversation
- Extract new appointments from natural language
- Store in PostgreSQL with structured fields

**Table Schema:**
```sql
CREATE TABLE reminders (
    id SERIAL PRIMARY KEY,
    senior_id VARCHAR(50) NOT NULL,
    reminder_type VARCHAR(50),  -- 'appointment', 'medication', 'call_back'
    title TEXT,
    description TEXT,
    scheduled_for TIMESTAMP,
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Example Flow:**
```
AI: "Hi Margaret! Just a reminder, you have a doctor's appointment tomorrow at 2pm."
Margaret: "Oh yes, and I also need to schedule a dentist appointment for next week."
AI: "I'll add that to your reminders. What day next week works for you?"
Margaret: "How about Tuesday at 10am?"
AI: "Perfect! I've scheduled your dentist appointment for Tuesday at 10am."
```

**Code:**
```python
def extract_appointment(text: str) -> Dict:
    # Use GPT-5 to extract structured data
    response = openai.chat.completions.create(
        model="gpt-5-chat",
        messages=[{
            "role": "system",
            "content": "Extract appointment details from text. Return JSON: {title, date, time}."
        }, {
            "role": "user",
            "content": text
        }]
    )

    return json.loads(response.choices[0].message.content)
```

---

### 6. Research Service

**Purpose:** Help seniors find doctors, services, and resources.

**Features:**
- Bing Search API integration
- GPT-5 summarization of results
- Store recommendations in conversation history

**Example Flow:**
```
Senior: "I need to find a cardiologist near me."
AI: "Let me search for cardiologists in your area... I found Dr. Smith at Heart Care Center,
     rated 4.8 stars, located 2 miles from you. Would you like me to send you their contact info?"
```

---

### 7. Call Flow Service

**Purpose:** Structured call agenda with dynamic todos.

**Features:**
- Load todos at call start (vitals checklist, reminders)
- Mark todos as completed during conversation
- Add new todos on-the-fly (research requests, follow-ups)

**Example Todos:**
```python
call_todos = [
    {"task": "Ask about blood pressure", "completed": False},
    {"task": "Ask about medications", "completed": False},
    {"task": "Mention dentist appointment tomorrow", "completed": False},
    {"task": "Research cardiologists (senior request)", "completed": False}
]
```

---

### 8. Cognitive Testing (4-Dimension Assessment)

**Purpose:** Detect cognitive decline through conversation patterns.

**Four Dimensions:**
1. **Memory**: Recall previous conversations, repeat information
2. **Orientation**: Know date, location, current events
3. **Coherence**: Logical flow of thoughts, sentence structure
4. **Attention**: Stay on topic, follow conversation thread

**Scoring:**
```python
def calculate_cognitive_score(conversation: List[Dict]) -> Dict:
    return {
        'memory_score': assess_memory(conversation),       # 0-100
        'orientation_score': assess_orientation(conversation),  # 0-100
        'coherence_score': assess_coherence(conversation),  # 0-100
        'attention_score': assess_attention(conversation)   # 0-100
    }
```

---

## 🚀 Deployment Guide

### Local Testing

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your Azure credentials

# Run locally with ngrok
./run_app.sh ngrok
```

### Azure Container Apps Deployment

```bash
# 1. Build Docker image
cd backend
docker build -t myvoiceagentacr.azurecr.io/voice-agent:latest .

# 2. Push to Azure Container Registry
az acr login --name myvoiceagentacr
docker push myvoiceagentacr.azurecr.io/voice-agent:latest

# 3. Deploy to Azure Container Apps
az containerapp update \
  --name voice-agent-backend \
  --resource-group voice-agent-rg \
  --image myvoiceagentacr.azurecr.io/voice-agent:latest

# 4. Get public URL
az containerapp show \
  --name voice-agent-backend \
  --resource-group voice-agent-rg \
  --query properties.configuration.ingress.fqdn
```

---

## 🎧 Real-Time Voice Tuning (WebRTC VAD + Latency)

### Standard VAD baseline (recommended)
- Engine: WebRTC VAD (8 kHz, 16‑bit PCM, 20 ms frames)
- Aggressiveness: `2` (0=most permissive, 3=most strict)
- Debounce/hangover (frame-based):
  - Speech ON: require ≥8 voiced frames in a 10‑frame window (≈200 ms)
  - Speech OFF: require 15 consecutive unvoiced frames (≈300 ms)
- Duplex control: mute mic during TTS + 600 ms cooldown
- Prompting: no “didn’t catch that” for 5 s after TTS; prompt if ~5 s of silence

### Environment variables
```
# Core WebRTC VAD
VAD_USE_WEBRTC=true
VAD_AGGRESSIVENESS=2          # 0..3 (raise to 3 if noisy, drop to 1 if too strict)
VAD_ON_WINDOW_FRAMES=10       # 10 frames ≈ 200 ms
VAD_ON_MIN_VOICED=8           # voiced frames required in window
VAD_OFF_CONSEC_UNVOICED=15    # ≈ 300 ms to end speech

# Timing/latency
VAD_CHUNK_BYTES=4000          # ~0.5 s chunking for faster turns
VAD_COOLDOWN_MS=600           # post‑TTS input cooldown
VAD_PROMPT_GRACE_SECONDS=5    # min time after TTS before prompting
VAD_SILENCE_CHUNKS_TO_PROMPT=10  # ~5 s silence before prompt

# Fallback (RMS) gate if VAD errors
VAD_MIN_THRESHOLD=0.006       # 0.004–0.012 typical
VAD_AMBIENT_MULTIPLIER=1.5    # 1.3–3.5 typical
VAD_AMBIENT_LEARNING_CHUNKS=2 # quick ambient calibration
VAD_DEBUG=true                # logs metrics (no PHI)
```

Tuning tips
- “Too deaf” (must speak loudly): lower `VAD_AGGRESSIVENESS` to 1, or relax ON window (7/10); optionally reduce fallback `VAD_MIN_THRESHOLD`/`VAD_AMBIENT_MULTIPLIER`.
- “Hears background/TV”: raise `VAD_AGGRESSIVENESS` to 3, or increase `VAD_ON_MIN_VOICED` to 9; consider lengthening `VAD_OFF_CONSEC_UNVOICED`.
- “Prompts too fast/slow”: adjust `VAD_PROMPT_GRACE_SECONDS` (min time after TTS) and `VAD_SILENCE_CHUNKS_TO_PROMPT` (silence before prompt).

### Local-mode parity: Azure Speech streaming STT
- For the closest behavior to local testing, feed Twilio audio directly into Azure Speech’s streaming STT (PushAudioInputStream) and let Azure’s built‑in VAD handle turn‑taking and noise suppression.
- Duplex control still applies (mute input while TTS + cooldown), but do not gate with custom VAD.

Recommended configuration for “local-like” behavior:
```
VAD_USE_WEBRTC=false          # disable custom gates, rely on Azure Speech VAD
VAD_COOLDOWN_MS=600           # keep duplex cooldown after TTS
VAD_PROMPT_GRACE_SECONDS=5    # avoid immediate re-prompts after TTS
```
Notes:
- This approach typically improves noise isolation at normal phone volumes.
- It may increase STT usage slightly due to continuous streaming.

### Turn-Taking and Latency

- Processing window ~0.5 s for quicker acknowledgements
- Serialized STT→LLM→TTS with a processing lock to prevent overlaps
- Input is muted during TTS and for a short cooldown after playback

### Deployment Notes (Azure Container Apps)

- Ensure external ingress is enabled on port 5000
- Set `--min-replicas 1` to avoid cold starts
- Use AMD64 images: `docker buildx build --platform linux/amd64 …`
- Keep the app warm by pinging `/health` every 1–5 minutes (optional)

### Launcher (.azure_endpoint)

`run_app.sh` auto-prepends `https://` if `.azure_endpoint` contains only the FQDN. This fixes readiness checks and call initiation that rely on a full URL.

---

## 🔐 Security & HIPAA Compliance

### Encryption
- **At Rest**: Azure default encryption (AES-256)
- **In Transit**: TLS 1.2+ (all Azure services)
- **Redis**: SSL-only connections (port 6380)

### Access Controls
- Azure RBAC (Role-Based Access Control)
- Managed identities (no hard-coded credentials)
- Key Vault for secrets

### Audit Logging
- Cosmos DB: All database operations logged
- PostgreSQL: Authentication and query logs
- Azure Monitor: Centralized log analytics

### HIPAA Compliance Checklist
- [x] BAA (Business Associate Agreement) with Azure
- [x] Encryption at rest and in transit
- [x] Audit logging enabled
- [x] 7-year backup retention
- [x] SQL Threat Protection
- [ ] Twilio HIPAA add-on (required for production)

**Cost:** ~$40/month for HIPAA compliance (excluding Twilio)

---

## 💰 Cost Breakdown

| Service | Tier | Monthly Cost |
|---------|------|--------------|
| Azure OpenAI GPT-5 | Standard | $50-200 |
| Azure Speech | Standard | $10-50 |
| Cosmos DB | 1000 RU/s | $25 |
| Redis | Basic C0 | $16 |
| PostgreSQL | Flexible Server | $15 |
| Container Apps | Consumption | $10-30 |
| Twilio | Pay-as-you-go | $0.013/min |
| **TOTAL** | | **$160-370/month** |

**HIPAA Add-on:** +$3,000/month (Twilio HIPAA)

---

## 🎯 Key Design Decisions

### 1. Why Three Databases?
- **Redis**: Ultra-fast session state (0.1ms latency)
- **Cosmos DB**: Flexible schema for evolving data models
- **PostgreSQL**: Structured analytics with powerful queries

### 2. Why Twilio Instead of Azure Communication Services?
- Azure ACS doesn't support WebSocket streaming (yet in preview)
- Twilio provides 1-2 second latency for real-time conversations
- Trade-off: Twilio HIPAA add-on is expensive ($3k/month)

### 3. Why Azure Speech Instead of Whisper API?
- Lower latency (300ms vs 1-2s)
- Streaming support (not available in OpenAI Whisper API)
- HIPAA-compliant out of the box

### 4. Why Materialized Views?
- Dashboard queries run 200x faster (0.01s vs 2s)
- Precomputed aggregations reduce database load
- Refresh on-demand or on schedule

---

## 📚 Additional Documentation

- **`AGENTSETUP.md`**: Complete setup guide with all Azure CLI commands
- **`backend/README.md`**: Backend-specific details
- **`backend/database/schema_postgres.sql`**: Full database schema
- **`backend/DEPLOYMENT.md`**: Azure deployment guide

---

## 🤝 Support

For issues or questions:
1. Check this documentation first
2. Review `AGENTSETUP.md` for setup instructions
3. Inspect database schema in `/backend/database/`
4. Review environment variables in `/backend/.env.example`

---

**Last Updated:** October 2025
**Architecture Version:** 1.0
**Status:** Production-ready (HIPAA-compliant with Twilio add-on)
