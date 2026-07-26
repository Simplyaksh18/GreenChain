"""
test_ai_layer.py — Phase 18 AI Layer tests.

Tests verify:
  1.  All 4 endpoints exist and return correct schema shape
  2.  Role access is enforced (403 for wrong role)
  3.  AI never alters report values, credit amounts, or approval status
  4.  AI never auto-approves or auto-rejects verifications
  5.  Rules fallback when Groq API is unavailable or key is missing
  6.  Missing / incomplete data is handled gracefully (no 500)
  7.  Disclaimer is present in all responses
  8.  AI mode is reported in all responses
  9.  Provider abstraction: rules vs groq selection
  10. Singleton reset utility works for test isolation
"""

import os
os.environ["ENV_FILE"] = ".env.test"
os.environ["DATABASE_URL"] = "sqlite:///./test_greenchain.db"

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.ai_schema import DISCLAIMER
from app.services.ai_provider import (
    RulesAIProvider,
    GroqAIProvider,
    get_ai_provider,
    reset_ai_provider,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _auth(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ══════════════════════════════════════════════════════════════════════════════
# Class 1 — Provider abstraction
# ══════════════════════════════════════════════════════════════════════════════

class TestProviderAbstraction:

    def setup_method(self):
        reset_ai_provider()

    def teardown_method(self):
        reset_ai_provider()

    def test_rules_provider_returns_string(self):
        p = RulesAIProvider()
        result = p.generate("test", {"_operation": "generic"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_rules_mode_name(self):
        assert RulesAIProvider().mode_name == "rules"

    def test_groq_mode_name(self):
        assert GroqAIProvider().mode_name == "groq"

    def test_factory_returns_rules_by_default(self):
        with patch("app.config.settings.AI_MODE", "rules"):
            provider = get_ai_provider()
        assert isinstance(provider, RulesAIProvider)

    def test_factory_returns_groq_when_configured(self):
        reset_ai_provider()
        with patch("app.config.settings.AI_MODE", "groq"):
            provider = get_ai_provider()
        assert isinstance(provider, GroqAIProvider)

    def test_singleton_cached(self):
        p1 = get_ai_provider()
        p2 = get_ai_provider()
        assert p1 is p2

    def test_reset_clears_singleton(self):
        p1 = get_ai_provider()
        reset_ai_provider()
        p2 = get_ai_provider()
        assert p1 is not p2


# ══════════════════════════════════════════════════════════════════════════════
# Class 2 — Rules engine correctness
# ══════════════════════════════════════════════════════════════════════════════

class TestRulesEngine:

    def setup_method(self):
        reset_ai_provider()

    def test_mrv_summary_no_report(self):
        p = RulesAIProvider()
        ctx = {
            "_operation": "mrv_summary",
            "farm_name": "Test Farm",
            "has_carbon_report": False,
            "report_status": "",
            "estimated_credits": 0,
            "sensor_reading_count": 0,
            "has_soc_estimate": False,
            "has_satellite_obs": False,
        }
        result = p.generate("", ctx)
        assert "No carbon report" in result

    def test_mrv_summary_with_credits(self):
        p = RulesAIProvider()
        ctx = {
            "_operation": "mrv_summary",
            "farm_name": "Green Farm",
            "has_carbon_report": True,
            "report_status": "APPROVED",
            "estimated_credits": 42,
            "sensor_reading_count": 20,
            "has_soc_estimate": True,
            "has_satellite_obs": False,
        }
        result = p.generate("", ctx)
        assert "42" in result
        assert "Green Farm" in result

    def test_mrv_summary_zero_credits_warning(self):
        p = RulesAIProvider()
        ctx = {
            "_operation": "mrv_summary",
            "farm_name": "Empty Farm",
            "has_carbon_report": True,
            "report_status": "DRAFT",   # zero-credits warning fires on DRAFT with 0 credits
            "estimated_credits": 0,
            "sensor_reading_count": 5,
            "has_soc_estimate": False,
            "has_satellite_obs": False,
        }
        result = p.generate("", ctx)
        assert "zero" in result.lower() or "credit" in result.lower()

    def test_verification_assist_high_risk_no_evidence(self):
        p = RulesAIProvider()
        ctx = {
            "_operation": "verification_assist",
            "evidence_file_count": 0,
            "sensor_reading_count": 0,
            "risk_level": "HIGH",
            "farm_approved": False,
        }
        result = p.generate("", ctx)
        assert "HIGH" in result
        assert "evidence" in result.lower()

    def test_fpo_action_summary_empty(self):
        p = RulesAIProvider()
        ctx = {
            "_operation": "fpo_action_summary",
            "pending_farm_approvals": 0,
            "mintable_report_count": 0,
            "initiated_payout_count": 0,
            "active_listing_count": 0,
            "evidence_gap_count": 0,
        }
        result = p.generate("", ctx)
        assert "up to date" in result.lower()

    def test_fpo_action_summary_with_items(self):
        p = RulesAIProvider()
        ctx = {
            "_operation": "fpo_action_summary",
            "pending_farm_approvals": 3,
            "mintable_report_count": 2,
            "initiated_payout_count": 0,
            "active_listing_count": 1,
            "evidence_gap_count": 0,
        }
        result = p.generate("", ctx)
        assert "3" in result or "farm" in result.lower()

    def test_farmer_help_explain_credits(self):
        p = RulesAIProvider()
        ctx = {
            "_operation": "farmer_help",
            "topic": "explain_credits",
            "estimated_credits": 0,
            "sensor_reading_count": 0,
        }
        result = p.generate("", ctx)
        assert "carbon credits" in result.lower()

    def test_farmer_help_why_zero_credits(self):
        p = RulesAIProvider()
        ctx = {
            "_operation": "farmer_help",
            "topic": "why_zero_credits",
            "estimated_credits": 0,
            "sensor_reading_count": 5,
        }
        result = p.generate("", ctx)
        assert "0" in result or "zero" in result.lower()

    def test_unknown_operation_returns_fallback(self):
        p = RulesAIProvider()
        result = p.generate("", {"_operation": "does_not_exist"})
        assert "not available" in result.lower()

    def test_mrv_summary_satellite_count_in_output(self):
        p = RulesAIProvider()
        ctx = {
            "_operation": "mrv_summary",
            "farm_name": "Satellite Farm",
            "has_carbon_report": True,
            "report_status": "VERIFIED",
            "estimated_credits": 5,
            "sensor_reading_count": 20,
            "has_soc_estimate": True,
            "has_satellite_obs": True,
            "satellite_count": 4,
            "avg_ndvi": 0.72,
            "drone_count": 0,
            "evidence_count": 3,
            "soc_confidence": 0.8,
            "is_minted": False,
            "verification_status": None,
        }
        result = p.generate("", ctx)
        assert "VERIFIED" in result
        assert "4" in result  # satellite count

    def test_mrv_summary_no_satellite_warns(self):
        p = RulesAIProvider()
        ctx = {
            "_operation": "mrv_summary",
            "farm_name": "No Sat Farm",
            "has_carbon_report": True,
            "report_status": "DRAFT",
            "estimated_credits": 3,
            "sensor_reading_count": 14,
            "has_soc_estimate": True,
            "has_satellite_obs": False,
            "satellite_count": 0,
            "avg_ndvi": None,
            "drone_count": 0,
            "evidence_count": 2,
            "soc_confidence": 0.6,
            "is_minted": False,
            "verification_status": None,
        }
        result = p.generate("", ctx)
        assert "satellite" in result.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Class 3 — Groq provider: fallback and response behaviour
# ══════════════════════════════════════════════════════════════════════════════

class TestGroqProvider:

    def setup_method(self):
        reset_ai_provider()

    def teardown_method(self):
        reset_ai_provider()

    def test_groq_falls_back_to_rules_when_api_key_missing(self):
        """No GROQ_API_KEY → silent fallback to rule engine."""
        p = GroqAIProvider()
        ctx = {
            "_operation": "mrv_summary",
            "farm_name": "Fallback Farm",
            "has_carbon_report": False,
            "report_status": "",
            "estimated_credits": 0,
            "sensor_reading_count": 0,
            "has_soc_estimate": False,
            "has_satellite_obs": False,
        }
        with patch("app.config.settings.GROQ_API_KEY", ""):
            result = p.generate("", ctx)
        assert isinstance(result, str)
        assert len(result) > 0
        # Rules fallback produces deterministic output
        assert "No carbon report" in result

    def test_groq_falls_back_to_rules_on_connection_error(self):
        """Network failure → fallback, no exception raised."""
        p = GroqAIProvider()
        ctx = {
            "_operation": "mrv_summary",
            "farm_name": "Network Error Farm",
            "has_carbon_report": False,
            "report_status": "",
            "estimated_credits": 0,
            "sensor_reading_count": 0,
            "has_soc_estimate": False,
            "has_satellite_obs": False,
        }
        with patch("app.config.settings.GROQ_API_KEY", "gsk_test_key"), \
             patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
            result = p.generate("", ctx)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_groq_returns_llm_response_when_api_succeeds(self):
        """Mock a successful Groq API response."""
        p = GroqAIProvider()
        mock_body = b'{"choices": [{"message": {"content": "Groq says: farm looks good."}}]}'
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("app.config.settings.GROQ_API_KEY", "gsk_test_key"), \
             patch("urllib.request.urlopen", return_value=mock_resp):
            result = p.generate("Summarise.", {"_operation": "mrv_summary"})
        assert result == "Groq says: farm looks good."

    def test_groq_api_key_not_logged(self):
        """Ensure the API key never appears in the provider repr or logs."""
        p = GroqAIProvider()
        assert "gsk_" not in repr(p)
        assert "api_key" not in repr(p).lower()

    def test_groq_fallback_result_is_non_empty(self):
        """Fallback to rules always produces a non-empty string."""
        p = GroqAIProvider()
        with patch("app.config.settings.GROQ_API_KEY", ""):
            result = p.generate("", {
                "_operation": "fpo_action_summary",
                "pending_farm_approvals": 0,
                "mintable_report_count": 0,
                "initiated_payout_count": 0,
                "active_listing_count": 0,
                "evidence_gap_count": 0,
            })
        assert len(result) > 0


# ══════════════════════════════════════════════════════════════════════════════
# Class 4 — HTTP endpoint access control
# ══════════════════════════════════════════════════════════════════════════════

class TestAIEndpointAccessControl:
    """Tests that role guards work correctly — no DB data needed for 401/403."""

    def test_mrv_summary_requires_auth(self, client):
        r = client.post("/ai/mrv-summary/1")
        assert r.status_code == 401

    def test_verification_assist_requires_auth(self, client):
        r = client.post("/ai/verification-assist/1")
        assert r.status_code == 401

    def test_fpo_action_summary_requires_auth(self, client):
        r = client.post("/ai/fpo/action-summary")
        assert r.status_code == 401

    def test_farmer_help_requires_auth(self, client):
        r = client.post("/ai/farmer/help")
        assert r.status_code == 401

    def test_verification_assist_blocked_for_farmer(self, client, farmer_user):
        headers = _auth(client, farmer_user.email, "password123")
        r = client.post("/ai/verification-assist/1", headers=headers)
        assert r.status_code == 403

    def test_verification_assist_blocked_for_fpo(self, client, fpo_user):
        headers = _auth(client, fpo_user.email, "password123")
        r = client.post("/ai/verification-assist/1", headers=headers)
        assert r.status_code == 403

    def test_fpo_action_summary_blocked_for_farmer(self, client, farmer_user):
        headers = _auth(client, farmer_user.email, "password123")
        r = client.post("/ai/fpo/action-summary", headers=headers)
        assert r.status_code == 403

    def test_farmer_help_blocked_for_fpo(self, client, fpo_user):
        headers = _auth(client, fpo_user.email, "password123")
        r = client.post(
            "/ai/farmer/help",
            json={"topic": "general"},
            headers=headers,
        )
        assert r.status_code == 403

    def test_mrv_summary_404_unknown_farm(self, client, farmer_user):
        headers = _auth(client, farmer_user.email, "password123")
        r = client.post("/ai/mrv-summary/99999", headers=headers)
        assert r.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Class 5 — AI does NOT mutate data
# ══════════════════════════════════════════════════════════════════════════════

class TestAIDoesNotMutateData:
    """Verify report values and approval status are unchanged after AI calls."""

    def test_mrv_summary_does_not_change_report_status(
        self, client, farmer_user, farm, carbon_report_draft, db
    ):
        from app.models.carbon_report import CarbonReport
        before = db.query(CarbonReport).filter(CarbonReport.id == carbon_report_draft.id).first()
        status_before  = before.status
        credits_before = before.estimated_credits

        headers = _auth(client, farmer_user.email, "password123")
        r = client.post(f"/ai/mrv-summary/{farm.id}", headers=headers)
        assert r.status_code != 500

        db.expire_all()
        after = db.query(CarbonReport).filter(CarbonReport.id == carbon_report_draft.id).first()
        assert after.status            == status_before
        assert after.estimated_credits == credits_before

    def test_farmer_help_does_not_change_farm(
        self, client, farmer_user, farm, db
    ):
        from app.models.farm import Farm
        before          = db.query(Farm).filter(Farm.id == farm.id).first()
        approved_before = before.is_approved

        headers = _auth(client, farmer_user.email, "password123")
        client.post(
            "/ai/farmer/help",
            json={"topic": "general", "farm_id": farm.id},
            headers=headers,
        )

        db.expire_all()
        after = db.query(Farm).filter(Farm.id == farm.id).first()
        assert after.is_approved == approved_before


# ══════════════════════════════════════════════════════════════════════════════
# Class 6 — Response schema compliance
# ══════════════════════════════════════════════════════════════════════════════

class TestResponseSchemaCompliance:

    def test_farmer_help_general_has_disclaimer(self, client, farmer_user):
        headers = _auth(client, farmer_user.email, "password123")
        r = client.post(
            "/ai/farmer/help",
            json={"topic": "general"},
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["disclaimer"] == DISCLAIMER
        assert body["ai_mode"] in ("rules", "groq")
        assert "explanation" in body
        assert isinstance(body["insights"], list)

    def test_farmer_help_explain_credits_topic(self, client, farmer_user):
        headers = _auth(client, farmer_user.email, "password123")
        r = client.post(
            "/ai/farmer/help",
            json={"topic": "explain_credits"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["topic"] == "explain_credits"

    def test_farmer_help_invalid_topic_422(self, client, farmer_user):
        headers = _auth(client, farmer_user.email, "password123")
        r = client.post(
            "/ai/farmer/help",
            json={"topic": "invalid_topic_xyz"},
            headers=headers,
        )
        assert r.status_code == 422

    def test_fpo_action_summary_schema(self, client, fpo_user, fpo_profile):
        headers = _auth(client, fpo_user.email, "password123")
        r = client.post("/ai/fpo/action-summary", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["disclaimer"] == DISCLAIMER
        assert body["ai_mode"] in ("rules", "groq")
        assert isinstance(body["action_items"], list)
        assert "summary" in body

    def test_fpo_action_summary_action_item_structure(self, client, fpo_user, fpo_profile):
        headers = _auth(client, fpo_user.email, "password123")
        r = client.post("/ai/fpo/action-summary", headers=headers)
        body = r.json()
        for item in body["action_items"]:
            assert "category" in item
            assert "count" in item
            assert "message" in item

    def test_mrv_summary_own_farm(self, client, farmer_user, farm):
        headers = _auth(client, farmer_user.email, "password123")
        r = client.post(f"/ai/mrv-summary/{farm.id}", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["farm_id"] == farm.id
        assert body["disclaimer"] == DISCLAIMER
        assert body["confidence_level"] in ("HIGH", "MEDIUM", "LOW")
        assert 0 <= body["data_completeness_pct"] <= 100
        assert isinstance(body["insights"], list)
        # New Phase-18 fields
        assert "has_carbon_report" in body
        assert isinstance(body["has_carbon_report"], bool)
        assert "next_best_action" in body
        assert isinstance(body["next_best_action"], str)
        assert "confidence_label" in body
        assert body["confidence_label"] in ("High", "Medium", "Low")
        assert "data_completeness" in body
        assert 0 <= body["data_completeness"] <= 100

    def test_mrv_summary_no_carbon_report_path(self, client, farmer_user, farm):
        """Farm with no carbon report: has_carbon_report=false, insights contain action."""
        headers = _auth(client, farmer_user.email, "password123")
        r = client.post(f"/ai/mrv-summary/{farm.id}", headers=headers)
        assert r.status_code == 200
        body = r.json()
        # Farm fixture has no carbon report
        assert body["has_carbon_report"] is False
        assert body["latest_report_id"] is None
        assert body["report_status"] is None
        # There should be at least one action-type insight
        types = [i["type"] for i in body["insights"]]
        assert "action" in types
        # next_best_action should mention generating a report
        assert "report" in body["next_best_action"].lower()

    def test_mrv_summary_with_carbon_report_shows_id_and_status(
        self, client, farmer_user, farm, carbon_report_draft
    ):
        """Farm with a carbon report: has_carbon_report=true, latest_report_id set."""
        headers = _auth(client, farmer_user.email, "password123")
        r = client.post(f"/ai/mrv-summary/{farm.id}", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["has_carbon_report"] is True
        assert body["latest_report_id"] == carbon_report_draft.id
        assert body["report_status"] is not None
        assert isinstance(body["summary"], str)
        assert len(body["summary"]) > 0

    def test_mrv_summary_farmer_cannot_access_other_farm(
        self, client, farmer_user, db
    ):
        from app.models.user import User, UserRole
        from app.models.farm import Farm
        from app.security import hash_password

        other_farmer = User(
            email="otherfarmer@test.com",
            password_hash=hash_password("password123"),
            role=UserRole.FARMER,
            name="Other Farmer",
            is_active=True,
        )
        db.add(other_farmer)
        db.commit()
        db.refresh(other_farmer)

        other_farm = Farm(
            farm_name="Other Farm",
            land_area_acres=12.0,
            latitude=20.0,
            longitude=75.0,
            village="Testpur",
            district="Testdistrict",
            state="TestState",
            soil_type="Loamy",
            water_source="Canal",
            farmer_id=other_farmer.id,
        )
        db.add(other_farm)
        db.commit()
        db.refresh(other_farm)

        headers = _auth(client, farmer_user.email, "password123")
        r = client.post(f"/ai/mrv-summary/{other_farm.id}", headers=headers)
        assert r.status_code == 403

    def test_verification_assist_verifier_404_unknown(
        self, client, verifier_user
    ):
        headers = _auth(client, verifier_user.email, "password123")
        r = client.post("/ai/verification-assist/99999", headers=headers)
        assert r.status_code == 404

    def test_verification_assist_recommendation_is_not_auto_approval(
        self, client, verifier_user, carbon_report_submitted, db
    ):
        """AI recommendation must include disclaimer that human approves.
        Uses carbon_report_submitted fixture which creates a VR automatically.
        """
        from app.models.carbon_report import CarbonReport, ReportStatus
        from app.models.verification import VerificationRequest, VerificationStatus

        vr = (
            db.query(VerificationRequest)
            .filter(VerificationRequest.carbon_report_id == carbon_report_submitted.id)
            .first()
        )
        assert vr is not None, "Fixture should have created a VerificationRequest"

        status_before    = carbon_report_submitted.status
        vr_status_before = vr.status

        headers = _auth(client, verifier_user.email, "password123")
        r = client.post(f"/ai/verification-assist/{vr.id}", headers=headers)
        assert r.status_code == 200
        body = r.json()

        # Recommendation present but note must say human decides
        assert body["recommendation"] in ("APPROVE", "REVIEW", "REJECT")
        assert "human" in body["recommendation_note"].lower()
        assert body["disclaimer"] == DISCLAIMER
        assert body["ai_mode"] in ("rules", "groq")

        # CRITICAL: report and VR status must not have changed
        db.expire_all()
        updated_report = (
            db.query(CarbonReport)
            .filter(CarbonReport.id == carbon_report_submitted.id)
            .first()
        )
        assert updated_report.status == status_before

        updated_vr = (
            db.query(VerificationRequest)
            .filter(VerificationRequest.id == vr.id)
            .first()
        )
        assert updated_vr.status == vr_status_before
