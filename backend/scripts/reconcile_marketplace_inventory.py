"""
Marketplace inventory reconciliation (read-only).

Prints one row per FarmerCreditBalance / CarbonToken pair with the
five-way conservation check:

    minted
  = unlisted (balance.credits_available)
  + Σ listing.credits_available for listings against this balance
  + Σ credits_requested for APPROVED / PAID orders on those listings
  + Σ credits_retired for retirement_certificates on those orders

If the equation doesn't hold the row is flagged MISMATCH. Exit code is 0
when everything balances and 1 when any mismatch is found — useful for a
scheduled staging check.

The script never modifies data. It never prints secrets, wallet keys,
API references, or full user emails.

Usage:
    python scripts/reconcile_marketplace_inventory.py
"""
from __future__ import annotations

import sys
from typing import Optional

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.carbon_token import CarbonToken
from app.models.farmer_credit_balance import FarmerCreditBalance
from app.models.marketplace import (
    ListingStatus,
    MarketplaceListing,
    MarketplaceOrder,
    OrderStatus,
    RetirementCertificate,
)

_RESERVED = (OrderStatus.APPROVED, OrderStatus.PAID)


def _reconcile_balance(db: Session, balance: FarmerCreditBalance) -> dict:
    token: Optional[CarbonToken] = None
    if balance.carbon_token_id:
        token = db.query(CarbonToken).filter(CarbonToken.id == balance.carbon_token_id).first()

    minted = token.credit_amount if token else balance.credits_earned

    listings = (
        db.query(MarketplaceListing)
        .filter(MarketplaceListing.farmer_credit_balance_id == balance.id)
        .all()
    )
    listing_ids = [l.id for l in listings]

    listing_available = sum(
        l.credits_available for l in listings
        if l.listing_status != ListingStatus.CANCELLED
    )

    reserved = 0
    if listing_ids:
        rows = (
            db.query(MarketplaceOrder.credits_requested)
            .filter(
                MarketplaceOrder.listing_id.in_(listing_ids),
                MarketplaceOrder.order_status.in_(_RESERVED),
            )
            .all()
        )
        reserved = int(sum(r[0] for r in rows))

    retired = 0
    if token is not None:
        retired = int(
            sum(
                (c.credits_retired or 0)
                for c in db.query(RetirementCertificate)
                .filter(RetirementCertificate.token_id == token.id)
                .all()
            )
        )

    unlisted = balance.credits_available
    total = unlisted + listing_available + reserved + retired
    diff = total - minted

    return {
        "balance_id": balance.id,
        "farmer_id": balance.farmer_id,
        "fpo_id": balance.fpo_id,
        "token_id": token.id if token else None,
        "minted": minted,
        "unlisted": unlisted,
        "listing_available": listing_available,
        "reserved": reserved,
        "retired": retired,
        "total": total,
        "diff": diff,
        "status": "OK" if diff == 0 else "MISMATCH",
    }


_HEADER_FMT = (
    "{:>10} {:>10} {:>10} {:>10} {:>10} {:>10} {:>10} {:>10} {:>10} {:>10}  {}"
)


def main() -> int:
    db = SessionLocal()
    exit_code = 0
    try:
        balances = db.query(FarmerCreditBalance).order_by(FarmerCreditBalance.id).all()
        if not balances:
            print("No FarmerCreditBalance rows to reconcile.")
            return 0

        print(_HEADER_FMT.format(
            "balance", "farmer", "fpo", "token",
            "minted", "unlisted", "listing", "reserved", "retired", "total", "status",
        ))
        for balance in balances:
            row = _reconcile_balance(db, balance)
            print(_HEADER_FMT.format(
                row["balance_id"], row["farmer_id"], row["fpo_id"], row["token_id"] or "-",
                row["minted"], row["unlisted"], row["listing_available"],
                row["reserved"], row["retired"], row["total"], row["status"],
            ))
            if row["status"] != "OK":
                exit_code = 1
                print(f"    -> diff = {row['diff']} (positive = over-counted, negative = missing)")

        print()
        print(f"Reconciliation result: {'OK' if exit_code == 0 else 'MISMATCH(ES)'}")
        return exit_code
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
