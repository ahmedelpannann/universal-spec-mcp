# Project Structure: SmartExpense AI

**File Organization:**
```
smartexpense/
├── .bob/                  # IBM Bob configuration and steering
├── .specs/                # Generated feature specifications
├── backend/
│   ├── src/
│   │   ├── api/           # FastAPI routers and endpoints
│   │   ├── core/          # Config, security, and database setup
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── schemas/       # Pydantic validation schemas
│   │   └── services/      # Business logic and watsonx integration
│   └── tests/             # Pytest unit and integration tests
├── frontend/
│   ├── src/
│   │   ├── components/    # Reusable Carbon React components
│   │   ├── pages/         # Page-level components
│   │   └── hooks/         # Custom React hooks
│   └── tests/             # Jest/React Testing Library tests
└── agents/                # watsonx Orchestrate ADK YAML and flows
```

**Naming Conventions:**
- **Python Files:** `snake_case.py` (e.g., `expense_service.py`)
- **React Files:** `PascalCase.tsx` (e.g., `ReceiptUploader.tsx`)
- **Database Tables:** Plural `snake_case` (e.g., `expense_reports`)
- **API Endpoints:** Plural nouns, kebab-case (e.g., `/api/v1/expense-reports`)

**Import Patterns:**
- Python: Use absolute imports starting from the `src` directory (e.g., `from src.models.expense import Expense`). Never use relative imports (`..`).
- React: Use absolute imports with the `@/` alias (e.g., `import { Button } from '@/components/ui'`).
