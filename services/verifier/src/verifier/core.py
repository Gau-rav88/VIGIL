import json
import zipfile
from pathlib import Path
from typing import Any
from vigil_common.canonical import canonical_json_bytes
from vigil_common.hashing import sha256_hex, sha256_bytes
from vigil_common.ledger import verify_ledger_chain
from vigil_common.merkle import compute_merkle_root
from vigil_common.signing import verify_ed25519


def verify_bundle(bundle_path: str | Path, pubkey_pem: str | None = None) -> dict[str, Any]:
    checks = []
    failed = []

    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            namelist = set(zf.namelist())

            # 1. Check required files
            required = ["dossier.json", "dossier.sig", "manifest.json", "ledger_proof.json"]
            for req in required:
                if req not in namelist:
                    failed.append(f"MISSING_{req.upper().replace('.', '_')}")

            if failed:
                return {"valid": False, "checks": checks, "failed": failed}

            dossier_data = json.loads(zf.read("dossier.json").decode("utf-8"))
            manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
            ledger_proof = json.loads(zf.read("ledger_proof.json").decode("utf-8"))
            sig_b64 = zf.read("dossier.sig").decode("utf-8").strip()

            checks.append({"name": "SCHEMA_VALID", "ok": True})

            # 2. Check Evidence Hashes
            evidence_items = manifest_data.get("evidence_manifest", [])
            checked_count = 0
            hashes_ok = True
            for item in evidence_items:
                ev_id = item["evidence_id"]
                expected_sha = item["sha256"]
                filename = f"evidence/{ev_id}"
                if filename in namelist:
                    actual_sha = sha256_hex(zf.read(filename))
                    if actual_sha != expected_sha:
                        hashes_ok = False
                        failed.append("HASH_MISMATCH")
                        break
                    checked_count += 1

            checks.append({"name": "EVIDENCE_HASHES", "ok": hashes_ok, "checked": checked_count})

            # 3. Check Merkle Root
            calc_root, _ = compute_merkle_root(evidence_items)
            expected_root = manifest_data.get("merkle_root") or dossier_data.get("merkle_root")
            merkle_ok = (calc_root == expected_root)
            if not merkle_ok:
                failed.append("MERKLE_MISMATCH")
            checks.append({"name": "MERKLE_ROOT", "ok": merkle_ok})

            # 4. Check Ledger Chain
            ledger_entries = ledger_proof.get("entries", [])
            ledger_ok = verify_ledger_chain(ledger_entries)
            if not ledger_ok:
                failed.append("LEDGER_CHAIN_BROKEN")
            checks.append({"name": "LEDGER_CHAIN", "ok": ledger_ok, "entries": len(ledger_entries)})

            # 5. Check Signature
            if pubkey_pem is None and "pubkey.pem" in namelist:
                pubkey_pem = zf.read("pubkey.pem").decode("utf-8")

            if pubkey_pem:
                dossier_copy = dict(dossier_data)
                dossier_copy.pop("signature", None)
                canon_bytes = canonical_json_bytes(dossier_copy)
                digest = sha256_bytes(canon_bytes)
                sig_ok = verify_ed25519(pubkey_pem, digest, sig_b64)
                if not sig_ok:
                    failed.append("SIGNATURE_INVALID")
                checks.append({
                    "name": "SIGNATURE",
                    "ok": sig_ok,
                    "key_id": dossier_data.get("signature", {}).get("key_id", "unknown")
                })

            review_present = dossier_data.get("human_review", {}).get("status") in ["APPROVED", "REJECTED", "REWORK"]
            checks.append({"name": "HUMAN_REVIEW_PRESENT", "ok": review_present})

            is_valid = len(failed) == 0 and all(c["ok"] for c in checks)
            return {
                "valid": is_valid,
                "dossier_id": dossier_data.get("dossier_id"),
                "version": dossier_data.get("version"),
                "checks": checks,
                "failed": failed,
            }

    except Exception as e:
        return {"valid": False, "checks": checks, "failed": ["BUNDLE_ERROR", str(e)]}
