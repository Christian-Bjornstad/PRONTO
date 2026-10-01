# PRONTO – gjennomgang med molekylærbiolog

Dette er en lokal demonstrasjon med de godkjente OUS-demodataene. Bruk den til
å vurdere arbeidsflyt, innhold og likhet med originalen `report.html` – ikke til
kliniske beslutninger. Ingen nye kliniske tolkninger er lagt inn.

## Åpne eller starte demoen

Start en separat demo som vist nedenfor; den åpne `demo-fidelity-20260929`
skal ikke nullstilles eller overskrives. Ingen innlogging kreves i den
lokale demoen. Initialer er selvoppgitte, ikke bekreftet identitet.

Bruk vanlig Chrome eller Edge ved ferdigstilling. Under kontrollen hang den
innebygde nettleseren i Codex ved nettleserens bekreftelsesdialog; hele flyten
er i stedet kontrollert i Chrome mot en isolert Django-testdatabase.

For en **ny, tom gjennomgang** (anbefalt rapport-ID: `demo-reset-html-20260929`): åpne PowerShell i prosjektets worktree med
prosjektets Python-avhengigheter installert, og kjør:

```powershell
$demoStamp = Get-Date -Format yyyyMMdd-HHmmss
$env:PRONTO_DJANGO_SECRET_KEY = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
python manage.py run_demo --database "reset-html-$demoStamp.demo.sqlite3" --report demo-reset-html-20260929 --port 8776
```

Åpne `http://127.0.0.1:8776/reports/demo-reset-html-20260929/` og la terminalen stå åpen. Hvis porten er opptatt, bruk en annen ledig port og åpne
tilsvarende adresse. Serveren binder bare til denne maskinen (127.0.0.1).
Ikke eksponer den via proxy eller nettverk.

Hver oppstart med `run_demo` krever et nytt databasenavn og lager en ny
gjennomgang. Tidligere vurderinger blir liggende i sine egne databasefiler.
For å fortsette en lagret demo etter at serveren er stoppet, bruk samme fil og
rapport-ID med `resume_demo`:

```powershell
$env:PRONTO_DJANGO_SECRET_KEY = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
python manage.py resume_demo --database "reset-html-<dato>.demo.sqlite3" --report demo-reset-html-20260929 --port 8776
```

`resume_demo` importerer ikke kildedata på nytt og sletter ikke revisjoner. Den
nekter en manglende/feil database, andre rapporter eller brukere og utvidet
alignment-tilgang. Stopp den gamle serverprosessen før samme port brukes igjen.

## Foreslått gjennomgang (15–20 minutter)

1. **Se informasjonen først.** Start i **Variant review**. Sammenlign med
   originalen: søk, filter, AF med tre desimaler og dybde tumor DNA. Åpne
   **Details** for kildeannotasjoner, tier og identifikatorer.
2. **Velg funn.** Bruk knappen for å ta et funn med i rapporten. Klassifikasjon,
   IGV-vurdering og kommentar er egne felt. Duplikate kildeforekomster deler
   vurdering; forhåndsvisningen teller unike valgte varianter. Filtrering
   endrer ikke utvalget.
3. **Vurder QC.** Under **Sequencing QC**, prøv vurderingsstatus og kommentar.
   Manglende målinger er merket, ikke fylt inn med antatte verdier.
4. **Forhåndsvis rapporten.** Kontroller valgte funn, skriv et tydelig merket
   demonstrasjonsnotat og prøv de tre notatfeltene. Forhåndsvisning verken
   lagrer eller ferdigstiller.
5. **Lagre.** Trykk **Save** og skriv egne initialer (2–8 bokstaver). Vent på
   «All changes saved». Kontroller initialer og revisjon i **Sign-off**.
   Last siden på nytt og bekreft at utvalg, notater og QC-vurdering består.
6. **Prøv Reset på en testgjennomgang.** Bekreft advarselen og skriv initialer.
   Utvalg, QC-vurdering, notater og TMB-korreksjon går tilbake til utgangspunktet.
   Kildedata, gamle revisjoner og handlingsloggen blir værende i databasen.
   Velg så funn og lagre på nytt før neste steg.
7. **Last ned selvstendig HTML.** Klikk **Download report HTML**, oppgi
   initialer og åpne den nedlastede `.html`-filen uten nettforbindelse. Sjekk
   Key findings, bare valgte varianter, konklusjonsnotater, revisjon og initialer.
   Nettleserens utskriftsforhåndsvisning skal fungere. Databasen loggfører
   `HTML_DOWNLOAD_REQUESTED`, ikke at filen faktisk ble åpnet eller skrevet ut.
8. **Ferdigstill til slutt.** Bruk en rapport dere er ferdige med å teste.
   Lagre først, trykk **Finalize** og bekreft med initialer. Samme biolog kan
   lagre og ferdigstille. Rapporten låses; det er ingen angreknapp tilbake
   til utkast. Kontroller signering og HTML-nedlasting igjen.

Ved lagringsfeil: ikke lukk siden. Sikre lokale endringer med den tilbudte
JSON-nedlastingen før dere laster nyeste revisjon. JSON er en arbeidskopi,
ikke bevis på database-lagring; automatisk import/gjenoppretting er ikke
implementert. Se [lagringsfeil og gjenoppretting](report-review-workspace.md#recovery-after-an-unsuccessful-save).

## Bevisste avgrensninger i demoen

- **OncoKB:** «Ikke mottatt». Kolonnen er klar for informasjon fra pipelinen;
  det gjøres ikke API-oppslag eller kliniske antakelser.
- **Egen biomarkørliste:** «Ikke krysssjekket». Dette betyr ikke «ingen treff».
  Liste, matching og leveranse fra pipelinen må avklares.
- **Datagrunnlag:** adapteren viser 30 kildeforekomster / 29 unike varianter.
  Originalen viser 24 / 23 fra en annen arbeidstabell. Avklar ønsket
  kilde/utvalgsregel; ekstra varianter skal ikke skjules på gjetning.
- **IGV:** reelle BAM/CRAM-filer og referanseoppsett er en egen verifikasjon.
  Den lokale demobrukeren har ikke tilgang til serverlagrede alignments.
  Lokalt filvalg er ikke automatisk opplasting eller lagring.
- **Skrivebeskyttet HTML:** lokal utskrift har ingen ny sentral loggføring.
  Utskrift via nettlesermeny og skjermbilder kan heller ikke garanteres logget.
- **Produksjon:** tilgangskontroll, sikkerhetskopiering, oppbevaring,
  driftsoppsett og klinisk validering må godkjennes separat.

## Sjekkliste og tilbakemeldinger tirsdag

- [ ] Tabellen er oversiktlig og nødvendige kildedata er enkle å finne.
- [ ] Avklart hvilken variantkilde og hvilket utvalg som skal brukes.
- [ ] Utvalg til sluttrapport er tydelig og duplikater forståelige.
- [ ] QC, notatfelter og begreper dekker biologens arbeidsflyt.
- [ ] Lagre → last på nytt bevarer alle vurderinger.
- [ ] Initialer vises riktig ved lagring, Reset, ferdigstilling og HTML-nedlasting.
- [ ] Nedlastet HTML har ønsket innhold og lesbar utskriftslayout sammenlignet med originalen.
- [ ] Ønsket OncoKB-format og egen biomarkørliste er notert.
- [ ] Gjenstående avvik prioriteres: må ha / ønskelig / senere.

Noter for hvert avvik: fane, handling, forventet resultat og faktisk resultat.
Ikke ta med pasientopplysninger i skjermbilder som skal deles i GitHub.
