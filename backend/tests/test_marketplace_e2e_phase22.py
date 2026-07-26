"""
Phase 22 → 22B — Marketplace end-to-end verification.

Updated for Phase 22B semantics:
  * listing creation DECREMENTS FarmerCreditBalance.credits_available
  * order approval RESERVES quantity (decrements listing.credits_available)
  * retirement REQUIRES PAID and does NOT decrement listing.credits_available again
  * self-purchase is blocked
  * mark-paid is a manual/test recorded state
"""
from __future__ import annotations

import pytest

from app.models.farmer_credit_balance import FarmerCreditBalance
from app.models.marketplace import (
    ListingStatus,
    MarketplaceListing,
    MarketplaceOrder,
    OrderStatus,
    RetirementCertificate,
    compute_certificate_hash,
)

AUTH = lambda t: {"Authorization": f"Bearer {t}"}

# Reuse the minted_token fixture from the sibling module.
from tests.test_registry_marketplace import minted_token  # noqa: F401


def _create_listing(client, fpo_token, token, fcb, credits=1, price=50000):
    resp = client.post(
        "/marketplace/listings",
        json={
            "farmer_credit_balance_id": fcb.id,
            "carbon_token_id": token.id,
            "credits_listed": credits,
            "price_per_credit": price,
        },
        headers=AUTH(fpo_token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _place_order(client, buyer_token, listing_id, credits, name="Buyer Co"):
    return client.post(
        "/marketplace/orders",
        json={
            "listing_id": listing_id,
            "buyer_name": name,
            "buyer_email": f"{name.lower().replace(' ', '')}@buy.com",
            "credits_requested": credits,
        },
        headers=AUTH(buyer_token),
    )


def _approve(client, fpo_token, order_id):
    return client.post(f"/marketplace/orders/{order_id}/approve", headers=AUTH(fpo_token))


def _mark_paid(client, fpo_token, order_id, reference="TEST-REF"):
    return client.post(
        f"/marketplace/orders/{order_id}/mark-paid",
        json={"payment_reference": reference},
        headers=AUTH(fpo_token),
    )


def _retire(client, fpo_token, order_id):
    return client.post(f"/marketplace/orders/{order_id}/retire", headers=AUTH(fpo_token))


# ── A. Full happy path ───────────────────────────────────────────────────────

class TestHappyPathE2E:
    def test_full_lifecycle_mint_list_order_approve_pay_retire_certificate(
        self, client, fpo_token, buyer_token, minted_token, db
    ):
        _, token, fcb = minted_token
        available_before = fcb.credits_available
        assert available_before >= 1

        listing = _create_listing(client, fpo_token, token, fcb, credits=1, price=50000)
        assert listing["listing_status"] == "ACTIVE"
        assert listing["credits_available"] == 1

        # Balance was decremented at listing time.
        db.expire_all()
        assert db.query(FarmerCreditBalance).get(fcb.id).credits_available == available_before - 1

        order_resp = _place_order(client, buyer_token, listing["id"], 1, "GreenCorp")
        assert order_resp.status_code == 201
        order = order_resp.json()
        assert order["order_status"] == "INTERESTED"

        appr = _approve(client, fpo_token, order["id"])
        assert appr.status_code == 200
        assert appr.json()["order_status"] == "APPROVED"

        # After approve: listing SOLD_OUT (only 1 credit), reservation intact.
        db.expire_all()
        listing_row = db.query(MarketplaceListing).get(listing["id"])
        assert listing_row.credits_available == 0
        assert listing_row.listing_status == ListingStatus.SOLD_OUT

        # Retire requires PAID — try before mark-paid, expect block.
        early = _retire(client, fpo_token, order["id"])
        assert early.status_code == 400

        pay = _mark_paid(client, fpo_token, order["id"], reference="INV-001")
        assert pay.status_code == 200
        assert pay.json()["order_status"] == "PAID"
        assert pay.json()["payment_method"] == "MANUAL_TEST"

        ret = _retire(client, fpo_token, order["id"])
        assert ret.status_code == 201, ret.text
        cert = ret.json()
        assert cert["credits_retired"] == 1
        assert len(cert["certificate_hash"]) == 64

        db.expire_all()
        order_row = db.query(MarketplaceOrder).get(order["id"])
        assert order_row.order_status == OrderStatus.RETIRED

        cert_rows = (
            db.query(RetirementCertificate)
            .filter(RetirementCertificate.order_id == order["id"])
            .all()
        )
        assert len(cert_rows) == 1


# ── B. Listing validation edge cases ─────────────────────────────────────────

class TestListingValidation:
    def test_listing_below_min_price_rejected(self, client, fpo_token, minted_token):
        _, token, fcb = minted_token
        resp = client.post(
            "/marketplace/listings",
            json={
                "farmer_credit_balance_id": fcb.id,
                "carbon_token_id": token.id,
                "credits_listed": 1,
                "price_per_credit": 0,
            },
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 422

    def test_listing_below_min_quantity_rejected(self, client, fpo_token, minted_token):
        _, token, fcb = minted_token
        resp = client.post(
            "/marketplace/listings",
            json={
                "farmer_credit_balance_id": fcb.id,
                "carbon_token_id": token.id,
                "credits_listed": 0,
                "price_per_credit": 50000,
            },
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 422

    def test_listing_creation_decrements_balance(
        self, client, fpo_token, minted_token, db
    ):
        """
        Phase 22B behavior: creating a listing now DOES decrement
        FarmerCreditBalance.credits_available (the reservation).
        """
        _, token, fcb = minted_token
        original = fcb.credits_available
        assert original >= 1
        _ = _create_listing(client, fpo_token, token, fcb, credits=1, price=10000)
        db.expire_all()
        after = db.query(FarmerCreditBalance).get(fcb.id).credits_available
        assert after == original - 1

    def test_second_listing_over_available_blocked(
        self, client, fpo_token, minted_token
    ):
        """
        With the balance decremented at listing time, a second listing that
        would exceed the remaining unlisted balance is blocked with 409.
        """
        _, token, fcb = minted_token
        assert fcb.credits_available >= 1
        _create_listing(client, fpo_token, token, fcb, credits=fcb.credits_available, price=50000)
        # Try to list one more than what's now free.
        resp = client.post(
            "/marketplace/listings",
            json={
                "farmer_credit_balance_id": fcb.id,
                "carbon_token_id": token.id,
                "credits_listed": 1,
                "price_per_credit": 50000,
            },
            headers=AUTH(fpo_token),
        )
        assert resp.status_code == 409


# ── C. Order / self-purchase / no-reservation-at-submit ──────────────────────

class TestOrderBehavior:
    def test_self_purchase_blocked_for_seller_farmer(
        self, client, fpo_token, farmer_token, minted_token
    ):
        """
        farmer_token belongs to the farmer whose farm produced the credits.
        They cannot buy their own listing.
        """
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        r = _place_order(client, farmer_token, listing["id"], 1, "Self Buyer")
        assert r.status_code == 403

    def test_self_purchase_blocked_for_seller_fpo(
        self, client, fpo_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        r = _place_order(client, fpo_token, listing["id"], 1, "Self FPO")
        assert r.status_code == 403

    def test_order_on_paused_listing_rejected(
        self, client, fpo_token, buyer_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        pr = client.patch(
            f"/marketplace/listings/{listing['id']}",
            json={"listing_status": "PAUSED"},
            headers=AUTH(fpo_token),
        )
        assert pr.status_code == 200
        r = _place_order(client, buyer_token, listing["id"], 1)
        assert r.status_code == 400

    def test_order_exceeding_available_rejected(
        self, client, fpo_token, buyer_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        r = _place_order(client, buyer_token, listing["id"], 999)
        assert r.status_code == 409

    def test_two_orders_can_both_be_placed_no_reservation_at_submit(
        self, client, fpo_token, buyer_token, minted_token
    ):
        """
        Order submission does not reserve; only approve reserves.
        """
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        r1 = _place_order(client, buyer_token, listing["id"], 1, "Buyer A")
        r2 = _place_order(client, buyer_token, listing["id"], 1, "Buyer B")
        assert r1.status_code == 201 and r2.status_code == 201


# ── D. Approval reserves; concurrent approvals never oversubscribe ───────────

class TestApprovalReservation:
    def test_approve_decrements_listing_available(
        self, client, fpo_token, buyer_token, minted_token, db
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        _approve(client, fpo_token, order["id"])
        db.expire_all()
        row = db.query(MarketplaceListing).get(listing["id"])
        assert row.credits_available == 0
        assert row.listing_status == ListingStatus.SOLD_OUT

    def test_second_approve_over_available_blocked(
        self, client, fpo_token, buyer_token, minted_token
    ):
        """
        Two orders each for the full 1-credit listing. Approve the first;
        approving the second must fail with 409 (insufficient inventory).
        """
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        o1 = _place_order(client, buyer_token, listing["id"], 1, "One").json()
        o2 = _place_order(client, buyer_token, listing["id"], 1, "Two").json()
        r1 = _approve(client, fpo_token, o1["id"])
        r2 = _approve(client, fpo_token, o2["id"])
        assert r1.status_code == 200
        assert r2.status_code == 409

    def test_double_approve_same_order_rejected(
        self, client, fpo_token, buyer_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        assert _approve(client, fpo_token, order["id"]).status_code == 200
        assert _approve(client, fpo_token, order["id"]).status_code == 400

    def test_reject_after_approve_returns_reservation(
        self, client, fpo_token, buyer_token, minted_token, db
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        _approve(client, fpo_token, order["id"])
        r = client.post(
            f"/marketplace/orders/{order['id']}/reject",
            json={"remarks": "changed mind"},
            headers=AUTH(fpo_token),
        )
        assert r.status_code == 200
        db.expire_all()
        row = db.query(MarketplaceListing).get(listing["id"])
        assert row.credits_available == 1
        assert row.listing_status == ListingStatus.ACTIVE

    def test_unrelated_fpo_cannot_approve(
        self, client, fpo_token, fpo2_user, buyer_token, minted_token, db
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()

        from app.models.fpo import FPOProfile
        from app.security import create_access_token
        p2 = FPOProfile(
            user_id=fpo2_user.id,
            organization_name="Rival FPO",
            registration_number="RIVAL-001",
            district="Pune",
            state="Maharashtra",
        )
        db.add(p2)
        db.commit()
        fpo2_token = create_access_token({"sub": str(fpo2_user.id), "role": fpo2_user.role.value})
        r = _approve(client, fpo2_token, order["id"])
        assert r.status_code == 403


# ── E. Payment state (mark-paid) ─────────────────────────────────────────────

class TestPayment:
    def test_mark_paid_requires_approved(
        self, client, fpo_token, buyer_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        r = _mark_paid(client, fpo_token, order["id"])
        assert r.status_code == 400

    def test_mark_paid_transitions_to_paid_with_metadata(
        self, client, fpo_token, buyer_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        _approve(client, fpo_token, order["id"])
        r = _mark_paid(client, fpo_token, order["id"], reference="INV-42")
        assert r.status_code == 200
        body = r.json()
        assert body["order_status"] == "PAID"
        assert body["payment_method"] == "MANUAL_TEST"
        assert body["payment_reference"] == "INV-42"
        assert body["paid_at"] is not None
        assert "test/manual mode" in body["message"].lower()

    def test_mark_paid_idempotent(
        self, client, fpo_token, buyer_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        _approve(client, fpo_token, order["id"])
        r1 = _mark_paid(client, fpo_token, order["id"])
        r2 = _mark_paid(client, fpo_token, order["id"])
        assert r1.status_code == 200 and r2.status_code == 200
        assert r2.json()["idempotent"] is True

    def test_farmer_cannot_mark_paid(
        self, client, fpo_token, buyer_token, farmer2_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        _approve(client, fpo_token, order["id"])
        r = _mark_paid(client, farmer2_token, order["id"])
        assert r.status_code == 403


# ── F. Retirement rules ──────────────────────────────────────────────────────

class TestRetirement:
    def test_retire_from_approved_blocked(
        self, client, fpo_token, buyer_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        _approve(client, fpo_token, order["id"])
        r = _retire(client, fpo_token, order["id"])
        assert r.status_code == 400

    def test_retire_from_paid_succeeds_and_creates_certificate(
        self, client, fpo_token, buyer_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1, "Cert").json()
        _approve(client, fpo_token, order["id"])
        _mark_paid(client, fpo_token, order["id"])
        r = _retire(client, fpo_token, order["id"])
        assert r.status_code == 201
        assert r.json()["credits_retired"] == 1

    def test_retire_does_not_double_decrement_listing(
        self, client, fpo_token, buyer_token, minted_token, db
    ):
        """
        Reservation happens at approve. Retire must NOT decrement again.
        """
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        _approve(client, fpo_token, order["id"])
        _mark_paid(client, fpo_token, order["id"])
        db.expire_all()
        before = db.query(MarketplaceListing).get(listing["id"]).credits_available
        _retire(client, fpo_token, order["id"])
        db.expire_all()
        after = db.query(MarketplaceListing).get(listing["id"]).credits_available
        assert before == after

    def test_duplicate_retirement_blocked(
        self, client, fpo_token, buyer_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        _approve(client, fpo_token, order["id"])
        _mark_paid(client, fpo_token, order["id"])
        _retire(client, fpo_token, order["id"])
        r = _retire(client, fpo_token, order["id"])
        assert r.status_code in (400, 409)


# ── G. Buyer certificate access ──────────────────────────────────────────────

class TestBuyerCertificateAccess:
    def test_buyer_can_fetch_own_certificate(
        self, client, fpo_token, buyer_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1, "MyCert").json()
        _approve(client, fpo_token, order["id"])
        _mark_paid(client, fpo_token, order["id"])
        _retire(client, fpo_token, order["id"])
        r = client.get(
            f"/marketplace/orders/{order['id']}/certificate", headers=AUTH(buyer_token)
        )
        assert r.status_code == 200
        assert r.json()["buyer_name"] == "MyCert"

    def test_other_buyer_cannot_fetch_certificate(
        self, client, fpo_token, buyer_token, farmer2_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        _approve(client, fpo_token, order["id"])
        _mark_paid(client, fpo_token, order["id"])
        _retire(client, fpo_token, order["id"])
        r = client.get(
            f"/marketplace/orders/{order['id']}/certificate", headers=AUTH(farmer2_token)
        )
        assert r.status_code == 403


# ── H. Cancellation returns credits ──────────────────────────────────────────

class TestCancellation:
    def test_cancel_returns_unreserved_credits_to_farmer(
        self, client, fpo_token, minted_token, db
    ):
        _, token, fcb = minted_token
        original = fcb.credits_available
        assert original >= 1
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        db.expire_all()
        assert db.query(FarmerCreditBalance).get(fcb.id).credits_available == original - 1

        r = client.post(f"/marketplace/listings/{listing['id']}/cancel", headers=AUTH(fpo_token))
        assert r.status_code == 200
        db.expire_all()
        assert db.query(FarmerCreditBalance).get(fcb.id).credits_available == original

    def test_cancel_blocked_when_approved_order_exists(
        self, client, fpo_token, buyer_token, minted_token
    ):
        _, token, fcb = minted_token
        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        _approve(client, fpo_token, order["id"])
        r = client.post(f"/marketplace/listings/{listing['id']}/cancel", headers=AUTH(fpo_token))
        assert r.status_code == 409


# ── I. Reconciliation invariant ──────────────────────────────────────────────

class TestReconciliation:
    def test_full_reconciliation_after_retirement(
        self, client, fpo_token, buyer_token, minted_token, db
    ):
        """
        For a token:
          minted = unlisted (balance.credits_available)
                 + Σ listing.credits_available (still-open)
                 + Σ reserved (APPROVED/PAID orders on listings)
                 + Σ retired (retirement_certificates.credits_retired)
        """
        _, token, fcb = minted_token
        original_minted = token.credit_amount
        assert original_minted >= 1

        listing = _create_listing(client, fpo_token, token, fcb, credits=1)
        order = _place_order(client, buyer_token, listing["id"], 1).json()
        _approve(client, fpo_token, order["id"])
        _mark_paid(client, fpo_token, order["id"])
        _retire(client, fpo_token, order["id"])

        db.expire_all()
        fresh_balance = db.query(FarmerCreditBalance).get(fcb.id)
        fresh_listing = db.query(MarketplaceListing).get(listing["id"])
        certs = (
            db.query(RetirementCertificate)
            .filter(RetirementCertificate.token_id == token.id)
            .all()
        )
        retired_total = sum(c.credits_retired for c in certs)
        reserved_total = (
            db.query(MarketplaceOrder)
            .filter(
                MarketplaceOrder.listing_id == fresh_listing.id,
                MarketplaceOrder.order_status.in_((OrderStatus.APPROVED, OrderStatus.PAID)),
            )
            .count()
        )  # 0 after retirement
        total = (
            fresh_balance.credits_available
            + fresh_listing.credits_available
            + reserved_total
            + retired_total
        )
        assert total == original_minted


# ── J. Certificate hash still deterministic ──────────────────────────────────

class TestCertificateHash:
    def test_hash_function_deterministic(self):
        h1 = compute_certificate_hash(1, 2, "X", 3, "2026-01-01T00:00:00+00:00")
        h2 = compute_certificate_hash(1, 2, "X", 3, "2026-01-01T00:00:00+00:00")
        assert h1 == h2 and len(h1) == 64
        assert compute_certificate_hash(1, 2, "X", 4, "2026-01-01T00:00:00+00:00") != h1
