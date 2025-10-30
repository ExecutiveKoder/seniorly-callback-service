# Senior Health Monitoring Voice Agent

An AI-powered voice service that calls seniors daily for wellness check-ins, cognitive health monitoring, and early detection of health concerns.

## Mission

Build a robust health monitoring system that:
- Performs daily automated check-ins with seniors
- Monitors cognitive function through natural conversations
- Tracks vitals and health concerns
- Identifies early signs of dementia or health decline
- Builds comprehensive longitudinal health profiles

## Features

- Natural, empathetic AI conversations (GPT-5-CHAT)
- Speech-to-Text and Text-to-Speech (Azure Speech Services)
- Subtle cognitive assessment through conversation and games
- Conversation history storage (Azure Cosmos DB)
- Session state management (Azure Redis Cache)
- Knowledge base integration (Azure AI Search)
- Local testing mode (microphone/speaker)
- Future: Automated phone calls via Azure Communication Services

## Architecture

```
User Voice Input
     ↓
Azure Speech Services (STT) → Convert voice to text
     ↓
Azure OpenAI GPT-5-CHAT → Generate empathetic response
     ↓
Azure Speech Services (TTS) → Convert text back to voice
     ↓
User Hears Response
     ↓
Data Storage:
  - Cosmos DB: Conversation history
  - Redis Cache: Session state
  - AI Search: Knowledge base (future)
```

## Project Structure

```
callback-voice-agent/
├── .env                          # Environment variables (credentials)
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── claude.md                     # Infrastructure documentation
├── instructions.txt              # Original setup notes
├── src/
│   ├── __init__.py
│   ├── config.py                 # Configuration management
│   ├── main.py                   # Main application entry point
│   ├── senior_health_prompt.py   # AI system prompts
│   └── services/
│       ├── __init__.py
│       ├── speech_service.py     # Azure Speech Services
│       ├── openai_service.py     # Azure OpenAI GPT-5-CHAT
│       └── data_service.py       # Cosmos DB, Redis, AI Search
└── tests/                        # Future: Test files
```

## Prerequisites

- Python 3.11+
- Azure subscription with services deployed (see `claude.md`)
- Microphone and speakers for local testing
- All credentials in `.env` file

## Installation

### 1. Clone/Navigate to Project

```bash
cd /Users/satssehgal/Documents/Code/callback-voice-agent
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** If `pyaudio` fails to install on macOS:
```bash
brew install portaudio
pip install pyaudio
```

### 4. Verify Environment Variables

Ensure your `.env` file has all required credentials:

```bash
cat .env
```

Required variables:
- `AZURE_OPENAI_KEY` and `AZURE_OPENAI_ENDPOINT`
- `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`
- `AZURE_COSMOS_ENDPOINT` and `AZURE_COSMOS_KEY`
- `AZURE_REDIS_HOST` and `AZURE_REDIS_KEY`
- `AZURE_SEARCH_ENDPOINT` and `AZURE_SEARCH_KEY`

## Usage

### Run the Application

```bash
python src/main.py
```

### Main Menu Options

1. **Start Voice Conversation** - Talk using microphone/speaker
2. **Start Text Conversation** - Type messages (faster for testing)
3. **View Conversation History** - Review past sessions
4. **Test Services** - Verify Azure service connections
5. **Exit** - Quit application

### Voice Conversation Mode

1. Select option 1 from menu
2. Enter senior's name (optional)
3. Speak into your microphone when prompted
4. AI will respond through your speakers
5. Say "goodbye" or "end call" to finish

### Text Conversation Mode

1. Select option 2 from menu
2. Enter senior's name (optional)
3. Type messages and press Enter
4. AI responses appear in terminal
5. Type "quit" to finish

## AI Conversation Flow

The AI follows a structured daily check-in:

1. **Warm Greeting** - "How are you doing today?"
2. **Sleep Quality** - Ask about last night's sleep
3. **Vitals Check** - Request any measurements (BP, heart rate, etc.)
4. **Pain/Discomfort** - Check for any physical issues
5. **Medication** - Confirm they've taken medications
6. **Concerns** - Listen to any worries or stories
7. **Cognitive Games** - Natural memory tests, word games
8. **Closing** - Positive farewell and reminder of tomorrow's call

## Cognitive Assessment

The AI subtly tests cognitive function through:

- **Memory Tests**: Recall previous conversations, remember word lists
- **Word Games**: Category fluency, word association
- **Date Awareness**: Casual questions about day/date
- **Story Recall**: Remember details from earlier in conversation
- **Problem Solving**: Simple daily life scenarios

## Data Storage

### Cosmos DB
- Stores complete conversation transcripts
- Tracks session metadata
- Builds longitudinal profiles

### Redis Cache
- Manages active session state
- Caches temporary data
- Fast session lookups

### AI Search
- (Future) Knowledge base for health information
- (Future) Personalized content retrieval

## Testing

### Quick Test (Text Mode)

```bash
python src/main.py
# Select option 2
# Have a short text conversation
```

### Full Test (Voice Mode)

```bash
python src/main.py
# Select option 1
# Ensure microphone and speakers are working
# Have a voice conversation
```

### View Saved Conversations

```bash
python src/main.py
# Select option 3
# Enter session ID from previous conversation
```

## Configuration

### Change Voice

Edit `.env`:
```bash
SPEECH_VOICE_NAME=en-US-GuyNeural
```

Available voices:
- `en-US-JennyNeural` (Default - warm, friendly female)
- `en-US-GuyNeural` (Male)
- `en-US-AriaNeural` (Female)
- See: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support

### Adjust AI Personality

Edit `src/senior_health_prompt.py` to modify:
- System prompt
- Conversation structure
- Cognitive assessment techniques
- Response style

## Deployment (Future)

### Phone Integration

Once Azure phone number is approved:
1. Update `.env` with phone number
2. Configure Azure Communication Services webhooks
3. Deploy to Azure Container Apps
4. Schedule automated daily calls

### Container Deployment

```bash
# Build Docker image
docker build -t voice-agent .

# Push to Azure Container Registry
az acr login --name myvoiceagentacr
docker tag voice-agent myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:latest
docker push myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:latest

# Deploy to Container Apps
az containerapp update --name voice-agent-app --resource-group voice-agent-rg \
  --image myvoiceagentacr-b7cwcyd4deh0f5ec.azurecr.io/voice-agent:latest
```

## Troubleshooting

### Microphone Not Working

**macOS:**
```bash
# Grant microphone permission in System Settings → Privacy & Security → Microphone
```

**Test microphone:**
```bash
python -c "import pyaudio; p = pyaudio.PyAudio(); print('Microphone OK')"
```

### Azure Service Errors

**Check connections:**
```bash
python src/main.py
# Select option 4 - Test Services
```

**Verify credentials:**
```bash
grep -E "KEY|ENDPOINT" .env | head -10
```

### Module Import Errors

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

## Security & Compliance

### HIPAA Compliance Considerations

⚠️ **Important**: This is a prototype. For production use with real patient data:

1. Enable Azure service encryption at rest
2. Use managed identities instead of keys
3. Enable audit logging on all services
4. Implement data retention policies
5. Add authentication and authorization
6. Obtain Business Associate Agreement (BAA) from Microsoft
7. Complete security assessment and penetration testing

### Data Privacy

- All conversations are stored in Azure Cosmos DB
- Session data cached in Redis (with TTL)
- No data leaves Azure infrastructure
- Credentials stored in `.env` (never commit to git!)

## Cost Estimates

Per 5-minute daily call per senior:
```
Azure OpenAI (GPT-5):     ~$0.10-0.15
Azure Speech (STT+TTS):   ~$0.13
Azure Cosmos DB:          ~$0.001
Azure Redis:              ~$0.002
Azure Container Apps:     ~$0.010
─────────────────────────────────
TOTAL:                    ~$0.25-0.30 per call
```

Monthly cost per senior (30 calls): **~$7.50-9.00**

With $25k Azure credits: Can support ~2,800-3,300 seniors for a month

## Documentation

- **claude.md** - Complete infrastructure audit and setup details
- **instructions.txt** - Original Azure setup notes
- **README.md** - This file

## Future Enhancements

- [ ] Scheduled automated calls via Azure Communication Services
- [ ] Family/caregiver dashboard
- [ ] Alert system for concerning changes
- [ ] Advanced cognitive assessment scoring
- [ ] Integration with EHR systems
- [ ] Multi-language support
- [ ] Video call option
- [ ] Medication reminder system
- [ ] Fall detection integration
- [ ] Analytics and reporting dashboard

## Support

For issues or questions:
1. Check `claude.md` for infrastructure details
2. Review Azure service status in Portal
3. Test individual services with option 4
4. Check logs in terminal output

## License

Proprietary - All Rights Reserved

## Authors

Sahitya Sehgal

---

**Version:** 1.0.0
**Last Updated:** October 30, 2025
**Status:** Development - Local Testing Phase
