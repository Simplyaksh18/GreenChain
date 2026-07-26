import logging
import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import auth, fpos, farmers, farms, sensors, emissions
from app.routers import evidence, carbon_reports, verification, admin
from app.routers import blockchain, tokens
from app.routers import satellite, drone, dashboard
from app.routers import users, mobile, system
from app.routers import credits, payouts   # Phase 9
from app.routers import mrv                # Phase 10A — high-emission demo
from app.routers import mrv_import         # Phase 11 — CSV imports
from app.routers import report_detail      # Phase 11 — report detail + eligibility
from app.routers import gis                # Phase 12 — GIS / satellite layer
from app.routers import soc                # Phase 12.5 — SOC (informational)
from app.routers import audit              # Phase 13 — Evidence & Audit Trail
from app.routers import registry           # Phase 16 — Public Registry
from app.routers import marketplace        # Phase 16 — Marketplace
from app.routers import payments           # Phase 17 — Razorpay Checkout
from app.routers import ai                 # Phase 18 — AI Layer

app = FastAPI(
    title="GreenChain API",
    description="Blockchain-based Carbon Credit MRV Platform for Agriculture",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

from app.config import get_cors_origins, validate_startup_config  # noqa: E402

# Fail fast on unsafe SECRET_KEY / CORS in staging/production. Dev/test skip
# strict checks; if SECRET_KEY is empty in dev, a documented dev-only fallback
# is applied so the process can still boot for local work.
validate_startup_config()

_CORS_ORIGINS = get_cors_origins()
# allow_credentials=True with allow_origins=["*"] is invalid per the CORS spec
# (browsers ignore the wildcard), so we only enable credentials for non-wildcard
# origin lists — matching Starlette's own guidance.
_ALLOW_CREDENTIALS = _CORS_ORIGINS != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Phase 1
app.include_router(auth.router)
# Phase 2
app.include_router(fpos.router)
app.include_router(farmers.router)
app.include_router(farms.router)
# Phase 3
app.include_router(sensors.router)
app.include_router(emissions.router)
# Phase 4
app.include_router(evidence.router)
app.include_router(carbon_reports.router)
app.include_router(verification.router)
app.include_router(admin.router)
# Phase 5
app.include_router(blockchain.router)
app.include_router(tokens.router)
# Phase 7
app.include_router(satellite.router)
app.include_router(drone.router)
app.include_router(dashboard.router)
# Phase 8
app.include_router(users.router)
app.include_router(mobile.router)
app.include_router(system.router)
# Phase 9: custodial model
app.include_router(credits.router)
app.include_router(payouts.router)
# Phase 10A
app.include_router(mrv.router)
# Phase 11
app.include_router(mrv_import.router)
app.include_router(report_detail.router)
# Phase 12 — GIS
app.include_router(gis.router)
# Phase 12.5 — SOC (informational only — not mintable)
app.include_router(soc.router)
# Phase 13 — Evidence & Audit Trail
app.include_router(audit.router)
# Phase 16 — Registry & Marketplace
app.include_router(registry.router)
app.include_router(marketplace.router)
# Phase 17 — Razorpay Checkout
app.include_router(payments.router)

app.include_router(ai.router)             # Phase 18 — AI Layer


# ── Static file serving: uploaded evidence files ───────────────────────────────
# Directory is resolved by app.config.resolve_evidence_upload_dir() — the SINGLE
# source of truth shared with routers/evidence.py. Reads UPLOAD_DIR at import
# time so the StaticFiles mount points at the same disk location we write to.
from app.config import resolve_evidence_upload_dir  # noqa: E402

_UPLOADS_DIR = str(resolve_evidence_upload_dir())
app.mount("/uploads/evidence", StaticFiles(directory=_UPLOADS_DIR), name="evidence_uploads")


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "GreenChain API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
def health(db: Session = Depends(get_db)):
    """
    Public liveness/readiness probe for platform health checks
    (Render, Railway, Docker HEALTHCHECK, load balancers).

    Returns 200 with a minimal safe payload. Never exposes secrets,
    URLs, keys, or internal metadata. Attempts a lightweight `SELECT 1`
    against the database; a DB failure downgrades `db` to "unavailable"
    but the endpoint itself still returns 200 so the process is not
    killed by a transient DB blip.
    """
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "health: db check failed (%s)", type(exc).__name__
        )
        db_status = "unavailable"

    return {
        "status": "ok",
        "db": db_status,
        "environment": os.environ.get("APP_ENV", "development"),
    }
