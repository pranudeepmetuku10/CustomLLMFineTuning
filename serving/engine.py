import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
from google.cloud import storage
import os
import shutil
import logging
from threading import Lock

logger = logging.getLogger(__name__)

class InferenceEngine:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(InferenceEngine, cls).__new__(cls)
                    cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
            
        self.model_name = "bigcode/starcoder2-3b"
        self.tokenizer = None
        self.base_model = None
        self.active_adapter = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.storage_client = storage.Client()
        self.initialized = True
        
    def load_base_model(self):
        """Loads the quantized base model into memory."""
        if self.base_model is not None:
            return

        logger.info(f"Loading base model {self.model_name} on {self.device}...")
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            
            # Quantization config for memory efficiency (4-bit)
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
            )
            
            self.base_model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True
            )
            logger.info("Base model loaded successfully.")
            
        except Exception as e:
            logger.error(f"Failed to load base model: {e}")
            raise e

    def download_adapter(self, gcs_path: str, local_dir: str):
        """Downloads adapter files from GCS to a local directory."""
        if os.path.exists(local_dir):
            # Check if valid adapter exists (simple check)
            if os.path.exists(os.path.join(local_dir, "adapter_config.json")):
                return
            
        os.makedirs(local_dir, exist_ok=True)
        
        # Parse GCS path
        # Expected: gs://bucket-name/path/to/adapter
        if not gcs_path.startswith("gs://"):
            raise ValueError(f"Invalid GCS path: {gcs_path}")
            
        path_parts = gcs_path.replace("gs://", "").split("/")
        bucket_name = path_parts[0]
        prefix = "/".join(path_parts[1:])
        
        logger.info(f"Downloading adapter from {gcs_path} to {local_dir}")
        
        bucket = self.storage_client.bucket(bucket_name)
        blobs = bucket.list_blobs(prefix=prefix)
        
        found = False
        for blob in blobs:
            # We only need the files relative to the model dir
            # e.g. prefix=users/../model/123/adapter_config.json
            # blob.name will be users/../model/123/adapter_config.json
            rel_path = blob.name.replace(prefix, "").lstrip("/")
            if not rel_path: 
                continue # It's the directory itself
                
            local_path = os.path.join(local_dir, rel_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            blob.download_to_filename(local_path)
            found = True
            
        if not found:
            raise ValueError(f"No adapter files found at {gcs_path}")

    def load_adapter(self, adapter_id: str, gcs_path: str):
        """Swaps the active adapter on the base model."""
        self.load_base_model() # Ensure base is loaded
        
        if self.active_adapter == adapter_id:
            return # Already loaded
            
        logger.info(f"Swapping to adapter {adapter_id}...")
        
        # Define local cache path
        local_adapter_path = os.path.join("model_cache", "adapters", adapter_id)
        self.download_adapter(gcs_path, local_adapter_path)
        
        try:
            # If we already have adapters attached, we might need to unload or swap
            # Simpler approach: Reload base model wrapper with PEFT
            # Or use PeftModel.from_pretrained to attach
            
            if isinstance(self.base_model, PeftModel):
                # Unload previous adapter to free memory/reset
                self.base_model.unload() 
                # Note: PeftModel.unload() returns the base model, but doesn't modify in-place strictly? 
                # Actually commonly we just load_adapter() on top if using standard PEFT methods
                # But simplest safe way:
                pass

            # Attach new adapter
            self.base_model = PeftModel.from_pretrained(
                self.base_model,
                local_adapter_path,
                adapter_name=adapter_id
            )
            self.active_adapter = adapter_id
            logger.info(f"Adapter {adapter_id} active.")
            
        except Exception as e:
            logger.error(f"Failed to load adapter: {e}")
            raise e

    def generate(self, prompt: str, max_new_tokens: int = 128, temperature: float = 0.2):
        """Generates code using the currently loaded model."""
        if not self.base_model:
            raise RuntimeError("Model not loaded")
            
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        
        with torch.no_grad():
            outputs = self.base_model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id
            )
            
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)
