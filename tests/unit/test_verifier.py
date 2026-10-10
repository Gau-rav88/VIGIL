from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from verifier.cli import main as verifier_cli_main
from verifier.core import verify_bundle


def test_verifier_core_and_cli(tmp_path: Path) -> None:
    bundle_path = Path("reports/sample_bundle/bundle.zip")
    if not bundle_path.exists():
        pytest.skip("reports/sample_bundle/bundle.zip not generated yet")

    # 1. Test verifier.core
    res = verify_bundle(str(bundle_path))
    assert res["valid"] is True
    assert len(res["checks"]) == 6

    # 2. Test verifier.cli with normal output
    test_args = ["vigil-verify", str(bundle_path), "--pubkey", "keys/dev_ed25519.pub"]
    with patch.object(sys, "argv", test_args):
        with pytest.raises(SystemExit) as exc:
            verifier_cli_main()
        assert exc.value.code == 0

    # 3. Test verifier.cli with --json
    test_args_json = ["vigil-verify", str(bundle_path), "--pubkey", "keys/dev_ed25519.pub", "--json"]
    with patch.object(sys, "argv", test_args_json):
        with pytest.raises(SystemExit) as exc:
            verifier_cli_main()
        assert exc.value.code == 0

    # 4. Test verifier.cli on invalid bundle
    bad_zip = tmp_path / "bad.zip"
    bad_zip.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    test_args_bad = ["vigil-verify", str(bad_zip)]
    with patch.object(sys, "argv", test_args_bad):
        with pytest.raises(SystemExit) as exc:
            verifier_cli_main()
        assert exc.value.code == 1
