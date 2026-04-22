from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.config import load_config, load_sector_config
from atlas20.data.processor import build_processed_datasets
from atlas20.logging_utils import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Atlas20 processed datasets from cache")
    parser.add_argument("--config", default="config/base.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    sector_config = load_sector_config(config.resolve_path("config/sectors.yaml"))
    configure_logging(config.logging.level)
    build_processed_datasets(config, sector_config)


if __name__ == "__main__":
    main()
