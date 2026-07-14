# OTX Plan Evidence Trace

## Primary Sources

- `docs/reference/trail.pdf`: Isaiah J. King et al., *TRAIL: A Knowledge
  Graph-based Approach for Attributing Advanced Persistent Threats*, ICDE 2025.
- `docs/reference/sample_code.py`: local implementation that claims to reproduce
  the TRAIL collection and graph workflow.
- `docs/sp.pdf`: *APT to Disagree*, a separate commercial-feed attribution
  comparison. It is not the source for the TRAIL OTX/Event graph.

## TRAIL-Backed Claims

| Claim | Primary evidence |
|---|---|
| TRAIL collects raw JSON reports containing IOCs and an attributed threat actor | TRAIL page 3, system overview |
| Each report is represented as a central Event node connected to reported IPs, URLs, and domains | TRAIL pages 3 and 5, Figure 2 and Table I |
| OTX is searched for Events tagged with APT names and aliases | TRAIL page 4, Section IV-A |
| The collection result first becomes a list of Event ids and associated APTs | TRAIL page 4, Section IV-A |
| Events with multiple valid APT aliases are ignored unless all aliases map to the same APT | TRAIL page 4, Section IV-A |
| The original TKG includes only APTs with at least 25 attributed Events | TRAIL page 4, Section IV-A |
| The original 4,512 Events were created between February 2015 and May 2023 | TRAIL page 4 |
| Primary reported IOCs are linked directly to Event; secondary IOCs are discovered through analysis and are not directly associated with Event | TRAIL pages 3-4 |
| Enrichment uses passive DNS and other analysis, is bounded to two hops, and produced 75% secondary nodes | TRAIL page 4 |
| Graph relations include Event-InReport-IP/Domain/URL, IP-ARecord-Domain, IP-InGroup-ASN, URL-ResolvesTo-IP, URL-HostedOn-Domain, and Domain-ResolvesTo-IP | TRAIL page 5, Table I |
| Passive DNS provides source-backed first/last-seen information for DNS resolutions | TRAIL page 5 example and Table I context |

## Local Implementation Support

`sample_code.py` follows the main TRAIL shape:

- It declares Event-InReport-IP/Domain/URL and DNS/ASN relations near the top of
  the file.
- It searches OTX with APT names and MITRE aliases.
- It implements the paper's single-APT tag filter.
- It writes Event/IOC graph records and then performs pDNS/ASN enrichment.

The code is evidence of the group's intended implementation, but where it
differs from the paper or project requirements it is not treated as ground
truth.

## Explicit Project Deviations

| Project decision | Difference from TRAIL | Reason |
|---|---|---|
| Preserve multi-actor and ambiguous Pulses | TRAIL filters them before graph inclusion | They are required evidence for ambiguity research |
| Preserve OTX `adversary` as source claims | TRAIL represents each Event with a single APT feature | Do not promote one source field or query match to final attribution |
| Do not compute confidence or final attribution during collection | TRAIL later trains attribution models | Outside current data-gathering scope |
| Do not run enrichment in the current phase | TRAIL treats enrichment as central to the final TKG | Enrichment is deferred support evidence, not Event discovery |
| Use Event-level indicator summaries instead of materializing all occurrences | TRAIL's final graph materializes primary and secondary IOC relations | Local OTX population contains 55.7 million embedded occurrences and requires a bounded consumer purpose |

## Engineering Adaptations, Not Paper Claims

The following phase boundaries are local engineering choices:

1. `discovery`: search APT names/aliases and write a candidate Event manifest.
2. `detail`: acquire or reuse one raw Pulse per candidate.
3. `source normalization`: preserve source actor claims without final inference.
4. `indicator summary`: record scale and source-time coverage without full
   occurrence materialization.

TRAIL describes collection followed by IOC analysis/enrichment, but it does not
specify these resumable collector phases. They exist to control API, storage,
and processing costs while retaining raw evidence.

## Time Policy

TRAIL reports that its selected Events were created between February 2015 and
May 2023. This is a property of the paper's collected population, not a required
filter for the current project.

The current OTX run has `since=null` and `until=null`. It is therefore correctly
described as unfiltered by time. The project preserves source timestamps and
collection timestamps and publishes a dataset temporal profile so future
consumers can derive any desired window without redefining source activity
intervals.

## Supported Current Objective

The evidence-supported, project-approved objective is:

1. Start with known MITRE APT groups and aliases.
2. Search OTX for related Event/Pulse candidates.
3. Preserve every candidate and discovery path, including ambiguous and
   multi-actor records.
4. Acquire or reuse raw Pulse detail once per candidate.
5. Preserve Event metadata, source actor claims, original timestamps, and an
   indicator summary.
6. Defer full Event-IOC materialization and enrichment until a bounded consumer
   need is defined.
