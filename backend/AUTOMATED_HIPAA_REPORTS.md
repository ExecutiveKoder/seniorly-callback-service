# Automated Monthly HIPAA Compliance Reports

## Option 1: Azure Logic Apps (Recommended - No Code)

**Cost:** ~$1-2/month

### Setup Steps:

#### 1. Create Logic App

```bash
# Create Logic App
az logic workflow create \
  --resource-group voice-agent-rg \
  --name hipaa-monthly-report \
  --location eastus2
```

#### 2. Configure in Azure Portal

1. Go to Azure Portal → Logic Apps → `hipaa-monthly-report`
2. Click "Logic app designer"
3. Build workflow (see visual designer steps below)

### Workflow Design:

```
1. TRIGGER: Recurrence
   - Frequency: Month
   - On these days: 1 (first day of month)
   - At: 9:00 AM

2. ACTION: HTTP Request to Azure Function
   - Method: POST
   - URI: <your-function-url>/api/generate-hipaa-report
   - (Or run the Python script via Container Instance)

3. ACTION: Send Email (Office 365/Outlook/Gmail)
   - To: your-email@company.com
   - Subject: Monthly HIPAA Compliance Report - {{utcNow('MMMM yyyy')}}
   - Body: HTML from step 2
   - Attachments: Report file
```

### Full Logic App JSON Template:

Save as `hipaa-report-logic-app.json`:

```json
{
  "definition": {
    "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
    "actions": {
      "Generate_Report": {
        "type": "Http",
        "inputs": {
          "method": "POST",
          "uri": "https://voice-agent-app.azurecontainerapps.io/api/generate-hipaa-report"
        },
        "runAfter": {}
      },
      "Send_Email": {
        "type": "ApiConnection",
        "inputs": {
          "host": {
            "connection": {
              "name": "@parameters('$connections')['office365']['connectionId']"
            }
          },
          "method": "post",
          "path": "/v2/Mail",
          "body": {
            "To": "your-email@company.com",
            "Subject": "Monthly HIPAA Compliance Report - @{formatDateTime(utcNow(), 'MMMM yyyy')}",
            "Body": "<p>Your automated monthly HIPAA compliance report is attached.</p><p>@{body('Generate_Report')}</p>",
            "Importance": "High"
          }
        },
        "runAfter": {
          "Generate_Report": ["Succeeded"]
        }
      }
    },
    "triggers": {
      "Recurrence": {
        "type": "Recurrence",
        "recurrence": {
          "frequency": "Month",
          "interval": 1,
          "schedule": {
            "hours": ["9"],
            "minutes": [0],
            "monthDays": [1]
          },
          "timeZone": "Eastern Standard Time"
        }
      }
    }
  },
  "parameters": {
    "$connections": {
      "value": {
        "office365": {
          "connectionId": "/subscriptions/{subscription-id}/resourceGroups/voice-agent-rg/providers/Microsoft.Web/connections/office365",
          "connectionName": "office365",
          "id": "/subscriptions/{subscription-id}/providers/Microsoft.Web/locations/eastus2/managedApis/office365"
        }
      }
    }
  }
}
```

Deploy:
```bash
az logic workflow create \
  --resource-group voice-agent-rg \
  --name hipaa-monthly-report \
  --location eastus2 \
  --definition @hipaa-report-logic-app.json
```

---

## Option 2: Azure Functions (More Control)

**Cost:** Free tier (1M executions/month free)

### Setup Steps:

#### 1. Create Azure Function

```bash
# Create Function App
az functionapp create \
  --resource-group voice-agent-rg \
  --name seniorly-hipaa-function \
  --storage-account <storage-account> \
  --consumption-plan-location eastus2 \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4
```

#### 2. Create Timer-Triggered Function

Create `function_app.py`:

```python
import azure.functions as func
import logging
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# Import your report generator
from generate_hipaa_report import HIPAAComplianceReporter

app = func.FunctionApp()

@app.schedule(
    schedule="0 0 9 1 * *",  # 9 AM on 1st day of every month
    arg_name="timer",
    run_on_startup=False
)
def monthly_hipaa_report(timer: func.TimerRequest) -> None:
    """Generate and email monthly HIPAA compliance report"""

    logging.info('Generating monthly HIPAA report...')

    try:
        # Generate report
        reporter = HIPAAComplianceReporter()
        report_path = reporter.generate_report()

        # Read report HTML
        with open(report_path, 'r') as f:
            report_html = f.read()

        # Send email
        send_report_email(
            to_email="your-email@company.com",
            subject=f"Monthly HIPAA Compliance Report - {datetime.now().strftime('%B %Y')}",
            html_content=report_html,
            attachment_path=report_path
        )

        logging.info('✅ Report sent successfully')

    except Exception as e:
        logging.error(f'❌ Error generating report: {e}')
        # Send error notification
        send_error_notification(str(e))


def send_report_email(to_email: str, subject: str, html_content: str, attachment_path: str):
    """Send email with report"""

    # Use Azure Communication Services or SendGrid
    from azure.communication.email import EmailClient

    connection_string = os.environ['ACS_CONNECTION_STRING']
    client = EmailClient.from_connection_string(connection_string)

    message = {
        "senderAddress": "noreply@seniorly.com",
        "recipients": {
            "to": [{"address": to_email}]
        },
        "content": {
            "subject": subject,
            "html": html_content
        },
        "attachments": [
            {
                "name": "hipaa_report.html",
                "contentType": "text/html",
                "contentInBase64": base64.b64encode(open(attachment_path, 'rb').read()).decode()
            }
        ]
    }

    poller = client.begin_send(message)
    result = poller.result()

    logging.info(f"Email sent: {result.message_id}")


def send_error_notification(error_message: str):
    """Send error notification if report generation fails"""
    # Send alert email
    pass
```

Deploy:
```bash
cd backend
func azure functionapp publish seniorly-hipaa-function
```

---

## Option 3: Simple Cron Job with SendGrid (Cheapest)

**Cost:** $0 (SendGrid free tier: 100 emails/day)

### Setup:

#### 1. Install SendGrid

```bash
pip install sendgrid
```

#### 2. Update Report Script

Add email functionality to `generate_hipaa_report.py`:

```python
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

def send_report_via_sendgrid(report_path: str, recipient_email: str):
    """Send report via SendGrid"""

    # Read report
    with open(report_path, 'rb') as f:
        report_data = f.read()

    # Create email
    message = Mail(
        from_email='noreply@seniorly.com',
        to_emails=recipient_email,
        subject=f'Monthly HIPAA Compliance Report - {datetime.now().strftime("%B %Y")}',
        html_content='<p>Your automated monthly HIPAA compliance report is attached.</p>'
    )

    # Add attachment
    encoded_file = base64.b64encode(report_data).decode()

    attachment = Attachment(
        FileContent(encoded_file),
        FileName('hipaa_report.html'),
        FileType('text/html'),
        Disposition('attachment')
    )
    message.attachment = attachment

    # Send
    try:
        sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
        response = sg.send(message)
        print(f"✅ Email sent! Status: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False
```

#### 3. Set Up Cron (Linux/Mac) or Task Scheduler (Windows)

**Linux/Mac:**

```bash
# Edit crontab
crontab -e

# Add this line (runs 9 AM on 1st of every month)
0 9 1 * * cd /path/to/backend && /path/to/venv/bin/python scripts/generate_hipaa_report.py
```

**Windows Task Scheduler:**

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Monthly, 1st day, 9:00 AM
4. Action: Start a program
5. Program: `C:\path\to\python.exe`
6. Arguments: `C:\path\to\scripts\generate_hipaa_report.py`

---

## Option 4: Azure Container Instances (Serverless)

**Cost:** ~$1/month (only runs when needed)

### Setup:

```bash
# Create Container Instance with cron schedule
az container create \
  --resource-group voice-agent-rg \
  --name hipaa-report-runner \
  --image python:3.11-slim \
  --restart-policy Never \
  --command-line "pip install -r requirements.txt && python scripts/generate_hipaa_report.py" \
  --environment-variables \
    AZURE_COSMOS_ENDPOINT=$AZURE_COSMOS_ENDPOINT \
    AZURE_COSMOS_KEY=$AZURE_COSMOS_KEY \
    SENDGRID_API_KEY=$SENDGRID_API_KEY

# Schedule via Logic App to run this container monthly
```

---

## Comparison

| Option | Cost/Month | Complexity | Email Service |
|--------|------------|------------|---------------|
| **Logic Apps** | $1-2 | Low (visual designer) | Built-in (Office 365) |
| **Azure Functions** | Free | Medium (code) | Azure Communication Services |
| **Cron + SendGrid** | $0 | Low | SendGrid (free tier) |
| **Container Instances** | $1 | Medium | SendGrid |

---

## Recommended Setup (Logic Apps + SendGrid)

### Step-by-Step:

#### 1. Get SendGrid API Key (FREE)

```bash
# Sign up: https://sendgrid.com (free tier: 100 emails/day)
# Create API key: Settings → API Keys → Create API Key
# Copy key: SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### 2. Add Endpoint to Your Backend

Add to `backend/src/main.py`:

```python
from flask import Flask, request, jsonify
from generate_hipaa_report import HIPAAComplianceReporter

app = Flask(__name__)

@app.route('/api/generate-hipaa-report', methods=['POST'])
def generate_hipaa_report():
    """API endpoint to generate HIPAA report"""
    try:
        reporter = HIPAAComplianceReporter()
        report_path = reporter.generate_report()

        # Read report
        with open(report_path, 'r') as f:
            html = f.read()

        # Send via SendGrid
        send_report_via_sendgrid(report_path, "your-email@company.com")

        return jsonify({"status": "success", "report_path": str(report_path)})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
```

#### 3. Create Logic App

```bash
# Create Logic App
az logic workflow create \
  --resource-group voice-agent-rg \
  --name hipaa-monthly-report \
  --location eastus2
```

#### 4. Configure Workflow (Azure Portal)

1. Open Logic App in portal
2. Add trigger: **Recurrence** (Monthly, 1st day, 9 AM)
3. Add action: **HTTP** (POST to your endpoint)
4. Save

Done! You'll get an email on the 1st of every month.

---

## Testing the Report

Run manually:

```bash
cd backend
python scripts/generate_hipaa_report.py
```

Check output:
```
backend/reports/hipaa_report_YYYYMMDD.html
```

Open in browser to view.

---

## What the Email Looks Like

**Subject:** Monthly HIPAA Compliance Report - October 2025

**Body:**
```
📊 Your automated monthly HIPAA compliance report is ready.

Report Period: October 2025
Generated: October 1, 2025 at 9:00 AM UTC

Key Metrics:
✅ Overall Status: COMPLIANT
✅ Total Operations: 12,456
✅ Security Incidents: 0
✅ Failure Rate: 0.02%

See attached HTML report for full details.

---
Seniorly Health Platform
HIPAA Compliance Team
```

**Attachment:** `hipaa_report_20251001.html` (beautifully formatted HTML report)

---

## Environment Variables Needed

Add to `.env`:

```bash
# SendGrid (for email)
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=noreply@seniorly.com

# Report recipient
HIPAA_REPORT_EMAIL=your-email@company.com
```

---

## Summary

**Easiest Setup:** Logic Apps + HTTP endpoint (30 min setup)
**Cheapest:** Cron + SendGrid ($0/month)
**Most Reliable:** Azure Functions ($0 with free tier)

**My Recommendation:**
1. Use **SendGrid free tier** for emails ($0)
2. Create HTTP endpoint in your backend (5 min)
3. Use **Azure Logic Apps** to trigger monthly (10 min)
4. Total cost: **$1-2/month**

You'll automatically get a beautiful HTML report in your inbox on the 1st of every month showing:
- ✅ Compliance status
- 📊 All audit metrics
- 🚨 Security incidents
- 🔐 Encryption status
- 💾 Backup status
- 📋 Complete audit trail

**Want me to set this up now?** I can create the Logic App for you.
