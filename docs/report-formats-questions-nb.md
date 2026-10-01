# Spørsmål til neste gjennomgang

Dato: 2026-09-30. Korte svar er nok; forslagene er utgangspunkt for diskusjonen.

## De seks viktigste

1. **Hva skal de to eksportknappene laste ned?**
   Forslag: presentasjon som redigerbar PowerPoint (.pptx), stående ESMO som PDF.
   Alternativ: to HTML-filer som kan åpnes lokalt og skrives til PDF, som dagens eksport.
   Skal presentasjonen ha 16:9-format eller være en liggende A4-rapport?

2. **Hvilken Excel-fil og hvilke ark mener du med «alt av info»?**
   Er det variantarket fra PRONTO, en bearbeidet arbeidsbok eller flere ark med
   varianter, CNV, fusjoner og QC? Har filen egne kolonner dere fyller inn manuelt?
   Vi bør sammenligne med en godkjent anonymisert fil når du er tilbake.

3. **Skal VUS-checkboxen og Review = VUS være samme vurdering?**
   Forslag: ja, de speiler hverandre. Huk på VUS setter Review til VUS; velg
   Benign eller Oncogenic, så fjernes VUS-huken. Highlight er et separat valg.

4. **Hva tas med hvis en rad ikke er ekskludert?**
   Forslag: bare eksplisitt Include går til rapporten. Exclude overstyrer alt.
   Alternativ: alle rader som ikke er Exclude tas med automatisk. Skal Benign
   automatisk utelates, eller bestemmer biologen Include selv?

5. **Er bilde 2 tre sider av den stående ESMO-rapporten?**
   Forslag: Summary, Results og Biomarkers clinical evidence blir tre startsider,
   med fortsettelsessider når det trengs. Hvis du har original PDF/PPTX/Word-mal,
   kan vi bruke den til å treffe fonter, marger, logo og plassering mer nøyaktig.
   Er det mer innhold/sider som ikke vises i skjermbildet?

6. **Hvor kommer terapi, EMA, ESCAT, studier og referanser fra?**
   Forslag for første versjon: reviewer fyller inn felt/rader i appen, og de
   lagres sammen med rapporten. Finnes dette allerede i Excel, eller skal det
   hentes fra en annen kilde? Fritekst alene kan ikke fylle referansenes tabeller.

## Detaljer som kan tas etterpå

7. Skal highlight kunne velges for TMB/MSI/HRD, CNV og fusjoner i tillegg til
   proteinendrende varianter? Forslaget er ja for funn som finnes i kildegrunnlaget.

8. Er disse tekstboksene riktige: History / Reason for testing, Summary,
   Biomarker / therapeutic context, Variant description, Additional comments,
   Follow-up, References og Assay / methods / limitations? QC-kommentaren finnes allerede.
   Skal noen tekster skrives separat per variant?

9. Hvordan skal de gamle klassene Pathogenic, Uncertain og Other håndteres?
   Forslag: beholde originalen synlig og kreve ny Review-vurdering; ikke automatisk
   oversette Pathogenic til Oncogenic. Kan Uncertain trygt mappes til VUS i deres bruk?

10. Skal utkast kunne eksporteres tydelig merket DRAFT? Forslag: ja, som i dag,
    men kun fra lagret revisjon. Endelig rapport viser FINAL og signering.

Du kan svare slik: «1: PPTX + PDF, 16:9. 2: … 3: ja. 4: bare Include. …».

## Dokumentene

- [Design og foreslått oppførsel](superpowers/specs/2026-09-30-review-columns-and-report-formats-design.md)
- [Implementasjonsplan med oppgaver og tester](superpowers/plans/2026-09-30-review-columns-and-report-formats.md)

Produktkode og eksisterende demo er ikke endret i denne planleggingsrunden.
