# App Review Weekly Pulse — System Architecture

> **Product:** Groww Mutual Fund App  
> **Goal:** Convert recent Google Play Store reviews into a one-page weekly product feedback pulse  
> **LLM Provider:** Groq  
> **Date:** 2026-03-10

---

## 1. System Overview

The **App Review Weekly Pulse** system is an end-to-end AI-powered pipeline that ingests public Google Play Store reviews for the Groww Mutual Fund app, distils them into thematic insights, and produces a concise one-page weekly pulse along with an email draft — all consumable by product leadership in under two minutes.

### Core Capabilities

| Capability | Description |
|---|---|
| **Review Ingestion** | Fetch reviews via **Play Store Review Collector** (auto-scrape) or Manual CSV upload; filtering for the last 8–12 weeks |
| **Public Data Only** | Only publicly accessible review data is collected (rating, text, title, date). No login or private data access used. |
| **PII Scrubbing** | Strip usernames, emails, device IDs, and any personally identifiable information |
| **Theme Extraction** | Use Groq LLM to cluster reviews into ≤ 5 dominant themes |
| **Insight Generation** | Surface real user quotes and derive 3 actionable product ideas |
| **Weekly Pulse** | Render a ≤ 250-word, leadership-scannable one-page report |
| **Email Draft & Delivery** | Auto-generate a ready-to-send email and optionally deliver via SMTP |
| **Quality Preprocessing** | Remove low-signal reviews (e.g., "nice", "ok") and sample to ≤ 300 reviews for efficiency |
| **Web Interface** | Lightweight UI for upload, trigger, view, and email generation |

### Pipeline Summary

- **Phase 1 → Review Collection**
- **Phase 2 → Review Cleaning**
- **Phase 3 → Theme Analysis (Groq)**
- **Phase 4 → Insight Generation (Groq)**
- **Phase 5 → Weekly Pulse Generation (Gemini)**
- **Phase 6 → Email Draft & Delivery (Optional)**
- **Phase 7 → Web UI Layer**

### Design Principles

- **Privacy-first** — No PII is stored or forwarded to the LLM.
- **Deterministic pipeline** — Each phase produces a well-defined intermediate artifact that can be inspected independently.
- **Idempotent runs** — Re-running the pipeline on the same data produces the same output.
- **Separation of concerns** — LLM calls are isolated behind a dedicated AI service layer.
- **Leadership-ready output** — Every artifact is designed for quick scanning, not deep reading.

---

## 2. High-Level Architecture

### 2.1 Simplified Execution Flow
```text
CSV Upload / Scrape
        ↓
Review Cleaning + PII Removal
        ↓
Theme Discovery
        ↓
Review Classification
        ↓
Quote Selection
        ↓
Action Generation
        ↓
Weekly Pulse Generation
        ↓
Email Draft & Delivery
```

```text
┌──────────────────────────────────────────────────────────────────────┐
│                        WEB INTERFACE (UI Layer)                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌───────────────┐  │
│  │   Upload /  │  │  Trigger   │  │   View     │  │  Email Draft  │  │
│  │   Fetch     │  │  Pipeline  │  │   Report   │  │   Trigger     │  │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └──────┬────────┘  │
└────────┼───────────────┼───────────────┼────────────────┼────────────┘
         │               │               │                │
         ▼               ▼               ▼                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      API / ORCHESTRATION LAYER                       │
│                                                                      │
│   Receives requests from UI → coordinates pipeline phases →         │
│   returns results to UI                                              │
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       PROCESSING PIPELINE                            │
│                                                                      │
│  ┌─────────────────────────┐                                         │
│  │   Google Play Store     │                                         │
│  └───────────┬─────────────┘                                         │
│              │                                                       │
│              ▼                                                       │
│  ┌─────────────────────────┐      ┌──────────────┐                   │
│  │ Play Store Collector    │◀─────┤ CSV Upload   │                   │
│  │ (google-play-scraper)   │      │ (Fallback)   │                   │
│  └───────────┬─────────────┘      └──────────────┘                   │
│              │                                                       │
│              ▼                                                       │
│  ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐        │
│  │Phase 1│▶│Phase 2│▶│Phase 3│▶│Phase 4│▶│Phase 5│▶│Phase 6│        │
│  │Collect│ │ Clean │ │ Theme │ │Insight│ │ Pulse │ │ Email+ │        │
│  └───────┘ └───────┘ └───────┘ └───────┘ └───────┘ └───────┘        │
│       │        │         │         │         │         │            │
│       ▼        ▼         ▼         ▼         ▼         ▼            │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │               AI SERVICE LAYER (Groq + Gemini)                  ││
│  │  Groq: Theme Discovery · Classification · Insight Generation     ││
│  │  Gemini: Pulse Composition · Email Drafting                      ││
│  └──────────────────────────────────────────────────────────────────┘│
└──────────┬───────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER                                │
│                                                                      │
│   Raw Reviews · Cleaned Reviews · Theme Maps · Pulse Reports ·       │
│   Email Drafts · Run Metadata                                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Model Clarification

**Review Record**
```json
{
  "reviewId": "gp:a1b2c3d4",
  "rating": 4,
  "text": "The app is great, but fund withdrawal takes too long.",
  "date": "2026-03-08T10:15:30Z"
}
```

**Themes**
```json
{
  "id": "theme_001",
  "label": "Withdrawal Delays",
  "description": "Users are complaining about the time it takes for funds to reflect in bank accounts."
}
```

**Grouped Reviews** (Theme Map Output)
```json
{
  "theme_001": [
    {
      "reviewId": "gp:a1b2c3d4",
      "rating": 4,
      "text": "The app is great, but fund withdrawal takes too long.",
      "date": "2026-03-08T10:15:30Z"
    }
  ]
}
```

**Weekly Pulse Output**
```json
{
  "date": "2026-03-10",
  "review_count": 300,
  "markdown_content": "# Groww Mutual Fund...\n..."
}
```

**Email Draft**
```json
{
  "subject": "[Weekly Pulse] Groww Mutual Fund Reviews — Week of 2026-03-10",
  "body": "Hi Team,\n\n..."
}
```

---

## 4. Phase-wise Architecture

### Phase 1 — Review Collection
**Goal:** Collect Google Play reviews.

**Responsibilities:**
- Fetch reviews using **google-play-scraper**
- Allow fallback **CSV upload via Web UI**
- Extract only required fields: `reviewId`, `rating`, `review_text`, `review_date`
- Store raw reviews

**Output artifact:** `storage/runs/{run_id}/input/raw_reviews.json`

**Flow:**
```text
Google Play Store ──▶ Play Store Collector (google-play-scraper) ──▶ Raw Reviews Dataset
```

**LLM Usage:** None

---

### Phase 2 — Review Cleaning & Sampling
**Goal:** Prepare high-quality data for analysis.

**Responsibilities:**
- Validate schema
- Filter reviews from the last **8–12 weeks**
- Remove PII
- Remove **low-signal reviews** (e.g., "nice", "ok", "bad app")
- Deduplicate reviews
- Sample **maximum 300 reviews**

**Output artifact:** `storage/runs/{run_id}/cleaned/reviews_cleaned.json`

**Flow:**
```text
Raw Reviews ──▶ Schema Validation ──▶ Date Filtering ──▶ PII Scrubbing ──▶ Low-Signal Filtering ──▶ Sampling (≤300) ──▶ Clean Review Dataset
```

**LLM Usage:** None

---

### Phase 3 — Theme Analysis (Groq LLM)
**Goal:** Identify major themes across user feedback.

**Responsibilities:**
- **Step 1 — Theme Discovery:** Sample 100–150 reviews, use Groq LLM to generate **3–5 dominant themes**
- **Step 2 — Review Classification:** Assign each review to exactly **one theme**

**Output artifact:** `storage/runs/{run_id}/analysis/theme_map.json`

**Flow:**
```text
Clean Reviews ──▶ Groq LLM ──▶ Theme Discovery ──▶ Theme Classification ──▶ Theme Map
```

---

### Phase 4 — Insight Generation
**Goal:** Extract meaningful insights from themes.

**Responsibilities:**
- Select **1–2 representative user quotes per theme**
- Generate **3 product action ideas**

**Output artifact:** `storage/runs/{run_id}/analysis/insights.json`

**Flow:**
```text
Theme Map ──▶ Groq LLM ──▶ Quote Selection ──▶ Action Generation
```

---

### Phase 5 — Weekly Pulse Generation
**Goal:** Generate the final leadership-ready report.

**Responsibilities:**
- Generate a **≤250 word weekly pulse**
- Format report in **Markdown**
- Ensure the structure contains: Top Themes, User Quotes, Product Action Ideas

**Output artifact:** `storage/runs/{run_id}/output/weekly_pulse.md`

**Flow:**
```text
Themes + Quotes + Actions ──▶ Gemini LLM ──▶ Weekly Pulse Document
```

---

### Phase 6 — Email Draft & Delivery
**Goal:** Prepare and optionally deliver the internal email containing the weekly pulse.

**Execution Modes:**

**Mode 1 — Dry Run (Default)**
- Generate the email draft using the Weekly Pulse via Gemini LLM.
- Save the output locally as:
  - `email_draft.md`
  - `email_draft.txt`
- Do **not connect to any SMTP server**.
- Used for safe testing and previewing the generated email.

**Mode 2 — Send Mode**
- Activated when the CLI flag `--send` is provided and SMTP credentials are available.
- The system will:
  - Generate the email draft.
  - Connect to the configured SMTP server.
  - Send the email automatically to the configured recipient list.

**Responsibilities:**
- Generate subject line.
- Generate professional internal email body.
- Embed the weekly pulse inside the email.
- Handle SMTP connection and secure transmission.

**SMTP Email Delivery**
The system uses Python's `smtplib` library to send emails. Configuration is loaded from environment variables:
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_TLS`
- `EMAIL_TO`

*Security Rule:* The SMTP password must **never be logged or stored in logs or files**. It must only be loaded from `.env` at runtime.

**Output artifact:** `storage/runs/{run_id}/output/email_draft.md`

**Flow:**
```text
Weekly Pulse
      ↓
Email Draft Generation
      ↓
If Dry Run → Save Draft Locally
If Send Mode → Connect SMTP → Send Email
```

---

### Phase 7 — Web UI Layer
**Goal:** Provide a simple interface to run and view the pipeline.

**Responsibilities:**
Allow users to:
- Fetch reviews automatically
- Upload CSV fallback
- Trigger pipeline execution
- View weekly pulse
- Generate email draft
- View run history

**UI Components should include:**
- Review ingestion panel
- Pipeline control panel
- Report viewer
- Run history table

**Flow:**
```text
User ──▶ Web UI ──▶ API / Orchestrator ──▶ Pipeline Phases
```

---

## 5. Data Flow Pipeline

```text
                    ┌───────────────────────────────┐
                    │      Google Play Store        │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ Phase 1: Review Collection    │
                    │ (google-play-scraper / CSV)   │
                    └───────────────┬───────────────┘
                                    │
                           Raw Reviews Dataset
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ Phase 2: Review Cleaning      │
                    │ • Validate & Date Filter      │
                    │ • Scrub PII & Low-Signal      │
                    │ • Deduplicate & Sample (300)  │
                    └───────────────┬───────────────┘
                                    │
                            Clean Review Set
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ Phase 3: Theme Analysis       │
                    │ • Theme Discovery (LLM)       │
                    │ • Review Classification (LLM) │
                    └───────────────┬───────────────┘
                                    │
                                Theme Map
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ Phase 4: Insight Generation   │
                    │ • Quote Selection (LLM)       │
                    │ • Action Generation (LLM)     │
                    └───────────────┬───────────────┘
                                    │
                            Selected Insights
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ Phase 5: Pulse Generation     │
                    │ • Compose ≤250w pulse (LLM)   │
                    └───────────────┬───────────────┘
                                    │
                               Weekly Pulse
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │ Phase 6: Email Draft & Delivery│
                    │ • Draft internal email (LLM)  │
                    │ • Optional SMTP Send          │
                    └───────────────┬───────────────┘
                                    │
                          ┌─────────┴──────────┐
                          ▼                    ▼
                   Weekly Pulse          Email Draft
                   (Markdown)            (Markdown + Plain)
```

### Intermediate Artifacts at Each Phase Boundary

| Boundary | Artifact | Format |
|---|---|---|
| After Phase 1 | Raw Reviews (`raw_reviews.json`) | JSON / CSV |
| After Phase 2 | Cleaned review dataset (`reviews_cleaned.json`) | JSON |
| After Phase 3 | Theme Map (`theme_map.json`) | JSON |
| After Phase 4 | Selected Insights (`insights.json`) | JSON |
| After Phase 5 | Weekly Pulse (`weekly_pulse.md`) | Markdown |
| After Phase 6 | Email Draft (`email_draft.md`) | Markdown |

---

## 6. AI Component Design (Groq & Gemini Usage)

### 6.1 LLM Integration Architecture

The AI layer incorporates robust engineering constraints for production-grade reliability:
- **Prompt Template Registry**: Centralized version-controlled storage for all prompts.
- **JSON Schema Validation**: Every LLM response is strictly validated against expected schemas to avoid upstream errors.
- **Retry Logic**: Automatic retry with exponential backoff for malformed outputs or API transient errors.
- **Rate-Limit Handling**: Safely regulates outgoing concurrent requests to Groq.
- **Token Budget Tracking**: Logs token usage per run to monitor cost and abort if threshold is breached.

### 6.2 Major LLM Call Inventory

| Call | Purpose | Detail | Output |
|---|---|---|---|
| **Theme Discovery** | Generates primary analysis labels (Phase 3) | Uses sample of 100-150 reviews | Groq: Exactly 3–5 themes (`id`, `label`, `description`) |
| **Theme Classification** | Tag reviews (Phase 3) | Batch processed across all records | Groq: Mapping of `reviewId → theme_id` |
| **Quote Selection** | Evidence gathering (Phase 4) | Extracts pure verbatims | Groq: 1–2 quotes per theme |
| **Action Generation** | Product ideation (Phase 4) | Evaluates Themes + Quotes | Groq: exactly 3 actionable ideas |
| **Pulse Composition** | Final formatting (Phase 5) | Combines all synthesis | Gemini: ≤ 250 words total |
| **Email Drafting** | Delivery (Phase 6) | Formats communication wrapper | Gemini: Internal email wrapping the pulse |

### 6.3 Multi-LLM Strategy

The system distributes LLM workloads across providers to optimize for different capabilities:
- **Groq LLM** is used for analytical tasks requiring precise data processing and high-speed classification (Theme Detection, Review Tagging, and Insight Generation).
- **Gemini LLM** is used for creative summarization and professional formatting tasks (Weekly Pulse Composition and Email Draft Generation) where long-context understanding and natural language fluidity are paramount.

### 5.3 Prompt Design Principles

1. **Structured output enforcement** — Every prompt requests JSON output with a defined schema. The response parser validates before proceeding.
2. **Token budgeting** — Each prompt includes a `max_tokens` ceiling calculated from expected output size + 20% buffer.
3. **Context minimisation** — Only the data strictly needed for the task is included in the prompt. Full review text is sent only when quotes are being selected.
4. **Role-setting** — System prompts establish the LLM as a "senior product analyst at a fintech company" to bias output toward relevant domain language.
5. **Anti-hallucination guardrails** — Quote selection prompts explicitly instruct: "Do not paraphrase. Use exact text from the provided reviews."

### 5.4 Error Handling & Fallbacks

| Failure Scenario | Handling Strategy |
|---|---|
| Groq API timeout | Retry with exponential backoff (max 3 attempts) |
| Malformed JSON response | Retry with simplified prompt; if still failing, extract with regex |
| Rate limit exceeded | Queue and retry after cooldown period |
| Theme count > 5 | Trigger `LLM-2` consolidation call |
| Pulse word count > 250 | Issue follow-up trimming prompt |
| Total API failure | Fall back to rule-based keyword extraction + template-based pulse |

---

## 7. Automation, Scheduler & CLI

### 7.1 Automation / Scheduler Design
The system enables a strictly hands-off flow via:
- **Weekly Scheduled Runs:** Handled via a centralized cron execution or a **GitHub Actions scheduled workflow**.
- **Automated Flow Details:**
  - `google-play-scraper` fires at the scheduled cadence (e.g., Monday 8 AM).
  - Drives Phase 1-6 autonomously.
  - Automatically generates the pulse, drafts the email, and signals the delivery mechanism to send the email.

### 7.2 CLI Execution Support
A modular CLI interface provides granular operations, essential for developer debugging and cron integration.

`python main.py --phase email`
(Default Dry Run)

`python main.py --phase email --send`
(Enable SMTP email delivery)

**Supported phases:** `scrape`, `analyze`, `classify`, `report`, `email`
**Supported options:** `--weeks`, `--send`, `--recipient`, `--date`

*Architecture Note:* Each modular phase gracefully picks up execution by reading from the **latest artifact produced by the previous phase** located inside the current run.

---

## 8. Storage Design

### 8.1 Directory Structure
Uses an auditable run-based structure containing explicitly requested artifacts:

```
storage/
├── runs/
│   └── {run_id}/
│       ├── input/           # raw reviews
│       ├── cleaned/         # cleaned reviews
│       ├── analysis/        # theme map, selected quotes
│       ├── output/          # weekly pulse, email draft
│       └── logs/            # LLM call logs
└── config/
    ├── prompts/             # Prompt templates (version-controlled)
    └── settings.json        # Config rules and API URLs
```

### 7.2 Storage Principles

| Principle | Rationale |
|---|---|
| **File-based storage** | No database needed for this scale; JSON + Markdown files are inspectable and version-controllable |
| **Run-scoped isolation** | Each run's artifacts are self-contained under a unique run directory |
| **Prompt versioning** | Prompts are stored as template files, enabling iteration without code changes |
| **LLM call logging** | Every Groq call (prompt, response, token count, latency) is logged for cost tracking and debugging |

### 7.3 Retention Policy

- **Raw CSVs:** Retained for 90 days, then auto-archived.
- **Generated outputs:** Retained indefinitely (small footprint: ~50 KB per run).
- **LLM logs:** Retained for 30 days for debugging, then summarised and archived.

---

## 8. Output Artifacts

### 8.1 Weekly Pulse (Primary Output)

**Format:** Markdown (≤ 250 words)  
**Structure:**

```
# Groww Mutual Fund — Weekly Review Pulse
**Week ending:** {date}  |  **Reviews analysed:** {count}

## Top Themes

### 1. {Theme Name} ({sentiment}) — {review_count} mentions
> "{verbatim user quote}"

### 2. {Theme Name} ({sentiment}) — {review_count} mentions
> "{verbatim user quote}"

...up to 5 themes...

## Product Action Ideas
1. **{Action Title}** — {one-line rationale}
2. **{Action Title}** — {one-line rationale}
3. **{Action Title}** — {one-line rationale}

---
_Generated by App Review Weekly Pulse · {timestamp}_
```

**Design Constraints:**
- Maximum 5 themes
- Maximum 3 action ideas
- Total word count ≤ 250
- Scannable in ≤ 2 minutes by a VP/Director

### 8.2 Email Draft

**Format:** Markdown + Plain Text  
**Contains:**
- Subject line: `[Weekly Pulse] Groww Mutual Fund Reviews — Week of {date}`
- Greeting line
- Inline weekly pulse (not an attachment)
- Brief sign-off
- No attachments or external links

### 8.3 Processed Insights (Theme Map)

**Format:** JSON  
**Contains:**
- Each theme with label, description, sentiment, review count
- Associated review texts (PII-free)
- Selected verbatim quotes
- Useful for downstream analytics or dashboarding

---

## 10. Scalability & Cost Management

### 10.1 Current Scale Assumptions

| Dimension | Current Assumption |
|---|---|
| Reviews per run | 500–2,000 |
| Runs per week | 1 (weekly cadence) |
| Concurrent users | 1–3 (internal team) |
| Output size | ~50 KB per run |

### 9.2 Scaling Vectors

| Scenario | Adaptation |
|---|---|
| **More reviews (5K+)** | Increase batch size; add a pre-clustering step (TF-IDF or embedding-based) before LLM theme extraction to reduce token usage |
| **Multiple apps** | Parameterise the pipeline by app ID; run independent pipelines per app; shared prompt templates |
| **Higher frequency (daily)** | Switch from file-based storage to a lightweight database (SQLite → PostgreSQL); add incremental ingestion (process only new reviews since last run) |
| **Multi-user access** | Add authentication to the web interface; introduce role-based access for viewing vs. triggering |
| **Multi-language reviews** | Add a translation step between Phase 1 and Phase 2 using Groq or a dedicated translation API |

### 10.3 Cost Management
Cost efficiency acts as a premier architectural concern. Constraints include:
- **Batching Reviews:** Packing optimally sized blocks of reviews into context windows.
- **Limiting Token Size:** Rigorous caps imposed on API generation outputs.
- **Caching Repeated LLM Calls:** Idempotent runs return locally cached LLM conclusions per deterministic inputs instead of refiring.
- **Using Smaller Models for Classification:** Fast routing inference (`llama-8b` equivalents) manages routine Review Classification, reserving powerful parameters strictly for complex operations like Synthesis.


### 9.4 Reliability

| Concern | Mitigation |
|---|---|
| **LLM availability** | Rule-based fallback for theme extraction; template-based fallback for pulse composition |
| **Data integrity** | Input validation at Phase 1; schema checks at every phase boundary |
| **Reproducibility** | Fixed random seeds where applicable; prompt templates are version-controlled |
| **Observability** | Structured logging at every phase; run status visible in UI; LLM call audit trail |

---

## 11. Observability
Visibility acts as the lifeline for asynchronous operations:
- **Logging of Pipeline Stages:** Explicit `INFO/DEBUG` logging isolates breaks cleanly into phase boundaries.
- **LLM Request/Response Logging:** Deep-logging intercepts and records every prompt string and exact raw JSON output to `runs/{run_id}/logs/`.
- **Error Handling for API Failures:** Graceful upstream interceptors to catch partial LLM outages securely instead of unhandled downstream exceptions.
- **Retry with Exponential Backoff:** All networked dependencies strictly enforce retry protocols mapping to HTTP 429 and HTTP 5xx.

---

## 12. Web Interface Architecture

The web UI is a **lightweight single-page application** that serves as the interaction layer for the pipeline.

### 12.1 UI Components

```
┌─────────────────────────────────────────────────────────┐
│                    HEADER / NAV BAR                      │
│         App Review Weekly Pulse · Groww MF               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │           INGESTION / UPLOAD PANEL               │   │
│  │  ┌────────────────────┐  ┌───────────────────┐   │   │
│  │  │  Auto-Fetch Pulse  │  │  CSV Upload Zone  │   │   │
│  │  │  [🚀 Start Fetch]  │  │  (Fallback)       │   │   │
│  │  └────────────────────┘  └───────────────────┘   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │           PIPELINE CONTROL PANEL                  │   │
│  │  [▶ Generate Pulse]    [📧 Generate Email Draft]  │   │
│  │                                                    │   │
│  │  Status: ████████░░ Phase 5 of 6 — Pulse Generation  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              REPORT VIEWER                        │   │
│  │                                                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐        │   │
│  │  │  Pulse   │  │  Email   │  │  Themes  │        │   │
│  │  │  Tab     │  │  Tab     │  │  Tab     │        │   │
│  │  └──────────┘  └──────────┘  └──────────┘        │   │
│  │                                                    │   │
│  │  [Rendered Markdown content of selected tab]       │   │
│  │                                                    │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              RUN HISTORY                          │   │
│  │  ┌────────┬────────────┬────────┬──────────────┐ │   │
│  │  │ Run ID │ Date       │ Status │ Actions      │ │   │
│  │  ├────────┼────────────┼────────┼──────────────┤ │   │
│  │  │ #007   │ 2026-03-10 │ ✅     │ View · Copy  │ │   │
│  │  │ #006   │ 2026-03-03 │ ✅     │ View · Copy  │ │   │
│  │  └────────┴────────────┴────────┴──────────────┘ │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### 12.2 Explicit API Endpoints (Backend Comm)

The architecture exposes robust, dedicated endpoints explicitly linking the Web UI interaction to backend orchestrators:

- `POST /api/upload` - Securely uploads and validates manual fallback CSV.
- `POST /api/run` - Triggers Phase 1-5 sequentially on target dataset.
- `GET /api/run/{id}/status` - Live polling endpoint validating progress of individual runs.
- `GET /api/run/{id}/pulse` - Delivers final generated Weekly Pulse Markdown object to UI.
- `POST /api/run/{id}/email` - Explicitly fires Phase 4 email dispatch or draft aggregation.

---

> **This document is the system architecture specification. Implementation should follow the phases, data flows, and component boundaries defined here.**
