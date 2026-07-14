#!/usr/bin/env python3
"""Run MITRE raw OTX downloader for shard part 01."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from download_otx_raw_mitre_part import main


if __name__ == "__main__":
    main(default_part=1)
