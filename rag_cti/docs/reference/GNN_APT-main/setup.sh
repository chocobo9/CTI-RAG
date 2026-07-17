#!/usr/bin/env bash
# setup.sh — one-shot setup for /attribute on a fresh machine.
#
# What this does:
#   1. Resolves ./trail (handles dangling symlink from a zip transfer)
#   2. Clones the TRAIL paper repo if missing
#   3. Fetches the timestamped TKG from this repo's GitHub Release if missing
#   4. Fetches our 5 fold checkpoints from the same release if missing
#   5. Fetches the paper authors' baseline weights from the release if missing
#      (only needed for USE_PAPER_BASELINE=1)
#   6. Creates .venv and installs Python dependencies
#   7. Prints the exact command to start the server
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
#
# Re-running is safe — every step is idempotent.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

ASSETS_BASE="https://github.com/jwang412s/GNN_APT/releases/download/assets-v1"

# fetch <url> <output>
fetch() {
  local url="$1" out="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --progress-bar -o "$out" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget --show-progress -O "$out" "$url"
  else
    echo "  need curl or wget on PATH to fetch $url" >&2
    exit 1
  fi
}

echo "[1/7] Checking ./trail layout"
if [ -L trail ] && [ ! -e trail ]; then
  echo "  ./trail is a dangling symlink — removing"
  rm trail
fi
if [ -L trail ]; then
  TARGET="$(readlink trail)"
  echo "  ./trail -> $TARGET (collapsing to a real directory)"
  rm trail
  if [ -d "$TARGET" ]; then
    cp -R "$TARGET" trail
  fi
fi

echo "[2/7] Cloning TRAIL paper repo if missing"
if [ ! -d trail ]; then
  # The paper's code-availability footnote points to cybermonic/trail.
  git clone https://github.com/cybermonic/trail.git trail
else
  echo "  ./trail already present — skipping clone"
fi

echo "[3/7] TKG dataset"
TKG_TS="trail/TKG_data/otx_dataset_timestamped/full_graph_csr.pt"
TKG_ORIG="trail/TKG_data/otx_dataset/full_graph_csr.pt"
if [ ! -f "$TKG_TS" ] && [ ! -f "$TKG_ORIG" ]; then
  echo "  fetching tkg_timestamped.tar.gz from GitHub Release..."
  mkdir -p trail/TKG_data
  fetch "$ASSETS_BASE/tkg_timestamped.tar.gz" /tmp/tkg_timestamped.tar.gz
  tar -xzf /tmp/tkg_timestamped.tar.gz -C trail/TKG_data
  rm -f /tmp/tkg_timestamped.tar.gz
  if [ ! -f "$TKG_TS" ]; then
    echo "  download succeeded but $TKG_TS still missing — bailing"
    exit 1
  fi
  echo "  TKG installed"
else
  echo "  TKG present"
fi

# assets-v1 contains the timestamped graph but its three CSV entries may be
# empty.  The author repository's TKG.zip contains the feature tables, and the
# timestamped graph has the same x/feat_map/event_ids/CSR tensors as that graph.
for csv in ips.csv urls.csv domains.csv; do
  if [ ! -s "$(dirname "$TKG_TS")/$csv" ]; then
    if [ ! -s "$(dirname "$TKG_ORIG")/$csv" ]; then
      echo "  extracting author feature tables from trail/TKG.zip..."
      python3 -m zipfile -e trail/TKG.zip trail/TKG_data
    fi
    rm -f "$(dirname "$TKG_TS")/$csv"
    cp "$(dirname "$TKG_ORIG")/$csv" "$(dirname "$TKG_TS")/$csv"
  fi
done

echo "[4/7] Re-trained fold checkpoints"
WDIR="sandbox/year_drop/B/weights"
mkdir -p "$WDIR"
MISSING=()
for i in 0 1 2 3 4; do
  if [ ! -f "$WDIR/fold${i}.pt" ]; then
    MISSING+=("fold${i}.pt")
  fi
done
if [ ${#MISSING[@]} -gt 0 ]; then
  echo "  fetching ${#MISSING[@]} fold checkpoint(s) from GitHub Release..."
  for f in "${MISSING[@]}"; do
    fetch "$ASSETS_BASE/$f" "$WDIR/$f"
  done
fi
echo "  fold0..fold4 present"

echo "[5/7] Paper baseline weights (for USE_PAPER_BASELINE=1)"
PAPER_WT="trail/src/weights/2-layer/gnn_train-0.777_max_lprop+feats+ae-new-data.pt"
if [ ! -f "$PAPER_WT" ]; then
  echo "  fetching paper_baseline.tar.gz from GitHub Release..."
  mkdir -p trail/src/weights
  fetch "$ASSETS_BASE/paper_baseline.tar.gz" /tmp/paper_baseline.tar.gz
  tar -xzf /tmp/paper_baseline.tar.gz -C trail/src/weights
  rm -f /tmp/paper_baseline.tar.gz
  echo "  paper baseline weights installed"
else
  echo "  paper baseline weights present"
fi

echo "[6/7] Python venv + dependencies"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
# PyG's compiled extensions need wheels built for the exact Torch ABI.  Installing
# the unpinned requirements in one shot makes pip try to build torch-scatter in an
# isolated environment before torch is importable (and fails on Python 3.12).
pip install --quiet torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install --quiet torch-scatter torch-sparse \
  -f https://data.pyg.org/whl/torch-2.5.1+cpu.html
pip install --quiet -r trail_gnn/requirements.txt

echo "[7/7] Done."
cat <<'EOF'

To start the server:
  source .venv/bin/activate
  python3 -m uvicorn predict_paper_server:app --host 0.0.0.0 --port 47823

Test /attribute once "[ready] server up." appears:
  curl -X POST http://localhost:47823/attribute \
       -H "Content-Type: application/json" \
       -d '{"iocs": [{"type":"domain","value":"suspicious.example.com"}]}'

Switch to the paper authors' single-fold checkpoint:
  USE_PAPER_BASELINE=1 python3 -m uvicorn predict_paper_server:app \
       --host 0.0.0.0 --port 47823
EOF
