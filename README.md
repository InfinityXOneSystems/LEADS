# LEADS System

**Lead normalization, validation, ingestion, scoring, and outreach automation for XPS Intelligence (Xtreme Polishing Systems)**

The LEADS system is a production-ready Python backend that ingests raw business leads from multiple scraping sources, enriches and validates the data, scores each lead using a multi-factor ML-inspired algorithm, categorizes them as Hot / Warm / Cold, and triggers automated email outreach campaigns to the top prospects.

---

## Architecture Overview

```
Scraper Sources (Google Maps, Yelp, LinkedIn, etc.)
         │
         ▼
  ┌──────────────────────────────────────────┐
  │           Ingestion Pipeline             │  ← Normalizes raw data into Lead model
  └──────────────────────┬───────────────────┘
                         ▼
  ┌──────────────────────────────────────────┐
  │          Validation Pipeline             │  ← Phone/email/address checks, industry filters
  └──────────────────────┬───────────────────┘
                         ▼
  ┌──────────────────────────────────────────┐
  │          Enrichment Pipeline             │  ← Epoxy keyword detection, contact verification
  └──────────────────────┬───────────────────┘
                         ▼
  ┌──────────────────────────────────────────┐
  │           Scoring Pipeline               │  ← Multi-factor 0-100 scoring
  └──────────────────────┬───────────────────┘
                         ▼
  ┌──────────────────────────────────────────┐
  │        Categorization Pipeline           │  ← Hot (≥75) / Warm (≥50) / Cold (<50)
  └──────────────────────┬───────────────────┘
                         ▼
         FastAPI REST API + Webhooks
         │                    │
         ▼                    ▼
   Frontend Display     Email Outreach
```

### Directory Structure

```
LEADS/
├── main.py                     # FastAPI app entry point
├── requirements.txt
├── .env.example
├── data/
│   ├── sample_leads.json       # Example lead data
│   └── scoring_weights.json    # Configurable scoring weights
├── src/
│   ├── config.py               # Settings (pydantic-settings)
│   ├── models/
│   │   ├── lead.py             # Core Lead model
│   │   ├── company.py          # Company + SocialPresence models
│   │   ├── contact.py          # Contact model
│   │   └── score_factors.py    # ScoreFactors + ScoringBreakdown models
│   ├── pipelines/
│   │   ├── ingestion.py        # Raw data → Lead object
│   │   ├── validation.py       # Data quality & format checks
│   │   ├── enrichment.py       # External data enrichment
│   │   ├── scoring.py          # Multi-factor lead scoring
│   │   └── categorization.py   # Hot/Warm/Cold bucketing + tagging
│   ├── services/
│   │   ├── validation_service.py   # Phone/email/address verification
│   │   ├── business_checker.py     # Google My Business status check
│   │   ├── enrichment_service.py   # Clearbit, Hunter.io, website analysis
│   │   ├── scoring_service.py      # Scoring weight management
│   │   └── email_outreach.py       # SMTP-based email campaigns
│   ├── api/
│   │   ├── routes.py           # Lead CRUD + pipeline endpoints
│   │   └── webhooks.py         # Scraper webhook receivers
│   ├── database/
│   │   └── models.py           # SQLAlchemy ORM models
│   └── utils/
│       ├── validators.py       # Phone / email / address validators
│       ├── formatters.py       # Frontend display formatters
│       └── logger.py           # Structured logging
└── tests/
    ├── test_validation.py
    ├── test_scoring.py
    ├── test_enrichment.py
    └── test_api.py
```

---

## Setup & Installation

### Prerequisites

- Python 3.11+
- PostgreSQL (or SQLite for development)
- Redis (optional, for Celery task queue)

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/your-org/LEADS.git
cd LEADS

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 5. Run the development server
python main.py
# OR
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Visit **http://localhost:8000/docs** for interactive API documentation.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./leads.db` | PostgreSQL/SQLite connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for Celery task queue |
| `SMTP_HOST` | `smtp.gmail.com` | Email server hostname |
| `SMTP_PORT` | `587` | Email server port (STARTTLS) |
| `SMTP_USER` | `""` | Email account username |
| `SMTP_PASSWORD` | `""` | Email account password |
| `FROM_EMAIL` | `noreply@xps-intelligence.com` | Sender email address |
| `FROM_NAME` | `XPS Intelligence Team` | Sender display name |
| `TWILIO_ACCOUNT_SID` | `""` | Twilio SID for phone verification |
| `TWILIO_AUTH_TOKEN` | `""` | Twilio auth token |
| `HUNTER_IO_API_KEY` | `""` | Hunter.io API key for email verification |
| `CLEARBIT_API_KEY` | `""` | Clearbit API key for company enrichment |
| `GOOGLE_MAPS_API_KEY` | `""` | Google Maps API for business status |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `HOT_SCORE_THRESHOLD` | `75` | Minimum score for "Hot" category |
| `WARM_SCORE_THRESHOLD` | `50` | Minimum score for "Warm" category |
| `SLACK_WEBHOOK_URL` | `""` | Slack webhook for hot lead alerts |
| `FRONTEND_URL` | `https://xps-intelligence.com` | Frontend URL for email links |
| `DEBUG` | `true` | Enable debug mode + auto-reload |

---

## API Documentation

### Base URL: `/api/v1/leads`

#### POST `/ingest`
Ingest a raw lead from a scraper (stores without processing).

**Request:**
```json
{
  "source": "google_maps",
  "company": {
    "name": "Acme Concrete Solutions",
    "phone": "+15551234567",
    "website": "https://acme-concrete.com",
    "address": "123 Main St",
    "city": "Cleveland",
    "state": "OH",
    "specializations": ["epoxy floors", "polished concrete"],
    "business_status": "active"
  },
  "primary_contact": {
    "name": "John Smith",
    "title": "Owner",
    "email": "john@acme-concrete.com"
  }
}
```

**Response:** `{ "id": "uuid", "status": "ingested", "company_name": "..." }`

---

#### POST `/validate`
Run validation rules on a lead payload.

**Response:**
```json
{
  "is_valid": true,
  "issues": [],
  "warnings": ["email: not provided"],
  "blocked_reasons": [],
  "completeness_score": 0.7,
  "validation_status": "valid"
}
```

---

#### POST `/score`
Score and categorize a lead.

**Response:**
```json
{
  "overall_score": 78,
  "category": "hot",
  "buying_likelihood": 0.7812,
  "confidence": 0.82,
  "breakdown": {
    "business_legitimacy": 0.95,
    "epoxy_relevance": 0.9,
    "market_opportunity": 0.6,
    "recent_activity": 0.85,
    "decision_maker_accessibility": 0.8,
    "social_engagement": 0.65
  }
}
```

---

#### POST `/process`
Run the full pipeline: ingest → validate → enrich → score → categorize.

**Response includes:** `id`, `company_name`, `overall_score`, `category`, `validation`, `frontend`

---

#### GET `/hot`
Get all hot leads (score ≥ 75), sorted by score descending.

**Query params:** `page` (default 1), `page_size` (default 50, max 100)

---

#### GET `/warm`
Get all warm leads (score 50–74).

---

#### GET `/cold`
Get all cold leads (score < 50).

---

#### GET `/search?query=<text>`
Search leads by company name, contact name, city, state, or email.

---

#### GET `/{lead_id}`
Get full lead object by ID.

---

#### POST `/{lead_id}/send-email?email_type=initial`
Send outreach email to a lead. `email_type` options: `initial`, `follow_up`, `final`.

---

### Webhooks: `/webhooks`

#### POST `/webhooks/scraper/leads`
Receive a batch of leads from a scraper. Runs full pipeline on each lead automatically.

```json
{
  "source": "google_maps",
  "batch_id": "batch-001",
  "leads": [ { ... }, { ... } ]
}
```

**Response:**
```json
{
  "batch_id": "batch-001",
  "processed": 15,
  "blocked": 2,
  "errors": 0,
  "results": [ ... ]
}
```

#### POST `/webhooks/lead/{lead_id}/email-opened`
Track email open event.

#### POST `/webhooks/lead/{lead_id}/email-clicked?link=<url>`
Track email click event.

---

## Scoring System

Leads are scored from **0 to 100** using six weighted factors:

| Factor | Weight | Description |
|---|---|---|
| Epoxy Relevance | 25% | Does the company work with epoxy/concrete/coatings? |
| Business Legitimacy | 20% | Is the business verified, rated, and active? |
| Accessibility | 15% | Can we reach the owner? (Phone, email, LinkedIn) |
| Activity | 15% | Recent Google reviews, active social channels |
| Opportunity | 15% | Company size, revenue, growth indicators |
| Engagement | 10% | Active on Facebook, Instagram, LinkedIn, YouTube |

**Categories:**
- 🔥 **Hot** (score ≥ 75): High-priority, immediate outreach
- 🌡️ **Warm** (score 50–74): Good prospects, queue for follow-up
- ❄️ **Cold** (score < 50): Low priority, bulk outreach only

Weights are configurable via `data/scoring_weights.json`.

---

## Pipeline Details

### 1. Ingestion Pipeline
- Normalizes raw JSON from any scraper source
- Extracts company, primary contact, and secondary contacts
- Validates and normalizes phone numbers to E.164 format
- Normalizes email addresses to lowercase
- Maps source to allowed values (defaults to `"other"`)

### 2. Validation Pipeline
- Checks required fields: company name, phone number
- Validates phone format (E.164 or US standard)
- Validates email format (regex-based)
- Validates address format (min 2 words, min 5 chars)
- Blocks leads with excluded industries (personal, hobby, retired, non-profit)
- Calculates completeness score (0.0–1.0)

### 3. Enrichment Pipeline
- Detects epoxy/concrete keywords in specializations and industry text
- Optionally calls Clearbit, Hunter.io, Twilio Lookup when configured
- Sets default business status to `"unknown"` if not provided

### 4. Scoring Pipeline
- Computes 6 factor scores (0.0–1.0 each)
- Applies configurable weights to produce overall score (0–100)
- Calculates buying likelihood (weighted sum, 0.0–1.0)
- Calculates confidence based on data completeness + verification status

### 5. Categorization Pipeline
- Assigns Hot/Warm/Cold based on score thresholds
- Generates descriptive tags: `active-social`, `epoxy-potential`, `high-relevance`, `verified-active`, `verified-contact`, `high-volume`, `growing-business`
- Ranks leads within each category by score

---

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_scoring.py -v

# Run with coverage
pip install pytest-cov
python -m pytest tests/ --cov=src --cov-report=term-missing
```

---

## Usage Examples

### Process a batch of leads from JSON

```python
import json
from src.pipelines.ingestion import IngestionPipeline
from src.pipelines.validation import ValidationPipeline
from src.pipelines.scoring import ScoringPipeline
from src.pipelines.categorization import CategorizationPipeline

with open("data/sample_leads.json") as f:
    raw_leads = json.load(f)

ingestion = IngestionPipeline()
validation = ValidationPipeline()
scoring = ScoringPipeline()
categorization = CategorizationPipeline()

processed = []
for raw in raw_leads:
    lead = ingestion.ingest(raw)
    lead, result = validation.validate(lead)
    if result["is_valid"]:
        lead = scoring.score(lead)
        lead = categorization.categorize(lead)
        processed.append(lead)

ranked = categorization.rank_leads(processed)
for lead in ranked:
    print(f"{lead.category.upper()} #{lead.category_rank}: {lead.company.name} ({lead.scores.overall_score}/100)")
```

### Send outreach to all hot leads

```python
from src.services.email_outreach import EmailOutreachService

service = EmailOutreachService(
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    smtp_user="you@company.com",
    smtp_password="your_password",
)

for lead in hot_leads:
    if lead.primary_contact.email:
        result = service.send_initial_email(
            lead_id=lead.id,
            to_email=lead.primary_contact.email,
            decision_maker_name=lead.primary_contact.name or "",
            company_name=lead.company.name,
            specializations=lead.company.specializations,
        )
        print(f"Email sent to {lead.company.name}: {result['success']}")
```

---

## License

Proprietary — Xtreme Polishing Systems © 2026. All rights reserved.
