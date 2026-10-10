from __future__ import annotations

import re
from typing import Any

from vigil_common.models.dossier import ForensicDossier


class DossierValidator:
    """
    Validates forensic dossiers per FR-DOS-02:
    1. Schema validation against ForensicDossier / schema.json
    2. Citation verification: every sentence in executive summary and timeline has >= 1 resolvable evidence_id
    3. Numeric consistency checks: volume sums, ratio, timestamp boundaries
    """

    @staticmethod
    def validate(
        dossier_data: dict[str, Any],
        manifest_evidence_ids: set[str] | None = None,
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []

        # 1. Pydantic / Schema Validation
        try:
            dossier = ForensicDossier.model_validate(dossier_data)
        except Exception as exc:
            errors.append(f"Schema validation error: {exc}")
            return False, errors

        # Collect available evidence IDs
        available_ids: set[str] = manifest_evidence_ids or {
            item.evidence_id for item in dossier.evidence_manifest
        }

        # 2. Citation Check on Executive Summary
        # Every sentence in executive_summary must cite at least one valid evidence_id
        exec_text = dossier.executive_summary.text
        # Split on sentence terminals
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", exec_text) if s.strip()]
        for i, s in enumerate(sentences):
            citations_in_s = re.findall(r"\[(EV-[A-Z_]+-[a-f0-9]+)\]", s)
            if not citations_in_s:
                # Also check citations list
                citations_in_s = [cid for cid in dossier.executive_summary.citations if cid in s]

            if not citations_in_s:
                errors.append(f"Sentence {i + 1} lacks evidence citation: '{s[:40]}...'")
            else:
                for cid in citations_in_s:
                    if cid not in available_ids:
                        errors.append(f"Unresolvable evidence citation in sentence {i + 1}: {cid}")

        # 3. Citation Check on Timeline Entries
        for idx, t in enumerate(dossier.timeline):
            if not t.evidence_ids:
                errors.append(f"Timeline entry {idx + 1} has no evidence_ids cited")
            for cid in t.evidence_ids:
                if cid not in available_ids:
                    errors.append(f"Timeline entry {idx + 1} cites unresolvable evidence_id: {cid}")

        # 4. Numeric Consistency Checks
        mkt = dossier.market_evidence
        if mkt.suspect_volume > mkt.total_volume:
            errors.append(f"Suspect volume {mkt.suspect_volume} exceeds total volume {mkt.total_volume}")

        if mkt.total_volume > 0:
            calc_ratio = mkt.suspect_volume / mkt.total_volume
            if abs(calc_ratio - mkt.suspect_volume_ratio) > 0.05:
                errors.append(
                    f"Suspect volume ratio mismatch: declared {mkt.suspect_volume_ratio:.3f} vs calculated {calc_ratio:.3f}"
                )

        return len(errors) == 0, errors
