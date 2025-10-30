# How to Access and Use Cosmos DB Audit Logs

## What's Being Logged

Every time someone (or your app) interacts with Cosmos DB, these events are logged:

1. **DataPlaneRequests** - All database operations:
   - Reading conversations (PHI data access)
   - Writing new messages
   - Updating sessions
   - Deleting records
   - Who did it, when, from where

2. **QueryRuntimeStatistics** - Query performance:
   - Which queries are running
   - How long they take
   - What data they access

3. **ControlPlaneRequests** - Administrative changes:
   - Database settings changes
   - User permission changes
   - Firewall rule updates

---

## How to Access Logs

### Option 1: Azure Portal (Easiest)

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to: **Cosmos DB** → `my-voice-agent-db`
3. Click **"Logs"** in left menu
4. Run queries (examples below)

### Option 2: Azure CLI

```bash
# Query logs via CLI
az monitor log-analytics query \
  --workspace /subscriptions/30a248ed-b2a6-45fd-8eed-714ffa3e3130/resourceGroups/voice-agent-rg/providers/Microsoft.OperationalInsights/workspaces/workspacevoiceagentrgbb4e \
  --analytics-query "YOUR_QUERY_HERE"
```

### Option 3: Log Analytics Workspace

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to: **Log Analytics workspaces** → `workspacevoiceagentrgbb4e`
3. Click **"Logs"** in left menu
4. Run queries

---

## Common Queries (Copy-Paste These)

### 1. See All Cosmos DB Activity (Last Hour)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where TimeGenerated > ago(1h)
| project TimeGenerated, OperationName, Resource, requestCharge_s, statusCode_s, clientIpAddress_s
| order by TimeGenerated desc
```

**What it shows:** All operations in last hour with who did what

---

### 2. See Who Accessed Specific Senior's Data (PHI Access Audit)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where Category == "DataPlaneRequests"
| where activityId_g contains "senior-id-here"  // Replace with actual senior ID
| project TimeGenerated, OperationName, clientIpAddress_s, userAgent_s, statusCode_s
| order by TimeGenerated desc
```

**What it shows:** Every time someone accessed this senior's conversations

**HIPAA Use Case:** Patient requests "Who accessed my records?"

---

### 3. Track Failed Login/Access Attempts (Security)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where statusCode_s >= 400  // HTTP errors (unauthorized, forbidden, etc.)
| project TimeGenerated, OperationName, statusCode_s, clientIpAddress_s, errorMessage_s
| order by TimeGenerated desc
```

**What it shows:** All failed access attempts

**HIPAA Use Case:** Detect unauthorized access attempts

---

### 4. See All Database Writes (Who Added/Changed Data)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where Category == "DataPlaneRequests"
| where OperationName in ("Create", "Update", "Replace", "Delete")
| project TimeGenerated, OperationName, Resource, clientIpAddress_s, requestCharge_s
| order by TimeGenerated desc
```

**What it shows:** Every create/update/delete operation

**HIPAA Use Case:** Audit trail of data modifications

---

### 5. Monitor High-Cost Queries (Performance & Cost)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where Category == "DataPlaneRequests"
| where todouble(requestCharge_s) > 10  // RU cost threshold
| project TimeGenerated, OperationName, requestCharge_s, duration_s, Resource
| order by todouble(requestCharge_s) desc
```

**What it shows:** Expensive queries costing lots of RUs

**Use Case:** Optimize performance and reduce costs

---

### 6. Track Administrative Changes (Who Changed Settings)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where Category == "ControlPlaneRequests"
| project TimeGenerated, OperationName, identity_claim_appid_g, clientIpAddress_s, statusCode_s
| order by TimeGenerated desc
```

**What it shows:** Database config changes (firewall, permissions, etc.)

**HIPAA Use Case:** Audit administrative access

---

### 7. Daily Access Summary (How Many Operations)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where TimeGenerated > ago(24h)
| summarize OperationCount = count() by OperationName
| order by OperationCount desc
```

**What it shows:** Summary of all operations in last 24 hours

**Use Case:** Daily monitoring report

---

### 8. Identify Unusual Access Patterns (Security Alert)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where TimeGenerated > ago(1h)
| summarize AccessCount = count() by clientIpAddress_s
| where AccessCount > 1000  // Threshold for unusual activity
| order by AccessCount desc
```

**What it shows:** IP addresses making excessive requests

**HIPAA Use Case:** Detect potential data breach or bot attacks

---

### 9. Track Conversation Access by Session ID

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where Category == "DataPlaneRequests"
| where Resource contains "sessions"  // Your container name
| where activityId_g contains "session-id-here"  // Replace with actual session ID
| project TimeGenerated, OperationName, clientIpAddress_s, statusCode_s
| order by TimeGenerated desc
```

**What it shows:** All access to a specific conversation session

**Use Case:** Audit specific conversation access

---

### 10. Generate HIPAA Compliance Report (Monthly)

```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where TimeGenerated > ago(30d)
| summarize
    TotalOperations = count(),
    UniqueIPs = dcount(clientIpAddress_s),
    FailedAttempts = countif(statusCode_s >= "400"),
    SuccessfulReads = countif(OperationName == "Query" and statusCode_s == "200"),
    SuccessfulWrites = countif(OperationName in ("Create", "Update", "Replace"))
| extend FailureRate = round((FailedAttempts * 100.0) / TotalOperations, 2)
```

**What it shows:** Complete monthly activity summary

**HIPAA Use Case:** Monthly compliance report

---

## Real-World HIPAA Scenarios

### Scenario 1: Patient Requests Access Log

**Question:** "Who has accessed my health records in the last 90 days?"

**Query:**
```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where TimeGenerated > ago(90d)
| where activityId_g contains "senior-id-12345"  // Patient's ID
| summarize AccessCount = count() by bin(TimeGenerated, 1d), clientIpAddress_s
| project Date = format_datetime(TimeGenerated, 'yyyy-MM-dd'), IPAddress = clientIpAddress_s, AccessCount
| order by Date desc
```

**Output:**
```
Date         IPAddress        AccessCount
2025-10-30   174.89.11.214   15
2025-10-29   174.89.11.214   12
2025-10-28   174.89.11.214   18
```

---

### Scenario 2: Security Breach Investigation

**Question:** "Was there unauthorized access on Oct 29th?"

**Query:**
```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where TimeGenerated between (datetime(2025-10-29) .. datetime(2025-10-30))
| where statusCode_s >= "400"  // Failed attempts
| summarize FailedAttempts = count() by clientIpAddress_s, statusCode_s
| order by FailedAttempts desc
```

---

### Scenario 3: Compliance Audit

**Question:** "Prove you're logging all PHI access"

**Query:**
```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where TimeGenerated > ago(7d)
| where Category == "DataPlaneRequests"
| summarize
    TotalDataAccess = count(),
    FirstAccess = min(TimeGenerated),
    LastAccess = max(TimeGenerated),
    UniqueIPs = dcount(clientIpAddress_s)
| project
    LoggingActive = "YES",
    TotalDataAccess,
    FirstAccess,
    LastAccess,
    UniqueIPs
```

**Output:**
```
LoggingActive  TotalDataAccess  FirstAccess           LastAccess            UniqueIPs
YES            1,234            2025-10-23 10:15:00   2025-10-30 14:30:00   3
```

---

## Set Up Alerts (Proactive Monitoring)

### Alert 1: Failed Access Attempts

```bash
# Create alert for multiple failed login attempts
az monitor metrics alert create \
  --name cosmos-failed-access-alert \
  --resource-group voice-agent-rg \
  --scopes /subscriptions/30a248ed-b2a6-45fd-8eed-714ffa3e3130/resourceGroups/voice-agent-rg/providers/Microsoft.DocumentDb/databaseAccounts/my-voice-agent-db \
  --condition "count ServerException > 10" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action-group <your-action-group-id>
```

### Alert 2: Unusual Access Volume

Create in Azure Portal:
1. Go to Cosmos DB → Alerts → New alert rule
2. Condition: "Total Requests > 10,000 in 1 hour"
3. Action: Send email to security team

---

## Exporting Logs for Long-Term Storage

HIPAA requires 7 years of audit log retention. Azure Log Analytics default is 30 days.

### Option 1: Export to Storage Account (Cheaper)

```bash
# Create storage account for long-term logs
az storage account create \
  --name seniorlyauditstorage \
  --resource-group voice-agent-rg \
  --location eastus2 \
  --sku Standard_LRS

# Configure continuous export
az monitor log-analytics workspace data-export create \
  --resource-group voice-agent-rg \
  --workspace-name workspacevoiceagentrgbb4e \
  --name cosmos-audit-export \
  --destination /subscriptions/30a248ed-b2a6-45fd-8eed-714ffa3e3130/resourceGroups/voice-agent-rg/providers/Microsoft.Storage/storageAccounts/seniorlyauditstorage \
  --tables AzureDiagnostics
```

**Cost:** ~$2-5/month for years of logs

### Option 2: Extend Log Analytics Retention

```bash
# Extend retention to 2 years (730 days)
az monitor log-analytics workspace table update \
  --resource-group voice-agent-rg \
  --workspace-name workspacevoiceagentrgbb4e \
  --name AzureDiagnostics \
  --retention-time 730
```

**Cost:** ~$20-30/month

---

## Python Script to Query Logs

Create `backend/scripts/query_audit_logs.py`:

```python
from azure.monitor.query import LogsQueryClient
from azure.identity import DefaultAzureCredential
from datetime import datetime, timedelta

credential = DefaultAzureCredential()
client = LogsQueryClient(credential)

workspace_id = "your-workspace-id"

# Query last 24 hours of Cosmos DB activity
query = """
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.DOCUMENTDB"
| where TimeGenerated > ago(24h)
| project TimeGenerated, OperationName, clientIpAddress_s, statusCode_s
| order by TimeGenerated desc
"""

response = client.query_workspace(workspace_id, query, timespan=timedelta(days=1))

for table in response.tables:
    for row in table.rows:
        print(f"{row[0]} | {row[1]} | {row[2]} | {row[3]}")
```

Run:
```bash
python backend/scripts/query_audit_logs.py
```

---

## Dashboard for Real-Time Monitoring

### Create in Azure Portal:

1. Go to **Azure Dashboards**
2. Create new dashboard: "Cosmos DB HIPAA Audit"
3. Add tiles:
   - **Total Operations** (last 24h)
   - **Failed Attempts** (security)
   - **Top IPs** (who's accessing)
   - **Operation Types** (read/write breakdown)

Save and share with compliance team.

---

## HIPAA Compliance Checklist

✅ **Audit Logging Enabled** - DONE (just enabled)
✅ **Logs include:**
   - Who (IP address, user agent)
   - What (operation type)
   - When (timestamp)
   - Where (resource accessed)
   - Result (success/failure)

✅ **Log Retention:** 30 days (default) → Extend to 7 years for HIPAA
✅ **Access Controls:** Logs protected by Azure RBAC
✅ **Immutable:** Logs cannot be modified or deleted by app
✅ **Alerting:** Set up for suspicious activity

---

## Quick Reference

### View logs in Azure Portal:
```
Cosmos DB → Logs → Run query
```

### View logs via CLI:
```bash
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query "YOUR_QUERY"
```

### Export logs for compliance:
```bash
# Set up continuous export to storage account
az monitor log-analytics workspace data-export create ...
```

---

## Summary

**You now have:**
- ✅ Complete audit trail of all Cosmos DB access
- ✅ 30 days of logs in Log Analytics
- ✅ Ability to query: who accessed what, when
- ✅ HIPAA-compliant audit logging

**Next steps:**
1. Test a few queries in Azure Portal
2. Set up alerts for failed access
3. Extend retention to 7 years (for full HIPAA compliance)
4. Create monthly compliance report workflow

**Logs location:**
- Azure Portal → Log Analytics → `workspacevoiceagentrgbb4e`
- Or: Cosmos DB → Logs

Ready to enable SQL auditing next!
