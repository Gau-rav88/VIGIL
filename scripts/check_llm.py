#!/usr/bin/env python3
"""
scripts/check_llm.py
Verifies LLM provider credentials and model availability.
"""
from __future__ import annotations

import argparse
import os
import sys

try:
    import httpx
except ImportError:
    print("[ERROR] httpx is required: install it via 'uv pip install httpx' or 'pip install httpx'")
    sys.exit(1)


def check_groq(api_key: str, target_model: str) -> bool:
    print("Checking Groq provider...")
    url = "https://api.groq.com/openai/v1/models"
    try:
        resp = httpx.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        if resp.status_code != 200:
            print(f"[ERROR] Groq API returned status {resp.status_code}: {resp.text[:200]}")
            return False

        data = resp.json()
        models = [m.get("id") for m in data.get("data", []) if "id" in m]
        print(f"Discovered {len(models)} Groq models.")
        if target_model in models:
            print(f"[OK] Model '{target_model}' is available on Groq.")
            return True
        else:
            print(f"[WARN] Configured model '{target_model}' NOT found in Groq models list.")
            print("Available models:")
            for m in sorted(models):
                print(f"  - {m}")
            return False
    except Exception as exc:
        print(f"[ERROR] Failed to query Groq models: {exc}")
        return False


def check_anthropic(api_key: str, target_model: str) -> bool:
    print("Checking Anthropic provider...")
    url = "https://api.anthropic.com/v1/models"
    try:
        resp = httpx.get(
            url,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            timeout=10.0,
        )
        if resp.status_code != 200:
            print(f"[ERROR] Anthropic API returned status {resp.status_code}: {resp.text[:200]}")
            return False

        data = resp.json()
        models = [m.get("id") for m in data.get("data", []) if "id" in m]
        print(f"Discovered {len(models)} Anthropic models.")
        if target_model in models:
            print(f"[OK] Model '{target_model}' is available on Anthropic.")
            return True
        else:
            print(f"[WARN] Configured model '{target_model}' NOT found in Anthropic models list.")
            print("Available models:")
            for m in sorted(models):
                print(f"  - {m}")
            return False
    except Exception as exc:
        print(f"[ERROR] Failed to query Anthropic models: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Check LLM provider credentials and model availability.")
    parser.add_argument("--provider", help="groq, anthropic, or none", default=None)
    parser.add_argument("--model", help="Target model to check", default=None)
    args = parser.parse_args()

    provider = (args.provider or os.getenv("LLM_PROVIDER", "none")).strip().lower()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    if provider == "none" and not groq_key and not anthropic_key:
        print("[INFO] LLM_PROVIDER=none and no API keys are set.")
        print("[INFO] VIGIL will run in deterministic TEMPLATE mode (court-admissible citations).")
        return 0

    if provider == "groq" or (provider == "none" and groq_key):
        if not groq_key:
            print("[ERROR] Provider is 'groq' but GROQ_API_KEY is not set.")
            return 1
        model = args.model or os.getenv("GROQ_MODEL") or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        success = check_groq(groq_key, model)
        return 0 if success else 1

    if provider == "anthropic" or (provider == "none" and anthropic_key):
        if not anthropic_key:
            print("[ERROR] Provider is 'anthropic' but ANTHROPIC_API_KEY is not set.")
            return 1
        model = args.model or os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        success = check_anthropic(anthropic_key, model)
        return 0 if success else 1

    print(f"[WARN] Unknown or unconfigured provider: {provider}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
