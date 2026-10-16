"""
Route-level validation tests for app/routes/pulse.py.
Uses FastAPI's TestClient against the Pydantic schema only (no DB needed
for these — invalid requests are rejected by validation before any query
runs). Run with: pytest tests/test_pulse_routes.py -v
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.pulse import CheckInRequest, MAX_PROBLEMS_PER_CHECKIN
from pydantic import ValidationError


# ── CheckInRequest validation (pure schema, no DB) ────────────────────────────

class TestCheckInRequestValidation:
    def test_single_valid_problem_accepted(self):
        req = CheckInRequest(problems=["anxiety"])
        assert req.problems == ["anxiety"]

    def test_two_valid_problems_accepted(self):
        req = CheckInRequest(problems=["anxiety", "mood"])
        assert req.problems == ["anxiety", "mood"]

    def test_empty_list_rejected(self):
        with pytest.raises(ValidationError):
            CheckInRequest(problems=[])

    def test_three_problems_rejected(self):
        with pytest.raises(ValidationError):
            CheckInRequest(problems=["anxiety", "mood", "grief"])

    def test_exceeds_max_by_one_rejected(self):
        with pytest.raises(ValidationError):
            CheckInRequest(problems=["anxiety"] * (MAX_PROBLEMS_PER_CHECKIN + 1))

    def test_duplicate_problem_ids_rejected(self):
        with pytest.raises(ValidationError):
            CheckInRequest(problems=["anxiety", "anxiety"])

    def test_unknown_problem_id_rejected(self):
        with pytest.raises(ValidationError):
            CheckInRequest(problems=["not_a_real_category"])

    def test_mixed_known_and_unknown_rejected(self):
        with pytest.raises(ValidationError):
            CheckInRequest(problems=["anxiety", "definitely_fake"])

    def test_sql_injection_like_string_rejected_as_unknown_id(self):
        with pytest.raises(ValidationError):
            CheckInRequest(problems=["anxiety'; DROP TABLE pulse_checkins; --"])

    def test_country_code_normalised_uppercase(self):
        req = CheckInRequest(problems=["anxiety"], country_code="in")
        assert req.country_code == "IN"

    def test_country_code_not_in_iso_list_becomes_none(self):
        # "INDIA" is not itself a valid 2-letter code — truncating it to
        # "IN" and accepting that would let arbitrary/malformed input be
        # silently reinterpreted as a real country. Must be dropped, not
        # coerced.
        req = CheckInRequest(problems=["anxiety"], country_code="INDIA")
        assert req.country_code is None

    def test_valid_iso_code_accepted(self):
        for code in ["IN", "US", "GB", "DE", "BR", "AU", "JP"]:
            req = CheckInRequest(problems=["anxiety"], country_code=code)
            assert req.country_code == code

    def test_invalid_two_letter_code_rejected_to_none(self):
        # "ZZ" and "XX" are not real ISO 3166-1 alpha-2 codes.
        req = CheckInRequest(problems=["anxiety"], country_code="ZZ")
        assert req.country_code is None

    def test_country_code_single_char_rejected_to_none(self):
        req = CheckInRequest(problems=["anxiety"], country_code="I")
        assert req.country_code is None

    def test_country_code_absent_defaults_none(self):
        req = CheckInRequest(problems=["anxiety"])
        assert req.country_code is None

    def test_country_code_injection_attempt_rejected_to_none(self):
        req = CheckInRequest(problems=["anxiety"], country_code="IN'; DROP TABLE pulse_checkins;--")
        assert req.country_code is None

    def test_country_name_truncated_to_80_chars(self):
        long_name = "A" * 200
        req = CheckInRequest(problems=["anxiety"], country_name=long_name)
        assert len(req.country_name) == 80

    def test_country_name_whitespace_only_becomes_none(self):
        req = CheckInRequest(problems=["anxiety"], country_name="   ")
        assert req.country_name is None

    def test_non_string_problems_rejected(self):
        with pytest.raises(ValidationError):
            CheckInRequest(problems=[123, 456])

    def test_problems_must_be_a_list_not_string(self):
        with pytest.raises(ValidationError):
            CheckInRequest(problems="anxiety")
