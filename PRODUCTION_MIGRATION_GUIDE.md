# 🚀 PRODUCTION MIGRATION GUIDE

**Purpose:** Migrate from Azure Sponsorship (development) to Pay-As-You-Go (HIPAA-compliant production)

**When to use this:** Before launching with real seniors and real PHI

---

## ⚠️ PREREQUISITES

Before starting this migration, ensure:
- [ ] All development testing is complete
- [ ] Application is working correctly with test data
- [ ] All HIPAA fixes from `HIPAA_CRITICAL_ACTION_PLAN.md` are complete
- [ ] You have access to Azure billing admin
- [ ] You have $500-1000 available for first month costs

---

## 📋 MIGRATION STEPS

### Phase 1: Create New Production Subscription (Day 1)

**1. Create New Pay-As-You-Go Subscription**

```bash
# Go to Azure Portal
open https://portal.azure.com

# Navigate to: Subscriptions → Add → Pay-As-You-Go
# OR use this direct link:
open https://azure.microsoft.com/pricing/purchase-options/pay-as-you-go/
```

- Create new subscription (don't upgrade existing sponsorship yet)
- Name it: "Seniorly-Production"
- Set up billing profile
- Add credit card

**2. Request Azure BAA (Immediately)**

```bash
# Open Azure support ticket
open https://azure.microsoft.com/support

# In ticket, specify:
# - Subject: "Request HIPAA Business Associate Agreement"
# - Subscription: "Seniorly-Production"
# - Service Type: "Compliance"
# - Issue: "Need BAA for HIPAA compliance"
```

⏱️ **Timeline:** 1-2 weeks for BAA approval

---

### Phase 2: Recreate Infrastructure in Production (Week 2)

**While waiting for BAA, recreate your infrastructure:**

**1. Set Variables**

```bash
# Production subscription
PROD_SUBSCRIPTION_ID="<your-new-subscription-id>"
PROD_RG="seniorly-prod-rg"
PROD_REGION="eastus2"

# Switch to production subscription
az account set --subscription $PROD_SUBSCRIPTION_ID
```

**2. Create Resource Group**

```bash
az group create \
  --name $PROD_RG \
  --location $PROD_REGION \
  --tags Environment=Production Compliance=HIPAA
```

**3. Deploy All Services**

Use your existing infrastructure-as-code or run these commands:

```bash
# Key Vault (CRITICAL - do this first)
az keyvault create \
  --name seniorly-prod-secrets \
  --resource-group $PROD_RG \
  --location $PROD_REGION \
  --enable-purge-protection true \
  --enable-soft-delete true \
  --retention-days 90

# Cosmos DB
az cosmosdb create \
  --name seniorly-prod-cosmos \
  --resource-group $PROD_RG \
  --locations regionName=$PROD_REGION failoverPriority=0 \
  --enable-analytical-storage true \
  --backup-policy-type Continuous

# SQL Database
az sql server create \
  --name seniorly-prod-sql \
  --resource-group $PROD_RG \
  --location $PROD_REGION \
  --admin-user sqladmin \
  --admin-password "<generate-new-password>"

az sql db create \
  --resource-group $PROD_RG \
  --server seniorly-prod-sql \
  --name SeniorHealthAnalytics \
  --edition Standard \
  --capacity 10 \
  --zone-redundant false \
  --backup-storage-redundancy Local

# Redis Cache
az redis create \
  --location $PROD_REGION \
  --name seniorly-prod-redis \
  --resource-group $PROD_RG \
  --sku Basic \
  --vm-size c0 \
  --enable-non-ssl-port false

# AI Services (OpenAI, Speech, Search)
# Run your existing deployment scripts here...

# Container Registry
az acr create \
  --resource-group $PROD_RG \
  --name seniorlyprodacr \
  --sku Standard

# Log Analytics (6-year retention for HIPAA)
az monitor log-analytics workspace create \
  --resource-group $PROD_RG \
  --workspace-name seniorly-prod-logs \
  --location $PROD_REGION \
  --retention-time 2190

# Container Apps Environment
az containerapp env create \
  --name seniorly-prod-env \
  --resource-group $PROD_RG \
  --location $PROD_REGION \
  --logs-workspace-id "<workspace-id>" \
  --logs-workspace-key "<workspace-key>"
```

**4. Migrate Secrets to Production Key Vault**

```bash
# Get secrets from dev Key Vault (sponsorship)
DEV_SUBSCRIPTION_ID="<your-sponsorship-subscription-id>"
az account set --subscription $DEV_SUBSCRIPTION_ID

# Export secrets (store temporarily in secure location)
az keyvault secret show --vault-name seniorly-secrets --name AzureOpenAIKey --query value -o tsv > /tmp/prod_secrets.txt
# ... repeat for all 10 secrets ...

# Switch to production
az account set --subscription $PROD_SUBSCRIPTION_ID

# Import to production Key Vault
az keyvault secret set --vault-name seniorly-prod-secrets --name AzureOpenAIKey --file /tmp/prod_secrets.txt
# ... repeat for all secrets ...

# DELETE temporary file
rm /tmp/prod_secrets.txt
```

**5. Update Application Configuration**

Update your `.env` or container app settings:

```bash
# Production endpoints
AZURE_KEY_VAULT_NAME=seniorly-prod-secrets
AZURE_COSMOS_ENDPOINT=https://seniorly-prod-cosmos.documents.azure.com:443/
AZURE_SQL_SERVER=seniorly-prod-sql.database.windows.net
AZURE_REDIS_HOST=seniorly-prod-redis.redis.cache.windows.net
# ... etc
```

---

### Phase 3: Configure HIPAA Compliance (Week 2-3)

**1. Configure Audit Logging (All Services)**

```bash
# Cosmos DB
az cosmosdb sql database throughput update \
  --account-name seniorly-prod-cosmos \
  --name conversations \
  --resource-group $PROD_RG \
  --throughput 400

# SQL Database
az sql server audit-policy update \
  --resource-group $PROD_RG \
  --server seniorly-prod-sql \
  --state Enabled \
  --bsts Enabled

az sql db audit-policy update \
  --resource-group $PROD_RG \
  --server seniorly-prod-sql \
  --name SeniorHealthAnalytics \
  --state Enabled \
  --bsts Enabled

# Enable threat detection
az sql db threat-policy update \
  --resource-group $PROD_RG \
  --server seniorly-prod-sql \
  --name SeniorHealthAnalytics \
  --state Enabled \
  --email-addresses sats@seniorly.ai
```

**2. Configure Backup Retention (6 years)**

```bash
# Log Analytics (already done above - 2190 days)

# SQL Database (7 years LTR)
az sql db ltr-policy set \
  --resource-group $PROD_RG \
  --server seniorly-prod-sql \
  --name SeniorHealthAnalytics \
  --weekly-retention P12W \
  --monthly-retention P12M \
  --yearly-retention P7Y \
  --week-of-year 1

# Cosmos DB continuous backup (already enabled above)
```

**3. Create Backup Storage for Cosmos**

```bash
# Create storage account for Cosmos exports
az storage account create \
  --name seniorlyprodbackup \
  --resource-group $PROD_RG \
  --location $PROD_REGION \
  --sku Standard_LRS \
  --min-tls-version TLS1_2

# Set lifecycle policy (delete after 6 years)
az storage account management-policy create \
  --account-name seniorlyprodbackup \
  --policy '{
    "rules": [{
      "enabled": true,
      "name": "DeleteAfter6Years",
      "type": "Lifecycle",
      "definition": {
        "actions": {
          "baseBlob": {
            "delete": { "daysAfterModificationGreaterThan": 2190 }
          }
        },
        "filters": { "blobTypes": ["blockBlob"] }
      }
    }]
  }'
```

---

### Phase 4: Deploy Application (Week 3)

**1. Build and Push Container**

```bash
# Switch to production subscription
az account set --subscription $PROD_SUBSCRIPTION_ID

# Login to production ACR
az acr login --name seniorlyprodacr

# Build and push
cd backend
docker build -t seniorlyprodacr.azurecr.io/voice-agent:v1.0.0 .
docker push seniorlyprodacr.azurecr.io/voice-agent:v1.0.0
```

**2. Create Container App**

```bash
az containerapp create \
  --name voice-agent-prod \
  --resource-group $PROD_RG \
  --environment seniorly-prod-env \
  --image seniorlyprodacr.azurecr.io/voice-agent:v1.0.0 \
  --target-port 8000 \
  --ingress external \
  --registry-server seniorlyprodacr.azurecr.io \
  --registry-identity system \
  --env-vars \
    AZURE_KEY_VAULT_NAME=seniorly-prod-secrets \
    PRODUCTION_MODE=true \
  --cpu 2 \
  --memory 4Gi \
  --min-replicas 1 \
  --max-replicas 10
```

**3. Enable Managed Identity**

```bash
# Assign system identity
az containerapp identity assign \
  --name voice-agent-prod \
  --resource-group $PROD_RG \
  --system-assigned

# Get identity ID
IDENTITY_ID=$(az containerapp identity show \
  --name voice-agent-prod \
  --resource-group $PROD_RG \
  --query principalId -o tsv)

# Grant Key Vault access
az keyvault set-policy \
  --name seniorly-prod-secrets \
  --object-id $IDENTITY_ID \
  --secret-permissions get list
```

---

### Phase 5: Testing & Validation (Week 3-4)

**1. Test Key Vault Integration**

```bash
# Test that app can read secrets
curl https://voice-agent-prod.azurecontainerapps.io/health
```

**2. Run HIPAA Compliance Audit**

```bash
# Run your HIPAA audit script against production
python3 scripts/dynamic_hipaa_report.py --subscription $PROD_SUBSCRIPTION_ID
```

**3. Verify BAA is Signed**

```bash
# Check Azure Portal
open https://portal.azure.com

# Navigate to: Cost Management + Billing → Agreements
# Verify: Business Associate Agreement is present and signed
# Save PDF copy to: compliance/Azure_BAA_Production_2025.pdf
```

**4. Test with Fake Data First**

- Use test phone numbers
- Create fake senior profiles
- Run full conversation flows
- Verify data stored correctly
- Check audit logs working

---

### Phase 6: Cutover to Production (Launch Day)

**1. Update DNS/Phone Numbers**

```bash
# Update Twilio webhook URL
# Old: https://voice-agent-app.azurecontainerapps.io
# New: https://voice-agent-prod.azurecontainerapps.io

# Or switch to Azure Communication Services
```

**2. Migration Checklist**

- [ ] BAA signed and saved
- [ ] All HIPAA audit items green
- [ ] Secrets in production Key Vault
- [ ] 6-year log retention configured
- [ ] Backup strategy tested
- [ ] Test calls successful
- [ ] Monitoring/alerting active
- [ ] Incident response plan ready
- [ ] Team trained on HIPAA procedures

**3. Go Live**

- Enable production traffic
- Monitor closely for 24 hours
- Keep sponsorship environment as backup

---

### Phase 7: Cleanup Old Development (After 30 Days)

**Only after production is stable for 30 days:**

```bash
# Switch to sponsorship subscription
az account set --subscription $DEV_SUBSCRIPTION_ID

# Delete development resources
az group delete --name voice-agent-rg --yes

# Keep sponsorship subscription for future development
```

---

## 💰 COST COMPARISON

| Item | Sponsorship (Dev) | Production (Paid) |
|------|------------------|-------------------|
| Subscription | $0 (credits) | $0 base fee |
| Cosmos DB | ~$50/month | ~$50/month |
| SQL Database | ~$15/month | ~$15/month |
| Redis | ~$20/month | ~$20/month |
| Container Apps | ~$30/month | ~$30/month |
| Log Retention (6yr) | ~$60/month | ~$60/month |
| AI Services | ~$100/month | ~$100/month |
| **Total** | **~$275/month (free)** | **~$275/month (paid)** |
| **BAA** | ❌ Not available | ✅ Included (free) |

**Reality:** Same infrastructure cost, but production is HIPAA-compliant.

---

## 🚨 TROUBLESHOOTING

**Issue: BAA request rejected**
- Ensure subscription is Pay-As-You-Go (not Free Trial or Sponsorship)
- Ensure billing is active with valid credit card
- Contact Azure compliance team directly

**Issue: Secrets not accessible**
- Verify managed identity has Key Vault permissions
- Check Key Vault firewall settings
- Test DefaultAzureCredential authentication

**Issue: High costs in first month**
- Check for resource over-provisioning
- Review container replica counts
- Optimize database throughput

---

## 📞 SUPPORT

- **Azure Support:** https://azure.microsoft.com/support
- **HIPAA Questions:** https://www.hhs.gov/hipaa
- **Emergency:** Contact your compliance officer

---

**Document Version:** 1.0
**Created:** October 31, 2025
**Last Updated:** October 31, 2025
