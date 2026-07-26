"""
Phase 16 — Registry & Marketplace tests.

Tests:
  - Public registry hides PII
  - FPO listing creation/validation
  - Buyer order flow
  - Retirement certificate creation
  - Search filters
  - Admin oversight
"""
import pytest

AUTH = lambda t: {"Authorization": f"Bearer {t}"}


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def minted_token(client, fpo_token, fpo_profile, farmer_user, farmer_token, admin_token, verifier_token, db):
    """
    Sets up: farm → approved → crop cycle → sensor sim → carbon report → verify → admin mint.
    Returns (farm_id, token, fcb) for use in marketplace tests.

    Mirrors the exact pattern from test_custodial_model.py:
      - POST /farms/{id}/crop-cycles
      - POST /sensors/simulate
      - POST /carbon-reports/generate/{cycle_id}
      - POST /carbon-reports/{id}/submit
      - POST /verification/{vr_id}/approve  (verifier)
      - POST /admin/tokens/mint/{report_id} (admin)
    """
    from app.models.carbon_token import CarbonToken
    from app.models.farmer_credit_balance import FarmerCreditBalance

    # Create farm
    farm_resp = client.post("/farms/", json={
        "farm_name": "Marketplace Test Farm",
        "village": "Testville",
        "district": "Pune",
        "state": "Maharashtra",
        "land_area_acres": 5.0,
        "latitude": 18.5,
        "longitude": 73.8,
        "soil_type": "Clay",
        "water_source": "Canal",
        "fpo_id": fpo_profile.id,
    }, headers=AUTH(farmer_token))
    assert farm_resp.status_code == 201, farm_resp.text
    farm_id = farm_resp.json()["id"]

    # Approve farm
    approve_resp = client.post(f"/fpo/farms/{farm_id}/approve", headers=AUTH(fpo_token))
    assert approve_resp.status_code == 200, approve_resp.text

    # Create crop cycle
    cycle_resp = client.post(f"/farms/{farm_id}/crop-cycles", json={
        "crop_type": "Paddy",
        "season": "Kharif 2024",
        "start_date": "2024-06-01",
        "baseline_method": "Historical average",
        "reduction_practice": "AWD irrigation",
    }, headers=AUTH(farmer_token))
    assert cycle_resp.status_code == 201, cycle_resp.text
    cycle_id = cycle_resp.json()["id"]

    # Simulate 90 days of sensor data (need enough CH4 flux for ≥1 credit)
    client.post("/sensors/simulate", json={
        "farm_id": farm_id,
        "crop_cycle_id": cycle_id,
        "number_of_days": 90,
    }, headers=AUTH(farmer_token))

    # Generate carbon report
    rpt_resp = client.post(f"/carbon-reports/generate/{cycle_id}", headers=AUTH(farmer_token))
    assert rpt_resp.status_code == 201, rpt_resp.text
    report_id = rpt_resp.json()["id"]

    # Submit for verification
    sub = client.post(f"/carbon-reports/{report_id}/submit", headers=AUTH(farmer_token))
    assert sub.status_code == 200, sub.text

    # Verifier approves
    pending = client.get("/verification/pending", headers=AUTH(verifier_token))
    vrs = [v for v in pending.json() if v["carbon_report_id"] == report_id]
    assert len(vrs) >= 1, f"No VerificationRequest found for report {report_id}"
    vr_id = vrs[0]["id"]
    approve = client.post(f"/verification/{vr_id}/approve", headers=AUTH(verifier_token))
    assert approve.status_code == 200, approve.text

    # Admin mints
    mint_resp = client.post(f"/admin/tokens/mint/{report_id}", headers=AUTH(admin_token))
    assert mint_resp.status_code in (200, 201), mint_resp.text

    token = db.query(CarbonToken).filter(CarbonToken.carbon_report_id == report_id).first()
    assert token is not None
    fcb = db.query(FarmerCreditBalance).filter(FarmerCreditBalance.carbon_report_id == report_id).first()
    assert fcb is not None

    # The emission formula produces very small values per reading (max ~11 kg CH4/day),
    # never reaching the 36.76 kg threshold for 1 credit on small test farms.
    # Patch the balance to a realistic test value so marketplace tests can proceed —
    # the marketplace/listing/retirement logic is what these tests validate, not minting.
    if fcb.credits_available < 2:
        fcb.credits_earned = 5
        fcb.credits_available = 5
        token.credit_amount = 5
        db.add(fcb)
        db.add(token)
        db.commit()

    return farm_id, token, fcb


# ── Public Registry Tests ─────────────────────────────────────────────────────

class TestPublicRegistry:
    def test_public_reports_no_auth_required(self, client):
        resp = client.get("/registry/public/reports")
        assert resp.status_code == 200

    def test_public_tokens_no_auth_required(self, client):
        resp = client.get("/registry/public/tokens")
        assert resp.status_code == 200

    def test_public_farm_detail(self, client, farmer_token, fpo_profile, fpo_token, farmer_user, db):
        # Create an approved farm
        farm_resp = client.post("/farms/", json={
            "farm_name": "Public Registry Farm",
            "village": "Regtown",
            "district": "Nashik",
            "state": "Maharashtra",
            "land_area_acres": 3.0,
            "latitude": 19.9,
            "longitude": 73.7,
            "soil_type": "Loam",
            "water_source": "Rain",
            "fpo_id": fpo_profile.id,
        }, headers=AUTH(farmer_token))
        farm_id = farm_resp.json()["id"]

        resp = client.get(f"/registry/public/farms/{farm_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["farm_name"] == "Public Registry Farm"
        # Privacy: no farmer contact info
        assert "email" not in data
        assert "phone" not in data
        assert "upi_id" not in data
        assert "bank_account" not in data
        assert "wallet_address" not in data

    def test_public_report_hides_pii(self, client, minted_token):
        farm_id, token, fcb = minted_token
        resp = client.get("/registry/public/reports")
        assert resp.status_code == 200
        for report in resp.json():
            assert "farmer_email" not in report
            assert "farmer_phone" not in report
            assert "upi_id" not in report
            assert "wallet_address" not in report
            # Full hash must not appear — only short hash
            if report.get("report_hash_short"):
                assert len(report["report_hash_short"]) < 64

    def test_registry_filter_by_district(self, client, minted_token):
        resp = client.get("/registry/public/reports?district=Pune")
        assert resp.status_code == 200
        for r in resp.json():
            assert r.get("district") is None or "pune" in r["district"].lower()

    def test_token_detail_no_wallet_secrets(self, client, minted_token):
        _, token, _ = minted_token
        resp = client.get(f"/registry/public/tokens/{token.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == token.id
        # No private fields
        assert "wallet_address" not in data
        assert "key_secret" not in data
        assert "fpo_wallet" not in data


# ── Marketplace Listing Tests ─────────────────────────────────────────────────

class TestMarketplaceListings:
    def test_fpo_can_create_listing(self, client, fpo_token, minted_token):
        _, token, fcb = minted_token
        credits_to_list = min(fcb.credits_available, 1) if fcb else 1

        resp = client.post("/marketplace/listings", json={
            "farmer_credit_balance_id": fcb.id,
            "carbon_token_id": token.id,
            "credits_listed": credits_to_list,
            "price_per_credit": 50000,  # ₹500 per credit (50000 paise)
            "currency": "INR",
        }, headers=AUTH(fpo_token))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["credits_listed"] == credits_to_list
        assert data["credits_available"] == credits_to_list
        assert data["listing_status"] == "ACTIVE"

    def test_fpo_cannot_list_more_than_available(self, client, fpo_token, minted_token):
        _, token, fcb = minted_token
        resp = client.post("/marketplace/listings", json={
            "farmer_credit_balance_id": fcb.id,
            "carbon_token_id": token.id,
            "credits_listed": fcb.credits_available + 9999,
            "price_per_credit": 50000,
            "currency": "INR",
        }, headers=AUTH(fpo_token))
        # Phase 22B uses 409 (conflict) for capacity conflicts.
        assert resp.status_code in (400, 409)

    def test_farmer_cannot_create_listing(self, client, farmer_token, minted_token):
        _, token, fcb = minted_token
        resp = client.post("/marketplace/listings", json={
            "farmer_credit_balance_id": fcb.id,
            "carbon_token_id": token.id,
            "credits_listed": 1,
            "price_per_credit": 50000,
            "currency": "INR",
        }, headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_fpo_can_update_listing_price(self, client, fpo_token, minted_token):
        _, token, fcb = minted_token
        credits = min(fcb.credits_available, 1)
        create_resp = client.post("/marketplace/listings", json={
            "farmer_credit_balance_id": fcb.id,
            "carbon_token_id": token.id,
            "credits_listed": credits,
            "price_per_credit": 50000,
        }, headers=AUTH(fpo_token))
        listing_id = create_resp.json()["id"]

        update_resp = client.patch(f"/marketplace/listings/{listing_id}", json={
            "price_per_credit": 60000,
        }, headers=AUTH(fpo_token))
        assert update_resp.status_code == 200
        assert update_resp.json()["price_per_credit"] == 60000

    def test_fpo_can_cancel_listing(self, client, fpo_token, minted_token):
        _, token, fcb = minted_token
        credits = min(fcb.credits_available, 1)
        create_resp = client.post("/marketplace/listings", json={
            "farmer_credit_balance_id": fcb.id,
            "carbon_token_id": token.id,
            "credits_listed": credits,
            "price_per_credit": 50000,
        }, headers=AUTH(fpo_token))
        listing_id = create_resp.json()["id"]

        cancel_resp = client.post(f"/marketplace/listings/{listing_id}/cancel",
                                  headers=AUTH(fpo_token))
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["listing_status"] == "CANCELLED"


# ── Marketplace Order Tests ───────────────────────────────────────────────────

class TestMarketplaceOrders:
    def _create_listing(self, client, fpo_token, token, fcb, price=50000):
        credits = min(fcb.credits_available, 2) or 1
        resp = client.post("/marketplace/listings", json={
            "farmer_credit_balance_id": fcb.id,
            "carbon_token_id": token.id,
            "credits_listed": credits,
            "price_per_credit": price,
        }, headers=AUTH(fpo_token))
        assert resp.status_code == 201, resp.text
        return resp.json()

    def test_buyer_can_submit_order(self, client, buyer_token, fpo_token, minted_token):
        _, token, fcb = minted_token
        listing = self._create_listing(client, fpo_token, token, fcb)
        credits_req = min(listing["credits_available"], 1)

        resp = client.post("/marketplace/orders", json={
            "listing_id": listing["id"],
            "buyer_name": "Green Corp Ltd",
            "buyer_email": "buyer@greencorp.com",
            "buyer_organization": "Green Corp",
            "credits_requested": credits_req,
        }, headers=AUTH(buyer_token))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["order_status"] == "INTERESTED"
        assert data["quoted_amount"] == credits_req * listing["price_per_credit"]

    def test_order_quoted_amount_correct(self, client, buyer_token, fpo_token, minted_token):
        _, token, fcb = minted_token
        listing = self._create_listing(client, fpo_token, token, fcb, price=75000)
        credits_req = min(listing["credits_available"], 1)

        resp = client.post("/marketplace/orders", json={
            "listing_id": listing["id"],
            "buyer_name": "Test Buyer",
            "buyer_email": "test@buyer.com",
            "credits_requested": credits_req,
        }, headers=AUTH(buyer_token))
        assert resp.status_code == 201
        assert resp.json()["quoted_amount"] == credits_req * 75000

    def test_fpo_can_approve_order(self, client, buyer_token, fpo_token, minted_token):
        _, token, fcb = minted_token
        listing = self._create_listing(client, fpo_token, token, fcb)
        order_resp = client.post("/marketplace/orders", json={
            "listing_id": listing["id"],
            "buyer_name": "Approve Buyer",
            "buyer_email": "approve@buyer.com",
            "credits_requested": min(listing["credits_available"], 1),
        }, headers=AUTH(buyer_token))
        order_id = order_resp.json()["id"]

        resp = client.post(f"/marketplace/orders/{order_id}/approve", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        assert resp.json()["order_status"] == "APPROVED"

    def test_fpo_can_reject_order(self, client, buyer_token, fpo_token, minted_token):
        _, token, fcb = minted_token
        listing = self._create_listing(client, fpo_token, token, fcb)
        order_resp = client.post("/marketplace/orders", json={
            "listing_id": listing["id"],
            "buyer_name": "Reject Buyer",
            "buyer_email": "reject@buyer.com",
            "credits_requested": min(listing["credits_available"], 1),
        }, headers=AUTH(buyer_token))
        order_id = order_resp.json()["id"]

        resp = client.post(f"/marketplace/orders/{order_id}/reject",
                           json={"remarks": "Not a qualified buyer"},
                           headers=AUTH(fpo_token))
        assert resp.status_code == 200
        assert resp.json()["order_status"] == "REJECTED"

    def test_farmer_cannot_view_orders(self, client, farmer_token):
        resp = client.get("/marketplace/orders", headers=AUTH(farmer_token))
        assert resp.status_code == 403

    def test_listing_orders_empty_returns_list_not_404(self, client, fpo_token, minted_token):
        """GET /marketplace/listings/{id}/orders returns [] not 404 when no orders exist."""
        _, token, fcb = minted_token
        listing = self._create_listing(client, fpo_token, token, fcb)
        resp = client.get(f"/marketplace/listings/{listing['id']}/orders",
                          headers=AUTH(fpo_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert data == []      # no orders yet — must be empty list, not 404

    def test_listing_orders_returns_orders_after_submission(
        self, client, fpo_token, buyer_token, minted_token
    ):
        """GET /marketplace/listings/{id}/orders returns submitted orders."""
        _, token, fcb = minted_token
        listing = self._create_listing(client, fpo_token, token, fcb)

        # Buyer submits an order
        client.post("/marketplace/orders", json={
            "listing_id": listing["id"],
            "buyer_name": "Detail Buyer",
            "buyer_email": "detail@buyer.com",
            "credits_requested": 1,
        }, headers=AUTH(buyer_token))

        resp = client.get(f"/marketplace/listings/{listing['id']}/orders",
                          headers=AUTH(fpo_token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["order_status"] == "INTERESTED"


# ── Retirement Certificate Tests ──────────────────────────────────────────────

class TestRetirementCertificate:
    def _setup_approved_order(self, client, buyer_token, fpo_token, token, fcb, price=50000):
        credits = min(fcb.credits_available, 1) or 1
        listing_resp = client.post("/marketplace/listings", json={
            "farmer_credit_balance_id": fcb.id,
            "carbon_token_id": token.id,
            "credits_listed": credits,
            "price_per_credit": price,
        }, headers=AUTH(fpo_token))
        listing = listing_resp.json()

        order_resp = client.post("/marketplace/orders", json={
            "listing_id": listing["id"],
            "buyer_name": "Cert Buyer",
            "buyer_email": "cert@buyer.com",
            "credits_requested": min(listing["credits_available"], 1),
        }, headers=AUTH(buyer_token))
        order_id = order_resp.json()["id"]

        client.post(f"/marketplace/orders/{order_id}/approve", headers=AUTH(fpo_token))
        # Phase 22B: retirement now requires PAID, so mark-paid before returning.
        client.post(f"/marketplace/orders/{order_id}/mark-paid", headers=AUTH(fpo_token))
        return listing["id"], order_id

    def test_retire_creates_certificate(self, client, buyer_token, fpo_token, minted_token):
        _, token, fcb = minted_token
        listing_id, order_id = self._setup_approved_order(client, buyer_token, fpo_token, token, fcb)

        resp = client.post(f"/marketplace/orders/{order_id}/retire",
                           json={"retirement_reason": "Carbon offset for 2024"},
                           headers=AUTH(fpo_token))
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["order_id"] == order_id
        assert data["buyer_name"] == "Cert Buyer"
        assert data["credits_retired"] == 1
        assert len(data["certificate_hash"]) == 64  # SHA-256 hex

    def test_retire_does_not_double_decrement_listing_credits(
        self, client, buyer_token, fpo_token, minted_token, db
    ):
        """
        Phase 22B change: reservation happens at approve, not at retire.
        `listing.credits_available` is decremented by approve() and MUST NOT
        be decremented again by retire(). This test proves the invariant.
        """
        _, token, fcb = minted_token
        listing_id, order_id = self._setup_approved_order(client, buyer_token, fpo_token, token, fcb)

        from app.models.marketplace import MarketplaceListing
        listing_before = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        before_avail = listing_before.credits_available  # already 0 for our single-credit listing

        client.post(f"/marketplace/orders/{order_id}/retire", headers=AUTH(fpo_token))

        db.expire(listing_before)
        db.refresh(listing_before)
        assert listing_before.credits_available == before_avail

    def test_cannot_retire_twice(self, client, buyer_token, fpo_token, minted_token):
        _, token, fcb = minted_token
        listing_id, order_id = self._setup_approved_order(client, buyer_token, fpo_token, token, fcb)

        client.post(f"/marketplace/orders/{order_id}/retire", headers=AUTH(fpo_token))
        resp2 = client.post(f"/marketplace/orders/{order_id}/retire", headers=AUTH(fpo_token))
        # Phase 22B: second retire either fails the status check (400)
        # or the certificate-uniqueness check (409). Both are correct.
        assert resp2.status_code in (400, 409)

    def test_certificate_hash_is_deterministic(self, db):
        from app.models.marketplace import compute_certificate_hash
        h1 = compute_certificate_hash(1, 2, "Test Buyer", 10, "2024-01-01T00:00:00+00:00")
        h2 = compute_certificate_hash(1, 2, "Test Buyer", 10, "2024-01-01T00:00:00+00:00")
        assert h1 == h2
        assert len(h1) == 64

    def test_get_certificate(self, client, buyer_token, fpo_token, minted_token):
        _, token, fcb = minted_token
        listing_id, order_id = self._setup_approved_order(client, buyer_token, fpo_token, token, fcb)
        client.post(f"/marketplace/orders/{order_id}/retire", headers=AUTH(fpo_token))

        resp = client.get(f"/marketplace/orders/{order_id}/certificate", headers=AUTH(fpo_token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["certificate_hash"]
        assert data["buyer_name"] == "Cert Buyer"
