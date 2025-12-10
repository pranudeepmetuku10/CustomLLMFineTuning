import requests
import getpass
import os

API_URL = "http://localhost:8000/api"

def login():
    print("--- Login ---")
    email = input("Email: ")
    password = getpass.getpass("Password: ")
    
    try:
        res = requests.post(f"{API_URL}/auth/login", json={"email": email, "password": password})
        if res.status_code != 200:
            print(f"Login failed: {res.status_code} - {res.text}")
            return None
        return res.json()["access_token"]
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to API at {API_URL}. Is it running?")
        return None

def main():
    print(f"Testing Training API at {API_URL}")
    token = login()
    if not token:
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. List Processed Datasets
    print("\n--- Listing Processed Datasets ---")
    res = requests.get(f"{API_URL}/datasets/", headers=headers)
    if res.status_code != 200:
        print("Failed to list datasets:", res.text)
        return
        
    datasets = res.json()["datasets"]
    # Filter for processed datasets only
    processed_datasets = [d for d in datasets if d["is_processed"]]
    
    if not processed_datasets:
        print("No processed datasets found! Please upload and process a dataset first.")
        return

    for idx, d in enumerate(processed_datasets):
        print(f"{idx+1}. {d['name']} (ID: {d['id']}) - {d['num_samples']} samples")
        
    choice = input("\nSelect dataset number to train on: ")
    try:
        ds = processed_datasets[int(choice)-1]
    except (ValueError, IndexError):
        print("Invalid selection")
        return

    # 2. Configure Training
    print(f"\n--- Configuring Training for '{ds['name']}' ---")
    model = input("Model Name [bigcode/starcoder2-3b]: ") or "bigcode/starcoder2-3b"
    epochs = input("Epochs [1]: ") or "1"
    batch_size = input("Batch Size [2]: ") or "2"
    
    payload = {
        "dataset_id": ds['id'],
        "model_name": model,
        "epochs": int(epochs),
        "batch_size": int(batch_size)
    }
    
    # 3. Trigger Training
    print(f"\nTriggering training job...")
    res = requests.post(f"{API_URL}/models/train", json=payload, headers=headers)
    
    if res.status_code == 200:
        data = res.json()
        print("\nSUCCESS! Training started.")
        print(f"Job ID: {data.get('job_id')}")
        print(f"Run Name: {data.get('run_name')}")
        print(f"Status: {data.get('status')}")
        print("\nYou will receive an email notification when it completes.")
    else:
        print(f"\nFAILED: {res.status_code}")
        print(res.text)

if __name__ == "__main__":
    main()
