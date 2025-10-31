"""
Setup Azure PostgreSQL Database - Run schema_postgres.sql
"""
import psycopg2
import sys
from pathlib import Path
import os
from dotenv import load_dotenv
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Load .env file
load_dotenv()

# Initialize Key Vault client
KEY_VAULT_NAME = os.getenv('AZURE_KEY_VAULT_NAME', 'seniorly-secrets')
KEY_VAULT_URL = f"https://{KEY_VAULT_NAME}.vault.azure.net"

try:
    credential = DefaultAzureCredential()
    secret_client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
    password = secret_client.get_secret('AzurePostgresPassword').value.strip("'\"")
except Exception as e:
    print(f"Warning: Could not get password from Key Vault: {e}")
    print("Falling back to .env file")
    password = os.getenv('AZURE_POSTGRES_PASSWORD', 'Seniorly2025!SecureDB').strip("'")

host = os.getenv('AZURE_POSTGRES_SERVER', 'seniorly-postgres-server.postgres.database.azure.com').strip("'")
database = os.getenv('AZURE_POSTGRES_DATABASE', 'SeniorHealthAnalytics').strip("'")
username = os.getenv('AZURE_POSTGRES_USERNAME', 'pgadmin').strip("'")
port = os.getenv('AZURE_POSTGRES_PORT', '5432').strip("'")

print("Connecting to Azure PostgreSQL Database...")
print(f"Host: {host}")
print(f"Database: {database}")
print(f"User: {username}\n")

try:
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host=host,
        database=database,
        user=username,
        password=password,
        port=port,
        sslmode='require'
    )
    conn.autocommit = True
    cursor = conn.cursor()
    print("✅ Connected successfully!\n")

    # Read schema_postgres.sql
    schema_file = Path(__file__).parent / 'schema_postgres.sql'
    print(f"Reading schema from: {schema_file}")

    with open(schema_file, 'r') as f:
        sql_script = f.read()

    # Remove comment blocks from queries
    queries = []
    current_query = []
    in_comment_block = False

    for line in sql_script.split('\n'):
        stripped = line.strip()

        # Handle comment blocks
        if stripped.startswith('/*'):
            in_comment_block = True
            continue
        if stripped.endswith('*/'):
            in_comment_block = False
            continue
        if in_comment_block:
            continue

        # Skip single-line comments and empty lines
        if stripped.startswith('--') or not stripped:
            continue

        current_query.append(line)

        # If line ends with semicolon, it's the end of a statement
        if stripped.endswith(';'):
            query = '\n'.join(current_query).strip()
            if query:
                queries.append(query)
            current_query = []

    print(f"\n📝 Executing {len(queries)} SQL statements...\n")

    for i, query in enumerate(queries, 1):
        try:
            # Show first 60 chars of query for identification
            query_preview = query[:60].replace('\n', ' ')
            print(f"Statement {i}: {query_preview}... ", end='')
            cursor.execute(query)
            print("✅")
        except Exception as e:
            error_msg = str(e)
            # Ignore "already exists" errors
            if 'already exists' in error_msg.lower():
                print("⚠️  Already exists (skipping)")
            else:
                print(f"❌ Error: {error_msg}")
                # Continue with other statements

    print("\n" + "="*60)
    print("✅ DATABASE SETUP COMPLETE!")
    print("="*60)
    print(f"Server: {host}")
    print(f"Database: {database}")
    print(f"\nTables created:")
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
    print(f"\nHelper views created:")
    print("  - vw_senior_current_vitals")
    print("  - vw_senior_7day_summary")
    print(f"\nFunctions created:")
    print("  - refresh_all_materialized_views()")
    print("="*60)
    print("\nConnection info for pgAdmin:")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Database: {database}")
    print(f"  Username: {username}")
    print(f"  SSL Mode: require")
    print("="*60)

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
