#!/usr/bin/env python3
"""CLI for Phase 6-A trusted full-deck orchestration."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from deck_orchestrator import DeckError, DeckRunner

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True); parser.add_argument("--resume", action="store_true"); parser.add_argument("--force", action="store_true"); parser.add_argument("--jobs", type=int); parser.add_argument("--page"); parser.add_argument("--from-page"); parser.add_argument("--skip-preview", action="store_true"); parser.add_argument("--dry-plan", action="store_true"); parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    try:
        result = DeckRunner(Path(args.manifest), resume=True, force=args.force, jobs=args.jobs, page=args.page, from_page=args.from_page, skip_preview=args.skip_preview).run(dry_plan=args.dry_plan)
    except (DeckError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}"); return 1
    if args.json_summary or args.dry_plan: print(json.dumps(result, ensure_ascii=False, indent=2))
    else: print(f"Deck run: {result['deck_run_id']}\nStatus: {result.get('overall_status')}")
    return 1 if result.get("overall_status") == "failed" else 0

if __name__ == "__main__": raise SystemExit(main())
