# Reversible Provisional Ranking for Competing Attribution Hypotheses

Design disposition (2026-07-20): retained research for a later Assessment/R2 cycle. It does not define the current Orientation or read-only Workspace acceptance surface.

## Conclusion

Use **lineage-aware ordinal ACH** as the minimum method. Analysis of Competing Hypotheses (ACH) structures hypotheses, evidence, contrary evidence, diagnosticity, sensitivity, and change indicators. A deterministic reducer then produces ordinal bands rather than an accumulated score or an uncalibrated probability.

The LLM proposes candidate hypotheses, evidence-to-hypothesis comparisons, rationales, assumptions, gaps, and change indicators. Trusted implementation validates references, resolves source lineage, applies the ordinal reducer, versions the result, and records why the ordering changed.

## Primary-source findings

### CIA: ACH and structured analysis

The CIA Tradecraft Primer describes ACH as identifying reasonable competing hypotheses, arranging the same evidence against every hypothesis, focusing on disconfirmation, testing sensitivity to critical evidence, reporting weaker alternatives, and identifying future indicators that would change the assessment. Evidence consistent with every hypothesis has little diagnostic value. ACH improves the process and audit trail but does not guarantee a correct answer. [CIA, *A Tradecraft Primer*](https://www.cia.gov/resources/csi/static/955180a45afe3f5013772c313b16face/Tradecraft-Primer-apr09.pdf), [CIA, *Psychology of Intelligence Analysis*](https://www.cia.gov/resources/csi/static/9a5f1162fd0932c29bfed1c030edf4ae/Pyschology-of-Intelligence-Analysis.pdf)

### ODNI: judgments, uncertainty, and change conditions

ICD 203 requires analysts to distinguish underlying information, assumptions, and judgments; explain source and methodology quality; distinguish likelihood from confidence in the analytic basis; consider plausible alternatives and contrary information; and identify indicators that would alter a judgment. [ODNI, *ICD 203 Analytic Standards*](https://www.odni.gov/files/documents/ICD/ICD-203_TA_Analytic_Standards_21_Dec_2022.pdf)

### STIX 2.1: versions, revocation, lineage, and disagreement

STIX objects that support versioning use `modified` for new versions and `revoked` when the creator permanently considers an object invalid. `derived-from` records lineage but does not replace versioning. An `Opinion` lets another producer express and explain agreement or disagreement with an existing object. STIX provides useful transport primitives, but it does not define an attribution-ranking algorithm. [OASIS, *STIX 2.1 Errata 01*](https://docs.oasis-open.org/cti/stix/v2.1/stix-v2.1.html)

## Method comparison

| Method | Strength | Main risk | Recommended role |
|---|---|---|---|
| Weighted total | Fast and deterministic | Arbitrary weights, duplicated reporting, decisive contradiction can be offset, false precision | Retrieval or triage priority only |
| Bayesian | Explicit priors and updates | Requires calibrated priors, likelihoods, and dependency model; LLMs can invent numbers | Later specialist module with validated calibration data |
| ACH matrix | Forces alternatives, contradiction, diagnosticity, sensitivity, and change indicators | Matrix cells still require judgment; inconsistency counts are not probabilities | Default analytic structure |
| Ordinal ranking | Avoids false precision; supports ties and version comparison | Coarse; does not itself analyze evidence | Output layer for ACH |

## Architecture inference: minimum method

This section is a CTI-RAG design inference, not a requirement imposed by the cited standards.

1. Include all reasonable hypotheses, including `unknown` and relevant shared-infrastructure, compromised-infrastructure, or false-flag alternatives.
2. Bind the assessment to immutable versions of hypotheses, Evidence References, extraction records, source lineages, the Case Revision, and the assessment method.
3. For each evidence-hypothesis pair, record `consistent`, `inconsistent`, `neutral`, or `unknown`, a short rationale, and `high`, `medium`, or `low` diagnosticity.
4. Treat high-diagnostic contrary evidence as more important than the number of generic supporting mentions. Do not force a winner when evidence is insufficient.
5. Run sensitivity analysis on critical evidence and assumptions. Record what would change the ordering.
6. Produce ordinal bands such as `leading`, `plausible`, `weakened`, and `insufficient_information`. Ties and partial order are valid.
7. Store an immutable assessment version. Reassessment creates a new version and a change summary; it never edits the old basis.

## Source dependency and circular corroboration

The reviewed CIA, ODNI, and STIX sources do not prescribe an automatic circular-corroboration algorithm. The following are architecture inferences:

- Preserve the original object, derivation path, lineage roots, and an independence group for every material assertion.
- Reports that quote, summarize, re-export, or infer from the same upstream report belong to one lineage group for corroboration.
- Count independent lineages, not feed entries. Multiple copies improve traceability, not independent confirmation.
- Treat unknown dependency as unknown; do not assume independence.
- Collapse a provenance cycle into one evidence group. A derived assertion cannot corroborate its own upstream basis.
- Keep Source Reliability and Information Credibility separate; neither converts directly into attribution probability.

## Recalculation and withdrawal

Any of the following invalidates the current Provisional Assessment for further use: evidence addition, withdrawal, revocation, restoration, or material credibility change; source-lineage changes; entity merge or split; hypothesis addition, removal, split, or rewrite; critical-assumption changes; or matrix, reducer, model, or prompt version changes.

Recalculate from the currently valid versioned inputs. Do not add or subtract from an old total. Retain withdrawn evidence in the audit chain but exclude it from the new ordering. Each snapshot records its input digest, method versions, ordinal bands, matrix references, predecessor, and change explanation.

## LLM boundary

The LLM may generate and refine hypotheses, draft matrix cells and rationales, identify diagnostic evidence, surface gaps, challenge assumptions, and propose change indicators. It may not declare source independence, invent Bayesian priors or likelihoods, maintain a cumulative score, delete contrary evidence, overwrite revoked records, or publish an accepted Case attribution.

All LLM output remains a structured R2 proposal. Workspace validates citations and the bound evidence basis; Intelligence and Evidence owns reusable provenance and resource versions; Case Management owns accepted judgments and their history.

## Minimum implementation

Start with three to seven explicit hypotheses; versioned hypotheses and evidence; a C/I/N/U matrix plus ordinal diagnosticity; source-lineage grouping; a contradiction-first ordinal reducer; assumptions and change indicators; and immutable assessment snapshots with diffs. Defer general Bayesian attribution until validated base rates, likelihoods, and dependency models exist.

## Grill scenarios

1. Five feeds repeat one provider attribution while one independent local observation contradicts it. Should the five copies collapse into one lineage and the diagnostic contradiction remain visible rather than becoming a 5:1 vote?
2. A certificate association that made Actor A `leading` is revoked. Should the system invalidate the old assessment, recompute from active evidence, preserve the prior snapshot, and explain the changed ordering?
3. The original candidate set contains only Actors A and B; later evidence introduces shared infrastructure, false flag, and unknown actor. Should the old assessment be invalidated and the full matrix rebuilt rather than inserting the alternatives into an old score?
