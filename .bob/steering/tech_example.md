# Technology Stack: SmartExpense AI

**Frontend:** 
- React 18 with TypeScript
- IBM Carbon Design System (Carbon Components React)
- TailwindCSS for utility styling

**Backend:** 
- Python 3.12
- FastAPI for REST APIs
- Pydantic for data validation and serialization
- SQLAlchemy 2.0 (Async) for ORM

**AI & Orchestration:**
- IBM watsonx Orchestrate (Agent Development Kit)
- LLM: `groq/openai/gpt-oss-120b` for reasoning and extraction

**Database:** 
- PostgreSQL 16 (Relational data)
- Redis (Caching and rate limiting)

**Infrastructure:** 
- Docker & Docker Compose for local development
- Red Hat OpenShift for production deployment
- IBM Cloud Object Storage (S3-compatible) for receipt image storage

**Constraints & Security:**
- All APIs must require a valid JWT token (Auth0 integration).
- PII (Personally Identifiable Information) must be encrypted at rest.
- Maximum file upload size for receipts is 10MB.
- All Python code must pass `ruff` linting and `mypy` strict type checking.
