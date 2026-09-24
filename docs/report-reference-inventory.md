# Local `report.html` reference inventory

Reference: `C:/Users/molpa/Documents/Inpred/report.html` (964 lines; `prototype/report.html` is byte-identical). This is a product and interaction reference, **not** an authoritative clinical data source. The approved OUS fixture and validated contracts remain the sources of report facts. This inventory is for Task 16 and informs the UI projection and acceptance tests.

## Controls and states

| Surface | Original controls | Important states and parity checks |
| --- | --- | --- |
| Sticky top bar | Sample/status; edit-mode toggle; `Lagre`; JSON load; reset; dirty indicator | Editing stays local until `Lagre` succeeds against the database; JSON transfer is separately labeled; reset requires confirmation; FINAL is read-only. The original instead writes every change to `localStorage` and makes `Lagre` download JSON. |
| Five tabs | Key findings, Variant review, CNV plots, Sequencing QC, Tumour board report | Selection preserves the user's working copy; keyboard tab semantics and focus must be reliable. |
| Key findings | TMB and MSI values, TMB gauge, LocalApp TMB, include/exclude counts, CNV/fusion/splicing cards, editable patient strip, protein-coding variant summary | Value editing and gauge dragging update dependents without losing focus. Gauge also needs a keyboard equivalent. Unavailable source values are labeled, not copied from the demo. |
| Variant review | Search; six chips (all/include/exclude/pathogenic/unsure/unreviewed); sortable table; IGV and class/report comments; judgement buttons; progress; confirmed bulk include/exclude | Search/chips/sort do not alter identities. Bulk actions affect only eligible unreviewed variants. The original's single `j` mixes include/exclude with pathogenic/unsure; the new contract keeps reporting decision and clinical classification independent. |
| CNV plots | Nine labeled plot buttons, switcher, caption, click-to-enlarge lightbox | Only declared images are selectable. Focus returns after closing enlargement. Original plot labels A1–D1 are a presentation convention, not evidence for missing data. |
| Sequencing QC | Threshold/status cards, source plot, enlargement | Structured `qcMetrics` or explicit unavailable state; no fabricated PASS/FAIL or threshold. |
| Tumour board | Three editable note boxes, sign-off name/date/status, `Generate MDT report`, `Mark final` | Print contains only included reviewed findings. FINAL requires saved latest revision and confirmation; same authorized biologist may finalize; no free final/draft toggle. |

## Source-field map for the approved OUS fixture

| Reference display field | Validated source or planned representation |
| --- | --- |
| Sample, patient pseudonym, reference build, run | `ReportData.sample.sampleId`, `.patientPseudonym`, `.referenceBuild`, and `run.runId`. |
| TMB `14.9 (19)`, MSI `4.13 (5/121)` | Numeric `ReportData.biomarkers` values `14.9 mut/Mb` and `4.13 %`; original strings are retained as `source.rawValue`. The UI may show the raw string only with its provenance. |
| Gene, location, DNA/protein change, tumour AF | `ReportData.variants`; all 30 source occurrences are retained, including two TERT occurrences with one `variantId` and distinct `occurrenceId` values. |
| Coding status, IGV/Run QC, variant comments and judgments | Some attributes appear in the prototype's raw variant rows but are not all mapped to `ReportData`. Review inputs belong in `ReviewState`; additional source columns require a traced, validated contract extension. Never infer a decision from a display tier. |
| CNV and sample-QC images | Three declared, SHA-256-verified attachments: one CNV PDF and two QC PNGs. Structured QC metrics are absent in this fixture. |
| Patient sex/age, tumour type, sample type/material, tumour content, study/hospitals, batch, pipeline | Present in prototype sample JSON or its slide-derived data, but absent from the approved `ReportData` mapping. Show unavailable until a source and policy-approved mapping are added. The pseudonym is **not** a substitute for a clinical identity field. |
| LocalApp TMB, TMB/MSI category, amplifications, fusions/splicing, detailed QC thresholds | Reference/prototype displays values and derived labels not currently traceable to the four mapped sources. Do not transplant their demo values, `1.27 Mb` denominator, category cutoffs, or green/red QC outcomes into `ReportData`. |
| Summary, biomarker/therapeutic context, additional comments, sign-off | Human `ReviewState` v2. A v1 `reportNotes` value migrates to `notes.importedLegacyNote`, separate from the three new fields. |

## UI projection contract

`pronto_report.renderers.projection.project_reference_ui` accepts validated, immutable `ReportData` and optional `ReviewState` snapshots. It returns JSON-ready UI data; it does not mutate either contract or infer missing clinical facts. Each displayed fact has an `availability` state, value, and source. Sample/run facts carry `REPORT_PROVENANCE` (report-level source files, **not** a claim of field-level lineage); biomarker and variant facts retain their more specific source references. Missing reference fields are `UNAVAILABLE` with no value or source. The frontend must render that state explicitly.

Variant rows are keyed by `occurrenceId`, while their human review is joined by `variantId`. Annotated facts remain separate from core fields, so an annotation cannot overwrite a gene or allele-frequency value. Value corrections remain a separate list with original value, corrected value, reason, author, and timestamp; projection never replaces the source fact. The validator enforces the audit fields before data reaches this function. The projector rejects duplicate biomarker IDs and unknown/duplicate variant reviews rather than silently hiding them.

## Current key-findings working copy

In a DRAFT preview, **Edit mode** reveals local correction controls for source-backed TMB/MSI and the supported `sample.tumourType`/`sample.specimenType` fields. A correction keeps the original source value visible and requires a reason; it is held only in page memory. The legacy JSON download is disabled while source corrections are pending because that file cannot yet represent/save them reliably. The top-bar **Lagre** button remains disabled until the authenticated database workflow in Tasks 24–27 is implemented. Unmapped LocalApp TMB, CNV/amplification, fusion/splicing and patient-context fields remain explicitly unavailable, rather than accepting invented values.

The key-findings table lists source occurrences with a non-empty `proteinChange`, retaining their occurrence IDs and source allele frequency. The reference's "coding status" filter is not reproduced: that field is not in the validated contract. Review decisions are kept in Variantgjennomgang instead of being inferred from source annotations.

Variantgjennomgang now filters source occurrences by search, reporting decision, or clinical classification while progress counts unique `variantId` values. Duplicate source occurrences retain distinct `occurrenceId` values and share one human review. Reporting decision, clinical classification, IGV assessment, and comment are separate review fields. A DRAFT bulk action affects only visible, unreviewed unique variants after confirmation; unlike the original prototype, it does not claim to target only coding variants because validated `Coding_status` is unavailable. No bulk action is shown for FINAL or read-only reports. These review interactions are page-memory changes until the authenticated save flow is available.

The tumour-board panel edits the three distinct ReviewState v2 note fields in page memory. A v1 review is migrated to v2 for this working copy; its legacy text is displayed separately and never reinterpreted as a summary. Included findings are refreshed from the current review controls, deduplicated by `variantId`, and printed with the current notes on an A4 landscape MDT view. Draft printouts state that they are unsigned working copies. Reviewer identity and FINAL status are displayed but cannot be altered locally; finalization remains the authenticated server action in Task 28.

## Follow-up visual baseline

The original HTML file is local and outside the repository; neither the file nor masked screenshots should be committed automatically. A browser navigation to its `file:` URL was blocked by the active browser security policy. No alternative browser route was used to bypass that restriction. Desktop/mobile screenshots therefore remain an open Task 16 item for an approved, permitted capture workflow or user-supplied screenshots. Code-level interaction inventory and source-gap checks can proceed meanwhile; visual parity cannot be signed off without the screenshots and clinical-user review.
