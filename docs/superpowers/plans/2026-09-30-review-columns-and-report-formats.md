# Variant review og to rapportformater — implementasjonsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after the open product choices are resolved. Steps use checkbox (`- [ ]`) syntax for tracking. This document does not request subagent execution.

**Goal:** Gjøre hele det avtalte Excel-datagrunnlaget tilgjengelig for review, legge til VUS/Review/Exclude/highlight og generere to rapportlayout fra de samme lagrede vurderingene og tekstene.

**Architecture:** Utvid versjonerte kilde- og review-kontrakter uten å overskrive historikk. La én rapportprojeksjon velge inkluderte/fremhevede funn og effektive korrigerte verdier. To separate maler eier presentasjonsformatet og den stående rapporten; Django autoriserer og logger eksport fra eksakt lagret revisjon.

**Tech Stack:** Python, Django, JSON Schema, Jinja/HTML, vanilla JavaScript/CSS, pytest og eksisterende Playwright-tester. PPTX/PDF-rendering velges etter filformatavklaring.

**Spec:** [2026-09-30-review-columns-and-report-formats-design.md](../specs/2026-09-30-review-columns-and-report-formats-design.md)

**Status:** Utkast til gjennomgang. Ingen implementasjonsoppgaver er fullført. Planen bygger på commit `a4b188c` i eksisterende `feature/report-review-workspace`.

## Global Constraints

- Arbeid i den eksisterende `feature/report-review-workspace`-worktree; ikke i gammel prototype eller eldre hovedutsjekk. Kontroller oppdatert HEAD før implementasjon.
- Bevar eksplisitt Save, revisjoner, FINAL-lås, gamle audit-rader og IGV-funksjoner. Ingen nye automatisk lagrede kliniske vurderinger.
- Nye tekster i produktet er engelske; planlegging og brukerdialog kan være norsk.
- Pasientdata, vedlagte rapportbilder og nye arbeidsbøker skal ikke legges i Git. Bruk eksisterende godkjente fixtures og syntetiske data for tester.
- Eldre kontrakter forblir lesbare. PATHOGENIC blir ikke stilltiende ONCOGENIC. Ikke oppfinn behandlinger, kliniske terskler eller negative analyser.
- Eksport bruker én lagret revisjon, inklusive lagrede korreksjoner; HTML/Office/PDF genereres aldri ved å kopiere arbeidsflatens DOM.
- Kjør målrettet RED/GREEN per logikkendring, relevante regresjoner og full kontroll før integrering. Ingen tester slettes/svekkes for å gjøre migrering grønn.
- Lag en ny isolert demo for manuell kontroll. Ikke reset, reseed eller bytt den åpne demoens database. Ingen produksjonsutrulling eller merge inngår.

## Review Focus

1. Samme variant i flere kildeforekomster: alle kildeverdier bevares, alle kontroller synkroniseres, ett rapportfunn uten vilkårlig annotasjonsvalg. Testes i oppgave 2, 3 og 5.
2. Uklassifisert og eldre FINAL-vurdering: ingen ny klinisk mening eller opplåsing gjennom migrering. Testes i oppgave 1 og 3.
3. Exclude med tidligere highlight/kommentar: gjenoppretting taper ikke data, begge eksportene utelater funnet. Testes i oppgave 3 og 5.
4. Brede Excel-ark, tomme verdier, nye/dublette overskrifter og formler: ingen stille tap eller formelkjøring. Testes i oppgave 2 og 3.
5. Lange tekster, mange varianter og eksport-retry etter nyere lagring/malendring: ingen avkutting eller bytte av revisjon/layout. Testes i oppgave 5, 6 og 7.

## Avhengigheter og prioritet

| Leveranse | Oppgaver | Svar som trengs |
| --- | --- | --- |
| Nye vurderingsfelt og synkronisering | 1, 3 | VUS = Review, Include-regel, eldre klassifikasjoner |
| Full kildevisning | 2, 3 | Hvilken Excel-fil, ark og autoritativt variantutvalg |
| Felles rapporttekster og kuraterte rader | 1, 4 | Tekstfelter og kilde for klinisk evidens |
| To rapportlayout | 5 | Originalmal/fullt bildeinnhold; presentasjonens sidestørrelse |
| To komplette eksportknapper | 6 | PPTX/PDF eller HTML; DRAFT-policy |
| Klar demo for brukerens gjennomgang | 7 | Forrige leveranser verifisert |

Dette er omtrent sju reviewbare leveranser, med kildeimport og side-/eksportlayout
som de mest usikre. Antall linjer eller et tidsløfte før Excel og mal er avklart
ville gi et misvisende estimat.

## Oppgave 1: ReviewState v3 og tapsfri migrering

**Files:** Create `pronto_report/schemas/review-state-v3.schema.json`. Modify `pronto_report/models.py`, `serialization.py`, `validation.py`, `migration.py`, `review/service.py` og review-seeding i `pronto_web/reports/management/commands/`. Test i eksisterende `pronto/tests/reporting/test_review_migration.py`, `test_schemas.py`, `test_serialization.py`, `test_review_service.py` og Django lagringstester.

**Interfaces:** `migrate_review_state_to_v3(review: ReviewState) -> ReviewState` tar v1/v2/v3 uten mutasjon. v3 har `clinicalClassification` UNCLASSIFIED/BENIGN/VUS/ONCOGENIC, boolsk `reportHighlight` på variantReviews og valgfritt read-only `legacyClinicalClassification` for tidligere klasser. Nye note-nøkler: `history`, `variantDescription`, `references`, `followUp`, `assayMethods`; eksisterende notater beholdes. `biomarkerReviews` knytter reportHighlight til kjent metricId. `reportEvidence` lagrer manuelle rader med stabil rowId, section, target og tekstfelter; nøyaktige radfelter fastsettes fra avtalt mal i oppgave 4.

- [ ] Skriv tester for validert v3, ugyldige klasser og ekte booleans, v1→v3/v2→v3, bevarte kommentarer/attribution/corrections, legacy-klasser og låst FINAL. Assert at inputdokumentet og tidligere revisjon ikke endres.
- [ ] Kjør `python -m pytest -q pronto/tests/reporting/test_review_migration.py pronto/tests/reporting/test_schemas.py pronto/tests/reporting/test_serialization.py`; bekreft at nye tester feiler på manglende v3.
- [ ] Implementer schema-dispatch for eksplisitte kjente versjoner, serialisering og migrering. Gi nye felter tomme/false-standarder; ikke bruk fravær av review som godkjent klasse. Behold eksisterende historiske v1/v2-rendering.
- [ ] Oppdater service til å akseptere avtalte v3-utkast, sjekke biomarker/finding-/variant-ID-er, beskytte legacy-felt og bevare base-revision-kontroll. Reset lager et tomt v3-utkast med bevarte read-only importnotater; FINAL forblir låst.
- [ ] Kjør målrettede review-/Django-tester for Save, Reset og Finalize; lag én fokusert commit når kontrollene passerer.

## Oppgave 2: Fullstendige kildekolonner og Excel-import

**Files:** Create `pronto_report/adapters/workbook.py`, `pronto_report/schemas/report-data-v2.schema.json`, `pronto/tests/reporting/test_workbook_adapter.py`. Modify `pronto_report/adapters/pronto_output.py`, `models.py`, `serialization.py`, `validation.py`, `renderers/projection.py` og `docs/report-data-fixture.md`. Extend `test_pronto_output_adapter.py`, `test_reference_projection.py`, `test_models.py`.

**Interfaces:** `read_source_workbook(path: Path) -> SourceWorkbook` leser valgte kilder uten å kjøre formler. `SourceWorkbook` gir tabell-ID, ark-/filmetadata, ordnede kolonner med columnId/label/position og rader med ordnede celler og kildehenvisning. ReportData v2 legger til `sourceTables`; variantforekomster refererer til tableId/rowId. `project_reference_ui(...)` gir sourceTables og alle kildeverdier til Details/All source columns. Strukturert CNV/RNA-import krever eget dokumentert feltkart fra den faktiske kilden, i samme leveranse hvis disse arkene er del av bestillingen.

- [ ] Kartlegg ark og header fra riktig arbeidsbok, og lag `docs/source-workbook-inventory.md`: kolonne, kilde, datatype, mapping, manglende verdi og stabil identitet. Sammenlign hele den avtalte kilden, ikke bare dagens 13 annotasjoner. Merk hvilke metadata/CNV/RNA-felter som mangler i eksisterende kontrakt.
- [ ] Lag en syntetisk arbeidsbok i testens midlertidige mappe, med nye/dublette kolonnenavn, tomme celler, multiline, dato, tall med ledende nuller, formel og to forekomster av samme variant. Assert at alle kolonner/celler og rekkefølge bevares, formelen ikke evalueres og source-hash stemmer.
- [ ] Kjør `python -m pytest -q pronto/tests/reporting/test_workbook_adapter.py pronto/tests/reporting/test_pronto_output_adapter.py`; forvent RED for manglende adapter/full kildebevaring.
- [ ] Implementer import med eksplisitt arkvalg og fil-/størrelsesgrenser som avviser hele importen med en forklaring fremfor å kutte kolonner. Avklar manglende cached formelverdier. Importér eksisterende TSV gjennom samme kildebevaring, og behold v1-innlesing.
- [ ] Knyt review til stabile ID-er og kildeforekomster. Avvis eller diagnostiser tvetydig matching; ikke flytt vurderinger etter sortering eller en endret radrekkefølge. Bekreft at nye kildekolonner ikke blir ubegrunnede clinicalClassification-verdier.
- [ ] Rerun adapter-, schema-, identitets- og projeksjonstester. Sammenlign kolonne- og celletelling med testarbeidsboken; dokumenter dekning og commit leveransen.

## Oppgave 3: VUS, Review, Exclude og highlight i begge faner

**Files:** Modify `pronto_report/renderers/html.py`, `templates/report/key-findings.html`, `templates/report/variant-review.html`, `static/report.js`, `static/report.css`. Extend `pronto/tests/reporting/browser/test_variant_workflow.py`, `test_save_flow.py` og `test_reference_shell.py`.

**Interfaces:** Ett oppdateringspunkt `setVariantReview(variantId, patch)` oppdaterer arbeidskopien og alle kontroller i Key findings/Variant review. `isIncluded(activity)` og `isHighlighted(activity)` følger sannhetstabellen i designet. Checkboxer bruker data-review-field og type checkbox med checked fra aktivitet; de lagrer ikke konkurrerende isVus/excluded-booleans.

- [ ] Skriv browsertester for Review = VUS ↔ VUS-checkbox, Benign/Oncogenic, tom starttilstand, highlight uten Include, Exclude/gjeninkludering og duplikate kildeforekomster. Assert klasse/kommentar beholdes ved Exclude, og at ikke-Include aldri fremheves i rapport.
- [ ] Kjør `python -m pytest -q pronto/tests/reporting/browser/test_variant_workflow.py`; bekreft at nye kontroller/regler mangler.
- [ ] Implementer engelske kolonnenavn og tilgjengelige checkbox-/select-labels. Oppdater filterchips/quick actions fra dagens Path/Uns til avtalte Review-verdier; unngå to motstridende klassifiseringskontroller. Behold Include separat og tydelig.
- [ ] Legg til ekskludert radstil med grå bakgrunn, lesbar tekst, gjennomstreking på data og tekstlig Excluded-status. Kontrollene skal fortsatt fungere med Tab/Space og ha lesbart fokus.
- [ ] Legg til All source columns-visning og komplette Details. Søk i alle importerte felter, og bevar Include/Exclude gjennom søk/sortering. Ikke la brede kildeark ødelegge kompakt standardvisning.
- [ ] Utvid input-lock under Save/Reset/Finalize/eksport til nye checkboxer. Verifiser Save→reload, mislykket Save, Reset og FINAL-read-only for alle nye felter. Rerun browser- og shell-tester ved 320/768/1024/1440 px; commit.

## Oppgave 4: Felles rapporttekster og evidensrader

**Files:** Modify `pronto_report/templates/report/tumour-board.html`, `renderers/html.py`, `static/report.js`, v3-schema fra oppgave 1 og `review/service.py`. Create focused `pronto/tests/reporting/test_report_fields.py`; extend `browser/test_tumour_board.py` og Django-save-tester.

**Interfaces:** Bruk `review.notes` for de åtte rapporttekstfeltene i designets tabell. Bruk `runQcAssessment.comment` for QC-tekst. `reportEvidence` har seksjonene PRESENTATION_CONTEXT/ACTIONABILITY/TRIAL/FOLLOW_UP; rader knyttes til variantId, metricId/findingId eller hele rapporten. Radfelter fra referansen: sensitive/resistant, GoF/LoF, EMA patient/other tumour; alteration, matchLevel, treatment, escat, source; trialNameNumber, phase; followUp, remark. Kilder/ID-er valideres; manuell tekst merkes som reviewerinnhold.

- [ ] Skriv tester for hver note og evidensseksjon: lagring, rehydrering, slettet rad, stabil rowId, ugyldig referanse og read-only legacy-tekst. Inkluder norsk Unicode, multiline og `<script>` som ufarlig tekst.
- [ ] Kjør `python -m pytest -q pronto/tests/reporting/test_report_fields.py pronto/tests/reporting/browser/test_tumour_board.py`; bekreft RED.
- [ ] Gjenbruk eksisterende Summary/Biomarker context/Additional og legg til History, Variant description, References, Follow-up og Assay/methods. Unngå parallelle tekstfelter for samme innhold.
- [ ] Legg til enkel Add row/Remove row-redigering for avtalte tabeller og nye highlight-kontroller for kildebaserte biomarkører/funn. Klargjør hvordan manuelt utfylte prøve-/analysedata skiller seg fra kildefakta.
- [ ] Save lagrer alt atomisk i v3; forhåndsvisning oppdateres lokalt uten database-write. Kontroller tomme felter, feltgrenser, ekskludert target og FINAL; rerun focused tests og commit.

## Oppgave 5: Felles eksportinnhold og to layoutmaler

**Files:** Create `pronto_report/renderers/export_projection.py`, `presentation_report.py`, `esmo_report.py`, `templates/exports/presentation.html`, `templates/exports/esmo.html`, `static/exports/presentation.css`, `static/exports/esmo.css`, `pronto/tests/reporting/test_report_formats.py`. Modify `renderers/summary_html.py` kun for avtalt kompatibilitet/gjenbruk.

**Interfaces:** `project_report_export(report: ReportData, review: ReviewState) -> dict[str, Any]` produserer reportId/revision/status, identifikasjon, effektive målinger, inkluderte varianter, highlightedFindings, notes, evidence og provenance. `render_presentation_html(export: Mapping[str, Any]) -> str` og `render_esmo_html(export: Mapping[str, Any]) -> str` gjengir samme modell. Malversjon er eksplisitt, første versjon `1.0`; ingen rå kilde-/reviewdict fra HTTP gjengis direkte.

- [ ] Skriv innholdstester som sammenligner variant-ID-er, notes og korrigerte TMB/MSI-/prøveverdier i begge formatene. Test INCLUDE+highlight, INCLUDE uten highlight, VUS, Exclude med highlight, Unreviewed og duplikate kilder med ulike annotasjoner. Begge formatene skal følge samme regler.
- [ ] Kjør `python -m pytest -q pronto/tests/reporting/test_report_formats.py`; forvent RED på manglende projeksjon/maler.
- [ ] Implementer felles projeksjon uten mutasjon og med stabile sorterings-/kildehenvisningsregler. Hold SNV/indel, CNV, RNA og biomarkører i riktige seksjoner; fravær blir Not provided, ikke negativt analysert.
- [ ] Bygg liggende mal med venstremetadata, hovedresultater/highlights/variantbeskrivelse og høyretabell. Alle inkluderte SNV/indel vises på hoved- eller fortsettelsessider. VUS får synlig markering og fotnote.
- [ ] Bygg stående Summary/Results/Biomarkers clinical evidence med referansens seksjoner og tabellhoder. Repeter identifikasjon, sideoverskrift og tabellhode på fortsettelsessider. Vis status/revisjon/signering uten å kopiere referansens pasienttekst.
- [ ] Render syntetiske tilfeller med 0/1/30/200 inkluderte varianter, lang varianttekst og 50 000 tegn i et notat. Kontroller at alt innhold er med, ingen overlapping finnes og skrifter forblir lesbare. Rerun format-/eksportregresjoner og commit.

## Oppgave 6: To auditerte eksportknapper og valgt filformat

**Files:** Create `pronto_web/reports/report_exports.py`, ny audit-modell og neste ledige Django-migrasjon, `pronto_web/reports/tests_report_exports.py`. Modify `models.py`, `views.py` ved behov, `pronto_web/urls.py`, `demo_access.py`, `pronto_report/renderers/html.py`, `static/report.js`. Create `pronto_report/renderers/presentation_pptx.py` / `report_pdf.py` bare dersom de formatene er valgt. Behold historisk `html_export_audit.py` og eksisterende rute.

**Interfaces:** `POST /reports/<report_id>/exports/` med `{schemaVersion: "1.0", reportId, revision, layout: "PRESENTATION" | "ESMO", fileFormat: "HTML" | "PPTX" | "PDF", declaredInitials, requestId}`. Bare avtalte layout/format-kombinasjoner tillates. Response er korrekt MIME attachment eller JSON-feil. Audit lagrer layout, filformat og templateVersion i tillegg til eksisterende identitets-/revisjonsfelter.

- [ ] Velg format fra brukerens svar. HTML: to selvstendige filer med inline CSS. PPTX: generer redigerbare tekstbokser/tabeller fra felles projeksjon med eksisterende PowerPoint-avhengighet. PDF: serverrender validerte maler med en avtalt lokal renderer, uten ekstern nettverkstilgang; renderer og fonter blir deklarerte runtime-avhengigheter.
- [ ] Skriv Django-tester for CSRF/tilgang/aktør, ugyldig format/layout/initialer/UUID, stale revision, no-store, MIME/filnavn, rendererfeil og rollback. Assert én audit per requestId, konflikt ved annet format/layout/aktør og samme historiske revisjon/mal ved retry etter ny lagring. Test også feil når opprinnelig malversjon ikke lenger kan gjengis.
- [ ] Kjør `python -m pytest -q pronto_web/reports/tests_report_exports.py`; forvent RED.
- [ ] Implementer atomisk snapshot-valg og audit, og generer hele filen før levering. Historiske audit-rader beholdes. Ikke loggfør at brukerens disk-lagring er fullført. Begrens renderarbeid slik at lange dokumenter gir tydelig feil fremfor delvis fil.
- [ ] Erstatt hovedknappen med Export presentation report / Export ESMO report. Behold JSON backup separat. Ulagret, saving/resetting/finalizing og pågående eksport blokkerer ny eksport. En feil beholder arbeidskopien og gir forståelig melding; aldri bland content-type fra feilresponse med en rapportfil.
- [ ] Test ren DRAFT/FINAL, dirty state, filnedlasting og nettverksfeil i nettleser. Kontroller valgt PPTX kan åpnes/redigeres, PDF har riktige sidestørrelser, eller HTML åpnes offline. Rerun eksisterende HTML-audit/demo-access-tester og commit.

## Oppgave 7: Integrert kontroll og demonstrasjon

**Files:** Extend `pronto/tests/reporting/browser/test_save_flow.py`, `test_variant_workflow.py`, `test_tumour_board.py` kun for gjenstående end-to-end-hull. Update `docs/demo-walkthrough-nb.md`, `docs/report-review-workspace.md` og faktisk kilde-/formatdekning.

**Interfaces:** Én ny isolert demo-ID/database, ikke brukerens eksisterende rapport. Endelig leveranse har to formatknapper og dokumenterte kildefelter; ingen påstand om klinisk validering eller identisk layout uten visuell sammenligning.

- [ ] Kjør `python -m pytest -q` med prosjektets runtime og relevante Django-testmoduler. Bekreft at eksisterende IGV/alignment, Save/Reset/Finalize, JSON-recovery og historisk HTML-eksport fortsatt passerer.
- [ ] I ny demo: Include flere varianter, sett de tre klassene, marker highlight, ekskluder et tidligere highlight, skriv alle rapporttekster/evidensrader og korriger TMB. Save→reload må bevare alt. Last ned begge formatene og sammenlign feltene med lagret revisjon.
- [ ] Test at en annen lagret revisjon gir konflikt uten å tape arbeidskopien; eksport etter Save gir riktig revisjon. Kontroller FINAL-lås og tillatt eksport. Inspiser auditens layout/format/mal/revisjon.
- [ ] Åpne eksportene offline, undersøk utskrift/sider og sammenlign med begge originalmalene. Kontroller lange tabeller/tekster og at ikke-inkluderte funn ikke lekker inn. Tab/Space/kontrollnavn fungerer ved 320/768/1024/1440 px; ingen konsollfeil.
- [ ] Dokumenter observerte resultater, kildebegrensninger og eventuelle visuelle avvik. Lag commit for dokumentasjonen og lever lokal demo og konkrete eksportfiler til brukerens gjennomgang. Gjør ingen merge eller publisering som del av denne planen.

## Selvkontroll av planen

- Alle fem punkter i bestillingen dekkes: Key findings (3), full kilde/Review/Exclude (1–3), presentasjon (4–6), stående rapport og to knapper (4–6), felles tekstfelter (1/4–6).
- Regler for utvalg og VUS har én sannhetskilde; biomarkør-highlights er også med.
- Hele Excel-filen er avhengig av virkelig kildekartlegging; generisk TSV-visning alene kalles ikke fullført.
- Begge layouter deler effektivt rapportinnhold og lagret revisjon; historiske kontrakter/audit og FINAL inngår i testene.
- Åpne spørsmål står i eget dokument, og formatspesifikk kode er ikke besluttet på brukerens vegne.
