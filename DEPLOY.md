# Cloud Deployment Guide

Deploy the Financial Agent System to the free tier of four services:

| Service | What it hosts | Free tier |
|---------|--------------|-----------|
| [Neon](https://neon.tech) | PostgreSQL + pgvector | 512 MB storage, 1 compute unit |
| [Upstash](https://upstash.com) | Redis Streams | 10,000 commands/day |
| [Railway](https://railway.app) | API server + worker | $5 credit/month (covers light usage) |
| [Vercel](https://vercel.com) | React frontend | Unlimited hobby projects |

---

## Step 1 — Push to GitHub

Everything must be in a GitHub repo before Railway and Vercel can deploy it.

```bash
cd ~/Desktop/Financial_Plan_AI
git init
git add .
git commit -m "initial commit"
```

Then create a new repo on [github.com/new](https://github.com/new) and push:

```bash
git remote add origin https://github.com/YOUR_USERNAME/financial-agent.git
git branch -M main
git push -u origin main
```

---

## Step 2 — Create Neon Database

1. Go to [neon.tech](https://neon.tech) → **Sign up** → **Create project**
2. Name it `financial-agent`, region closest to you
3. Go to **Connection Details** → copy the **Connection string**  
   It looks like: `postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/financial_agent?sslmode=require`
4. Enable pgvector: open the **SQL Editor** and run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
5. Run the schema: paste the contents of `infrastructure/init.sql` into the SQL Editor and run it

---

## Step 3 — Create Upstash Redis

1. Go to [console.upstash.com](https://console.upstash.com) → **Create database**
2. Name it `financial-agent`, type **Regional**, pick a region
3. Go to **Details** → copy the **Redis URL**  
   It looks like: `rediss://default:TOKEN@xxx.upstash.io:6379`

---

## Step 4 — Deploy API on Railway

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select your `financial-agent` repo
3. Railway auto-detects the Dockerfile — click **Deploy**
4. Go to the service **Settings** tab:
   - **Start Command**: `python3 -m uvicorn src.api.main:app --host 0.0.0.0 --port $PORT`
5. Go to **Variables** tab → add all variables from `.env.cloud.example`:
   ```
   DATABASE_URL     = <your Neon connection string>
   REDIS_URL        = <your Upstash Redis URL>
   LLM_PROVIDER     = groq
   GROQ_API_KEY     = <your Groq key>
   GROQ_MODEL       = llama-3.3-70b-versatile
   API_KEY          = fca_<generate a strong random hex>
   ENVIRONMENT      = production
   LOG_LEVEL        = INFO
   LOG_FORMAT       = json
   AGENT_MAX_STEPS  = 8
   ```
6. Go to **Settings** → **Networking** → **Generate Domain** — copy the URL (e.g. `https://financial-agent-api.up.railway.app`)

---

## Step 5 — Deploy Worker on Railway

The worker is the same Docker image but runs a different command.

1. In your Railway project → **New Service** → **GitHub Repo** → same repo
2. Go to **Settings** → **Start Command**:
   ```
   python3 -m src.events.worker
   ```
3. Go to **Variables** → add the **same variables** as the API service above  
   (Railway lets you copy variables between services)
4. Deploy — the worker will connect to Neon + Upstash and start listening for tasks

---

## Step 6 — Deploy Frontend on Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project** → import your GitHub repo
2. Vercel asks for **Root Directory** → set it to `frontend`
3. Framework preset will auto-detect as **Vite**
4. Go to **Environment Variables** → add:
   ```
   VITE_API_URL = https://financial-agent-api.up.railway.app
   ```
   _(replace with your actual Railway API URL from Step 4)_
5. Click **Deploy** — Vercel builds and publishes in ~60 seconds
6. Your frontend is live at `https://your-project.vercel.app`

---

## Step 7 — Seed data (first time only)

Run the seed script against your Neon database to populate accounts and transactions:

```bash
cd ~/Desktop/Financial_Plan_AI

# Set your Neon connection string
export DATABASE_URL="postgresql://user:pass@ep-xxx.neon.tech/financial_agent?sslmode=require"

# Seed accounts + transactions
python3 scripts/seed_data.py

# Seed compliance policies into pgvector
python3 scripts/seed_policies.py
```

---

## Verify Everything Works

```bash
# 1. Health check the Railway API
curl https://your-api.up.railway.app/health

# 2. Submit a task (use the API key you set in Railway variables)
curl -X POST https://your-api.up.railway.app/tasks \
  -H "X-API-Key: fca_your_key" \
  -H "Content-Type: application/json" \
  -d '{"description": "Check ACC-0001 for unusual activity", "account_id": "ACC-0001"}'

# 3. Open the frontend
open https://your-project.vercel.app
```

---

## Updating the Deployment

Push to `main` — Railway and Vercel both watch the repo and auto-redeploy on every push.

```bash
git add .
git commit -m "your changes"
git push
```
