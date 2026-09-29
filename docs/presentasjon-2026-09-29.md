# PRONTO: manus for demonstrasjon på denne PC-en

## Start her

Åpne **[den klargjorte rapporten](http://127.0.0.1:8772/reports/demo-presentation-20260929/)**
i Chrome eller Edge. Den er en ny, lokal gjennomgang med godkjente demodata.
Per 29. september før demonstrasjonen har databasen én utkast-revisjon og
ingen lagrings- eller utskriftslogg. Ikke åpne de eldre demo-adressene til
presentasjonen: de har andre databasefiler og kan inneholde tidligere tester.

Ha gjerne to vinduer ved siden av hverandre: rapporten og PowerShell for
databasekontrollen nedenfor. La serveren kjøre. Hvis adressen ikke svarer,
se «Hvis serveren har stoppet» nederst; **ikke** slett eller overskriv en
eksisterende databasefil.

**Viktig skille:** «Lagre» skriver en ny versjon av *gjennomgangen* til
SQLite-databasen. Kildedataene fra pipelinen endres ikke. Valg, klassifikasjon,
IGV-vurdering, kommentarer, QC-vurdering, notater og eventuelle begrunnede
kildekorreksjoner ligger i ReviewState. Initialer og handlingstid blir loggført.

## Kort introduksjon du kan si

> «Dette er den nye arbeidsflaten rundt rapporten vi likte. Først ser biologen
> alle tilgjengelige kildedata, deretter velger vedkommende hva som skal med
> i tumorboard-rapporten. Endringer ligger lokalt i nettleseren fram til vi
> trykker Lagre. Da får vi en ny revisjon i databasen. Vi kan laste siden på
> nytt og se at valgene fortsatt er der. Til slutt kan rapporten ferdigstilles
> og låses med initialer.»

Dette er en **demo**, ikke en klinisk godkjent produksjonsløsning.

## Klikk-for-klikk: anbefalt rekkefølge (ca. 20 minutter)

### 1. Vis utgangspunktet (2 minutter)

Start på **Variantgjennomgang**. Pek på status **Utkast** og «Alle endringer
lagret». Det betyr at ingen *nye* endringer venter lokalt; første tomme
revisjon er allerede i demo-databasen. Vis fanene Nøkkelfunn,
Variantgjennomgang, CNV-plott, Sekvenserings-QC og Molekylært tumorboard.

Si: «Rapporten viser 30 kildeforekomster, men 29 unike varianter. To TERT-rader
er samme variant i vurderingen. Originalens arbeidstabell hadde 24/23, så
datakilde og ønsket filtrering er noe vi må avklare – vi skjuler ikke rader
basert på gjetning.»

### 2. Se data før dere velger (3 minutter)

I **Nøkkelfunn**, vis kildebaserte TMB/MSI-verdier og at manglende informasjon
står som utilgjengelig. I **Variantgjennomgang**, søk for eksempel etter
`CHEK2`. Åpne **Detaljer** i raden. Pek på gen, endring, AF som andel med tre
desimaler, dybde tumor DNA og kildeannotasjon. AF `0,042` betyr andel, ikke
`0,042 %`.

Vis kolonnene **OncoKB: Ikke mottatt** og **Egen biomarkørliste: Ikke
krysssjekket**. Dette er plassholdere for framtidige pipeline-data, **ikke**
«ingen treff». Ikke presentér tier eller andre kildeannotasjoner som en
automatisk klinisk klassifikasjon.

### 3. Gjør en synlig endring (3 minutter)

På CHEK2, klikk **Ta med i rapport**. Skriv en tydelig ikke-klinisk kommentar,
for eksempel `DEMO: valgt for å vise arbeidsflyten`. La klassifikasjon og
IGV-vurdering stå «Ikke vurdert» hvis dere ikke faktisk vurderer dem. Pek på
at forhåndsvisningen nå teller **ett unikt valgt funn**. Søk eller filtrer på
et annet gen og gå tilbake: utvalget skal ikke forsvinne av filtrering.

Si: «Valget er foreløpig bare i nettleseren. Nå viser jeg at det først blir
varig når jeg trykker Lagre.»

### 4. Vis QC og rapportutkast (3 minutter)

I **Sekvenserings-QC** kan dere se de to kildeplottene. Strukturerte
QC-målinger mangler i dette datagrunnlaget; ikke vis dem som «godkjent».
Skriv eventuelt en demo-kommentar, for eksempel `DEMO: QC-kommentar`.

Klikk **Forhåndsvis rapport** eller fanen **Molekylært tumorboard**. Bare det
valgte funnet vises under «Funn til diskusjon». Skriv `DEMO: notat til
tumorboard` i **Interpretation summary**. De to andre notatfeltene kan vises
uten å fylles med oppdiktet klinisk innhold. Forhåndsvisning lagrer ikke.

### 5. Bevis lagring i databasen (4 minutter)

Før du klikker **Lagre**, kjør databasekommandoen under. Den skal vise
`Revisjon: 1`, `Valgte: 0`, `Initialer: None` og tom lagringslogg.

Klikk deretter **Lagre**, skriv demo-initialer som `DM` i dialogen og
**Bekreft**. Vent på «Alle endringer lagret». I signeringskortet skal du se
«Sist lagret av: DM» og «Lagret revisjon: 2».

Kjør **samme databasekommando** igjen. Nå skal nyeste revisjon være `2`,
`Valgte: 1`, og lagringsloggen skal ha `SAVE_DRAFT` med `DM`. Legg merke til
at revisjon 1 fortsatt finnes i databasen: lagring legger til historikk.
Last deretter rapporten på nytt (`Ctrl+R`) og vis at CHEK2-utvalget, notatet
og eventuell QC-kommentar består. Det er den beste, lett forståelige
demonstrasjonen av ekte lagring.

### 6. Vis utskrift (2 minutter)

Fra **Molekylært tumorboard**, trykk **Generer MDT-utskrift** og skriv
initialer. Kontroller at utskriftsvisningen inneholder valgt funn og notat,
ikke uvalgte varianter. I databasen kan du kjøre kommandoen igjen og se en
utskriftsforespørsel. Loggen betyr **forespurt utskrift**, ikke at papir eller
PDF faktisk ble produsert. Nettleserens vanlige utskriftsmeny og skjermbilder
kan ikke loggføres sentralt.

### 7. Ferdigstill bare hvis dere vil vise låsing (2 minutter)

Gjør dette **til slutt** på den egne demogjennomgangen. Sørg for at alle
endringer er lagret. Klikk **Ferdigstill**, bekreft låsing, og skriv initialer.
Den samme biologen kan lagre og ferdigstille. Vis status **Endelig**, initialer,
at notatfeltene er skrivebeskyttet, og at databasen nå har en ny `FINAL`
revisjon og logghandlingen `FINALIZE`. Dette kan ikke angres i grensesnittet.
Hvis dere vil fortsette å redigere under møtet, **ikke** ferdigstill; bruk et
nytt demodatasett senere.

## PowerShell: vis databasen uten å endre den

Åpne PowerShell i denne mappen:

```powershell
cd C:\Users\molpa\Documents\Inpred\repos\PRONTO\.worktrees\igv-django-integration
```

Kjør dette **før og etter** Lagre. `mode=ro` betyr skrivebeskyttet
databaseforbindelse:

```powershell
python -c "import sqlite3,json; c=sqlite3.connect('file:presentation-20260929.demo.sqlite3?mode=ro',uri=True); r=c.execute('select revision,review_data from reports_reviewrevision order by revision desc limit 1').fetchone(); d=json.loads(r[1]); print('Revisjon:',r[0], 'Status:',d['status'], 'Valgte:',sum(v['reportingDecision']=='INCLUDE' for v in d['variantReviews']), 'QC:',d['runQcAssessment']['status'], 'Initialer:',d.get('lastSavedAttribution')); print('Lagringslogg:',c.execute('select revision,action,declared_initials from reports_reviewaudit order by revision').fetchall()); print('Utskriftsforespørsler:',c.execute('select revision,declared_initials from reports_reportprintaudit order by requested_at').fetchall())"
```

Denne kommandoen viser **nyeste** revisjon og logghandlinger, men ikke selve
kommentarinnholdet på storskjerm. Du kan bruke sideoppfriskning for å bevise
at kommentaren er lagret uten å vise rå JSON.

## Hva du kan si om teknikken

`Pipelinefiler → validert ReportData → HTML-arbeidsflate → ReviewState →
SQLite-revisjon + handlingslogg → oppdatert rapport/utskrift`.

- **ReportData** er kildedata og proveniens. Valgene endrer ikke kilden.
- **ReviewState** er biologens egne vurderinger og tekst. Hver vellykkede
  lagring oppretter neste revisjon; en foreldet revisjon overskriver ikke
  nyere arbeid automatisk.
- **Initialer** oppgis ved lagring, ferdigstilling og utskriftsforespørsel.
  De er loggføring i demoen, **ikke** identitetskontroll. Lokal demo åpnes
  uten innlogging; produksjonstilgang må løses separat.
- **Ferdigstilling** skjer mot siste lagrede revisjon og låser rapporten.
- **IGV** er integrert som visning/filflyt, men denne demoen har ikke
  serverlagrede BAM/CRAM-alignments eller full klinisk IGV-verifikasjon.

## Ærlige svar på forventede spørsmål

- «Er OncoKB aktiv?» **Nei.** Kolonnen venter på verdier fra pipelinen.
- «Betyr ikke krysssjekket ingen biomarkørtreff?» **Nei.** Matching er ikke
  implementert; listen og leveranseformatet må avklares.
- «Hvorfor er det flere varianter enn i originalen?» Ulik kildetabell i
  adapteren. Vi må avtale korrekt kilde/filtrering med fagmiljøet.
- «Er initialer sikker identifikasjon?» **Nei.** De er selvoppgitt logg i
  lokal demo, ikke en produksjonsmodell for autentisering.
- «Kan rapporten gjenåpnes etter ferdigstilling?» Den kan leses og skrives
  ut, men ikke redigeres videre i denne arbeidsflyten.
- «Er dette klart for pasientbruk?» **Nei.** Klinisk validering, tilgang,
  drift, backup og databehandling må godkjennes separat.

## Hvis serveren har stoppet

`run_demo` kan **ikke** gjenåpne den eksisterende databasefilen; den krever
en ny fil hver gang. Start en **ny, tom** demo i PowerShell fra prosjektmappen:

```powershell
$demoStamp = Get-Date -Format yyyyMMdd-HHmmss
$env:PRONTO_DJANGO_SECRET_KEY = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
python manage.py run_demo --database "presentation-$demoStamp.demo.sqlite3" --report "demo-presentation-$demoStamp" --port 8772
```

Kommandoen skriver den nye adressen. Den nye demoen har **egen** database;
ikke bruk databasekommandoen over uten å bytte filnavn. Eldre filer blir
liggende urørt. Hold dette PowerShell-vinduet åpent gjennom møtet.

## Noter tilbakemeldinger

Be biologen prioritere: (1) manglende data/felt, (2) hva som må kunne
velges til sluttrapport, (3) QC- og signeringsordlyd, (4) PDF-layout, og
(5) hvilken variantkilde som skal være autoritativ. Noter fane, handling,
forventet og faktisk resultat. Ikke legg pasientopplysninger i GitHub.
