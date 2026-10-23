# PRONTO manual for overtakelse og drift

Teknisk overlevering av rapportløsningen til ny forvalter

23. oktober 2026 · Leveransegrunnlag c2bab16 med rettelse for HTML eksport av ReviewState v4

Denne manualen forklarer hvordan PRONTO installeres, brukes, vedlikeholdes og videreføres. Den dekker hele kjeden fra TSOPPI og kliniske metadata til database, vurderingsarbeid, HTML, PDF og IGV. Målgruppen er både fagbrukeren som skal overta rapportarbeidet, og utvikleren eller driftsansvarlig som skal kunne forvalte løsningen uten muntlig forklaring fra den opprinnelige utvikleren.

Lokal rapportbehandling er kontrollert med automatiske tester, en separat gjennomkjøring av import, lagring, ferdigstilling og eksport, samt kontroll av den eksisterende databasen. Denne leveransen gir et konkret grunnlag for overtakelse. Innføring med reelle pasientdata, flerbrukerdrift og permanent BAM eller CRAM lagring krever de lokale driftsbeslutningene og kontrollene beskrevet i kapittel 15 og 18.

Leveransen består av denne manualen, et eget kildekodearkiv og et kontrollnotat med versjon og testresultater. Kildekodearkivet inneholder den konkrete programversjonen og godkjente testfiler. Den lokale databasen, passord, nøkler, referansegenomer og genererte pasientrapporter overføres separat gjennom godkjent intern lagring.

## 1 Slik tar neste person over

### Start her

Les kapittel 2 for helhetsbildet, kapittel 7 for oppstart, kapittel 8 for daglig bruk og kapittel 14 for sikkerhetskopi. Utvikleren bør deretter lese datakontraktene, databasemodellen og importløpet i kapittel 5, 6 og 10. Kapittel 18 brukes ved selve overtakelsen.

Den nye forvalteren må overta tre forskjellige ting: programkoden, det private driftsoppsettet og ansvaret for datagrunnlaget. Et kildekodearkiv alene inneholder ingen brukerkontoer eller vurderinger. En databasekopi alene inneholder ikke alle genomfiler, den hemmelige nøkkelen eller et komplett installert Python-miljø.

### Anbefalt første arbeidsøkt

1. Pakk ut kildekoden til en ny prosjektmappe. Kontroller versjonen mot kontrollnotatet. Ikke arbeid videre i den eldre PRONTO-hovedmappen ved en feil.
2. Installer Python-miljøet og Poppler som beskrevet i kapittel 7. Bruk en isolert database ved første kontroll.
3. Avtal om overtakelsen gjelder en tom installasjon eller eksisterende rapporter og historikk. Flytt eksisterende privat tilstand etter fremgangsmåten i kapittel 14.
4. Opprett en personlig konto. Kontroller at akkurat de riktige rapportene er synlige, og at en annen konto uten rapporttilgang ikke kan åpne dem.
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

PRONTO omfatter en eldre kommandolinjeflyt for rapportgenerering og en nyere nettbasert arbeidsflate. Den eldre flyten behandler TSOPPI-resultater og kan produsere PowerPoint og remisseutkast. Nettløsningen bygger et validert rapportgrunnlag, viser det i HTML og lagrer brukerens vurderinger i Django-databasen. Nettløsningen lager PDF direkte med ReportLab.

| Trinn | Hva skjer | Ansvarlig del |
| 1 Analysegrunnlag | TSO500 og TSOPPI produserer annoterte varianttabeller, sammendrag, prøveoversikt og plott. | Ekstern analysepipeline |
| 2 Kliniske metadata | Prøve, run, pseudonym og kliniske opplysninger knyttes til analysen. | InPreD metadatafil og laboratoriets rutine |
| 3 Rapportgrunnlag | Adapteren leser deklarerte filer, lager stabile identifikatorer og lagrer kildespor. | pronto_report/adapters/ |
| 4 Privat lagring | Rapport, bilder, vurderinger og tilganger lagres gjennom Django ORM. | pronto_web/reports/ |
| 5 Arbeidsflate | Python bygger HTML; JavaScript håndterer tabeller, redigering, dialoger og kommandoer. | renderers, templates og static |
| 6 Faglig vurdering | Brukeren velger inkludering, klassifisering, QC, kommentarer og rapporttekst. | ReviewState og WorkingDraft |
| 7 Leveranse | En lagret vurdering vises som historikk, FINAL, PDF eller en separat HTML-rapport. | Eksportendepunkter og renderere |

### Hvor data faktisk hentes fra

Webappen leser hovedsakelig rapportgrunnlaget fra sin egen database. Den søker ikke løpende i ClinVar, COSMIC, gnomAD, OncoKB eller sykehusets journalsystem. Slike annoteringer finnes eventuelt allerede i TSOPPI-tabellene. Det finnes ingen generell overvåking av nye run-mapper eller ferdig integrasjon mot LIMS i denne leveransen.

IGV laster nødvendige deler av BAM eller CRAM og referansefiler når brukeren åpner en region. Dette er en separat dataflyt og gir ikke nye kliniske annoteringer. Genlisten som brukes for Biomarker er en lokal liste fra september 2026.

### Viktige arkitekturvalg

Kildegrunnlaget og vurderingen er skilt. En brukerendring av en kildeverdi registreres som en begrunnet korreksjon, mens den importerte verdien beholdes. HTML og PDF bygger på de samme validerte kontraktene. Dette gjør det mulig å følge hvilke opplysninger som kom fra analysen, og hvilke som ble lagt til under faglig vurdering.

## 3 Hvilke filer gjør hva

Alle stier i tabellen er relative til den prosjektmappen som inneholder manage.py. Rediger kildefilene og generer rapporten på nytt; en ferdig HTML-fil er et resultat, ikke riktig sted for varige kodeendringer.

| Fil eller mappe | Rolle ved vedlikehold |
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

### Filene adapteren forventer

En kilderot inneholder InPreD_PRONTO_metadata.txt og nøyaktig én fil som matcher *_variant_summary.tsv. Under mappen med aktuell sample_id skal sample_list.tsv og én småvarianttabell finnes. Adapteren foretrekker *_small_variant_table_forQC.tsv; hvis ingen finnes, brukes *_small_variant_table.tsv. Flere treff gir feil fremfor et tilfeldig filvalg.

Metadatafilen må inneholde aktuell Sample_id. Sequencing_run_id og Study_id brukes som obligatoriske identitetsopplysninger. Sammendraget må ha den aktuelle prøven, med støtte for prøvens _P-suffiks. Manglende kildefiler, manglende identitet eller manglende sammendragsrad avbryter importen.

| Kildetype | Hva den brukes til |
| Metadata TSV | Prøve, run, pasientpseudonym og tilgjengelig klinisk diagnose. |
| Variant summary TSV | TMB og MSI med rå kildeverdi og kildeposisjon. |
| Small variant table TSV | Gen, koordinat, alleler, transkript, proteinendring, frekvens, dybde og annoteringer. |
| Sample list TSV | Deklarert prøveliste i importgrunnlaget og kildespor. Full klinisk prøvekobling må kvalitetssikres i importløpet. |
| CNV overview PDF | Deklarert CNV-plott for aktuell prøve. |
| Sample QC PNG | Deklarerte QC-bilder i prøvemappen. |
| CNV og RNA tabeller | Kan representeres som sourceTables i ReportData v2. Ordinær, pasientkoblet import må settes opp eksplisitt. |

### Beregning og visning

Webadapteren leser TMB og MSI fra sammendraget. Den gjennomfører ikke en ny TMB-beregning og finner ikke selv en behandlingsindikasjon. Den eldre PRONTO-flyten har egne beregninger og filtreringsregler. Ved regelendringer må man derfor først avklare hvilket løp som faktisk produserte kildeverdien.

DisplayRange er en visningsskala, for eksempel [0-100+]. Den er ikke en klinisk grenseverdi. Manglende verdier skal fremstå som utilgjengelige. I det godkjente OUS-testgrunnlaget er TMB 14,9 og MSI 4,13, og alle 30 kildeforekomstene av småvarianter bevares. Dette er testkontroller, ikke referanseverdier for andre prøver.

Kildetabell-leseren støtter XLSX, TSV, TXT og semikolonseparert CSV. Den har grenser på 25 MiB filstørrelse, 10 000 datarader og 500 kolonner. XLSX har i tillegg grense for utpakket størrelse. Flere ark krever eksplisitt arkvalg. Gul kildefarge kan registreres som sourceApproved, men setter ikke automatisk brukerens rapportvalg.

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

Startvalg hentes fra Class_judgement, CPSR_ClinVar_class og IGV_QC når de er entydige og støttet. Lagrede manuelle valg beholdes. Et treff i genes-september-2026.json betyr genmedlemskap og velger hverken Include eller Highlight.

## 6 Databasen og hva som lagres hvor

Lokal oppstart bruker SQLite. Den aktive filen velges i .local-web/config.json; standard er .local-web/pronto.sqlite3. Grunninnstillingene har også et annet standardnavn, pronto_web.sqlite3. Det er derfor avgjørende å lese faktisk konfigurasjon før backup, migrering eller flytting. Ikke velg database ut fra navnet på den første SQLite-filen i prosjektmappen.

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
| Django auth og session | Brukere, passordhasher, grupper, tillatelser og innloggingssesjoner. |

Databasen inneholder ikke bare et register over filstier. Den inneholder selve rapportgrunnlaget, vurderingene, rapportbildene og presentasjonsfigurene. BAM eller CRAM, referansegenomer, lokale kildefiler og ferdige PDF eller HTML-nedlastinger kan ligge utenfor databasen og må håndteres separat.

Migreringene ligger i pronto_web/reports/migrations/. Historikken har to 0002-grener som samles i 0003. Den inneholder også 0010 for arbeidskladder. Bruk migrate; ikke slett migreringsfiler eller endre tabellene manuelt. Audit er beskyttet av applikasjonsrutiner og databaseforhold, men er ikke et kryptografisk, manipulasjonssikkert register mot en databaseadministrator.

## 7 Installasjon og lokal oppstart

### Ny installasjon på Windows

Bruk Python 3.14 som prosjektet og CI er satt opp for. Installer Poppler slik at pdfinfo og pdftoppm finnes i PATH. Poppler brukes når kildeplott i PDF skal vises i HTML. PDF-rapportene som PRONTO selv produserer, bruker ReportLab.

Åpne PowerShell i den utpakkede PRONTO-mappen:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\start_web.py --setup-user ditt-brukernavn
```

Oppgi et nytt passord i terminalen. Passordreglene krever minst 12 tegn og avviser blant annet vanlige passord og rent numeriske passord. Åpne http://127.0.0.1:8770/reports/ og logg inn. Kontoen er en vanlig bruker, ikke administrator. Den får ReportGrant til rapportene som finnes når kontoen opprettes; nye rapporter må tildeles eksplisitt.

### Senere oppstart

```powershell
.\.venv\Scripts\python.exe scripts\start_web.py
```

Oppstarten gjenbruker nøkkel, database og port. Den oppretter ikke nye prøver og nullstiller ikke vurderinger. Hold terminalen åpen; Ctrl+C stopper serveren. En tom database gir en tom rapportoversikt. Første oppstart importerer ikke automatisk tidligere analysefiler.

### Eksisterende database og kontroll

```powershell
.\.venv\Scripts\python.exe scripts\start_web.py --database 'C:\PRONTO-data\pronto.sqlite3' --check
.\.venv\Scripts\python.exe scripts\start_web.py --port 8771
```

--database må vise til en eksisterende fil. --check kjører kontroll og nødvendige migreringer uten å starte serveren; den er derfor ikke en rent lesende databasekontroll. Ta backup først. Valgt port og database huskes i config.json. Ikke slett .local-web for å løse et oppstartsproblem.

På Linux brukes python3.14 -m venv .venv og .venv/bin/python i de tilsvarende kommandoene. Lokal oppstart binder bare til 127.0.0.1. Oppsett for en ekstern server er beskrevet i kapittel 15. requirements-browser.txt trengs for nettlesertester, ikke vanlig rapportbruk.

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

## 10 Nye rapporter og innhenting av data

### Tilgjengelig import og dagens grense

adapt_pronto_output kan bygge et validert rapportgrunnlag fra en eksplisitt kilderot og prøveidentifikator. CLI-kommandoen export er derimot avgrenset til det godkjente OUS-testgrunnlaget. Den er en reproduserbar testinngang, ikke en generell produksjonsimportør for vilkårlige prøver.

Det finnes ingen ferdig brukerknapp for ordinær pasientimport, ingen automatisk mappeovervåking og ingen komplett, automatisk pasientkoblet CNV og RNA-import. Innføring av nye kliniske datastrømmer må derfor eies av en utvikler og valideres mot aktuelle filer. Dette er et konkret innføringspunkt ved videre overtakelse.

### Reproduserbart testgrunnlag og HTML

Fra prosjektroten kan utvikleren lage rapportgrunnlag og en skrivebeskyttet HTML-arbeidsflate uten å bruke den private databasen:

```powershell
.\.venv\Scripts\python.exe -m pronto_report.cli export --fixture ous --output Out\handover-report.json
.\.venv\Scripts\python.exe -m pronto_report.cli render-html Out\handover-report.json --asset-root test_data\ous\251114_A02134_0115_BHCJCKDRX7_TSO_500_LocalApp_postprocessing_results --output Out\handover-report.html
```

Den lange asset-root-stien er én sammenhengende sti. --review kan brukes med en tilhørende validert ReviewState JSON. Bruk --generated-at med en fast UTC-tid hvis byteidentisk gjengenerering av JSON er nødvendig. Uten dette varierer genereringstiden.

### Slik må en kontrollert databaseimport bygges

1. Velg kilderot, sample_id, genereringstid og generatorversjon eksplisitt. Kontroller prøve, run og referansebygg mot laboratoriets prøveoversikt.
2. Kjør adapt_pronto_output. Avklar diagnostikk og manglende data før rapporten tas i bruk. Valider alle vedlegg med load_plot_images og de deklarerte hashene.
3. Opprett en ny ReportRecord med serialize_report_data. Avvis ID-kollisjon; ikke oppdater en allerede vurdert rapport med nye rådata under samme ID.
4. Opprett en gyldig innledende DRAFT ReviewRevision med riktig reportId, revision, reviewer, tidsstempler, tomme vurderinger, QC, notes og korreksjoner. Oppgrader til gjeldende kontrakt med upgrade_review ved behov.
5. Opprett ett ReportAsset per deklarert vedlegg og eksplisitte ReportGrant til aktuelle brukere. Utfør databaseinnleggingen samlet i transaction.atomic().
6. Åpne rapporten som riktig bruker, lagre en vurdering og kontroller begge PDF-formatene og historikk. En ReportRecord uten innledende vurdering har ikke et komplett redigeringsløp.

Dette importmønsteret er gjennomkjørt på godkjent testgrunnlag i en separat database ved overleveringen. Det gir ikke automatisk validering av andre laboratorieformater. enrich_demo_report er en eksplisitt demonstrasjonsfunksjon med blandede eksempelprøver og syntetisk HRD. Den skal ikke brukes som klinisk pasientimport.

## 11 HTML PDF og rapportmaler

### Arbeidsflate og frittstående HTML

renderers/html.py bygger den interaktive arbeidsflaten av HTML-deler, CSS, JavaScript og validerte data. projection.py og review_v3 eller review_v4 forbereder visningsinnholdet. Brukerhandlinger sendes til Django gjennom report.js og working-draft.js. Det er ingen separat Node eller React-bygging som må kjøres for vanlig oppstart.

CLI render-html lager en frittstående, skrivebeskyttet rapportflate med innebygde data og støttede plott. HTML-nedlastingsendepunktet lager i stedet et redusert rapportsammendrag gjennom summary_html.py. Dette er to ulike leveranseformater. En eksportert HTML-fil har ikke serverens konto og tilgangskontroll rundt seg; oppbevar den i et godkjent område.

HTML-eksportendepunktet er en kompatibilitetsflyt med deklarerte initialer og lagret ReviewRevision. Det fryser ikke automatisk en aktiv WorkingDraft slik PDF-endepunktet gjør. Ved bruk av dette API-et må klienten velge en faktisk bevart revisjon. Oppgi ikke en uspart kladderevisjon og forvent at den eksporteres.

Ved overleveringen ble summary_html.py rettet slik at gjeldende ReviewState v4 kan eksporteres. Tidligere ble den avvist selv om den var gyldig og ferdigstilt. Regresjonstesten kontrollerer blant annet lagret tekst, escaping, manuell CNV og eksportspor.

### De to PDF-formatene

Presentation er liggende A4 med pasientfelt, Key relevant findings og kompakte funntabeller. ESMO er stående A4 med sammendrag, resultater og kliniske tekstseksjoner. Malnavnet ESMO beskriver rapportoppsettet og er ikke dokumentasjon på ekstern godkjenning. Lange tabeller og tekster fortsetter på flere sider.

project_report_export i report_pdf.py samler inkluderte småvarianter, CNV og RNA, korreksjoner, QC og notater. Ekskludering overstyrer Highlight. Dublette småvariantforekomster slås sammen ved presentasjon. Kontroller PDF visuelt ved endringer i kolonner, lange tekster eller skriftstørrelser; en bestått JSON-test beviser ikke at en side er lesbar.

PNG, JPEG og WebP som lastes opp som presentasjonsfigurer, dekodes og lagres på nytt som PNG. Maksimalt 8 MB og 64 millioner kildepiksler tillates per opplasting; lagret størrelse skaleres til høyst 16 millioner piksler. Inntil 30 figurer kan velges. Privat per rapport-grense er 64 MB og 100 figurer. Utvalgte figurer kommer på slutten av Presentation PDF, med lagret rekkefølge og bildetekst.

## 12 IGV og genomfiler

### Tre forskjellige bruksmåter

Lokal visning åpner BAM og tilhørende BAI eller CSI fra brukerens maskin i nettleseren. Valg av lokale filer laster ikke BAM-filen opp til serveren. Et regionutdrag inneholder bare de lesningene som faktisk finnes i utdraget. Tom visning utenfor dette området betyr ikke at hele originalprøven mangler lesninger.

Registrerte kilder hentes fra et eksplisitt manifest som kobler reportId, sampleId, referenceBuild, rolle og et konkret data og indekspar. PRONTO leter ikke tilfeldig etter et filnavn. Begge PRONTO_ALIGNMENT_SOURCE_ROOT og PRONTO_ALIGNMENT_REGISTRY_JSON må være satt. Filene skal ligge under den private kilderoten.

Permanent bevaring er et eget løp med eksplisitt bekreftelse, rettigheter, størrelsesgrenser, privat staging og privat lager. Denne funksjonen er avslått uten full konfigurasjon. Native Windows er begrenset til visning; bevaring krever Linux eller et tilsvarende validert Linux-miljø med pysam.

### Referansegenomer

Lokal oppstart oppdager komplette filpar i .local-web/references/: GRCh37.fa med GRCh37.fa.fai, og GRCh38.fa med GRCh38.fa.fai. Start appen på nytt etter at filpar legges til. Appen laster ikke referansefiler ned automatisk. I den kontrollerte lokale installasjonen finnes begge parene; innholdets biologiske korrekthet må forvaltes av laboratoriet.

Rapport, BAM eller CRAM og referanse må bruke samme bygg. Innloggede referanseruter støtter nødvendige byteområder. FASTA-innhold krever ett gyldig byteområde ved GET; FAI kan leses samlet opp til 8 MiB. igv.js versjon 3.7.0 følger prosjektet lokalt. Standard genomliste og offentlig CDN brukes ikke.

### Vilkår for permanent bevaring

Separate eksisterende kataloger for STORE_ROOT og STAGING_ROOT må ligge utenfor prosjekt og statisk eller offentlig lagring. Per fil, indeks, rapport og ledig plass må ha eksplisitte grenser. PRONTO_ALIGNMENT_POLICY_APPROVED=true er bare en teknisk bekreftelse på at institusjonen allerede har godkjent lagring, sletting, backup og tilgang. Brukeren må dessuten ha ReportWriteGrant.

Hele filparet valideres, hashes og publiseres først etter vellykket kopiering. Bare READY er synlig. DELETING skjuler et par mens sletting fullføres; en feil skal ikke gjøre det synlig igjen. Upload skjer i sammenhengende deler på høyst 8 MiB. Vanlig Save av rapportvurdering lagrer ingen BAM.

## 13 Konfigurasjon og HTTP grensesnitt

### Viktige innstillinger

| Innstilling | Betydning |
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

Ta backup av den aktive databasen, .local-web/config.json og secret.key gjennom et beskyttet internt område. Ta separat vare på referansegenomer og indekser, analysegrunnlag, eventuelt alignment-register, bevarte filpar, rapporteksporter og driftens settings. Installer .venv på nytt fra requirements fremfor å kopiere miljøet til en annen maskin.

Bruk SQLite backup API for en konsistent kopi når databasen er åpen. En tilfeldig filkopi mens noen skriver kan mangle transaksjoner eller kreve WAL-filer. Ved en helt stoppet tjeneste kan en kontrollert filkopi brukes. Stopp også eventuelle opplastinger hvis backup skal samordnes med et privat alignment-lager.

### Eksempel med SQLite backup API

Kjør følgende som et eget Python-skript i et beskyttet område. Bytt stiene til de avtalte filene. Målet skal være en ny fil; bruk ikke den aktive databasen som mål.

```python
from pathlib import Path
import sqlite3

source = Path(r'C:\PRONTO-data\pronto.sqlite3').resolve()
target = Path(r'C:\PRONTO-backup\pronto-2026-10-23.sqlite3')
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
4. Start launcheren med --database som peker til den nye kopien. Dette lagrer riktig absolutt sti og unngår at gammel config peker tilbake til den gamle maskinen. Kjør --check etter backup.
5. Kontroller innlogging, tilgang, rapportantall, siste FINAL, aktiv kladd, rapportbilder, figurer og begge PDF-formatene. Kontroller IGV separat.
6. Avtal når den nye installasjonen blir skrivende hovedinstallasjon. Hold den gamle avslått for å hindre to divergerende databaser.

Ved en mislykket oppgradering gjenopprettes både tidligere kode og den tilhørende databasebackupen. Ikke forsøk en tilfeldig baklengs migrering. Backupfrekvens, oppbevaringstid og akseptabelt datatap må fastsettes av driften. Save-hendelsene gir ikke full gjenoppretting av overskrevne arbeidskladder.

## 15 Tilgang og forutsetninger for serverdrift

### Kontoer og rapporttilgang

Bruk personlige kontoer i ordinær drift. Nye rapporter krever eksplisitt ReportGrant. Kontoopprettelse i launcheren gir tilgang til alle rapporter som finnes på opprettelsestidspunktet; vurder derfor om dette passer den lokale arbeidsdelingen før kontoen opprettes. Det finnes ikke et ferdig administratorgrensesnitt for all rapporttildeling.

En teknisk forvalter kan bruke Django shell med korrekt database og settings. get_or_create på ReportGrant kan gi tilgang til en bestemt eksisterende rapport og bruker; sletting av den samme koblingen trekker tilgangen tilbake. Ikke gi ReportWriteGrant som standard. Den gjelder genomfilbevaring, ikke det vanlige rapportarbeidet. For å sperre en konto settes is_active til false.

### Lokalt produkt og delt tjeneste

start_web.py bruker Djangos utviklingsserver og er laget for lokal bruk på 127.0.0.1. Å endre adressen til 0.0.0.0 er ikke en ferdig produksjonsinstallasjon. Delt drift trenger en valgt produksjonsserver, HTTPS, vertsliste, riktig proxy-oppsett, sikker nøkkelforvaltning, statiske filer, logger, backup, overvåking og en test av samtidige brukere.

Grunninnstillingene mangler HTTPS-redirect og HSTS. check --deploy varsler om dette. Et eget produksjonsoppsett må håndtere HTTPS på riktig sted og kontrollere proxy-innstillingene. Ikke aktiver HSTS ukritisk før domenets HTTPS-drift er verifisert. SQLite støtter ikke Djangos select_for_update; flerkontobruk og eventuelt annet databasevalg må derfor vurderes og testes i det faktiske driftsmiljøet.

### Drift som må etableres utenfor applikasjonen

Overvåk oppstart, feil ved lagring og eksport, ledig disk, backupalder og databaselåser. Ved alignment-bevaring må også opplastinger og DELETING-poster følges opp. Det finnes ikke ferdig sentral varsling eller en etablert vaktordning i denne leveransen. Logger kan inneholde intern driftsinformasjon og skal ikke legges i Git.

Demo-kommandoene run_demo, resume_demo og seed_demo_patients er for isolerte demonstrasjonsdatabaser. De kan aktivere demoidentitet og bruker egenregistrerte initialer. De er ikke ordinær innlogging for klinisk drift. .local-web skal heller ikke sendes som en åpen del av dokumentpakken, selv om installasjonen inneholder testprøver.

## 16 Vedlikehold og feilsøking

### Oppgradering

Ta en konsistent backup og noter nåværende kodeversjon før endring. Installer nye requirements i et isolert miljø. Kontroller makemigrations --check --dry-run, kjør de nødvendige migreringene på en testkopi og gjennomfør relevante tester. Kontroller lange rapporter visuelt i begge PDF-formatene. Planlegg en tilbakeføring av både kode og database før produksjonskopien endres.

### Vanlige problemer

| Symptom | Første kontroll og tiltak |
| Ingen rapporter i oversikten | Kontroller valgt database i config.json og ReportGrant. En ny installasjon er tom til data importeres. |
| Innlogging virker ikke | Kontroller konto, passord, is_active, korrekt port og korrekt local_settings ved lokal HTTP. |
| Porten er opptatt | Stopp den aktuelle serveren eller bruk --port 8771. Ikke avslutt andre prosesser uten å identifisere dem. |
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

## 17 Kontrollresultater ved overlevering

Kontrollene gjelder den identifiserte kildeversjonen og miljøet på denne Windows-maskinen. Automatiske tester bruker godkjente fixtures eller syntetisk grunnlag. De endrer ikke vurderingsinnholdet i den aktive databasen. En separat backup ble laget med SQLite backup API.

| Kontroll | Resultat |
| Python og avhengigheter | Python 3.14.0. pip check fant ingen brutte avhengighetskrav. Dette er ikke en CVE-revisjon. |
| pytest før rettelsen | 420 bestått og 18 utelatt. |
| Nettlesertester | 76 bestått i ekte headless Chromium gjennom Playwright. |
| Django før rettelsen | 107 tester kjørt, OK, én utelatt. |
| HTML regresjon | Reprodusert avvisning av gyldig v4, deretter bestått test for ferdigstilt v4 med manuell CNV og lagret tekst. |
| Sluttkjøring etter rettelsen | pytest: 420 bestått, 18 utelatt. Django: 108 kjørt, OK, én utelatt. Nettlesertestene inngår i pytest. |
| Systemkontroll | Ingen ordinære systemfeil. Ingen uregistrerte modellendringer. |
| Deploymentkontroll | To varsler med en egnet midlertidig nøkkel: HSTS og HTTPS-redirect mangler i grunnoppsettet. |
| Aktiv database | integrity_check er ok. Ingen brudd på fremmednøkler. |
| Datakontrakter | 31 rapporter og 85 vurderinger eller arbeidskladder validerte. |
| Rapportvedlegg | 45 vedlegg samsvarte med deklarerte SHA-256 og forventet vedleggssett. |
| Sikkerhetskopi | Separat backup kan åpnes og har samme tabellantall og gyldig integritet. |
| Gjennomkjøring i ny database | Import, CSRF-beskyttet Save, 409 ved foreldet Save, Finalize og historikk bestått. |
| Eksporter i gjennomkjøring | ESMO PDF med fire sider, Presentation PDF med én side og frittstående HTML bestått. Lagret tekst finnes i eksportene. |
| Tilgang i gjennomkjøring | Uinnlogget oversikt omdirigeres til innlogging. Bruker uten rapporttilgang får 404. |
| Lokale referansefiler | Begge forventede FASTA og FAI-par finnes for GRCh37 og GRCh38. |

17 Linux-avhengige tester for pysam og privat alignment-bevaring ble utelatt på native Windows. Én test av symbolske lenker ble utelatt fordi Windows ikke tillot opprettelse av lenker. Django-kjøringen utelot den samme lenketesten. Utelatt betyr ikke bestått.

Docker-klienten finnes, men Docker Linux-tjenesten var ikke tilgjengelig under kontrollen. Docker-bygg og hele OUS og HUS-fixtureflyten ble derfor ikke kjørt på nytt. Prosjektets Dockerfile pakker den eldre kommandolinjeflyten; den inneholder ikke en ferdig distribusjon av webappen. Det er heller ikke gjennomført ekstern produksjonsdrift, klinisk godkjenning, belastningstest eller en full sårbarhetsrevisjon av avhengighetene.

## 18 Sjekkliste for formell overtakelse

### Det som følger med

Kildekodepakken omfatter et fast programgrunnlag med HTML-rettelsen og tilhørende regresjonstest. Kontrollnotatet oppgir nøyaktig commit, filnavn, testresultater og eventuelle begrensninger. Denne manualen forklarer komponenter, dataflyt, kontrakter, database, oppstart, vurdering, eksport og drift. Den lokale databasen er ikke en del av kildekodepakken.

### Avklar og kvitter ved overtakelsen

| Punkt | Hvem kvitterer |
| Ny faglig og teknisk eier er navngitt. | Avgiver og mottaker |
| Riktig kodeversjon er installert fra arkivet eller tilsvarende Git-commit. | Teknisk forvalter |
| Eksisterende database eller bevisst tom installasjon er valgt. | Teknisk og faglig eier |
| Ny personlig konto og riktige rapporttilganger er kontrollert. | Driftsansvarlig |
| Backup, beskyttet lagringssted og gjenoppretting er overtatt. | Driftsansvarlig |
| Kildegrunnlag og referansegenomer er lokalisert og faglig verifisert. | Faglig eier |
| Rapporten er gjennomgått fra lagring til FINAL og begge PDF-formatene. | Mottaker |
| Import av nye kliniske prøver har en navngitt eier og validert rutine. | Teknisk og faglig eier |
| Omfanget lokal bruk eller delt serverdrift er besluttet. | Systemeier |
| Linux-bevaring av alignments forblir av eller er særskilt validert og godkjent. | Data og driftsansvarlig |
| Tidspunkt for å ta gammel skrivende installasjon ut av bruk er avtalt. | Avgiver og mottaker |

### Videre arbeid som ikke skal skjules

For ordinær klinisk innføring må mottakeren etablere en pasientkoblet import av de faktiske laboratoriefilene, validere alle beregninger og presentasjoner faglig og velge et godkjent driftsmiljø. Delt serverdrift trenger produksjonsserver og HTTPS. Eventuell BAM eller CRAM bevaring trenger Linux-kontroll, lagerpolicy og backup med filsystemet. Dette er innføringsansvar, ikke funksjoner som aktiveres av å overta Word-filen.

Ingen automatisk sammenslåing av samtidige kladder, journalsystemkobling, kontinuerlig ekstern annotering eller full historikk av hver Save inngår i den beskrevne flyten. Ved videreutvikling skal kontrakter, innhold og lagringsregler holdes konsistente mellom arbeidsflate, historikk, HTML og PDF.

## 19 Referanser og kommandoer for utvikleren

Følgende filer i leveransen er de konkrete tekniske referansene. De eldre arkitekturskissene utenfor den aktive prosjektmappen beskriver tidligere idéer og skal ikke behandles som en presis beskrivelse av dagens implementasjon.

| Referanse i prosjektet | Når den brukes |
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
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt -r requirements-browser.txt
.\.venv\Scripts\python.exe -m pytest -q -rs
$env:DJANGO_SETTINGS_MODULE='pronto_web.test_settings'
.\.venv\Scripts\python.exe manage.py test pronto_web.reports
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

test_settings bruker isolerte testinnstillinger og en offentlig testnøkkel. Ikke bruk dette settings-modulet for å starte en ordinær tjeneste. Nettlesertestene finner lokal Chrome eller Edge på støttede Windows-stier; PRONTO_BROWSER_EXECUTABLE kan angi en eksplisitt binær. Browser-testene bruker syntetisk innhold og lokale testservere.

### Versjon og filplassering i den opprinnelige installasjonen

Den samlede løsningen som ble kontrollert, ligger under repos/PRONTO/.worktrees/igv-django-integration i Inpred-arbeidsområdet. Roten repos/PRONTO er en eldre arbeidskopi. Mappenavnet er beholdt ved feilrettingen, selv om Git-branchen kan ha fått et nytt navn. Et navn på en worktree er ikke bevis på hvilken kodeversjon den inneholder; kontroller commit i kontrollnotatet.

Den beskyttede databasebackupen ligger under .local-web/backups i den aktive arbeidskopien. Den konkrete backupfilen er registrert i det lokale kontrollgrunnlaget. Ved overtakelse flyttes denne og den private konfigurasjonen separat, slik kapittel 14 beskriver.
