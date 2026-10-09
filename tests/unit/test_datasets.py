from pathlib import Path

import pytest
from vigil_common.datasets import DatasetRegistry, open_dataset

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "datasets"
MANIFEST_PATH = FIXTURES_DIR / "sample_manifest.yaml"


def test_dataset_registry_loading():
    registry = DatasetRegistry(manifest_path=MANIFEST_PATH)
    assert "test_messages" in registry.list_datasets()
    meta = registry.get("test_messages")
    assert meta is not None
    assert meta.repo_path == "sample_messages.jsonl"
    assert registry.is_synthetic("test_messages") is True


def test_open_dataset_iterator():
    items = list(open_dataset("test_messages", data_dir=FIXTURES_DIR, manifest_path=MANIFEST_PATH))
    assert len(items) == 2
    assert items[0]["event_id"] == "test_01"
    assert items[1]["event_id"] == "test_02"


def test_open_dataset_missing_key():
    with pytest.raises(KeyError):
        list(open_dataset("non_existent_dataset", data_dir=FIXTURES_DIR, manifest_path=MANIFEST_PATH))
