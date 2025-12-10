import requests
import getpass
import os
import sys

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
    print(f"Testing Inference API at {API_URL}")
    token = login()
    if not token:
        return

    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. List Trained Models
    print("\n--- Listing Trained Models ---")
    try:
        res = requests.get(f"{API_URL}/models/", headers=headers)
        if res.status_code != 200:
            print("Failed to list models:", res.text)
            return
            
        models = res.json()
        # Filter for completed models only
        ready_models = [m for m in models if m["status"] in ["COMPLETED", "SUCCEEDED"]]
        
        if not ready_models:
            print("No ready models found! Please train a model first.")
            return

        for idx, m in enumerate(ready_models):
            print(f"{idx+1}. {m['name']} (ID: {m['id']})")
            
        choice = input("\nSelect model number to use: ")
        try:
            model = ready_models[int(choice)-1]
        except (ValueError, IndexError):
            print("Invalid selection")
            return
            
    except Exception as e:
        print(f"Error listing models: {e}")
        return

    # 2. Run Inference
    print(f"\n--- Inference with '{model['name']}' ---")
    print("Enter your prompt (or 'q' to quit):")
    
    while True:
        prompt = input("\nPrompt > ")
        if prompt.lower() in ['q', 'quit', 'exit']:
            break
            
        payload = {
            "prompt": prompt,
            "max_tokens": 128,
            "temperature": 0.2
        }
        
        print("Generating...", end="", flush=True)
        try:
            res = requests.post(
                f"{API_URL}/models/{model['id']}/predict", 
                json=payload, 
                headers=headers
            )
            
            if res.status_code == 200:
                result = res.json()
                print("\n--- Generated Text ---")
                print(result["generated_text"])
                print("----------------------")
            else:
                print(f"\nFailed: {res.status_code} - {res.text}")
                
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()
