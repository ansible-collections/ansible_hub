import importlib.util
import sys
from unittest.mock import MagicMock

import pytest

# ah_collection.py imports ansible-core modules (AnsibleModule, etc.) at the top
# level. ansible-core is not installed in the unit test environment, so we mock
# those modules in sys.modules before loading the file. This lets us import and
# test pure helper functions like extract_version_from_path without needing a
# full Ansible installation.
for mock_module in [
    "ansible",
    "ansible.module_utils",
    "ansible.module_utils._text",
    "ansible.module_utils.basic",
    "plugins",
    "plugins.modules",
    "plugins.module_utils",
    "plugins.module_utils.ah_module",
]:
    sys.modules.setdefault(mock_module, MagicMock())

spec = importlib.util.spec_from_file_location(
    "ah_collection", "plugins/modules/ah_collection.py", submodule_search_locations=[]
)
mod = importlib.util.module_from_spec(spec)
mod.__package__ = "plugins.modules"
spec.loader.exec_module(mod)

extract_version_from_path = mod.extract_version_from_path


@pytest.mark.parametrize(
    "path, expected",
    [
        ("my_ns-my_collection-1.0.0.tar.gz", "1.0.0"),
        ("/tmp/my_ns-my_collection-1.0.0.tar.gz", "1.0.0"),
        ("/home/my-user/collections/my_ns-my_collection-1.0.0.tar.gz", "1.0.0"),
        ("/opt/ansible-automation/build-output/my_ns-my_collection-1.0.0.tar.gz", "1.0.0"),
        ("./my_ns-my_collection-1.0.0.tar.gz", "1.0.0"),
        ("/tmp/my_ns-my_collection-2.1.0-beta.1.tar.gz", "2.1.0-beta.1"),
        ("/path/to/sample-sample-1.0.0.tar.gz", "1.0.0"),
        ("/no-hyphens/path/ns-name-0.0.1.tar.gz", "0.0.1"),
    ],
    ids=[
        "bare_filename",
        "simple_absolute_path",
        "directory_with_hyphens",
        "multiple_directory_hyphens",
        "relative_path",
        "prerelease_version",
        "sample_collection",
        "single_directory_hyphen",
    ],
)
def test_version_extraction(path, expected):
    assert extract_version_from_path(path) == expected
