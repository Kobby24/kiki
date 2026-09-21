# Sikapa Backend Swagger Testing Guide

This guide is based on the current code in this repository. It is written for testing through FastAPI Swagger UI at:

```text
http://localhost:8000/docs
```

The current backend is a simulation-first MVP. It does not connect to a live Mobile Money provider and it never accepts or submits a Mobile Money PIN.

## 1. Actual Endpoint Inventory

There are no query parameters in the current API. The `cashout_id` path parameter is a UUID. Protected endpoints use the `Authorization: Bearer <access_token>` header.

| Method | Endpoint | Auth required | Swagger visibility | Purpose |
|---|---|---:|---|---|
| GET | `/` | No | Visible | API information |
| GET | `/api/v1/health` | No | Visible | Health check |
| POST | `/api/v1/auth/register` | No | Visible | Create a user |
| POST | `/api/v1/auth/login` | No | Visible | JSON login and JWT creation |
| GET | `/api/v1/auth/me` | Yes | Visible | Return the current user |
| POST | `/api/v1/auth/token` | No | Hidden | OAuth2 form-login compatibility route |
| POST | `/api/v1/intent/interpret` | No | Visible | Interpret a proposed intent |
| POST | `/api/v1/cashout` | Yes | Visible | Create a cash-out request |
| GET | `/api/v1/cashout` | Yes | Visible | List the current user's cash-outs |
| GET | `/api/v1/cashout/{cashout_id}` | Yes | Visible | Get one owned cash-out |
| POST | `/api/v1/cashout/{cashout_id}/confirm` | Yes | Visible | Confirm or cancel a cash-out |
| POST | `/api/v1/cashout/{cashout_id}/authorization/start` | Yes | Visible | Return user-controlled authorization instructions |
| POST | `/api/v1/cashout/{cashout_id}/authorization/status` | Yes | Visible | Record simulated authorization result |
| POST | `/api/v1/cashout/{cashout_id}/communication` | Yes | Visible | Generate the agent-facing message |
| GET | `/api/v1/cashout/{cashout_id}/status` | Yes | Visible | Return cash-out status |
| GET | `/api/v1/cashout/{cashout_id}/receipt` | Yes | Visible | Return a completed receipt |

`/api/v1/auth/token` is implemented with `include_in_schema=False`, so it does not appear in `/docs`. It accepts `application/x-www-form-urlencoded` fields named `username` and `password`; it is not required for the reliable Swagger workflow below.

## 2. Prerequisites

### Start the backend

From PowerShell in the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

If PowerShell blocks activation, run the executable directly:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Expected URLs:

```text
API root:  http://localhost:8000/
Swagger:   http://localhost:8000/docs
ReDoc:     http://localhost:8000/redoc
Health:    http://localhost:8000/api/v1/health
```

### Database requirements

With no `.env` file, the application uses:

```text
sqlite+aiosqlite:///./sikapa.db
```

In the default `development` environment, startup creates the local tables automatically. No seed data is required. For a clean repeatable test, stop the server, remove `sikapa.db`, and start it again. Do not remove a production database.

For Supabase/PostgreSQL, set `DATABASE_URL` in `.env`, for example:

```text
DATABASE_URL=postgresql+asyncpg://<backend-only-credentials>
```

The current application does not use `SUPABASE_URL`, `SUPABASE_ANON_KEY`, or `SUPABASE_SERVICE_ROLE_KEY` in its request path. Supabase is therefore not required for local Swagger testing. The service-role key must never be placed in Swagger requests or frontend code.

For a database managed by Alembic, apply the migration before starting the API:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Local development startup may also call `create_all`; production database setup should use Alembic.

### Current environment variables

The settings actually read by the application are:

```text
APP_NAME                  optional, defaults to Sikapa API
ENVIRONMENT               optional, defaults to development
DEBUG                     optional, defaults to false
DATABASE_URL              optional, defaults to local SQLite
JWT_SECRET_KEY            strongly recommended; change the development default
JWT_ALGORITHM             optional, defaults to HS256
ACCESS_TOKEN_EXPIRE_MINUTES optional, defaults to 60
MOMO_MODE                 optional, defaults to simulation
CORS_ORIGINS              optional comma-separated origins
INTENT_CONFIDENCE_THRESHOLD optional; currently not applied by the intent route
```

`MOMO_MODE=simulation` is the only provider mode implemented by the cash-out routes. A live provider is not available.

## 3. Swagger Authentication

### Reliable method: JSON login, then Bearer token

The current `/api/v1/auth/login` endpoint expects JSON, not OAuth2 form data.

1. Open `POST /api/v1/auth/register`.
2. Click **Try it out**.
3. Use the registration body in the Test Data section.
4. Click **Execute** and copy the returned `id` if needed.
5. Open `POST /api/v1/auth/login`.
6. Click **Try it out**.
7. Enter the JSON login body.
8. Click **Execute**.
9. Copy the `access_token` from the response.
10. Click the **Authorize** button with the lock icon near the top of Swagger.
11. Enter the token in the Bearer credential field. If the dialog displays a value field, enter `Bearer <access_token>`; if it labels the scheme as OAuth2 and asks for credentials instead, use the limitation note below.
12. Click **Authorize**, then **Close**.
13. Protected operations should now include the `Authorization` header when executed.

### Current Swagger OAuth2 limitation

`get_current_user` uses `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`, so Swagger describes an OAuth2 password scheme whose token URL is `/api/v1/auth/login`. However, `/api/v1/auth/login` is implemented as a JSON endpoint. Swagger's OAuth2 password dialog sends form data, so its automatic **Authorize** exchange can return `422`.

This does not mean JSON login is broken. The reliable test is to obtain the JWT from the JSON login endpoint and provide it as a Bearer token. If the Swagger UI in the installed FastAPI version does not allow pasting a bearer token for this scheme, protected requests cannot be completed entirely through the current Authorize dialog. This is a documentation/auth-scheme mismatch in the current implementation.

## 4. Safe Test Data

Use fake data only:

```json
{
  "email": "sikapa.swagger@example.com",
  "password": "TestPassword123!",
  "phone_number": "0240000000",
  "preferred_language": "tw"
}
```

Use a fresh email if the account already exists. Never use a real Mobile Money PIN, real payment credentials, or a real financial account.

Useful identifiers:

```text
{access_token} = login response.access_token
{cashout_id}   = create cash-out response.id
```

## 5. Public Endpoint Tests

### GET `/`

Purpose: returns links to the API documentation and health endpoint.

Steps:

1. Expand `GET /`.
2. Click **Try it out**.
3. Click **Execute**.

Expected result: `200 OK`.

```json
{
  "service": "sikapa-api",
  "docs": "/docs",
  "health": "/api/v1/health"
}
```

Failure test: this endpoint has no request input and no expected application-level failure case.

### GET `/api/v1/health`

Purpose: confirms that the API process is responding.

Steps:

1. Expand `GET /api/v1/health`.
2. Click **Try it out**.
3. Click **Execute**.

Expected result: `200 OK`.

```json
{
  "status": "ok",
  "service": "sikapa-api",
  "environment": "development"
}
```

The environment value reflects `ENVIRONMENT` in `.env`.

### POST `/api/v1/intent/interpret`

Purpose: converts input into a proposed cash-out intent. It does not create a cash-out and cannot authorize a transaction.

This endpoint is public and needs no token.

#### Structured intent

Request:

```json
{
  "input_type": "structured",
  "language": "tw",
  "amount": 100
}
```

Expected: `200 OK`.

```json
{
  "intent": "cash_out",
  "amount": 100,
  "currency": "GHS",
  "language": "tw",
  "confidence": 0.99,
  "requires_confirmation": true,
  "requires_clarification": false
}
```

#### Twi text input

Request:

```json
{
  "input_type": "text",
  "text": "Me pɛ sɛ meyi sidi ɔha.",
  "language": "tw"
}
```

Expected: `200 OK`, with `intent: "cash_out"`, `amount: 100`, confidence `0.94`, and `requires_confirmation: true`.

#### Missing amount / clarification

Request:

```json
{
  "input_type": "text",
  "text": "Me pɛ sɛ meyi sika.",
  "language": "tw"
}
```

Expected: `200 OK`, with `intent: null`, `amount: null`, `confidence: 0.0`, and `requires_clarification: true`. The current implementation does not return a 4xx for an unclear intent.

#### Ambiguous input

Request:

```json
{
  "input_type": "text",
  "text": "Hello",
  "language": "tw"
}
```

Expected: `200 OK` with `requires_clarification: true`.

#### Unsupported language behavior

Request:

```json
{
  "input_type": "text",
  "text": "I want to cash out 100",
  "language": "fr"
}
```

Expected: `200 OK`. The schema accepts any 2-10 character language code; the service still returns a proposed cash-out intent. Language support is not actually restricted, and communication falls back to English for languages other than `tw`.

#### Invalid input type

Request:

```json
{
  "input_type": "voice_note",
  "text": "cash out 100",
  "language": "en"
}
```

Expected: `422 Unprocessable Entity`, because `input_type` must be `speech`, `text`, `phrase`, `icon`, or `structured`.

Other validation tests: omit `input_type` for `422`; use `amount: 0` or a negative amount for `422`; use text longer than 500 characters for `422`.

## 6. Authentication Lifecycle

### POST `/api/v1/auth/register`

Steps:

1. Expand the endpoint and click **Try it out**.
2. Enter:

```json
{
  "email": "sikapa.swagger@example.com",
  "password": "TestPassword123!",
  "phone_number": "0240000000",
  "preferred_language": "tw"
}
```

3. Click **Execute**.

Expected: `201 Created`.

```json
{
  "id": "<user UUID>",
  "email": "sikapa.swagger@example.com",
  "phone_number": "0240000000",
  "preferred_language": "tw"
}
```

The password hash is never returned.

Duplicate test: execute the same request again. Expected: `409 Conflict` with an HTTP error envelope similar to:

```json
{
  "detail": {
    "error": "EMAIL_EXISTS",
    "message": "An account with this email already exists."
  }
}
```

Validation tests: malformed email or a password shorter than 8 characters returns `422`. The current registration schema does not forbid arbitrary extra fields, so do not interpret ignored extra fields as supported API fields.

### POST `/api/v1/auth/login`

Steps:

1. Expand and click **Try it out**.
2. Enter:

```json
{
  "email": "sikapa.swagger@example.com",
  "password": "TestPassword123!"
}
```

3. Execute and copy `access_token`.

Expected: `200 OK`.

```json
{
  "access_token": "<JWT>",
  "token_type": "bearer"
}
```

Save the JWT as `{access_token}`. Its default expiry is 60 minutes.

Wrong password test: use `WrongPassword123!`. Expected: `401 Unauthorized`.

```json
{
  "detail": {
    "error": "INVALID_CREDENTIALS",
    "message": "Email or password is incorrect."
  }
}
```

### GET `/api/v1/auth/me`

Authorize first, then:

1. Expand the endpoint.
2. Click **Try it out**.
3. Execute.

Expected: `200 OK` with the authenticated user's `id`, `email`, `phone_number`, and `preferred_language`.

Without a token: expected `401 Unauthorized`. With `Bearer not-a-real-token`: expected `401 Unauthorized` with `UNAUTHENTICATED`.

### POST `/api/v1/auth/token` (hidden)

This route is implemented but excluded from Swagger's OpenAPI schema. It expects form data, not JSON:

```text
username=sikapa.swagger@example.com
password=TestPassword123!
```

It is not available as an operation in `/docs`, so it cannot be tested through the current Swagger UI. It can be called with an HTTP client using `Content-Type: application/x-www-form-urlencoded`. The visible JSON `/login` route is the recommended test path.

## 7. Cash-Out End-to-End Test

All endpoints in this section require authorization. Create `{access_token}` through login and use it as a Bearer token. Create `{cashout_id}` from the response to step 1.

### Step 1: Create a cash-out

Endpoint: `POST /api/v1/cashout`

Body:

```json
{
  "amount": 100,
  "currency": "GHS",
  "language": "tw",
  "input_method": "structured"
}
```

Expected: `201 Created`.

Important response:

```json
{
  "id": "<cashout UUID>",
  "amount": 100,
  "currency": "GHS",
  "status": "awaiting_confirmation",
  "language": "tw",
  "simulation": true,
  "transaction_reference": null,
  "message": "<confirmation message>",
  "requires_confirmation": true
}
```

Copy `id` as `{cashout_id}`. The current implementation creates the row with `simulation: true` and does not automatically interpret intent.

Failure tests:

- No Bearer token: `401`.
- Amount `0`, negative, or greater than `100000`: `422`.
- Currency `"ghs"` or `"Ghana"`: `422`; currency must be exactly three uppercase letters.
- Input method `"voice_note"`: `422`.
- Add `"pin": "1234"`: `422`; the cash-out schema forbids extra fields, including PIN-like fields.

### Step 2: List cash-outs

Endpoint: `GET /api/v1/cashout`

No body or query parameters.

Expected: `200 OK` with a list containing only the authenticated user's cash-outs. A new cash-out should show `awaiting_confirmation`.

Failure test: no token returns `401`.

### Step 3: Get one cash-out

Endpoint: `GET /api/v1/cashout/{cashout_id}`

Enter `{cashout_id}` from step 1 and execute.

Expected: `200 OK` with the cash-out object.

Invalid UUID such as `not-a-uuid`: `422`.

A valid UUID belonging to no record, or belonging to another user, returns `404`:

```json
{
  "detail": {
    "error": "CASHOUT_NOT_FOUND",
    "message": "Cash-out request not found."
  }
}
```

### Step 4: Confirm the request

Endpoint: `POST /api/v1/cashout/{cashout_id}/confirm`

Body:

```json
{
  "confirmed": true
}
```

Expected: `200 OK` and `status: "awaiting_authorization"`.

Although the service internally passes through `confirmed`, the API commits the request in one call and the returned persistent status is `awaiting_authorization`.

To cancel instead, use:

```json
{
  "confirmed": false
}
```

Expected: `200 OK` and `status: "cancelled"`.

Invalid transition test: execute confirmation again after the request is already awaiting authorization or completed. Expected: `409 Conflict` with `INVALID_STATE_TRANSITION`.

### Step 5: Start authorization guidance

Endpoint: `POST /api/v1/cashout/{cashout_id}/authorization/start`

No request body.

Expected: `200 OK`:

```json
{
  "cashout_id": "<cashout UUID>",
  "status": "awaiting_authorization",
  "authorization_method": "user_momo_ussd",
  "instructions": [
    "Di Mobile Money interface no akwankyerɛ akyi.",
    "Wo ara na ɛsɛ sɛ wosi tua no so dua.",
    "Mma Sikapa obiara wo PIN."
  ],
  "simulation": true
}
```

No PIN is requested. Follow the instructions only as a demo concept; no real MoMo/USSD action is performed by this backend.

Invalid state test: call this before confirmation or after cancellation. Expected: `409 Conflict` with `INVALID_STATE_TRANSITION`.

### Step 6: Record simulated authorization

Endpoint: `POST /api/v1/cashout/{cashout_id}/authorization/status`

Body:

```json
{
  "status": "authorized"
}
```

Expected: `200 OK` with:

```json
{
  "status": "simulated",
  "simulation": true,
  "transaction_reference": "SIM-<generated reference>"
}
```

The service internally transitions through `authorized`, `processing`, and `completed`, then stores `simulated` because the provider is the simulation provider. Copy `transaction_reference` if you need to display it, but later endpoints use `{cashout_id}`.

Supported body values are only `authorized`, `cancelled`, and `failed`.

Cancellation test: create a fresh cash-out, confirm it, and submit `{"status":"cancelled"}` while it is awaiting authorization. Expected: `200 OK` with `status: "cancelled"`.

Failure behavior: `{"status":"failed"}` validates as a request, but the current state machine does not permit a direct `awaiting_authorization -> failed` transition, so it returns `409`. There is no public API operation that leaves a cash-out in `processing`; therefore a successful failed-provider flow cannot currently be reached through Swagger.

### Step 7: Generate agent communication

Endpoint: `POST /api/v1/cashout/{cashout_id}/communication`

No request body.

Expected: `200 OK`:

```json
{
  "cashout_id": "<cashout UUID>",
  "language": "tw",
  "text": "Mepa wo kyɛw, ɔpɛ sɛ ogye GHS 100.00 fi ne Mobile Money so.",
  "message_type": "agent_message",
  "cashout_amount": 100,
  "audio_reference": null
}
```

The endpoint currently does not require a completed or confirmed state, although the recommended demo order is to call it after simulated completion. A nonexistent or non-owned `{cashout_id}` returns `404`.

### Step 8: Check status

Endpoint: `GET /api/v1/cashout/{cashout_id}/status`

Expected after step 6:

```json
{
  "cashout_id": "<cashout UUID>",
  "status": "simulated",
  "simulation": true
}
```

### Step 9: Retrieve the receipt

Endpoint: `GET /api/v1/cashout/{cashout_id}/receipt`

Expected after step 6: `200 OK`.

```json
{
  "reference": "SIM-<generated reference>",
  "amount": 100,
  "currency": "GHS",
  "status": "simulated",
  "date": "<ISO timestamp>",
  "simulation": true
}
```

Before completion, the endpoint returns `409 Conflict`:

```json
{
  "detail": {
    "error": "RECEIPT_UNAVAILABLE",
    "message": "A receipt is available after completion."
  }
}
```

The receipt contains no PIN, password, API key, or authorization secret.

## 8. State Transition Tests

### Reachable successful flow

The actual API-visible sequence is:

```text
awaiting_confirmation
        |
        | POST /confirm {"confirmed": true}
        v
awaiting_authorization
        |
        | POST /authorization/status {"status": "authorized"}
        v
simulated
```

Internally, the authorization operation passes through `authorized`, `processing`, and `completed`, but the final persisted response is `simulated`.

### Reachable cancellation flow

```text
awaiting_confirmation --confirm false--> cancelled
awaiting_authorization --authorization status cancelled--> cancelled
```

### Invalid transitions to test

Use a fresh cash-out for each case where needed:

| Test | Operation | Expected |
|---|---|---|
| Confirm completed request | POST `/confirm` with `confirmed: true` after simulated completion | `409 INVALID_STATE_TRANSITION` |
| Start authorization before confirmation | POST `/authorization/start` immediately after creation | `409` |
| Authorize before confirmation | POST `/authorization/status` immediately after creation | `409` |
| Authorize cancelled request | Cancel, then POST `/authorization/status` with `authorized` | `409` |
| Confirm cancelled request | Cancel, then POST `/confirm` again | `409` |
| Receipt before completion | GET `/receipt` after creation | `409 RECEIPT_UNAVAILABLE` |
| Nonexistent cash-out | Any protected cash-out route with a random UUID | `404 CASHOUT_NOT_FOUND` |
| Malformed UUID | Any `{cashout_id}` route with `abc` | `422` |

## 9. Simulation Mode Verification

The default setting is `MOMO_MODE=simulation`, and the current cash-out route always constructs `SimulationMomoProvider` directly. Complete the end-to-end sequence and verify:

- Creation returns `simulation: true`.
- Authorization instructions return `simulation: true`.
- Authorization completion returns `status: "simulated"`.
- A `SIM-...` transaction reference is generated.
- Status returns `simulation: true`.
- Receipt returns `status: "simulated"` and `simulation: true`.
- No external MoMo service is called.
- No PIN is requested, stored, inferred, or submitted.

The current provider factory exists but is not used by the cash-out route. Changing `MOMO_MODE` to a non-simulation value does not enable a live provider; an official provider adapter is unfinished.

## 10. Ownership and Security Tests

### No token

Try `GET /api/v1/cashout` or `GET /api/v1/auth/me` without clicking **Authorize**. Expected: `401 Unauthorized`.

### Invalid token

Authorize with `Bearer definitely-not-a-real-token`, then call `GET /api/v1/auth/me`. Expected: `401 Unauthorized` with:

```json
{
  "detail": {
    "error": "UNAUTHENTICATED",
    "message": "Invalid authentication credentials."
  }
}
```

### User ownership

1. Register and log in as User A with `sikapa.a@example.com`.
2. Authorize with User A's token.
3. Create a cash-out and copy `{cashout_id}`.
4. Log in as User B with `sikapa.b@example.com`.
5. Replace the Swagger Bearer token with User B's token.
6. Call `GET /api/v1/cashout/{cashout_id}` using User A's ID.

Expected: `404 CASHOUT_NOT_FOUND`, not `403`. The service intentionally filters by both cash-out ID and current user ID, so another user's record is indistinguishable from a nonexistent record.

Repeat with `/status`, `/receipt`, `/communication`, `/confirm`, and authorization routes. They use the same ownership lookup and should also return `404`.

### PIN protection

There is no PIN field in any request schema. For `POST /api/v1/cashout`, add:

```json
{
  "amount": 100,
  "pin": "1234"
}
```

Expected: `422` because extra fields are forbidden by `CashoutCreate`. Do not use a real PIN in this test.

## 11. Validation and Not-Found Tests

| Endpoint | Invalid test | Expected |
|---|---|---|
| Register | Omit `email` | `422` |
| Register | Password fewer than 8 characters | `422` |
| Register | Malformed email | `422` |
| Login | Omit `password` | `422` |
| Intent | Omit `input_type` | `422` |
| Intent | Invalid `input_type` | `422` |
| Intent | Amount `0` or negative | `422` |
| Cash-out create | Missing `amount` | `422` |
| Cash-out create | Amount `0`, negative, or over `100000` | `422` |
| Cash-out create | Lowercase currency | `422` |
| Cash-out create | Unsupported `input_method` | `422` |
| Cash-out create | Extra `pin` field | `422` |
| Cash-out path | `cashout_id=not-a-uuid` | `422` |
| Any owned cash-out | Valid random UUID | `404` |
| Confirm | Missing `confirmed` | `422` |
| Authorization status | `status=unknown` | `422` |
| Receipt | Incomplete request | `409` |

Validation errors use FastAPI's standard shape:

```json
{
  "detail": [
    {
      "loc": ["body", "amount"],
      "msg": "Input should be greater than 0",
      "type": "greater_than"
    }
  ]
}
```

The exact validation message can vary slightly with the installed Pydantic version; the HTTP status and location are the important checks.

Application errors use FastAPI's HTTP exception envelope:

```json
{
  "detail": {
    "error": "ERROR_CODE",
    "message": "Human-readable message."
  }
}
```

## 12. Database Verification

### Local SQLite

The local database file is `sikapa.db`. Do not expose it or commit credentials. A developer can inspect it with a SQLite viewer after stopping the server.

Expected persistence:

| Swagger operation | Expected database effect |
|---|---|
| Register | Row in `users`; only `password_hash`, never the plaintext password |
| Create cash-out | Row in `cashout_requests` with `awaiting_confirmation` and `simulation=true` |
| Confirm true | `status=awaiting_authorization`, `user_confirmed=true` |
| Confirm false | `status=cancelled`, `user_confirmed=false` |
| Start authorization | `authorization_status=started` |
| Authorization authorized | `authorization_status=authorized`, `transaction_reference=SIM-...`, `status=simulated` |
| Authorization cancelled | `authorization_status=cancelled`, `status=cancelled` |
| Communication | Row in `communications`; `agent_message` updated on the cash-out |

### Supabase/PostgreSQL

When `DATABASE_URL` points to Supabase PostgreSQL and the migration is applied, inspect the same tables in the Supabase SQL editor. Use backend-only database credentials in `.env`; never put `DATABASE_URL` or the service-role key into Swagger or frontend code.

The current repository does not create Supabase Auth users or use Supabase Storage. Authentication and persistence are handled by this FastAPI application and SQLAlchemy.

## 13. Complete Swagger Checklist

- [ ] Start the API and open `/docs`
- [ ] GET `/`
- [ ] GET `/api/v1/health`
- [ ] Register a user
- [ ] Duplicate registration returns `409`
- [ ] Login with JSON
- [ ] Copy `{access_token}`
- [ ] Authorize with Bearer token, noting the OAuth2 dialog limitation
- [ ] GET `/api/v1/auth/me`
- [ ] `/me` without token returns `401`
- [ ] `/me` with invalid token returns `401`
- [ ] Intent structured input
- [ ] Intent Twi text input
- [ ] Intent missing amount requests clarification
- [ ] Intent invalid input type returns `422`
- [ ] Create cash-out
- [ ] Copy `{cashout_id}`
- [ ] List cash-outs
- [ ] Get cash-out
- [ ] Confirm cash-out
- [ ] Start authorization
- [ ] Record simulated authorization
- [ ] Verify `simulation: true`
- [ ] Verify `SIM-...` transaction reference
- [ ] Generate agent communication
- [ ] Check status
- [ ] Retrieve receipt
- [ ] Cancel a separate cash-out
- [ ] Test invalid state transition
- [ ] Test invalid cash-out UUID
- [ ] Test nonexistent cash-out
- [ ] Test User A/User B ownership
- [ ] Test extra PIN field is rejected
- [ ] Test receipt before completion
- [ ] Test validation errors
- [ ] Test hidden `/auth/token` limitation

## 14. Short Hackathon Demo Script

Use a fresh fake email and one amount, such as GHS 100.

```text
STEP 1 — Start the server
PowerShell: .venv\Scripts\python.exe -m uvicorn app.main:app --reload
Open: http://localhost:8000/docs

STEP 2 — Register
POST /api/v1/auth/register
Use the fake registration body.

STEP 3 — Login
POST /api/v1/auth/login
Copy response.access_token as {access_token}.

STEP 4 — Authorize requests
Click Swagger Authorize and provide the Bearer token.
If the OAuth2 dialog attempts form login against /auth/login and returns 422,
use the JSON-login token/manual Bearer workflow described above.

STEP 5 — Interpret intent
POST /api/v1/intent/interpret
Body: {"input_type":"text","text":"Me pɛ sɛ meyi sidi ɔha.","language":"tw"}
Show cash_out, amount 100, and requires_confirmation true.

STEP 6 — Create cash-out
POST /api/v1/cashout
Body: {"amount":100,"currency":"GHS","language":"tw","input_method":"structured"}
Copy response.id as {cashout_id}.

STEP 7 — Confirm
POST /api/v1/cashout/{cashout_id}/confirm
Body: {"confirmed":true}
Show status awaiting_authorization.

STEP 8 — Start user-controlled authorization
POST /api/v1/cashout/{cashout_id}/authorization/start
Show the Twi instructions and the explicit no-PIN instruction.

STEP 9 — Simulate authorization
POST /api/v1/cashout/{cashout_id}/authorization/status
Body: {"status":"authorized"}
Show status simulated, simulation true, and the SIM- reference.

STEP 10 — Generate agent message
POST /api/v1/cashout/{cashout_id}/communication
Show the Twi agent-facing message and amount.

STEP 11 — Check status
GET /api/v1/cashout/{cashout_id}/status
Show simulated.

STEP 12 — Retrieve receipt
GET /api/v1/cashout/{cashout_id}/receipt
Show reference, amount, status, date, and simulation=true.
```

## 15. Current Limitations / Blocked Tests

1. **Swagger OAuth2 authorization mismatch:** the security scheme points to `/api/v1/auth/login`, but that route accepts JSON while Swagger's OAuth2 password exchange sends form data. JSON login works; automatic OAuth2 authorization may return `422`.
2. **Hidden form token route:** `/api/v1/auth/token` is implemented but excluded from `/docs`, so it cannot be exercised from the generated Swagger operation list.
3. **No live Mobile Money provider:** the current route always uses `SimulationMomoProvider`. No real withdrawal is initiated.
4. **No externally verified failed state:** the public flow completes directly to `simulated`; there is no endpoint that leaves a request in `processing`, so a provider-failure transition cannot be demonstrated through Swagger. Submitting `failed` from `awaiting_authorization` returns `409`.
5. **Supabase is optional for local testing:** the default SQLite database is sufficient. Supabase testing requires a valid backend-only `DATABASE_URL` and an applied migration.
6. **No seed data:** every user and cash-out used in the guide is created through the API.
7. **Communication has no completion guard:** the current endpoint can generate an agent message before confirmation. The guide uses the safer completed-flow order, but this behavior is not currently restricted by the service.
8. **Audio/TTS is not exposed as an API route:** the speech abstraction exists in code, but there is no Swagger endpoint for audio synthesis.
