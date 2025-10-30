# Azure SQL Database Setup for Analytics

This directory contains the schema and setup instructions for the Azure SQL analytics database.

## 📊 Purpose

The Azure SQL database stores extracted health metrics, cognitive assessments, and wellness data for:
- Dashboard visualizations
- Trend analysis
- Health alerts
- Caregiver insights

**Separate from operational data:**
- Cosmos DB = Operational (conversations, sessions)
- Azure SQL = Analytics (metrics, trends, dashboards)

---

## 🚀 Setup Instructions

### Step 1: Create Azure SQL Database

```bash
# Login to Azure
az login

# Create Azure SQL Server
az sql server create \
  --name seniorly-sql-server \
  --resource-group voice-agent-rg \
  --location eastus2 \
  --admin-user sqladmin \
  --admin-password 'YourSecurePassword123!'

# Create Database (Basic tier for testing)
az sql db create \
  --resource-group voice-agent-rg \
  --server seniorly-sql-server \
  --name SeniorHealthAnalytics \
  --service-objective Basic \
  --backup-storage-redundancy Local
```

**Cost:** Basic tier = ~$5/month

### Step 2: Configure Firewall

```bash
# Allow Azure services
az sql server firewall-rule create \
  --resource-group voice-agent-rg \
  --server seniorly-sql-server \
  --name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# Allow your local IP for development
az sql server firewall-rule create \
  --resource-group voice-agent-rg \
  --server seniorly-sql-server \
  --name AllowLocalDev \
  --start-ip-address YOUR_IP_ADDRESS \
  --end-ip-address YOUR_IP_ADDRESS
```

### Step 3: Run Schema Creation

```bash
# Using Azure Data Studio, SQL Server Management Studio, or sqlcmd
sqlcmd -S seniorly-sql-server.database.windows.net \
  -d SeniorHealthAnalytics \
  -U sqladmin \
  -P 'YourSecurePassword123!' \
  -i schema.sql
```

**Or use Azure Portal:**
1. Go to Azure Portal → SQL databases → SeniorHealthAnalytics
2. Click "Query editor"
3. Login with sqladmin credentials
4. Paste contents of `schema.sql`
5. Click "Run"

### Step 4: Update .env File

Add these variables to your `.env` file:

```bash
# Azure SQL Database (Analytics)
AZURE_SQL_SERVER='seniorly-sql-server.database.windows.net'
AZURE_SQL_DATABASE='SeniorHealthAnalytics'
AZURE_SQL_USERNAME='sqladmin'
AZURE_SQL_PASSWORD='YourSecurePassword123!'
```

### Step 5: Install Python ODBC Driver

**Mac:**
```bash
brew install unixodbc
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
brew install msodbcsql18 mssql-tools18
```

**Ubuntu/Linux:**
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

**Windows:**
Download from: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

### Step 6: Install Python Dependencies

```bash
pip install pyodbc
```

---

## 📁 Database Schema

### Tables

1. **senior_vitals** - Health measurements (BP, heart rate, weight, etc.)
2. **cognitive_assessments** - Cognitive health scores over time
3. **call_summary** - Overview of each daily call
4. **health_alerts** - Alerts for concerning patterns
5. **medication_adherence** - Medication taking patterns

### Materialized Views (for fast queries)

1. **vw_latest_vitals_by_senior** - Current vitals for each senior
2. **vw_cognitive_trend_30d** - 30-day cognitive trend
3. **vw_medication_adherence_weekly** - Weekly adherence rates
4. **vw_active_alerts_summary** - Unresolved alerts by senior

---

## 🔍 Sample Queries

### Get current vitals for a senior
```sql
SELECT * FROM vw_senior_current_vitals
WHERE senior_id = 'e6077e0e-334c-498d';
```

### Get blood pressure trend (last 30 days)
```sql
SELECT
    CAST(recorded_at AS DATE) as date,
    AVG(CASE WHEN vital_type = 'bp_systolic' THEN vital_value END) as systolic,
    AVG(CASE WHEN vital_type = 'bp_diastolic' THEN vital_value END) as diastolic
FROM senior_vitals
WHERE senior_id = 'e6077e0e-334c-498d'
    AND vital_type IN ('bp_systolic', 'bp_diastolic')
    AND recorded_at >= DATEADD(day, -30, GETDATE())
GROUP BY CAST(recorded_at AS DATE)
ORDER BY date DESC;
```

### Get cognitive decline alert
```sql
SELECT
    assessment_date,
    avg_score,
    LAG(avg_score, 1) OVER (ORDER BY assessment_date) as previous_score
FROM vw_cognitive_trend_30d
WHERE senior_id = 'e6077e0e-334c-498d'
    AND avg_score < LAG(avg_score, 1) OVER (ORDER BY assessment_date) - 10
ORDER BY assessment_date DESC;
```

### Get active alerts
```sql
SELECT * FROM vw_active_alerts_summary
WHERE senior_id = 'e6077e0e-334c-498d'
ORDER BY
    CASE severity
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        ELSE 4
    END;
```

---

## 🔗 Integration with Next.js Dashboard

The analytics service automatically extracts metrics from each call and saves to Azure SQL.

**Data Flow:**
```
Voice Call Ends
    ↓
Generate AI Summary
    ↓
Extract Metrics (vitals, cognitive, alerts)
    ↓
Save to Azure SQL
    ↓
Next.js Dashboard queries SQL for charts/tables
```

**Next.js connection example:**
```typescript
// lib/db.ts
import { Connection } from 'tedious';

const config = {
  server: process.env.AZURE_SQL_SERVER!,
  authentication: {
    type: 'default',
    options: {
      userName: process.env.AZURE_SQL_USERNAME!,
      password: process.env.AZURE_SQL_PASSWORD!
    }
  },
  options: {
    database: process.env.AZURE_SQL_DATABASE!,
    encrypt: true
  }
};

export async function querySeniorVitals(seniorId: string) {
  // Query implementation
}
```

---

## 🔒 Security Best Practices

1. **Use Managed Identity** (recommended for production)
2. **Rotate passwords** regularly
3. **Restrict firewall rules** to specific IPs
4. **Enable auditing** for compliance
5. **Use read-only connections** for dashboards

---

## 📈 Performance Tips

1. **Materialized views** are already indexed - use them!
2. **Partition tables** if you have >10M rows
3. **Archive old data** (>1 year) to separate table
4. **Use connection pooling** in Python/Next.js
5. **Consider upgrading tier** if queries are slow

---

## 🧪 Testing

Test the analytics extraction:

```python
from src.services.analytics_service import AnalyticsService

analytics = AnalyticsService()

# Test with sample data
success = analytics.extract_and_save_metrics(
    senior_id='e6077e0e-334c-498d',
    session_id='test-session-123',
    call_summary='Senior reported blood pressure 120/80...',
    conversation_history=[
        {'role': 'assistant', 'content': 'How are you feeling?'},
        {'role': 'user', 'content': 'My blood pressure is 120 over 80'}
    ],
    call_duration=300,
    call_completed=True
)

print(f"Metrics saved: {success}")
```

---

## 🐛 Troubleshooting

**"Login failed for user"**
- Check username/password in .env
- Verify firewall rules allow your IP

**"ODBC Driver not found"**
- Install ODBC Driver 18 (see Step 5)
- Check driver name in connection string

**"Table does not exist"**
- Run schema.sql first (Step 3)
- Check database name in connection

**"Slow queries"**
- Use materialized views instead of raw tables
- Add indexes to frequently queried columns
- Consider upgrading database tier

---

## 📚 Additional Resources

- [Azure SQL Documentation](https://learn.microsoft.com/en-us/azure/azure-sql/)
- [pyodbc Documentation](https://github.com/mkleehammer/pyodbc/wiki)
- [SQL Server Performance Tuning](https://learn.microsoft.com/en-us/sql/relational-databases/performance/performance-center-for-sql-server-database-engine)
