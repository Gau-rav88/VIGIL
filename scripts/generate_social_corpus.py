from __future__ import annotations

import json
from pathlib import Path


def generate_corpus() -> list[dict]:
    rows: list[dict] = []
    row_id = 1

    symbols = ["ZENITHSME", "ACMESYSTEMS", "NOVAPHARMA", "SOLARIS", "RELIANCE", "TCS", "INFY"]
    aliases = {
        "ZENITHSME": ["$ZENITHSME", "ZENITHSME", "Zenith SME Technologies Ltd", "ZENITH"],
        "ACMESYSTEMS": ["$ACMESYSTEMS", "ACMESYSTEMS", "ACME Industrial Systems", "ACME"],
        "NOVAPHARMA": ["$NOVAPHARMA", "NOVAPHARMA", "Nova Pharmaceuticals Ltd", "NOVA"],
        "SOLARIS": ["$SOLARIS", "SOLARIS", "Solaris Clean Energy Ltd", "SOLAR"],
        "RELIANCE": ["$RELIANCE", "RELIANCE"],
        "TCS": ["$TCS", "TCS"],
        "INFY": ["$INFY", "INFY"],
    }

    # 1. BUY_CALL Templates (120 rows)
    buy_templates = [
        # English
        ("{sym} is breaking out! Everyone buy now before it hits upper circuit!", "en", "BUY_CALL", None, 0.9),
        ("Whale volume spotted in {sym}! All members load up aggressively!", "en", "BUY_CALL", None, 0.8),
        ("Strong buy on {sym} with stoploss nil! Rocket rally starting!", "en", "BUY_CALL", None, 0.85),
        ("{sym} circuit to circuit runner! Accumulate maximum quantity today!", "en", "BUY_CALL", None, 0.8),
        ("MULTIBAGGER ALERT: {sym} accumulator mode ON. Buy immediately!", "en", "BUY_CALL", None, 0.9),
        ("Operator entry confirmed in {sym}! Buy now, 100% gain guaranteed!", "en", "BUY_CALL", None, 0.9),
        ("Take positions in {sym} now! Explosive upper rally expected before close!", "en", "BUY_CALL", None, 0.75),
        ("Massive buying volume detected on {sym}. Strong buy call!", "en", "BUY_CALL", None, 0.8),
        # Hinglish
        ("Bhai log {sym} me circuit lagne wala hai! 100% multibagger guaranteed, buy now!", "hi", "BUY_CALL", None, 0.95),
        ("Jackpot call: {sym} me heavy operator buying! Sabhi members buy karo immediately!", "hi", "BUY_CALL", None, 0.9),
        ("Dhamaka breakout in {sym}! All premium members load now!", "hi", "BUY_CALL", None, 0.85),
        ("Lagao paisa {sym} me, direct upper freeze lagega!", "hi", "BUY_CALL", None, 0.8),
        ("Kharido {sym} daba ke, paisa double banega rocket share!", "hi", "BUY_CALL", None, 0.9),
        ("Bada blast aane wala hai {sym} me! Turant lelo aur hold karo!", "hi", "BUY_CALL", None, 0.85),
        ("Operator buying heavy volume in {sym}! Jaldi kharido miss mat karna!", "hi", "BUY_CALL", None, 0.9),
        ("Udne wala hai {sym}! Sabhi log turant buy karo CMP pe!", "hi", "BUY_CALL", None, 0.85),
    ]

    for sym in symbols:
        alias_list = aliases[sym]
        for tmpl, lang, cta, tp, urg in buy_templates:
            alias = alias_list[row_id % len(alias_list)]
            text = tmpl.replace("{sym}", alias)
            mtype = "CASHTAG" if alias.startswith("$") else ("COMPANY_NAME" if "Ltd" in alias or "Systems" in alias else ("ALIAS" if alias in ("ZEN", "ACME", "NOVA", "SOLAR", "ZENITH") else "SYMBOL"))
            rows.append({
                "id": f"row-{row_id:04d}",
                "text": text,
                "lang": lang,
                "ground_truth": {
                    "ticker": sym,
                    "mention_type": mtype,
                    "cta_class": cta,
                    "target_price": tp,
                    "urgency": urg,
                },
            })
            row_id += 1
            if len(rows) >= 160:
                break
        if len(rows) >= 160:
            break

    # 2. HOLD_PUMP Templates
    hold_templates = [
        # English
        ("Hold tight and don't sell {sym}, this is easily going 5x!", "en", "HOLD_PUMP", None, 0.75),
        ("Don't sell a single share of {sym}! Minimum 100% gain coming!", "en", "HOLD_PUMP", None, 0.8),
        ("Holding strong on {sym}! Diamond hands only, do not exit!", "en", "HOLD_PUMP", None, 0.7),
        ("Strictly hold your positions in {sym}! Massive whale support!", "en", "HOLD_PUMP", None, 0.65),
        ("Dont sell {sym} at current levels, hold tight for upper circuit!", "en", "HOLD_PUMP", None, 0.75),
        ("Hold your shares of {sym}, do not give your supply to operators!", "en", "HOLD_PUMP", None, 0.7),
        # Hinglish
        ("Bechna mat {sym} ka ek bhi share! Pakad ke rakho sabhi!", "hi", "HOLD_PUMP", None, 0.85),
        ("Hold karo {sym} bhai log, bada dhamaka aane wala hai!", "hi", "HOLD_PUMP", None, 0.8),
        ("Pakad ke rakho {sym}, operator exit nahi kiya hai abhi tak!", "hi", "HOLD_PUMP", None, 0.75),
        ("Koi bhi sell mat karo {sym}, hold tight!", "hi", "HOLD_PUMP", None, 0.8),
        ("Hold tight dosto {sym} me, panic sell bilkul mat karo!", "hi", "HOLD_PUMP", None, 0.75),
    ]

    current_count = len(rows)
    for sym in symbols:
        alias_list = aliases[sym]
        for tmpl, lang, cta, tp, urg in hold_templates:
            alias = alias_list[row_id % len(alias_list)]
            text = tmpl.replace("{sym}", alias)
            mtype = "CASHTAG" if alias.startswith("$") else ("COMPANY_NAME" if "Ltd" in alias or "Systems" in alias else ("ALIAS" if alias in ("ZEN", "ACME", "NOVA", "SOLAR", "ZENITH") else "SYMBOL"))
            rows.append({
                "id": f"row-{row_id:04d}",
                "text": text,
                "lang": lang,
                "ground_truth": {
                    "ticker": sym,
                    "mention_type": mtype,
                    "cta_class": cta,
                    "target_price": tp,
                    "urgency": urg,
                },
            })
            row_id += 1
            if len(rows) - current_count >= 110:
                break
        if len(rows) - current_count >= 110:
            break

    # 3. TARGET_PRICE Templates
    target_templates = [
        # English
        ("Big news coming on {sym}! Target 60.00 within 2 days! Miss mat karna!", "en", "TARGET_PRICE", "60.00", 0.85),
        ("{sym} next multibagger target price 120.00 guaranteed by Friday!", "en", "TARGET_PRICE", "120.00", 0.8),
        ("Operator target for {sym} is 85.50! Strong rally building up!", "en", "TARGET_PRICE", "85.50", 0.75),
        ("Urgent alert: {sym} target 45.00 fixed before expiry!", "en", "TARGET_PRICE", "45.00", 0.85),
        ("Institutional target 250.00 on {sym}! Clear all asks!", "en", "TARGET_PRICE", "250.00", 0.7),
        ("Short term target price 55.00 on {sym}! Huge upside!", "en", "TARGET_PRICE", "55.00", 0.75),
        # Hinglish
        ("{sym} me target 60.00 kal tak pakka! Miss mat karna!", "hi", "TARGET_PRICE", "60.00", 0.9),
        ("Operator group leak: {sym} will hit target 75.00 in 3 days!", "hi", "TARGET_PRICE", "75.00", 0.85),
        ("Jackpot call: {sym} target 110.00 pakka! Bada rally aayega!", "hi", "TARGET_PRICE", "110.00", 0.8),
        ("Rocket share {sym}, buy at CMP, target 95.00!", "hi", "TARGET_PRICE", "95.00", 0.8),
        ("Paisa double {sym} me, target 80.00 aayega jaldi!", "hi", "TARGET_PRICE", "80.00", 0.85),
    ]

    current_count = len(rows)
    for sym in symbols:
        alias_list = aliases[sym]
        for tmpl, lang, cta, tp, urg in target_templates:
            alias = alias_list[row_id % len(alias_list)]
            text = tmpl.replace("{sym}", alias)
            mtype = "CASHTAG" if alias.startswith("$") else ("COMPANY_NAME" if "Ltd" in alias or "Systems" in alias else ("ALIAS" if alias in ("ZEN", "ACME", "NOVA", "SOLAR", "ZENITH") else "SYMBOL"))
            rows.append({
                "id": f"row-{row_id:04d}",
                "text": text,
                "lang": lang,
                "ground_truth": {
                    "ticker": sym,
                    "mention_type": mtype,
                    "cta_class": cta,
                    "target_price": tp,
                    "urgency": urg,
                },
            })
            row_id += 1
            if len(rows) - current_count >= 110:
                break
        if len(rows) - current_count >= 110:
            break

    # 4. EXIT_SIGNAL Templates
    exit_templates = [
        # English
        ("Dump {sym} immediately! Operators are dumping all shares!", "en", "EXIT_SIGNAL", None, 0.9),
        ("Exit now from {sym}, book profit before market collapse!", "en", "EXIT_SIGNAL", None, 0.85),
        ("Sell all positions in {sym}! Heavy selling pressure!", "en", "EXIT_SIGNAL", None, 0.8),
        ("Cut position on {sym} now, dump starting fast!", "en", "EXIT_SIGNAL", None, 0.85),
        ("Time to dump {sym}! Take profits off the table!", "en", "EXIT_SIGNAL", None, 0.75),
        ("Massive dump warning on {sym}! Exit your holdings now!", "en", "EXIT_SIGNAL", None, 0.9),
        # Hinglish
        ("Niklo {sym} se turant! Operator dump kar raha hai!", "hi", "EXIT_SIGNAL", None, 0.9),
        ("Becho sabhi {sym}, profit book karo abhi ke abhi!", "hi", "EXIT_SIGNAL", None, 0.85),
        ("Sab bech do {sym} me, exit signal confirmed!", "hi", "EXIT_SIGNAL", None, 0.85),
        ("Jaldi niklo {sym} se, circuit khul gaya hai!", "hi", "EXIT_SIGNAL", None, 0.9),
        ("Bhai log becho {sym}, operator exit ho gaya hai!", "hi", "EXIT_SIGNAL", None, 0.85),
    ]

    current_count = len(rows)
    for sym in symbols:
        alias_list = aliases[sym]
        for tmpl, lang, cta, tp, urg in exit_templates:
            alias = alias_list[row_id % len(alias_list)]
            text = tmpl.replace("{sym}", alias)
            mtype = "CASHTAG" if alias.startswith("$") else ("COMPANY_NAME" if "Ltd" in alias or "Systems" in alias else ("ALIAS" if alias in ("ZEN", "ACME", "NOVA", "SOLAR", "ZENITH") else "SYMBOL"))
            rows.append({
                "id": f"row-{row_id:04d}",
                "text": text,
                "lang": lang,
                "ground_truth": {
                    "ticker": sym,
                    "mention_type": mtype,
                    "cta_class": cta,
                    "target_price": tp,
                    "urgency": urg,
                },
            })
            row_id += 1
            if len(rows) - current_count >= 90:
                break
        if len(rows) - current_count >= 90:
            break

    # 5. COORDINATION_TIMING Templates
    timing_templates = [
        # English
        ("Coordinated buy order at 14:30 sharp on {sym}! Don't miss this rocket!", "en", "COORDINATION_TIMING", None, 0.9),
        ("Everyone place buy orders for {sym} at 11:15 sharp! Clear the asks!", "en", "COORDINATION_TIMING", None, 0.85),
        ("All enter at 10:00 on {sym}! Coordinated buy push!", "en", "COORDINATION_TIMING", None, 0.85),
        ("Enter sharp at 15:00 on {sym}, coordinated entry timing!", "en", "COORDINATION_TIMING", None, 0.8),
        ("Place orders on {sym} sharp at 09:15! Synchronized buy!", "en", "COORDINATION_TIMING", None, 0.85),
        # Hinglish
        ("Bada blast aane wala hai {sym} me at 14:30! Sab milke kharido!", "hi", "COORDINATION_TIMING", None, 0.9),
        ("Paisa double opportunity in {sym}! Entry sharp at 14:30!", "hi", "COORDINATION_TIMING", None, 0.85),
        ("Sab milke kharido {sym} ko 2 baje sharp! Circuit lagega!", "hi", "COORDINATION_TIMING", None, 0.9),
        ("Ek sath enter karo {sym} me at 12:00 sharp! All members ready!", "hi", "COORDINATION_TIMING", None, 0.85),
        ("Timing alert: {sym} me 11:00 baje sharp order lagao!", "hi", "COORDINATION_TIMING", None, 0.85),
    ]

    current_count = len(rows)
    for sym in symbols:
        alias_list = aliases[sym]
        for tmpl, lang, cta, tp, urg in timing_templates:
            alias = alias_list[row_id % len(alias_list)]
            text = tmpl.replace("{sym}", alias)
            mtype = "CASHTAG" if alias.startswith("$") else ("COMPANY_NAME" if "Ltd" in alias or "Systems" in alias else ("ALIAS" if alias in ("ZEN", "ACME", "NOVA", "SOLAR", "ZENITH") else "SYMBOL"))
            rows.append({
                "id": f"row-{row_id:04d}",
                "text": text,
                "lang": lang,
                "ground_truth": {
                    "ticker": sym,
                    "mention_type": mtype,
                    "cta_class": cta,
                    "target_price": tp,
                    "urgency": urg,
                },
            })
            row_id += 1
            if len(rows) - current_count >= 90:
                break
        if len(rows) - current_count >= 90:
            break

    # 6. NEUTRAL Templates
    neutral_templates = [
        # English
        ("Discussion on {sym} quarterly financial results and operating margin.", "en", "NEUTRAL", None, 0.2),
        ("What are your thoughts on {sym} performance this fiscal year?", "en", "NEUTRAL", None, 0.15),
        ("Checking the daily chart of {sym}, consolidating near support.", "en", "NEUTRAL", None, 0.2),
        ("Annual report for {sym} published today on exchange portal.", "en", "NEUTRAL", None, 0.1),
        ("Institutional holding in {sym} remained flat over last quarter.", "en", "NEUTRAL", None, 0.15),
        ("General discussion regarding macro inflation trends and interest rates.", "en", "NEUTRAL", None, 0.1),
        ("Market looking quiet today across index heavyweights.", "en", "NEUTRAL", None, 0.1),
        ("Global cues mixed today with asian indices trading in red.", "en", "NEUTRAL", None, 0.1),
        # Hinglish
        ("{sym} ke quarterly results kaise rahe is baar?", "hi", "NEUTRAL", None, 0.2),
        ("Aaj market thoda rangebound chal raha hai, wait and watch mode.", "hi", "NEUTRAL", None, 0.15),
        ("Koi {sym} ka balance sheet review kar raha hai kya?", "hi", "NEUTRAL", None, 0.15),
        ("Dosto aaj nifty sideways hai, koi aggressive setup nahi dikh raha.", "hi", "NEUTRAL", None, 0.1),
        ("Kafi time baad market me thoda normal volume dekhne ko mila.", "hi", "NEUTRAL", None, 0.1),
    ]

    current_count = len(rows)
    for sym in symbols:
        alias_list = aliases[sym]
        for tmpl, lang, cta, tp, urg in neutral_templates:
            if "{sym}" in tmpl:
                alias = alias_list[row_id % len(alias_list)]
                text = tmpl.replace("{sym}", alias)
                mtype = "CASHTAG" if alias.startswith("$") else ("COMPANY_NAME" if "Ltd" in alias or "Systems" in alias else ("ALIAS" if alias in ("ZEN", "ACME", "NOVA", "SOLAR", "ZENITH") else "SYMBOL"))
                target_sym = sym
            else:
                text = tmpl
                mtype = None
                target_sym = None

            rows.append({
                "id": f"row-{row_id:04d}",
                "text": text,
                "lang": lang,
                "ground_truth": {
                    "ticker": target_sym,
                    "mention_type": mtype,
                    "cta_class": cta,
                    "target_price": tp,
                    "urgency": urg,
                },
            })
            row_id += 1
            if len(rows) - current_count >= 130:
                break
        if len(rows) - current_count >= 130:
            break

    return rows


def main() -> None:
    corpus = generate_corpus()
    out_dir = Path(__file__).resolve().parents[1] / "datasets" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "social_labeled_v1.draft.jsonl"

    with open(out_file, "w", encoding="utf-8") as f:
        for row in corpus:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Generated {len(corpus)} labeled rows in {out_file}")


if __name__ == "__main__":
    main()
