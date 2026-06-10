"""Download recent public CTI PDF reports to data/raw/pdfs/.

Fetches from three sources in order:
  1. Curated  — FBI IC3 annual internet crime reports (5 direct URLs)
  2. CISA     — scrapes the cybersecurity advisory listing for PDF attachments
  3. ENISA    — scrapes the publications listing for threat landscape PDFs

Stops once --max files have been successfully saved.

Usage:
    python scripts/fetch_pdfs.py
    python scripts/fetch_pdfs.py --max 30 --out-dir data/raw/pdfs
    python scripts/fetch_pdfs.py --dry-run          # list URLs without writing files
    python scripts/fetch_pdfs.py --sources cisa     # only one source

Requirements (all already project deps or transitive):
    httpx, tenacity, beautifulsoup4 (via unstructured[pdf])
"""
from __future__ import annotations

# ruff: noqa: E402  (sys.path bootstrap before imports - run-without-install pattern)
import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rag_cti._logging import configure_logging, get_logger

try:
    from bs4 import BeautifulSoup
except ImportError:
    print(
        "ERROR: beautifulsoup4 not installed.\n"
        "Run: pip install beautifulsoup4",
        file=sys.stderr,
    )
    sys.exit(1)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_OUT = Path("data/raw/pdfs")
_DEFAULT_MAX = 50
_DEFAULT_TIMEOUT = 30.0
_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB hard cap per file

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CTI-RAG-fetcher/1.0; research use)"
    ),
    "Accept": "text/html,application/pdf,*/*",
}

_CISA_BASE = "https://www.cisa.gov"
_CISA_INDEX = "https://www.cisa.gov/news-events/cybersecurity-advisories"

_ENISA_BASE = "https://www.enisa.europa.eu"
_ENISA_INDEX = "https://www.enisa.europa.eu/publications"

# ---------------------------------------------------------------------------
# Curated list — only URLs verified as stable public government resources
# ---------------------------------------------------------------------------

# (url, local_filename)
_CURATED: list[tuple[str, str]] = [
    # FBI Internet Crime Complaint Center — annual reports
    (
        "https://www.ic3.gov/Media/PDF/AnnualReport/2023_IC3Report.pdf",
        "fbi_ic3_annual_2023.pdf",
    ),
    (
        "https://www.ic3.gov/Media/PDF/AnnualReport/2022_IC3Report.pdf",
        "fbi_ic3_annual_2022.pdf",
    ),
    (
        "https://www.ic3.gov/Media/PDF/AnnualReport/2021_IC3Report.pdf",
        "fbi_ic3_annual_2021.pdf",
    ),
    (
        "https://www.ic3.gov/Media/PDF/AnnualReport/2020_IC3Report.pdf",
        "fbi_ic3_annual_2020.pdf",
    ),
    (
        "https://www.ic3.gov/Media/PDF/AnnualReport/2019_IC3Report.pdf",
        "fbi_ic3_annual_2019.pdf",
    ),
]

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _make_client(timeout: float) -> httpx.Client:
    return httpx.Client(headers=_HEADERS, timeout=timeout, follow_redirects=True)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=False,
)
def _get_html(client: httpx.Client, url: str) -> BeautifulSoup | None:
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as exc:
        logger.warning("page fetch failed", url=url, error=str(exc))
        return None


def _safe_filename(url: str, prefix: str = "") -> str:
    """Derive a filesystem-safe filename from a URL path."""
    stem = urlparse(url).path.rstrip("/").split("/")[-1]
    stem = re.sub(r"[^\w.\-]", "_", stem)
    if not stem.lower().endswith(".pdf"):
        stem += ".pdf"
    return f"{prefix}{stem}" if prefix else stem


# ---------------------------------------------------------------------------
# Source 1: Curated list
# ---------------------------------------------------------------------------


def collect_curated() -> list[tuple[str, str]]:
    return list(_CURATED)


# ---------------------------------------------------------------------------
# Source 2: CISA cybersecurity advisories
# ---------------------------------------------------------------------------


def collect_cisa(client: httpx.Client, limit: int = 40) -> list[tuple[str, str]]:
    """Scrape CISA advisory index and individual advisory pages for PDF links.

    CISA serves advisory PDFs from /sites/default/files/. We first harvest
    any direct PDF hrefs from the index page, then visit individual AA-prefixed
    advisory pages (up to 15) to find their attached PDFs.
    """
    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    soup = _get_html(client, _CISA_INDEX)
    if soup is None:
        logger.warning("CISA index unreachable, skipping source")
        return results

    def _add(href: str) -> None:
        if len(results) >= limit:
            return
        url = href if href.startswith("http") else urljoin(_CISA_BASE, href)
        if url not in seen:
            seen.add(url)
            results.append((url, _safe_filename(url, prefix="cisa_")))

    # Direct PDF links on the index page
    for tag in soup.find_all("a", href=True):
        href: str = tag["href"]
        if "/sites/default/files/" in href and href.lower().endswith(".pdf"):
            _add(href)

    # Visit individual advisory pages (AA## pattern) for their PDF attachments
    advisory_hrefs = [
        tag["href"]
        for tag in soup.find_all("a", href=True)
        if re.search(r"/cybersecurity-advisories/aa\d", tag["href"], re.I)
    ]

    for href in advisory_hrefs[:15]:
        if len(results) >= limit:
            break
        page_url = href if href.startswith("http") else urljoin(_CISA_BASE, href)
        page_soup = _get_html(client, page_url)
        if page_soup is None:
            continue
        for tag in page_soup.find_all("a", href=True):
            h: str = tag["href"]
            if h.lower().endswith(".pdf"):
                _add(h)
        time.sleep(0.5)  # polite crawl delay

    logger.info("CISA collection complete", count=len(results))
    return results


# ---------------------------------------------------------------------------
# Source 3: ENISA publications
# ---------------------------------------------------------------------------


def collect_enisa(client: httpx.Client, limit: int = 20) -> list[tuple[str, str]]:
    """Scrape ENISA publications page for direct PDF download links.

    ENISA hosts threat landscape, incident analysis, and sector reports as
    public PDFs linked directly from their publications listing.
    """
    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    soup = _get_html(client, _ENISA_INDEX)
    if soup is None:
        logger.warning("ENISA index unreachable, skipping source")
        return results

    for tag in soup.find_all("a", href=True):
        if len(results) >= limit:
            break
        href: str = tag["href"]
        if not href.lower().endswith(".pdf"):
            continue
        url = href if href.startswith("http") else urljoin(_ENISA_BASE, href)
        if url not in seen:
            seen.add(url)
            results.append((url, _safe_filename(url, prefix="enisa_")))

    logger.info("ENISA collection complete", count=len(results))
    return results


# ---------------------------------------------------------------------------
# Downloader
# ---------------------------------------------------------------------------


def download_pdf(
    client: httpx.Client,
    url: str,
    dest: Path,
    dry_run: bool,
) -> bool:
    """Stream-download one PDF to *dest*. Returns True on success."""
    if dest.exists():
        logger.info("already present, skipping", file=dest.name)
        return True

    if dry_run:
        print(f"    [dry-run] {url}")
        return True

    try:
        with client.stream("GET", url) as resp:
            resp.raise_for_status()

            content_type = resp.headers.get("content-type", "")
            if "pdf" not in content_type and not url.lower().endswith(".pdf"):
                logger.warning(
                    "not a PDF response, skipping",
                    url=url,
                    content_type=content_type,
                )
                return False

            data = bytearray()
            for chunk in resp.iter_bytes(chunk_size=65_536):
                data.extend(chunk)
                if len(data) > _MAX_FILE_BYTES:
                    logger.warning(
                        "file exceeds size cap, skipping",
                        url=url,
                        cap_mb=_MAX_FILE_BYTES // 1_048_576,
                    )
                    return False

        dest.write_bytes(bytes(data))
        logger.info("saved", file=dest.name, kb=len(data) // 1024)
        return True

    except Exception as exc:
        logger.warning("download failed", url=url, error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run(
    out_dir: Path,
    max_files: int,
    timeout: float,
    dry_run: bool,
    sources: list[str],
) -> None:
    configure_logging("INFO")
    out_dir.mkdir(parents=True, exist_ok=True)

    client = _make_client(timeout)
    candidates: list[tuple[str, str]] = []

    step = 1
    total_steps = len(sources)

    if "curated" in sources:
        print(f"[{step}/{total_steps}] Loading curated FBI IC3 reports ...")
        before = len(candidates)
        candidates.extend(collect_curated())
        print(f"      +{len(candidates) - before} entries.\n")
        step += 1

    if "cisa" in sources:
        print(f"[{step}/{total_steps}] Scraping CISA advisory index ...")
        before = len(candidates)
        candidates.extend(collect_cisa(client, limit=max_files))
        print(f"      +{len(candidates) - before} CISA entries found.\n")
        step += 1

    if "enisa" in sources:
        print(f"[{step}/{total_steps}] Scraping ENISA publications index ...")
        before = len(candidates)
        candidates.extend(collect_enisa(client, limit=max(10, max_files // 3)))
        print(f"      +{len(candidates) - before} ENISA entries found.\n")

    # Deduplicate by URL, preserve source order
    seen_urls: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for url, name in candidates:
        if url not in seen_urls:
            seen_urls.add(url)
            deduped.append((url, name))

    to_fetch = deduped[:max_files]
    action = "Would download" if dry_run else "Downloading"
    print(f"{action} up to {len(to_fetch)} PDFs → {out_dir}\n")

    ok = skipped = failed = 0
    for i, (url, filename) in enumerate(to_fetch, 1):
        dest = out_dir / filename
        label = f"[{i:02d}/{len(to_fetch)}]"

        if dest.exists():
            print(f"  {label} SKIP  {filename}")
            skipped += 1
            continue

        print(f"  {label} {'LIST' if dry_run else 'GET '}  {filename}")
        if download_pdf(client, url, dest, dry_run=dry_run):
            ok += 1
        else:
            failed += 1

        if not dry_run:
            time.sleep(0.3)  # rate-limit outbound requests

    client.close()

    sep = "─" * 52
    print(f"\n{sep}")
    if dry_run:
        print(f"  [dry-run] {ok} PDFs would be downloaded to {out_dir}")
    else:
        print(f"  ✓ {ok} downloaded   {skipped} already on disk   {failed} failed")
        print(f"  Output: {out_dir.resolve()}")
    print(f"{sep}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download recent public CTI PDF reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  python scripts/fetch_pdfs.py\n"
            "  python scripts/fetch_pdfs.py --max 30\n"
            "  python scripts/fetch_pdfs.py --sources cisa enisa\n"
            "  python scripts/fetch_pdfs.py --dry-run\n"
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_DEFAULT_OUT,
        help=f"Destination directory (default: {_DEFAULT_OUT})",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=_DEFAULT_MAX,
        dest="max_files",
        help=f"Maximum PDFs to download (default: {_DEFAULT_MAX})",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=_DEFAULT_TIMEOUT,
        help=f"HTTP timeout in seconds (default: {_DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be downloaded without saving any files",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["curated", "cisa", "enisa"],
        choices=["curated", "cisa", "enisa"],
        metavar="SOURCE",
        help="Sources to pull from: curated cisa enisa (default: all three)",
    )
    args = parser.parse_args()
    run(
        out_dir=args.out_dir,
        max_files=args.max_files,
        timeout=args.timeout,
        dry_run=args.dry_run,
        sources=args.sources,
    )


if __name__ == "__main__":
    main()
