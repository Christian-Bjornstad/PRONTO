# PRONTO appen

Manual for overtakelse og drift

Teknisk og praktisk overlevering til ny forvalter

26. oktober 2026

Programversjon og eksakte kontrollresultater identifiseres i pakkens manifest.

Denne manualen forklarer hvordan den nye PRONTO-appen installeres, brukes, vedlikeholdes og videreføres. Appen samler valg av kjøringsmapper, kontrollert import, database og serverstyring. Den eksisterende HTML-arbeidsflaten brukes videre til vurdering og rapportering. Den dekker hele kjeden fra TSOPPI og kliniske metadata til database, vurderingsarbeid, HTML, PDF og IGV. Målgruppen er både fagbrukeren som skal overta rapportarbeidet, og utvikleren eller driftsansvarlig som skal kunne forvalte løsningen uten muntlig forklaring fra den opprinnelige utvikleren.

Den leverte jobbkjøringen er kontrollert i en separat lokal testdatabase. Filsøket fant 13 DNA-prøver fordelt på fire toppmapper. Alle 13 prøvene er importert. Åtte mangler Study_id; dette er tillatt og verdiene er lagret som manglende. Originalfilene ble bare lest. Biomarkørlisten fra september 2026 inneholdt 90 rader og ga 65 unike gensymboler. Dette er teknisk importkontroll; rapportinnhold og faglige vurderinger må fortsatt gjennomgås av ansvarlig bruker. Python FELLES og Ivanti må prøves på jobb-PC-en.

Leveransen består av denne manualen, et eget kildekodearkiv og et kontrollnotat med versjon og testresultater. Kildekodearkivet inneholder den konkrete programversjonen og godkjente testfiler. Den lokale databasen, passord, nøkler, referansegenomer og genererte pasientrapporter overføres separat gjennom godkjent intern lagring.

## 1 Slik tar neste person over

### Start her

Les kapittel 2 for helhetsbildet, kapittel 7 for appens fem sider og oppstart, kapittel 8 for daglig rapportarbeid og kapittel 14 for sikkerhetskopi. Utvikleren bør deretter lese datakontraktene, databasemodellen og importløpet i kapittel 5, 6 og 10. Kapittel 18 brukes ved selve overtakelsen.

Den nye forvalteren må overta tre forskjellige ting: programkoden, det private driftsoppsettet og ansvaret for datagrunnlaget. Et kildekodearkiv alene inneholder ingen brukerkontoer eller vurderinger. En databasekopi alene inneholder ikke alle genomfiler, den hemmelige nøkkelen eller et komplett installert Python-miljø.

### Anbefalt første arbeidsøkt

1. Pakk ut kildekoden til en ny prosjektmappe. Kontroller versjonen mot kontrollnotatet. Ikke arbeid videre i den eldre PRONTO-hovedmappen ved en feil.
2. Installer Python-miljøet og Poppler som beskrevet i kapittel 7. Bruk en isolert database ved første kontroll.
3. Avtal om overtakelsen gjelder en tom installasjon eller eksisterende rapporter og historikk. Flytt eksisterende privat tilstand etter fremgangsmåten i kapittel 14.
4. Opprett første personlige konto i en tom database, eller logg inn med eksisterende konto. Kontroller riktig datamappe i Innstillinger, prøv kjøringsmappene i Importer og avklar alle kilder før import. Kontroller rapporttilgang med både riktig konto og en annen konto uten tilgang.
5. Gjennomfør en rapport på godkjent testgrunnlag: åpne, rediger, lagre, last siden på nytt, ferdigstill og last ned begge PDF-formatene. Bruk en testkopi ved øving.
6. Gjenopprett en backup til en annen filsti. Kontroller rapporter, vedlegg, siste FINAL og aktiv kladd før den gamle installasjonen tas ut av bruk.

### Ansvar som må fordeles

| Rolle | Konkret ansvar |
| Faglig eier | Godkjenner kildeverdier, filtreringsregler, rapportinnhold og faglig bruk. |
| Teknisk forvalter | Vedlikeholder Python, Django, skjemaer, migreringer, tester og rapportmaler. |
| Driftsansvarlig | Forvalter kontoer, nettverk, backup, gjenoppretting, lagringskapasitet og logger. |
| Dataansvarlig | Bestemmer tilgang, oppbevaring, sletting og godkjente lagringsområder. |

Rollene kan fylles av samme person, men ansvaret må være navngitt. Ingen nye eksterne kontoer eller driftsavtaler opprettes automatisk av PRONTO.

## 2 Helheten fra analyse til rapport

PRONTO omfatter en ny lokal app for import og serverstyring, en nettbasert rapportarbeidsflate og en eldre kommandolinjeflyt for rapportgenerering. Den eldre flyten behandler TSOPPI-resultater og kan produsere PowerPoint og remisseutkast. Nettløsningen bygger et validert rapportgrunnlag, viser det i HTML og lagrer brukerens vurderinger i Django-databasen. Nettløsningen lager PDF direkte med ReportLab.

| Trinn | Hva skjer | Ansvarlig del |
| 1 Analysegrunnlag | TSO500 og TSOPPI produserer annoterte varianttabeller, sammendrag, prøveoversikt og plott. | Ekstern analysepipeline |
| 2 Kliniske metadata | Prøve, run, pseudonym og kliniske opplysninger knyttes til analysen. | InPreD metadatafil og laboratoriets rutine |
| 3 Filer og importplan | Brukeren velger PRONTO-mappen eller én til fem separate kildemapper. Filgjenkjenningen kobler kilder til prøve og kjøring og viser mangler før import. | pronto_desktop og pronto_ingest/discovery.py |
| 4 Rapportgrunnlag | Importen validerer filer, arkiverer kildekopier, beregner hash og oppretter rapport og første DRAFT samlet per prøve. | pronto_ingest/importer.py og adapterne |
| 5 Privat lagring | Rapport, bilder, vurderinger og tilganger lagres gjennom Django ORM. | pronto_web/reports/ |
| 6 Arbeidsflate | Python bygger HTML; JavaScript håndterer tabeller, redigering, dialoger og kommandoer. | renderers, templates og static |
| 7 Faglig vurdering | Brukeren velger inkludering, klassifisering, QC, kommentarer og rapporttekst. | ReviewState og WorkingDraft |
| 8 Leveranse | En lagret vurdering vises som historikk, FINAL, PDF eller en separat HTML-rapport. | Eksportendepunkter og renderere |

### Hvor data faktisk hentes fra

Webappen leser hovedsakelig rapportgrunnlaget fra sin egen database. Den søker ikke løpende i ClinVar, COSMIC, gnomAD, OncoKB eller sykehusets journalsystem. Slike annoteringer finnes eventuelt allerede i TSOPPI-tabellene. Det finnes ingen generell overvåking av nye run-mapper eller ferdig integrasjon mot LIMS i denne leveransen.

IGV laster nødvendige deler av BAM eller CRAM og referansefiler når brukeren åpner en region. Dette er en separat dataflyt og gir ikke nye kliniske annoteringer. Biomarkørlisten velges som XLSX under Innstillinger. Appen bruker en lokal kopi til å vise oppførte gensymboler i fet skrift i HTML.

### Viktige arkitekturvalg

Kildegrunnlaget og vurderingen er skilt. En brukerendring av en kildeverdi registreres som en begrunnet korreksjon, mens den importerte verdien beholdes. HTML og PDF bygger på de samme validerte kontraktene. Dette gjør det mulig å følge hvilke opplysninger som kom fra analysen, og hvilke som ble lagt til under faglig vurdering.

## 3 Hvilke filer gjør hva

Alle stier i tabellen er relative til den prosjektmappen som inneholder manage.py. Rediger kildefilene og generer rapporten på nytt; en ferdig HTML-fil er et resultat, ikke riktig sted for varige kodeendringer.

| Fil eller mappe | Rolle ved vedlikehold |
| PRONTO_INSTALL.cmd og PRONTO_START.cmd | Inngang for installasjon og oppstart med lokal Python eller Python FELLES gjennom Ivanti. |
| PRONTO_SNARVEI.cmd og scripts/create_desktop_shortcut.ps1 | Valgfri Windows-snarvei med PRONTO-ikon. Opprettes bare når brukeren kjører kommandoen. |
| install_python_felles.py og start_python_felles.py | Installerer og starter i aktiv Python 3.14 uten krav om et separat child-interpreter-løp. |
| pronto_desktop/gui.py og theme.py | Appens fem sider, filvalg, bakgrunnsjobber, fremdrift, innlogging og visuell utforming. |
| pronto_desktop/runtime.py | Datarot, databasevalg, migrering, kontoer, historikk, sikkerhetskopi og oppstartsinnstillinger. |
| pronto_desktop/server.py | Lokal WSGI-server, helseidentitet, portkonflikter, gjenbruk og trygg stopp. |
| pronto_ingest/contracts.py og discovery.py | Importkontrakter, kjøringsprofiler, kilderoller og eksplisitt kobling av funnet fil til prøve. |
| pronto_ingest/importer.py | Prøvevalidering, kildearkiv, hash, dublettvern, databaseinnlegging og importstatus. |
| Script/PRONTO.py | Eldre hovedprogram for TSOPPI-behandling, filtrering og PowerPoint eller remisse. |
| pronto/pronto.py | Hjelpefunksjoner brukt av den eldre analyse og rapportflyten. |
| Config/configure_PRONTO.ini | Node, kildesti, tegnsett og filtreringsoppsett for den eldre flyten. |
| In/ og Out/ | Inndata og rapportmaler, samt lokalt genererte resultater. Out skal ikke brukes som kildekode. |
| pronto_report/adapters/ | Leser PRONTO og TSOPPI-filer samt komplette kildetabeller. |
| pronto_report/models.py | Typede, uforanderlige representasjoner av rapport og vurdering. |
| schemas/ og validation.py | Versjonerte JSON Schema og validering av sammenheng mellom rapport og vurdering. Ligger under pronto_report. |
| identity.py og serialization.py | Stabile rapport og variantidentifikatorer, samt deterministisk JSON. Ligger under pronto_report. |
| pronto_report/review/ | Vurderingsregler, kildebaserte startvalg, genliste og kommandokontrakter. |
| pronto_report/renderers/ | Bygger arbeidsflate, rapportvisning, HTML-sammendrag og begge PDF-formatene. |
| pronto_report/templates/report/ | HTML-deler for blant annet variantreview, CNV, RNA, QC og Report. |
| pronto_report/static/ | CSS, JavaScript og lokalt inkludert igv.js. Ingen CDN er nødvendig for IGV-koden. |
| pronto_web/reports/models.py | Databasetabeller og integritetskrav. |
| pronto_web/reports/views.py | Innlogging, rapporttilgang, rendering og HTTP-håndtering. |
| working_drafts.py og review_repository.py | Arbeidskladder, samtidighetskontroll og databasegrensen for vurderinger. Ligger under pronto_web/reports. |
| pdf_export.py, html_export_audit.py og figures.py | Eksport, eksportspor og private presentasjonsfigurer. Ligger under pronto_web/reports. |
| alignment og igv moduler | Oppslag, byteområder, referanser og valgfri lagring av genomfiler. Ligger under pronto_web/reports. |
| scripts/start_web.py | Lokal oppstart, vedvarende nøkkel og databasevalg, migrering og brukeropprettelse. |
| pronto_web/settings.py og local_settings.py | Grunnoppsett og eget oppsett for lokal HTTP på loopback. |
| docs/ og test_data/ | Driftsguider og godkjente testfiler. Tester ligger i pronto/tests og pronto_web/reports. |

## 4 Analysefiler og kliniske opplysninger

### Filene appen finner og adapteren bruker

Appen søker i én til fem valgte mapper og deres undermapper. TSOPPI-profilen kjenner igjen råkjøringen, _CNVs, _report_preQC og _report_preQC_newPRONTO_version med samme kjørings-ID. Den identifiserer kjente tabeller fra kolonneoverskrifter og kjente plott fra filnavn; kildeidentitet krever eksakt prøvekobling. Ved import lager appen en midlertidig, kanonisk kilderot som passer den eksisterende adapteren. Ved direkte bruk av denne adapteren inneholder kilderoten InPreD_PRONTO_metadata.txt og nøyaktig én fil som matcher *_variant_summary.tsv. Under mappen med aktuell sample_id skal sample_list.tsv og én småvarianttabell finnes. Adapteren foretrekker *_small_variant_table_forQC.tsv; hvis ingen finnes, brukes *_small_variant_table.tsv. Flere treff gir feil fremfor et tilfeldig filvalg.

Metadatafilen må inneholde aktuell Sample_id. Sequencing_run_id er obligatorisk. Study_id er valgfritt; tom verdi lagres som null og vises som ikke oppgitt i rapporten. Sammendraget må ha den aktuelle prøven, med støtte for prøvens _P-suffiks. Manglende kildefiler, manglende identitet eller manglende sammendragsrad avbryter importen.

| Kildetype | Hva den brukes til |
| Metadata TSV | Prøve, run, pasientpseudonym og tilgjengelig klinisk diagnose. |
| Variant summary TSV | TMB og MSI med rå kildeverdi og kildeposisjon. |
| Small variant table TSV | Gen, koordinat, alleler, transkript, proteinendring, frekvens, dybde og annoteringer. |
| Prøveliste eller TSOPPI koblingskommentar | Eksakt kobling til én DNA-tumorprøve og eventuelle RNA-tumor-ID-er. Kildespor og validering før tabellrader tas inn. |
| CNV overview PDF | Deklarert CNV-plott for aktuell prøve. |
| Sample QC PNG | Deklarerte QC-bilder i prøvemappen. |
| CNV og RNA tabeller | Importeres som sourceTables i ReportData v2. Rader med prøve-ID filtreres på bekreftet prøve og tillatte RNA-koblinger. Generisk tabell uten identitet krever eksplisitt kobling. |

Kjente tilleggsnavn er CNV_summary_table.csv, fusion_and_splice_variant_candidates_withQC.xlsx, <sampleID>_CNV_overview_plots.pdf og <sampleID>_sample_QC_plot.png. Eksempler på RNA-domeneplott er MET-splice-variant_domain_plot.pdf og TMPRSS2-ERG_2000_domain_plot.pdf. Navnet alene bekrefter ikke prøvetilhørighet.

### Valg mellom rapportversjoner og CNV løsninger

TSOPPI-profilen bruker samme kjørings-ID i de fire mappenavnene. Automatisk versjon velger den nye rapportmappen når den finnes, ellers den gamle eller råvarianten. Velges en bestemt versjon, vises manglende kilder som avvik fremfor å hente en annen versjon for den enkelte prøven. Bare én småvarianttabell går inn i rapportgrunnlaget. Gamle Word- og PowerPoint-utkast leses ikke som nye funn.

For sammenslått CNV velges merged_CNV_summary_FC_sorted.tsv foran fraction_sorted. Eksakt DNA-prøvemappe er et definert koblingsgrunnlag bare i denne navngitte profilen. For Cancan velges main, alt01 eller alt02 uttrykkelig. Tabell og bilde skal ha samme løsningsnavn. Cancan bevarer kolonnene gene.name, minor.cn, major.cn, total.cn og øvrige råkolonner i en egen CNV-kildetabell. Purity og ploidy skal forstås med metode og valgt løsning, og settes ikke automatisk som en felles klinisk tumorprosent.

Mutasjonssignatur og RNA-profiler er egne plottkilder. For QC brukes PNG foran tilsvarende PDF for samme prøve, slik at begge formatene ikke vises som to forskjellige resultater. Prøvekoblede støttefiler fra extra_files under valgt rapportversjon arkiveres som kildespor; de blir ikke automatisk klassifiserte funn. RNA med Event_Type lik punktum forblir uvurdert.

### Beregning og visning

Webadapteren leser TMB og MSI fra sammendraget. Den gjennomfører ikke en ny TMB-beregning og finner ikke selv en behandlingsindikasjon. Den eldre PRONTO-flyten har egne beregninger og filtreringsregler. Ved regelendringer må man derfor først avklare hvilket løp som faktisk produserte kildeverdien.

DisplayRange er en visningsskala, for eksempel [0-100+]. Den er ikke en klinisk grenseverdi. Manglende verdier skal fremstå som utilgjengelige. I det godkjente OUS-testgrunnlaget er TMB 14,9 og MSI 4,13, og alle 30 kildeforekomstene av småvarianter bevares. Dette er testkontroller, ikke referanseverdier for andre prøver.

Kildetabell-leseren støtter XLSX, TSV og TXT samt CSV med semikolon, komma eller tabulator når forventet kolonneoverskrift entydig identifiserer skilletegnet. Den har grenser på 25 MiB filstørrelse, 10 000 datarader og 500 kolonner. XLSX har i tillegg grense på 100 MiB samlet utpakket størrelse. Bibliotekleseren kan ta et eksplisitt arknavn, men desktopprofilen gjenkjenner støttede enkeltarkfiler. Flerarksarbeidsbøker krever en validert profilendring. Gul kildefarge kan registreres som sourceApproved, men setter ikke automatisk brukerens rapportvalg.

## 5 Datakontrakter og identitet

### ReportData

ReportData er rapportens importerte faktagrunnlag. Den gjeldende adapteren produserer schemaVersion 2.0. Viktige felt er reportId, sample, run, provenance, biomarkers, qcMetrics, variants, attachments, diagnostics og sourceTables. V1 støttes fortsatt for eldre data. sourceTables bevarer ordnede kolonner, råverdier, filnavn, hash og radidentitet.

provenance beskriver genereringstid, generatorversjon og kildefiler med SHA-256. attachments beskriver vedlegg; filinnholdet lagres separat. diagnostics gjør mangler synlige, for eksempel fravær av strukturert QC. Et QC-bilde blir ikke automatisk omgjort til strukturerte måleverdier.

### ReviewState

ReviewState er brukerens vurdering. Arbeidsflaten bruker versjon 4.0 med blant annet variantReviews, findingReviews, biomarkerReviews, sectionQc, notes, valueCorrections, presentationFigures og manualCnvRows. Eldre versjoner 1 til 3 kan leses og oppgraderes gjennom eksisterende migreringsfunksjoner. Datakontraktversjon og Django-databasemigrering er to forskjellige versjonssystemer.

ReportingDecision og clinicalClassification er uavhengige. En variant kan ha en klassifisering og likevel være utelatt fra rapporten. Report highlight velger relevante funn blant de inkluderte. IGV-vurdering er et tredje valg. Korreksjoner krever støttet feltsti, opprinnelig verdi, ny verdi, begrunnelse og sporbar forfatter og tid.

### Identifikatorer og dubletter

reportId beregnes deterministisk fra prøve og run. variantId identifiserer varianten og deles mellom dublette forekomster. occurrenceId identifiserer hver enkelt kilderad. Samme variant kan derfor vises flere ganger i kildegrunnlaget uten at den faglige vurderingen blir delt i flere uavhengige beslutninger. Ikke erstatt disse identifikatorene med radnummer eller et nytt tilfeldig ID ved hver import.

### Valideringsgrenser

serialization.py avviser blant annet dupliserte JSON-felter, ikke-endelige tall og for store dokumenter. JSON-grensen er 25 MiB. Schema og den påfølgende sammenhengsvalideringen kontrollerer identitet og variantreferanser. En vurdering fra en annen rapport skal avvises. Bruk deserialize og validate-funksjonene; direkte skriving av vilkårlig JSON til databasen omgår disse kontrollene.

Startvalg hentes fra Class_judgement, CPSR_ClinVar_class og IGV_QC når de er entydige og støttet. Lagrede manuelle valg beholdes. Et treff i den tilknyttede XLSX-listen betyr genmedlemskap og velger hverken Include eller Highlight. Eldre oppsett uten desktopkonfigurasjon har fortsatt den innebygde listen som reserve.

## 6 Databasen og hva som lagres hvor

Lokal oppstart bruker SQLite. Appens datamappe og port huskes i brukerprofilens PRONTO/desktop.json, på Windows normalt under LOCALAPPDATA. En ny datarot bruker database/pronto.sqlite3. Første oppstart uten eget valg gjenbruker det eldre oppsettet fra .local-web/config.json; standard der er .local-web/pronto.sqlite3. Grunninnstillingene har også et annet standardnavn, pronto_web.sqlite3. Det er derfor avgjørende å lese faktisk konfigurasjon før backup, migrering eller flytting. Ikke velg database ut fra navnet på den første SQLite-filen i prosjektmappen.

| Django modell | Innhold og sammenheng |
| ReportRecord | Én rapport med report_id som primærnøkkel og ReportData i JSON. |
| ReportGrant | Kobler bruker og rapport. Gir rapporttilgang og adgang til ordinær vurdering. |
| ReportWriteGrant | Egen tillatelse til å bevare eller slette alignments. Er adskilt fra vanlig rapporttilgang. |
| WorkingDraft | Maksimalt én aktiv kladd per rapport. Har revisjon, version og ReviewState JSON. |
| WorkingDraftEvent | Små hendelser for lagring, ferdigstilling, ny kladd og nullstilling. Bevarer ikke full tidligere kladd på hver Save. |
| ReviewRevision | Bevarte rapportvurderinger med unik kombinasjon av rapport og revisjon. |
| ReviewAudit | Hendelser fra eldre revisjonsflyt og lagret attribusjon. Unik per rapport og revisjon. |
| ReportAsset | Binære rapportvedlegg som matcher attachments og deres hash. |
| PresentationFigure | Privat, uforanderlig PNG med hash, opplaster og tidspunkt. Utvalget ligger i ReviewState. |
| ReportPdfExportAudit | Hvem som ba om hvilket PDF-format, revisjon, requestId og malversjon. |
| ReportHtmlExportAudit | Forespørsel om HTML-eksport for en bestemt lagret revisjon. |
| ReportPrintAudit | Forespørsel om utskrift fra den eldre utskriftsflyten. |
| SavedAlignment | Metadata, hash og private lagringsnøkler for bevarte BAM eller CRAM-par. Filbytes ligger på filsystemet. |
| AlignmentUploadSession | Eier, forventet størrelse, mottatt byteantall, utløp og tilstand under opplasting. |
| AlignmentEvent | Minimalt spor for SAVE, COPY og DELETE av alignments. |
| ImportBatch | Én importjobb med bruker, faktisk antall valgte mapper, start, slutt og samlet status. Inneholder ikke kildemappenes absolutte stier. |
| ImportItem | Én prøves resultat i jobben, med prøve, kjøring, fingerprint, status og eventuell rapportkobling. |
| ImportSource | Hver arkivert kilde med rolle, opprinnelig filnavn, relativ arkivnøkkel, SHA-256 og størrelse. Bytes ligger i raw_imports. |
| Django auth og session | Brukere, passordhasher, grupper, tillatelser og innloggingssesjoner. |

Databasen inneholder ikke bare et register over filstier. Den inneholder selve rapportgrunnlaget, vurderingene, rapportbildene og presentasjonsfigurene. Importerte kildesnapshots ligger i datarotens raw_imports med genererte arkivnøkler. BAM eller CRAM, referansegenomer, opprinnelige analysemapper og ferdige PDF eller HTML-nedlastinger kan også ligge utenfor databasen og må håndteres separat.

Migreringene ligger i pronto_web/reports/migrations/. Historikken har to 0002-grener som samles i 0003. Den inneholder også 0010 for arbeidskladder og 0011_import_batches for ImportBatch, ImportItem og ImportSource. Bruk migrate; ikke slett migreringsfiler eller endre tabellene manuelt. Audit er beskyttet av applikasjonsrutiner og databaseforhold, men er ikke et kryptografisk, manipulasjonssikkert register mot en databaseadministrator.

## 7 Installere starte og bruke appen

### Installasjon med lokal Python eller Python FELLES

Pakk ut hele programmappen til en fast plass som brukeren har riktig tilgang til. Behold startfiler, Python-filer, maler, skjemaer og statiske filer samlet. PRONTO_INSTALL.cmd brukes første gang og ved nødvendig reparasjon. PRONTO_START.cmd brukes til vanlig oppstart. Ingen demonstrasjonspasienter opprettes automatisk.

Programmet er satt opp for Python 3.14. requirements-desktop.txt inkluderer de eksisterende Python-avhengighetene og PyQt6. På en PC med Ivanti åpner startfilene Python FELLES og legger en kommando på utklippstavlen. Lim inn med Ctrl+V og trykk Enter. Installeringskommandoen kjøres i den aktive tolken. Lukk Python FELLES etter installasjon og start appen på nytt. Denne konkrete Ivanti-integrasjonen og maskinens rettigheter må kontrolleres på jobb-PC-en.

På en lokal utviklermaskin kan et isolert miljø opprettes fra prosjektmappen:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\.venv\Scripts\python.exe -m pronto_desktop
```

PDF-kildeplott valideres før de lagres og krever i tillegg Poppler med pdfinfo og pdftoppm tilgjengelig i PATH for Python-prosessen. Python-pakken pdf2image installerer ikke disse programmene. PDF-rapportene PRONTO selv produserer bruker ReportLab. Installer Poppler i godkjent område, legg bin-mappen i PATH og start Python FELLES eller appen på nytt etter endring. Kontroller verktøyene under Log og med Get-Command pdfinfo, pdftoppm i PowerShell. Import med PDF-plott avvises før rapporten lagres hvis verktøyene mangler. Et program som har vært åpent mens PATH ble endret kan fortsatt bruke gammelt miljø.

### Første oppstart og eksisterende data

Appen gjenbruker .local-web/config.json, database og nøkkel ved første oppstart uten valgt datarot. Dette gjør at rapporter fra det eldre lokale oppsettet kan beholdes. Databasemigreringer som mangler kjøres ved oppstart; en eksisterende database sikkerhetskopieres før nødvendige migreringer. Oppstartsvalget --check er derfor ikke en rent lesende kontroll.

Innstillinger viser hvilken database, hvilket kildearkiv og hvilken port som faktisk brukes. En husket datamappe med utilgjengelig database skal gi oppstartsfeil. Gjenopprett tilgang til den riktige plasseringen før videre bruk; ikke erstatt en arbeidsdatabase med en ny tom fil for å få programmet til å starte.

For en ny, separat arbeidsplass eller testdatabase brukes et eksplisitt valg én gang:

```powershell
.\.venv\Scripts\python.exe -m pronto_desktop --data-root 'C:\PRONTO-test' --port 8772
```

Det nye oppsettet får database/pronto.sqlite3, raw_imports, backups og secret.key under den valgte dataroten. En annen port er nødvendig hvis en eksisterende rapportserver allerede bruker 8770. Datarot og port huskes for neste oppstart. Appen flytter ingen gamle data automatisk.

### De fem sidene i kontrollsenteret

| Side | Daglig bruk |
| Oversikt | Viser antall rapporter i aktiv database, prøver i importplanen og prøver klare for import. Åpner importflyten. |
| Importer | Valg av overordnet mappe og ekstra kildemapper, rapportversjon, CNV-kilde, filkontroll, avkryssing av prøver, kildefiler, avvik, import og avbryt. |
| Rapporter | Viser importresultater fra økten og egen lagret importhistorikk etter innlogging. Åpner HTML-oversikten. |
| Innstillinger | Viser aktiv database og kildearkiv, tar sikkerhetskopi, håndterer appinnlogging og lagrer datamappe og port for neste oppstart. |
| Log | Viser fremdrift, meldinger og feil fra økten. Loggen kan kopieres og må håndteres som annet analysegrunnlag. |

Ctrl+1 til Ctrl+5 bytter side. Ctrl+R starter filkontroll. Knapper og felter kan nås med tastatur. Filkontroll, import, innlogging, backup og serverstart utføres i bakgrunnsarbeid slik at appen kan vise status underveis.

### Importere en kjøring

1. Velg PRONTO-mappen som inneholder de fire kjøringsmappene. Alternativt velger du én til fem separate kildemapper; de må være forskjellige og ikke ligge inne i hverandre. Velg rapportversjon og CNV-kilde før filkontrollen. Cancan krever også valg av løsning.
2. Legg til alle kildemappene og trykk Kontroller filer én gang. Appen undersøker mappene samlet og kobler kjente kilder per prøve og kjøring. Mappevalg alene starter ingen filkontroll. Utvid prøven for å se kildene. Ingenting legges i rapportdatabasen ved denne kontrollen.
3. Avklar bare reelle mangler eller konkurrerende kilder under en prøve. Andre filer samler ubrukte alternativer og trenger ingen manuell kobling. Ved avvik gir Filvalg tilgang til Koble kildefil, hvor bare allerede funnet materiale kan velges. Kontroller alltid kildeinnholdet mot prøven.
4. Merk prøvene du vil importere, eller bruk Velg klare prøver. Prøver med Create_report satt til bindestrek eller tomt felt krever dette uttrykkelige prøvevalget. Det er ikke nødvendig å velge hver fil. Et negativt metadataflagg kan ikke overstyres. Trykk Importer valgte og logg inn med personlig PRONTO-konto. En tom brukertabell kan få sin første konto; passord lagres ikke i innstillingene, og kontoen blir ikke administrator.
5. Les resultatet for hver prøve. Importert, Allerede importert, Feilet og Avbrutt betyr forskjellige ting. Prøver med avvik blir ikke kliniske rapporter bare fordi andre prøver i samme jobb lykkes.
6. Trykk Åpne rapporter og logg inn i HTML-arbeidsflaten. Kontroller prøve, run, kilder, CNV, RNA og plott før du begynner vurderingen.

Endres mappevalg, rapportversjon eller CNV-kilde og løsning, nullstilles importplanen. Trykk Kontroller filer for et nytt samlet søk. Den gamle planen kan ikke brukes til import. Endres en kildefil etter kontrollen eller under kopiering, skal importen avvise det berørte grunnlaget. Slik blir det synlig at filene ikke lenger er de som ble kontrollert.

Versjon 0.3 bruker samme PRONTO-ikon i appvindu, oppgavelinje, nettleser og HTML-rapport. Lukk eldre appvinduer før oppdateringen startes. PRONTO_SNARVEI.cmd kan lage en snarvei med riktig ikon etter at hele programmappen er pakket ut på sin faste plass.

Avbryt er en samarbeidsbasert stopp ved trygge kontrollpunkter. Allerede fullførte prøver beholdes. En prøve som ikke har fullført sin databaseinnlegging skal ikke stå igjen som en halv rapport. Lukkes appen mens en jobb pågår, venter den til jobben kan avsluttes trygt. Det er ikke en tvungen prosessavslutning av et eksternt analyseprogram.

### Starte stoppe og åpne rapportserveren

Start server starter den lokale rapportserveren på 127.0.0.1. Åpne rapporter starter den ved behov og åpner adressen i nettleseren. Start av serveren importerer ingen data. Stopp stanser bare en server som denne appen eier. Ved avslutning stanser appen sin egen server etter at pågående HTTP-arbeid er ferdig.

En allerede kjørende desktopserver kan gjenbrukes når den beviser samme database, hemmelige nøkkel og programidentitet. Den vises som kjørende, men appen tar ikke eierskap til å stoppe den andre prosessens server. En annen tjeneste eller database på samme port gir portkonflikt. Den eldre start_web-serveren har ikke desktopserverens helseprotokoll; stopp den kontrollert eller velg en annen port.

Innstillinger kan lagre en eksisterende PRONTO-datamappe og port for neste oppstart. Dette endrer ikke databasen midt i økten. Opprettelse av en ny tom datarot gjøres eksplisitt med --data-root. Logg ut av appen avslutter appens importidentitet; nettleserens rapportinnlogging styres separat.

### Den eldre oppstarten

scripts/start_web.py kan fortsatt starte bare webdelen. Den bruker utviklingsserver, krever åpen terminal og støtter --database, --port, --check og --setup-user. --database må peke på en eksisterende fil. Brukeropprettelse med --setup-user gir den nye kontoen tilgang til alle rapporter som finnes akkurat da. Dette gjelder den eldre kommandoen; første bruker opprettet i desktopappen får ingen generell tilgang til eksisterende rapporter.

## 8 Daglig bruk av arbeidsflaten

### Fra oversikt til vurdering

Rapportoversikten viser bare rapporter som kontoen har tilgang til, med 25 per side. Den skiller aktiv arbeidskladd fra siste ferdigstilte revisjon. Åpne rapporten og kontroller prøve, run, referansebygg og kildenes fullstendighet før du begynner tolkningen. Historiske revisjoner er skrivebeskyttet.

Trykk Edit mode for å redigere. Variant review viser småvarianter og deres kildedata. Inc eller Exc angir om funnet skal rapporteres. Review angir klassifisering. Report highlight velger Key relevant findings, mens IGV QC registrerer vurdering av lesestøtte. Søk, filtre og sortering endrer bare visningen, ikke lagrede beslutninger.

Expand table åpner samme tabell i en justerbar dialog. Zoom skalerer hele tabellen. Når dialogen lukkes, følger de samme endringene tilbake til fanen. Kontroller alle kildekolonner ved behov; det er ingen automatisk ny ekstern annotering i denne visningen.

CNV har egne valg for Gain eller Loss og Cytoband, samt Add CNV row. En manuell rad har egne felter for gen og Tumor_FC; øvrige kildefelt er tomme. En inkludert manuell CNV må ha et gen før ferdigstilling. RNA har tilsvarende inkludering og fremheving. QC-kommentarene for CNV og RNA skrives i hver sin fane.

### QC og rapporttekst

Fem vurderingsområder dekker småvarianter, CNV, RNA, mutasjonssignaturer og samlet QC. Tilstandene er Not reviewed, Pass, Conditional og Fail. Et grønt kildeplott eller et gult felt i en kildearbeidsbok er ikke i seg selv en manuell QC-signering.

Report samler rapporttekst, blant annet sykehistorie, sammendrag, terapeutisk kontekst, variantbeskrivelse, klinisk evidens, studier, oppfølging, metode, referanser og tilleggsopplysninger. Det finnes ikke automatisk medisinsk tekstproduksjon eller kildesøk for disse feltene. Fagbrukeren er ansvarlig for innholdet.

### Lagre og avslutte økten

Save må trykkes eksplisitt. Det er ingen autosave og ingen normal lagring av vurderingen i localStorage. Last siden på nytt etter vellykket lagring og kontroller at arbeidet består. Ved arbeidsdagens slutt må usignert arbeid være lagret. Ferdigstill først når rapporten er faglig klar og alle lokale endringer er lagret.

## 9 Arbeidskladder revisjoner og konflikter

En aktiv WorkingDraft er en redigerbar arbeidskopi. Save erstatter innholdet i denne kladden og øker kladdens version. Den oppretter ikke en full historisk rapportrevisjon for hvert klikk. Dette betyr at historikkvisningen ikke kan brukes til å hente frem vilkårlig tekst fra hver tidligere kladdelagring.

| Handling | Virkning |
| Save | Lagrer kladden og en liten hendelse. Tidligere kladdeinnhold overskrives. |
| Finalize | Krever lagret kladd, oppretter en FINAL ReviewRevision og fjerner den aktive kladden. |
| Start new revision | Kopierer valgt lagret DRAFT eller FINAL til ny arbeidskladd. Den valgte historiske revisjonen beholdes. |
| Erstatt aktiv kladd | Krever bekreftelse før den eksisterende kladden erstattes. Sikre uferdig arbeid først. |
| PDF eksport | Bevarer den eksporterte kladden som en lagret revisjon. Videre redigering går i neste revisjon. Eksport signerer ikke rapporten. |
| RESET | Nullstiller vurderingsinnhold gjennom en eksplisitt kommando. ReportData endres ikke. |

### Samtidig arbeid

Kladderevisjon og version fungerer som endringstoken. En nettleser som bygger på gammelt grunnlag får HTTP 409. Serveren skal dermed avvise en foreldet lagring fremfor å overskrive nyere arbeid. Dette er konfliktdeteksjon, ikke samskriving eller automatisk sammenslåing av to personers arbeid.

Ved feil skal siden holdes åpen. Bruk tilbudet om lokal JSON-kopi for å sikre de ulagrede endringene. En JSON-nedlasting bekrefter ikke at databasen er oppdatert. Last deretter siste lagrede tilstand og avstem forskjellene manuelt. Nedlastet gjenopprettings-JSON importeres ikke automatisk tilbake til databasen.

FINAL kan ikke redigeres direkte. Start en ny revisjon for videre arbeid. Historikk åpnes med ?revision=N og skal beholde det opprinnelige innholdet. I den ordinære arbeidsflaten kommer identitet fra innlogget konto. Gamle demo eller revisjonsposter kan ha egenregistrerte initialer; disse beholder opprinnelig attribusjon.

## 10 Filgjenkjenning import og datainnhenting

### Fra kjøringsmapper til en kontrollert plan

pronto_ingest/discovery.py går gjennom de valgte mappene uten å følge symbolske lenker eller Windows-junctions. Søk er begrenset til 50 000 filer og 30 undermappenivåer. Kjente kildetyper er CSV, TSV, TXT, XLSX, PNG og PDF. BAM, CRAM, FASTQ og VCF brukes ikke som innlesing til varianttabellen og kopieres ikke av denne importflyten.

Metadata bestemmer kombinasjonene av Sample_id og Sequencing_run_id. I TSOPPI-profilen avgrenses radene til den aktuelle kjøringen og DNA-prøvemappene; historiske metadata blir ikke egne rapporter. Et positivt Create_report-flagg gir et forhåndsvalgt prøvevalg. Bindestrek eller tomt felt krever uttrykkelig avkryssing, mens negative eller ukjente verdier ikke kan overstyres. Den eldre generelle profilen beholder kravet om positivt metadataflagg. Study_id er valgfritt. Rapportidentiteten bygger på Sample_id og Sequencing_run_id.

Påkrevde datakilder er metadata, summary og variants samt en eksplisitt DNA/RNA-kobling. I den generelle profilen kommer denne fra sample_list.tsv med én DNA-tumorprøve. TSOPPI-profilen kan bruke entydige kommentarer i concordance- og variantfiler i stedet. Alle tilgjengelige koblingspåstander må være samstemte, inkludert eventuell sample_list. RNA utledes aldri fra et lignende prøveprefiks. En intern sample_list-representasjon opprettes bare i det midlertidige adapterområdet, og originalfilene bevares i kildearkivet.

DiscoveryPlan inneholder mapper, ReportPlan per prøve, ufordelte kandidater, advarsler og filsignaturer. ReportPlan er klar bare når påkrevde roller er entydige og ingen blokkerende avvik gjenstår. Ukjente filer velges ikke automatisk. Et funn på disk er ikke en beslutning om at filen tilhører en pasient.

pronto_ingest/naming.py gjenkjenner navnefamilier uten å normalisere prøve- eller kjøringsidentiteten. Store og små bokstaver, vanlige skilletegn og versjonssuffiks som v2 kan variere i rolleordene. Metadata gjenkjennes fra kolonner og eksakt kjøring. Analysesammendrag kan ha et generelt navn når innhold og kjøringsmappe stemmer. Råmappen kan ha det kjente TSO_500_LocalApp_postprocessing_results-suffikset. Flere konkurrerende kandidater for samme rolle blir fortsatt et avvik; appen velger ikke vilkårlig den første filen.

| Rolle | Gjenkjenning og kobling |
| metadata | Kolonnene Sample_id, Sequencing_run_id og Study_id. Eksakt prøve og run må finnes entydig. |
| summary | Kolonnene sample_id, TMB og MSI. Eksakt prøve eller prøvens _P-suffiks. |
| variants | Gene_symbol, Genomic_location og DNA_change. Eksakt prøvemappe eller støttet prøvesuffiks. forQC foretrekkes fremfor den alternative tabellen. |
| sample_list | sample_type og sample_ID, inkludert støttet kommentarheader. Eksakt DNA-tumoridentitet og deklarerte RNA-koblinger. |
| cnv_table | Gene_Symbol og de støttede CNV-kolonnene. Eksakt prøve-ID når den finnes, ellers eksplisitt valg av generisk tabell. |
| rna_table | Provisional_Event_Type og de støttede RNA-kolonnene. Rader begrenses til DNA-prøven og tillatte RNA-ID-er. |
| cnv_plot og qc_plot | Kjente filnavn og eksakt prøvekobling. Generisk filnavn blir ikke automatisk riktig prøve. |
| other_plot | Kjente domeneplott i et bekreftet prøvescope eller gjennom eksplisitt kobling. |

De fire arbeidsmappene fra jobb-PC-en er kartlagt ved visning. Det støttede katalogmønsteret og koblingskommentarene er prøvd med syntetiske filer; full import av den faktiske kjøringen gjenstår. Nye filnavn, prøveprefikser, kolonner, ark eller katalogmønstre må legges inn som en kontrollert profil og testes på representative filer før de kan brukes uten manuell avklaring. Ikke løs ukjent prøvekobling med omtrentlige navnetreff.

### Hva prosesseringen utfører

importer.import_plan krever en aktiv eksisterende bruker. Den oppretter én ImportBatch og behandler prøvene hver for seg. For hver prøve kontrolleres kildeplassering under de valgte mappene, lenker, størrelser og endring siden mappekontrollen. Kildearkivet må ligge utenfor analysemapper og kan ikke være en lenke.

Kildefiler kopieres til en ny privat katalog under raw_imports. Filenes størrelse og SHA-256 kontrolleres før og etter kopiering. Adapterens kanoniske prøvemappe bygges midlertidig fra kopiene og fjernes etter at rapportgrunnlaget er validert. Arkivet beholder kildebytes med genererte navn; ImportSource bevarer opprinnelig navn og rolle. Rapportsider skal ikke få eksponert arbeidsstasjonens absolutte kildestier.

Interne adaptertabeller bruker tabulator som skilletegn, også når originalen er CSV. Originalkolonner, råverdier, flerlinjede felt og kontrollsum bevares i kildetabellen og arkivet. En kommentar som står inne i et sitert datafelt skal ikke fjernes som en filkommentar.

TMB og MSI leses fra sammendraget; importen gjør ikke en ny analyseberegning. Småvariantene kommer fra den annoterte tabellen. CNV og RNA leses som komplette støttede kildetabeller, og identitetskolonner filtreres på bekreftet prøve. Et manuelt valg av fil overstyrer ikke en motstridende prøve-ID i tabellradene. Generiske tabeller uten prøveidentitet krever at brukeren faktisk har kontrollert sammenhengen.

Plott valideres før innlegging. Rapporten tillater høyst 100 plott og samlet 64 MiB vedleggsbytes; hvert vedlegg har grense på 12 MiB. PNG-plott kontrolleres for gyldig bildeinnhold og høyst 64 millioner piksler. Et PDF-plott kan ha høyst 100 sider og må kunne rasteriseres med de tilgjengelige PDF-verktøyene.

Et kildefingerprint beregnes av prøve, run, kilderoller og filhashene. Deretter opprettes ReportRecord, første DRAFT ReviewRevision, ReportAsset, importørens ReportGrant, ImportItem og ImportSource i én databasetransaksjon. Første kladd oppgraderes av den eksisterende kontraktflyten når arbeidsflaten åpner den. Importen gir ikke ReportWriteGrant for BAM eller CRAM.

### Dubletter konflikter og delvise kjøringer

Samme rapportidentitet med samme kjente fingerprint og tilgang for importøren gir Allerede importert. Det opprettes ikke en ny rapport, og manuelle vurderinger erstattes ikke. Samme prøve og run med annet grunnlag eller uten dokumentert tidligere importfingerprint avvises som konflikt. Hvis rapporten finnes uten at importøren har tilgang, gir ikke en ny import automatisk tilgang.

Feil eller avbrudd før prøveinnleggingen er ferdig ruller tilbake den prøven og rydder det nye, uferdige kildearkivet. Fullførte prøver i samme jobb beholdes. Jobben får COMPLETED, PARTIAL eller CANCELLED og et resultat per prøve. Ved en brå avslutning av hele PC-en kan en RUNNING-post eller en foreldreløs kildekatalog kreve teknisk undersøkelse. Ingen automatisk omstart eller vilkårlig sletting av slike kataloger skal antas.

Filgjenkjenning og import er en lokal prosess for ferdige analyseresultater. Den kjører ikke variant calling, CNV-analyse eller en Archer-pipeline. MolStat, Solide og Archer er brukt som referanser for arbeidsflyt og appstruktur; de startes ikke som skjulte avhengigheter når PRONTO importerer.

### Utviklerens isolerte testinnganger

scripts/create_desktop_example.py lager fire mapper med syntetiske prøver, historiske metadata, DNA/RNA-kommentarer, to rapportversjoner, sammenslått CNV, Cancan-løsninger og plott. Programmet leser ingen pasientfiler. Bruk en separat testdatabase. Eksemplet dokumenterer kjent struktur og er ikke bevis på at jobb-PC-ens mapper er identiske.

```powershell
.\.venv\Scripts\python.exe scripts\create_desktop_example.py --output Out\desktop-example
.\.venv\Scripts\python.exe -m pronto_desktop --data-root 'C:\PRONTO-test' --port 8772
```

Den eksisterende CLI-kommandoen export --fixture ous kan fortsatt produsere et reproduserbart ReportData-grunnlag. render-html kan bygge en frittstående skrivebeskyttet HTML med --asset-root. --review kan koble en validert vurdering til eksporten. CLI-fixtureinngangen er avgrenset teststøtte; desktopimporten er den ordinære brukerinngangen for støttet kjøringsstruktur.

enrich_demo_report blander eksempelprøver og syntetisk HRD med eksplisitt demoformål. Den brukes ikke av desktopimporten og skal ikke aktiveres for klinisk grunnlag.

## 11 HTML PDF og rapportmaler

### Arbeidsflate og frittstående HTML

renderers/html.py bygger den interaktive arbeidsflaten av HTML-deler, CSS, JavaScript og validerte data. projection.py og review_v3 eller review_v4 forbereder visningsinnholdet. Brukerhandlinger sendes til Django gjennom report.js og working-draft.js. Det er ingen separat Node eller React-bygging som må kjøres for vanlig oppstart.

CLI render-html lager en frittstående, skrivebeskyttet rapportflate med innebygde data og støttede plott. HTML-nedlastingsendepunktet lager i stedet et redusert rapportsammendrag gjennom summary_html.py. Dette er to ulike leveranseformater. En eksportert HTML-fil har ikke serverens konto og tilgangskontroll rundt seg; oppbevar den i et godkjent område.

HTML-eksportendepunktet er en kompatibilitetsflyt med deklarerte initialer og lagret ReviewRevision. Det fryser ikke automatisk en aktiv WorkingDraft slik PDF-endepunktet gjør. Ved bruk av dette API-et må klienten velge en faktisk bevart revisjon. Oppgi ikke en uspart kladderevisjon og forvent at den eksporteres.

I leveransen fra 23. oktober 2026 ble summary_html.py rettet slik at gjeldende ReviewState v4 kan eksporteres. Tidligere ble den avvist selv om den var gyldig og ferdigstilt. Regresjonstesten kontrollerer blant annet lagret tekst, escaping, manuell CNV og eksportspor.

Importerte generelle CNV-plott, inkludert Cancan, og RNA-domeneplott vises i de respektive fanene med forstørring. Den bekreftede kilderollen brukes ved plassering; et misvisende filnavn skal ikke flytte et eksplisitt RNA-plott til CNV. Den eldre nisiders CNV-visningen med navngitte panelgrupper er beholdt for det kjente overview-formatet.

### De to PDF oppsettene

Presentation er liggende A4 med pasientfelt, Key relevant findings og kompakte funntabeller. ESMO er stående A4 med sammendrag, resultater og kliniske tekstseksjoner. Malnavnet ESMO beskriver rapportoppsettet og er ikke dokumentasjon på ekstern godkjenning. Lange tabeller og tekster fortsetter på flere sider.

project_report_export i report_pdf.py samler inkluderte småvarianter, CNV og RNA, korreksjoner, QC og notater. Ekskludering overstyrer Highlight. Dublette småvariantforekomster slås sammen ved presentasjon. Kontroller PDF visuelt ved endringer i kolonner, lange tekster eller skriftstørrelser; en bestått JSON-test beviser ikke at en side er lesbar.

PNG, JPEG og WebP som lastes opp som presentasjonsfigurer, dekodes og lagres på nytt som PNG. Maksimalt 8 MB og 64 millioner kildepiksler tillates per opplasting; lagret størrelse skaleres til høyst 16 millioner piksler. Inntil 30 figurer kan velges. Privat per rapport-grense er 64 MB og 100 figurer. Utvalgte figurer kommer på slutten av Presentation PDF, med lagret rekkefølge og bildetekst.

## 12 IGV og genomfiler

### Tre forskjellige bruksmåter

Lokal visning åpner BAM og tilhørende BAI eller CSI fra brukerens maskin i nettleseren. Valg av lokale filer laster ikke BAM-filen opp til serveren. Et regionutdrag inneholder bare de lesningene som faktisk finnes i utdraget. Tom visning utenfor dette området betyr ikke at hele originalprøven mangler lesninger.

Registrerte kilder hentes fra et eksplisitt manifest som kobler reportId, sampleId, referenceBuild, rolle og et konkret data og indekspar. PRONTO leter ikke tilfeldig etter et filnavn. Begge PRONTO_ALIGNMENT_SOURCE_ROOT og PRONTO_ALIGNMENT_REGISTRY_JSON må være satt. Filene skal ligge under den private kilderoten.

Permanent bevaring er et eget løp med eksplisitt bekreftelse, rettigheter, størrelsesgrenser, privat staging og privat lager. Denne funksjonen er avslått uten full konfigurasjon. Native Windows er begrenset til visning; bevaring krever Linux eller et tilsvarende validert Linux-miljø med pysam.

### Referansegenomer

Ved det eldre lokale oppsettet oppdages komplette filpar i .local-web/references/. Med valgt datarot brukes i stedet references/ under den dataroten. Filene heter GRCh37.fa med GRCh37.fa.fai, og GRCh38.fa med GRCh38.fa.fai. Start appen på nytt etter at filpar legges til. Appen laster ikke referansefiler ned automatisk. Den eldre lokale kontrollen 23. oktober fant begge parene. Dette bekrefter ikke at de følger en ny installasjon; innholdets biologiske korrekthet må forvaltes av laboratoriet.

Rapport, BAM eller CRAM og referanse må bruke samme bygg. Innloggede referanseruter støtter nødvendige byteområder. FASTA-innhold krever ett gyldig byteområde ved GET; FAI kan leses samlet opp til 8 MiB. igv.js versjon 3.7.0 følger prosjektet lokalt. Standard genomliste og offentlig CDN brukes ikke.

### Vilkår for permanent bevaring

Separate eksisterende kataloger for STORE_ROOT og STAGING_ROOT må ligge utenfor prosjekt og statisk eller offentlig lagring. Per fil, indeks, rapport og ledig plass må ha eksplisitte grenser. PRONTO_ALIGNMENT_POLICY_APPROVED=true er bare en teknisk bekreftelse på at institusjonen allerede har godkjent lagring, sletting, backup og tilgang. Brukeren må dessuten ha ReportWriteGrant.

Hele filparet valideres, hashes og publiseres først etter vellykket kopiering. Bare READY er synlig. DELETING skjuler et par mens sletting fullføres; en feil skal ikke gjøre det synlig igjen. Upload skjer i sammenhengende deler på høyst 8 MiB. Vanlig Save av rapportvurdering lagrer ingen BAM.

## 13 Konfigurasjon og HTTP grensesnitt

### Viktige innstillinger

| Innstilling | Betydning |
| PRONTO/desktop.json i lokal brukerprofil | Desktopappens huskede datarot og port. Inneholder ikke passord. Visning av aktiv database finnes under Innstillinger. |
| .local-web/config.json | Eldre oppstartsvalg for eksisterende database og port. Gjenbrukes ved første desktopoppstart uten ny datarot. |
| PRONTO_DJANGO_SECRET_KEY | Obligatorisk nøkkel ved direkte Django-oppstart. Lokal launcher bruker secret.key. |
| PRONTO_DJANGO_DB | Eksplisitt SQLite-sti for Django. Launcher setter den fra valgt konfigurasjon. |
| DJANGO_SETTINGS_MODULE | Velger settings, local_settings eller test_settings. Testoppsett skal bare brukes til tester. |
| PRONTO_WORKING_DRAFTS | true aktiverer gjeldende kladdeflyt på egen installasjon. Lokal launcher aktiverer den automatisk. |
| PRONTO_STATIC_ROOT | Samlekatalog for collectstatic på en separat server. |
| PRONTO_IGV_GRCh37_FASTA_PATH og FAI_PATH | Serverfiler for lokalt servert GRCh37. Tilsvarende finnes for GRCh38. |
| PRONTO_IGV_GRCh37_FASTA_URL og FAI_URL | Samme origin-ruter for IGV-referansen. Tilsvarende finnes for GRCh38. |
| PRONTO_ALIGNMENT innstillinger | Separate kilder, lager, staging, grenser, lokal valideringsreferanse og policy. Se IGV-guiden. |

ALLOWED_HOSTS er en Python-innstilling, ikke en ferdig miljøvariabel i denne leveransen. Et annet vertsnavn krever et eget kontrollert settings-oppsett. Lokal HTTP slår av Secure-kravet for cookies bare i local_settings og brukes sammen med binding til loopback. Grunnoppsettet beholder Secure-cookies.

### De viktigste rutene

| Rute under rapporten | Bruk |
| GET /reports/ og /reports/ID/ | Oversikt og autorisert rapportvisning. |
| POST /reports/ID/working/ | Gjeldende SAVE, RESET, FINALIZE og REOPEN. |
| GET /reports/ID/?revision=N | Skrivebeskyttet historikk. |
| POST /reports/ID/pdf-exports/ | Eksakt lagret revisjon, ESMO eller PRESENTATION. |
| POST /reports/ID/html-exports/ | Kompatibel HTML-eksport av bevart revisjon. |
| POST /reports/ID/figures/ | Privat opplasting av presentasjonsfigur. |
| /reports/ID/alignments/ | Autoriserte filområder og separat bevaringsprotokoll. |
| /accounts/login/ og /accounts/password/ | Innlogging og passordendring. |

Arbeidskommandoen bruker schemaVersion 2.0, reportId, action, baseRevision og expectedVersion. SAVE har en full ReviewState v4 som draft. REOPEN bruker sourceRevision og ved behov replaceWorking. Maksimal JSON-kropp er 1 MiB. 201 betyr lagret, 409 konflikt, 422 ugyldig innhold, 413 for stort innhold, 401 manglende innlogging og 403 vanlig CSRF-avvisning. Manglende rapporttilgang gir normalt 404.

## 14 Sikkerhetskopi flytting og gjenoppretting

### Hva backup må omfatte

Ta backup av den aktive databasen, brukerprofilens PRONTO/desktop.json, relevant oppstartskonfigurasjon og secret.key gjennom et beskyttet internt område. Ved eldre oppsett må .local-web/config.json bevares. Ved ny datarot følger database/pronto.sqlite3, raw_imports, references og secret.key dataroten; innstillingene i lokal brukerprofil ligger utenfor den. Ta separat vare på referansegenomer og indekser, analysegrunnlag, eventuelt alignment-register, bevarte filpar, rapporteksporter og driftens settings. Installer .venv på nytt fra requirements fremfor å kopiere miljøet til en annen maskin.

Bruk SQLite backup API for en konsistent kopi når databasen er åpen. En tilfeldig filkopi mens noen skriver kan mangle transaksjoner eller kreve WAL-filer. Ved en helt stoppet tjeneste kan en kontrollert filkopi brukes. Stopp også eventuelle opplastinger hvis backup skal samordnes med et privat alignment-lager.

### Backup fra appen og teknisk reservekommando

Ta sikkerhetskopi under Innstillinger bruker SQLite backup API og kontrollerer integrity_check. Kopien ligger i datarotens backups. Knappen tar ikke en komplett kopi av råarkiv, referanser eller bevarte alignments. Planlegg samlet backup og en verifisert gjenoppretting av disse delene.

### Eksempel med SQLite backup API

Kjør følgende som et eget Python-skript i et beskyttet område. Bytt stiene til de avtalte filene. Målet skal være en ny fil; bruk ikke den aktive databasen som mål.

```python
from pathlib import Path
import sqlite3

source = Path(r'C:\PRONTO-data\pronto.sqlite3').resolve()
target = Path(r'C:\PRONTO-backup\pronto-2026-10-24.sqlite3')
target.touch(exist_ok=False)
with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
    with sqlite3.connect(target) as dst:
        src.backup(dst)
with sqlite3.connect(target) as restored:
    assert restored.execute('PRAGMA integrity_check').fetchone() == ('ok',)
    assert not restored.execute('PRAGMA foreign_key_check').fetchall()
```

### Flytting til ny maskin

1. Stopp den gamle serveren og sikre eventuelle ulagrede nettleserendringer. Ta en siste backup. Dokumenter kodeversjon og migreringsnivå sammen med backupen.
2. Installer samme kodeversjon på ny maskin. Kopier backup til en ny privat driftssti; behold originalbackupen urørt.
3. Overfør nøkkel og nødvendige filer via godkjent intern kanal. Ikke legg secret.key, innloggingstekster eller databasen i kildekodearkivet.
4. For en ny datarot legges databasen i database/pronto.sqlite3 og de tilhørende mappene og nøkkelen på riktig plass. Start desktopappen med --data-root som peker på denne dataroten, og kontrollér aktiv fil under Innstillinger. Ved beholdt eldre oppsett brukes scripts/start_web.py --database for å oppdatere den eksisterende filstien. Kjør --check etter backup; dette kan migrere databasen.
5. Kontroller innlogging, tilgang, rapportantall, siste FINAL, aktiv kladd, rapportbilder, figurer og begge PDF-formatene. Kontroller IGV separat.
6. Avtal når den nye installasjonen blir skrivende hovedinstallasjon. Hold den gamle avslått for å hindre to divergerende databaser.

Ved en mislykket oppgradering gjenopprettes både tidligere kode og den tilhørende databasebackupen. Ikke forsøk en tilfeldig baklengs migrering. Backupfrekvens, oppbevaringstid og akseptabelt datatap må fastsettes av driften. Save-hendelsene gir ikke full gjenoppretting av overskrevne arbeidskladder.

## 15 Tilgang og forutsetninger for serverdrift

### Kontoer og rapporttilgang

Bruk personlige kontoer i ordinær drift. Desktopimporten gir ReportGrant til den aktive importøren for nyopprettede rapporter. Andre brukere trenger eksplisitt tildeling. Desktopappens første konto gir ingen generell tilgang til eksisterende rapporter. Den eldre scripts/start_web.py --setup-user gir derimot tilgang til alle rapporter som finnes på opprettelsestidspunktet; vurder derfor om dette passer den lokale arbeidsdelingen før kontoen opprettes. Det finnes ikke et ferdig administratorgrensesnitt for all rapporttildeling.

En teknisk forvalter kan bruke Django shell med korrekt database og settings. get_or_create på ReportGrant kan gi tilgang til en bestemt eksisterende rapport og bruker; sletting av den samme koblingen trekker tilgangen tilbake. Ikke gi ReportWriteGrant som standard. Den gjelder genomfilbevaring, ikke det vanlige rapportarbeidet. For å sperre en konto settes is_active til false.

### Lokalt produkt og delt tjeneste

Desktopappen bruker en egen, begrenset WSGI-server med binding til 127.0.0.1 og kontrollert eierskap. Den eldre start_web.py bruker Djangos utviklingsserver. Begge er laget for lokal arbeidsstasjon. Å endre adressen til 0.0.0.0 er ikke en ferdig produksjonsinstallasjon. Delt drift trenger en valgt produksjonsserver, HTTPS, vertsliste, riktig proxy-oppsett, sikker nøkkelforvaltning, statiske filer, logger, backup, overvåking og en test av samtidige brukere.

Grunninnstillingene mangler HTTPS-redirect og HSTS. check --deploy varsler om dette. Et eget produksjonsoppsett må håndtere HTTPS på riktig sted og kontrollere proxy-innstillingene. Ikke aktiver HSTS ukritisk før domenets HTTPS-drift er verifisert. SQLite støtter ikke Djangos select_for_update; flerkontobruk og eventuelt annet databasevalg må derfor vurderes og testes i det faktiske driftsmiljøet.

### Drift som må etableres utenfor applikasjonen

Overvåk oppstart, feil ved lagring og eksport, ledig disk, backupalder og databaselåser. Ved alignment-bevaring må også opplastinger og DELETING-poster følges opp. Det finnes ikke ferdig sentral varsling eller en etablert vaktordning i denne leveransen. Logger kan inneholde intern driftsinformasjon og skal ikke legges i Git.

Demo-kommandoene run_demo, resume_demo og seed_demo_patients er for isolerte demonstrasjonsdatabaser. De kan aktivere demoidentitet og bruker egenregistrerte initialer. De er ikke ordinær innlogging for klinisk drift. .local-web skal heller ikke sendes som en åpen del av dokumentpakken, selv om installasjonen inneholder testprøver.

## 16 Vedlikehold og feilsøking

### Oppgradering

Ta en konsistent backup og noter nåværende kodeversjon før endring. Installer nye requirements i et isolert miljø. Kontroller makemigrations --check --dry-run, kjør de nødvendige migreringene på en testkopi og gjennomfør relevante tester. Kontroller lange rapporter visuelt i begge PDF-formatene. Planlegg en tilbakeføring av både kode og database før produksjonskopien endres.

### Vanlige problemer

| Symptom | Første kontroll og tiltak |
| Ingen rapporter i oversikten | Kontroller aktiv database under Innstillinger og ReportGrant for HTML-brukeren. En ny installasjon er tom til data importeres. |
| Importplanen har ingen prøver | Kontroller metadataheaders, eksakte prøve-ID-er og kjørings-ID-er. Faktisk jobbstruktur kan kreve en ny profil. |
| Ingen import etter mappevalg | Velg PRONTO-mappen eller separate kildemapper, velg versjon og trykk Kontroller filer. Merk prøvene før import. Les avvik, kildeliste og prøveidentitet før Importer valgte. |
| Samme prøve avvises | Kontroller fingerprint og opprinnelig import. Endret eller ukjent rågrunnlag skal ikke overskrive vurderte rapporter. |
| Husket database er utilgjengelig | Gjenopprett tilgang til riktig datarot. Ikke slett desktop.json eller lag en tom erstatning uten bevisst nyinstallasjon. |
| Innlogging virker ikke | Kontroller konto, passord, is_active, korrekt port og korrekt local_settings ved lokal HTTP. |
| Porten er opptatt | Identifiser den aktuelle tjenesten eller velg ny port for neste oppstart. Appen gjenbruker bare en server med riktig privat identitet og stopper ikke andres prosesser. |
| Manglende SECRET_KEY | Bruk launcheren eller sett en privat nøkkel ved direkte Django-oppstart. Ikke bruk testnøkkelen i drift. |
| Lagre gir konflikt | Sikre lokal JSON, last siste tilstand og avstem manuelt. 409 skal ikke løses ved å overskrive databaseraden. |
| Feil ved PDF eller HTML | Behold kladden. Kontroller serverlogg, lagret revisjon, kontrakt og tilgjengelige vedlegg eller figurer. |
| CNV eller QC-plott vises ikke | Kontroller pdfinfo og pdftoppm, ReportAsset, deklarert hash, filtype og vedleggsgrense. |
| IGV mangler referanse | Kontroller komplett FASTA og FAI, riktig bygg og autentiserte referanseruter. Start lokal server på nytt. |
| IGV viser ingen reads | Kontroller filpar, indeks, koordinat, chr-navn, referansebygg og at regionen finnes i utdraget. |
| BAM Save er utilgjengelig | Windows er kun for visning. På Linux kontrolleres policy, private røtter, grenser, referanse og write grant. |
| Database is locked | Sikre ulagret arbeid, kontroller konkurrerende skrivere og disk. Ikke slett SQLite-filer eller journalfiler. |
| Vedlegg hash stemmer ikke | Stans bruken av vedlegget og kontroller import eller backup. Ikke omgå hashkontrollen. |

### Alignment vedlikehold

På et konfigurert Linux-oppsett kan clean_alignment_staging --dry-run vise utløpte sesjoner. Kommandoen uten --dry-run rydder eide stagingbytes, men sletter ikke READY-par. reconcile_alignment_store identifiserer gamle foreldreløse par og midlertidige kopier. --delete skal bare brukes i vedlikeholdspause uten aktive opplastinger og etter backup. Uventede filer krever manuell undersøkelse.

Utfyllende driftstekst finnes i docs/igv-alignment-operations.md. Regler for fixtures og lokaldata finnes i docs/fixture-and-privacy-policy.md. Hold nye skjermbilder, databaser, kildearbeidsbøker og rapporteksporter utenfor Git.

## 17 Kontrollresultater og verifiseringsgrenser

### Kontroll av den nye appen

Kontrollene gjelder programgrunnlaget som identifiseres i pakkens manifest. App- og importtestene bruker midlertidige databaser, syntetiske filer eller godkjente fixtures. Resultatene gir teknisk kontroll av den støttede filstrukturen; de erstatter ikke verifisering av den reelle kjøringen fra jobb-PC-en.

| Kontroll | Resultat ved denne leveransen |
| Målrettede app og importtester | Se leveransemanifestet for endelig antall. Omfatter firemapperprofil, eldre oppsett, eksplisitt prøvevalg, Cancan, DNA/RNA-kobling, GUI og faktisk HTTP-gjennomkjøring. |
| Samlet pytest | Endelig resultat og kjøretid står i leveransemanifestet og kontrollnotatet. |
| Django requesttester | 108 tester, OK, én utelatt. Kjøretid 104,274 sekunder. |
| System og modellkontroll | Django system check uten feil. Ingen uregistrerte modellendringer. pip check uten brutte avhengighetskrav. |
| Native grensesnitt | Bakgrunnsjobber, kjøringsmapper, versjonsvalg, prøvevalg, kildekobling, kontoopprettelse, importøridentitet, historikk, avbryt, backup, serverstyring og tastaturnavigasjon kontrollert. Fem sider gjennomgått visuelt med syntetisk eksempel. |
| Import og sikkerhet | Prøvegrenser, RNA-kobling, generisk CNV-valg, endrede kilder, dubletter, konflikter, arkiv og transaksjon per prøve kontrollert i tester. |
| Databasemigrering og backup | Tom og eksisterende syntetisk database, backup før migrering, WAL-innhold, kontogjenbruk og utilgjengelig husket datarot kontrollert. |
| Serverlivsløp | Oppstart, stopp, privat helseidentitet, portkonflikt, gjenbruk uten eierskap og fullføring av pågående HTTP-kall kontrollert. |

Den nye appen er også startet synlig mot det eksisterende lokale oppsettet. Rapportserveren svarte på port 8772. Innholdshash før og etter viste bevarte rapporter, vurderinger, vedlegg, tilganger og kontoer. Nøkkelen ble beholdt, databaseintegritet og fremmednøkler var gyldige, og sikkerhetskopien før migrering 0011 ble kontrollert. Dette er en bevaringskontroll av eksisterende innhold, ikke en klinisk godkjenning.

### Tidligere databasestatus fra 23 oktober

Ved den tidligere overleveringen 23. oktober 2026 ble den daværende lokale databasen kontrollert med integrity_check, foreign_key_check, kontraktvalidering og vedleggshash. Den kontrollen omfattet 31 rapporter, 85 vurderinger eller arbeidskladder og 45 vedlegg. Tallene er en datert historisk kontroll, ikke nye opptellinger for denne appversjonen eller et løfte om innholdet i en tom installasjon.

Den tidligere gjennomkjøringen på separat database kontrollerte import, CSRF-beskyttet Save, 409 ved foreldet lagring, Finalize, historikk og både PDF og HTML. Rettingen av HTML-eksport for gyldig ReviewState v4 følger fortsatt koden. Resultater og rålogger må leses sammen med dato og nøyaktig versjon i den aktuelle pakken.

### Gjenstående miljøkontroller

Den leverte jobbkjøringen er prøvd lokalt i separat database: alle 13 prøver ble importert, inkludert åtte uten Study_id. Python FELLES, Ivanti, tilgangsrettigheter og Poppler må fortsatt kontrolleres på jobb-PC-en. Klinisk innhold er ikke faglig godkjent av den tekniske testen. Native Windows dekker ikke de Linux-avhengige funksjonene for permanent BAM eller CRAM-bevaring. Utelatte tester er ikke beståtte tester.

Docker Linux-tjenesten var ikke tilgjengelig ved den tidligere kontrollen og Docker-fixtureløpet ble da ikke kjørt på nytt. Dockerfile beskriver den eldre kommandolinjeflyten, ikke en ferdig desktop- eller webdistribusjon. Det foreligger heller ikke ekstern produksjonsdrift, klinisk godkjenning, generell belastningstest eller full sårbarhetsrevisjon av avhengighetene i denne overleveringen.

## 18 Sjekkliste for formell overtakelse

### Det som følger med

Kildekodepakken omfatter desktopappen, importen av kjøringsmapper, databaseendringen 0011, rapportarbeidsflaten og tilhørende tester. Den tidligere HTML-rettelsen og regresjonstesten er beholdt. Kontrollnotatet oppgir nøyaktig commit, filnavn, testresultater og eventuelle begrensninger. Denne manualen forklarer komponenter, dataflyt, kontrakter, database, oppstart, vurdering, eksport og drift. Den lokale databasen er ikke en del av kildekodepakken.

### Avklar og kvitter ved overtakelsen

| Punkt | Hvem kvitterer |
| Ny faglig og teknisk eier er navngitt. | Avgiver og mottaker |
| Riktig kodeversjon er installert fra arkivet eller tilsvarende Git-commit. | Teknisk forvalter |
| Eksisterende database eller bevisst tom installasjon er valgt. | Teknisk og faglig eier |
| Ny personlig konto og riktige rapporttilganger er kontrollert. | Driftsansvarlig |
| Backup, beskyttet lagringssted og gjenoppretting er overtatt. | Driftsansvarlig |
| Kildegrunnlag og referansegenomer er lokalisert og faglig verifisert. | Faglig eier |
| Rapporten er gjennomgått fra lagring til FINAL og begge PDF-formatene. | Mottaker |
| De faktiske fire kjøringsmappene er importert i testmiljø, og prøvekobling og innhold er faglig validert. | Teknisk og faglig eier |
| Omfanget lokal bruk eller delt serverdrift er besluttet. | Systemeier |
| Linux-bevaring av alignments forblir av eller er særskilt validert og godkjent. | Data og driftsansvarlig |
| Tidspunkt for å ta gammel skrivende installasjon ut av bruk er avtalt. | Avgiver og mottaker |

### Videre arbeid som ikke skal skjules

For ordinær klinisk innføring må mottakeren kontrollere den implementerte pasientkoblingen mot de faktiske laboratoriefilene, supplere filprofilen ved avvik, validere alle beregninger og presentasjoner faglig og velge et godkjent driftsmiljø. Delt serverdrift trenger produksjonsserver og HTTPS. Eventuell BAM eller CRAM bevaring trenger Linux-kontroll, lagerpolicy og backup med filsystemet. Dette er innføringsansvar, ikke funksjoner som aktiveres av å overta Word-filen.

Ingen automatisk sammenslåing av samtidige kladder, journalsystemkobling, kontinuerlig ekstern annotering eller full historikk av hver Save inngår i den beskrevne flyten. Ved videreutvikling skal kontrakter, innhold og lagringsregler holdes konsistente mellom arbeidsflate, historikk, HTML og PDF.

## 19 Referanser og kommandoer for utvikleren

Følgende filer i leveransen er de konkrete tekniske referansene. De eldre arkitekturskissene utenfor den aktive prosjektmappen beskriver tidligere idéer og skal ikke behandles som en presis beskrivelse av dagens implementasjon.

| Referanse i prosjektet | Når den brukes |
| docs/desktop-app.md | Praktisk bruk av desktopappen, kjøringsmapper, import, dataflyt, lagring og driftsgrense. |
| docs/oppstart-nb.md | Vanlig lokal oppstart, konto og databasevalg. |
| docs/report-review-workspace.md | Kladder, revisjoner, konflikter og manuelle tabellvalg. |
| docs/integrated-review.md | CNV, RNA, QC, figurer og PDF. |
| docs/review-command-contract.md | Gjeldende kommando API v2 og eldre kompatibilitets API. |
| docs/igv-alignment-operations.md | Referanser, register, privat lagring og opprydding. |
| docs/synthetic-demo.md | Isolert syntetisk pasientkohort. |
| docs/fixture-and-privacy-policy.md | Hva som er godkjent testgrunnlag og hva som holdes utenfor Git. |
| CONTRIBUTING.md og requirements filer | Miljø og testavhengigheter. |
| .github/workflows/test.yml | Autoritative CI-kommandoer for enhetstester og Docker-fixtures. |
| schemas under pronto_report | ReportData v1 og v2, ReviewState v1 til v4. |

### Testkommandoer fra prosjektroten

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-desktop-test.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-browser.txt
$env:QT_QPA_PLATFORM='offscreen'
.\.venv\Scripts\python.exe -m pytest pronto/tests/ingest pronto/tests/desktop -q
.\.venv\Scripts\python.exe -m pytest -q -rs
$env:DJANGO_SETTINGS_MODULE='pronto_web.test_settings'
.\.venv\Scripts\python.exe manage.py test pronto_web.reports
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

test_settings bruker isolerte testinnstillinger og en offentlig testnøkkel. Ikke bruk dette settings-modulet for å starte en ordinær tjeneste. Nettlesertestene finner lokal Chrome eller Edge på støttede Windows-stier; PRONTO_BROWSER_EXECUTABLE kan angi en eksplisitt binær. Browser-testene bruker syntetisk innhold og lokale testservere.

### Versjon og filplassering i den opprinnelige installasjonen

Den samlede løsningen som ble kontrollert, ligger under repos/PRONTO/.worktrees/igv-django-integration i Inpred-arbeidsområdet. Roten repos/PRONTO er en eldre arbeidskopi. Mappenavnet er beholdt ved feilrettingen, selv om Git-branchen kan ha fått et nytt navn. Et navn på en worktree er ikke bevis på hvilken kodeversjon den inneholder; kontroller commit i kontrollnotatet.

Backup fra den nye desktopappen ligger under backups i den aktive dataroten. Den tidligere beskyttede databasebackupen ligger under .local-web/backups i den eldre aktive arbeidskopien. Den konkrete backupfilen er registrert i det lokale kontrollgrunnlaget. Ved overtakelse flyttes denne og den private konfigurasjonen separat, slik kapittel 14 beskriver.


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
