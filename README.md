# App Review Weekly Pulse

Turns recent Google Play reviews of the Groww Mutual Fund app into a one-page weekly product feedback pulse and an email draft. All AI steps run on Google Gemini. See [architecture.md](architecture.md) for the design.

The app ships in two forms that share the same pipeline code:

| | Stack | Use it for |
|---|---|---|
| **Web app (Vercel)** | FastAPI (`main.py`) + static frontend (`public/`) | Production hosting |
| **Streamlit app** | `phase7_streamlit_ui/app.py` | Local use only. Streamlit needs a long-running server, so it cannot run on Vercel |

## Deploy to Vercel

1. Push the repo to GitHub and import it in Vercel. No build settings are needed: Vercel detects the FastAPI app in `main.py`, installs `requirements.txt` and serves `public/` from its CDN.
2. Add these **Environment Variables** (Project Settings, Environment Variables):

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | yes | Gemini Developer API key (an `AIza...` key from Google AI Studio) |
| `APP_PASSWORD` | strongly recommended | Shared password for the site. Without it anyone with the URL can spend your Gemini credits and send email |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_TLS`, `EMAIL_TO` | optional | Email delivery |
| `KV_REST_API_URL`, `KV_REST_API_TOKEN` | optional | Persistent run history (see below) |
| `GEMINI_ANALYSIS_MODEL`, `GEMINI_SYNTHESIS_MODEL`, `LLM_TOKEN_BUDGET` | optional | Overrides |

3. Deploy. `vercel.json` sets the function limit to 300 seconds. If your plan caps functions lower, the pipeline still works because every step is its own short request (the slowest, theme analysis, usually takes 15 to 40 seconds).

### How it works on serverless

- The pipeline is a chain of **stateless API calls** the browser makes in order: `collect`, `clean`, `analyze`, `insights`, `pulse`. Each call receives the previous step's output, so nothing has to survive between requests and each stays inside Vercel time limits.
- **Run history** is kept in the browser (localStorage, last 10 runs) by default. For history that survives across browsers and devices, add the **Upstash Redis** integration from the Vercel Marketplace; it provides `KV_REST_API_URL` and `KV_REST_API_TOKEN` and the app picks them up automatically.
- Gemini cost is measured per request and stored with each run, so the Usage and cost tab works without any server-side log.
- Vercel's filesystem is read-only apart from `/tmp`, so nothing is written to the repo directory.

Known limits: Google Play scraping runs from Vercel's shared IPs and can occasionally be rate limited, in which case use the CSV upload. A request body is limited to about 4.5 MB, which comfortably fits the 1000-review maximum.

## Run locally

```bash
pip install -r requirements-streamlit.txt
```

Create `.env` (see `.env.example`), then pick one:

```bash
uvicorn main:app --reload                       # the Vercel app at http://localhost:8000
streamlit run phase7_streamlit_ui/app.py        # the Streamlit app
python cli.py --phase collect                   # command line, phases: collect clean analyze insight pulse email
python cli.py --phase email --send              # sends through SMTP
```

On Streamlit Cloud, put the same keys in the app's secrets.

## Pages

**Overview** (charts, themes, actions), **Reviews** (live Play Store feed and the analysis dataset), **Report** (weekly pulse, email draft and send), **Pipeline** (Play Store fetch or CSV upload, live status) and **Run history** (runs table plus a Usage and cost tab with all Gemini pricing and spend). Cost is intentionally shown nowhere else.

CSV fallback columns: `rating` and `review_text` are required; `reviewId` and `review_date` are optional.

## AI usage

| Step | Model |
|---|---|
| Review classification | `gemini-3.5-flash-lite` |
| Theme discovery, quote selection, action ideas, pulse, email intro | `gemini-3.6-flash` |

Calls are retried with exponential backoff and tracked against a token budget. Reviews are PII-scrubbed (emails, phone numbers, links, long numeric IDs) before any text is sent to the model.

## API cost

Every Gemini call is priced from Google's published paid-tier rates (`PRICING` in `services/gemini_client.py`) and shown per run and in the Usage and cost tab of Run history. Thinking is set to `minimal` to keep output tokens low. A typical run of about 70 reviews costs roughly $0.03 (about $0.12 per month at one run a week). `gemini-3.6-flash` pricing doubles on 1 Jan 2027, and the table accounts for that. Figures are estimates; Google AI Studio billing is authoritative.

## Tests

```bash
python -m pytest -q
```
