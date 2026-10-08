# Starte PRONTO på denne PC-en

Åpne PowerShell og kjør:

```powershell
Set-Location 'C:\Users\molpa\Documents\Inpred\repos\PRONTO\.worktrees\igv-django-integration'
.\.venv\Scripts\python.exe scripts\start_web.py
```

Åpne <http://127.0.0.1:8770/reports/> og logg inn. La PowerShell-vinduet stå åpent.
Stopp serveren med **Ctrl+C**. Start igjen med samme kommando.

Oppstarten husker database og port i `.local-web/config.json`. Den gjenbruker
nøkkelen i `.local-web/secret.key`; oppstarten lager ikke nye pasienter og nullstiller
ikke vurderinger. Databasen på denne PC-en er `.local-web/pronto.sqlite3`, med
de 31 eksisterende rapportene, lagrede versjoner og vedlegg.

Brukeren på denne PC-en heter **molpa**. Det første passordet ligger i den private
filen `.local-web/innlogging.txt`. Etter innlogging kan du velge **Change password**
i pasientoversikten. Denne filen oppdateres ikke automatisk etter passordbytte.

Lagring, nullstilling, signering og PDF-eksport knyttes til kontoen som er logget inn.
Du trenger ikke oppgi initialer. Tidligere lagrede versjoner beholder sin opprinnelige
registrering; nye handlinger registrerer brukernavn og bruker-ID fra innloggingen.

Hvis port 8770 er opptatt, velg en annen port:

```powershell
.\.venv\Scripts\python.exe scripts\start_web.py --port 8771
```

Da blir adressen <http://127.0.0.1:8771/reports/>. Porten huskes ved senere oppstart.
Serveren starter i forgrunnen; dersom den allerede kjører i bakgrunnen, stopp
prosessen med PID fra `.local-web/server.pid` før du starter igjen:

```powershell
$prontoServerPid = [int](Get-Content .local-web\server.pid)
$prontoServerProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $prontoServerPid"
if ($prontoServerProcess.CommandLine -like '*scripts/start_web.py*') {
    Stop-Process -Id $prontoServerPid
}
```

## Første oppstart på en annen PC

Installer Python og PDF-verktøyene `pdfinfo` og `pdftoppm` (Poppler). De må ligge
i PATH for å vise PDF-plottene. Fra prosjektmappen:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\start_web.py --setup-user ditt-brukernavn
```

Velg passord når terminalen spør. Denne oppstarten lager en tom database og en
vanlig brukerkonto. Kontoen får tilgang til rapportene som finnes ved opprettelse,
uten administratorrettigheter eller rett til å lagre alignments. Nye rapporter
må få eksplisitte tilgangstildelinger. For å bruke en eksisterende database:

```powershell
.\.venv\Scripts\python.exe scripts\start_web.py --database 'C:\sti\pronto.sqlite3' --setup-user ditt-brukernavn
```

Ikke bruk `--setup-user` når kontoen allerede finnes. Ta en sikkerhetskopi før du
oppgraderer en eksisterende database. Oppstarten kjører nødvendige database-migreringer.

## Drift og data

Dette er lokal oppstart med innlogging, bundet til `127.0.0.1`. Den bruker Djangos
utviklingsserver. Drift for flere brukere krever en egen installasjon med HTTPS og
en produksjonsserver; standardinnstillingene krever fortsatt sikre cookies.
`.local-web` inneholder private filer og skal ikke deles eller legges i Git.

De simulerte pasientene er fortsatt testdata. Gjentatte demo-bannere og automatisk
fylltekst er fjernet fra visningene. Kildeinformasjon, SYN-pasientkoder, kildeplotter
og opprinnelige revisjoner er bevart. Fritekst skrevet av brukere endres ikke.
Tabeller fra flere prøver er fortsatt merket med en kort beskjed om dette.
