/* Web-only IGV controller. A local File is never posted or persisted here. */
/* igv.js browser/reference/track APIs: https://igv.org/doc/igvjs/Browser-Creation/ */
/* Alignment track format and indexURL: https://igv.org/doc/igvjs/tracks/Alignment-Track/ */
const panel = document.getElementById("igv-panel");

if (panel) {
  const status = document.getElementById("igv-status");
  const viewer = document.getElementById("igv-viewer");
  const select = document.getElementById("igv-source");
  const dataInput = document.getElementById("igv-data");
  const indexInput = document.getElementById("igv-index");
  const localState = document.getElementById("igv-local-state");
  const sources = JSON.parse(document.getElementById("igv-sources").textContent);
  const references = JSON.parse(document.getElementById("igv-references").textContent);
  let locus = null;
  let build = panel.dataset.referenceBuild;
  let activeBrowser = null;
  let igvModule = null;
  let launcher = null;
  let busy = false;
  let generation = 0;

  function setStatus(message) {
    status.textContent = message;
  }

  function sameOriginPath(value) {
    return typeof value === "string" && value.startsWith("/") && !value.startsWith("//") && !value.includes("\\");
  }

  function referenceForBuild(requestedBuild) {
    const reference = references[requestedBuild];
    if (!reference || !sameOriginPath(reference.fastaURL) || !sameOriginPath(reference.indexURL)) {
      throw new Error(`Referansefiler for ${requestedBuild} er ikke konfigurert på denne serveren.`);
    }
    return { id: requestedBuild, name: requestedBuild, fastaURL: reference.fastaURL, indexURL: reference.indexURL };
  }

  function selectedLocalPair() {
    const dataFile = dataInput.files[0];
    const indexFile = indexInput.files[0];
    if (!dataFile || !indexFile || !dataFile.size || !indexFile.size) {
      throw new Error("Velg både en BAM/CRAM-fil og tilhørende indeks.");
    }
    const format = dataFile.name.toLowerCase().endsWith(".bam") ? "bam" :
      dataFile.name.toLowerCase().endsWith(".cram") ? "cram" : null;
    if (!format || !(format === "bam" ? /\.(bai|csi)$/i : /\.crai$/i).test(indexFile.name)) {
      throw new Error("Filformat og indeks passer ikke sammen.");
    }
    return { dataFile, indexFile, format };
  }

  async function openPair(track, isLocal) {
    if (busy || !locus) return;
    busy = true;
    const currentGeneration = ++generation;
    const requestedLocus = locus;
    localState.hidden = true;
    setStatus("Åpner IGV …");
    try {
      const reference = referenceForBuild(build);
      igvModule ??= (await import("./igv/igv.esm.min.js")).default;
      if (activeBrowser) {
        igvModule.removeBrowser(activeBrowser);
        activeBrowser = null;
      }
      viewer.replaceChildren();
      const createdBrowser = await igvModule.createBrowser(viewer, {
        reference,
        locus: requestedLocus,
        loadDefaultGenomes: false,
        queryParametersSupported: false,
        showSVGButton: false,
        tracks: [{ type: "alignment", format: track.format, name: track.name,
          url: track.data, indexURL: track.index }],
      });
      if (currentGeneration !== generation) {
        igvModule.removeBrowser(createdBrowser);
        return;
      }
      activeBrowser = createdBrowser;
      if (locus !== requestedLocus) {
        await createdBrowser.search(locus);
        if (currentGeneration !== generation) return;
      }
      setStatus(isLocal ? "Lokal fil åpnet i IGV. Ikke lagret." : `Registrert kilde åpnet: ${track.name}.`);
      localState.hidden = !isLocal;
    } catch (_error) {
      if (currentGeneration === generation) {
        viewer.replaceChildren();
        setStatus(`IGV kunne ikke åpnes. ${_error.message || "Kontroller filer og referanse."}`);
      }
    } finally {
      busy = false;
    }
  }

  document.querySelectorAll("[data-igv-locus]").forEach((button) => {
    button.addEventListener("click", async () => {
      launcher = button;
      locus = button.dataset.igvLocus;
      panel.hidden = false;
      panel.scrollIntoView({ block: "nearest" });
      document.getElementById("igv-close").focus();
      if (activeBrowser) {
        try {
          await activeBrowser.search(locus);
          setStatus(`IGV flyttet til ${locus}.`);
        } catch (_error) {
          setStatus("Kunne ikke flytte IGV til denne varianten.");
        }
      } else {
        setStatus(document.getElementById("igv-registry-error")
          ? "Registrerte kilder er utilgjengelige. Velg lokale filer eller kontakt administrator."
          : sources.length ? "Velg en registrert kilde eller lokale filer." : "Ingen registrert kilde. Velg lokale filer.");
      }
    });
  });

  for (const source of sources) {
    if (source.referenceBuild !== build || !sameOriginPath(source.dataURL) || !sameOriginPath(source.indexURL)) continue;
    const option = document.createElement("option");
    option.value = source.sourceId;
    option.textContent = `${source.role.replaceAll("_", " ")} · ${source.format.toUpperCase()}`;
    select.append(option);
  }
  select.disabled = select.options.length < 2;
  document.getElementById("igv-open-source").addEventListener("click", () => {
    const source = sources.find((item) => item.sourceId === select.value && item.referenceBuild === build);
    if (!source || !sameOriginPath(source.dataURL) || !sameOriginPath(source.indexURL)) {
      setStatus("Velg en registrert kilde først.");
      return;
    }
    void openPair({ format: source.format, name: source.role, data: source.dataURL, index: source.indexURL }, false);
  });
  document.getElementById("igv-open-local").addEventListener("click", () => {
    try {
      const pair = selectedLocalPair();
      void openPair({ format: pair.format, name: "Lokal fil", data: pair.dataFile, index: pair.indexFile }, true);
    } catch (error) {
      setStatus(error.message);
    }
  });
  function closePanel() {
    generation += 1;
    panel.hidden = true;
    if (activeBrowser && igvModule) igvModule.removeBrowser(activeBrowser);
    activeBrowser = null;
    viewer.replaceChildren();
    dataInput.value = "";
    indexInput.value = "";
    localState.hidden = true;
    setStatus("Velg en variant.");
    launcher?.focus();
  }
  document.getElementById("igv-close").addEventListener("click", closePanel);
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePanel();
  });
}
