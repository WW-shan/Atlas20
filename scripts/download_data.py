from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from atlas20.config import load_config
from atlas20.data.processor import download_and_cache_raw_data
from atlas20.logging_utils import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and cache Atlas20 raw data")
    parser.add_argument("--config", default="config/base.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level)
    download_and_cache_raw_data(config)


if __name__ == "__main__":
    main()
