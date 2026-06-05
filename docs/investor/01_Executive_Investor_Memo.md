# Solarica — Executive Investor Memo

**The Execution Intelligence Platform for utility‑scale renewable energy**

*Confidential — Draft v1*

---

## 1. One‑line

Solarica turns the engineering drawings of a solar project into a **live, verified execution model** — the single source of truth that today does not exist on any solar construction site.

## 2. What is Solarica?

Solarica is an **Execution Intelligence Platform**. It ingests the CAD/PDF engineering package of a utility‑scale renewable project and produces a structured **Execution Model** — every block, row, tracker, pier, string, panel and device — and then keeps that model in sync with what is actually happening in the field: progress, tests, materials, defects, safety, payments and changes.

It is **not** a project‑management tool, a document store, or a BIM viewer. Those describe *intent*. Solarica describes *reality* — what has actually been installed, verified, paid for, and is safe — measured against the engineering intent, continuously.

We call the output the **Execution Twin**: a trusted data layer that sits between engineering and the field.

## 3. The problem

A 100–300 MW solar project is built from tens of thousands of near‑identical components installed by hundreds of subcontractors over 12–24 months. The information that governs this work flows like this today:

> Engineering drawings → PDF → Excel → WhatsApp → meetings → manual reports → decisions

Every hand‑off loses fidelity. The consequences are not cosmetic:

- **No single source of truth.** Engineering says one thing, the field tracker says another, the payment sheet a third. Nobody can answer "what is *actually* done and verified?" without a meeting.
- **Progress is self‑reported.** Contractor claims drive payment, with little independent, evidence‑based verification → over‑billing and disputes.
- **Engineering revisions are silent.** A revised drawing changes string numbering or pier counts; the field keeps building to the old rev. Rework is discovered weeks later.
- **QA and commissioning are paper.** IV‑curve, Megger, polarity, continuity and grounding tests live in spreadsheets disconnected from the asset they certify.
- **Safety/structural defects are invisible at scale.** A tracker with missing bolts or fasteners is a safety, structural, financial and schedule risk — found by chance, not by system.
- **Blockers compound.** Access, materials, and dependency blockers are tracked in chat, not modeled.

These look like separate problems. They are symptoms of one root cause:

> **Renewable‑energy construction has no trusted execution data layer.**

## 4. Why now

- **Scale has outrun the tooling.** Project sizes 5–10×'d in a decade; the coordination tooling did not. Excel + WhatsApp does not scale to 25,000 piers and 6,000 strings.
- **Capital discipline.** Higher rates mean owners and EPCs are under pressure to prove progress, control payments, and de‑risk schedule — exactly what an execution layer enables.
- **The drawings are finally machine‑readable.** Modern electrical/structural packages ship as vector CAD/PDF with named layers. The semantic content (rows, trackers, strings, piers, colors) is *in the file* — extractable without manual digitization, as we have proven.
- **Field connectivity + offline.** Phones/tablets are ubiquitous on site; offline‑first apps make capture reliable even with no signal.

## 5. What we have already built and proven (the hard part)

The defensible core — and the part everyone assumes is impossible — is turning a raw engineering package into an exact execution model **automatically**. This is built and demonstrated on real projects:

**EPL — Execution Preparation Layer (working today):**
- **CAD/PDF parsing without rasterization.** We read the vector geometry and OCG layer structure directly (PyMuPDF), preserving every layer, color, symbol and label.
- **Physical row + tracker detection.** Automatically reconstructs the site's physical rows/trackers and their geometry from the drawing grid.
- **Pier extraction at BOM accuracy.** On a real construction set we extracted **24,130 piers matching the bill of materials exactly**, with per‑row numbering.
- **String detection at 100% on the reference project.** Using three site invariants (each string = 44 panels, one color, one green‑start/red‑end marker) we deterministically detect **288 strings, every one exactly 44 panels, 100% named and validated** — including cross‑row strings — straight from the panel layout. No manual tracing.
- **Numbering validation + cross‑row detection.** We cross‑check the drawing's own string numbers and surface inconsistencies.
- **Field‑ready visualization.** Grid + WebGL map (25k+ piers) with status tracking, and an **offline‑first** field app (local cache, optimistic writes, auto‑sync) for sites with no connectivity.

This proves the thesis: **the engineering package can be turned into a structured, verifiable execution model automatically and exactly.** Everything else in the platform is built on top of this layer.

## 6. The platform (vision → roadmap)

The execution model becomes the spine for a family of intelligence modules. EPL is live; the modules below are the productization roadmap, each addressing a concrete, observed site pain:

| Module | What it does | Status |
|---|---|---|
| **EPL** | Drawings → execution model (rows, trackers, piers, strings, panels, devices) | **Built / proven** |
| **Verified Progress** | Definition‑of‑Done per component, evidence capture, % complete that is *measured*, not claimed | Design → build |
| **Payment Intelligence** | Contractor claims matched to verified progress; approval workflow; payment eligibility | Roadmap |
| **Test Intelligence** | IV‑curve, Megger, polarity, continuity, grounding, commissioning — tied to the asset | Roadmap |
| **Safety & Structural Compliance** | Missing‑fastener / structural‑defect detection and escalation; safety risk register | Roadmap |
| **Inventory Intelligence** | Material receipt → installation reconciliation | Roadmap |
| **Change Impact Intelligence** | Drawing revision → automatic impact on built/claimed scope | Roadmap |
| **Blocker Intelligence** | Model access/material/dependency blockers and their schedule impact | Roadmap |
| **Operations / Solarica Case™** | Hand‑over twin for O&M; defect cases with full execution provenance | Roadmap |

## 7. Why Solarica is different

- **It starts from the drawing, not the spreadsheet.** Competitors digitize the field manually or wrap PM/QA forms around it. We generate the model from the source of truth (engineering) and verify the field against it.
- **Exact, not approximate.** Our detection is deterministic and BOM‑exact (24,130 piers; 288/288 strings). Investors and owners can trust the numbers.
- **Execution truth, not document management.** The unit of value is a verified component, not a stored file.
- **Offline‑native.** Built for real field conditions from day one.

## 8. Why this can become large

Every utility‑scale renewable project — globally, every year — has progress disputes, payment disputes, silent revisions, QA gaps, blockers, and no single source of truth. The pain is universal and recurring, not project‑specific.

- **Wedge:** EPL (drawings → verified model) — the painful, defensible entry point.
- **Land‑and‑expand:** add Verified Progress → Payment → Test → Safety on the same model.
- **Beyond solar:** the same execution‑twin pattern applies to BESS, wind, transmission, and broadly to any large, repetitive infrastructure build.

The category is not "solar construction software." It is the **trusted execution data layer for infrastructure delivery.**

## 9. Moat

- **Drawing‑to‑model extraction IP** (layer/semantic parsing, deterministic string/pier/row detection) — hard to replicate, improves with every project ingested.
- **Data network effect:** each project teaches the parser new drawing conventions; the learning layer generalizes across EPCs and design houses.
- **Workflow lock‑in:** once payment and progress run on Solarica, it becomes the system of record.
- **Provenance:** every verified fact carries its evidence chain — the basis for the O&M hand‑over twin (Solarica Case™).

## 10. Proof point — BHK case study (headline)

On the BHK reference project, from the engineering package alone, Solarica automatically produced: 107 physical rows, the tracker/pier geometry, and **288 strings at 100% accuracy (44 panels each, fully numbered, cross‑row strings resolved)** — work that is otherwise done by hand over days and is error‑prone. (Full case study in the Product Spec and Deck.)

## 11. The ask

[Placeholder — to be set with founder: round size, use of funds, milestones.]
Indicative use of funds: productize Verified Progress + Payment Intelligence on the existing EPL core, ingest N additional reference projects to harden the parser, and land 2–3 design‑partner EPCs.

---

*Appendices (to follow): technical architecture, security model, detailed BHK case study, competitive landscape, financial model.*
