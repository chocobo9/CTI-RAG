from pathlib import Path

from rag_cti.connectors.abuse_export_collection import DEFAULT_RAW_DATA_ROOT
from rag_cti.connectors.orkl_collection import DEFAULT_ROOT as ORKL_CONNECTOR_ROOT
from scripts.collect_cisa_advisories import DEFAULT_ROOT as CISA_ROOT
from scripts.collect_malpedia_snapshot import DEFAULT_ROOT as MALPEDIA_ROOT
from scripts.collect_orkl import DEFAULT_ROOT as ORKL_ROOT
from scripts.collect_threatfox import DEFAULT_ROOT as THREATFOX_ROOT
from scripts.collect_urlhaus import DEFAULT_ROOT as URLHAUS_ROOT
from scripts.ingest import _DEFAULT_SPARSE_VOCAB
from scripts.validate_source_collections import REPORT_DIR, SOURCE_ROOTS


def test_source_collectors_default_to_complete_packages_under_raw() -> None:
    expected = {
        "cisa": Path("data/raw/cisa"),
        "malpedia": Path("data/raw/malpedia"),
        "orkl": Path("data/raw/orkl"),
        "threatfox": Path("data/raw/threatfox"),
        "urlhaus": Path("data/raw/urlhaus"),
    }

    assert CISA_ROOT == expected["cisa"]
    assert MALPEDIA_ROOT == expected["malpedia"]
    assert ORKL_ROOT == expected["orkl"]
    assert THREATFOX_ROOT == expected["threatfox"]
    assert URLHAUS_ROOT == expected["urlhaus"]
    assert ORKL_CONNECTOR_ROOT == expected["orkl"]
    assert DEFAULT_RAW_DATA_ROOT == Path("data/raw")
    assert SOURCE_ROOTS == {
        "orkl": expected["orkl"],
        "urlhaus": expected["urlhaus"],
        "threatfox": expected["threatfox"],
    }


def test_derived_collection_assets_do_not_default_to_data_root() -> None:
    assert REPORT_DIR == Path("data/raw/reports")
    assert _DEFAULT_SPARSE_VOCAB == Path(
        "data/processed/sparse_vocab/sparse_vocab.json"
    )
