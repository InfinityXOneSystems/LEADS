#!/usr/bin/env python3
"""Export processed lead data to static JSON files for GitHub Pages.

Usage (from repo root):
    python scripts/export_leads.py [--input data/sample_leads.json] [--outdir docs/api]

The script runs every lead through the full normalization pipeline and writes
the following files to ``--outdir``:
  - leads.json  – all normalized leads
  - hot.json    – hot leads (score ≥ 75)
  - warm.json   – warm leads (score 50-74)
  - cold.json   – cold leads (score < 50)
  - meta.json   – export metadata / totals

These files are consumed by GitHub Pages (this repo's gh-pages branch) and
dispatched to the XPS Intelligence Frontend repo via repository_dispatch.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Ensure repo root is on PYTHONPATH regardless of CWD
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from src.models.lead import FrontendFormat, Lead  # noqa: E402
from src.pipelines.categorization import CategorizationPipeline  # noqa: E402
from src.pipelines.enrichment import EnrichmentPipeline  # noqa: E402
from src.pipelines.ingestion import IngestionPipeline  # noqa: E402
from src.pipelines.scoring import ScoringPipeline  # noqa: E402
from src.pipelines.validation import ValidationPipeline  # noqa: E402
from src.services.xps_sync import XPSSyncService  # noqa: E402
from src.utils.formatters import LeadFormatter  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

logger = get_logger("export_leads")

DEFAULT_INPUT = str(_REPO_ROOT / "data" / "sample_leads.json")
DEFAULT_OUTDIR = str(_REPO_ROOT / "docs" / "api")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help="Path to raw leads JSON file (default: data/sample_leads.json)",
    )
    parser.add_argument(
        "--outdir",
        default=DEFAULT_OUTDIR,
        help="Output directory for static JSON files (default: docs/api)",
    )
    parser.add_argument(
        "--dispatch",
        action="store_true",
        default=False,
        help="Dispatch a repository_dispatch event to the XPS Frontend repo",
    )
    return parser.parse_args()


def run_pipeline(raw: dict) -> Optional[Lead]:
    """Run a single raw lead through the full normalization pipeline."""
    ingestion = IngestionPipeline()
    validation = ValidationPipeline()
    enrichment = EnrichmentPipeline()
    scoring = ScoringPipeline()
    categorization = CategorizationPipeline()

    lead = ingestion.ingest(raw)
    lead, result = validation.validate(lead)
    if not result.get("is_valid") and result.get("blocked_reasons"):
        logger.info(f"Lead blocked: {result['blocked_reasons']}")
        return None

    lead = enrichment.enrich(lead)
    lead = scoring.score(lead)
    lead = categorization.categorize(lead)

    lead_dict = lead.model_dump()
    frontend_data = LeadFormatter.format_lead_for_frontend(lead_dict)
    lead.frontend = FrontendFormat(**frontend_data)
    return lead


def export_leads(input_path: str, outdir: str, dispatch: bool) -> None:
    """Load leads, normalize, then write static JSON files."""
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)

    logger.info(f"Loading leads from {input_path}")
    with open(input_path, encoding="utf-8") as fh:
        raw_leads = json.load(fh)

    processed = []
    for raw in raw_leads:
        lead = run_pipeline(raw)
        if lead is not None:
            processed.append(lead)

    logger.info(f"Processed {len(processed)}/{len(raw_leads)} leads")

    sync = XPSSyncService(
        github_token=os.getenv("XPS_GITHUB_TOKEN", ""),
        xps_system_repo=os.getenv("XPS_SYSTEM_REPO", "InfinityXOneSystems/LEADS"),
        xps_frontend_repo=os.getenv(
            "XPS_FRONTEND_REPO", "InfinityXOneSystems/frontend-system"
        ),
        pages_branch=os.getenv("XPS_PAGES_BRANCH", "gh-pages"),
    )
    payload = sync.build_export_payload(processed)

    # Write per-category files and combined file
    files = {
        "leads.json": payload["leads"],
        "hot.json": payload["hot"],
        "warm.json": payload["warm"],
        "cold.json": payload["cold"],
    }
    for filename, data in files.items():
        dest = out / filename
        dest.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info(f"Wrote {len(data)} leads → {dest}")

    # Write metadata
    meta = {
        "schema_version": payload["schema_version"],
        "exported_at": payload["exported_at"],
        "source_repo": payload["source_repo"],
        "totals": payload["totals"],
    }
    meta_dest = out / "meta.json"
    meta_dest.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    logger.info(f"Wrote metadata → {meta_dest}")

    if dispatch:
        result = sync.dispatch_frontend_update(payload)
        if result.get("success"):
            logger.info("Dispatched leads-updated event to XPS Frontend")
        else:
            logger.warning(f"Frontend dispatch failed: {result}")

    logger.info(
        f"Export complete: {payload['totals']['hot']} hot, "
        f"{payload['totals']['warm']} warm, "
        f"{payload['totals']['cold']} cold"
    )


if __name__ == "__main__":
    args = parse_args()
    export_leads(
        input_path=args.input,
        outdir=args.outdir,
        dispatch=args.dispatch,
    )
