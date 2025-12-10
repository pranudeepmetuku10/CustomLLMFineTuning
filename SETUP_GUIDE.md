# Infrastructure Setup Guide

This document explains what you need to set up for the platform to work.

---

## 1. PostgreSQL Database

### Option A: Local Docker (Easiest)
Run the included docker-compose:
```bash
docker-compose up -d postgres
```
This creates:
- Database: `llm_platform`
- User: `postgres`
- Password: `postgres_dev_password`
- Port: `5432`

### Option B: Cloud PostgreSQL (Production)
| Provider | Service | Setup |
|----------|---------|-------|
| **GCP** | Cloud SQL for PostgreSQL | [Console](https://console.cloud.google.com/sql) |
| **AWS** | Amazon RDS for PostgreSQL | [Console](https://console.aws.amazon.com/rds) |
| **Azure** | Azure Database for PostgreSQL | [Console](https://portal.azure.com) |

**Recommended specs:** 2 vCPUs, 8GB RAM, 50GB SSD

After creating, update `.env`:
```env
DB_HOST=<your-cloud-db-host>
DB_PORT=5432
DB_NAME=llm_platform
DB_USER=<your-db-user>
DB_PASSWORD=<your-db-password>
```

---

## 2. Google Cloud Storage (GCS)

### Required Buckets
Create 2 buckets in GCP:

| Bucket Purpose | Suggested Name | Storage Class |
|----------------|----------------|---------------|
| User Datasets | `llm-platform-datasets-{project}` | Standard |
| Trained Adapters | `llm-platform-adapters-{project}` | Standard |

### Setup Steps
1. Go to [GCP Console](https://console.cloud.google.com/storage)
2. Create buckets with names above
3. Create a Service Account with "Storage Admin" role
4. Download JSON key file
5. Update `.env`:
```env
GCS_PROJECT=your-gcp-project-id
GCS_DATASETS_BUCKET=llm-platform-datasets-yourproject
GCS_ADAPTERS_BUCKET=llm-platform-adapters-yourproject
GOOGLE_APPLICATION_CREDENTIALS=C:/path/to/service-account.json
```

---

## 3. Email Alerts (Gmail SMTP)

### Gmail App Password Setup
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Step Verification (required)
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Create new app password for "Mail"
5. Copy the 16-character password

Update `.env`:
```env
EMAIL_PASSWORD=your-16-char-app-password
```

**Already configured in `monitoring_config.yaml`:**
- Sender: `mlopsproject25@gmail.com`
- Recipient: `mlopsproject25@gmail.com`

---

## 4. Your Updated .env File

Create a `.env` file with these values:

```env
# =============================================================================
# DATABASE - Update with your values
# =============================================================================
DB_HOST=localhost  # or your cloud DB host
DB_PORT=5432
DB_NAME=llm_platform
DB_USER=postgres
DB_PASSWORD=your_password_here

# =============================================================================
# AUTHENTICATION - Generate a secret key
# =============================================================================
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_generated_secret_key_here

# =============================================================================
# GOOGLE CLOUD STORAGE - Update with your GCP setup
# =============================================================================
GCS_PROJECT=your-gcp-project-id
GCS_DATASETS_BUCKET=your-datasets-bucket-name
GCS_ADAPTERS_BUCKET=your-adapters-bucket-name
GOOGLE_APPLICATION_CREDENTIALS=C:/path/to/your/service-account.json

# =============================================================================
# EMAIL ALERTS (Gmail)
# =============================================================================
EMAIL_PASSWORD=your-gmail-app-password

# =============================================================================
# DEVELOPMENT
# =============================================================================
DEBUG=true
LOG_LEVEL=INFO
ENVIRONMENT=development
```

---

## 5. Model (Already Done ✅)

Your StarCoder2-3B model is at:
```
custom-llm-finetuning-platform/model/starcoder2-3b/
```

The config already points to this path.

---

## Quick Checklist

| Item | Status | Action |
|------|--------|--------|
| PostgreSQL | ⬜ | Run `docker-compose up -d postgres` or create cloud DB |
| GCS Buckets | ⬜ | Create 2 buckets in GCP Console |
| GCS Service Account | ⬜ | Create & download JSON key |
| Gmail App Password | ⬜ | Create at Google Account settings |
| `.env` file | ⬜ | Copy from `.env.example` and fill values |
| Model | ✅ | Already at `model/starcoder2-3b/` |

---

## After Setup

Once you've completed the above, run:
```bash
# 1. Create & activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run database migrations
alembic upgrade head

# 4. Verify setup
python -c "from auth.database import engine; print('DB OK')"
```

**Reply with the values you've configured and I'll update the project files accordingly.**
