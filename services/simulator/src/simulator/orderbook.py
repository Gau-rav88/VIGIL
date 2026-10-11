from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from vigil_common.models.market import L2Snapshot, L3OrderEvent, Party, TradeTick


@dataclass
class RestingOrder:
    order_id: str
    symbol: str
    exchange: Literal["NSE", "BSE", "NASDAQ", "NYSE", "SYNTH"]
    side: Literal["BUY", "SELL"]
    price: float
    qty: int
    leaves_qty: int
    account_id: str
    broker_id: str
    gateway_id: str | None = None
    device_fp: str | None = None
    ip_hash: str | None = None
    asn: int | None = None
    api_client_id: str | None = None
    order_to_ack_us: int | None = None
    scenario_label: str | None = None


class OrderBook:
    def __init__(
        self,
        symbol: str,
        exchange: Literal["NSE", "BSE", "NASDAQ", "NYSE", "SYNTH"] = "SYNTH",
        run_id: str = "",
    ) -> None:
        self.symbol = symbol
        self.exchange = exchange
        self.run_id = run_id
        self.bids: dict[float, list[RestingOrder]] = {}  # price -> orders
        self.asks: dict[float, list[RestingOrder]] = {}  # price -> orders
        self.orders_by_id: dict[str, RestingOrder] = {}
        self.seq: int = 0
        self.trade_seq: int = 0

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def next_trade_id(self) -> str:
        self.trade_seq += 1
        if self.run_id:
            return f"T-{self.symbol}-{self.run_id}-{self.trade_seq:09d}"
        return f"T-{self.symbol}-{self.trade_seq:09d}"

    def make_event_id(self, seq: int, tag: str) -> str:
        key = f"{self.symbol}:{seq}:{tag}:{self.run_id}" if self.run_id else f"{self.symbol}:{seq}:{tag}"
        return str(uuid.uuid5(uuid.NAMESPACE_OID, key))

    def best_bid(self) -> float | None:
        active_bids = [p for p, orders in self.bids.items() if orders]
        return max(active_bids) if active_bids else None

    def best_ask(self) -> float | None:
        active_asks = [p for p, orders in self.asks.items() if orders]
        return min(active_asks) if active_asks else None

    def add_order(
        self,
        order_id: str,
        side: Literal["BUY", "SELL"],
        price: float,
        qty: int,
        account_id: str,
        broker_id: str,
        ts_exchange: str,
        gateway_id: str | None = None,
        device_fp: str | None = None,
        ip_hash: str | None = None,
        asn: int | None = None,
        api_client_id: str | None = None,
        order_to_ack_us: int | None = 500,
        scenario_label: str | None = None,
        is_synthetic: bool = True,
        match_order_id: str | None = None,
    ) -> tuple[list[L3OrderEvent], list[TradeTick]]:
        new_seq = self.next_seq()
        new_event = L3OrderEvent(
            schema_version="1.0.0",
            event_id=self.make_event_id(new_seq, f"{order_id}:NEW"),
            exchange=self.exchange,
            symbol=self.symbol,
            seq=new_seq,
            ts_exchange=ts_exchange,
            order_id=order_id,
            action="NEW",
            side=side,
            order_type="LIMIT",
            price=f"{price:.2f}",
            qty=qty,
            leaves_qty=qty,
            account_id=account_id,
            broker_id=broker_id,
            gateway_id=gateway_id,
            device_fp=device_fp,
            ip_hash=ip_hash,
            asn=asn,
            api_client_id=api_client_id,
            order_to_ack_us=order_to_ack_us,
            is_synthetic=is_synthetic,
        )

        l3_events: list[L3OrderEvent] = [new_event]
        trades: list[TradeTick] = []
        leaves_qty = qty

        incoming_order = RestingOrder(
            order_id=order_id,
            symbol=self.symbol,
            exchange=self.exchange,
            side=side,
            price=price,
            qty=qty,
            leaves_qty=qty,
            account_id=account_id,
            broker_id=broker_id,
            gateway_id=gateway_id,
            device_fp=device_fp,
            ip_hash=ip_hash,
            asn=asn,
            api_client_id=api_client_id,
            order_to_ack_us=order_to_ack_us,
            scenario_label=scenario_label,
        )

        if match_order_id and match_order_id in self.orders_by_id:
            resting = self.orders_by_id[match_order_id]
            matched_qty = min(leaves_qty, resting.leaves_qty)
            leaves_qty -= matched_qty
            resting.leaves_qty -= matched_qty
            match_price = resting.price

            buyer_party = (
                Party(
                    account_id=account_id,
                    broker_id=broker_id,
                    gateway_id=gateway_id,
                    order_id=order_id,
                    device_fp=device_fp,
                    ip_hash=ip_hash,
                    asn=asn,
                    api_client_id=api_client_id,
                    order_to_ack_us=order_to_ack_us,
                )
                if side == "BUY"
                else Party(
                    account_id=resting.account_id,
                    broker_id=resting.broker_id,
                    gateway_id=resting.gateway_id,
                    order_id=resting.order_id,
                    device_fp=resting.device_fp,
                    ip_hash=resting.ip_hash,
                    asn=resting.asn,
                    api_client_id=resting.api_client_id,
                    order_to_ack_us=resting.order_to_ack_us,
                )
            )
            seller_party = (
                Party(
                    account_id=resting.account_id,
                    broker_id=resting.broker_id,
                    gateway_id=resting.gateway_id,
                    order_id=resting.order_id,
                    device_fp=resting.device_fp,
                    ip_hash=resting.ip_hash,
                    asn=resting.asn,
                    api_client_id=resting.api_client_id,
                    order_to_ack_us=resting.order_to_ack_us,
                )
                if side == "BUY"
                else Party(
                    account_id=account_id,
                    broker_id=broker_id,
                    gateway_id=gateway_id,
                    order_id=order_id,
                    device_fp=device_fp,
                    ip_hash=ip_hash,
                    asn=asn,
                    api_client_id=api_client_id,
                    order_to_ack_us=order_to_ack_us,
                )
            )

            trade_id = self.next_trade_id()
            trade_seq = self.next_seq()
            trade = TradeTick(
                schema_version="1.0.0",
                event_id=self.make_event_id(trade_seq, trade_id),
                exchange=self.exchange,
                symbol=self.symbol,
                trade_id=trade_id,
                seq=trade_seq,
                ts_exchange=ts_exchange,
                price=f"{match_price:.2f}",
                qty=matched_qty,
                aggressor_side=side,
                buyer=buyer_party,
                seller=seller_party,
                market_segment="SME" if "SME" in self.symbol else "CASH",
                is_synthetic=is_synthetic,
                scenario_label=scenario_label or resting.scenario_label,
            )
            trades.append(trade)

            b_seq = self.next_seq()
            l3_events.append(
                L3OrderEvent(
                    schema_version="1.0.0",
                    event_id=self.make_event_id(b_seq, f"{order_id}:TRADE_IN"),
                    exchange=self.exchange,
                    symbol=self.symbol,
                    seq=b_seq,
                    ts_exchange=ts_exchange,
                    order_id=order_id,
                    action="TRADE",
                    side=side,
                    order_type="LIMIT",
                    price=f"{match_price:.2f}",
                    qty=matched_qty,
                    leaves_qty=leaves_qty,
                    account_id=account_id,
                    broker_id=broker_id,
                    is_synthetic=is_synthetic,
                )
            )
            s_seq = self.next_seq()
            l3_events.append(
                L3OrderEvent(
                    schema_version="1.0.0",
                    event_id=self.make_event_id(s_seq, f"{resting.order_id}:TRADE_REST"),
                    exchange=self.exchange,
                    symbol=self.symbol,
                    seq=s_seq,
                    ts_exchange=ts_exchange,
                    order_id=resting.order_id,
                    action="TRADE",
                    side=resting.side,
                    order_type="LIMIT",
                    price=f"{match_price:.2f}",
                    qty=matched_qty,
                    leaves_qty=resting.leaves_qty,
                    account_id=resting.account_id,
                    broker_id=resting.broker_id,
                    is_synthetic=is_synthetic,
                )
            )

            if resting.leaves_qty == 0:
                book_side = self.asks if resting.side == "SELL" else self.bids
                if resting.price in book_side:
                    r_list = book_side[resting.price]
                    if resting in r_list:
                        r_list.remove(resting)
                    if not r_list:
                        del book_side[resting.price]
                self.orders_by_id.pop(resting.order_id, None)

        elif side == "BUY":
            while leaves_qty > 0:
                best_ask_price = self.best_ask()
                if best_ask_price is None or best_ask_price > price:
                    break
                resting_list = self.asks[best_ask_price]
                resting = resting_list[0]
                if resting.account_id == account_id and scenario_label is None:
                    # STP: Cancel resting self order
                    resting_list.pop(0)
                    self.orders_by_id.pop(resting.order_id, None)
                    if not resting_list:
                        del self.asks[best_ask_price]
                    continue

                matched_qty = min(leaves_qty, resting.leaves_qty)
                leaves_qty -= matched_qty
                resting.leaves_qty -= matched_qty

                # Generate trade tick
                buyer_party = Party(
                    account_id=account_id,
                    broker_id=broker_id,
                    gateway_id=gateway_id,
                    order_id=order_id,
                    device_fp=device_fp,
                    ip_hash=ip_hash,
                    asn=asn,
                    api_client_id=api_client_id,
                    order_to_ack_us=order_to_ack_us,
                )
                seller_party = Party(
                    account_id=resting.account_id,
                    broker_id=resting.broker_id,
                    gateway_id=resting.gateway_id,
                    order_id=resting.order_id,
                    device_fp=resting.device_fp,
                    ip_hash=resting.ip_hash,
                    asn=resting.asn,
                    api_client_id=resting.api_client_id,
                    order_to_ack_us=resting.order_to_ack_us,
                )
                trade_id = self.next_trade_id()
                trade_seq = self.next_seq()
                trade = TradeTick(
                    schema_version="1.0.0",
                    event_id=self.make_event_id(trade_seq, trade_id),
                    exchange=self.exchange,
                    symbol=self.symbol,
                    trade_id=trade_id,
                    seq=trade_seq,
                    ts_exchange=ts_exchange,
                    price=f"{best_ask_price:.2f}",
                    qty=matched_qty,
                    aggressor_side="BUY",
                    buyer=buyer_party,
                    seller=seller_party,
                    market_segment="SME" if "SME" in self.symbol else "CASH",
                    is_synthetic=is_synthetic,
                    scenario_label=scenario_label or resting.scenario_label,
                )
                trades.append(trade)

                # L3 TRADE events
                b_seq = self.next_seq()
                l3_events.append(
                    L3OrderEvent(
                        schema_version="1.0.0",
                        event_id=self.make_event_id(b_seq, f"{order_id}:TRADE_BUY"),
                        exchange=self.exchange,
                        symbol=self.symbol,
                        seq=b_seq,
                        ts_exchange=ts_exchange,
                        order_id=order_id,
                        action="TRADE",
                        side="BUY",
                        order_type="LIMIT",
                        price=f"{best_ask_price:.2f}",
                        qty=matched_qty,
                        leaves_qty=leaves_qty,
                        account_id=account_id,
                        broker_id=broker_id,
                        is_synthetic=is_synthetic,
                    )
                )
                s_seq = self.next_seq()
                l3_events.append(
                    L3OrderEvent(
                        schema_version="1.0.0",
                        event_id=self.make_event_id(s_seq, f"{resting.order_id}:TRADE_SELL"),
                        exchange=self.exchange,
                        symbol=self.symbol,
                        seq=s_seq,
                        ts_exchange=ts_exchange,
                        order_id=resting.order_id,
                        action="TRADE",
                        side="SELL",
                        order_type="LIMIT",
                        price=f"{best_ask_price:.2f}",
                        qty=matched_qty,
                        leaves_qty=resting.leaves_qty,
                        account_id=resting.account_id,
                        broker_id=resting.broker_id,
                        is_synthetic=is_synthetic,
                    )
                )

                if resting.leaves_qty == 0:
                    resting_list.pop(0)
                    self.orders_by_id.pop(resting.order_id, None)
                    if not resting_list:
                        del self.asks[best_ask_price]

            incoming_order.leaves_qty = leaves_qty
            if leaves_qty > 0:
                self.bids.setdefault(price, []).append(incoming_order)
                self.orders_by_id[order_id] = incoming_order

        else:  # SELL
            while leaves_qty > 0:
                best_bid_price = self.best_bid()
                if best_bid_price is None or best_bid_price < price:
                    break
                resting_list = self.bids[best_bid_price]
                resting = resting_list[0]
                if resting.account_id == account_id and scenario_label is None:
                    # STP: Cancel resting self order
                    resting_list.pop(0)
                    self.orders_by_id.pop(resting.order_id, None)
                    if not resting_list:
                        del self.bids[best_bid_price]
                    continue

                matched_qty = min(leaves_qty, resting.leaves_qty)
                leaves_qty -= matched_qty
                resting.leaves_qty -= matched_qty

                buyer_party = Party(
                    account_id=resting.account_id,
                    broker_id=resting.broker_id,
                    gateway_id=resting.gateway_id,
                    order_id=resting.order_id,
                    device_fp=resting.device_fp,
                    ip_hash=resting.ip_hash,
                    asn=resting.asn,
                    api_client_id=resting.api_client_id,
                    order_to_ack_us=resting.order_to_ack_us,
                )
                seller_party = Party(
                    account_id=account_id,
                    broker_id=broker_id,
                    gateway_id=gateway_id,
                    order_id=order_id,
                    device_fp=device_fp,
                    ip_hash=ip_hash,
                    asn=asn,
                    api_client_id=api_client_id,
                    order_to_ack_us=order_to_ack_us,
                )
                sell_trade_id = self.next_trade_id()
                sell_trade_seq = self.next_seq()
                trade = TradeTick(
                    schema_version="1.0.0",
                    event_id=self.make_event_id(sell_trade_seq, sell_trade_id),
                    exchange=self.exchange,
                    symbol=self.symbol,
                    trade_id=sell_trade_id,
                    seq=sell_trade_seq,
                    ts_exchange=ts_exchange,
                    price=f"{best_bid_price:.2f}",
                    qty=matched_qty,
                    aggressor_side="SELL",
                    buyer=buyer_party,
                    seller=seller_party,
                    market_segment="SME" if "SME" in self.symbol else "CASH",
                    is_synthetic=is_synthetic,
                    scenario_label=scenario_label or resting.scenario_label,
                )
                trades.append(trade)

                s_seq2 = self.next_seq()
                l3_events.append(
                    L3OrderEvent(
                        schema_version="1.0.0",
                        event_id=self.make_event_id(s_seq2, f"{order_id}:TRADE_SELL"),
                        exchange=self.exchange,
                        symbol=self.symbol,
                        seq=s_seq2,
                        ts_exchange=ts_exchange,
                        order_id=order_id,
                        action="TRADE",
                        side="SELL",
                        order_type="LIMIT",
                        price=f"{best_bid_price:.2f}",
                        qty=matched_qty,
                        leaves_qty=leaves_qty,
                        account_id=account_id,
                        broker_id=broker_id,
                        is_synthetic=is_synthetic,
                    )
                )
                b_seq2 = self.next_seq()
                l3_events.append(
                    L3OrderEvent(
                        schema_version="1.0.0",
                        event_id=self.make_event_id(b_seq2, f"{resting.order_id}:TRADE_BUY"),
                        exchange=self.exchange,
                        symbol=self.symbol,
                        seq=b_seq2,
                        ts_exchange=ts_exchange,
                        order_id=resting.order_id,
                        action="TRADE",
                        side="BUY",
                        order_type="LIMIT",
                        price=f"{best_bid_price:.2f}",
                        qty=matched_qty,
                        leaves_qty=resting.leaves_qty,
                        account_id=resting.account_id,
                        broker_id=resting.broker_id,
                        is_synthetic=is_synthetic,
                    )
                )

                if resting.leaves_qty == 0:
                    resting_list.pop(0)
                    self.orders_by_id.pop(resting.order_id, None)
                    if not resting_list:
                        del self.bids[best_bid_price]

            incoming_order.leaves_qty = leaves_qty
            if leaves_qty > 0:
                self.asks.setdefault(price, []).append(incoming_order)
                self.orders_by_id[order_id] = incoming_order

        return l3_events, trades

    def cancel_order(
        self,
        order_id: str,
        ts_exchange: str,
        is_synthetic: bool = True,
    ) -> L3OrderEvent | None:
        resting = self.orders_by_id.pop(order_id, None)
        if not resting:
            return None

        if resting.side == "BUY":
            orders = self.bids.get(resting.price, [])
            self.bids[resting.price] = [o for o in orders if o.order_id != order_id]
            if not self.bids[resting.price]:
                del self.bids[resting.price]
        else:
            orders = self.asks.get(resting.price, [])
            self.asks[resting.price] = [o for o in orders if o.order_id != order_id]
            if not self.asks[resting.price]:
                del self.asks[resting.price]

        cancel_seq = self.next_seq()
        return L3OrderEvent(
            schema_version="1.0.0",
            event_id=self.make_event_id(cancel_seq, f"{order_id}:CANCEL"),
            exchange=self.exchange,
            symbol=self.symbol,
            seq=cancel_seq,
            ts_exchange=ts_exchange,
            order_id=order_id,
            action="CANCEL",
            side=resting.side,
            order_type="LIMIT",
            price=f"{resting.price:.2f}",
            qty=resting.qty,
            leaves_qty=0,
            account_id=resting.account_id,
            broker_id=resting.broker_id,
            gateway_id=resting.gateway_id,
            device_fp=resting.device_fp,
            ip_hash=resting.ip_hash,
            asn=resting.asn,
            api_client_id=resting.api_client_id,
            is_synthetic=is_synthetic,
        )

    def get_l2_snapshot(
        self,
        ts_exchange: str,
        depth_levels: int = 10,
        is_synthetic: bool = True,
    ) -> L2Snapshot:
        # Sort bids descending
        sorted_bids = sorted([p for p in self.bids if self.bids[p]], reverse=True)[:depth_levels]
        bid_levels: list[list[object]] = []
        for p in sorted_bids:
            orders = self.bids[p]
            agg_qty = sum(o.leaves_qty for o in orders)
            bid_levels.append([f"{p:.2f}", agg_qty, len(orders)])

        # Sort asks ascending
        sorted_asks = sorted([p for p in self.asks if self.asks[p]])[:depth_levels]
        ask_levels: list[list[object]] = []
        for p in sorted_asks:
            orders = self.asks[p]
            agg_qty = sum(o.leaves_qty for o in orders)
            ask_levels.append([f"{p:.2f}", agg_qty, len(orders)])

        # Ensure at least depth_levels or min items if needed
        snap_seq = self.next_seq()
        return L2Snapshot(
            schema_version="1.0.0",
            event_id=self.make_event_id(snap_seq, "L2_SNAPSHOT"),
            exchange=self.exchange,
            symbol=self.symbol,
            seq=snap_seq,
            ts_exchange=ts_exchange,
            depth_levels=depth_levels,
            bids=bid_levels,
            asks=ask_levels,
            is_snapshot=True,
            is_synthetic=is_synthetic,
        )
