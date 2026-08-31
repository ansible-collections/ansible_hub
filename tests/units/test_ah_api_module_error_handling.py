import importlib.util
import pathlib
from unittest.mock import MagicMock

import pytest

# ansible-core stubbing (AnsibleModule stand-in, etc.) lives in conftest.py,
# shared with test_ah_pulp_object_update.py, and runs before this file is
# collected.

_module_path = pathlib.Path(__file__).resolve().parents[2] / "plugins" / "module_utils" / "ah_api_module.py"
spec = importlib.util.spec_from_file_location("ah_api_module", str(_module_path))
mod = importlib.util.module_from_spec(spec)
mod.__package__ = "plugins.module_utils"
spec.loader.exec_module(mod)

AHAPIModule = mod.AHAPIModule
AHAPIModuleError = mod.AHAPIModuleError


def _make_api(raw_response):
    """Build an AHAPIModule instance without running its heavy __init__.

    make_request() only needs make_request_raw_reponse() to return a response;
    it doesn't touch anything else __init__ would normally set up, so a bare
    instance with that one method stubbed is enough to exercise it in
    isolation.
    """
    api = object.__new__(AHAPIModule)
    api.make_request_raw_reponse = MagicMock(return_value=raw_response)
    return api


def test_make_request_surfaces_unrecognized_error_shape():
    """An API error body in a shape make_request() doesn't special-case should
    still surface its real content, not a generic "response has no read"
    message that hides what the server actually said.
    """
    api = _make_api({"status_code": 400, "json": {"content_guard": ["Invalid hyperlink - Incorrect URL match."]}})

    with pytest.raises(AHAPIModuleError) as exc_info:
        api.make_request("PATCH", "https://hub.example.com/pulp/api/v3/thing/1/", data={"description": "x"})

    assert "content_guard" in str(exc_info.value)
    assert "Invalid hyperlink" in str(exc_info.value)


def test_make_request_handles_text_only_error_body():
    """A non-JSON error body (no "json" key, only "text") must not crash the
    fallback logic that looks for "non_field_errors" or "errors" keys.
    """
    api = _make_api({"status_code": 400, "text": "plain text error"})

    with pytest.raises(AHAPIModuleError) as exc_info:
        api.make_request("PATCH", "https://hub.example.com/pulp/api/v3/thing/1/", data={"description": "x"})

    assert "plain text error" in str(exc_info.value)


def test_make_request_reports_the_real_status_code_for_non_field_errors():
    """The non_field_errors branch hardcoded "HTTP 400" regardless of the
    response's actual status code. A 409 (or any non-400 error the server
    returns through this same code path) should be reported as 409, not a
    fabricated 400.
    """
    api = _make_api({"status_code": 409, "json": {"non_field_errors": ["conflict"]}})

    with pytest.raises(AHAPIModuleError) as exc_info:
        api.make_request("PATCH", "https://hub.example.com/pulp/api/v3/thing/1/", data={"description": "x"})

    assert "409" in str(exc_info.value)
    assert "400" not in str(exc_info.value)


def test_make_request_reports_unknown_status_when_missing():
    """response.get("status_code") with no default renders as the literal
    string "None" when the key is absent, which reads like a bug in the
    error message itself. "unknown" is clearer.
    """
    api = _make_api({"json": {"weird_shape": True}})

    with pytest.raises(AHAPIModuleError) as exc_info:
        api.make_request("PATCH", "https://hub.example.com/pulp/api/v3/thing/1/", data={"description": "x"})

    assert "unknown" in str(exc_info.value)
    assert "None" not in str(exc_info.value)


def test_make_request_truncates_a_large_unrecognized_error_body():
    """The unrecognized-shape fallback interpolates the raw server response
    verbatim. Bound the size so an unusually large body doesn't flood the
    job output.
    """
    huge_value = "x" * 5000
    api = _make_api({"status_code": 400, "json": {"some_field": huge_value}})

    with pytest.raises(AHAPIModuleError) as exc_info:
        api.make_request("PATCH", "https://hub.example.com/pulp/api/v3/thing/1/", data={"description": "x"})

    assert len(str(exc_info.value)) < 1000
