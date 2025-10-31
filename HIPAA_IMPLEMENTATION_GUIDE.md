# 🔐 HIPAA IMPLEMENTATION GUIDE

**Purpose:** Step-by-step implementation of remaining HIPAA compliance requirements

**Prerequisites:**
- Key Vault migration complete ✅
- 6-year log retention configured ✅
- Azure Sponsorship limitation documented ✅

---

## 1️⃣ MFA FOR API ACCESS

**HIPAA Requirement:** § 164.312(d) - Person or Entity Authentication

Since you have a **webapp frontend**, you need MFA for:
- Admin access to Azure Portal
- Web app user logins (for caregivers/staff viewing senior data)
- API endpoints that access PHI

### Option A: Azure AD B2C for User Authentication (RECOMMENDED)

**Best for:** Web app with caregiver/staff logins

**1. Create Azure AD B2C Tenant**

```bash
# Create B2C tenant
az ad b2c tenant create \
  --display-name "Seniorly-Auth" \
  --domain-name seniorlyauth \
  --country-code US \
  --data-residency-location "United States"

# Note the tenant ID
B2C_TENANT_ID="<tenant-id>"
```

**2. Register Web Application**

```bash
# Register the web app
az ad app create \
  --display-name "Seniorly-WebApp" \
  --sign-in-audience "AzureADandPersonalMicrosoftAccount" \
  --web-redirect-uris "https://yourapp.com/auth/callback" "http://localhost:3000/auth/callback"

# Get app ID
APP_ID=$(az ad app list --display-name "Seniorly-WebApp" --query "[0].appId" -o tsv)
echo "App ID: $APP_ID"

# Create client secret
az ad app credential reset --id $APP_ID --append
```

**3. Configure MFA Policies**

Go to Azure Portal:
1. Navigate to: **Azure AD B2C** → **User flows**
2. Click: **New user flow**
3. Select: **Sign up and sign in**
4. Enable:
   - ✅ Email verification
   - ✅ Multi-factor authentication (REQUIRED)
   - ✅ Phone number verification

**4. Web App Integration (React/Next.js Example)**

```bash
# Install MSAL (Microsoft Authentication Library)
npm install @azure/msal-browser @azure/msal-react
```

**Frontend Code:** `src/auth/authConfig.js`

```javascript
import { PublicClientApplication } from "@azure/msal-browser";

const msalConfig = {
  auth: {
    clientId: "YOUR_APP_ID", // from step 2
    authority: "https://seniorlyauth.b2clogin.com/seniorlyauth.onmicrosoft.com/B2C_1_signupsignin",
    knownAuthorities: ["seniorlyauth.b2clogin.com"],
    redirectUri: "http://localhost:3000/auth/callback",
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  }
};

// MFA is enforced in B2C user flow configuration
export const msalInstance = new PublicClientApplication(msalConfig);
```

**Frontend Code:** `src/App.js`

```javascript
import { MsalProvider, useMsal, useIsAuthenticated } from "@azure/msal-react";
import { msalInstance } from "./auth/authConfig";

function App() {
  return (
    <MsalProvider instance={msalInstance}>
      <MainApp />
    </MsalProvider>
  );
}

function MainApp() {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();

  const handleLogin = () => {
    instance.loginPopup({
      scopes: ["openid", "profile", "User.Read"]
    });
  };

  if (!isAuthenticated) {
    return <button onClick={handleLogin}>Login with MFA</button>;
  }

  return <Dashboard user={accounts[0]} />;
}
```

**5. Backend API Protection**

```python
# backend/src/middleware/auth_middleware.py
from functools import wraps
from flask import request, jsonify
import jwt
from jwt import PyJWKClient

# Azure AD B2C config
B2C_TENANT = "seniorlyauth"
B2C_POLICY = "B2C_1_signupsignin"
JWKS_URL = f"https://{B2C_TENANT}.b2clogin.com/{B2C_TENANT}.onmicrosoft.com/{B2C_POLICY}/discovery/v2.0/keys"

def require_mfa_auth(f):
    """Decorator to require MFA-authenticated requests"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing or invalid token"}), 401

        token = auth_header.split(' ')[1]

        try:
            # Verify JWT token
            jwks_client = PyJWKClient(JWKS_URL)
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            # Decode and validate
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience="YOUR_APP_ID",
                issuer=f"https://{B2C_TENANT}.b2clogin.com/..."
            )

            # Check MFA claim (amr = Authentication Methods Reference)
            if 'amr' not in decoded or 'mfa' not in decoded['amr']:
                return jsonify({"error": "MFA required"}), 403

            # Add user info to request
            request.user = decoded
            return f(*args, **kwargs)

        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

    return decorated


# Usage in your API routes
from flask import Flask
from src.middleware.auth_middleware import require_mfa_auth

app = Flask(__name__)

@app.route('/api/seniors/<senior_id>/health', methods=['GET'])
@require_mfa_auth  # ← Requires MFA
def get_senior_health(senior_id):
    # Access PHI only after MFA verification
    user_email = request.user['email']

    # Log access for HIPAA audit
    logger.info(f"PHI_ACCESS: {user_email} accessed senior {senior_id}")

    # Return health data
    return jsonify({"data": "..."})
```

**6. Install Backend Dependencies**

```bash
cd backend
pip install PyJWT cryptography
```

Add to `requirements.txt`:
```
PyJWT==2.10.1
cryptography==46.0.3
```

**Cost:** Azure AD B2C is **FREE** for first 50,000 users/month

---

### Option B: Simple API Key + TOTP (For Internal Admin Tools)

**Best for:** Admin scripts, internal dashboards (no external users)

**1. Generate API Keys**

```python
# backend/scripts/generate_admin_key.py
import secrets
import pyotp
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Generate secure API key
api_key = secrets.token_urlsafe(32)
print(f"API Key: {api_key}")

# Generate TOTP secret for MFA
totp_secret = pyotp.random_base32()
print(f"TOTP Secret: {totp_secret}")
print(f"QR Code: {pyotp.totp.TOTP(totp_secret).provisioning_uri('admin@seniorly.ai', issuer_name='Seniorly')}")

# Store in Key Vault
credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://seniorly-secrets.vault.azure.net", credential=credential)

client.set_secret("AdminAPIKey", api_key)
client.set_secret("AdminTOTPSecret", totp_secret)

print("✅ Stored in Key Vault")
```

**2. MFA Verification Middleware**

```python
# backend/src/middleware/mfa_middleware.py
import pyotp
from functools import wraps
from flask import request, jsonify
from src.config import get_secret

def require_mfa(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get API key and TOTP from headers
        api_key = request.headers.get('X-API-Key')
        totp_code = request.headers.get('X-TOTP-Code')

        if not api_key or not totp_code:
            return jsonify({"error": "Missing API key or TOTP code"}), 401

        # Verify API key
        valid_key = get_secret('AdminAPIKey')
        if api_key != valid_key:
            return jsonify({"error": "Invalid API key"}), 401

        # Verify TOTP
        totp_secret = get_secret('AdminTOTPSecret')
        totp = pyotp.TOTP(totp_secret)

        if not totp.verify(totp_code, valid_window=1):
            return jsonify({"error": "Invalid or expired TOTP code"}), 401

        return f(*args, **kwargs)

    return decorated

# Usage
@app.route('/admin/export-phi', methods=['POST'])
@require_mfa
def export_phi():
    # Only accessible with API key + current TOTP code
    return jsonify({"data": "..."})
```

**3. Admin Script Example**

```python
# scripts/download_phi_report.py
import pyotp
import requests

API_KEY = "<from-keyvault>"
TOTP_SECRET = "<from-keyvault>"

# Generate current TOTP code
totp = pyotp.TOTP(TOTP_SECRET)
current_code = totp.now()

# Make authenticated request
response = requests.post(
    "https://yourapi.com/admin/export-phi",
    headers={
        "X-API-Key": API_KEY,
        "X-TOTP-Code": current_code
    }
)

print(response.json())
```

**Install:** `pip install pyotp qrcode`

---

## 2️⃣ FIELD-LEVEL ENCRYPTION (COSMOS DB)

**HIPAA Requirement:** § 164.312(a)(2)(iv) - Encryption of PHI at rest

Cosmos DB already has encryption at rest, but HIPAA best practice is **field-level encryption** for highly sensitive data (SSN, health conditions).

### Implementation

**1. Create Encryption Key in Key Vault**

```bash
# Create encryption key
az keyvault key create \
  --vault-name seniorly-secrets \
  --name cosmos-phi-encryption \
  --kty RSA \
  --size 2048

# Get key ID
KEY_ID=$(az keyvault key show --vault-name seniorly-secrets --name cosmos-phi-encryption --query key.kid -o tsv)
echo "Key ID: $KEY_ID"
```

**2. Install Encryption Library**

```bash
pip install cryptography
```

Add to `requirements.txt`:
```
cryptography==46.0.3
```

**3. Encryption Service**

```python
# backend/src/services/encryption_service.py
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from azure.keyvault.keys.crypto import CryptographyClient
from azure.identity import DefaultAzureCredential
import base64
import os

class PHIEncryptionService:
    """Encrypt sensitive PHI fields before storing in Cosmos DB"""

    def __init__(self):
        # Get encryption key from Key Vault
        credential = DefaultAzureCredential()
        key_id = "https://seniorly-secrets.vault.azure.net/keys/cosmos-phi-encryption"
        self.crypto_client = CryptographyClient(key_id, credential)

        # Derive symmetric key for Fernet (faster for field-level encryption)
        self._setup_fernet()

    def _setup_fernet(self):
        """Setup Fernet symmetric encryption"""
        # In production, derive this from Key Vault key
        # For now, store in Key Vault as secret
        from src.config import get_secret
        fernet_key = get_secret('CosmosEncryptionKey')

        if not fernet_key:
            # Generate new key
            fernet_key = Fernet.generate_key().decode()
            # Store in Key Vault (manual step first time)
            print(f"⚠️  Store this in Key Vault as 'CosmosEncryptionKey': {fernet_key}")

        self.fernet = Fernet(fernet_key.encode())

    def encrypt_field(self, plaintext: str) -> str:
        """Encrypt a sensitive field"""
        if not plaintext:
            return plaintext

        encrypted = self.fernet.encrypt(plaintext.encode())
        return base64.b64encode(encrypted).decode()

    def decrypt_field(self, ciphertext: str) -> str:
        """Decrypt a sensitive field"""
        if not ciphertext:
            return ciphertext

        try:
            encrypted = base64.b64decode(ciphertext.encode())
            decrypted = self.fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            print(f"Decryption error: {e}")
            return None

# Singleton instance
phi_encryption = PHIEncryptionService()
```

**4. Update Data Service to Encrypt/Decrypt**

```python
# backend/src/services/data_service.py
from src.services.encryption_service import phi_encryption

class DataService:
    # ... existing code ...

    def save_conversation(self, senior_id, conversation_data):
        """Save conversation with encrypted PHI fields"""

        # Encrypt sensitive fields before storing
        if 'medications' in conversation_data:
            conversation_data['medications'] = phi_encryption.encrypt_field(
                str(conversation_data['medications'])
            )

        if 'health_conditions' in conversation_data:
            conversation_data['health_conditions'] = phi_encryption.encrypt_field(
                str(conversation_data['health_conditions'])
            )

        if 'symptoms' in conversation_data:
            conversation_data['symptoms'] = phi_encryption.encrypt_field(
                str(conversation_data['symptoms'])
            )

        # Store in Cosmos DB (now encrypted)
        self.container.upsert_item(conversation_data)

    def get_conversation(self, senior_id, conversation_id):
        """Retrieve and decrypt conversation"""

        # Get from Cosmos DB
        item = self.container.read_item(
            item=conversation_id,
            partition_key=senior_id
        )

        # Decrypt sensitive fields
        if 'medications' in item:
            item['medications'] = phi_encryption.decrypt_field(item['medications'])

        if 'health_conditions' in item:
            item['health_conditions'] = phi_encryption.decrypt_field(item['health_conditions'])

        if 'symptoms' in item:
            item['symptoms'] = phi_encryption.decrypt_field(item['symptoms'])

        return item
```

**5. Generate and Store Fernet Key**

```bash
# Generate encryption key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Store in Key Vault
az keyvault secret set \
  --vault-name seniorly-secrets \
  --name CosmosEncryptionKey \
  --value "<generated-key>"
```

**Benefits:**
- PHI encrypted even if Cosmos DB backup is compromised
- Encryption key separate from data (Key Vault)
- Complies with § 164.312(a)(2)(iv)

---

## 3️⃣ SQL ALWAYS ENCRYPTED

**HIPAA Requirement:** § 164.312(a)(2)(iv) - Encryption of PHI at rest

SQL Server has built-in **Always Encrypted** feature for column-level encryption.

### Implementation

**1. Enable Always Encrypted on SQL Database**

```bash
# Connect to SQL Server
az sql db show \
  --resource-group voice-agent-rg \
  --server seniorly-sql-server \
  --name SeniorHealthAnalytics

# Note: Always Encrypted requires SQL Management Studio or Azure Data Studio
# Cannot be done via CLI
```

**2. Create Column Master Key in Key Vault**

```bash
# Create key for SQL encryption
az keyvault key create \
  --vault-name seniorly-secrets \
  --name sql-always-encrypted-cmk \
  --kty RSA \
  --size 4096 \
  --ops wrapKey unwrapKey

# Get key URL
KEY_URL=$(az keyvault key show --vault-name seniorly-secrets --name sql-always-encrypted-cmk --query key.kid -o tsv)
echo "Column Master Key URL: $KEY_URL"
```

**3. Configure Always Encrypted (Using Azure Data Studio)**

Download Azure Data Studio: https://aka.ms/azuredatastudio

```sql
-- Connect to your SQL Database
-- Right-click database → Tasks → Encrypt Columns

-- Or use T-SQL:

-- Create Column Master Key
CREATE COLUMN MASTER KEY [CMK_KeyVault]
WITH (
    KEY_STORE_PROVIDER_NAME = 'AZURE_KEY_VAULT',
    KEY_PATH = 'https://seniorly-secrets.vault.azure.net/keys/sql-always-encrypted-cmk/<version>'
);

-- Create Column Encryption Key
CREATE COLUMN ENCRYPTION KEY [CEK1]
WITH VALUES (
    COLUMN_MASTER_KEY = [CMK_KeyVault],
    ALGORITHM = 'RSA_OAEP',
    ENCRYPTED_VALUE = 0x... -- Generated by Azure Data Studio
);

-- Encrypt existing columns
ALTER TABLE senior_vitals
ALTER COLUMN blood_pressure VARCHAR(20)
ENCRYPTED WITH (
    COLUMN_ENCRYPTION_KEY = [CEK1],
    ENCRYPTION_TYPE = Deterministic,
    ALGORITHM = 'AEAD_AES_256_CBC_HMAC_SHA_256'
);

ALTER TABLE senior_vitals
ALTER COLUMN heart_rate INT
ENCRYPTED WITH (
    COLUMN_ENCRYPTION_KEY = [CEK1],
    ENCRYPTION_TYPE = Randomized,
    ALGORITHM = 'AEAD_AES_256_CBC_HMAC_SHA_256'
);

-- Encrypt all PHI columns
ALTER TABLE cognitive_assessments
ALTER COLUMN assessment_results NVARCHAR(MAX)
ENCRYPTED WITH (
    COLUMN_ENCRYPTION_KEY = [CEK1],
    ENCRYPTION_TYPE = Randomized,
    ALGORITHM = 'AEAD_AES_256_CBC_HMAC_SHA_256'
);
```

**4. Update Python Connection String**

```python
# backend/src/config.py

# SQL connection for Always Encrypted
def get_sql_connection_string():
    """Get SQL connection string with Always Encrypted enabled"""
    server = os.getenv('AZURE_SQL_SERVER')
    database = os.getenv('AZURE_SQL_DATABASE')
    username = os.getenv('AZURE_SQL_USERNAME')
    password = get_secret('AzureSQLPassword')

    return (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server=tcp:{server},1433;"
        f"Database={database};"
        f"Uid={username};"
        f"Pwd={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
        f"ColumnEncryption=Enabled;"  # ← Enable Always Encrypted
        f"KeyStoreAuthentication=KeyVaultClientSecret;"
        f"KeyStorePrincipalId=<your-app-id>;"
        f"KeyStoreSecret=<your-app-secret>;"
    )
```

**5. Grant SQL Access to Key Vault**

```bash
# Create service principal for SQL
az ad sp create-for-rbac \
  --name "seniorly-sql-encryption" \
  --skip-assignment

# Get object ID
SP_OBJECT_ID=$(az ad sp list --display-name "seniorly-sql-encryption" --query "[0].id" -o tsv)

# Grant Key Vault access
az keyvault set-policy \
  --name seniorly-secrets \
  --object-id $SP_OBJECT_ID \
  --key-permissions get unwrapKey wrapKey
```

**Note:** Always Encrypted is complex. For initial HIPAA compliance, **Cosmos field-level encryption (Option 2) is sufficient**. Add SQL Always Encrypted in production.

---

## 4️⃣ NETWORK SEGMENTATION (VNET)

**HIPAA Requirement:** § 164.312(e)(1) - Transmission Security

Isolate PHI resources on private network, block public internet access.

### Implementation

**1. Create Virtual Network**

```bash
# Create VNet
az network vnet create \
  --resource-group voice-agent-rg \
  --name seniorly-vnet \
  --address-prefix 10.0.0.0/16 \
  --subnet-name app-subnet \
  --subnet-prefix 10.0.1.0/24

# Create database subnet
az network vnet subnet create \
  --resource-group voice-agent-rg \
  --vnet-name seniorly-vnet \
  --name data-subnet \
  --address-prefix 10.0.2.0/24 \
  --service-endpoints Microsoft.AzureCosmosDB Microsoft.Sql Microsoft.Storage
```

**2. Create Private Endpoints for Resources**

```bash
# Cosmos DB private endpoint
az network private-endpoint create \
  --resource-group voice-agent-rg \
  --name cosmos-private-endpoint \
  --vnet-name seniorly-vnet \
  --subnet data-subnet \
  --private-connection-resource-id $(az cosmosdb show --name seniorly-cosmos --resource-group voice-agent-rg --query id -o tsv) \
  --group-id Sql \
  --connection-name cosmos-private-connection

# SQL Database private endpoint
az network private-endpoint create \
  --resource-group voice-agent-rg \
  --name sql-private-endpoint \
  --vnet-name seniorly-vnet \
  --subnet data-subnet \
  --private-connection-resource-id $(az sql server show --name seniorly-sql-server --resource-group voice-agent-rg --query id -o tsv) \
  --group-id sqlServer \
  --connection-name sql-private-connection

# Redis private endpoint
az network private-endpoint create \
  --resource-group voice-agent-rg \
  --name redis-private-endpoint \
  --vnet-name seniorly-vnet \
  --subnet data-subnet \
  --private-connection-resource-id $(az redis show --name seniorly-redis --resource-group voice-agent-rg --query id -o tsv) \
  --group-id redisCache \
  --connection-name redis-private-connection
```

**3. Disable Public Access**

```bash
# Cosmos DB - disable public access
az cosmosdb update \
  --name seniorly-cosmos \
  --resource-group voice-agent-rg \
  --enable-public-network false

# SQL - disable public access
az sql server update \
  --name seniorly-sql-server \
  --resource-group voice-agent-rg \
  --enable-public-network false

# Storage account
az storage account update \
  --name seniorlyphibackup \
  --resource-group voice-agent-rg \
  --default-action Deny \
  --public-network-access Disabled
```

**4. Integrate Container Apps with VNet**

```bash
# Update Container Apps Environment to use VNet
az containerapp env update \
  --name voice-agent-env \
  --resource-group voice-agent-rg \
  --infrastructure-subnet-resource-id $(az network vnet subnet show --resource-group voice-agent-rg --vnet-name seniorly-vnet --name app-subnet --query id -o tsv)
```

**5. Configure Network Security Groups**

```bash
# Create NSG for app subnet
az network nsg create \
  --resource-group voice-agent-rg \
  --name app-nsg

# Allow HTTPS inbound
az network nsg rule create \
  --resource-group voice-agent-rg \
  --nsg-name app-nsg \
  --name AllowHTTPS \
  --priority 100 \
  --source-address-prefixes Internet \
  --destination-port-ranges 443 \
  --protocol Tcp \
  --access Allow

# Deny all other inbound
az network nsg rule create \
  --resource-group voice-agent-rg \
  --nsg-name app-nsg \
  --name DenyAllInbound \
  --priority 4096 \
  --access Deny \
  --protocol '*'

# Associate with subnet
az network vnet subnet update \
  --resource-group voice-agent-rg \
  --vnet-name seniorly-vnet \
  --name app-subnet \
  --network-security-group app-nsg
```

**Cost Impact:** ~$50-100/month for private endpoints

---

## ⚠️ IMPORTANT NOTES

**For Azure Sponsorship (Development):**
- MFA: Can implement for free
- Field-level encryption: Can implement (uses Key Vault you already have)
- SQL Always Encrypted: Can configure but not critical for dev
- VNet: Can create but adds cost (~$50/month)

**Recommendation for NOW (Development Phase):**
1. ✅ Implement MFA (Azure AD B2C - free)
2. ✅ Implement Cosmos field-level encryption (uses existing Key Vault)
3. ⏳ Skip SQL Always Encrypted (low priority, complex)
4. ⏳ Skip VNet (adds cost, do in production)

**For Production (After Upgrading Subscription):**
- Implement all 4 features
- Total added cost: ~$50-100/month (mostly private endpoints)

---

**Next Steps:**
1. Try running your app: `cd backend && ./run_app.sh`
2. Choose which features to implement now vs. production
3. I can help implement MFA + Cosmos encryption if you want

