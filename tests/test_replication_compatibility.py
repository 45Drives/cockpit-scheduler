import ast
import importlib
import pkgutil
from pathlib import Path

import replication


SCRIPTS_DIR = Path(replication.__file__).resolve().parent.parent
PACKAGE_DIR = Path(replication.__file__).resolve().parent


def test_all_replication_sources_parse_with_python_36_grammar():
    files = [SCRIPTS_DIR / "replication-script.py"] + sorted(PACKAGE_DIR.rglob("*.py"))
    assert files
    for path in files:
        ast.parse(path.read_text(), filename=str(path), feature_version=(3, 6))


def test_every_replication_module_imports_without_optional_runtime_tools():
    module_names = [item.name for item in pkgutil.walk_packages(replication.__path__, replication.__name__ + ".")]
    assert module_names
    for module_name in module_names:
        importlib.import_module(module_name)


def test_compatibility_entrypoint_stays_small_and_delegates_to_package():
    entrypoint = SCRIPTS_DIR / "replication-script.py"
    source = entrypoint.read_text()
    assert source.startswith("#!/usr/bin/env python3")
    assert "from replication.main import main" in source
    assert len(source.splitlines()) <= 20

