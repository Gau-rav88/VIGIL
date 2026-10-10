from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def render_dossier_pdf(dossier: dict[str, Any], output_path: str | Path | None = None) -> bytes:
    """
    Renders a comprehensive SEBI/SEC-grade forensic evidence PDF dossier
    with >= 6 distinct forensic sections, manifest hash, and QR code.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf if output_path is None else str(output_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DossierTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0f172a"),
    )
    h2_style = ParagraphStyle(
        "DossierH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1e293b"),
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "DossierBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
    )
    meta_style = ParagraphStyle(
        "DossierMeta",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#475569"),
    )

    story: list[Any] = []

    # Header / Title Block
    story.append(Paragraph("PROJECT VIGIL — FORENSIC EVIDENCE DOSSIER", title_style))
    story.append(Paragraph(f"Case ID: {dossier.get('case_id')} | Dossier ID: {dossier.get('dossier_id')} | Version: {dossier.get('version', 1)}", meta_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#cbd5e1")))
    story.append(Spacer(1, 10))

    # --- SECTION 1: EXECUTIVE SUMMARY ---
    story.append(Paragraph("1. Executive Summary & Forensic Narrative", h2_style))
    exec_summary = dossier.get("executive_summary", {})
    text = exec_summary.get("text", "Autonomous multi-agent investigation confirmed coordinated cross-modal market manipulation.")
    story.append(Paragraph(text, body_style))
    citations = exec_summary.get("citations", [])
    if citations:
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"<b>Key Citations:</b> {', '.join(citations)}", meta_style))
    story.append(Spacer(1, 10))

    # --- SECTION 2: SUBJECT & TIMELINE ---
    story.append(Paragraph("2. Subject Instrument & Chronological Timeline", h2_style))
    subj = dossier.get("subject", {})
    subj_data = [
        ["Target Symbol", subj.get("symbol", "N/A"), "Exchange", subj.get("exchange", "N/A")],
        ["Window Start", subj.get("window_start", "N/A"), "Window End", subj.get("window_end", "N/A")],
        ["Manipulation Types", ", ".join(subj.get("manipulation_types", ["PUMP_AND_DUMP"])), "Jurisdiction", dossier.get("jurisdiction", "SEBI_IN")],
    ]
    subj_table = Table(subj_data, colWidths=[100, 160, 90, 190])
    subj_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
    ]))
    story.append(subj_table)
    story.append(Spacer(1, 8))

    timeline = dossier.get("timeline", [])
    if timeline:
        t_data = [["Timestamp (UTC)", "Track", "Description", "Evidence Citation"]]
        for t in timeline[:6]:
            t_data.append([
                t.get("ts", "")[:19],
                t.get("track", "SYSTEM"),
                t.get("description", "")[:60],
                ", ".join(t.get("evidence_ids", []))[:30],
            ])
        t_table = Table(t_data, colWidths=[100, 60, 240, 140])
        t_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        story.append(t_table)
    story.append(Spacer(1, 10))

    # --- SECTION 3: MARKET EVIDENCE ---
    story.append(Paragraph("3. Quantitative Market Evidence", h2_style))
    mkt = dossier.get("market_evidence", {})
    mkt_data = [
        ["Total Volume", f"{mkt.get('total_volume', 0):,}", "Suspect Volume", f"{mkt.get('suspect_volume', 0):,}"],
        ["Suspect Ratio", f"{mkt.get('suspect_volume_ratio', 0.0) * 100:.1f}%", "Price Movement", f"{mkt.get('price_move_pct', 0.0):+.2f}%"],
    ]
    mkt_table = Table(mkt_data, colWidths=[100, 160, 100, 180])
    mkt_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(mkt_table)
    story.append(Spacer(1, 10))

    # --- SECTION 4: SOCIAL INTELLIGENCE ---
    story.append(Paragraph("4. Social Intelligence & Cross-Modal Alignment", h2_style))
    soc = dossier.get("social_evidence", {})
    align = soc.get("alignment", {}) or {}
    soc_data = [
        ["Channels Monitored", ", ".join(soc.get("channels", ["Telegram", "X"])), "Message Count", str(soc.get("message_count", 0))],
        ["Hype Peak Score", f"{soc.get('hype_peak', 0.0):.1f} / 100", "Coordinated Campaigns", str(soc.get("near_duplicate_campaigns", 0))],
        ["Alignment Lag", f"{align.get('best_lag_s', 0.0):.1f} sec", "Peak Correlation (XCorr)", f"{align.get('xcorr_peak', 0.0):.3f}"],
    ]
    soc_table = Table(soc_data, colWidths=[110, 150, 110, 170])
    soc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(soc_table)
    story.append(Spacer(1, 10))

    # --- SECTION 5: ATTRIBUTION & RINGS ---
    story.append(Paragraph("5. Cyber-Forensics Graph Attribution & Entity Resolution", h2_style))
    attr = dossier.get("attribution", {})
    rings = attr.get("rings", [])
    if rings:
        r_data = [["Ring ID", "Score", "Accounts Count", "Coordination Methods", "Cycles"]]
        for r in rings:
            r_data.append([
                r.get("ring_id", ""),
                f"{r.get('ring_score', 0.0):.3f}",
                str(len(r.get("accounts", []))),
                ", ".join(r.get("methods", []))[:45],
                str(r.get("cycle_count", 0)),
            ])
        r_table = Table(r_data, colWidths=[80, 50, 80, 260, 70])
        r_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        story.append(r_table)
    story.append(Spacer(1, 10))

    # --- SECTION 6: REGULATORY VIOLATIONS ---
    story.append(Paragraph("6. Regulatory Violations & Legal Statutory Mapping", h2_style))
    clauses = dossier.get("violated_clauses", [])
    if clauses:
        c_data = [["Regime", "Clause ID", "Statutory Title", "Legal Review"]]
        for c in clauses:
            c_data.append([
                c.get("regime", ""),
                c.get("clause_id", ""),
                c.get("title", "")[:60],
                "REQUIRED" if c.get("legal_review_required") else "NONE",
            ])
        c_table = Table(c_data, colWidths=[60, 90, 310, 80])
        c_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]))
        story.append(c_table)
    story.append(Spacer(1, 10))

    # --- SECTION 7: CERTIFICATE OF INTEGRITY & QR CODE ---
    story.append(Paragraph("7. Cryptographic Certificate of Integrity & Verification Anchor", h2_style))
    sig = dossier.get("signature", {})
    merkle_root = dossier.get("merkle_root", "N/A")
    manifest_items = dossier.get("evidence_manifest", [])
    manifest_hash = sig.get("digest_sha256", "0" * 64)

    # Generate QR Code linking to verification endpoint
    qr_url = f"http://localhost:3000/verify?dossier={dossier.get('dossier_id')}&root={merkle_root}"
    qr_img = qrcode.make(qr_url, box_size=3, border=1)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    qr_flowable = Image(qr_buf, width=70, height=70)

    cert_text = (
        f"<b>Signature Algorithm:</b> {sig.get('alg', 'Ed25519')}<br/>"
        f"<b>Key ID:</b> {sig.get('key_id', 'dev-2026-01')}<br/>"
        f"<b>Canonicalization:</b> {sig.get('canonicalization', 'RFC8785-JCS')}<br/>"
        f"<b>Manifest Digest (SHA-256):</b> {manifest_hash}<br/>"
        f"<b>Merkle Root:</b> {merkle_root}<br/>"
        f"<b>Evidence Items Count:</b> {len(manifest_items)}<br/>"
        f"<b>Signature:</b> {sig.get('value_b64', '')[:32]}...<br/>"
    )

    cert_table = Table([[Paragraph(cert_text, meta_style), qr_flowable]], colWidths=[460, 80])
    cert_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
    ]))
    story.append(cert_table)

    doc.build(story)

    if output_path is not None:
        return Path(output_path).read_bytes()
    return buf.getvalue()
