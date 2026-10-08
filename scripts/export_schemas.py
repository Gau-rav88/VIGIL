#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Add libs to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "libs" / "vigil_common" / "src"))

from vigil_common.models.market import TradeTick, L2Snapshot, L3OrderEvent
from vigil_common.models.social import SocialMessage, SocialSignal
from vigil_common.models.anomaly import AnomalyEvent
from vigil_common.models.dossier import ForensicDossier

SCHEMA_MAP = {
    "trade_tick.schema.json": TradeTick,
    "l2_snapshot.schema.json": L2Snapshot,
    "l3_order_event.schema.json": L3OrderEvent,
    "social_message.schema.json": SocialMessage,
    "social_signal.schema.json": SocialSignal,
    "anomaly_event.schema.json": AnomalyEvent,
    "forensic_dossier.schema.json": ForensicDossier,
}


def export_schemas(check_only: bool = False) -> int:
    target_dir = ROOT / "libs" / "vigil_common" / "schemas"
    target_dir.mkdir(parents=True, exist_ok=True)
    has_diff = False

    for filename, model_cls in SCHEMA_MAP.items():
        schema_data = model_cls.model_json_schema()
        schema_data["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        out_file = target_dir / filename
        formatted = json.dumps(schema_data, indent=2, sort_keys=True) + "\n"

        if check_only:
            if not out_file.exists():
                print(f"Missing schema: {filename}")
                has_diff = True
            else:
                existing = out_file.read_text(encoding="utf-8")
                if existing != formatted:
                    print(f"Schema mismatch: {filename}")
                    has_diff = True
        else:
            out_file.write_text(formatted, encoding="utf-8")
            print(f"Exported {filename} -> {out_file}")

    return 1 if (check_only and has_diff) else 0


if __name__ == "__main__":
    check_mode = "--check" in sys.argv
    sys.exit(export_schemas(check_only=check_mode))
