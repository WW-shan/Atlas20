from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.config import load_config
from atlas20.pipeline import run_research_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Atlas20 end-to-end research pipeline")
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--refresh-raw", action="store_true", help="Refresh raw API caches before backtesting")
    args = parser.parse_args()

    config = load_config(args.config)
    run_research_pipeline(config, refresh_raw=args.refresh_raw)


if __name__ == "__main__":
    main()
