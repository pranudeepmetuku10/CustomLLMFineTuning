
import requests
import os
import json
from google.cloud import storage
from dotenv import load_dotenv

load_dotenv()

API_URL = "http://localhost:8000/api"

def check_gcs(path):
    try:
        if not path: return "No Path"
        path = path.replace("gs://", "")
        parts = path.split("/")
        bucket_name = parts[0]
        blob_name = "/".join(parts[1:]) + "/adapter_config.json"
        
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        return blob.exists()
    except Exception as e:
        return f"Error: {e}"

def main():
    # 1. Login
    print("Logging in...")
    res = requests.post(f"{API_URL}/auth/login", json={"email": "user@example.com", "password": "password123"})
    if res.status_code != 200:
        # Try asking for password if hardcoded fails, but for debug assuming default or fail
        print("Login failed with default creds. Input manually.")
        import getpass
        pwd = getpass.getpass("Password: ")
        res = requests.post(f"{API_URL}/auth/login", json={"email": "user@example.com", "password": pwd})
        
    token = res.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. List Models
    print("\n--- Fetching Models from API ---")
    res = requests.get(f"{API_URL}/models/", headers=headers)
    models = res.json()
    
    print(f"Found {len(models)} jobs in DB.\n")
    
    for m in models:
        jid = m['id']
        status = m['status']
        config = m.get('config', {})
        output_dir = config.get('output_dir')
        
        print(f"Job: {jid}")
        print(f"  Status: {status}")
        print(f"  Output Dir: {output_dir}")
        
        # 3. Indepdent Check
        if output_dir:
            exists = check_gcs(output_dir)
            print(f"  [Independent Check] adapter_config.json exists? {exists}")
        else:
            print(f"  [Independent Check] No output_dir defined config.")
        print("-" * 30)

if __name__ == "__main__":
    main()
