from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from vigil_common.models.market import L2Snapshot, L3OrderEvent, TradeTick

from simulator.groundtruth import ScenarioGroundTruth
from simulator.orderbook import OrderBook
from simulator.ring import RingSpec, build_ring, generate_id

LARGE_MID_SYMBOLS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "TATAMOTORS", "BHARTIARTL",
    "ITC", "SBIN", "LICI", "HINDUNILVR", "LT", "BAJFINANCE", "MARUTI", "SUNPHARMA",
    "TITAN", "KOTAKBANK", "ADANIENT", "AXISBANK", "NTPC", "ONGC", "POWERGRID",
    "TATASTEEL", "ULTRACEMCO", "M&M", "COALINDIA", "BAJAJFINSV", "WIPRO", "HCLTECH", "ACMESYSTEMS"
]

MICRO_SME_SYMBOLS = [
    "ZENITHSME", "MICROTECH", "ALPHASME", "SOLARIS", "NOVAPHARMA",
    "NEXUSSME", "PRISMIND", "VORTEXSME", "STELLARSME", "APEXSME"
]


@dataclass
class OrganicAccount:
    account_id: str
    broker_id: str
    device_fp: str
    ip_hash: str
    asn: int
    gateway_id: str


@dataclass
class SymbolState:
    symbol: str
    tier: str  # large, mid, micro, sme
    base_price: float
    current_mid: float
    tps: float
    sigma: float
    book: OrderBook


class MarketModel:
    def __init__(
        self,
        rng: np.random.Generator,
        scenario_cfg: dict[str, Any] | None = None,
    ) -> None:
        self.rng = rng
        self.scenario_cfg = scenario_cfg or {}
        self.organic_accounts = self._init_organic_accounts(2000)
        self.symbols_state: dict[str, SymbolState] = {}
        self.ring_spec: RingSpec | None = build_ring(self.scenario_cfg, self.rng)
        self.spoofer_accounts: list[OrganicAccount] = []
        self.ground_truth: ScenarioGroundTruth | None = None
        self.order_counter = 0

        self._init_symbols()
        self._init_ground_truth()

    def _init_organic_accounts(self, count: int) -> list[OrganicAccount]:
        brokers = [f"BRK-{i+1:02d}" for i in range(12)]
        num_devices = count // 2  # max 2 accounts per device
        num_asns = count // 5     # max 5 accounts per ASN

        devices = [generate_id(self.rng, 22) for _ in range(num_devices)]
        asns = [int(self.rng.integers(10000, 65000)) for _ in range(num_asns)]

        accounts: list[OrganicAccount] = []
        for i in range(count):
            acc_id = generate_id(self.rng, 22)
            brk = brokers[i % len(brokers)]
            dev = devices[i % num_devices]
            asn = asns[i % num_asns]
            ip = generate_id(self.rng, 22)
            gw = f"GW-{self.rng.integers(1, 6)}"
            accounts.append(
                OrganicAccount(
                    account_id=acc_id,
                    broker_id=brk,
                    device_fp=dev,
                    ip_hash=ip,
                    asn=asn,
                    gateway_id=gw,
                )
            )
        return accounts

    def _init_symbols(self) -> None:
        # 30 Large / Mid
        for sym in LARGE_MID_SYMBOLS:
            base_p = float(self.rng.integers(100, 2500))
            tps = float(self.rng.uniform(1.5, 4.0))
            self.symbols_state[sym] = SymbolState(
                symbol=sym,
                tier="large",
                base_price=base_p,
                current_mid=base_p,
                tps=tps,
                sigma=0.015,
                book=OrderBook(symbol=sym),
            )

        # 10 Micro / SME
        for sym in MICRO_SME_SYMBOLS:
            base_p = 40.0 if sym == "ZENITHSME" else float(self.rng.integers(15, 80))
            tps = 0.4 if sym == "ZENITHSME" else float(self.rng.uniform(0.2, 0.6))
            self.symbols_state[sym] = SymbolState(
                symbol=sym,
                tier="sme",
                base_price=base_p,
                current_mid=base_p,
                tps=tps,
                sigma=0.03,
                book=OrderBook(symbol=sym),
            )

        # Override target if specified in scenario
        target = self.scenario_cfg.get("target")
        if target:
            sym = target.get("symbol", "ZENITHSME")
            base_p = float(target.get("base_price", 40.0))
            tps = float(target.get("base_rate_tps", 0.4))
            tier = str(target.get("tier", "micro"))
            self.symbols_state[sym] = SymbolState(
                symbol=sym,
                tier=tier,
                base_price=base_p,
                current_mid=base_p,
                tps=tps,
                sigma=0.035,
                book=OrderBook(symbol=sym),
            )

        # Seed initial books with orders
        for sym_state in self.symbols_state.values():
            self._seed_initial_book(sym_state)

    def _seed_initial_book(self, state: SymbolState) -> None:
        mid = state.current_mid
        tick = 0.05
        # Add 10 bid levels and 10 ask levels
        for level in range(1, 11):
            bid_p = round(mid - level * tick, 2)
            ask_p = round(mid + level * tick, 2)
            acc_bid = self.organic_accounts[self.rng.integers(0, len(self.organic_accounts))]
            acc_ask = self.organic_accounts[self.rng.integers(0, len(self.organic_accounts))]
            qty = int(self.rng.integers(50, 500) * 10)

            self.order_counter += 1
            state.book.add_order(
                order_id=f"O-SEED-B-{self.order_counter}",
                side="BUY",
                price=bid_p,
                qty=qty,
                account_id=acc_bid.account_id,
                broker_id=acc_bid.broker_id,
                ts_exchange="2026-03-14T04:00:00.000000Z",
                gateway_id=acc_bid.gateway_id,
                device_fp=acc_bid.device_fp,
                ip_hash=acc_bid.ip_hash,
                asn=acc_bid.asn,
            )
            self.order_counter += 1
            state.book.add_order(
                order_id=f"O-SEED-A-{self.order_counter}",
                side="SELL",
                price=ask_p,
                qty=qty,
                account_id=acc_ask.account_id,
                broker_id=acc_ask.broker_id,
                ts_exchange="2026-03-14T04:00:00.000000Z",
                gateway_id=acc_ask.gateway_id,
                device_fp=acc_ask.device_fp,
                ip_hash=acc_ask.ip_hash,
                asn=acc_ask.asn,
            )

    def _init_ground_truth(self) -> None:
        scenario_id = self.scenario_cfg.get("id", "baseline_01")
        target_sym = self.scenario_cfg.get("target", {}).get("symbol", "")

        gt = ScenarioGroundTruth(
            scenario_id=scenario_id,
            target_symbol=target_sym,
        )

        if self.ring_spec:
            gt.ring_accounts = [acc.account_id for acc in self.ring_spec.accounts]
            gt.brokers = list({acc.broker_id for acc in self.ring_spec.accounts})
            gt.shared_devices = self.ring_spec.shared_devices
            gt.shared_asn = self.ring_spec.shared_asn
            gt.wash_cycles = self.ring_spec.wash_cycles
            gt.reaction_lag_s = self.ring_spec.reaction_lag_mean
            gt.dump_start_s = self.ring_spec.dump_start_s

            social_cfg = self.scenario_cfg.get("social", {})
            t0_s = social_cfg.get("t0_s")
            if t0_s is not None:
                gt.social_burst_t0_s = float(t0_s)
                gt.market_pump_t0_s = float(t0_s + self.ring_spec.reaction_lag_mean)
                gt.effective_lag_s = self.ring_spec.reaction_lag_mean

        # Spoofing ground truth
        spoofer_cfg = self.scenario_cfg.get("spoofers")
        if spoofer_cfg:
            count = int(spoofer_cfg.get("count", 2))
            spoofer_accs = [generate_id(self.rng, 22) for _ in range(count)]
            gt.spoofers = spoofer_accs
            self.spoofer_accounts = [
                OrganicAccount(
                    account_id=acc_id,
                    broker_id=f"BRK-SP-{i+1:02d}",
                    device_fp=generate_id(self.rng, 22),
                    ip_hash=generate_id(self.rng, 22),
                    asn=int(self.rng.integers(10000, 65000)),
                    gateway_id=f"GW-SP-{i+1}",
                )
                for i, acc_id in enumerate(spoofer_accs)
            ]

        self.ground_truth = gt

    def generate_step(
        self,
        sim_time_s: float,
        dt_s: float,
        current_iso_time: str,
    ) -> tuple[list[L3OrderEvent], list[TradeTick], list[L2Snapshot]]:
        all_l3: list[L3OrderEvent] = []
        all_trades: list[TradeTick] = []
        all_l2: list[L2Snapshot] = []

        scenario_id = self.scenario_cfg.get("id", "baseline")
        target_info = self.scenario_cfg.get("target", {})
        target_symbol = target_info.get("symbol")

        # 1. Price dynamics & organic orders across symbols
        for sym, state in self.symbols_state.items():
            # Check if target symbol is undergoing scenario pump/dump
            is_target = (sym == target_symbol)
            drift = 0.0

            if is_target and self.ring_spec:
                price_effect = self.scenario_cfg.get("price_effect", {})
                pump_pct = price_effect.get("pump_pct", 38.0)
                dump_pct = price_effect.get("dump_pct", -30.0)

                social_t0 = self.scenario_cfg.get("social", {}).get("t0_s", 300)
                pump_start = social_t0 + self.ring_spec.reaction_lag_mean
                dump_start = self.ring_spec.dump_start_s or 1140

                if pump_start <= sim_time_s < dump_start:
                    # Pump phase: upward drift
                    pump_duration = dump_start - pump_start
                    drift = (pump_pct / 100.0) / max(1.0, pump_duration)
                elif sim_time_s >= dump_start:
                    # Dump phase: downward drop
                    dump_duration = 300.0
                    if sim_time_s < dump_start + dump_duration:
                        drift = (dump_pct / 100.0) / dump_duration

            # GBM step
            norm_shock = self.rng.standard_normal()
            step_vol = (state.sigma / 60.0) * np.sqrt(dt_s)
            state.current_mid *= np.exp((drift - 0.5 * step_vol**2) * dt_s + step_vol * norm_shock)

            # Poisson arrival for organic orders
            expected_orders = state.tps * dt_s
            num_orders = int(self.rng.poisson(expected_orders))

            for _ in range(num_orders):
                acc = self.organic_accounts[self.rng.integers(0, len(self.organic_accounts))]
                is_buy = bool(self.rng.random() < 0.5)
                self.order_counter += 1
                oid = f"O-{self.order_counter:09d}"

                # Decide if crossing (market/aggressive) or resting (limit)
                is_aggressive = bool(self.rng.random() < 0.35)
                tick = 0.05
                side: Literal["BUY", "SELL"]
                if is_buy:
                    if is_aggressive:
                        best_ask = state.book.best_ask() or (state.current_mid + tick)
                        order_price = best_ask
                    else:
                        order_price = round(state.current_mid - self.rng.integers(1, 5) * tick, 2)
                    side = "BUY"
                else:
                    if is_aggressive:
                        best_bid = state.book.best_bid() or (state.current_mid - tick)
                        order_price = best_bid
                    else:
                        order_price = round(state.current_mid + self.rng.integers(1, 5) * tick, 2)
                    side = "SELL"

                qty = int(self.rng.integers(10, 100) * (5 if state.tier == "sme" else 10))

                l3s, trs = state.book.add_order(
                    order_id=oid,
                    side=side,
                    price=order_price,
                    qty=qty,
                    account_id=acc.account_id,
                    broker_id=acc.broker_id,
                    ts_exchange=current_iso_time,
                    gateway_id=acc.gateway_id,
                    device_fp=acc.device_fp,
                    ip_hash=acc.ip_hash,
                    asn=acc.asn,
                )
                all_l3.extend(l3s)
                all_trades.extend(trs)

            # Generate L2 snapshot for this symbol
            # (Every 250ms matches our dt_s!)
            l2 = state.book.get_l2_snapshot(
                ts_exchange=current_iso_time,
                depth_levels=10,
            )
            all_l2.append(l2)

        # 2. Ring manipulation orders (if active)
        if self.ring_spec and target_symbol and target_symbol in self.symbols_state:
            target_state = self.symbols_state[target_symbol]
            social_t0 = self.scenario_cfg.get("social", {}).get("t0_s", 300)
            pump_start = social_t0 + self.ring_spec.reaction_lag_mean
            dump_start = self.ring_spec.dump_start_s or 1140

            # (A) Coordinated pump buys
            if pump_start <= sim_time_s < dump_start:
                # Ring members buy aggressively
                if self.rng.random() < 0.6:
                    ring_acc = self.ring_spec.accounts[self.rng.integers(0, len(self.ring_spec.accounts))]
                    self.order_counter += 1
                    oid = f"O-RING-{self.order_counter:09d}"
                    best_ask = target_state.book.best_ask() or target_state.current_mid
                    # Aggressive buy lifting asks
                    l3s, trs = target_state.book.add_order(
                        order_id=oid,
                        side="BUY",
                        price=round(best_ask * 1.01, 2),
                        qty=int(self.rng.integers(200, 800)),
                        account_id=ring_acc.account_id,
                        broker_id=ring_acc.broker_id,
                        ts_exchange=current_iso_time,
                        gateway_id=ring_acc.gateway_id,
                        device_fp=ring_acc.device_fp,
                        ip_hash=ring_acc.ip_hash,
                        asn=ring_acc.asn,
                        scenario_label=scenario_id,
                    )
                    all_l3.extend(l3s)
                    all_trades.extend(trs)

            # (B) Wash trading cycles
            wash_cycles = self.ring_spec.wash_cycles
            if wash_cycles and (scenario_id == "wash_ring_01" or pump_start <= sim_time_s < dump_start):
                interval_s = 20.0
                c_idx = int(sim_time_s // interval_s) - 1
                if sim_time_s >= 20.0 and (sim_time_s % interval_s) < dt_s and 0 <= c_idx < len(wash_cycles):
                    cycle = wash_cycles[c_idx]
                    acc_ids = cycle["accounts"]
                    qty = int(cycle["qty"])
                    wash_price = round(target_state.current_mid, 2)

                    # Execute all legs of the cycle so the circular trade closes
                    for step_idx in range(len(acc_ids)):
                        seller_id = acc_ids[step_idx]
                        buyer_id = acc_ids[(step_idx + 1) % len(acc_ids)]

                        seller = next((a for a in self.ring_spec.accounts if a.account_id == seller_id), None)
                        buyer = next((a for a in self.ring_spec.accounts if a.account_id == buyer_id), None)
                        if not seller or not buyer:
                            continue

                        self.order_counter += 1
                        sell_oid = f"O-WASH-S-{self.order_counter:09d}"
                        self.order_counter += 1
                        buy_oid = f"O-WASH-B-{self.order_counter:09d}"

                        # Seller places limit
                        s_l3, _ = target_state.book.add_order(
                            order_id=sell_oid,
                            side="SELL",
                            price=wash_price,
                            qty=qty,
                            account_id=seller.account_id,
                            broker_id=seller.broker_id,
                            ts_exchange=current_iso_time,
                            gateway_id=seller.gateway_id,
                            device_fp=seller.device_fp,
                            ip_hash=seller.ip_hash,
                            asn=seller.asn,
                            scenario_label=scenario_id,
                        )
                        all_l3.extend(s_l3)

                        # Buyer immediately takes it
                        b_l3, b_trs = target_state.book.add_order(
                            order_id=buy_oid,
                            side="BUY",
                            price=wash_price,
                            qty=qty,
                            account_id=buyer.account_id,
                            broker_id=buyer.broker_id,
                            ts_exchange=current_iso_time,
                            gateway_id=buyer.gateway_id,
                            device_fp=buyer.device_fp,
                            ip_hash=buyer.ip_hash,
                            asn=buyer.asn,
                            scenario_label=scenario_id,
                            match_order_id=sell_oid,
                        )
                        all_l3.extend(b_l3)
                        all_trades.extend(b_trs)
                        for tr in b_trs:
                            if self.ground_truth:
                                self.ground_truth.wash_trade_ids.append(tr.trade_id)

            # (C) Coordinated dump selling
            if sim_time_s >= dump_start:
                if self.rng.random() < 0.8:
                    ring_acc = self.ring_spec.accounts[self.rng.integers(0, len(self.ring_spec.accounts))]
                    self.order_counter += 1
                    oid = f"O-DUMP-{self.order_counter:09d}"
                    best_bid = target_state.book.best_bid() or target_state.current_mid
                    # Aggressive market sell hitting bids
                    l3s, trs = target_state.book.add_order(
                        order_id=oid,
                        side="SELL",
                        price=round(best_bid * 0.98, 2),
                        qty=int(self.rng.integers(500, 2000)),
                        account_id=ring_acc.account_id,
                        broker_id=ring_acc.broker_id,
                        ts_exchange=current_iso_time,
                        gateway_id=ring_acc.gateway_id,
                        device_fp=ring_acc.device_fp,
                        ip_hash=ring_acc.ip_hash,
                        asn=ring_acc.asn,
                        scenario_label=scenario_id,
                    )
                    all_l3.extend(l3s)
                    all_trades.extend(trs)

        # 3. Spoofing cycles (if active)
        if self.spoofer_accounts and target_symbol and target_symbol in self.symbols_state:
            target_state = self.symbols_state[target_symbol]
            cycles = int(self.scenario_cfg.get("spoofers", {}).get("cycles", 8))
            interval = max(30.0, 900.0 / max(1, cycles))
            if sim_time_s >= 10.0 and (sim_time_s % interval) < dt_s:
                for sp_acc in self.spoofer_accounts:
                    best_bid = target_state.book.best_bid() or target_state.current_mid
                    tick = 0.05
                    spoof_oids: list[str] = []
                    # Layer 5 large BUY orders below best bid
                    for l_idx in range(1, 6):
                        self.order_counter += 1
                        oid = f"O-SPOOF-{self.order_counter:09d}"
                        spoof_oids.append(oid)
                        spoof_p = round(best_bid - l_idx * tick, 2)
                        s_l3, _ = target_state.book.add_order(
                            order_id=oid,
                            side="BUY",
                            price=spoof_p,
                            qty=3000,
                            account_id=sp_acc.account_id,
                            broker_id=sp_acc.broker_id,
                            ts_exchange=current_iso_time,
                            gateway_id=sp_acc.gateway_id,
                            device_fp=sp_acc.device_fp,
                            ip_hash=sp_acc.ip_hash,
                            asn=sp_acc.asn,
                            scenario_label=scenario_id,
                        )
                        all_l3.extend(s_l3)

                    # Opposite-side aggressive SELL order crossing best bid
                    self.order_counter += 1
                    exec_oid = f"O-SPOOF-EXEC-{self.order_counter:09d}"
                    ex_l3, ex_tr = target_state.book.add_order(
                        order_id=exec_oid,
                        side="SELL",
                        price=round(best_bid, 2),
                        qty=200,
                        account_id=sp_acc.account_id,
                        broker_id=sp_acc.broker_id,
                        ts_exchange=current_iso_time,
                        gateway_id=sp_acc.gateway_id,
                        device_fp=sp_acc.device_fp,
                        ip_hash=sp_acc.ip_hash,
                        asn=sp_acc.asn,
                        scenario_label=scenario_id,
                    )
                    all_l3.extend(ex_l3)
                    all_trades.extend(ex_tr)

                    # Cancel the layered BUY orders
                    for c_oid in spoof_oids:
                        c_ev = target_state.book.cancel_order(c_oid, current_iso_time)
                        if c_ev:
                            all_l3.append(c_ev)

        return all_l3, all_trades, all_l2
