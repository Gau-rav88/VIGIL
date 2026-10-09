import argparse
import json
import sys
from pathlib import Path

from verifier.core import verify_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="VIGIL Forensic Dossier Offline Verifier")
    parser.add_argument("bundle", type=str, help="Path to evidence bundle ZIP file")
    parser.add_argument("--pubkey", type=str, required=False, help="Path to Ed25519 public key PEM")
    parser.add_argument("--json", action="store_true", help="Output verification result as JSON")
    args = parser.parse_args()

    pubkey_pem = None
    if args.pubkey:
        pubkey_pem = Path(args.pubkey).read_text(encoding="utf-8")

    result = verify_bundle(args.bundle, pubkey_pem)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = "PASSED" if result["valid"] else "FAILED"
        print(f"Verification: {status}")
        for check in result["checks"]:
            mark = "✓" if check.get("ok") else "✗"
            print(f"  [{mark}] {check['name']}")
        if result["failed"]:
            print(f"Failures: {', '.join(result['failed'])}")

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
