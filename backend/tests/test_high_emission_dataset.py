"""
High-Emission Test Dataset — Phase 10A/10B End-to-End Validation

Generates realistic livestock/manure-management carbon reduction scenarios
with 5–20 tCO₂e reductions. Tests the complete pipeline:

    Report Submission → Verification → Credit Issuance → Tokenization
    → Custodial Ledger Update → Farmer Credit Balance
    → FPO Mock Payout → Payout History

METHODOLOGY (IPCC Tier 1 livestock methane):
  Cattle (dairy, beef): ~100–200 kg CH₄/head/year
  Buffaloes:           ~55 kg CH₄/head/year
  Goats/Sheep:         ~5–8 kg CH₄/head/year
  Manure management improvement reduces enteric fermentation 10–30%

  CH₄ GWP100 = 28 × CO₂e
  1 tCO₂e = 1 carbon credit

  Example: 10 dairy cattle × 150 kg CH₄/yr × 0.20 improvement
           = 300 kg CH₄ reduced = 300 × 28 / 1000 = 8.4 tCO₂e = 8 credits

SCENARIOS:
  A) Small herd SRI rice + 12 cattle → 5 credits       (borderline eligible)
  B) Medium dairy farm, 20 cattle     → 8 credits       (verified, payout eligible)
  C) Large mixed livestock operation  → 15 credits      (issued + distributed)
  D) Buffalo herd, manure biodigester → 12 credits      (tokenized, ready for payout)
  E) Zero-emission edge case          → 0 credits       (certificate only, no payout)

NOTE: All users/data labeled [TEST-DEMO]. Isolated test DB — no production impact.
"""
import math
from datetime import datetime, timezone, timedelta

import pytest

from app.models.user import User, UserRole
from app.models.fpo import FPOProfile
from app.models.farm import Farm, CropCycle
from app.models.carbon_report import CarbonReport, ReportStatus
from app.models.farmer_credit_balance import FarmerCreditBalance, CreditBalanceStatus
from app.models.farmer_profile import FarmerProfile, PayoutMethod
from app.models.payout import Payout, PayoutStatus
from app.security import hash_password


# ── Shared methane / CO₂e helpers ────────────────────────────────────────────

CH4_GWP100 = 28  # IPCC AR6 methane global warming potential (20-yr excluded)


def ch4_to_co2e(kg_ch4: float) -> float:
    """Convert kg CH₄ to tonnes CO₂e."""
    return (kg_ch4 * CH4_GWP100) / 1000


def credits_from_co2e(co2e_tonnes: float) -> int:
    """Integer credits = floor(tCO₂e). Matches GreenChain minting logic."""
    return math.floor(co2e_tonnes)


# ── Scenario definitions ──────────────────────────────────────────────────────

SCENARIOS = [
    # (name, livestock, baseline_ch4_kg, improvement_pct, practice_note)
    {
        "id": "A",
        "farm_name": "[TEST] Ravi Small Farm - SRI Rice + 12 Cattle",
        "farmer_email": "test_ravi@demo.greenchain",
        "farmer_name": "Ravi Kumar [TEST]",
        "livestock": "12 dairy cattle",
        "baseline_ch4_kg": 12 * 150.0,         # 12 cattle × 150 kg CH₄/yr = 1800 kg
        "improvement_pct": 0.12,                # 12% reduction via improved feed
        "practice": "Improved_Feed_SRI",
        "reduction_practice": "SRI",
        "baseline_method": "IPCC_TIER1",
        "upi_id": "ravi.kumar@okaxis",
        "expected_credits_ge": 5,               # ≥5 credits
        "expected_credits_le": 7,
        "payout_eligible": True,
        "payout_price_per_credit_paise": 75_000,  # ₹750 per credit
    },
    {
        "id": "B",
        "farm_name": "[TEST] Meena Medium Dairy - 20 Holstein Cattle",
        "farmer_email": "test_meena@demo.greenchain",
        "farmer_name": "Meena Devi [TEST]",
        "livestock": "20 Holstein dairy cattle",
        # 20 cattle × 160 kg CH₄/yr = 3200 kg baseline
        # 16% reduction = 512 kg → 14.336 tCO₂e → 14 credits
        "baseline_ch4_kg": 20 * 160.0,
        "improvement_pct": 0.16,                 # 16% reduction via biodigester
        "practice": "Biodigester_Manure",
        "reduction_practice": "BIODIGESTER",
        "baseline_method": "IPCC_TIER1",
        "upi_id": "meena.devi@okicici",
        "expected_credits_ge": 13,
        "expected_credits_le": 15,
        "payout_eligible": True,
        "payout_price_per_credit_paise": 80_000,  # ₹800 per credit
    },
    {
        "id": "C",
        "farm_name": "[TEST] Singh Large Mixed Livestock - 15 Cattle + 30 Goats",
        "farmer_email": "test_singh@demo.greenchain",
        "farmer_name": "Gurpreet Singh [TEST]",
        "livestock": "15 Sahiwal cattle + 30 goats",
        # 15 cattle × 130 kg + 30 goats × 6 kg = 1950 + 180 = 2130 kg CH₄/yr
        # 25% reduction = 532.5 kg → 14.91 tCO₂e → 14 credits → use 17% for ~15 credits
        # 15 cattle × 130 kg × 0.25 + 30 × 6 × 0.25 = 487.5 + 45 = 532.5 kg → 14.91 tCO₂e
        "baseline_ch4_kg": 15 * 130.0 + 30 * 6.0,
        "improvement_pct": 0.27,                 # 27% via pasture management + biochar → ~16 tCO₂e
        "practice": "Pasture_Biochar",
        "reduction_practice": "BIOCHAR",
        "baseline_method": "IPCC_TIER1",
        "upi_id": "gurpreet.singh@okhdfc",
        "expected_credits_ge": 15,
        "expected_credits_le": 18,
        "payout_eligible": True,
        "status_override": CreditBalanceStatus.DISTRIBUTED,  # fully distributed (historical)
        "payout_price_per_credit_paise": 90_000,  # ₹900 per credit
    },
    {
        "id": "D",
        "farm_name": "[TEST] Fatima Buffalo Herd - 25 Murrah Buffaloes",
        "farmer_email": "test_fatima@demo.greenchain",
        "farmer_name": "Fatima Sheikh [TEST]",
        "livestock": "25 Murrah buffaloes",
        "baseline_ch4_kg": 25 * 55.0,            # 25 buffaloes × 55 kg CH₄/yr = 1375 kg
        "improvement_pct": 0.30,                  # 30% via anaerobic biodigester
        "practice": "Anaerobic_Biodigester",
        "reduction_practice": "BIODIGESTER",
        "baseline_method": "IPCC_TIER1",
        "upi_id": "fatima.sheikh@paytm",
        "expected_credits_ge": 11,
        "expected_credits_le": 13,
        "payout_eligible": True,
        "payout_price_per_credit_paise": 85_000,  # ₹850 per credit
    },
    {
        "id": "E",
        "farm_name": "[TEST] Zero-Cert Edge - Minimal Reduction Farm",
        "farmer_email": "test_zero@demo.greenchain",
        "farmer_name": "Zero Edge [TEST]",
        "livestock": "2 goats",
        "baseline_ch4_kg": 2 * 6.0,             # 2 goats × 6 kg CH₄/yr = 12 kg
        "improvement_pct": 0.20,                 # 20% = 2.4 kg CH₄ = 0.067 tCO₂e → 0 credits
        "practice": "Feed_Improvement",
        "reduction_practice": "SRI",
        "baseline_method": "IPCC_TIER1",
        "upi_id": None,
        "expected_credits_ge": 0,
        "expected_credits_le": 0,
        "payout_eligible": False,
    },
]


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_test_user(db, name: str, email: str, role: UserRole) -> User:
    user = User(
        name=name,
        email=email,
        password_hash=hash_password("testpass123"),
        role=role,
        is_active=True,
        is_approved=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_fpo_user(db):
    return _make_test_user(db, "FPO Demo [TEST]", "test_fpo@demo.greenchain", UserRole.FPO)


@pytest.fixture
def test_fpo_profile(db, test_fpo_user):
    profile = FPOProfile(
        user_id=test_fpo_user.id,
        organization_name="GreenChain Demo FPO [TEST]",
        registration_number="DEMO-FPO-001",
        state="Maharashtra",
        district="Pune",
        wallet_address="0xDemoFPOWalletAddress1234567890abcdef001",
        wallet_verified=True,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _build_scenario(db, scenario: dict, fpo_user: User, fpo_profile: FPOProfile):
    """Build a complete scenario: user → farm → cycle → report → balance."""
    farmer = _make_test_user(
        db, scenario["farmer_name"], scenario["farmer_email"], UserRole.FARMER
    )

    # Farmer profile with UPI payout
    if scenario.get("upi_id"):
        fp = FarmerProfile(
            user_id=farmer.id,
            preferred_payout_method=PayoutMethod.UPI,
            upi_id=scenario["upi_id"],
            payout_details_verified=True,
            payout_verification_method="FORMAT_CHECK",
            payout_details_verified_at=datetime.now(timezone.utc),
        )
        db.add(fp)

    farm = Farm(
        farmer_id=farmer.id,
        fpo_id=fpo_profile.id,
        farm_name=scenario["farm_name"],
        village="Demo Village",
        district="Pune",
        state="Maharashtra",
        land_area_acres=round(5.0 + (hash(scenario["id"]) % 20), 1),
        latitude=18.5 + (hash(scenario["id"]) % 100) / 1000,
        longitude=73.8 + (hash(scenario["id"]) % 100) / 1000,
        soil_type="Loamy",
        water_source="Canal",
        is_approved=True,
    )
    db.add(farm)
    db.commit()
    db.refresh(farm)

    cycle = CropCycle(
        farm_id=farm.id,
        crop_type="Mixed Livestock",
        season="Annual",
        start_date=datetime.now(timezone.utc) - timedelta(days=365),
        end_date=datetime.now(timezone.utc) - timedelta(days=5),
        baseline_method=scenario["baseline_method"],
        reduction_practice=scenario["reduction_practice"],
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)

    # Compute methane + CO₂e values
    baseline_ch4 = scenario["baseline_ch4_kg"]
    reduction_ch4 = baseline_ch4 * scenario["improvement_pct"]
    current_ch4 = baseline_ch4 - reduction_ch4
    co2e = ch4_to_co2e(reduction_ch4)
    credits = credits_from_co2e(co2e)

    # Report hash — deterministic for test repeatability
    report_hash_data = f"test-{scenario['id']}-{baseline_ch4}-{reduction_ch4}"
    import hashlib
    report_hash = hashlib.sha256(report_hash_data.encode()).hexdigest()

    report = CarbonReport(
        farm_id=farm.id,
        crop_cycle_id=cycle.id,
        baseline_methane_kg=round(baseline_ch4, 2),
        current_methane_kg=round(current_ch4, 2),
        methane_reduction_kg=round(reduction_ch4, 2),
        co2e_reduction_tonnes=round(co2e, 4),
        estimated_credits=credits,
        report_hash=report_hash[:64],
        status=ReportStatus.VERIFIED,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    status = scenario.get("status_override", CreditBalanceStatus.TOKENIZED)
    distributed = credits if status == CreditBalanceStatus.DISTRIBUTED else 0
    available = credits - distributed

    balance = FarmerCreditBalance(
        farmer_id=farmer.id,
        fpo_id=fpo_profile.id,
        carbon_report_id=report.id,
        credits_earned=credits,
        credits_available=available,
        credits_distributed=distributed,
        status=status,
    )
    db.add(balance)
    db.commit()
    db.refresh(balance)

    return {
        "farmer": farmer,
        "farm": farm,
        "cycle": cycle,
        "report": report,
        "balance": balance,
        "co2e": co2e,
        "credits": credits,
        "baseline_ch4": baseline_ch4,
        "reduction_ch4": reduction_ch4,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestHighEmissionScenarios:
    """
    Verify that each scenario produces the expected credit count
    and that calculated values are physically reasonable.
    """

    def _run_scenario(self, db, test_fpo_user, test_fpo_profile, scenario_id: str):
        sc = next(s for s in SCENARIOS if s["id"] == scenario_id)
        return _build_scenario(db, sc, test_fpo_user, test_fpo_profile)

    # ── Scenario A: Small farm, 12 cattle, ~5-7 credits ──────────────────────

    def test_scenario_A_small_herd_credits(self, db, test_fpo_user, test_fpo_profile):
        """12 dairy cattle + SRI → 5–7 tCO₂e → 5–7 credits."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "A")
        sc = SCENARIOS[0]
        assert sc["expected_credits_ge"] <= result["credits"] <= sc["expected_credits_le"], (
            f"Expected {sc['expected_credits_ge']}–{sc['expected_credits_le']} credits, "
            f"got {result['credits']} (co2e={result['co2e']:.3f})"
        )
        assert result["co2e"] >= 5.0
        assert result["balance"].credits_earned == result["credits"]
        assert result["balance"].credits_available == result["credits"]

    def test_scenario_A_methane_values_are_physical(self, db, test_fpo_user, test_fpo_profile):
        """Baseline and current methane must be positive; reduction > 0."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "A")
        assert result["report"].baseline_methane_kg > 0
        assert result["report"].current_methane_kg > 0
        assert result["report"].methane_reduction_kg > 0
        assert result["report"].current_methane_kg < result["report"].baseline_methane_kg

    # ── Scenario B: Medium dairy, 20 cattle, ~8-10 credits, payout eligible ──

    def test_scenario_B_medium_dairy_credits(self, db, test_fpo_user, test_fpo_profile):
        """20 Holstein cattle + biodigester → 13–15 credits (14.3 tCO₂e)."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "B")
        sc = SCENARIOS[1]
        assert sc["expected_credits_ge"] <= result["credits"] <= sc["expected_credits_le"], (
            f"Expected {sc['expected_credits_ge']}–{sc['expected_credits_le']} credits, "
            f"got {result['credits']}"
        )
        assert result["credits"] >= 13

    def test_scenario_B_farmer_has_upi_payout_details(self, db, test_fpo_user, test_fpo_profile):
        """Farmer B should have verified UPI payout details."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "B")
        from app.models.farmer_profile import FarmerProfile
        fp = db.query(FarmerProfile).filter(
            FarmerProfile.user_id == result["farmer"].id
        ).first()
        assert fp is not None
        assert fp.preferred_payout_method == PayoutMethod.UPI
        assert fp.payout_details_verified is True
        assert fp.upi_id == "meena.devi@okicici"

    def test_scenario_B_balance_is_payout_eligible(self, db, test_fpo_user, test_fpo_profile):
        """Farmer B balance: credits_available > 0, status TOKENIZED."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "B")
        assert result["balance"].credits_available > 0
        assert result["balance"].status == CreditBalanceStatus.TOKENIZED

    # ── Scenario C: Large mixed, ~15-17 credits, fully distributed ───────────

    def test_scenario_C_large_mixed_high_credits(self, db, test_fpo_user, test_fpo_profile):
        """30 cattle + 50 goats + biochar → ≥15 credits."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "C")
        sc = SCENARIOS[2]
        assert sc["expected_credits_ge"] <= result["credits"] <= sc["expected_credits_le"]
        assert result["credits"] >= 15

    def test_scenario_C_is_distributed(self, db, test_fpo_user, test_fpo_profile):
        """Scenario C balance is fully distributed (historical payout)."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "C")
        assert result["balance"].status == CreditBalanceStatus.DISTRIBUTED
        assert result["balance"].credits_distributed == result["credits"]
        assert result["balance"].credits_available == 0

    def test_scenario_C_co2e_exceeds_15(self, db, test_fpo_user, test_fpo_profile):
        """Scenario C produces >15 tCO₂e reduction."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "C")
        assert result["co2e"] >= 15.0

    # ── Scenario D: Buffalo herd, 25 Murrah, ~11-13 credits ──────────────────

    def test_scenario_D_buffalo_herd_credits(self, db, test_fpo_user, test_fpo_profile):
        """25 Murrah buffaloes + anaerobic biodigester → 11–13 credits."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "D")
        sc = SCENARIOS[3]
        assert sc["expected_credits_ge"] <= result["credits"] <= sc["expected_credits_le"]

    def test_scenario_D_baseline_uses_ipcc_buffalo_factor(self, db, test_fpo_user, test_fpo_profile):
        """Buffalo baseline: 25 × 55 kg CH₄/yr = 1375 kg (IPCC default)."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "D")
        assert abs(result["report"].baseline_methane_kg - 1375.0) < 1.0

    def test_scenario_D_30pct_reduction_from_biodigester(self, db, test_fpo_user, test_fpo_profile):
        """Biodigester achieves ≥25% CH₄ reduction from baseline."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "D")
        actual_pct = result["reduction_ch4"] / result["baseline_ch4"]
        assert actual_pct >= 0.25

    # ── Scenario E: Zero-credit edge case ────────────────────────────────────

    def test_scenario_E_zero_credits(self, db, test_fpo_user, test_fpo_profile):
        """2 goats at 20% improvement → <1 tCO₂e → 0 credits."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "E")
        assert result["credits"] == 0
        assert result["co2e"] < 1.0

    def test_scenario_E_balance_has_zero_available(self, db, test_fpo_user, test_fpo_profile):
        """Zero-credit balance: all credit counts are 0."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "E")
        assert result["balance"].credits_earned == 0
        assert result["balance"].credits_available == 0

    def test_scenario_E_no_payout_no_upi(self, db, test_fpo_user, test_fpo_profile):
        """Zero-credit farmer has no payout profile."""
        result = self._run_scenario(db, test_fpo_user, test_fpo_profile, "E")
        fp = db.query(FarmerProfile).filter(
            FarmerProfile.user_id == result["farmer"].id
        ).first()
        assert fp is None


class TestHighEmissionEndToEndPayout:
    """
    End-to-end payout flow for Scenario B (medium dairy, ≥8 credits).
    Verifies the full pipeline: balance → initiate payout → history.
    """

    def _login(self, client, email: str, password: str = "testpass123") -> str:
        res = client.post("/auth/login", json={"email": email, "password": password})
        assert res.status_code == 200, f"Login failed: {res.text}"
        return res.json()["access_token"]

    def _auth_headers(self, client, email: str) -> dict:
        return {"Authorization": f"Bearer {self._login(client, email)}"}

    def test_full_pipeline_report_to_mock_payout(
        self, client, db, test_fpo_user, test_fpo_profile
    ):
        """
        End-to-end: verified report → FarmerCreditBalance → FPO lists balances
        → initiate mock payout → payout history shows COMPLETED.
        """
        sc = next(s for s in SCENARIOS if s["id"] == "B")
        result = _build_scenario(db, sc, test_fpo_user, test_fpo_profile)
        farmer = result["farmer"]
        balance = result["balance"]
        credits = result["credits"]
        assert credits >= 8, "Scenario B must produce ≥8 credits for this test"

        fpo_headers = self._auth_headers(client, "test_fpo@demo.greenchain")

        # FPO lists farmer credit balances
        list_res = client.get("/fpo/credits/farmers", headers=fpo_headers)
        assert list_res.status_code == 200
        balances_data = list_res.json()
        assert any(b["id"] == balance.id for b in balances_data), \
            "Balance not found in FPO farmer list"

        # FPO views payout details for this balance (masked UPI)
        detail_res = client.get(
            f"/fpo/credits/farmers/{balance.id}/payout-details",
            headers=fpo_headers,
        )
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["has_payout_details"] is True
        assert detail["payout_details_verified"] is True
        # UPI must be masked — never expose raw value
        assert "okicici" in (detail["upi_id_masked"] or "")
        assert detail.get("upi_id_masked") != "meena.devi@okicici", \
            "Raw UPI ID must not be returned to FPO!"

        # FPO initiates mock payout
        price_per_credit = 80_000  # ₹800 in paise
        initiate_res = client.post(
            "/fpo/payouts/initiate",
            headers=fpo_headers,
            json={
                "credit_balance_id": balance.id,
                "amount_credits": credits,
                "price_per_credit": price_per_credit,
                "currency": "INR",
                "remarks": "[TEST] Phase 10B mock payout - Scenario B",
            },
        )
        assert initiate_res.status_code in (200, 201), (
            f"Payout initiation failed: {initiate_res.text}"
        )
        payout_data = initiate_res.json()
        payout_id = payout_data["id"]
        assert payout_data["amount_credits"] == credits
        assert payout_data["payout_amount"] == credits * price_per_credit
        expected_status = payout_data.get("status", "")
        assert expected_status in ("INITIATED", "COMPLETED", "PROCESSING"), \
            f"Unexpected initial payout status: {expected_status}"

        # FPO views payout history
        history_res = client.get("/fpo/payouts", headers=fpo_headers)
        assert history_res.status_code == 200
        history = history_res.json()
        assert any(p["id"] == payout_id for p in history), "Payout not found in history"

        # Farmer views their payouts
        farmer_headers = self._auth_headers(client, farmer.email)
        farmer_history_res = client.get("/farmers/payouts", headers=farmer_headers)
        assert farmer_history_res.status_code == 200
        farmer_history = farmer_history_res.json()
        assert any(p["id"] == payout_id for p in farmer_history), \
            "Payout not in farmer history"

    def test_zero_credit_balance_payout_blocked(
        self, client, db, test_fpo_user, test_fpo_profile
    ):
        """Scenario E: zero-credit balance cannot be paid out."""
        sc = next(s for s in SCENARIOS if s["id"] == "E")
        result = _build_scenario(db, sc, test_fpo_user, test_fpo_profile)
        balance = result["balance"]
        assert balance.credits_available == 0

        fpo_headers = self._auth_headers(client, "test_fpo@demo.greenchain")
        initiate_res = client.post(
            "/fpo/payouts/initiate",
            headers=fpo_headers,
            json={
                "credit_balance_id": balance.id,
                "amount_credits": 0,
                "price_per_credit": 80_000,
                "currency": "INR",
            },
        )
        # Backend should reject 0-credit payout
        assert initiate_res.status_code in (400, 422), (
            f"Zero-credit payout should be rejected, got {initiate_res.status_code}"
        )

    def test_mock_payout_does_not_expose_credentials(
        self, client, db, test_fpo_user, test_fpo_profile
    ):
        """Mock payout response must never contain Razorpay credentials."""
        sc = next(s for s in SCENARIOS if s["id"] == "B")
        result = _build_scenario(db, sc, test_fpo_user, test_fpo_profile)
        balance = result["balance"]
        credits = result["credits"]

        fpo_headers = self._auth_headers(client, "test_fpo@demo.greenchain")
        initiate_res = client.post(
            "/fpo/payouts/initiate",
            headers=fpo_headers,
            json={
                "credit_balance_id": balance.id,
                "amount_credits": credits,
                "price_per_credit": 80_000,
                "currency": "INR",
            },
        )
        if initiate_res.status_code in (200, 201):
            response_str = str(initiate_res.json())
            assert "rzp_" not in response_str.lower(), "Razorpay key leaked in payout response!"
            assert "secret" not in response_str.lower(), "Secret leaked in payout response!"


class TestCo2eCalculations:
    """
    Unit tests verifying the CO₂e math for each scenario.
    These are deterministic — they don't touch the database.
    """

    @pytest.mark.parametrize("scenario", SCENARIOS)
    def test_co2e_calculation_matches_expected_range(self, scenario):
        """Each scenario's CO₂e math produces credits within expected range."""
        baseline = scenario["baseline_ch4_kg"]
        reduction_ch4 = baseline * scenario["improvement_pct"]
        co2e = ch4_to_co2e(reduction_ch4)
        credits = credits_from_co2e(co2e)

        assert credits >= scenario["expected_credits_ge"], (
            f"Scenario {scenario['id']}: got {credits} credits (co2e={co2e:.3f}), "
            f"expected ≥{scenario['expected_credits_ge']}"
        )
        assert credits <= scenario["expected_credits_le"], (
            f"Scenario {scenario['id']}: got {credits} credits (co2e={co2e:.3f}), "
            f"expected ≤{scenario['expected_credits_le']}"
        )

    @pytest.mark.parametrize("scenario", [s for s in SCENARIOS if s["id"] != "E"])
    def test_eligible_scenarios_have_positive_credits(self, scenario):
        """All non-zero scenarios should produce ≥1 credit."""
        baseline = scenario["baseline_ch4_kg"]
        reduction_ch4 = baseline * scenario["improvement_pct"]
        co2e = ch4_to_co2e(reduction_ch4)
        credits = credits_from_co2e(co2e)
        assert credits >= 1

    def test_total_dataset_range_is_5_to_20_tco2e(self):
        """Each individual scenario (except E) produces 5–20 tCO₂e."""
        for sc in SCENARIOS:
            if sc["id"] == "E":
                continue
            baseline = sc["baseline_ch4_kg"]
            reduction_ch4 = baseline * sc["improvement_pct"]
            co2e = ch4_to_co2e(reduction_ch4)
            assert 5.0 <= co2e, (
                f"Scenario {sc['id']}: co2e={co2e:.3f} below 5 tCO₂e minimum"
            )
            # Upper bound: scenarios may reach up to 20 tCO₂e
            # (Scenario C is intentionally at the high end ~16 tCO₂e)
            assert co2e <= 20.0, (
                f"Scenario {sc['id']}: co2e={co2e:.3f} exceeds 20 tCO₂e maximum. "
                f"Reduce livestock count or improvement_pct."
            )

    def test_ch4_to_co2e_gwp_factor(self):
        """1 kg CH₄ = 0.028 tCO₂e (GWP100=28)."""
        assert abs(ch4_to_co2e(1000.0) - 28.0) < 0.001

    def test_credits_floor_rounding(self):
        """Credits are floor(tCO₂e) — fractional tonnes don't count."""
        assert credits_from_co2e(8.99) == 8
        assert credits_from_co2e(9.00) == 9
        assert credits_from_co2e(0.99) == 0
