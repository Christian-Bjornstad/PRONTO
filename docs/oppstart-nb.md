# Starte PRONTO lokalt

Åpne PowerShell i prosjektmappen, der `manage.py` og `requirements.txt` ligger.
Har du allerede satt opp appen, kjører du:

```powershell
.\.venv\Scripts\python.exe scripts\start_web.py
```

Åpne <http://127.0.0.1:8770/reports/> og logg inn med kontoen din. La terminalen
stå åpen. Stopp serveren med **Ctrl+C**, og start igjen med samme kommando.

Oppstarten husker database og port i `.local-web/config.json` og gjenbruker
nøkkelen i `.local-web/secret.key`. Den lager ikke nye pasienter eller
nullstiller vurderinger. Standarddatabasen er `.local-web/pronto.sqlite3`.
Ikke slett `.local-web` for å starte serveren på nytt.

## Første oppstart

Installer Python 3.14 og PDF-verktøyene `pdfinfo` og `pdftoppm` (Poppler).
Poppler må ligge i PATH for å vise PDF-plottene. Fra prosjektmappen:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\start_web.py --setup-user ditt-brukernavn
```

Velg passord når terminalen spør. Dette lager en tom database og en vanlig
brukerkonto. Brukeren får tilgang til rapportene som finnes ved opprettelse,
uten administratorrettigheter eller rett til å lagre alignments. Nye rapporter
må få eksplisitte tilgangstildelinger.

For å velge en eksisterende database, erstatt eksempelstien med din egen:

```powershell
.\.venv\Scripts\python.exe scripts\start_web.py --database 'C:\data\pronto.sqlite3' --setup-user ditt-brukernavn
```

Utelat `--setup-user` når kontoen allerede finnes. Ta sikkerhetskopi før
oppgradering av en eksisterende database. Oppstarten kjører nødvendige
database-migreringer. **Change password** i pasientoversikten endrer passordet.
Bruk kontoen din ved senere oppstart; ikke legg brukernavn eller passord i Git.

## Port og kontroll av oppsett

Hvis port 8770 er opptatt, stopp den kjørende PRONTO-serveren eller velg en
annen port:

```powershell
.\.venv\Scripts\python.exe scripts\start_web.py --port 8771
```

Adressen blir <http://127.0.0.1:8771/reports/>. Porten huskes ved senere oppstart.
For å kontrollere oppsett og kjøre migreringer uten å starte serveren:

```powershell
.\.venv\Scripts\python.exe scripts\start_web.py --check
```

## Vurdering, lagring og historikk

Handlinger registreres på kontoen som er logget inn. Du trenger ikke oppgi
initialer. Tidligere registreringer beholder sin opprinnelige identitet.

- **Edit mode** åpner redigering. Endringer lagres først når du trykker **Save**.
- **Save** overskriver den aktive arbeidskladden. Hver lagring lager ikke en
  ekstra rapportversjon.
- **Finalize** bevarer en signert revisjon og avslutter arbeidskladden.
- **Start new revision** kopierer en valgt DRAFT eller FINAL til en ny kladd.
  En FINAL beholdes i historikken. Du må bekrefte dersom en aktiv kladd erstattes.
- PDF-eksport bevarer den lagrede rapporten som ble eksportert. Videre arbeid
  kan derfor få et nytt revisjonsnummer.

En foreldet nettleser kan ikke overskrive nyere arbeid. Ved konflikt: behold
den lokale kopien før du laster nyeste versjon. Se
[arbeidsflaten og lagringsfeil](report-review-workspace.md).

Variant review, CNV og RNA har Inc/Exc og Report highlight. Bare inkluderte
funn kommer med videre; highlight angir **Key relevant findings**. CNV har
Gain/Loss, Cytoband og **Add CNV row**. CNV og RNA har QC-kommentar i hver sin
fane. **Expand table** åpner tabellen i en justerbar visning der zoom skalerer
hele tabellen.

Biomarker viser genmedlemskap i genlisten fra september 2026. Et treff velger
ikke Include eller Highlight. Class_judgement og CPSR_ClinVar_class gir
startvalg for uvurderte varianter. Allerede lagrede valg beholdes;
**Use source defaults** henter kildevalgene på nytt.

## IGV og referansegenomer

IGV trenger lokal referansesekvens i tillegg til BAM-filen og indeksen.
Legg komplette filpar i `.local-web/references/`:

- `GRCh37.fa` og `GRCh37.fa.fai`
- `GRCh38.fa` og `GRCh38.fa.fai`

Start serveren igjen etter at filer er lagt til. Åpne **Variant review → View
in IGV**, velg BAM og tilhørende `.bai` eller `.csi`, og trykk **Open local
files**. Rapporten, BAM-filen og referansen må bruke samme genombygg.
Et regionutdrag viser bare alignments innenfor området som finnes i filen.

Lokalt filvalg sender ikke BAM-filen til serveren. Referansene gjøres
tilgjengelige etter innlogging. Dette aktiverer ikke lagring av BAM-filer.
Se [IGV-drift](igv-alignment-operations.md) for eget oppsett.

## Drift og tidssone

Oppstarten binder til `127.0.0.1` og bruker Djangos utviklingsserver. Drift
for flere brukere trenger eget HTTPS- og produksjonsserveroppsett.
`.local-web` inneholder database, private filer og lokalt oppsett og skal ikke
deles eller legges i Git. Oppbevar sikkerhetskopier utenfor Git.

Appen viser tider i `Europe/Oslo`, med automatisk sommer- og vintertid.
Databasen og API-et beholder UTC.

Lokal oppstart aktiverer arbeidskladder automatisk. For egen serverinstallasjon
aktiveres flyten med `PRONTO_WORKING_DRAFTS=true` etter migrering. Kommando-API
v2 bruker eget endringstoken; eldre klienter må oppdateres eller bruke den eldre
arbeidsflyten. Se [kommando-API](review-command-contract.md).
