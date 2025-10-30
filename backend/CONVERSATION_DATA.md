# Conversation Data Storage & Access Guide

## Where Are Conversations Stored?

All raw conversation transcripts are stored in **Azure Cosmos DB** in the `sessions` container.

### Data Structure

Each session document in Cosmos DB looks like this:

```json
{
  "id": "abc123-session-uuid",
  "sessionId": "abc123-session-uuid",
  "createdAt": "2025-10-30T12:34:56.789Z",
  "updatedAt": "2025-10-30T12:39:20.123Z",
  "messages": [
    {
      "role": "assistant",
      "content": "Hello John! This is Jessica calling from Seniorly. How are you doing today?",
      "timestamp": "2025-10-30T12:34:56.789Z",
      "metadata": {
        "safety_analysis": {...}
      }
    },
    {
      "role": "user",
      "content": "I'm doing well, thank you!",
      "timestamp": "2025-10-30T12:35:02.123Z",
      "metadata": {...}
    },
    {
      "role": "assistant",
      "content": "That's wonderful to hear! Let's start with your blood pressure...",
      "timestamp": "2025-10-30T12:35:05.456Z",
      "metadata": {...}
    }
  ],
  "metadata": {
    "senior_name": "John",
    "senior_id": "senior-uuid-123",
    "phone_number": "289-324-2125",
    "duration": 287,
    "summary": "John reported feeling well. Blood pressure: 120/80...",
    "completed": true,
    "ai_name": "Jessica",
    "company_name": "Seniorly"
  }
}
```

## Accessing Conversations

### Option 1: Azure Portal (Manual)

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Cosmos DB account: `my-voice-agent-db`
3. Open database: `conversations`
4. Open container: `sessions`
5. Click "Items" to browse sessions
6. Click any session to see the full conversation in the `messages` array

### Option 2: Export Script (Recommended)

Use the provided export script to extract all conversations:

```bash
cd backend

# Export all conversations as text transcripts
python export_transcripts.py

# Export only last 7 days
python export_transcripts.py --days 7

# Export single session
python export_transcripts.py --session abc123-session-uuid

# Export all sessions for a specific senior
python export_transcripts.py --senior senior-uuid-123

# Export as JSONL format (for ML training)
python export_transcripts.py --jsonl
```

**Output:**
- Creates folder: `backend/exports/YYYYMMDD_HHMMSS/`
- Text transcripts: `{session_id}.txt`
- Training data: `training_data.jsonl`

### Option 3: Python API

```python
from src.services.data_service import CosmosDBService
from src.config import config

# Initialize Cosmos DB
cosmos = CosmosDBService(
    endpoint=config.AZURE_COSMOS_ENDPOINT,
    key=config.AZURE_COSMOS_KEY,
    database_name=config.COSMOS_DATABASE,
    container_name=config.COSMOS_CONTAINER
)

# Get formatted transcript for a session
transcript = cosmos.get_conversation_transcript("session-id-here")
print(transcript)

# Get raw session data
session = cosmos.get_session("session-id-here")
messages = session['messages']
for msg in messages:
    print(f"{msg['role'].upper()}: {msg['content']}")
```

## What Data Is Stored?

### Per Message:
- **role**: "user" or "assistant"
- **content**: Exact text of what was said
- **timestamp**: When the message was sent
- **metadata**: Safety analysis, alerts, etc.

### Per Session (in metadata):
- **senior_name**: First name of senior
- **senior_id**: Unique senior identifier
- **phone_number**: Senior's phone number
- **duration**: Call duration in seconds
- **summary**: AI-generated call summary
- **completed**: Whether call finished successfully
- **ai_name**: Name of AI assistant (e.g., "Jessica")
- **company_name**: "Seniorly"

## Use Cases

### 1. Training Data for AI Fine-Tuning

Export conversations in JSONL format:

```bash
python export_transcripts.py --jsonl --days 30
```

Use `training_data.jsonl` to fine-tune your model with real senior conversations.

**Format:**
```json
{"session_id": "...", "created_at": "...", "metadata": {...}, "messages": [{"role": "assistant", "content": "..."}, {"role": "user", "content": "..."}]}
```

### 2. Quality Review & Auditing

Export readable text transcripts:

```bash
python export_transcripts.py --days 7
```

Review transcripts to:
- Check AI behavior
- Identify issues
- Monitor safety protocols
- Ensure empathetic responses

### 3. Senior Health Monitoring

Query sessions for specific senior:

```bash
python export_transcripts.py --senior <senior-id>
```

Review conversation history to track:
- Health trends over time
- Cognitive changes
- Medication adherence patterns

### 4. Analytics & Reporting

Session metadata is automatically extracted and stored in Azure SQL for dashboard analytics:
- Vitals trends
- Cognitive assessments
- Health alerts
- Call summaries

## Querying Cosmos DB Directly

### Azure CLI
```bash
# Get all sessions
az cosmosdb sql query \
  --account-name my-voice-agent-db \
  --database-name conversations \
  --container-name sessions \
  --query-text "SELECT * FROM c"

# Get sessions for specific senior
az cosmosdb sql query \
  --account-name my-voice-agent-db \
  --database-name conversations \
  --container-name sessions \
  --query-text "SELECT * FROM c WHERE c.metadata.senior_id = 'senior-id-here'"

# Get sessions from last 24 hours
az cosmosdb sql query \
  --account-name my-voice-agent-db \
  --database-name conversations \
  --container-name sessions \
  --query-text "SELECT * FROM c WHERE c.createdAt >= '2025-10-29T00:00:00Z'"
```

### Python SDK
```python
from azure.cosmos import CosmosClient

client = CosmosClient(endpoint, key)
database = client.get_database_client("conversations")
container = database.get_container_client("sessions")

# Query all sessions
query = "SELECT * FROM c"
sessions = list(container.query_items(
    query=query,
    enable_cross_partition_query=True
))

# Filter by senior
query = "SELECT * FROM c WHERE c.metadata.senior_id = 'senior-123'"
senior_sessions = list(container.query_items(
    query=query,
    enable_cross_partition_query=True
))
```

## Data Retention

**Current Setup:**
- No automatic deletion
- All conversations stored indefinitely
- Manually delete old sessions via Azure Portal if needed

**Recommendations:**
- Keep last 90 days for active use
- Archive older data to Azure Blob Storage (cheaper)
- Implement Time-To-Live (TTL) policy in Cosmos DB

## Privacy & Security

**HIPAA Considerations:**
- Conversations contain PHI (Protected Health Information)
- Cosmos DB is HIPAA-compliant (with proper configuration)
- Access requires Azure credentials
- Enable encryption at rest and in transit
- Audit all access with Azure Monitor

**Safety Analysis:**
- Each message includes safety analysis in metadata
- Emergency situations flagged with alert level
- Review safety alerts regularly

## Summary

✅ **Raw conversations are stored** in Cosmos DB `sessions` container
✅ **Full message history preserved** in `messages` array
✅ **Metadata included** for context (senior info, duration, summary)
✅ **Export script provided** for easy access
✅ **Multiple formats available** (text, JSONL)
✅ **Queryable via Azure Portal, CLI, or Python SDK**

**Next Steps:**
1. Run `python export_transcripts.py` to see your conversations
2. Review transcripts for quality
3. Use JSONL format for ML training
4. Query Cosmos DB for specific analysis needs
