# GreenChain

**A mobile carbon-credit MRV and marketplace platform for Indian smallholder farmers, built with React Native, FastAPI, PostgreSQL, and Polygon Amoy.**

## Overview

GreenChain manages the carbon-credit lifecycle from farm onboarding to retirement:

**Farm registration → crop-cycle monitoring → evidence collection → carbon reporting → verification → token minting → marketplace listing → retirement certificate**

The platform uses a custodial model in which Farmer Producer Organizations (FPOs) manage blockchain assets on behalf of farmers, reducing wallet and onboarding complexity.

## Key Features

### Carbon MRV
- Farm and crop-cycle management
- Deterministic sensor simulation
- Methane baseline and reduction calculations
- Evidence upload with SHA-256 hashing
- Verifier review, risk classification, approval, and rejection

### Multi-Role Workflows
- **Farmer:** Farms, crop cycles, reports, evidence, and credit balances
- **FPO:** Farm approval, listings, buyer orders, payment confirmation, and payouts
- **Verifier:** Report and evidence review
- **Admin:** Platform oversight and token minting
- **Buyer:** Marketplace browsing, purchase requests, and retirement certificates

### Marketplace Integrity
- Listing creation reserves farmer credits
- Order approval reserves listing inventory
- PostgreSQL row locking helps prevent concurrent overselling
- Retirement requires a paid state
- Duplicate retirement is blocked
- Reconciliation checks validate credit conservation
- 52 focused marketplace tests

### Blockchain
- Polygon Amoy testnet
- ERC-1155 smart contract
- Custodial FPO wallet model
- Minting and retirement transaction records
- Off-chain ownership and reservation ledger

### GIS, Payments, and Certificates
- Google Maps integration for farm boundaries
- Provider-based GIS design with mock fallback
- RazorpayX test-mode farmer payouts
- Manual/test buyer payment confirmation
- SHA-256 retirement certificates

## Architecture

```text
React Native Mobile App
        |
        | HTTPS + JWT
        v
FastAPI Backend on Render
        |
        +-------------------+--------------------+
        |                   |                    |
        v                   v                    v
PostgreSQL          Persistent Evidence      External Services
SQLAlchemy          Storage on Render         Polygon Amoy
Alembic                                      Google Maps
                                             RazorpayX
                                             Groq (optional)
```

## Technology Stack

| Layer | Technology |
|---|---|
| Mobile | React Native, Expo SDK 54, React Navigation |
| State | Zustand |
| API | Axios |
| Secure Storage | Expo SecureStore |
| Backend | FastAPI, Gunicorn, Uvicorn |
| Database | PostgreSQL, SQLAlchemy |
| Migrations | Alembic |
| Authentication | JWT and bcrypt |
| Blockchain | Polygon Amoy, ERC-1155, web3.py |
| Payments | RazorpayX test mode |
| AI | Rules engine with optional Groq |
| Testing | pytest, FastAPI TestClient |
| Deployment | Render and EAS Build |

## Marketplace Credit Flow

```text
Minted Credits
   ├── Farmer Available Balance
   ├── Listed Credits
   ├── Reserved Buyer Orders
   └── Retired Credits
```

Reservation rules are applied during listing and approval so the same credits cannot be sold twice. Retirement does not subtract inventory again.

## Deployment

- **Backend:** Render
- **Staging URL:** https://greenchain-f3x4.onrender.com
- **Database:** Managed PostgreSQL
- **Evidence storage:** Render persistent disk
- **Mobile builds:** EAS development, preview APK, and production AAB profiles
- **Migrations:** 22 Alembic revisions with a single current head

## Testing and Quality

- 1,100+ backend tests passing
- 52/52 marketplace tests passing
- TypeScript compilation clean
- Expo Doctor checks passing
- Role-based authorization on mutating endpoints
- Environment-based secret and CORS validation
- JWT stored with Expo SecureStore

## Current Scope and Limitations

GreenChain is a **staging prototype and portfolio project**, not a public production platform.

- Blockchain runs on Polygon Amoy testnet
- Sensor data is simulated
- GIS uses mock providers unless external credentials are configured
- AI defaults to deterministic rules
- Buyer payment confirmation is manual/test mode
- RazorpayX is used only in test mode
- No mainnet deployment or real economic value transfer
- Real-device validation and production hardening are ongoing

## Running Locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Mobile

```bash
cd mobile
cp .env.example .env
npm ci
npm run dev
```

Set the local backend URL in `.env`:

```env
EXPO_PUBLIC_API_BASE_URL=http://YOUR_LOCAL_IP:8000
```

## What I Learned

- Designing multi-role authorization across mobile and backend
- Preventing marketplace oversubscription with reservations and row locking
- Managing additive database migrations
- Separating on-chain transactions from off-chain ownership state
- Handling environment-specific mobile API configuration
- Building deployment-safe configuration for secrets, CORS, and uploads
- Managing test-fixture drift as the project grows

## Future Improvements

- GitHub Actions CI
- Object storage for evidence
- Real buyer payment gateway
- Push notifications
- Offline caching
- Sentry monitoring
- Rate limiting
- Real satellite and drone integrations
- Play Store internal testing
- Regional-language support

## Project Status

**Staging prototype — portfolio-ready, with production hardening in progress.**
