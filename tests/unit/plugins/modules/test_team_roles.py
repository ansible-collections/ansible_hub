import importlib.util
import pathlib
import sys
from unittest.mock import MagicMock

from packaging.version import Version


for mock_module in [
    "ansible",
    "ansible.module_utils",
    "plugins",
    "plugins.modules",
    "plugins.module_utils",
    "plugins.module_utils.ah_api_module",
]:
    sys.modules.setdefault(mock_module, MagicMock())

_module_path = pathlib.Path(__file__).resolve().parents[4] / "plugins" / "modules" / "team_roles.py"
spec = importlib.util.spec_from_file_location("team_roles", str(_module_path), submodule_search_locations=[])
mod = importlib.util.module_from_spec(spec)
mod.__package__ = "plugins.modules"
spec.loader.exec_module(mod)
# ansible-core is mocked in unit tests; use a real comparator for version gates.
mod.LooseVersion = Version


def test_get_team_id_scopes_lookup_to_organization():
    module = MagicMock()
    module.make_request.return_value = {
        "status_code": 200,
        "json": {
            "results": [
                {"id": 1, "name": "team1", "organization": {"id": 10, "name": "org1"}},
                {"id": 2, "name": "team1", "organization": {"id": 20, "name": "org2"}},
            ]
        },
    }

    assert mod.get_team_id(module, "team1", "org2") == 2
    module.build_ui_v2_url.assert_called_once_with(
        "teams", query_params={"name": "team1", "organization": "org2"}
    )


def test_get_team_id_returns_none_for_wrong_organization():
    module = MagicMock()
    module.make_request.return_value = {
        "status_code": 200,
        "json": {"results": [{"id": 1, "name": "team1", "organization": {"id": 10, "name": "org1"}}]},
    }

    assert mod.get_team_id(module, "team1", "org2") is None


def test_get_team_id_rejects_ambiguous_team_without_organization():
    module = MagicMock()
    module.make_request.return_value = {
        "status_code": 200,
        "json": {
            "results": [
                {"id": 1, "name": "team1", "organization": {"id": 10, "name": "org1"}},
                {"id": 2, "name": "team1", "organization": {"id": 20, "name": "org2"}},
            ]
        },
    }

    assert mod.get_team_id(module, "team1") is None
    module.fail_json.assert_called_once_with(
        msg=(
            "Multiple teams named `team1` were found. Specify the "
            "`organization` parameter to select the intended team."
        )
    )


def test_get_team_id_rejects_ambiguous_team_when_organization_is_omitted_from_results():
    module = MagicMock()
    module.make_request.return_value = {
        "status_code": 200,
        "json": {
            "results": [
                {"id": 1, "name": "team1"},
                {"id": 2, "name": "team1"},
            ]
        },
    }

    assert mod.get_team_id(module, "team1", "org1") is None
    module.fail_json.assert_called_once_with(
        msg="Multiple teams named `team1` matched organization `org1`. The API response was ambiguous."
    )


def test_get_team_id_rejects_unverified_single_team_for_organization():
    module = MagicMock()
    module.make_request.return_value = {
        "status_code": 200,
        "json": {"results": [{"id": 1, "name": "team1"}]},
    }

    assert mod.get_team_id(module, "team1", "org1") is None
    module.fail_json.assert_called_once_with(
        msg=(
            "Team `team1` matched organization `org1`, but the API response "
            "did not include organization metadata, so the team could not be verified."
        )
    )


def test_validate_server_version_rejects_before_hub_4_10():
    module = MagicMock()

    mod.validate_server_version(module, "4.9.14", "org1")

    module.fail_json.assert_called_once_with(
        msg="This module requires private automation hub version 4.10 or later. Your version is 4.9.14"
    )


def test_validate_server_version_requires_organization_on_hub_4_10():
    module = MagicMock()

    mod.validate_server_version(module, "4.10.14", None)

    module.fail_json.assert_called_once_with(
        msg=(
            "Hub 4.10 team_roles requires the organization parameter for "
            "Gateway-managed teams. Use group_roles for standalone Hub 4.10."
        )
    )


def test_validate_server_version_accepts_hub_4_10_with_organization():
    module = MagicMock()

    mod.validate_server_version(module, "4.10.14", "org1")

    module.fail_json.assert_not_called()


def test_validate_server_version_accepts_hub_4_11_without_organization():
    module = MagicMock()

    mod.validate_server_version(module, "4.11.0", None)

    module.fail_json.assert_not_called()
