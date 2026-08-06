# EviTRAIL Enrichment Delivery Update

## Frozen inputs

- OTX dataset: 4,136 Events and 2,704 source claims.
- Additional-sources dataset: 19,276 Events and 52,550 source claims.
- Actor vocabulary: 484 actors; frozen vocabulary and registry hashes are preserved.
- Historical 17,454, 10,253, and 8,597 populations were not used.

## Published layout

- `no_enrichment/`: the previously published factual baseline.
- `pdns/`: OTX enrichment with bounded passive DNS only.
- `pdns_asn/`: the same pDNS layer plus terminal IP-to-ASN facts.

The `pdns` and `pdns_asn` archives each contain both datasets and the frozen
vocabulary. They are data-only artifacts; no model training was run as part of
this collection and projection task.

## Collection result

All 190,984 planned OTX queries reached a terminal ledger state with pending = 0
and a maximum of three attempts:

| Terminal state | Count | Share | Meaning |
|---|---:|---:|---|
| `written` | 130,524 | 68.343% | HTTP 200 response stored as raw evidence |
| `empty` | 11,666 | 6.108% | HTTP 200 response with no usable pDNS/ASN value |
| `unsupported` | 1,258 | 0.659% | Permanent unsupported/invalid response |
| `permanent_error` | 7 | 0.004% | Permanent HTTP error |
| `retry_exhausted` | 47,529 | 24.886% | No usable response after bounded retries, mostly timeouts |

The `retry_exhausted` rows are complete audit records, but they are not successful
OTX observations. Raw responses, planned queries, Stage-2 selection, and the
complete ledger remain in the separate local audit root and are not bundled into
the model delivery archives.

## Projected facts

- OTX / pDNS: 280,916 pDNS edges.
- OTX / pDNS+ASN: the same 280,916 pDNS edges plus 25,965 ASN edges.
- Additional / pDNS: 411,424 pDNS edges.
- Additional / pDNS+ASN: the same 411,424 pDNS edges plus 49,250 ASN edges.

The four logical variants passed frozen-file, provenance, relation, pDNS-layer
reuse, and terminal-ledger validation. A representative EviTRAIL reader smoke
also passed on the additional-sources pDNS+ASN handoff.
