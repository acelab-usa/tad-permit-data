"""run_all_ingestion.py -- runs ingestion for every registered jurisdiction
in one invocation, so a scheduler (cron, a GitHub Actions scheduled
workflow, etc.) has a single command to call instead of one per city --
and so a newly-registered jurisdiction (see sources/registry.py) is picked
up automatically, with no scheduler config to update.

Each jurisdiction is isolated: one failing outright (an unexpected
exception escaping dataloader.load_data(), not the routine per-record/
per-page failures dataloader.py already handles internally) is logged and
skipped, the rest still run. Requires workflow.py running separately as a
persistent worker -- this script only triggers ingestion and pushes
Hatchet events, it doesn't process them.

Usage:
    uv run python run_all_ingestion.py [--size N] [--jurisdictions a,b,c]

Examples:
    uv run python run_all_ingestion.py                       # every registered jurisdiction, size=100
    uv run python run_all_ingestion.py --size 25              # smaller batch per city
    uv run python run_all_ingestion.py --jurisdictions dc,la   # just these two, e.g. for testing
"""
import argparse
import time

from dataloader import load_data
from logging_setup import get_logger
from sources import list_sources

logger = get_logger("run_all_ingestion")


def run_all(jurisdictions: list, size: int) -> dict:
    """Runs load_data() for each jurisdiction, isolated from one another.
    Returns {"succeeded": [...], "failed": [...]}."""
    succeeded = []
    failed = []

    for jurisdiction in jurisdictions:
        started = time.monotonic()
        try:
            load_data(jurisdiction, size=size)
            succeeded.append(jurisdiction)
        except Exception as e:
            failed.append(jurisdiction)
            logger.error(
                "%s: ingestion run failed unexpectedly, skipping to the next jurisdiction: %s",
                jurisdiction, e,
            )
        else:
            logger.info("%s: done in %.1fs", jurisdiction, time.monotonic() - started)

    return {"succeeded": succeeded, "failed": failed}


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--jurisdictions",
        help="Comma-separated jurisdictions to run (default: every registered jurisdiction)",
    )
    parser.add_argument("--size", type=int, default=100, help="Record/page batch size per jurisdiction (default: 100)")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    jurisdictions = (
        [j.strip() for j in args.jurisdictions.split(",") if j.strip()]
        if args.jurisdictions
        else list_sources()
    )

    logger.info("Starting ingestion run for %s jurisdiction(s): %s", len(jurisdictions), ", ".join(jurisdictions))
    result = run_all(jurisdictions, size=args.size)

    logger.info(
        "Ingestion run complete: %s/%s jurisdiction(s) succeeded%s",
        len(result["succeeded"]), len(jurisdictions),
        f", failed: {', '.join(result['failed'])}" if result["failed"] else "",
    )
