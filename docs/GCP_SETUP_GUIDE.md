# Google Cloud Setup Guide

Complete step-by-step instructions for setting up Cloud SQL (PostgreSQL) and Cloud Storage (GCS).

---

## Prerequisites

1. A Google Cloud account ([Create one here](https://console.cloud.google.com))
2. A GCP project created
3. Billing enabled on the project

---

## Part 1: Create a GCP Project (Skip if you have one)

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Click the **project dropdown** at the top (next to "Google Cloud")
3. Click **"NEW PROJECT"**
4. Enter:
   - **Project name**: `llm-finetuning-platform` (or your choice)
   - **Organization**: Leave as default
5. Click **"CREATE"**
6. Wait for project creation, then select it from the dropdown

> **Note your Project ID** - you'll need it (e.g., `llm-finetuning-platform-12345`)

---

## Part 2: Enable Required APIs

1. Go to [APIs & Services](https://console.cloud.google.com/apis/dashboard)
2. Click **"+ ENABLE APIS AND SERVICES"**
3. Search and enable these APIs:
   - **Cloud SQL Admin API**
   - **Cloud Storage API** (usually enabled by default)

---

## Part 3: Create Cloud SQL PostgreSQL Instance

### Step 1: Navigate to Cloud SQL
1. Go to [Cloud SQL](https://console.cloud.google.com/sql)
2. Click **"CREATE INSTANCE"**
3. Select **"PostgreSQL"**

### Step 2: Configure Instance
Fill in these settings:

| Setting | Value |
|---------|-------|
| **Instance ID** | `llm-platform-db` |
| **Password** | Create a strong password (save this!) |
| **Database version** | PostgreSQL 15 |
| **Cloud SQL edition** | Enterprise |
| **Region** | Choose closest to you (e.g., `us-central1`) |
| **Zonal availability** | Single zone (for dev) |

### Step 3: Machine Configuration
1. Expand **"Machine configuration"**
2. Select:
   - **Machine type**: Lightweight (1 vCPU, 3.75 GB) - ~$25/month
   - Or **Standard (2 vCPU, 8 GB)** for production

### Step 4: Storage
1. Expand **"Storage"**
2. Set:
   - **Storage type**: SSD
   - **Storage capacity**: 10 GB (can auto-increase)

### Step 5: Connections
1. Expand **"Connections"**
2. Check **"Public IP"**
3. Under **"Authorized networks"**, click **"ADD NETWORK"**
   - **Name**: `my-ip`
   - **Network**: Your IP address (find at [whatismyip.com](https://whatismyip.com))
   - Or use `0.0.0.0/0` for any IP (less secure, for dev only)

### Step 6: Create
1. Click **"CREATE INSTANCE"**
2. Wait 5-10 minutes for creation

### Step 7: Get Connection Details
Once created:
1. Click on your instance name
2. Note the **Public IP address** (e.g., `34.123.45.67`)
3. This is your `DB_HOST`

### Step 8: Create Database
1. Click **"Databases"** in left menu
2. Click **"CREATE DATABASE"**
3. Enter name: `llm_platform`
4. Click **"CREATE"**

### Your Cloud SQL Values:
```
DB_HOST=34.xxx.xxx.xxx (your instance IP)
DB_PORT=5432
DB_NAME=llm_platform
DB_USER=postgres
DB_PASSWORD=your_password_you_set
```

---

## Part 4: Create Cloud Storage Buckets

### Step 1: Navigate to Cloud Storage
1. Go to [Cloud Storage](https://console.cloud.google.com/storage)
2. Click **"CREATE BUCKET"**

### Step 2: Create Datasets Bucket
1. **Name**: `llm-platform-datasets-{your-project-id}`
   - Example: `llm-platform-datasets-myproject123`
   - Must be globally unique!
2. **Location type**: Region
3. **Location**: Same as your Cloud SQL (e.g., `us-central1`)
4. **Storage class**: Standard
5. **Access control**: Uniform
6. Click **"CREATE"**

### Step 3: Create Adapters Bucket
Repeat the same steps with:
1. **Name**: `llm-platform-adapters-{your-project-id}`
2. Same settings as above

### Your GCS Values:
```
GCS_DATASETS_BUCKET=llm-platform-datasets-yourproject
GCS_ADAPTERS_BUCKET=llm-platform-adapters-yourproject
```

---

## Part 5: Create Service Account & Download Key

### Step 1: Navigate to IAM
1. Go to [IAM & Admin > Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
2. Click **"+ CREATE SERVICE ACCOUNT"**

### Step 2: Create Account
1. **Service account name**: `llm-platform-service`
2. **Service account ID**: Auto-generated
3. **Description**: `Service account for LLM Fine-Tuning Platform`
4. Click **"CREATE AND CONTINUE"**

### Step 3: Assign Roles
1. Click **"Select a role"**
2. Add these roles (click "+ ADD ANOTHER ROLE" for each):
   - **Storage Admin** (for buckets)
   - **Cloud SQL Client** (for database)
3. Click **"CONTINUE"**
4. Click **"DONE"**

### Step 4: Download Key
1. Click on the service account you just created
2. Go to **"KEYS"** tab
3. Click **"ADD KEY"** > **"Create new key"**
4. Select **"JSON"**
5. Click **"CREATE"**
6. **Save the downloaded file** to a safe location
   - Example: `C:\Users\HP\Downloads\LLM_test\custom-llm-finetuning-platform\secrets\service-account.json`

### Your Service Account Value:
```
GOOGLE_APPLICATION_CREDENTIALS=C:\Users\HP\Downloads\LLM_test\custom-llm-finetuning-platform\secrets\service-account.json
```

---

## Part 6: Final Summary

After completing all steps, you should have:

```env
# Database (Cloud SQL)
DB_HOST=34.xxx.xxx.xxx          # Your Cloud SQL IP
DB_PORT=5432
DB_NAME=llm_platform
DB_USER=postgres
DB_PASSWORD=your_password

# Cloud Storage
GCS_PROJECT=your-project-id
GCS_DATASETS_BUCKET=llm-platform-datasets-yourproject
GCS_ADAPTERS_BUCKET=llm-platform-adapters-yourproject
GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\service-account.json
```

---

## Cost Estimate (USD/month)

| Service | Spec | Estimated Cost |
|---------|------|----------------|
| Cloud SQL | Lightweight (1 vCPU, 3.75GB, 10GB SSD) | ~$25-35 |
| Cloud Storage | Standard, 50GB | ~$1-2 |
| **Total** | | **~$30-40/month** |

> **Tip**: Use Google Cloud's free trial ($300 credit for 90 days)

---

## Quick Links

- [Cloud Console](https://console.cloud.google.com)
- [Cloud SQL](https://console.cloud.google.com/sql)
- [Cloud Storage](https://console.cloud.google.com/storage)
- [Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)
- [Billing](https://console.cloud.google.com/billing)
