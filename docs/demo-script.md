# Project VIGIL: 10-Minute Investigator Rehearsal Demo Script

**Scenario:** Automated Detection, Cross-Modal Attribution & Cryptographic Dossier Signing of a Coordinated SME Pump-and-Dump Ring  
**Target Security:** `ZENITHSME` (Micro-cap Equity)  
**Attack Vector:** Telegram/Discord Cashtag Social Hype Blitz leading Synchronized Order Layering & Coordinated Syndicate Dump  
**Total Running Time:** 10 Minutes  

---

## Roles & Personas

- **Persona A (Investigator):** Operational surveillance analyst tasked with triaging real-time alerts, inspecting cross-modal lag peaks, expanding entity relationship graphs, and submitting case directives.
- **Persona B (Compliance Officer):** Supervisory reviewer with forensic signing authorization, KYC unmasking permissions (Guardrail G-3), and dossier publication authority (Guardrail G-1).

---

## Rehearsal Timeline

```mermaid
journey
    title 10-Minute VIGIL Forensic Investigation Journey
    section Ingestion & Alerting (00:00 - 02:00)
      Boot Simulation: 5: Investigator
      Real-Time Telemetry: 5: Investigator
      Fast-Path Hype Burst: 5: Investigator
    section Cross-Modal Triage (02:00 - 04:30)
      Inspect Case Dossier: 5: Investigator
      XCorr Alignment (150s lag): 5: Investigator
      MRS Escalation (4.6 -> 68.0): 5: Investigator
    section Graph Attribution (04:30 - 07:00)
      Explore 20-Node Ring: 5: Investigator
      Inspect Evidence Overlay: 5: Investigator
      Submit Directives: 5: Investigator
    section Compliance & Signing (07:00 - 10:00)
      Officer Dual Review: 5: Officer
      KYC Unmasking Audit: 5: Officer
      Ed25519 Cryptographic Sign: 5: Officer
      Offline CLI Verification: 5: Officer
```

---

### Phase 1: Injection & Real-Time Alerting (00:00 – 02:00)

1. **Start Scenario:**
   Navigate to `/simulator` in the UI or launch via CLI:
   ```bash
   make scenario ID=pump_dump_ring_01 SPEED=10 SEED=42
   ```
2. **Open Live Monitor (`/live`):**
   - Point out the real-time order stream for `ZENITHSME`.
   - Observe incoming social hype alerts on Telegram/Discord channels.
   - Note the **Hype Burst anomaly**: Social hype score spikes past `70.0/100` within 30 seconds.
   - Note the subsequent market reaction: Volume spike ($z > 5.0$) and price jump follow within 2.5 minutes.

---

### Phase 2: Cross-Modal Alignment & Case Triage (02:00 – 04:30)

1. **Navigate to Cases Workbench (`/cases`):**
   - Filter by status `PENDING_REVIEW` or symbol `ZENITHSME`.
   - Select newly generated case (e.g. `CASE-2026-ZENITHSME-01`).
2. **Examine Alignment & MRS Dashboard (`/cases/[caseId]`):**
   - **Cross-Modal Normalized Cross-Correlation:** Point out the prominent xcorr peak ($\rho = 0.84$) at lag **$\tau = +150$s** ($p < 0.001$). Highlight that social hype strictly precedes market trading volume.
   - **Manipulation Risk Score (MRS):** Point out the dramatic escalation from baseline baseline score **4.65/100** to **68.05/100** at dump onset ($14.6\times$ surge).
   - Point out the auto-generated case narrative citing evidence IDs (`EV-TRADE-*`, `EV-SOC-*`).

---

### Phase 3: Graph Attribution & Syndicate Ring (04:30 – 07:00)

1. **Launch Graph Explorer (`/cases/[caseId]/graph`):**
   - Show Cytoscape interactive topology: 20 trader nodes clustered tightly around shared hardware fingerprints (`SHARED_DEVICE`), circular wash cycles (`CIRCULAR_CYCLE`), and synchronized order subnets.
   - Highlight **Ring Score:** Cluster ring score calculates to **0.988 / 1.000**, with 100% recall of injected ring participants.
   - Point out **Guardrail G-2 compliance**: Only links with confidence $\ge 0.60$ are promoted to findings.
2. **Investigator Actions:**
   - Demonstrate adding an investigator directive (e.g. "Request broker execution logs for Broker BRK-01").
   - Click **Submit for Compliance Review**.

---

### Phase 4: Compliance Review, KYC Reveal & Cryptographic Verification (07:00 – 10:00)

1. **Switch Persona to Compliance Officer:**
   - Authenticate with `role: compliance_officer`.
   - Open `/cases/[caseId]`. Observe that the compliance review panel is now active.
2. **Execute KYC Unmasking (Guardrail G-3):**
   - Click on ringleader node `ACC-BUY-0012-TOKENB64`.
   - Click **Reveal Identity**.
   - Input mandatory legal justification: `"Court warrant W-2026-991 SEBI investigation"`.
   - Show unmasked details (Full Name, PAN hash, Broker ID) and emphasize that an immutable audit log entry was written to the PostgreSQL ledger.
3. **Approve & Publish Case (Guardrail G-1):**
   - Select verdict: **APPROVED**.
   - Case transitions from `PENDING_REVIEW` to `PUBLISHED`.
   - System compiles final signed forensic dossier with ReportLab PDF and cryptographic bundle.
4. **Download & Verify Evidence Bundle Offline:**
   - Download `bundle.zip` from `/dossiers/[dossierId]`.
   - Run the air-gapped forensic verifier in the terminal:
     ```bash
     make verify BUNDLE=reports/sample_bundle/bundle.zip
     ```
   - **Result:** 6/6 verification steps pass green:
     1. Pydantic schema validation: Valid
     2. SHA-256 byte integrity: 100% match
     3. RFC 6962 binary Merkle root recomputation: Match
     4. Cryptographic ledger chain continuity: Valid
     5. RFC 8785 canonical JSON digest & Ed25519 signature: Verified
     6. Compliance approval audit: Approved
5. **Tamper Detection Demonstration:**
   - Flip a single byte in the evidence archive:
     ```bash
     printf '\x00' | dd of=/tmp/tampered.zip bs=1 seek=200 count=1 conv=notrunc
     uv run vigil-verify /tmp/tampered.zip --pubkey keys/dev_ed25519.pub
     ```
   - **Result:** Verifier immediately exits non-zero with `HASH_MISMATCH` / `INTEGRITY_TAMPER_DETECTED`.
