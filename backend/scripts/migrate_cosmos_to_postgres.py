"""
Migrate health data from Cosmos DB conversations to PostgreSQL analytics database
Parses conversations to extract vitals, cognitive indicators, and health metrics
"""
import os
import sys
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from azure.cosmos import CosmosClient
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

load_dotenv()

# Initialize Azure Key Vault
KEY_VAULT_NAME = os.getenv('AZURE_KEY_VAULT_NAME', 'seniorly-secrets')
KEY_VAULT_URL = f"https://{KEY_VAULT_NAME}.vault.azure.net"

try:
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
    pg_password = secret_client.get_secret('AzurePostgresPassword').value
    cosmos_key = secret_client.get_secret('AzureCosmosKey').value
except Exception as e:
    print(f"⚠️  Using .env fallback: {e}")
    pg_password = os.getenv('AZURE_POSTGRES_PASSWORD').strip("'")
    cosmos_key = os.getenv('AZURE_COSMOS_KEY').strip("'")

# Connect to Cosmos DB
cosmos_endpoint = os.getenv('AZURE_COSMOS_ENDPOINT').strip("'")
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
cosmos_db = cosmos_client.get_database_client('conversations')
cosmos_container = cosmos_db.get_container_client('sessions')

# Connect to PostgreSQL
pg_conn = psycopg2.connect(
    host=os.getenv('AZURE_POSTGRES_SERVER').strip("'"),
    database=os.getenv('AZURE_POSTGRES_DATABASE').strip("'"),
    user=os.getenv('AZURE_POSTGRES_USERNAME').strip("'"),
    password=pg_password,
    port=os.getenv('AZURE_POSTGRES_PORT', '5432').strip("'"),
    sslmode='require'
)
pg_conn.autocommit = False
pg_cursor = pg_conn.cursor()

print("✅ Connected to Cosmos DB and PostgreSQL\n")

# Helper functions to extract data from conversations
def extract_blood_pressure(text: str) -> Optional[Tuple[int, int]]:
    """Extract blood pressure like '120/80' or '120 over 80'"""
    patterns = [
        r'(\d{2,3})\s*/\s*(\d{2,3})',  # 120/80
        r'(\d{2,3})\s+over\s+(\d{2,3})',  # 120 over 80
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            systolic, diastolic = int(match.group(1)), int(match.group(2))
            # Validate reasonable ranges
            if 60 <= systolic <= 250 and 40 <= diastolic <= 150:
                return (systolic, diastolic)
    return None

def extract_heart_rate(text: str) -> Optional[int]:
    """Extract heart rate mentions"""
    # Look for heart rate context
    if re.search(r'\b(heart rate|pulse|bpm)\b', text, re.IGNORECASE):
        # Find nearby numbers
        match = re.search(r'\b(\d{2,3})\b', text)
        if match:
            hr = int(match.group(1))
            if 30 <= hr <= 200:  # Reasonable range
                return hr
    return None

def extract_sleep_hours(text: str) -> Optional[float]:
    """Extract sleep duration"""
    patterns = [
        r'(\d+\.?\d*)\s*hours?\s+(?:of\s+)?sleep',
        r'slept?\s+(?:for\s+)?(\d+\.?\d*)\s*hours?',
        r'got\s+(?:about\s+)?(\d+\.?\d*)\s*hours?',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            hours = float(match.group(1))
            if 0 <= hours <= 24:
                return hours
    return None

def extract_pain_level(text: str) -> Optional[int]:
    """Extract pain level (1-10 scale)"""
    if re.search(r'\b(pain|hurt|ache|discomfort)\b', text, re.IGNORECASE):
        match = re.search(r'\b(\d{1,2})\s*(?:out of 10|/10)?\b', text)
        if match:
            pain = int(match.group(1))
            if 0 <= pain <= 10:
                return pain
    return None

def extract_medications_taken(text: str) -> Optional[bool]:
    """Determine if medications were taken"""
    if re.search(r'\b(took|taken|take|taking)\s+(my\s+)?(meds|medications?|pills?)\b', text, re.IGNORECASE):
        return True
    if re.search(r'\b(yes|yeah|yep|uh-huh),?\s+(I\s+)?(did|took|taken)\b', text, re.IGNORECASE):
        return True
    if re.search(r'\b(didn\'?t|haven\'?t|forgot|missed)\s+(my\s+)?(meds|medications?|pills?)\b', text, re.IGNORECASE):
        return False
    return None

def extract_cognitive_indicators(messages: List[Dict]) -> Dict[str, any]:
    """
    Analyze conversation for cognitive health indicators
    Returns scores for memory, orientation, language, executive function
    """
    scores = {
        'memory_score': None,
        'orientation_score': None,
        'language_score': None,
        'executive_function_score': None,
        'coherence_score': None,
        'overall_score': None
    }

    # Simple heuristics based on conversation quality
    total_turns = len([m for m in messages if m['role'] == 'user'])

    if total_turns >= 5:
        # Estimate based on conversation engagement
        user_messages = [m['content'] for m in messages if m['role'] == 'user']

        # Language score: based on response length and coherence
        avg_length = sum(len(m.split()) for m in user_messages) / len(user_messages) if user_messages else 0
        scores['language_score'] = min(100, int(avg_length * 10))  # Simple heuristic

        # Orientation score: assume good if they're responding appropriately
        scores['orientation_score'] = 85  # Default assumption

        # Memory score: check if they reference previous info
        has_memory_refs = any(re.search(r'\b(remember|last time|before|earlier)\b', m, re.IGNORECASE)
                             for m in user_messages)
        scores['memory_score'] = 90 if has_memory_refs else 75

        # Executive function: check if they can explain decisions/plans
        has_planning = any(re.search(r'\b(will|going to|plan|later|tomorrow)\b', m, re.IGNORECASE)
                          for m in user_messages)
        scores['executive_function_score'] = 85 if has_planning else 70

        # Overall score
        valid_scores = [s for s in [scores['memory_score'], scores['orientation_score'],
                                    scores['language_score'], scores['executive_function_score']] if s]
        scores['overall_score'] = int(sum(valid_scores) / len(valid_scores)) if valid_scores else None

    return scores

def parse_conversation(session: Dict) -> Dict[str, any]:
    """Parse a conversation session and extract all health data"""
    session_id = session['sessionId']
    messages = session.get('messages', [])
    metadata = session.get('metadata', {})
    created_at = datetime.fromisoformat(session['createdAt'].replace('Z', '+00:00'))

    # Get senior_id from metadata or generate from session
    senior_id = metadata.get('senior_id', session_id.split('-')[0])

    data = {
        'session_id': session_id,
        'senior_id': senior_id,
        'call_date': created_at,
        'vitals': [],
        'cognitive': extract_cognitive_indicators(messages),
        'call_summary': {
            'call_duration': metadata.get('call_duration'),
            'call_completed': metadata.get('call_completed', True),
            'medication_adherence': None,
        },
        'medications_taken': None,
    }

    # Parse messages for health data
    for message in messages:
        content = message.get('content', '')
        timestamp = datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))

        # Extract vitals
        bp = extract_blood_pressure(content)
        if bp:
            data['vitals'].append({
                'vital_type': 'bp_systolic',
                'vital_value': bp[0],
                'unit': 'mmHg',
                'recorded_at': timestamp
            })
            data['vitals'].append({
                'vital_type': 'bp_diastolic',
                'vital_value': bp[1],
                'unit': 'mmHg',
                'recorded_at': timestamp
            })

        hr = extract_heart_rate(content)
        if hr:
            data['vitals'].append({
                'vital_type': 'heart_rate',
                'vital_value': hr,
                'unit': 'bpm',
                'recorded_at': timestamp
            })

        sleep = extract_sleep_hours(content)
        if sleep:
            data['vitals'].append({
                'vital_type': 'sleep_hours',
                'vital_value': sleep,
                'unit': 'hours',
                'recorded_at': timestamp
            })

        pain = extract_pain_level(content)
        if pain:
            data['vitals'].append({
                'vital_type': 'pain_level',
                'vital_value': pain,
                'unit': 'scale',
                'recorded_at': timestamp
            })

        # Medications
        meds = extract_medications_taken(content)
        if meds is not None:
            data['medications_taken'] = meds
            data['call_summary']['medication_adherence'] = meds

    # Generate summary from conversation
    user_messages = [m['content'] for m in messages if m['role'] == 'user']
    assistant_messages = [m['content'] for m in messages if m['role'] == 'assistant']

    summary_parts = []
    if data['vitals']:
        summary_parts.append(f"Collected {len(data['vitals'])} vital signs")
    if data['medications_taken'] is not None:
        summary_parts.append("Medications: " + ("Taken" if data['medications_taken'] else "Missed"))
    summary_parts.append(f"Conversation had {len(user_messages)} exchanges")

    data['call_summary']['summary_text'] = ". ".join(summary_parts) if summary_parts else "Brief check-in"

    return data

# Main migration
print("📊 Fetching conversations from Cosmos DB...\n")
query = "SELECT * FROM c ORDER BY c.createdAt DESC"
sessions = list(cosmos_container.query_items(query=query, enable_cross_partition_query=True))
print(f"Found {len(sessions)} total conversations\n")

stats = {
    'sessions_processed': 0,
    'vitals_inserted': 0,
    'cognitive_assessments_inserted': 0,
    'call_summaries_inserted': 0,
    'medication_logs_inserted': 0,
    'duplicates_skipped': 0,
}

for i, session in enumerate(sessions, 1):
    try:
        session_id = session['sessionId']

        # Check if already migrated (avoid duplicates)
        pg_cursor.execute("SELECT 1 FROM call_summary WHERE session_id = %s LIMIT 1", (session_id,))
        if pg_cursor.fetchone():
            stats['duplicates_skipped'] += 1
            continue

        print(f"[{i}/{len(sessions)}] Processing session {session_id[:8]}...")

        data = parse_conversation(session)

        # Insert vitals
        if data['vitals']:
            vitals_data = [
                (
                    data['senior_id'],
                    v['recorded_at'],
                    v['vital_type'],
                    v['vital_value'],
                    v['unit'],
                    'call',
                    session_id
                )
                for v in data['vitals']
            ]
            execute_values(
                pg_cursor,
                "INSERT INTO senior_vitals (senior_id, recorded_at, vital_type, vital_value, unit, source, session_id) VALUES %s",
                vitals_data
            )
            stats['vitals_inserted'] += len(vitals_data)

        # Insert cognitive assessment
        cog = data['cognitive']
        if cog['overall_score']:
            pg_cursor.execute("""
                INSERT INTO cognitive_assessments
                (senior_id, assessment_date, memory_score, orientation_score, language_score,
                 executive_function_score, overall_score, session_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                data['senior_id'],
                data['call_date'],
                cog['memory_score'],
                cog['orientation_score'],
                cog['language_score'],
                cog['executive_function_score'],
                cog['overall_score'],
                session_id
            ))
            stats['cognitive_assessments_inserted'] += 1

        # Insert call summary
        summary = data['call_summary']
        pg_cursor.execute("""
            INSERT INTO call_summary
            (senior_id, call_date, session_id, call_duration, call_completed,
             medication_adherence, summary_text)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            data['senior_id'],
            data['call_date'],
            session_id,
            summary['call_duration'],
            summary['call_completed'],
            summary['medication_adherence'],
            summary['summary_text']
        ))
        stats['call_summaries_inserted'] += 1

        # Insert medication log
        if data['medications_taken'] is not None:
            pg_cursor.execute("""
                INSERT INTO medication_adherence
                (senior_id, log_date, medications_taken, session_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (senior_id, log_date) DO UPDATE
                SET medications_taken = EXCLUDED.medications_taken
            """, (
                data['senior_id'],
                data['call_date'].date(),
                data['medications_taken'],
                session_id
            ))
            stats['medication_logs_inserted'] += 1

        stats['sessions_processed'] += 1
        pg_conn.commit()

    except Exception as e:
        print(f"  ❌ Error processing session: {e}")
        pg_conn.rollback()
        continue

print("\n" + "="*60)
print("✅ MIGRATION COMPLETE!")
print("="*60)
print(f"Sessions processed: {stats['sessions_processed']}")
print(f"Duplicates skipped: {stats['duplicates_skipped']}")
print(f"Vitals inserted: {stats['vitals_inserted']}")
print(f"Cognitive assessments: {stats['cognitive_assessments_inserted']}")
print(f"Call summaries: {stats['call_summaries_inserted']}")
print(f"Medication logs: {stats['medication_logs_inserted']}")
print("="*60)

pg_cursor.close()
pg_conn.close()
