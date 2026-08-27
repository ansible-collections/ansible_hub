import importlib.util
import pathlib
import sys
from unittest.mock import MagicMock

# ah_pulp_object.py imports ah_api_module.py, which imports ansible-core
# modules at the top level. ansible-core is not installed in the unit test
# environment, so mock those modules before loading either file.
for mock_module in [
    "ansible",
    "ansible.module_utils",
    "ansible.module_utils._text",
    "ansible.module_utils.basic",
    "ansible.module_utils.compat",
    "ansible.module_utils.compat.version",
    "ansible.module_utils.urls",
]:
    sys.modules.setdefault(mock_module, MagicMock())

_module_utils_dir = pathlib.Path(__file__).resolve().parents[2] / "plugins" / "module_utils"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, str(_module_utils_dir / filename))
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = "plugins.module_utils"
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_load("plugins.module_utils.ah_api_module", "ah_api_module.py")
ah_pulp_object = _load("plugins.module_utils.ah_pulp_object", "ah_pulp_object.py")

AHPulpObject = ah_pulp_object.AHPulpObject


def _make_object(data):
    mock_api = MagicMock()
    mock_api.check_mode = False
    mock_api.make_request.return_value = {"status_code": 200, "json": {}}
    obj = AHPulpObject(mock_api, data=data)
    return obj, mock_api


def test_update_sends_patch_not_put():
    """update() should send a partial update (PATCH), not a full replace (PUT).

    The payload passed to update() is always a subset of the object's fields
    (e.g. just {"description": ...}), never the full representation. Sending
    that partial body via PUT makes the server re-validate fields the caller
    never touched (e.g. content_guard on a container distribution), which is
    what broke ah_ee_repository updates (AAP-90033).
    """
    obj, mock_api = _make_object({"name": "existing", "pulp_href": "/pulp/api/v3/thing/1/"})

    obj.update({"description": "new description"}, auto_exit=False)

    method_used = mock_api.make_request.call_args[0][0]
    assert method_used == "PATCH"
