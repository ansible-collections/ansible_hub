import importlib.util
import pathlib
import sys
import types
from unittest.mock import MagicMock

import pytest

# AHAPIModule subclasses ansible.module_utils.basic.AnsibleModule.
# ansible-core is not installed in the unit test environment, and a MagicMock
# cannot stand in as a base class (subclassing a MagicMock instance silently
# produces another MagicMock instead of a real class), so give it a real,
# empty stand-in class instead of a MagicMock.
_fake_basic = types.ModuleType("ansible.module_utils.basic")


class _FakeAnsibleModule:
    pass


_fake_basic.AnsibleModule = _FakeAnsibleModule
_fake_basic.env_fallback = lambda *args, **kwargs: None
sys.modules["ansible.module_utils.basic"] = _fake_basic

for mock_module in [
    "ansible",
    "ansible.module_utils",
    "ansible.module_utils._text",
    "ansible.module_utils.compat",
    "ansible.module_utils.compat.version",
    "ansible.module_utils.urls",
]:
    sys.modules.setdefault(mock_module, MagicMock())

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
