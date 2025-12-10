# Custom LLM Fine-Tuning Platform

A multi-tenant MLOps platform for fine-tuning large language models using QLoRA, built on StarCoder2-3B.

## Features

- **Multi-Tenant Architecture**: User isolation with JWT authentication
- **QLoRA Fine-Tuning**: Parameter-efficient training with 4-bit quantization
- **Per-User Adapters**: Each user's model weights stored separately
- **Dynamic Inference**: Load user-specific adapters on-demand
- **Full MLOps Pipeline**: Data versioning, experiment tracking, monitoring

## Tech Stack

| Component | Technology |
|-----------|------------|
| Base Model | StarCoder2-3B |
| Fine-Tuning | QLoRA (PEFT + bitsandbytes) |
| Database | PostgreSQL |
| API | FastAPI |
| Orchestration | Apache Airflow |
| Tracking | MLflow |
| Data Versioning | DVC |
| Monitoring | Prometheus + Grafana |

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+
- CUDA-capable GPU (recommended)
- Google Cloud account (for storage)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-org/custom-llm-finetuning-platform.git
   cd custom-llm-finetuning-platform
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   .\venv\Scripts\activate   # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Set up PostgreSQL database**
   ```bash
   # Create database
   createdb llm_platform
   
   # Run migrations
   alembic upgrade head
   ```

6. **Start the API server**
   ```bash
   uvicorn serving.api.main:app --reload
   ```

## Project Structure

```
custom-llm-finetuning-platform/
├── auth/                 # Authentication & multi-tenancy
├── configs/              # Configuration files
├── data/                 # Data pipeline
├── monitoring/           # Metrics & alerting
├── orchestration/        # Airflow DAGs & K8s
├── registry/             # Model registry
├── serving/              # API & inference
├── storage/              # Tenant storage
├── training/             # QLoRA training
├── ui/                   # Web frontend
└── tests/                # Unit & integration tests
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /auth/signup` | Create account |
| `POST /auth/login` | Get JWT token |
| `POST /api/datasets` | Upload dataset |
| `POST /api/training` | Start training job |
| `POST /v1/completions` | Generate code |

## License

MIT License - See LICENSE file for details.
