# PRONTO desktop

PRONTO desktop samler filinnlasting, import til databasen, serverstart og åpning av HTML-rapportene i ett lokalt program. Appen bruker dagens rapportmotor, innlogging, vurderinger og historikk. Velg fem mapper fra én kjøring, kontroller filkoblingene, og trykk Prosesser og importer.

## Installere og starte

Pakk ut hele programmappen til en fast plass. Bruk PRONTO_INSTALL.cmd første gang og PRONTO_START.cmd ved senere oppstart. Startfilene støtter lokal Python og Python FELLES gjennom Ivanti. Faktisk Ivanti og tilgang på jobb-PC må kontrolleres der. Ikke flytt bare startfilene ut av programmappen.

Installer også Poppler slik at `pdfinfo` og `pdftoppm` finnes i PATH for den samme brukeren og Python-økten. Dette gjøres normalt gjennom lokal IT. Kontroller med `Get-Command pdfinfo, pdftoppm` i PowerShell, og start Python FELLES eller appen på nytt etter endring av PATH. Python-pakkene alene installerer ikke disse programmene. Diagnostikk viser status; import med PDF-plott avvises før rapporten lagres hvis verktøyene mangler.

Med prosjektets Python 3.14-miljø kan du også bruke:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe -m pronto_desktop
```

Dagens .local-web/config.json og private database gjenbrukes ved første oppstart når ingen ny datarot er valgt. Appen kopierer ikke rapporter fra en annen database og lager ingen demonstrasjonspasienter ved oppstart. Manglende tilgang til en valgt eksisterende database skal løses før videre bruk.

For en ny, separat installasjon eller testdatabase:

```powershell
.\.venv\Scripts\python.exe -m pronto_desktop --data-root 'C:\PRONTO-test' --port 8772
```

Velg en ny mappe for et tomt oppsett. Port 8772 er nyttig når den eldre rapportserveren allerede kjører på 8770. Valgt datarot huskes for neste oppstart. Bytte av database krever at appen startes på nytt. Appen flytter ikke den gamle databasen automatisk.

## De fem mappene

Velg fem forskjellige mapper i Importer. Appen undersøker undermappene; de fem mappene skal ikke ligge inne i hverandre. De trenger ikke ha bestemte navn. Filgjenkjenningen bruker kjente filnavn og kolonneoverskrifter.

Nåværende TSOPPI-profil trenger metadata, analysesammendrag, småvarianttabell og prøveoversikt. CNV, RNA og plott er tillegg som kobles til en bestemt prøve. Hver prøve vises med mangler eller tvetydige treff før den importeres. De ekte jobb-PC-mappene er ikke testet ennå, så andre filformater kan kreve en ny innlesingsprofil.

| Filrolle | Kjent grunnlag |
|---|---|
| Metadata | InPreD_PRONTO_metadata.txt med Sample_id, Sequencing_run_id og Study_id |
| Sammendrag | *_variant_summary.tsv med sample_id, TMB og MSI |
| Småvarianter | *_small_variant_table_forQC.tsv, ellers *_small_variant_table.tsv |
| Prøveliste | sample_list.tsv med prøve-ID og prøvetype |
| CNV | CNV_summary_table.csv eller tabell med de tilsvarende kolonnene |
| RNA | fusion_and_splice_variant_candidates_withQC.xlsx eller tilsvarende tabell |
| Plott | Prøvekoblede CNV/QC PDF eller PNG og eksplisitte RNA-domeneplott |

Kontroller filene før du starter importen. En generell CNV-fil uten prøveidentitet må velges eksplisitt for riktig prøve. RNA-rader med Sample_ID begrenses til den bekreftede prøven og RNA-koblingene i prøvelisten. Appen skal ikke bruke andre pasienters rader som funn bare fordi en fil er valgt manuelt. Ukjente filer gir ikke automatisk kliniske data.

BAM/CRAM-filer leses ikke som varianttabeller og kopieres ikke ukritisk inn i databasen. Lokal IGV-visning brukes fortsatt separat med riktig indeks og referansebygg.

## Prosessering og rapportarbeid

Logg inn med en aktiv personlig PRONTO-konto før import. En tom database kan få sin første konto i appen. Brukerkontoen får tilgang til rapportene den selv importerer. Ingen konto blir administrator av denne handlingen. HTML-rapportene har fortsatt egen innlogging og vanlig rapporttilgang.

Prosesser og importer validerer kildene, bevarer private kildekopier med SHA-256, oppretter rapportgrunnlag, første DRAFT og vedlegg, og registrerer importhistorikk. Én prøve lagres samlet; andre prøver kan fullføres selv om ett element feiler. Kjøringen viser hva som ble importert, var importert fra før, feilet eller ble avbrutt.

Samme uendrede kildegrunnlag skal ikke gi dubletter. Endret rågrunnlag under en eksisterende prøve og kjøring avvises som konflikt; gamle vurderinger skal ikke overskrives. En rapport opprettet før importhistorikken ble innført kan heller ikke gjenimporteres blindt som om kildegrunnlaget var kjent.

Mappekontrollen undersøker opptil 50 000 filer og 30 nivåer. Lenker og Windows-junctions følges ikke. Kildetabeller er begrenset til 25 MiB, 10 000 datarader og 500 kolonner. Rapportplott er begrenset til 12 MiB per fil, 20 PDF-sider og samlet 100 plott eller 64 MiB per rapport. En fil som endres etter kontrollen må undersøkes på nytt før import. Ødelagte eller ukjente filer blir ikke automatisk rapportinnhold.

Start server og Åpne rapporter åpner den eksisterende HTML-arbeidsflaten. Der fortsetter Save, Finalize, ny revisjon, PDF og HTML som før. Serverstart importerer aldri filene på nytt. En server som tilhører en annen prosess eller database stoppes ikke for å frigjøre porten.

## Lagring og backup

Appinnstillinger ligger i den lokale PRONTO-profilen. Ny datarot har database/pronto.sqlite3, privat råarkiv, nøkkel og backupmappe. Ved gjenbruk av det gamle oppsettet beholdes den eksisterende databasestien. Rapportgrunnlag, vedlegg, vurderinger og historikk lagres i Django-databasen; kildesnapshots lagres i det private råarkivet og registreres med hash.

Backupknappen tar en konsistent SQLite-kopi og kontrollerer integriteten. Arkiverte originalfiler, referansegenomer og nøkkel må inngå i driftens separate filbackup. Ta vare på tidligere backup ved oppgradering; appen tar backup før nødvendige migreringer av en eksisterende database.

Avslutt eller stopp jobben ved et trygt punkt og sikre ulagrede endringer i nettleseren. En stoppet server betyr ikke at ulagret nettlesertekst er skrevet til databasen.

## Lokal driftsgrense

Den innebygde serveren er for lokal arbeidsstasjon på 127.0.0.1. Den er ikke et ferdig oppsett for flere PC-er, offentlig nettverk eller klinisk produksjonsgodkjenning. Windows-versjonen beholder visning av alignments; permanent BAM/CRAM-bevaring har fortsatt de separate Linux- og lagringskravene beskrevet i IGV-guiden.

Prosesser-knappen behandler ferdige analysefiler. Den kjører ikke sekvensering, variant calling eller et nytt TSO500/TSOPPI-analyseforløp.

## Prøve appen uten jobbdata

Lag et femmappesett fra det allerede godkjente offentlige OUS-testgrunnlaget:

```powershell
.\.venv\Scripts\python.exe scripts\create_desktop_example.py --output Out\desktop-example
.\.venv\Scripts\python.exe -m pronto_desktop --data-root 'C:\PRONTO-test' --port 8772
```

Velg de fem mappene under Out/desktop-example. Den femte mappen er tom i eksempelet; antall mapper er ikke antall prøver. Bruk en separat testdatabase. Eksempelet tester kjent grunnstruktur og plott, og bekrefter ikke at den faktiske jobbkjøringen har samme format.

## Utviklerkontroll

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop-test.txt
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest pronto/tests/ingest pronto/tests/desktop -q
.\.venv\Scripts\python.exe -m pytest -q
$env:DJANGO_SETTINGS_MODULE='pronto_web.test_settings'
.\.venv\Scripts\python.exe manage.py test pronto_web.reports
```

Testene bruker midlertidige databaser, syntetiske mapper og de godkjente fixturefilene. Den virkelige driftsdatabasen skal ikke brukes i tester.
