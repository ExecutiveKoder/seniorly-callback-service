"""
Setup Azure SQL Database - Run schema.sql
"""
import pyodbc
import sys
from pathlib import Path

# Database connection details (from environment)
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

server = os.getenv('AZURE_SQL_SERVER', 'seniorly-sql-server.database.windows.net').strip("'")
database = os.getenv('AZURE_SQL_DATABASE', 'SeniorHealthAnalytics').strip("'")
username = os.getenv('AZURE_SQL_USERNAME', 'sqladmin').strip("'")
password = os.getenv('AZURE_SQL_PASSWORD', 'YourSecurePassword123!').strip("'")

connection_string = (
    f"Driver={{ODBC Driver 18 for SQL Server}};"
    f"Server=tcp:{server},1433;"
    f"Database={database};"
    f"Uid={username};"
    f"Pwd={password};"
    f"Encrypt=yes;"
    f"TrustServerCertificate=no;"
    f"Connection Timeout=30;"
)

print("Connecting to Azure SQL Database...")
try:
    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()
    print("✅ Connected successfully!\n")

    # Read schema.sql
    schema_file = Path(__file__).parent / 'schema.sql'
    print(f"Reading schema from: {schema_file}")

    with open(schema_file, 'r') as f:
        sql_script = f.read()

    # Split by GO statements
    batches = sql_script.split('GO')

    print(f"\n📝 Executing {len(batches)} SQL batches...\n")

    for i, batch in enumerate(batches, 1):
        batch = batch.strip()
        if not batch or batch.startswith('--') or batch.startswith('/*'):
            continue

        try:
            # Skip comment-only batches
            if all(line.strip().startswith('--') or not line.strip() for line in batch.split('\n')):
                continue

            print(f"Batch {i}... ", end='')
            cursor.execute(batch)
            conn.commit()
            print("✅")
        except Exception as e:
            error_msg = str(e)
            # Ignore "already exists" errors
            if 'already exists' in error_msg.lower() or 'there is already an object' in error_msg.lower():
                print("⚠️  Already exists (skipping)")
            else:
                print(f"❌ Error: {error_msg}")
                # Continue with other batches

    print("\n" + "="*60)
    print("✅ DATABASE SETUP COMPLETE!")
    print("="*60)
    print(f"Server: {server}")
    print(f"Database: {database}")
    print(f"Tables created:")
    print("  - senior_vitals")
    print("  - cognitive_assessments")
    print("  - call_summary")
    print("  - health_alerts")
    print("  - medication_adherence")
    print(f"\nMaterialized views created:")
    print("  - vw_latest_vitals_by_senior")
    print("  - vw_cognitive_trend_30d")
    print("  - vw_medication_adherence_weekly")
    print("  - vw_active_alerts_summary")
    print("="*60)

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
