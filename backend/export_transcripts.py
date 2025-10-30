"""
Export conversation transcripts from Cosmos DB for training and review

Usage:
    python export_transcripts.py                     # Export all transcripts
    python export_transcripts.py --session <id>      # Export single session
    python export_transcripts.py --senior <id>       # Export all for a senior
    python export_transcripts.py --days 7            # Export last 7 days
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.config import config
from src.services.data_service import CosmosDBService

def export_single_transcript(cosmos: CosmosDBService, session_id: str, output_dir: Path):
    """Export a single session transcript"""
    print(f"Exporting session: {session_id}")

    transcript = cosmos.get_conversation_transcript(session_id)
    if not transcript:
        print(f"  ❌ Session not found: {session_id}")
        return False

    # Save to file
    output_file = output_dir / f"{session_id}.txt"
    with open(output_file, 'w') as f:
        f.write(transcript)

    print(f"  ✅ Saved: {output_file}")
    return True

def export_all_transcripts(cosmos: CosmosDBService, output_dir: Path, days: Optional[int] = None):
    """Export all session transcripts"""
    print(f"Querying all sessions from Cosmos DB...")

    # Query all sessions
    query = "SELECT * FROM c"
    if days:
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        query = f"SELECT * FROM c WHERE c.createdAt >= '{cutoff_date}'"

    try:
        sessions = list(cosmos.container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        print(f"Found {len(sessions)} sessions")

        exported = 0
        for session in sessions:
            session_id = session.get('id')
            if session_id:
                if export_single_transcript(cosmos, session_id, output_dir):
                    exported += 1

        print(f"\n✅ Exported {exported}/{len(sessions)} transcripts")

    except Exception as e:
        print(f"❌ Error querying sessions: {e}")

def export_by_senior(cosmos: CosmosDBService, senior_id: str, output_dir: Path):
    """Export all transcripts for a specific senior"""
    print(f"Querying sessions for senior: {senior_id}")

    query = f"SELECT * FROM c WHERE c.metadata.senior_id = '{senior_id}'"

    try:
        sessions = list(cosmos.container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        print(f"Found {len(sessions)} sessions for senior {senior_id}")

        # Create senior-specific subdirectory
        senior_dir = output_dir / f"senior_{senior_id[:8]}"
        senior_dir.mkdir(exist_ok=True)

        exported = 0
        for session in sessions:
            session_id = session.get('id')
            if session_id:
                if export_single_transcript(cosmos, session_id, senior_dir):
                    exported += 1

        print(f"\n✅ Exported {exported}/{len(sessions)} transcripts to {senior_dir}")

    except Exception as e:
        print(f"❌ Error querying sessions: {e}")

def export_as_jsonl(cosmos: CosmosDBService, output_file: Path, days: Optional[int] = None):
    """Export conversations in JSONL format for ML training"""
    print(f"Exporting conversations in JSONL format for training...")

    query = "SELECT * FROM c"
    if days:
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        query = f"SELECT * FROM c WHERE c.createdAt >= '{cutoff_date}'"

    try:
        sessions = list(cosmos.container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))

        print(f"Found {len(sessions)} sessions")

        with open(output_file, 'w') as f:
            for session in sessions:
                messages = session.get('messages', [])
                if not messages:
                    continue

                # Format for training: {"messages": [{"role": "...", "content": "..."}]}
                training_data = {
                    "session_id": session.get('id'),
                    "created_at": session.get('createdAt'),
                    "metadata": session.get('metadata', {}),
                    "messages": [
                        {"role": msg["role"], "content": msg["content"]}
                        for msg in messages
                    ]
                }

                f.write(json.dumps(training_data) + '\n')

        print(f"\n✅ Exported {len(sessions)} conversations to {output_file}")
        print(f"   Format: JSONL (one JSON object per line)")

    except Exception as e:
        print(f"❌ Error exporting JSONL: {e}")

def main():
    """Main export function"""
    print("\n" + "="*60)
    print("📄 CONVERSATION TRANSCRIPT EXPORTER")
    print("="*60 + "\n")

    # Validate configuration
    if not config.validate():
        print("❌ Configuration validation failed. Check your .env file.")
        sys.exit(1)

    # Initialize Cosmos DB service
    cosmos = CosmosDBService(
        endpoint=config.AZURE_COSMOS_ENDPOINT,
        key=config.AZURE_COSMOS_KEY,
        database_name=config.COSMOS_DATABASE,
        container_name=config.COSMOS_CONTAINER
    )

    # Create output directory
    output_dir = Path(__file__).parent / "exports" / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}\n")

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Export conversation transcripts')
    parser.add_argument('--session', type=str, help='Export single session by ID')
    parser.add_argument('--senior', type=str, help='Export all sessions for a senior ID')
    parser.add_argument('--days', type=int, help='Export sessions from last N days')
    parser.add_argument('--jsonl', action='store_true', help='Export as JSONL for ML training')
    args = parser.parse_args()

    # Execute appropriate export
    if args.session:
        export_single_transcript(cosmos, args.session, output_dir)
    elif args.senior:
        export_by_senior(cosmos, args.senior, output_dir)
    elif args.jsonl:
        jsonl_file = output_dir / "training_data.jsonl"
        export_as_jsonl(cosmos, jsonl_file, args.days)
    else:
        # Export all
        export_all_transcripts(cosmos, output_dir, args.days)

        # Also create JSONL version
        jsonl_file = output_dir / "training_data.jsonl"
        export_as_jsonl(cosmos, jsonl_file, args.days)

    print(f"\n" + "="*60)
    print(f"✅ EXPORT COMPLETE")
    print(f"   Location: {output_dir}")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
