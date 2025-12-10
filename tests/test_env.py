"""Quick test script to verify environment configuration."""
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

print("=" * 50)
print("Environment Configuration Test")
print("=" * 50)

# Database
print("\n📦 Database:")
print(f"  Host: {os.getenv('DB_HOST')}")
print(f"  Port: {os.getenv('DB_PORT')}")
print(f"  Name: {os.getenv('DB_NAME')}")
print(f"  User: {os.getenv('DB_USER')}")
print(f"  Password: {'*' * len(os.getenv('DB_PASSWORD', '')) if os.getenv('DB_PASSWORD') else 'NOT SET'}")

# GCS
print("\n☁️ Google Cloud:")
print(f"  Project: {os.getenv('GCS_PROJECT')}")
print(f"  Datasets Bucket: {os.getenv('GCS_DATASETS_BUCKET')}")
print(f"  Adapters Bucket: {os.getenv('GCS_ADAPTERS_BUCKET')}")
print(f"  Credentials: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")

# Email
print("\n📧 Email:")
print(f"  Password: {'SET' if os.getenv('EMAIL_PASSWORD') else 'NOT SET'}")

# Auth
print("\n🔐 Auth:")
print(f"  Secret Key: {'SET' if os.getenv('SECRET_KEY') else 'NOT SET'}")

print("\n" + "=" * 50)
print("✅ Configuration loaded successfully!")
print("=" * 50)
