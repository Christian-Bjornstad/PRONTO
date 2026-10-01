# Variant review og to rapportformater — designutkast

Dato: 2026-09-30. Status: planleggingsutkast; produktkode er ikke endret.

Bestilling: nye VUS-/highlight-felt, alle relevante Excel-data inne i arbeidsflaten,
Review-listen Benign/VUS/Oncogenic, Exclude, to eksportknapper og felles rapporttekster.
Spørsmålene kan besvares når brukeren er tilbake; forslagene nedenfor er ikke
registrert som godkjente kliniske eller formatmessige valg.

## Formål og eksisterende løsning

Molekylærbiologen skal kunne gjennomføre variantvurderingen uten en separat
Excel-fil, velge rapportfunn, skrive tekst én gang og produsere begge rapportformatene.
Arbeidsflaten skal fortsatt være den kjente femfaners løsningen.

Planleggingen bygger på `feature/report-review-workspace`, commit `a4b188c`, i
`repos/PRONTO/.worktrees/igv-django-integration`. Dette er nyere enn hovedutsjekken
og den gamle `prototype/`-rapporten. Eksisterende funksjoner omfatter eksplisitt
Save, revisjoner, FINAL-lås, Reset, IGV, QC-vurdering og revidert HTML-nedlasting.

Kontrollert i kildekoden:

- `ReviewState` v2 har separat `reportingDecision` og `clinicalClassification`.
  Klassene er UNCLASSIFIED/PATHOGENIC/UNCERTAIN/OTHER; Benign og Oncogenic finnes
  ikke som egne verdier. Et tekstbytte i nedtrekkslisten alene er derfor utilstrekkelig.
- Key findings viser proteinendrende varianter, kildefrekvens/dybde, IGV og utvalg.
- Variant review viser kompakte kolonner og et utvalg importerte annotasjoner i Details.
- Adapteren leser PRONTO-TSV, og mapper 13 annotasjonskolonner eksplisitt.
  Den er ikke en generell importør av brukerens Excel-arbeidsbok.
- Notatfeltene summary, biomarkerContext og additional finnes allerede.
- HTML-eksporten bruker lagret revisjon, korrigerte verdier og unike INCLUDE-varianter.
  Den har foreløpig én generisk layout, ingen formatvelger og ingen highlight-markering.

## Referanser og visuell målsetting

Bildene i bestillingen er layoutreferanser. Pasientdata, legemidler, kliniske
konklusjoner og terskler i bildene skal ikke bli standardinnhold i appen.

**Bilde 1: presentasjonsrapport i liggende format.** Smalt venstrefelt med
pasient-/prøve-/analysedata, et hovedfelt med resultatsammendrag, key relevant
findings og variant description, og en smal tabell til høyre med inkluderte
SNV-/indel-varianter. Lyse gråblå seksjonsfelt og kompakt tabelltypografi.
Sensitive/resistant-feltene beholder den viste grønne/røde markeringen sammen
med tekst. VUS markeres i tabell og forklares i fotnote.

**Bilde 2: stående rapport, tre sider vist ved siden av hverandre.**

| Side | Seksjoner | Utforming |
| --- | --- | --- |
| Summary | Patient and sample details; Assay details; Assay quality evaluation; History / Reason for testing; Summary of most relevant findings | Mørk blå typografi, gråblå tabeller, identifikasjon øverst |
| Results | Mutations; Copy number alterations; Gene fusions; Mutational signatures | Mørk grønn typografi og tabellhoder; QC ved relevante seksjoner |
| Biomarkers clinical evidence | Clinical actionability annotation; Clinical trial biomarker matching; Findings for potential follow-up | Olivengrønn typografi og tabellhoder; kilder og forbehold nederst |

Brukerens navn «ESMO» brukes som arbeidsnavn for dette formatet. Bildet alene
fastsetter ikke en ESMO-standard eller godkjent rapporttekst. Målet om å se helt
lik ut beholdes; nøyaktig sidestørrelse, skrifter, logo og marger kontrolleres mot
originalmalen hvis den er tilgjengelig. Utsnittet skal ikke behandles som hele malen.

## Anbefalt arbeidsflyt

1. Åpne Variant review og se alle importerte kildekolonner.
2. Sett Review, Include/Exclude, IGV og eventuell kommentar.
3. Marker VUS og Report highlight fra Key findings; samme vurdering vises i begge faner.
4. Åpne report-fanen og fyll felles tekster samt eventuelle evidensrader.
5. Forhåndsvis begge rapportlayoutene med arbeidskopien tydelig merket som ulagret.
6. Save lagrer en ny revisjon. De to eksportknappene bruker denne revisjonen.

### Review, VUS, highlight og utvalg

Forslag til én sannhetskilde per valg:

| Visning | Lagring | Foreslått oppførsel |
| --- | --- | --- |
| Review | `clinicalClassification`: UNCLASSIFIED/BENIGN/VUS/ONCOGENIC | Tom starttilstand vises som Not reviewed; de tre kliniske valgene er Benign, VUS og Oncogenic |
| VUS-checkbox | Avledet fra `clinicalClassification == VUS` | Avhuking setter VUS. Fjerning av huk når klassen er VUS setter UNCLASSIFIED. Ingen ekstra boolsk VUS-verdi |
| Include | `reportingDecision == INCLUDE` | Beholdes som eksplisitt valg; klasse alene velger ikke funnet til rapport |
| Exclude-checkbox | `reportingDecision == EXCLUDE` | Huk setter EXCLUDE; fjerning setter UNREVIEWED. Et ekskludert funn kan inkluderes igjen med Include |
| Report highlight-checkbox | `reportHighlight: boolean` | Fremhever et inkludert funn. Endrer ikke klasse eller utvalg automatisk |

Ekskluderte rader gråes og kildeverdiene får gjennomstreking. Kontrollene for
gjeninkludering og Details skal fortsatt være tydelige og tilgjengelige.
Ekskludering sletter ikke klasse, kommentar, IGV-vurdering eller highlight-valg.
Highlight på en rad som ikke er INCLUDE vises som inaktivt for rapporten.

| Rapporteringsvalg | Highlight | Rapporttabell | Fremhevet funn |
| --- | --- | --- | --- |
| INCLUDE | false | Ja | Nei |
| INCLUDE | true | Ja | Ja |
| EXCLUDE | begge | Nei | Nei |
| UNREVIEWED | begge | Nei | Nei |

VUS kan inkluderes og fremheves, men merkes synlig. Benign ekskluderes ikke
automatisk med mindre brukeren ber om en slik regel. Søk, filtre og sortering
endrer aldri rapportutvalget.

Duplikate kildeforekomster beholder egne occurrenceId og kildeverdier og deler
vurdering via variantId. Eksport viser én biologisk variant én gang. Ved ulike
annotasjoner mellom forekomster må verdier være kildehenvist; ingen stilltiende
valg av den mest fordelaktige annotasjonen.

### Hele Excel-datagrunnlaget

Før import implementeres må det avklares hvilken arbeidsbok/tabell og hvilke
ark som faktisk er autoritative. Bevar alle kolonner i den avtalte variantkilden,
også tomme felter, nye/ukjente kolonner og original kolonnerekkefølge.

Vis kompakte kolonner med gen, variant, frekvens, dybde, Review, Include, Exclude,
highlight og IGV. Legg til **All source columns** som utvidet tabellmodus og
fullstendige kildefelter i Details, slik at ingen verdi krever en separat fil.
Søk skal inkludere de importerte kildefeltene. Brede tabeller skal rulle i sin
egen region. Ekskluderte rader skal fortsatt kunne undersøkes.

Importen bevarer ark/fil, rad, kolonne, datatype, original verdi og filhash.
En vurdering bindes til stabil variantidentitet, aldri til dagens synlige radnummer.
Dublette kolonneoverskrifter skiller seg ved kolonneindeks. Formler skal ikke
kjøres: bevar formeltekst og eventuelt eksisterende beregnet verdi med tydelig
status når verdi mangler. Hyperlenker og HTML-lignende tekst gjengis trygt som data.
Ingen kolonner kuttes stille dersom kontrakt- eller størrelsesgrenser overskrides.

Det eksisterende TSV-sporet beholdes. Full visning av TSV er et nyttig første
steg, men oppfyller ikke «hele Excel-filen» før den er sammenlignet med riktig arbeidsbok.

### Report highlight for biomarkører og andre funn

Variantenes highlight-checkbox dekker ikke alene TMB/MSI, CNV, fusjoner eller
splicing. Planen omfatter separate highlight-valg for tilgjengelige biomarkører,
og tilsvarende valg for strukturerte CNV-/RNA-funn når deres kilde er kartlagt.
Målinger beholder sine eksisterende metricId; andre funn trenger stabile findingId.
Manglende HRD, fusjonsresultat eller CNV-data vises som Not provided, aldri som
Negative eller None detected. En tom liste er ikke bevis på negativ analyse.

### Rapportfelter og felles tekst

Gjenbruk eksisterende felter og legg til det som mangler:

| Felt i report-fanen | Presentasjonsrapport | Stående rapport |
| --- | --- | --- |
| History / Reason for testing, nytt | Kort klinisk bakgrunn | Summary: egen seksjon |
| Summary of most relevant findings, eksisterende summary | Hovedsammendrag | Summary: funnsammendrag |
| Biomarkers and therapeutic context, eksisterende biomarkerContext | Terapeutisk tekst ved fremhevede funn | Biomarkers clinical evidence: konteksttekst |
| Variant description, nytt | Egen seksjon | Results: tolkningstekst etter aktuelle funn |
| QC interpretation, eksisterende runQcAssessment.comment | Kort analysemerknad | Assay quality evaluation og relevante QC-merknader |
| Additional comments, eksisterende additional | Kommentarer/fortsettelsesside | Relevant merknadsseksjon |
| References, nytt | Referanser nederst/fortsettelsesside | Referanser ved evidens/avslutning |
| Follow-up, nytt | Kort oppfølging/fortsettelsesside | Findings for potential follow-up |
| Assay / methods / limitations, nytt | Kompakt assay-tekst | Assay details og metode-/begrensningstekst |

Identifikasjon, prøveinformasjon og målinger hentes fra validerte kilder og
lagrede korreksjoner. Manglende fakta som skal fylles manuelt trenger egne
merkede rapportfelter; de skal ikke fremstilles som importerte fakta.

En tekstboks er ikke nok til tabellene i referansene. Gi manuell radredigering
for terapeutisk kontekst, EMA-kontekst, klinisk evidens, studier og oppfølging.
Verdiene hentes fra en faktisk kilde eller skrives inn av reviewer. Ingen
automatisk OncoKB-, ESCAT-, legemiddel- eller studieanbefaling inngår i endringen.
Generelle tekster vises én gang; variantrader kan knyttes til variantId, øvrige
rader til metricId/findingId. Ikke kopier pasienttekster fra eksempelbildene.

## Arkitektur og eksport

Anbefaling: én felles rapportprojeksjon, to vedlikeholdte layoutmaler. Dette
gjenbruker eksisterende lagring/revisjoner og hindrer at formatene viser ulike
utvalg eller tekst. Å kopiere den levende DOM-en eller bygge rapportene helt
uavhengig anbefales ikke; det øker risikoen for ulagrede data og innholdsavvik.

- `ReportData` v2 utvider kildegrunnlaget med komplette tabeller og nødvendige
  strukturerte fakta. v1 forblir lesbart; innhent kilden før det hevdes full dekning.
- `ReviewState` v3 lagrer de nye klassene, reportHighlight, ekstra notater og
  kuraterte rapport-/evidensrader. Eksisterende v1/v2-historikk bevares.
- VUS-checkboxen har ingen egen lagringsverdi. Exclude har ingen egen
  konkurrerende boolsk verdi; begge er visninger av etablerte beslutningsfelter.
- Migrering lagrer tidligere klasse i legacyClinicalClassification og setter
  ny klasse til UNCLASSIFIED inntil en uttrykkelig godkjent mapping finnes.
  Særlig PATHOGENIC skal ikke automatisk bli ONCOGENIC. Eldre FINAL-rapporter
  forblir låst og gjengis med opprinnelig klasse; migrering alene skaper ingen revisjon.
- Et felles `project_report_export(report, review)` bruker kun lagrede
  korrigerte verdier, include/highlight-reglene, notater og kildehenvisninger.
- To hovedknapper: **Export presentation report** og **Export ESMO report**.
  Forhåndsvisning av begge er tilgjengelig før eksport. JSON backup forblir separat.
- Filformat er åpent: anbefalt leveranse er redigerbar PPTX for presentasjon
  og PDF for stående rapport; to selvstendige utskrivbare HTML-filer er et
  enklere alternativ som bygger direkte på dagens eksport. Velg etter svar.
- Uansett filformat bruker eksporten serverens lagrede revisjon, ikke nettleserens
  tabellrader. Ulagrede endringer blokkerer eksport med Save-first-melding.
- Ny audit identifiserer layout, filformat, malversjon, rapportrevisjon,
  requestId, aktør, initialer og tidspunkt. Historisk HTML-audit bevares.
  En retry må gjengi den registrerte historiske revisjonen og samme malversjon;
  gjenbruk av requestId med annen layout eller format er konflikt.

Presentasjonens høyretabell er for SNV/indel; inkluderbare CNV-/RNA-funn har
egne seksjoner. Ingen inkluderte funn skal forsvinne fordi en side er full.
Store tabeller og lange tekster lager merkede fortsettelsessider med repeterte
overskrifter, identifikasjon og sidetall. Bruk ikke uleselig fontkrymping.
Stående rapport starter med de tre referansesidene og kan bli lengre ved behov.

## Akseptansekriterier

1. VUS og Report highlight vises i Key findings og synkroniseres med Variant
   review, også ved duplikate kildeforekomster og etter Save/reload/Reset.
2. Review tilbyr Benign/VUS/Oncogenic; eldre vurderinger går ikke tapt eller
   gis en ny klinisk mening uten en avtalt mapping.
3. Exclude gråer/gjennomstreker raden, bevarer vurderingen og fjerner funnet
   fra begge eksportene. Unreviewed blir heller ikke eksportert som inkludert.
4. Hver kolonne og verdi fra avtalt Excel-kilde er tilgjengelig i appen,
   kontrollert mot en godkjent testarbeidsbok. Nye kolonner tapes ikke.
5. Highlight avgjør fremheving; Include avgjør rapportutvalg. En filtrert eller
   sortert arbeidsflate endrer ikke rapportenes innhold.
6. Alle nye tekstfelter og evidensrader lagres og gjenfinnes i begge formatene
   på avtalt plass. Rapporttekst kan ikke produsere HTML/script-injeksjon.
7. Liggende rapport gjenskaper bilde 1; stående rapport gjenskaper sideinndeling,
   seksjoner og tabellstruktur i bilde 2. Originalmal styrer nøyaktig visuell sammenligning.
8. Lange tekster, mange inkluderte varianter, tomme seksjoner og lange gen-/variantnavn
   gir lesbar eksport uten avkutting, overlapp eller skjulte funn.
9. Eksport bruker én lagret revisjon med korreksjoner og tydelig DRAFT/FINAL-status.
   Konflikter, retry, tilgang, audit, eksisterende IGV, Save og FINAL fungerer fortsatt.

## Avklaringer før produktimplementasjon

Se [spørsmål til neste gjennomgang](../../report-formats-questions-nb.md).
De viktigste valgene er filformat, riktig Excel-kilde, VUS/Review-sammenheng,
utvalgsregel og original rapportmal. Implementasjonsplanen beskriver hvilke
deler som avhenger av hvert svar, uten å late som de allerede er besluttet.
