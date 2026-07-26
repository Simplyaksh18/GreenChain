GreenChain
Mobile carbon-credit MRV platform for Indian smallholder farmers — verified methane reductions become tradable credits held custodially by FPOs, retired against tokenized ownership on Polygon Amoy.

Overview
Smallholder farmers in India can measurably reduce agricultural methane through practices like alternate wetting-and-drying in paddy — but they can't access voluntary carbon markets alone. Registration, monitoring, verification, tokenization and buyer settlement all require infrastructure they don't have.

GreenChain is a five-role mobile + backend platform that walks the full MRV → mint → market → retire pipeline. FPOs (Farmer Producer Organizations) act as custodians — they onboard farmers, aggregate credits, list them for sale, and retire them on behalf of buyers. Verifiers audit reports. Admins mint tokens on Polygon Amoy testnet. Buyers browse the marketplace and hold retirement certificates.

Why I Built This
I wanted a project that stretched every layer I care about — a real data model, real state machines, real deployment — inside a domain that isn't just another CRUD app. Carbon MRV forces you to reason about custodial ownership, inventory reservation, and the boundary between what's actually on-chain and what's off-chain. It also forces honesty about what's simulated versus real. That's the kind of scope I wanted to defend end-to-end.

Key Features
Carbon MRV

Deterministic sensor simulator with per-crop-cycle seeding
Methane baseline vs. current calculation (Paddy / Wheat / Millet / Maize factors)
Verifier queue with risk scoring and evidence attachment
SHA-256 hashed evidence uploads with audit trail
Multi-role workflows

Farmer: farm + crop cycles + reports + credit balance
FPO: farm approval, listing management, order processing, payouts
Verifier: report review, risk classification, approve/reject
Admin: cross-FPO oversight, token minting
Buyer: marketplace browse, purchase requests, own-certificate view
Marketplace with reservation semantics

Listing creation decrements the farmer's unlisted credit balance
Approval reserves credits at the listing level (SELECT ... FOR UPDATE)
Retirement requires an explicit paid state — no double subtraction
Reconciliation script proves conservation invariant
Blockchain (Polygon Amoy testnet)

ERC-1155 contract deployed and address recorded
Mint / retire transactions written to a blockchain_transactions table alongside off-chain state
Custodial model: token held by FPO wallet; farmer ownership tracked in FarmerCreditBalance
GIS and evidence

Provider-agnostic GIS layer (Copernicus / Bhoonidhi / Bhuvan interfaces + mock fallback)
Google Maps SDK integration for farm boundaries
Camera and document evidence with server-side hashing
Payments and certificates

RazorpayX test-mode integration for FPO → farmer payouts
Manual/test payment recording for buyer marketplace orders (no gateway involved)
Deterministic SHA-256 retirement certificates issued to buyers
Deployment and testing

Backend live on Render at greenchain-f3x4.onrender.com
22 sequential Alembic migrations, single head, additive-only patterns
1100+ backend tests, 52/52 marketplace tests green, TypeScript clean
User Roles
Role	Responsibility
Farmer	Registers farms, runs crop cycles, uploads evidence, generates reports, views credit balance
FPO	Approves farms, lists credits, processes buyer orders, records payments, initiates farmer payouts
Verifier	Reviews carbon reports, checks evidence, approves or rejects
Admin	Mints tokens against verified reports, oversees all FPOs, retires on behalf if needed
Buyer	Browses active listings, submits purchase requests, views their own retirement certificates
End-to-End Workflow
Farmer            FPO           Verifier        Admin          Buyer
  │                │                │             │              │
  ├─ Farm ────────►│ (approve)      │             │              │
  ├─ Crop cycle    │                │             │              │
  ├─ Evidence ────►│                │             │              │
  ├─ Report ──────────────────────► (verify)      │              │
  │                │                │             │              │
  │                │                └───────────► (mint token)   │
  │                │                              │              │
  │                ├─ Listing (reserves balance)  │              │
  │                │                              │              │
  │                │                              │              ├─ Browse
  │                │◄────── Purchase request ───────────────────┤
  │                ├─ Approve (reserves inv.)     │              │
  │                ├─ Mark paid (manual/test)     │              │
  │                ├─ Retire ───────────────────► (chain tx)     │
  │                │                              │              │
  │                │                              └─ Certificate ►
Architecture
┌────────────────────┐      HTTPS + JWT
│  React Native App  │ ────────────────────►┐
│  (Expo SDK 54)     │                      │
└────────────────────┘                      ▼
                                 ┌─────────────────────┐
                                 │  FastAPI Backend    │
                                 │  (Render web svc)   │
                                 └──────────┬──────────┘
                                            │
                       ┌────────────────────┼──────────────────────┐
                       ▼                    ▼                      ▼
              ┌─────────────┐      ┌────────────────┐    ┌──────────────────┐
              │ PostgreSQL  │      │ Persistent disk│    │ External providers│
              │ (Render)    │      │ /var/data      │    │ Polygon Amoy      │
              │ 22 Alembic  │      │ evidence files │    │ RazorpayX (test)  │
              │ migrations  │      │                │    │ Google Maps       │
              └─────────────┘      └────────────────┘    │ Groq (optional)   │
                                                        └──────────────────┘
Technology Stack
Layer	Choice
Mobile	React Native 0.81, Expo SDK 54, React Navigation, react-native-paper
Mobile state	Zustand
HTTP client	Axios with JWT interceptor + 401 auto-logout
Secure storage	expo-secure-store
Backend	FastAPI 0.115, Uvicorn workers under Gunicorn
ORM	SQLAlchemy 2.0 with SELECT ... FOR UPDATE locking
Migrations	Alembic (22 revisions, single head)
Database	PostgreSQL (SQLite for tests via StaticPool)
Auth	JWT (HS256) + bcrypt 4.2 (pinned)
Blockchain	web3.py 6+ against Polygon Amoy, ERC-1155 contract
Payments	Razorpay Python SDK (test mode)
AI	Deterministic rules engine (default) + optional Groq LLM
Testing	pytest, TestClient, SQLite StaticPool
Deployment	Render blueprint (backend + PG + persistent disk), EAS Build (mobile)
Marketplace Integrity
Every carbon credit lives in exactly one bucket at any point:

minted  =  unlisted (farmer balance)
        +  listing available
        +  reserved (approved/paid orders)
        +  retired
The router uses SELECT ... FOR UPDATE at every mutating boundary — listing create, cancel, order approve, reject-after-approve, mark-paid, retire. Approval decrements the listing's available quantity; retirement never decrements it again. A standalone reconciliation script walks all balances and returns non-zero if any diff > 0. Oversubscription is prevented at approval time (409 conflict); double retirement is prevented by a unique index on retirement_certificates.order_id plus a status guard. This isn't a formal proof — it's a machine-verified invariant covered by 52 focused tests.

Blockchain Model
Network: Polygon Amoy (testnet). Contract deployed at 0x04Bb0784db43fb447AA2be0e7825549Ab9190f86.
Token standard: ERC-1155 (multi-token; suits per-report credit issuance).
Custody: FPO wallet holds the token; individual farmer ownership tracked off-chain in FarmerCreditBalance. This is a deliberate MVP simplification — farmers don't need wallets to earn credits.
On-chain: mint transaction hash, retirement transaction hash, contract address, network label.
Off-chain: balance ledger, reservation state, buyer identity, retirement certificate metadata.
This is testnet software. No mainnet deployment. No real economic value moves.

Deployment
Backend: Render blueprint (render.yaml) — one web service + managed PostgreSQL + 1 GB persistent disk mounted at /var/data for evidence files. start.sh runs Alembic and starts Gunicorn with two Uvicorn workers.
Public staging URL: greenchain-f3x4.onrender.com (currently healthy; Render free tier — cold starts possible).
Mobile: EAS Build profiles for development APK, preview APK, production AAB. Preview and production inject EXPO_PUBLIC_API_BASE_URL via eas.json so the shipped app points at Render regardless of local dev config.
Database: managed PostgreSQL; SQLite used only in tests.
Env model: APP_ENV gates strict validation. Staging/production refuse to boot with a default SECRET_KEY or a wildcard CORS_ORIGINS.
Security Measures
Verified controls:

bcrypt password hashing (pinned 4.2.x for passlib compatibility)
JWT bearer auth with 60-minute expiry; hardened verify_password returns False on malformed hashes rather than 500
Role-based authorization on every mutating endpoint
Startup config validation refuses known-default SECRET_KEY and wildcard CORS in staging/production
Secrets loaded from environment only, never committed
expo-secure-store for JWT on mobile
Marketplace ownership checks on every listing / order / payment / retire path
Evidence uploads written under a configured UPLOAD_DIR that lives on the persistent disk
Not claimed: comprehensive OWASP audit, rate limiting, WAF, penetration testing.

Current Scope and Honest Limitations
Blockchain is testnet only. Polygon Amoy. No mainnet plans in this phase.
Sensor data is simulated — a deterministic per-cycle generator, not real IoT.
GIS uses mock provider by default. Copernicus / Bhoonidhi / Bhuvan clients exist but require credentials to activate.
AI defaults to rules. Groq is optional; falls back cleanly.
Buyer "payment" is manual/test. No real payment gateway on the buyer side. RazorpayX is wired only for FPO → farmer payouts, in test mode.
No public production release. No Play Store listing. No live user data.
20 legacy tests fail due to fixture drift unrelated to any current feature — documented, not swept under the rug.
Real-device end-to-end walkthrough not yet completed.
What I Learned
Reservation is a state machine, not a field. I derived reserved-quantity from credits_requested + status ∈ {APPROVED, PAID} instead of adding a redundant column — cheaper schema, harder to fall out of sync.
Row locking matters even in a small app. Two concurrent approve requests against the last credit would silently oversell without SELECT ... FOR UPDATE.
Migrations should be additive. Every one of my 22 revisions adds; none drops or renames destructively. Downgrade paths are real.
Config validation belongs at startup, not per-request. Failing fast on a missing SECRET_KEY in production is safer than a security hole discovered by an audit.
Test fixtures decay. Twelve of my legacy failures come from a shared farm fixture that shifted meaning as the app grew. Fixture ownership is a real thing.
The mobile-backend URL boundary belongs in build config, not source. EAS env blocks per profile beat sprinkling if __DEV__ across the codebase.
Custodial blockchain is a trade-off. Farmers get zero-friction access; I gave up on-chain provenance of individual ownership. That was the right MVP call, and I can articulate why.
Future Improvements
Object storage (S3/GCS) for evidence — enables CDN + backup
CI pipeline (GitHub Actions)
Real payment gateway for buyers
Push notifications
Offline caching layer
Real satellite/drone integration credentials
Rate limiting on /auth/*
Sentry for backend + mobile
Play Store internal-testing distribution
i18n (Hindi + regional languages)
Running Locally
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Mobile
cd mobile
cp .env.example .env   # fill EXPO_PUBLIC_API_BASE_URL to your LAN IP
npm ci
npm run dev            # expo start --dev-client --clear
Project Status
Staging prototype — portfolio-ready.
Backend deployed and healthy on Render. Buyer + FPO + farmer flows functional through the API. Mobile app builds cleanly and preview APK ships pointing at the deployed backend. Ready to demo end-to-end; not ready for real users.
