import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
DEFAULT_MANIFEST = ROOT_DIR / "datasets" / "manifest.yaml"
DEFAULT_DATA_DIR = ROOT_DIR / "datasets" / "data"


class DatasetMeta:
    def __init__(self, name: str, repo_path: str, sha256: str, license: str, is_synthetic: bool, target_schema: str, description: str = ""):
        self.name = name
        self.repo_path = repo_path
        self.sha256 = sha256
        self.license = license
        self.is_synthetic = is_synthetic
        self.target_schema = target_schema
        self.description = description

    def __repr__(self) -> str:
        return f"<DatasetMeta name={self.name} path={self.repo_path} synthetic={self.is_synthetic}>"


class DatasetRegistry:
    def __init__(self, manifest_path: Optional[Path] = None):
        self.manifest_path = manifest_path or DEFAULT_MANIFEST
        self._datasets: Dict[str, DatasetMeta] = {}
        self._load()

    def _load(self) -> None:
        if not self.manifest_path.exists():
            return
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        for name, meta in data.get("datasets", {}).items():
            self._datasets[name] = DatasetMeta(
                name=name,
                repo_path=meta.get("repo_path", ""),
                sha256=meta.get("sha256", ""),
                license=meta.get("license", "Unknown"),
                is_synthetic=bool(meta.get("is_synthetic", True)),
                target_schema=meta.get("target_schema", ""),
                description=meta.get("description", ""),
            )

    def get(self, name: str) -> Optional[DatasetMeta]:
        return self._datasets.get(name)

    def list_datasets(self) -> List[str]:
        return list(self._datasets.keys())

    def is_synthetic(self, name: str) -> bool:
        meta = self.get(name)
        return meta.is_synthetic if meta else True


def open_dataset(name: str, data_dir: Optional[Path] = None, manifest_path: Optional[Path] = None) -> Iterator[Dict[str, Any]]:
    registry = DatasetRegistry(manifest_path=manifest_path)
    meta = registry.get(name)
    base_dir = data_dir or DEFAULT_DATA_DIR

    if not meta:
        raise KeyError(f"Dataset '{name}' is not registered in manifest.")

    file_path = base_dir / meta.repo_path
    if not file_path.exists():
        raise FileNotFoundError(f"Dataset file not found at {file_path}. Run `make datasets` first.")

    suffix = file_path.suffix.lower()
    name_lower = file_path.name.lower()

    if name_lower.endswith(".zst"):
        try:
            import zstandard as zstd
            dctx = zstd.ZstdDecompressor()
            with open(file_path, "rb") as fh:
                with dctx.stream_reader(fh) as reader:
                    text_data = reader.read().decode("utf-8")
                    for line in text_data.splitlines():
                        line = line.strip()
                        if line:
                            yield json.loads(line)
        except ImportError:
            raise RuntimeError("zstandard package is required to open .zst datasets")

    elif suffix in [".jsonl", ".ndjson"]:
        with open(file_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)

    elif suffix == ".csv":
        with open(file_path, "r", encoding="utf-8") as fh:
            csv_reader = csv.DictReader(fh)
            for row in csv_reader:
                yield dict(row)

    elif suffix == ".json":
        with open(file_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                for item in data:
                    yield item
            else:
                yield data
    else:
        raise ValueError(f"Unsupported dataset format for file: {file_path}")
