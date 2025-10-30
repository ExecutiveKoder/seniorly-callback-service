# Seniorly Voice Agent Platform

AI-powered voice agent for senior health monitoring with real-time analytics dashboard.

## Project Structure

```
/
├── backend/          # Python voice agent + API
│   ├── src/         # Voice agent logic, AI, speech services
│   ├── database/    # Azure SQL schema and setup
│   └── tests/       # Backend tests
│
└── frontend/        # Next.js dashboard (coming soon)
    ├── pages/       # Dashboard pages
    ├── components/  # React components
    └── lib/         # API clients, utilities
```

## Features

### Backend (Voice Agent)
- **AI-Powered Conversations**: Azure OpenAI GPT-5 for natural senior interactions
- **Speech Services**: Azure Speech (Jason voice) for TTS/STT
- **Telephony**: AWS Connect (+18337876435) for outbound calling
- **Real-time Analytics**: Extracts vitals, cognitive metrics from conversations
- **Data Storage**:
  - Azure Cosmos DB for conversations
  - Azure Redis for session state
  - Azure SQL for analytics/dashboards

### Frontend (Dashboard)
- **Next.js + Tailwind CSS**: Responsive web & mobile
- **Authentication**: Secure user login
- **Analytics Dashboard**: View senior health metrics from Azure SQL
- **Real-time Updates**: Monitor active calls and health alerts

## Quick Start

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python src/main.py
```

### Frontend (Coming Soon)
```bash
cd frontend
npm install
npm run dev
```

## Architecture

**Call Flow:**
1. AWS Connect places outbound call to senior
2. Senior answers, audio streams to backend via Twilio Media Streams
3. Azure Speech converts speech → text
4. Azure OpenAI generates responses
5. Azure Speech converts text → speech (Jason voice)
6. Conversation data saved to Cosmos DB
7. Health metrics extracted and saved to Azure SQL
8. Dashboard reads from SQL for analytics

## Documentation

- `/backend/README.md` - Backend setup and architecture
- `/backend/database/` - Database schema and setup
- `/backend/DEPLOYMENT.md` - Azure deployment guide
- `/backend/SAFETY.md` - HIPAA compliance considerations

## Environment Variables

See `/backend/.env.example` for required Azure and AWS credentials.

## License

Proprietary - Seniorly Health Platform
