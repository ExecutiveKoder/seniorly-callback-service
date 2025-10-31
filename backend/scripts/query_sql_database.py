#!/usr/bin/env python3
"""
Quick script to query Azure SQL Database
Shows what data is being captured
"""
import pyodbc
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config, get_secret

# Get connection details
server = config.AZURE_SQL_SERVER
database = config.AZURE_SQL_DATABASE
username = config.AZURE_SQL_USERNAME
password = get_secret('AzureSQLPassword', 'AZURE_SQL_PASSWORD')

connection_string = (
    f"Driver={{ODBC Driver 18 for SQL Server}};"
    f"Server=tcp:{server},1433;"
    f"Database={database};"
    f"Uid={username};"
    f"Pwd={password};"
    f"Encrypt=yes;"
    f"TrustServerCertificate=no;"
)

print("🔌 Connecting to Azure SQL Database...")
print(f"   Server: {server}")
print(f"   Database: {database}\n")

try:
    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()
    print("✅ Connected!\n")

    # Show all tables
    print("=" * 80)
    print("📊 TABLES IN DATABASE")
    print("=" * 80)
    cursor.execute("""
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
    """)
    tables = cursor.fetchall()
    for table in tables:
        print(f"  • {table[0]}")
    print()

    # Count records in each table
    print("=" * 80)
    print("📈 RECORD COUNTS")
    print("=" * 80)
    for table in tables:
        table_name = table[0]
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name}: {count} records")
        except Exception as e:
            print(f"  {table_name}: Error - {e}")
    print()

    # Show recent vitals
    print("=" * 80)
    print("🩺 RECENT VITALS (Last 10 records)")
    print("=" * 80)
    cursor.execute("""
        SELECT TOP 10
            senior_id,
            blood_pressure,
            heart_rate,
            weight,
            recorded_at
        FROM senior_vitals
        ORDER BY recorded_at DESC
    """)
    vitals = cursor.fetchall()
    if vitals:
        print(f"{'Senior ID':<40} {'BP':<15} {'HR':<10} {'Weight':<10} {'Date'}")
        print("-" * 80)
        for v in vitals:
            print(f"{v[0]:<40} {v[1] or 'N/A':<15} {str(v[2]) or 'N/A':<10} {str(v[3]) or 'N/A':<10} {v[4]}")
    else:
        print("  No vitals recorded yet")
    print()

    # Show recent cognitive assessments
    print("=" * 80)
    print("🧠 RECENT COGNITIVE ASSESSMENTS (Last 10)")
    print("=" * 80)
    cursor.execute("""
        SELECT TOP 10
            senior_id,
            assessment_type,
            score,
            notes,
            assessed_at
        FROM cognitive_assessments
        ORDER BY assessed_at DESC
    """)
    assessments = cursor.fetchall()
    if assessments:
        for a in assessments:
            print(f"  Senior: {a[0][:8]}...")
            print(f"  Type: {a[1]}")
            print(f"  Score: {a[2]}")
            print(f"  Notes: {a[3] or 'N/A'}")
            print(f"  Date: {a[4]}")
            print()
    else:
        print("  No assessments recorded yet")
    print()

    # Show recent call summaries
    print("=" * 80)
    print("📞 RECENT CALL SUMMARIES (Last 5)")
    print("=" * 80)
    cursor.execute("""
        SELECT TOP 5
            senior_id,
            call_duration_seconds,
            mood,
            health_concerns,
            call_date
        FROM call_summary
        ORDER BY call_date DESC
    """)
    calls = cursor.fetchall()
    if calls:
        for c in calls:
            print(f"  Senior: {c[0][:8]}...")
            print(f"  Duration: {c[1]} seconds")
            print(f"  Mood: {c[2] or 'N/A'}")
            print(f"  Concerns: {c[3] or 'None'}")
            print(f"  Date: {c[4]}")
            print()
    else:
        print("  No call summaries yet")

    cursor.close()
    conn.close()
    print("=" * 80)
    print("✅ Query complete!")

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
