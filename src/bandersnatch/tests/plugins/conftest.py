from collections import defaultdict
from pathlib import Path

import pytest

import bandersnatch.storage


@pytest.fixture(autouse=True)
def plugin_test_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """
    Automatically isolates each test into its own temp dir and
    ensures the storage plugin registry is clean.
    """
    monkeypatch.setattr(
        bandersnatch.storage,
        "loaded_storage_plugins",
        defaultdict(list),
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path
