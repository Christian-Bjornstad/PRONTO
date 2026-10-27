# PRONTO desktop

## Automatisk databasevalg for nettverksinstallasjon fra 0.6.4

Start den oppdaterte appen først som brukeren som allerede har fungerende
databasevalg. Etter vellykket oppstart publiserer appen `pronto-installation.json`
ved siden av PRONTO_START.cmd dersom program, datarot og database ligger på
Windows-nettverksstier. Filen inneholder bare datarot og databasepeker, ingen
passord eller hemmelig nøkkel. Den får arvede filrettigheter fra programmappen
og erstattes aldri automatisk dersom den allerede finnes.

Kollegene starter deretter appen fra samme oppdaterte programmappe. En bruker
uten eget databasevalg leser installasjonens peker og husker den i egen profil.
Eldre profil med samme datarot uten databasepeker kan også bruke fellesvalget.
Ingen database kopieres og ingen tom erstatningsdatabase opprettes ved feil.
Eksplisitte valg av annen database beholdes. En privat database på lokal disk
publiseres ikke til kolleger. Relative stier brukes når data ligger i programmappen,
ellers beholdes den fullstendige nettverksstien.

Første bruker må kunne opprette pekerfilen i programmappen. De øvrige trenger
lesetilgang til denne filen. Alle trenger fortsatt faktisk tilgang til datarot,
database og opprinnelig secret.key. Ved endring av felles databasevalg må områdets
forvalter oppdatere pekerfilen og avklare brukernes lagrede valg. Dette er
automatisk oppsett, ikke ny støtte for samtidig skriving til delt SQLite-fil.

## Felles programmappe og personlig oppsett fra 0.6.3

Desktopappen skriver ikke lenger til felles `.local-web/config.json` ved oppstart.
Filen brukes bare som eldre databasepeker ved første oppstart. Faktisk database,
datarot og lokal port huskes i hver brukers `%LOCALAPPDATA%\PRONTO\desktop.json`.
Det opprettes ingen privat kopi av pasientdatabasen. En eventuell kopi av privat
brukerbootstrap lagres også i brukerprofilen, ikke tilbake i programmappen.

Hvis felles config.json ikke kan leses, åpnes et valg av eksisterende SQLite-fil.
Velg den avtalte databasen, ikke en backup eller en ny fil. Ved standardoppsett
ligger den i `.local-web/pronto.sqlite3`; nyere datarøtter bruker
`database/pronto.sqlite3`. Appen trenger også den opprinnelige secret.key i
dataroten. Valget huskes per bruker. Ved database utenfor den eldre dataroten
kan `--data-root <opprinnelig datarot> --database <eksisterende database>` angi
begge eksplisitt. Manglende nøkkel eller filtilgang skal ikke omgås ved å opprette
ny database eller erstatte nøkkelen.

Programfiler trenger lesetilgang. Databasen og dataroten trenger rettigheter til
skriving og oppretting av SQLite-journal, råarkiv og backup. Nøkkelen trenger
lesetilgang. PRONTO-brukere og administratorrollen endrer ikke Windows/Isilon-
rettigheter. Dersom disse mangler, må tilgang gis av områdets forvalter.
Oppstartsrettingen innfører ikke samtidig flerbrukerlagring på en delt SQLite-fil.

## Oppstartsretting 0.6.1 — 27. oktober 2026

Feilen `invalid uri authority` ved oppstart fra nettverksområde skyldtes at
sikkerhetskopieringen før migrering brukte `Path.as_uri()` direkte. En UNC-sti
ble dermed en SQLite-URI med nettverksserver som authority, som standard SQLite
avviser. Backup bruker nå `file://localhost//server/share/...?...` med korrekt
escaping og `mode=ro`. Dette bevarer UNC-stien og skrivebeskyttet kildelesing.
Sikkerhetskopieringen hoppes ikke over. Rettelsen gjelder også lesing av lokale
demodatabaser fra UNC-sti og gjør ikke SQLite egnet for samtidig flerbrukerdrift.

Oppdater koden på `feature/pronto-desktop`, avslutt Python FELLES og start på
nytt. Behold valgt datamappe, database, råarkiv og nøkkel. Ikke lag en ny database
for å løse feilen. Denne feilen skyldes ikke manglende Python-avhengigheter.

Ved oppstartsfeil skrives loggen normalt til
`%LOCALAPPDATA%\PRONTO\logs\bootstrap.log` i den aktive Python/Citrix-økten.
Lim `%LOCALAPPDATA%\PRONTO\logs` inn i adressefeltet i Filutforsker i samme
økt. Hvis profilområdet ikke kan skrives til, brukes `%TEMP%\PRONTO\logs`.
Feilmeldingen viser den faktiske mappen som ble brukt. Hvis ingen av stedene
kan brukes, skrives feildetaljene direkte i Python-vinduet. Reinstallering
anbefales bare ved importfeil, ikke ved databasefeil.

Kontrollert på en eksisterende lokal Windows SMB/UNC-deling: opprinnelig feil,
backup med spesialtegn i filnavn, migrering fra 0011, bevart brukerkonto og
HTTP-oppstart. Jobbens Isilon/Citrix-område må prøves der; det er ikke tilgjengelig
fra utviklingsmaskinen.

PRONTO desktop samler filinnlasting, import til databasen, serverstart og åpning av HTML-rapportene i ett lokalt program. Velg PRONTO-mappen med kjøringsmappene, kontroller versjon og prøver, og importer. Appen bruker dagens rapportmotor, innlogging, vurderinger og historikk.

## Installere og starte

Pakk ut hele programmappen til en fast plass. Bruk PRONTO_INSTALL.cmd første gang og PRONTO_START.cmd ved senere oppstart. Startfilene støtter lokal Python og Python FELLES gjennom Ivanti. Faktisk Ivanti og tilgang på jobb-PC må kontrolleres der. Ikke flytt bare startfilene ut av programmappen.

Lukk den gamle appen før du starter en oppdatert versjon. Versjon 0.3 har automatisk filkobling og felles PRONTO-ikon i app, oppgavelinje, nettleser og rapport. Kjør `PRONTO_SNARVEI.cmd` hvis du vil lage en Windows-snarvei med dette ikonet. Snarveien peker på den utpakkede programmappen, som derfor må bli liggende på samme plass.

Fra versjon 0.6.2 installerer PRONTO_INSTALL.cmd PDF-leseren pypdfium2 i det aktive Python-miljøet. Poppler og endring av PATH er ikke nødvendig. Lukk Python FELLES etter installasjon og start PRONTO_START.cmd på nytt. Den innebygde leseren bruker en DLL fra Python-pakken; ingen eksterne PDF-programmer startes. Hvis biblioteket mangler, kan et eksisterende Poppler-oppsett fortsatt brukes som reserve.

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

## Kjøringsmappene

Velg én overordnet PRONTO-mappe, eller legg til opptil fem forskjellige kildemapper. Flere valgte mapper må ikke ligge inne i hverandre. Appen undersøker undermappene uten å flytte eller endre kildene. Den kartlagte TSOPPI-profilen gjenkjenner disse fire mappene med samme kjørings-ID:

```text
PRONTO/
  <run>/
  <run>_CNVs/
  <run>_report_preQC/
  <run>_report_preQC_newPRONTO_version/
```

Legg til alle kildemappene først. Trykk deretter `Kontroller filer` for ett samlet søk. Mappevalg, innlimte stier og endrede importvalg starter ikke søk automatisk. Appen kobler kjente kilder til prøvene; du skal normalt bare velge hvilke prøver som skal importeres.

Filtypen gjenkjennes fra kolonnene og kjente navnemønstre. Rolleord i navn kan variere i store og små bokstaver, bindestrek, understrek og versjonssuffiks som `_v2`. Råmappen kan også ende med `_TSO_500_LocalApp_postprocessing_results`. Metadata trenger ikke et bestemt filnavn, og analysesammendrag kan for eksempel hete `analysis_variant_summary.tsv`. Prøve-ID og kjørings-ID må fortsatt stemme nøyaktig. Et annet prøvenavn blir aldri et omtrentlig treff.

Velg rapportversjon før filkontrollen. Automatisk bruker ny rapportversjon når den finnes, ellers gammel eller råvarianttabell. Et uttrykkelig versjonsvalg skal ikke hente manglende prøver fra en annen rapportversjon. Endring av mappe, versjon eller CNV-kilde krever ny filkontroll.

CNV-kilden kan være sammenslått CNV-tabell eller Cancan. Sammenslått bruker `FC_sorted` foran `fraction_sorted`. Cancan krever valg av `main`, `alt01` eller `alt02` og kobler tabell og bilde fra samme løsning. Et løsningsnavn er ingen faglig godkjenning. Purity og ploidy fra forskjellige metoder må vurderes i sitt eget kildegrunnlag.

| Filrolle | Kjent grunnlag |
|---|---|
| Metadata | InPreD_PRONTO_metadata_tsoppi.txt eller InPreD_PRONTO_metadata.txt med Sample_id, Sequencing_run_id og Study_id |
| Sammendrag | *_variant_summary.tsv med sample_id, TMB og MSI |
| Småvarianter | *_small_variant_table_forQC.tsv, ellers *_small_variant_table.tsv |
| Prøvekobling | sample_list.tsv, eller eksplisitte DNA/RNA-kommentarer i concordance- og variantfilene i TSOPPI-profilen |
| Sammenslått CNV | <DNA>_merged_CNV_summary_FC_sorted.tsv, ellers fraction_sorted; Gene_Symbol og eksakt DNA-mappe |
| Cancan | <DNA>_<løsning>_gene_table.tsv med gene.name og kopitallskolonner i prøvens Cancan-mappe |
| RNA | <RNA>_fusion_and_splice_variant_candidates.tsv, eller eldre støttet XLSX-tabell |
| Plott | CNV, DNA/RNA-QC, joint_mutational_signature og RNA_profiles; PNG foretrekkes fremfor tilsvarende QC-PDF |
| Støttefiler | Kjente prøvefiler under valgt rapportversjons extra_files arkiveres som kildegrunnlag |

Metadata kan inneholde historiske kjøringer. Appen bruker én entydig rad for valgt prøve og kjøring. Prøver med `Create_report = -` eller tomt felt står uten avkrysning: merk prøven uttrykkelig for å importere den. Et negativt valg i metadata kan ikke overstyres av avkrysningen. Originalmetadata endres ikke.

DNA/RNA-koblingen må være eksplisitt og samstemt i alle tilgjengelige koblingskilder. RNA utledes ikke fra lignende filnavn. Når sample_list mangler, lager importen bare en intern adapterrepresentasjon fra de kontrollerte kommentarene; den skriver ingen ny fil i analysemappene. RNA-rader begrenses til bekreftede ID-er.

Kontroller filene før import. En generell CNV-fil uten prøveidentitet krever eksplisitt kobling utenfor den navngitte TSOPPI-profilen. Støttefiler, gamle DOCX/PPTX-rapporter og ukjente filer blir ikke automatisk nye kliniske funn. `Event_Type = .` i RNA-tabellen blir ikke en godkjent vurdering.

BAM/CRAM-filer leses ikke som varianttabeller og kopieres ikke ukritisk inn i databasen. Lokal IGV-visning brukes fortsatt separat med riktig indeks og referansebygg.

## Prosessering og rapportarbeid

Statusfeltet viser den konkrete årsaken når en prøve stoppes. Manglende Study_id hindrer ikke import. Når prøven velges, vises at feltet er valgfritt. «Metadatafil mangler» betyr at ingen lesbar fil med de påkrevde kolonnene ble funnet. Velg prøveraden for å lese forklaringen. Åpne Filvalg og velg «Fyll inn Study_id» for valgfri utfylling før import; appen fyller ikke inn oppdiktede identifikatorer.

Legg til alle mappene og trykk Kontroller filer. Utvid prøvene for å se de automatisk koblede kildene. Merk prøvene som skal importeres, eller bruk `Velg klare prøver`. Dette er et prøvevalg, ikke et krav om å velge hver fil. Negative metadataflagg kan ikke overstyres.

`Andre filer` samler ubrukte alternativer, som gamle rapportversjoner, QC i et annet filformat og CNV-løsninger som ikke er valgt. Disse må ikke kobles manuelt. Bare reelle mangler eller konkurrerende kilder under en prøve krever avklaring. Manuell kildekobling ligger under `Filvalg` og brukes ved slike avvik.

Logg inn med en aktiv personlig PRONTO-konto før import. En tom database kan få sin første konto i appen. Brukerkontoen får tilgang til rapportene den selv importerer. Ingen konto blir administrator av denne handlingen. HTML-rapportene har fortsatt egen innlogging og vanlig rapporttilgang.

Importer valgte validerer kildene, bevarer private kildekopier med SHA-256, oppretter rapportgrunnlag, første DRAFT og vedlegg, og registrerer importhistorikk. Én prøve lagres samlet; andre prøver kan fullføres selv om ett element feiler. Kjøringen viser hva som ble importert, var importert fra før, feilet eller ble avbrutt.

Samme uendrede kildegrunnlag skal ikke gi dubletter. Endret rågrunnlag under en eksisterende prøve og kjøring avvises som konflikt; gamle vurderinger skal ikke overskrives. En rapport opprettet før importhistorikken ble innført kan heller ikke gjenimporteres blindt som om kildegrunnlaget var kjent.

Mappekontrollen undersøker opptil 50 000 filer og 30 nivåer. Lenker og Windows-junctions følges ikke. Kildetabeller er begrenset til 25 MiB, 10 000 datarader og 500 kolonner. Rapportplott er begrenset til 12 MiB per fil, 100 PDF-sider og samlet 100 plott eller 64 MiB per rapport. En fil som endres etter kontrollen må undersøkes på nytt før import. Ødelagte eller ukjente filer blir ikke automatisk rapportinnhold.

Start server og Åpne rapporter åpner den eksisterende HTML-arbeidsflaten. Der fortsetter Save, Finalize, ny revisjon, PDF og HTML som før. Serverstart importerer aldri filene på nytt. En server som tilhører en annen prosess eller database stoppes ikke for å frigjøre porten.

## Lagring og backup

Appinnstillinger ligger i den lokale PRONTO-profilen. Ny datarot har database/pronto.sqlite3, privat råarkiv, nøkkel og backupmappe. Ved gjenbruk av det gamle oppsettet beholdes den eksisterende databasestien. Rapportgrunnlag, vedlegg, vurderinger og historikk lagres i Django-databasen; kildesnapshots lagres i det private råarkivet og registreres med hash.

Backupknappen tar en konsistent SQLite-kopi og kontrollerer integriteten. Arkiverte originalfiler, referansegenomer og nøkkel må inngå i driftens separate filbackup. Ta vare på tidligere backup ved oppgradering; appen tar backup før nødvendige migreringer av en eksisterende database.

Avslutt eller stopp jobben ved et trygt punkt og sikre ulagrede endringer i nettleseren. En stoppet server betyr ikke at ulagret nettlesertekst er skrevet til databasen.

## Lokal driftsgrense

Den innebygde serveren er for lokal arbeidsstasjon på 127.0.0.1. Den er ikke et ferdig oppsett for flere PC-er, offentlig nettverk eller klinisk produksjonsgodkjenning. Windows-versjonen beholder visning av alignments; permanent BAM/CRAM-bevaring har fortsatt de separate Linux- og lagringskravene beskrevet i IGV-guiden.

Importen behandler ferdige analysefiler. Den kjører ikke sekvensering, variant calling eller et nytt TSO500/TSOPPI-analyseforløp.

## Prøve appen uten jobbdata

Lag et syntetisk eksempel med fire kjøringsmapper, historiske metadata, eksplisitte DNA/RNA-koblinger, CNV, Cancan og plott:

```powershell
.\.venv\Scripts\python.exe scripts\create_desktop_example.py --output Out\desktop-example
.\.venv\Scripts\python.exe -m pronto_desktop --data-root 'C:\PRONTO-test' --port 8772
```

Velg Out/desktop-example i Importer. Kjør filkontroll og merk SYN0001-D01-P01-A01 før import. Prøven er bevisst satt til `Create_report = -` for å teste dette valget. Bruk en separat testdatabase. Eksempelet leser ingen pasientfiler og oppretter ingen egen sample_list i kildemappene.

Den leverte kjøringen er testet i separat lokal database. Filsøket fant 13 DNA-prøver; alle 13 ble importert, inkludert åtte uten Study_id. En importert rapport er åpnet med alle plott, gennavn fra biomarkørlisten i fet skrift og lagring av kladd. Databasebackup er kontrollert. Rapportinnhold må fortsatt gjennomgås faglig. Python FELLES, Ivanti og den innebygde PDF-leseren må også prøves i det faktiske jobbmiljøet.

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


## 20 Biomarkørliste og ny database

I Innstillinger velger du Biomarkørliste og Velg XLSX. Appen leser kolonnene Molekylær markør og Biomarkør_spesifikasjon. En kontrollert kopi og SHA-256 lagres i dataroten som biomarker-list.xlsx og biomarker-list.json. Originalen flyttes ikke. Listen lastes igjen ved neste oppstart. Åpne rapporten på nytt for å se endret markering. Både aktive og lukkede oppføringer bidrar til genmedlemskap; fet skrift sier ingenting om studieegnethet. TMB og MSI behandles ikke som gensymboler. Ingen liste er aktiv i en ny desktopdatabase før en fil er valgt.

Ny tom database under Innstillinger velger en tom mappe og lagrer oppsett for neste oppstart. Start appen på nytt; migreringene lager tabellene uten demo, rapporter eller brukere fra den gamle databasen. Opprett deretter første personlige konto. Databasen og senere redigeringer bevares i denne dataroten mellom oppstarter. Eksisterende database velges med det vanlige mappevalget. Behold hele dataroten ved flytting, inkludert nøkkel, råarkiv og biomarkørliste.

Filversjon, CNV-tabell og Cancan-løsning ligger under Avansert i Importer. Vanlig import bruker nyeste tilgjengelige rapportfiler og den sammenslåtte CNV-tabellen. Valgene henter alternative resultater som allerede finnes i mappene; appen kjører ikke Cancan eller variant calling.

Kjente eksportavvik håndteres av parseren: den sammenslåtte metadataoverskriften for de tre siste feltene deles, gamle rader med to manglende sluttfelt fylles med tomme felt, og kommentaren ID of the matched tumor RNA sample gjenkjennes. Manglende Study_id kan fylles inn i appen før import. PDF-plott kan ha opptil 100 sider og rasteriseres i grupper på fem med en samlet grense på 200 millioner piksler per PDF.


### Manuell utfylling av Study_id

Study_id kan stå tomt. Hvis verdien er kjent, velg prøven, åpne Filvalg og trykk Fyll inn Study_id for valgfri utfylling. Oppgi korrekt verdi for den viste prøven og kjøringen. Knappen fyller bare inn et manglende felt i én entydig metadatarad. Den endrer ikke prøve-ID, kjørings-ID, RNA-kobling eller Create_report, og opphever ikke andre avvik. Et Study_id som allerede finnes i kildefilen kan ikke overskrives gjennom denne knappen. Tomt felt fjerner den manuelle utfyllingen.

Utfyllingen gjelder arbeidsøkten før import og blir lagret permanent ved import. Nytt filsøk beholder den bare når samme metadatafil er uendret; ved endret kilde nullstilles verdien med en merknad. Velg prøven for import etter at feltet er fylt inn. Avsluttes appen før import, må verdien fylles inn på nytt.

Originalfilen i analysemappen endres ikke. Importen arkiverer originalen og manual-metadata.json med opprinnelig verdi, manuell verdi, prøve, kjøring og kontrollsum for metadatafilen. Sidefilen registreres som ImportSource med rollen metadata_override og tas med i proveniens og importens fingeravtrykk. ImportBatch registrerer ansvarlig importbruker og tidspunkt. Rapporten får diagnostikken MANUAL_STUDY_ID. Gjentatt import med samme kilder og verdi gir ingen dublett; en annen verdi under en allerede importert identitet avvises som konflikt.

Appmenyen viser et stort PRONTO-ikon med navnet under. PRONTO_SNARVEI.cmd oppretter en Windows-snarvei med samme ikon. Det underliggende PowerShell-skriptet støtter også DataRoot og Port når en bestemt eksisterende database skal åpnes.


### Valgfritt Study_id fra versjon 0.4.1

Study_id er ikke et importkrav. Tom tekst, bare mellomrom og plassholderne NA, N/A, bindestrek eller punktum lagres som null i ReportData v2. HTML og PDF viser at verdien ikke er oppgitt. Sample_id og Sequencing_run_id må fortsatt identifisere prøven og kjøringen entydig. Metadatafilen og dens kolonneoverskrifter kreves fortsatt. Manuell utfylling er valgfri.

Hele den leverte kjøringen er nå importert i separat lokal testdatabase: 13 rapporter, hvorav åtte uten Study_id. Originalfilene er uendret. Den nye tomme databasen for vanlig appbruk er fortsatt separat fra denne testen.


### Personlige brukere i versjon 0.5

Den lokale teamleveransen inneholder kontoene siri, anja, vigdis, laxmi, helen, tonje og christian, med personlige startpassord gitt separat. En ny database oppretter disse automatisk når config/initial-users.json følger programmet. Denne private oppstartsfilen inneholder PBKDF2-hasher, ikke lesbare passord, og følger ikke Git eller det offentlige kildearkivet. En kopi lagres i dataroten ved første oppstart. Uten oppstartsfil brukes fortsatt vanlig førstegangsopprettelse av en konto.

Kontoene er aktive vanlige brukere uten administratorrettigheter. De tilhører gruppen PRONTO report team. En rapport importert av en teambruker gir rapporttilgang til de aktive medlemmene i dette teamet. En bruker utenfor teamet får bare egne rapporttilganger; eksisterende private rapporter deles ikke automatisk. Personlige endringer lagres med den innloggede brukerens identitet, og revisjonskonflikter håndteres som før. Appens importhistorikk viser egne importjobber.

Innstillinger har knappen Endre passord. Den åpner passordsiden i nettleseren, der brukeren logger inn og oppgir gammelt og nytt passord. Den samme funksjonen finnes nederst i rapportoversikten. Startpassordene har ti tegn. Nye passord følger den eksisterende kontrollen med minst tolv tegn og kontroll mot vanlige passord. Appen lagrer bare passordhashen i databasen. Ved ny oppstart beholdes endrede passord og deaktiverte kontoer. Startfilen kan ikke overta et eksisterende brukernavn utenfor teamgruppen.

PRONTO_tom_database_med_brukere.zip inneholder en egen datamappe med alle sju brukere, biomarkørlisten og null rapporter. Pakk ut mappen til en fast plass og velg den som eksisterende datamappe under Innstillinger. Lagre for neste oppstart og start appen på nytt. Datamappen inneholder også nøkkelen og må håndteres som privat driftsoppsett.

For en separat kontrollinstallasjon kan PRONTO_INITIAL_USERS_FILE angi en bestemt privat JSON-fil. En eksplisitt tom miljøverdi deaktiverer automatisk brukeropprettelse for isolerte tester. Oppstartsfilen har schemaVersion 1.0 og users med bare username, firstName og passwordHash. Maksimalt 50 brukere og 64 KiB støttes; hashformatet er PBKDF2-SHA256 med minst én million iterasjoner.


### Plottvisning og bakgrunnsjobber fra versjon 0.5.2

Key findings viser nøkkeltallene først. Mutasjonssignaturen ligger i en lukket seksjon under nøkkeltallene og åpnes ved behov. Dette er en mutasjonssignatur og ikke et CNV-plott.

En CNV-PDF med flere sider vises som ett dokument med sidevelger og Previous page og Next page. Alle sider beholdes. Den leverte CNV-PDF-en har 55 sider; dette ga tidligere 55 like knapper med samme filnavn. Det eldre PDF-formatet med nøyaktig ni sider beholder panelnavnene og gruppen B3 og C1.

Bakgrunnsjobber avslutter nå opprydding av databaseforbindelser før grensesnittet mottar ferdigmeldingen. Ferdigmeldingen håndteres i et eksplisitt Qt-slot på vinduet. Isolert Windows-test med syntetisk import og 300 vindusendringer er gjennomført uten krasj. Dette fastslår ikke årsaken til den tidligere rapporterte native Windows-feilen. Tidsavbrutte ledige nettleserforbindelser avsluttes stille uten en unødig feilstakk i loggen.


### Administrator og revisjoner fra versjon 0.6

Innstillinger → Brukere åpner brukeradministrasjonen i nettleseren. Logg inn som administrator molpat. Den private apppakken inneholder en separat initial-admin.json med administratorens passordhash; passordet distribueres separat. Ingen passord eller administratorhash ligger i GitHub. Ved installasjon fra GitHub uten privat startfil: åpne Innstillinger → Brukere, opprett molpat med avtalt passord i engangsoppsettet og logg deretter inn i nettleseren. Engangsoppsettet er bare tilgjengelig lokalt i desktop-appen når databasen ikke har noen administratorkonto. Det finnes ingen åpen nettside for å opprette administratorer.

Administrator kan opprette vanlige teambrukere, deaktivere og aktivere kontoer og sette nytt passord. Nye teambrukere får tilgang til eksisterende teamrapporter og senere teamimporter. Private rapporter uten teamtilgang deles ikke. Kontoer slettes ikke, slik at vurderinger fortsatt kan knyttes til riktig person. Administratoren ligger i gruppen PRONTO administrators og får ikke generell Django-superbrukertilgang. Vanlige brukere kan verken opprette kontoer, tildele administratorrolle eller rydde revisjoner. Administratorens eget passord endres med vanlig Endre passord, og oppstarten tilbakestiller det aldri.

Vanlig Save oppdaterer én WorkingDraft med samme revisjonsnummer. Version øker for å oppdage samtidige endringer. Start new revision og Finalize bevarer egne revisjoner. Første PDF-eksport bevarer kladden og fortsetter arbeidet i neste revisjon; flere PDF-formater av helt uendret innhold bruker den samme bevarte revisjonen. Eksportsporet skiller forespurt arbeidsrevisjon fra revisjonen som faktisk ble eksportert. Filnavn og status viser den eksporterte revisjonen.

I rapportoversikten finner molpat Administrer revisjoner. Eldre utkast kan fjernes fra den vanlige versjonslisten og gjenopprettes på samme side. Gjeldende, ferdigstilte og eksporterte revisjoner og en aktiv kladds kilde beholdes. Dette er reversibel rydding: selve vurderingen og revisjonsnummeret beholdes i databasen, og nummer gjenbrukes ikke. AdministrationEvent registrerer brukerhandlinger og rydding; HiddenRevision markerer skjulte utkast. ReportRecord.team_shared markerer rapporter som deles med nye teambrukere. Migreringen merker tidligere teamimporter; individuelle rapporttilganger blir ikke til teamdeling. Migreringene 0012–0014 kjøres automatisk med databasebackup ved oppstart.

### Presentasjonsrapport fra versjon 0.6

Presentation PDF følger InPreD MolMDT-enkelsidemalen i 16:9: pasientfelt til venstre, signaturer, CNV og RNA øverst, hovedfunn og beskrivelser i midten og inkluderte mutasjoner til høyre. Bare inkluderte funn rapporteres; hovedfunn krever også Report highlight. Tomme resultater vises som manglende opplysninger. Lange tabeller og beskrivelser fortsetter på senere sider. Fullstendige kildeannotasjoner, øvrige notater og QC følger på detaljsider, og valgte figurer kommer til slutt.

Under Tumour board report → Presentation — annotations finnes manuelle felt for de markerte hovedfunnene. GoF/LoF, Sensitive, Resistant, EMA for pasientens tumortype eller annen tumortype, signaturstatus og beskrivelse lagres sammen med vurderingen. Appen beregner ikke behandlingsindikasjon, HRD/MSI-status eller regulatorisk godkjenning fra disse feltene. De fylles ut og kontrolleres av ansvarlig fagbruker. Uutfylte felt viser en strek i presentasjonen. ESMO-formatet beholder sitt stående rapportoppsett.


## PDF-leser fra 0.6.2

Oppdater programfilene, kjør PRONTO_INSTALL.cmd én gang for å installere pypdfium2==5.14.0, lukk Python FELLES og start på nytt. Denne versjonen fjerner installasjonskravet om pdfinfo og pdftoppm. Datamappe, database og eksisterende rapporter beholdes. PDF-leseren behandler én side om gangen med grenser på 100 sider, 32 millioner piksler per side og 200 millioner piksler samlet per PDF. Native PDFium-kall er serialisert fordi biblioteket ikke er trådsikkert.
