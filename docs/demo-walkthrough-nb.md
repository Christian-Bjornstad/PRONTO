# PRONTO – gjennomgang med molekylærbiolog

Dette er en lokal demonstrasjon med de godkjente OUS-demodataene. Bruk den til
å vurdere arbeidsflyt, innhold og likhet med originalen `report.html` – ikke til
kliniske beslutninger. Ingen nye kliniske tolkninger er lagt inn.

## Åpne eller starte demoen

Den klargjorte demoen ligger på
[rapporten på port 8772](http://127.0.0.1:8772/reports/demo-tuesday/), så lenge
serverprosessen kjører på denne maskinen. Ingen innlogging kreves i denne
lokale demoen. Initialer er selvoppgitte, ikke bekreftet identitet.

Bruk vanlig Chrome eller Edge ved ferdigstilling. Under kontrollen hang den
innebygde nettleseren i Codex ved nettleserens bekreftelsesdialog; hele flyten
er i stedet kontrollert i Chrome mot en isolert Django-testdatabase.

For en **ny, tom gjennomgang**: åpne PowerShell i prosjektets worktree med
prosjektets Python-avhengigheter installert, og kjør:

```powershell
$demoStamp = Get-Date -Format yyyyMMdd-HHmmss
$env:PRONTO_DJANGO_SECRET_KEY = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
python manage.py run_demo --database "tuesday-$demoStamp.demo.sqlite3" --report demo-tuesday --port 8772
```

La terminalen stå åpen. Hvis porten er opptatt, bruk for eksempel 8773 og åpne
tilsvarende adresse. Serveren binder bare til denne maskinen (127.0.0.1).
Ikke eksponer den via proxy eller nettverk.

Hver oppstart med `run_demo` krever et nytt databasenavn og lager en ny
gjennomgang. Kommandoen nekter å overskrive eller gjenåpne eksisterende
databaser. Tidligere vurderinger blir liggende i sine egne databasefiler;
de er **ikke** med i en ny demo. Gjenåpning av en lagret demodatabase krever
separat oppsett – ikke slett databasen for å omgå kontrollen.

## Foreslått gjennomgang (15–20 minutter)

1. **Se informasjonen først.** Start i Variantgjennomgang. Sammenlign med
   originalen: søk, filter, AF med tre desimaler og dybde tumor DNA. Åpne
   Detaljer for kildeannotasjoner, tier og identifikatorer.
2. **Velg funn.** Bruk knappen for å ta et funn med i rapporten. Klassifikasjon,
   IGV-vurdering og kommentar er egne felt. Duplikate kildeforekomster deler
   vurdering; forhåndsvisningen teller unike valgte varianter. Filtrering
   endrer ikke utvalget.
3. **Vurder QC.** Under Sekvenserings-QC, prøv vurderingsstatus og kommentar.
   Manglende målinger er merket, ikke fylt inn med antatte verdier.
4. **Forhåndsvis rapporten.** Kontroller valgte funn, skriv et tydelig merket
   demonstrasjonsnotat og prøv de tre notatfeltene. Forhåndsvisning verken
   lagrer eller ferdigstiller.
5. **Lagre.** Trykk Lagre og skriv egne initialer (2–8 bokstaver). Vent på
   «Alle endringer lagret». Kontroller initialer og revisjon i Signering.
   Last siden på nytt og bekreft at utvalg, notater og QC-vurdering består.
6. **Test utskrift.** Generer MDT-utskrift og oppgi initialer. Kontroller
   PDF/utskriftsvisningen: bare valgte funn, riktige kommentarer og tydelig
   utkaststatus. Loggen registrerer utskriftsforespørselen, ikke at papir
   faktisk ble skrevet ut eller at PDF ble lagret.
7. **Ferdigstill til slutt.** Bruk en rapport dere er ferdige med å teste.
   Lagre først, trykk Ferdigstill og bekreft med initialer. Samme biolog kan
   lagre og ferdigstille. Rapporten låses; det er ingen angreknapp tilbake
   til utkast. Kontroller signering og utskrift igjen.

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
- [ ] Initialer vises riktig ved lagring, ferdigstilling og utskrift.
- [ ] PDF har ønsket innhold og lesbar layout sammenlignet med originalen.
- [ ] Ønsket OncoKB-format og egen biomarkørliste er notert.
- [ ] Gjenstående avvik prioriteres: må ha / ønskelig / senere.

Noter for hvert avvik: fane, handling, forventet resultat og faktisk resultat.
Ikke ta med pasientopplysninger i skjermbilder som skal deles i GitHub.
