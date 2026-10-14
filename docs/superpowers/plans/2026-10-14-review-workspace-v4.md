# Implementeringsplan: Review workspace v4

Design: `docs/superpowers/specs/2026-10-13-review-workspace-design.md`, godkjent av brukeren 14. oktober 2026.

Utføres i eksisterende arbeidsgren `feature/review-workspace-v4`. Eksisterende revisjoner bevares. Appen bruker Django, JSON Schema, vanlig JavaScript/CSS og ReportLab.

- [x] Genregister og standardvalg: `review/gene_registry.py`, `review/source_defaults.py`. Test eksakt medlemskap, kildekonflikter og manuelle overstyringer i `test_review_v4.py`.
- [x] Kontrakt: `review-state-v4.schema.json`, modeller, serialisering og validering. Behold lesing av v1–v3. Test CNV-rader, numeriske null/zero og annotasjoner.
- [x] Arbeidskladd: `reports/working_drafts.py`, WorkingDraft/WorkingDraftEvent og migrering 0010. Save erstatter én kladd med versjonskontroll; Finalize og PDF-eksport bevarer snapshots. Test tilgang, konflikt, gjenåpning, eksportretry og vedlegg i `test_working_draft.py`.
- [x] Tabeller: `renderers/review_v4.py`, `static/review-v4.js` og eksisterende variant-renderer. Felles Inc/Exc, CNV-topprader, Gain/Loss, Cytoband og QC-kommentarer.
- [x] Fokusvisning: samme levende tabell flyttes inn i en størrelsesjusterbar dialog med zoom, faste overskrifter og gen-/kromosomkolonner. Test lukking uten datatap og arbeidskommandoenes nettleserrespons i `browser/test_review_v4.py`.
- [x] PDF: utvid `report_pdf.py` med manuelle CNV-rader, Cytoband, Gain/Loss, Tumor_FC og seksjonskommentarer. Test begge eksportformatene.
- [x] Full pytest, Django request suite, separat kodegjennomgang og målrettet mutasjonstest. Visuell kontroll av tabell og begge PDF-er.
- [x] Backup og migrering på kopi av lokal SQLite-database.
- [x] Aktiver den nye arbeidsflyten lokalt, oppgrader databasen, start server og kontroller innloggingssiden.
- [ ] Commit, PR til `feature/igv-django-integration`, grønne CI-kontroller og merge.

Særlig kontroll: PDF-retry skal ikke gi en gammel klient et nytt lagringstoken; nylig lagret innhold skal være kilde ved gjenåpning; bilder skal tilhøre rapporten; ikke-endelige tall skal avvises; tidligere signerte versjoner skal være uendret.

Verifikasjon: full lokal suite 409 best�tt / 18 plattformavhengige hopp, Django 105 tester OK / 1 hopp; senere m�lrettet lagringssuite 9 best�tt og v4 tabell-/nettlesersuite 14 best�tt. Separat kodegjennomgang er avsluttet uten gjenst�ende blokkere. Migrering er verifisert p� kopi og live-databasen har beholdt alle 31 rapporter og 84 tidligere versjoner.
