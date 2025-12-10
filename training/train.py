import os
import argparse
import sys
import torch
import traceback
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling,
    BitsAndBytesConfig,
    TrainerCallback
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from google.cloud import aiplatform
from email_utils import send_email, get_training_success_html, get_training_failure_html

class VertexCallback(TrainerCallback):
    """Callback to log metrics to Vertex AI Experiments"""
    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs:
            metrics = {k: v for k, v in logs.items() if isinstance(v, (int, float))}
            try:
                aiplatform.log_metrics(metrics)
            except Exception as e:
                print(f"Warning: Failed to log to Vertex: {e}")

def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tune LLM with QLoRA")
    parser.add_argument("--model_name", type=str, default="bigcode/starcoder2-3b", help="Model name or path")
    parser.add_argument("--dataset_path", type=str, required=True, help="Path to dataset")
    parser.add_argument("--output_dir", type=str, default="/gcs_output", help="Output directory")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=4, help="Batch size per device")
    parser.add_argument("--learning_rate", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--experiment_name", type=str, default=None, help="Vertex Experiment Name")
    parser.add_argument("--run_name", type=str, default=None, help="Vertex Run Name")
    parser.add_argument("--project_id", type=str, default=None, help="GCP Project ID")
    parser.add_argument("--location", type=str, default="us-central1", help="GCP Location")
    parser.add_argument("--resume_from_checkpoint", type=str, default=None, help="Checkpoint path")
    parser.add_argument("--user_email", type=str, default=None, help="User email")
    return parser.parse_args()

def preprocess_function(examples, tokenizer):
    if "text" in examples:
        texts = examples["text"]
    elif "instruction" in examples and "output" in examples:
        texts = [f"### Instruction:\n{inst}\n\n### Response:\n{out}" for inst, out in zip(examples["instruction"], examples["output"])]
    else:
        keys = list(examples.keys())
        text_key = next((k for k in ['content', 'code', 'body'] if k in keys), keys[0])
        texts = examples[text_key]
    
    result = tokenizer(texts, truncation=True, max_length=512, padding="max_length", return_tensors=None)
    result["labels"] = result["input_ids"].copy()
    return result

def main():
    args = parse_args()
    print(f"Starting training with args: {args}")
    
    if args.experiment_name and args.project_id:
        print(f"Initializing Vertex AI Experiment: {args.experiment_name} / {args.run_name}")
        aiplatform.init(project=args.project_id, location=args.location, experiment=args.experiment_name)
        if args.run_name:
            try:
                aiplatform.start_run(args.run_name)
            except Exception:
                aiplatform.start_run(args.run_name, resume=True)
            
            params = {k: v for k, v in vars(args).items() if v is not None}
            aiplatform.log_params(params)

    print(f"GPU Available: {torch.cuda.is_available()}")
    
    print("Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    
    print("Loading model...")
    bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(args.model_name, quantization_config=bnb_config, device_map="auto", trust_remote_code=True)
    model = prepare_model_for_kbit_training(model)
    model.config.use_cache = False
    
    print("Applying LoRA...")
    lora_config = LoraConfig(
        r=16, 
        lora_alpha=32, 
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], 
        lora_dropout=0.05, 
        bias="none", 
        task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, lora_config)
    
    # Enable gradient checkpointing to save memory
    model.gradient_checkpointing_enable()
    model.print_trainable_parameters()
    
    print(f"Loading dataset from {args.dataset_path}...")
    dataset = None
    is_split = False
    base_path = args.dataset_path.rstrip("/")
    
    if not (base_path.endswith(".json") or base_path.endswith(".jsonl")):
        try:
            print(f"Attempting to load split files from {base_path}...")
            data_files = {
                "train": f"{base_path}/train.json", 
                "validation": f"{base_path}/val.json",
                "test": f"{base_path}/test.json"
            }
            dataset = load_dataset("json", data_files=data_files)
            print("Successfully loaded pre-split dataset.")
            is_split = True
        except Exception as e:
            print(f"Failed to load splits: {e}. Fallback to single file.")
            dataset = None

    if not dataset:
        data_files = {"train": args.dataset_path}
        dataset = load_dataset("json", data_files=data_files, split="train")

    test_dataset = None
    if is_split:
        train_dataset = dataset["train"]
        eval_dataset = dataset["validation"]
        if "test" in dataset:
            test_dataset = dataset["test"]
    else:
        print("Splitting dataset (10% validation)...")
        dataset = dataset.train_test_split(test_size=0.1)
        train_dataset = dataset["train"]
        eval_dataset = dataset["test"]

    print(f"Training samples: {len(train_dataset)}, Eval samples: {len(eval_dataset)}")
    
    tokenized_train = train_dataset.map(lambda x: preprocess_function(x, tokenizer), batched=True, remove_columns=train_dataset.column_names)
    tokenized_eval = eval_dataset.map(lambda x: preprocess_function(x, tokenizer), batched=True, remove_columns=eval_dataset.column_names)
    
    tokenized_test = None
    if test_dataset:
        print(f"Test samples: {len(test_dataset)}")
        tokenized_test = test_dataset.map(lambda x: preprocess_function(x, tokenizer), batched=True, remove_columns=test_dataset.column_names)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        fp16=True,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        optim="paged_adamw_8bit",
        lr_scheduler_type="cosine",
        report_to=[]  # We use custom callback
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
        eval_dataset=tokenized_eval,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
        callbacks=[VertexCallback()] if args.experiment_name else []
    )
    
    print("Starting training...")
    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)
    
    
    # NEW: Save to local directory first, then upload
    local_output_dir = "/tmp/model_output"
    print(f"Saving model locally to {local_output_dir}...")
    trainer.save_model(local_output_dir)
    tokenizer.save_pretrained(local_output_dir)
    
    metrics = trainer.evaluate()
    print(f"Validation metrics: {metrics}")
    
    if tokenized_test:
        print("Running evaluation on test set...")
        test_metrics = trainer.evaluate(tokenized_test, metric_key_prefix="test")
        print(f"Test metrics: {test_metrics}")
        metrics.update(test_metrics)

    # Upload to GCS
    print(f"Uploading model artifacts to {args.output_dir}...")
    try:
        destination_blob_prefix = args.output_dir.replace("gs://", "").split("/", 1)[1]
        bucket_name = args.output_dir.replace("gs://", "").split("/")[0]
        
        from google.cloud import storage
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        
        for root, dirs, files in os.walk(local_output_dir):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, local_output_dir)
                blob_path = f"{destination_blob_prefix}/{relative_path}"
                
                blob = bucket.blob(blob_path)
                blob.upload_from_filename(local_path)
                print(f"Uploaded {file} to gs://{bucket_name}/{blob_path}")
                
        print("Upload complete.")
    except Exception as e:
        print(f"Failed to upload to GCS: {e}")
        # Build failure email content if needed
        raise e

    if args.experiment_name and args.project_id:
        try:
            import math
            perimeter = math.exp(metrics.get("eval_loss", 0))
            aiplatform.log_metrics({"perplexity": perimeter, **metrics})
            aiplatform.end_run()
        except:
            pass
            
    if args.user_email:
        try:
            job_id = args.run_name.replace("run-", "") if args.run_name else "unknown"
            html = get_training_success_html(args.model_name, job_id, metrics)
            send_email("Training Complete", html, args.user_email)
        except Exception as e:
            print(f"Failed to send success email: {e}")

    print("Done!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Training Failed: {e}")
        traceback.print_exc()
        user_email = None
        model_name = "model"
        run_name = "unknown"
        try:
            if "--user_email" in sys.argv:
                idx = sys.argv.index("--user_email")
                if idx + 1 < len(sys.argv):
                    user_email = sys.argv[idx + 1]
            if "--model_name" in sys.argv:
                idx = sys.argv.index("--model_name")
                if idx + 1 < len(sys.argv):
                    model_name = sys.argv[idx + 1]
        except:
            pass
        if user_email:
            try:
                html = get_training_failure_html(model_name, run_name, str(e))
                send_email("Training Failed", html, user_email)
            except:
                pass
        sys.exit(1)
