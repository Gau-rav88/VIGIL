from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

import numpy as np


def generate_id(rng: np.random.Generator, length: int = 22) -> str:
    raw = rng.bytes(length)
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=").replace("/", "_").replace("+", "-")
    return encoded[:length]


@dataclass
class RingAccount:
    account_id: str
    broker_id: str
    device_fp: str
    ip_hash: str
    asn: int
    gateway_id: str


@dataclass
class RingSpec:
    accounts: list[RingAccount]
    shared_devices: dict[str, list[str]]
    shared_asn: int
    wash_cycles: list[dict[str, Any]]
    reaction_lag_mean: float
    reaction_lag_sd: float
    buy_volume_share: float
    dump_start_s: float | None = None
    wash_trade_ids: list[str] = field(default_factory=list)


def build_ring(
    scenario_cfg: dict[str, Any],
    rng: np.random.Generator,
) -> RingSpec | None:
    ring_cfg = scenario_cfg.get("ring")
    if not ring_cfg:
        return None

    num_accounts = ring_cfg.get("accounts", 6)
    num_brokers = ring_cfg.get("brokers", 3)
    num_devices = ring_cfg.get("shared_devices", max(1, num_accounts // 4))
    shared_asn = 55836 if ring_cfg.get("shared_asn") else int(rng.integers(10000, 60000))

    brokers = [f"BRK-{i+1:02d}" for i in range(num_brokers)]
    device_fps = [generate_id(rng, 22) for _ in range(num_devices)]

    accounts: list[RingAccount] = []
    device_map: dict[str, list[str]] = {dev: [] for dev in device_fps}

    for i in range(num_accounts):
        acc_id = generate_id(rng, 22)
        dev = device_fps[i % num_devices]
        device_map[dev].append(acc_id)
        brk = brokers[i % num_brokers]
        ip = generate_id(rng, 22)
        gw = f"GW-{rng.integers(1, 4)}"

        accounts.append(
            RingAccount(
                account_id=acc_id,
                broker_id=brk,
                device_fp=dev,
                ip_hash=ip,
                asn=shared_asn,
                gateway_id=gw,
            )
        )

    # Build wash cycles
    wash_cycles: list[dict[str, Any]] = []
    wc_cfg = ring_cfg.get("wash_cycles")
    if wc_cfg:
        count = wc_cfg.get("count", 4)
        lengths = wc_cfg.get("lengths", [2, 3, 4])
        qty = wc_cfg.get("qty", 1000)

        for c_idx in range(count):
            cycle_len = lengths[c_idx % len(lengths)]
            # Pick cycle_len accounts
            perm = rng.choice(num_accounts, size=min(cycle_len, num_accounts), replace=False)
            cycle_accs = [accounts[idx].account_id for idx in perm]
            wash_cycles.append({
                "cycle_id": f"wash_cycle_{c_idx+1}",
                "accounts": cycle_accs,
                "length": len(cycle_accs),
                "qty": qty,
            })

    lag_cfg = ring_cfg.get("reaction_lag_s", {})
    if isinstance(lag_cfg, dict):
        reaction_lag_mean = float(lag_cfg.get("mean", 150))
        reaction_lag_sd = float(lag_cfg.get("sd", 20))
    else:
        reaction_lag_mean = float(lag_cfg) if lag_cfg else 150.0
        reaction_lag_sd = 20.0

    return RingSpec(
        accounts=accounts,
        shared_devices=device_map,
        shared_asn=shared_asn,
        wash_cycles=wash_cycles,
        reaction_lag_mean=reaction_lag_mean,
        reaction_lag_sd=reaction_lag_sd,
        buy_volume_share=float(ring_cfg.get("buy_volume_share", 0.45)),
        dump_start_s=float(ring_cfg.get("dump_start_s", 1140)) if ring_cfg.get("dump_start_s") else None,
    )
