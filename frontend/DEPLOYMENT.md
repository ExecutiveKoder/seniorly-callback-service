# Frontend Deployment Guide - Azure Static Web Apps

## Overview

This Next.js dashboard will be deployed to **Azure Static Web Apps**, which provides:
- ✅ Free tier available
- ✅ Automatic CI/CD from GitHub
- ✅ Global CDN (fast worldwide)
- ✅ Free SSL certificates
- ✅ Built-in authentication
- ✅ Supports Next.js SSR and API routes

---

## Option 1: Azure Static Web Apps (Recommended)

### Prerequisites
- GitHub repository (already set up ✅)
- Azure subscription

### Step 1: Create Static Web App

```bash
# Install Azure Static Web Apps CLI
npm install -g @azure/static-web-apps-cli

# Login to Azure
az login

# Create Static Web App
az staticwebapp create \
  --name seniorly-dashboard \
  --resource-group voice-agent-rg \
  --source https://github.com/ExecutiveKoder/seniorly-callback-service \
  --location eastus2 \
  --branch master \
  --app-location "frontend" \
  --api-location "" \
  --output-location ".next"
```

### Step 2: Configure GitHub Actions

Azure will automatically create a GitHub Actions workflow file at:
`.github/workflows/azure-static-web-apps-<name>.yml`

**Manual Configuration (if needed):**

Create `.github/workflows/azure-static-web-apps.yml`:

```yaml
name: Azure Static Web Apps CI/CD

on:
  push:
    branches:
      - master
  pull_request:
    types: [opened, synchronize, reopened, closed]
    branches:
      - master

jobs:
  build_and_deploy_job:
    if: github.event_name == 'push' || (github.event_name == 'pull_request' && github.event.action != 'closed')
    runs-on: ubuntu-latest
    name: Build and Deploy Job
    steps:
      - uses: actions/checkout@v3
        with:
          submodules: true

      - name: Build And Deploy
        id: builddeploy
        uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_API_TOKEN }}
          repo_token: ${{ secrets.GITHUB_TOKEN }}
          action: "upload"
          app_location: "frontend"
          api_location: ""
          output_location: ".next"

  close_pull_request_job:
    if: github.event_name == 'pull_request' && github.event.action == 'closed'
    runs-on: ubuntu-latest
    name: Close Pull Request Job
    steps:
      - name: Close Pull Request
        id: closepullrequest
        uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_API_TOKEN }}
          action: "close"
```

### Step 3: Configure Next.js for Static Web Apps

Update `frontend/next.config.ts`:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone', // For Azure Static Web Apps

  // Environment variables
  env: {
    AZURE_SQL_SERVER: process.env.AZURE_SQL_SERVER,
    AZURE_SQL_DATABASE: process.env.AZURE_SQL_DATABASE,
  },

  // Disable image optimization for static export
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
```

### Step 4: Add Environment Variables

In Azure Portal:
1. Go to your Static Web App
2. Click "Configuration" in left menu
3. Add environment variables:
   - `AZURE_SQL_SERVER`
   - `AZURE_SQL_DATABASE`
   - `AZURE_SQL_USERNAME`
   - `AZURE_SQL_PASSWORD`

### Step 5: Deploy

```bash
# Push to GitHub (already done ✅)
git push origin master

# GitHub Actions will automatically build and deploy
```

**Deployment URL:**
`https://seniorly-dashboard.azurestaticapps.net`

---

## Option 2: Azure App Service (Alternative)

If you need full Node.js runtime (for complex API routes):

```bash
# Create App Service plan
az appservice plan create \
  --name seniorly-dashboard-plan \
  --resource-group voice-agent-rg \
  --sku B1 \
  --is-linux

# Create web app
az webapp create \
  --resource-group voice-agent-rg \
  --plan seniorly-dashboard-plan \
  --name seniorly-dashboard \
  --runtime "NODE:20-lts"

# Configure deployment from GitHub
az webapp deployment source config \
  --name seniorly-dashboard \
  --resource-group voice-agent-rg \
  --repo-url https://github.com/ExecutiveKoder/seniorly-callback-service \
  --branch master \
  --manual-integration

# Set app settings
az webapp config appsettings set \
  --resource-group voice-agent-rg \
  --name seniorly-dashboard \
  --settings \
    AZURE_SQL_SERVER="seniorly-sql-server.database.windows.net" \
    AZURE_SQL_DATABASE="SeniorHealthAnalytics" \
    WEBSITE_NODE_DEFAULT_VERSION="20-lts"
```

**Deployment URL:**
`https://seniorly-dashboard.azurewebsites.net`

---

## Option 3: Azure Container Apps (Same as Backend)

Use if you want frontend and backend in same infrastructure:

### Create Dockerfile for Frontend

Create `frontend/Dockerfile`:

```dockerfile
FROM node:20-alpine AS base

# Install dependencies
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Build application
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Production image
FROM base AS runner
WORKDIR /app

ENV NODE_ENV production

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT 3000

CMD ["node", "server.js"]
```

### Deploy to Container Apps

```bash
# Build and push image
cd frontend
docker build -t myvoiceagentacr.azurecr.io/voice-agent-dashboard:latest .
docker push myvoiceagentacr.azurecr.io/voice-agent-dashboard:latest

# Create container app
az containerapp create \
  --name voice-agent-dashboard \
  --resource-group voice-agent-rg \
  --environment voice-agent-env \
  --image myvoiceagentacr.azurecr.io/voice-agent-dashboard:latest \
  --target-port 3000 \
  --ingress external \
  --env-vars \
    AZURE_SQL_SERVER="seniorly-sql-server.database.windows.net" \
    AZURE_SQL_DATABASE="SeniorHealthAnalytics"
```

---

## Connecting Frontend to Backend (Azure SQL)

### Install SQL Client Library

```bash
cd frontend
npm install mssql
```

### Create Database Client

Create `frontend/lib/db.ts`:

```typescript
import sql from 'mssql'

const config: sql.config = {
  server: process.env.AZURE_SQL_SERVER!,
  database: process.env.AZURE_SQL_DATABASE!,
  user: process.env.AZURE_SQL_USERNAME!,
  password: process.env.AZURE_SQL_PASSWORD!,
  options: {
    encrypt: true,
    trustServerCertificate: false
  }
}

let pool: sql.ConnectionPool | null = null

export async function query<T>(sqlQuery: string, params?: any[]): Promise<T[]> {
  if (!pool) {
    pool = await sql.connect(config)
  }

  const request = pool.request()

  // Add parameters
  if (params) {
    params.forEach((param, index) => {
      request.input(`p${index + 1}`, param)
    })
  }

  const result = await request.query(sqlQuery)
  return result.recordset
}

export async function closePool() {
  if (pool) {
    await pool.close()
    pool = null
  }
}
```

### Create API Route for Vitals

Create `frontend/app/api/seniors/[id]/vitals/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server'
import { query } from '@/lib/db'

interface VitalRecord {
  vital_type: string
  vital_value: number
  unit: string
  recorded_at: string
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const seniorId = params.id

    const vitals = await query<VitalRecord>(`
      SELECT vital_type, vital_value, unit, recorded_at
      FROM vw_latest_vitals_by_senior
      WHERE senior_id = @p1
      ORDER BY recorded_at DESC
    `, [seniorId])

    return NextResponse.json(vitals)
  } catch (error) {
    console.error('Error fetching vitals:', error)
    return NextResponse.json(
      { error: 'Failed to fetch vitals' },
      { status: 500 }
    )
  }
}
```

### Create Dashboard Page

Create `frontend/app/dashboard/page.tsx`:

```typescript
export default async function DashboardPage() {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/seniors/123/vitals`)
  const vitals = await response.json()

  return (
    <div className="container mx-auto p-8">
      <h1 className="text-3xl font-bold mb-8">Senior Health Dashboard</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {vitals.map((vital) => (
          <div key={vital.vital_type} className="bg-white p-6 rounded-lg shadow">
            <h3 className="text-lg font-semibold">{vital.vital_type}</h3>
            <p className="text-3xl font-bold mt-2">
              {vital.vital_value} {vital.unit}
            </p>
            <p className="text-sm text-gray-500 mt-2">
              {new Date(vital.recorded_at).toLocaleDateString()}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
```

---

## Authentication (Azure AD B2C)

For secure dashboard access:

```bash
# Install NextAuth
npm install next-auth @next-auth/azure-ad-b2c-adapter

# Configure in app/api/auth/[...nextauth]/route.ts
```

---

## Custom Domain

After deployment:

1. Go to Azure Portal → Your Static Web App
2. Click "Custom domains" in left menu
3. Add domain: `dashboard.seniorly.com`
4. Update DNS with provided CNAME
5. Azure automatically provisions SSL certificate

---

## Cost Comparison

| Option | Monthly Cost | Best For |
|--------|--------------|----------|
| **Static Web Apps (Free)** | $0 | Small traffic, static sites |
| **Static Web Apps (Standard)** | $9 | Production apps, authentication |
| **App Service (B1)** | $13 | Full Node.js runtime needed |
| **Container Apps** | $20-40 | Microservices, same infra as backend |

**Recommendation:** Start with **Azure Static Web Apps** (free tier or $9/month).

---

## Deployment Checklist

- [ ] Create Azure Static Web App resource
- [ ] Configure GitHub Actions workflow
- [ ] Add environment variables in Azure Portal
- [ ] Update Next.js config for standalone output
- [ ] Create database connection library (`lib/db.ts`)
- [ ] Create API routes for dashboard data
- [ ] Test connection to Azure SQL
- [ ] Set up custom domain (optional)
- [ ] Configure authentication (optional)
- [ ] Push to GitHub → auto-deploy!

---

## Monitoring & Logs

View deployment logs:
- GitHub Actions: https://github.com/ExecutiveKoder/seniorly-callback-service/actions
- Azure Portal: Your Static Web App → "Logs" section

---

## Summary

✅ **Azure Static Web Apps** is the recommended option for Next.js
✅ **Automatic CI/CD** from GitHub (push to deploy)
✅ **Free tier** available for testing
✅ **Global CDN** for fast performance
✅ **Easy integration** with Azure SQL backend

**Next Steps:**
1. Run `az staticwebapp create` command above
2. Push code to GitHub
3. Watch it auto-deploy! 🚀
