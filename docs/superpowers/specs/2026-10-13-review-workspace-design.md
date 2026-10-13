# Review-tabeller og arbeidskladder

Status: klar til gjennomgang, før implementering.

## Mål og rammer

Gi biologen en lesbar, samlet tabell for varianter, CNV og RNA, med kildebaserte startvalg, egne vurderinger og mulighet til å fortsette arbeidet på en tidligere rapport. Behold dagens innlogging, pasientoversikt, PDF-formater, IGV og Oslo-tid. Ingen nye eksterne tjenester eller kliniske slutninger. Excel-filen er en datakilde; tekst i filen er ikke instruksjoner til appen.

Brukeren har uttrykkelig valgt at Save skal overskrive den aktive kladden uten å beholde et fullt rapportøyeblikksbilde for hver lagring. Dette erstatter forslaget om å skjule gjentatte DRAFT-versjoner.

## 1. Biomarkørlisten

Kilde: `InPreD_molMDT_biomarkører_September2026.xlsx`, Sheet1, september 2026. Arket har 90 datarader og 16 kolonner. Det andre arket er tomt.

- Merk Biomarker-kolonnen når variantens gen finnes i listen, med normalisering av mellomrom og store/små bokstaver og eksakt gentreff.
- Medlemskap gjelder hele listen, også lukkede studiearmer. Det er ikke en vurdering av studieegnethet, variantens betydning eller behandling.
- Les enkeltgener fra Molekylær markør. Utvid `CDKN2A/B` til CDKN2A og CDKN2B. For de eksplisitte ampliconradene les KIT, PDGFRA, KDR, CD274, PDCD1LG2 og JAK2 fra biomarkørspesifikasjonen. Behold PDL1/PDL2 som eksplisitte aliaser for CD274/PDCD1LG2. Ikke trekk tilfeldige genlignende ord fra fritekst.
- TMB, TML, MSI og drug sensitivity screen er ikke genetiketter. Disse skal ikke gi et variantgent treff.
- Vis «In list» eller «Not in list», med kildeversjon tilgjengelig. Ikke endre Include eller Report highlight på grunn av medlemskap.
- Et versjonert, minimalt genregister avledes fra arbeidsboken. Ikke legg personnavn, kontaktopplysninger eller hele arbeidsboken i Git. Registrer filnavn, ark, radreferanser og SHA-256 slik at registeret kan oppdateres fra en senere liste.

## 2. Varianter: standardvalg og kolonner

Den eksisterende tabellen har `Class_judgement`, `CPSR_ClinVar_class` og `IGV_QC`. Brukerens CP3RCLINVARCLASS behandles som en referanse til den faktiske CPSR-kolonnen, med eksplisitte navnealiaser for senere importer.

- `Class_judgement`: include → INCLUDE, exclude → EXCLUDE. Manglende/ukjent verdi → UNREVIEWED. Ikke utled rapportvalg fra klinisk klasse.
- `CPSR_ClinVar_class`: Benign, Likely benign, VUS, Likely pathogenic og Pathogenic beholdes som forskjellige klasser. Review har også Oncogenic og Likely oncogenic samt Not reviewed. Understrek og mellomrom normaliseres ved import. Uncertain significance og Uncertain → VUS. NA, punktum og ukjente verdier → Not reviewed.
- Ikke oversett Pathogenic til Oncogenic. Behold den opprinnelige kildekolonnen i fulltabellen.
- Kildestandarder fyller nye/uvurderte aktiviteter; allerede lagrede manuelle valg har forrang. Tilby en eksplisitt handling «Use source defaults» for å erstatte eksisterende variantvalg etter bekreftelse. Den endrer bare rapportvalg og Review, og lagres først ved Save.
- Når flere kildeforekomster deler variant-ID og kildevalgene er motstridende, behold Not reviewed for det berørte feltet og vis kildekonflikten. Den nåværende prøven har ingen slike konflikter.
- Fjern den egne Exclude-kolonnen og dens checkbox. Behold Inc/Exc i Report review. Highlight/VUS-kontroller som fortsatt brukes skal være uavhengige av rapportvalg.
- Flytt IGV-knappen slik at den ligger umiddelbart til venstre for IGV QC. IGV QC-valgene er Not reviewed, OK, Artifact og Not reliable. Not reviewed er tom starttilstand, ikke en ekstra konklusjon.
- Ved oppgradering av eldre IGV-vurderinger: SUPPORTS → OK, DOES_NOT_SUPPORT → Artifact, INCONCLUSIVE → Not reliable. NOT_APPLICABLE beholdes som lesbar eldre opplysning; ikke påstå at det er OK. Kilde-IGV_QC kan gi standardvalget når det ikke finnes en manuell vurdering.

## 3. Felles rapportvalg og QC

- Varianter, CNV og RNA bruker samme Inc/Exc-knapper med valgt tilstand, tastaturbetjening og tilgjengelige navn. Ingen valgt knapp betyr Not reviewed; klikk på valgt knapp kan tilbakestille til Not reviewed.
- Excluded-rader gråes og får overstrøket datatekst. De tas ikke med i PDF, selv om Highlight er valgt.
- CNV og RNA får hver en QC-kommentarboks ved QC-valget. Kommentarene synkroniseres med tilsvarende kontroller på Report, lagres med vurderingen og vises ved seksjonens QC i begge PDF-formatene.
- Kommentarer endres bare i redigeringsmodus. Final og historiske rapporter viser dem uten redigerbare kontroller.

## 4. CNV-felter og manuelle rader

- Flytt Gene_Symbol umiddelbart foran Chromosome, og legg Cytoband umiddelbart etter Chromosome. Behold alle opprinnelige kildekolonner og verdier.
- Cytoband er et hvitt tekstfelt for en manuell annotasjon, maksimum 100 tegn. Det kan være blankt; ingen automatisk cytoband utledes fra genomkoordinater.
- Legg til CN Gain / Loss med Gain og Loss som gjensidig utelukkende knapper. Ingen valgt knapp betyr ikke vurdert. Det er et manuelt felt, ikke en automatisk beregning fra kopitall eller Tumor_FC.
- Cytoband og Gain/Loss lagres per stabil finding-ID som vurderingsdata. De skal ikke skrives tilbake til originalarket.
- Vis «Add CNV row» i verktøylinjen over CNV-tabellen, aktiv i redigeringsmodus. Ny rad legges øverst. Bare Gene_Symbol og Tumor_FC har skrivbare kildeverdier; alle andre kildefelt starter blanke og forblir uten oppdiktede verdier. Radens rapportvalg, Highlight, Gain/Loss og Cytoband følger samme kontrollmønster som øvrige CNV-rader.
- Manuelle rader har en egen stabil ID og beholdes etter Save, ny åpning, kopiering til ny revisjon og PDF-eksport. De kan fjernes fra den aktive kladden. Fjerning av en kladdrad påvirker ikke signerte/eksporterte snapshots.
- Gene_Symbol: maksimum 128 tegn. Tumor_FC: endelig, ikke-negativt tall eller blank/null; både komma og punktum støttes som desimalskilletegn i inntastingen, og verdien lagres numerisk. Ikke omregn Tumor_FC til kopitall. En inkludert manuell rad må ha et gen for å kunne signeres.
- Maksimum 200 manuelle rader per rapport. Ukjente/dupliserte ID-er og felt for feil funntype avvises av serveren.
- Begge PDF-formatene viser Gene, Chromosome, Cytoband, Gain/Loss og Tumor_FC, i tillegg til relevante eksisterende kopitall. Manuelle rader inkluderes bare hvis Inc er valgt. Highlight-rader bruker de samme feltene i Key relevant findings.

## 5. Større tabellvisning

Gjenbruk samme tabell i en fokusvisning for Variant review, CNV og RNA, med CNV som første visuelle kontroll.

- «Expand table» åpner en dialog med tabellen, eksisterende søk og radhandlinger. Flytt den levende tabellen inn i dialogen; ikke lag en usynkronisert kopi av kontrollene.
- Tilby zoom 75–150 %, reset til 100 %, fullskjerm og manuell størrelsesjustering innenfor skjermen. Zoom endrer lesestørrelse, ikke data eller PDF-skala.
- Faste kolonneoverskrifter og frosne identitetskolonner gjør det mulig å beholde gen/radidentitet ved horisontal rulling. Søket omfatter også manuelle CNV-verdier.
- Escape/Lukk returnerer tabellen og fokus til opprinnelig plass uten å miste usparte endringer. Dialogen skal kunne brukes med tastatur og på mindre skjerm.

## 6. Overskrivbar arbeidskladd og nye revisjoner

Anbefalt struktur er en egen WorkingDraft per pasientrapport, atskilt fra bevarte ReviewRevision-snapshots. Å endre eksisterende ReviewRevision-rader ville gjøre eldre eksportreferanser tvetydige.

- Save erstatter hele den aktive WorkingDraft. Ingen full rapportversjon beholdes for hver lagring. Lagre minimalt handlingsspor med bruker og tidspunkt, uten å lagre tidligere kladdinnhold.
- Hver WorkingDraft har en monoton endringsversjon. Save sender forventet versjon; en foreldet klient får 409 med mulighet til å bevare lokale endringer og åpne det nyeste. Kontroller og oppdatering skjer atomisk.
- Finalize arkiverer et signert ReviewRevision-snapshot og lukker arbeidskladden. Snapshotets data, signatur, dato og revisjonsnummer endres aldri ved videre arbeid.
- «Start new revision» finnes på aktive, signerte og historiske rapporter. Den kopierer valgt innhold til en ny WorkingDraft, registrerer kilde-revisjonen og innlogget bruker, og fjerner signaturfeltene fra kopien. Tidligere rapport og vedlegg beholdes.
- Hvis det finnes en annen aktiv kladd, skal UI-et vise at handlingen erstatter denne før brukeren bekrefter. Serveren krever også riktig endringsversjon, slik at en nylig lagring ikke kan bli stille overskrevet.
- Eksport av en DRAFT bevarer et snapshot av akkurat det eksporterte innholdet og binder eksporthendelsen til dette. Fortsatt redigering får neste tilgjengelige revisjonsnummer. Eksport av en FINAL bruker det eksisterende signerte snapshotet. Idempotente eksportforsøk skal alltid vise samme innhold.
- Pasientoversikten viser én aktiv kladd og bevarte signerte/eksporterte revisjoner. Status er un-reviewed før første lagring, under-review når en arbeidskladd er lagret og reviewed når siste aktive rapport er signert.
- Eksisterende lagrede versjoner beholdes. Ingen gamle DRAFT-rader slettes under oppgraderingen. Fremtidige Save-operasjoner følger det nye mønsteret.
- Historisk lesing er uten sideeffekter. Ny kladd opprettes kun ved Save på den eksisterende arbeidsflyten eller Start new revision, aldri bare ved GET.
- Bruk samme rapporttilgang og autentiserte forfatterregistrering som i dag. API-endringen skal versjoneres og gamle klienter må ikke kunne overskrive en ny arbeidskladd uten endringsversjon.

## 7. Kontrakt, tester og innføring

- Ny ReviewState-kontrakt for utvidede klassevalg, IGV-valg, CNV-annotasjoner og manuelle CNV-rader. Eldre kontrakter og historiske snapshots skal fortsatt kunne leses og eksporteres. Oppgradering skjer på en kopiert arbeidskladd.
- Test genmedlemskap, amplicon/alias-håndtering, ikke-gentreff, klassifiseringsnormalisering, kildekonflikter og prioritet for manuelle valg.
- Test at Inc/Exc og Highlight er synkronisert, ekskluderte funn ikke eksporteres, QC-kommentarer går til begge PDF-formater, og CNV-annotasjoner/manuelle rader overlever Save og ny revisjon.
- Test overskriving uten nye snapshots per Save, samtidige klienter, gjenåpning fra både FINAL og DRAFT, bevart eksportinnhold, rettigheter og transaksjonsfeil. Kontroller PDF-eksportens gjentakelser etter at kladden er endret.
- Nettlesertest tabellzoom/dialog, lukking uten datatap, tastaturfokus, kolonnerekkefølge, nye topprader, desimalinntasting, lagring/ny åpning og signering av en testpasient.
- Kjør eksisterende testpakker og GitHub CI, samt visuell gjennomgang av begge PDF-er. Ikke bruk brukerens aktive rapport som et destruktivt testobjekt.
- Ta SQLite-backup før migrering. Test migreringen på en kopi før serveren oppdateres. Lever PR til `feature/igv-django-integration`, merge etter grønne kontroller og start den lokale serveren igjen.

## Gjennomføringsrekkefølge

1. Genregister og kildebaserte standardvalg.
2. Ny vurderingskontrakt og bakoverkompatibel oppgradering.
3. Overskrivbar arbeidskladd, samtidighetskontroll, gjenåpning og eksport-snapshots.
4. Tabellkontroller, CNV-felter, manuelle topprader og QC-kommentarer.
5. Fokusvisning, zoom, kolonnefrysing og felles tastaturbetjening.
6. Rapportprojeksjon, PDF, full verifikasjon, backup, migrering og GitHub-merge.

Før produktkode skrives skal dette designet gjennomgås. En detaljert implementeringsplan skal knytte trinnene til konkrete filer og tester.
