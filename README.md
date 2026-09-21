# Sikapa Backend

FastAPI MVP for Twi-first, accessible cash-out assistance. The backend proposes intent, requires explicit confirmation, provides user-controlled Mobile Money authorization guidance, and uses a clearly marked simulation provider.

## Setup

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Use `DATABASE_URL=postgresql+asyncpg://...` for Supabase PostgreSQL. `SUPABASE_SERVICE_ROLE_KEY`, `MOMO_API_SECRET`, and `AI_API_KEY` are backend-only secrets and must never be sent to the frontend.

## Database and migrations

```powershell
alembic upgrade head
```

For a new schema revision: `alembic revision --autogenerate -m "describe change"`. Local development may create tables automatically; production uses Alembic.

## Run and test

```powershell
uvicorn app.main:app --reload
pytest
```

Open `http://localhost:8000/docs` for interactive API documentation. Health checks use `/api/v1/health`.

## Architecture

Routes delegate to services. SQLAlchemy models isolate persistence, `CashoutService` owns the state machine and ownership checks, and `MomoProvider` isolates simulation from any future official provider adapter. Communication and speech are replaceable service abstractions.

## Cash-out flow

1. Register and log in.
2. Interpret user input as a proposed intent.
3. Create a cash-out and display the confirmation message.
4. Confirm explicitly.
5. Start authorization and guide the user through the official MoMo/USSD interface.
6. Record simulation authorization only after the user completes it.
7. Generate the agent message, status, and receipt.

Simulation responses are marked with `simulation: true` and use `SIM-...` references. This project does not request, store, infer, log, or submit Mobile Money PINs, and it does not claim a real transaction occurred. A production provider must be officially documented and independently validated before being enabled.

## Frontend contract

Authenticated endpoints require `Authorization: Bearer <access_token>`. The frontend uses `cashout_id`, `status`, `simulation`, `transaction_reference`, `message`, and `instructions`; it never receives database URLs, service-role keys, provider secrets, or PIN fields. Invalid ownership returns 404, invalid state transitions return 409, and validation errors return 422.
