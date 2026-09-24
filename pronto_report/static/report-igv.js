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
  const saveButton = document.getElementById("igv-save");
  const savedState = document.getElementById("igv-saved-state");
  const saveError = document.getElementById("igv-save-error");
  const saveDialog = document.getElementById("igv-save-confirm");
  const uploadProgress = document.getElementById("igv-upload-progress");
  const uploadMeter = document.getElementById("igv-upload-meter");
  const sources = JSON.parse(document.getElementById("igv-sources").textContent);
  const references = JSON.parse(document.getElementById("igv-references").textContent);
  let locus = null;
  let build = panel.dataset.referenceBuild;
  let activeBrowser = null;
  let igvModule = null;
  let launcher = null;
  let busy = false;
  let generation = 0;
  let activePair = null;
  let uploadController = null;
  let uploadSession = null;

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

  async function openPair(track, isLocal, source = null) {
    if (busy || !locus) return;
    busy = true;
    const currentGeneration = ++generation;
    const requestedLocus = locus;
    localState.hidden = true;
    if (savedState) savedState.hidden = true;
    if (saveError) saveError.hidden = true;
    if (saveButton) saveButton.disabled = true;
    activePair = null;
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
      activePair = isLocal ? { kind: "local", dataFile: track.data, indexFile: track.index, format: track.format }
        : { kind: source.sourceId.startsWith("saved-") ? "saved" : "registered", source };
      if (savedState) savedState.hidden = activePair.kind !== "saved";
      if (saveButton) saveButton.disabled = activePair.kind === "saved";
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
    option.textContent = `${source.sourceId.startsWith("saved-") ? "Lagret · " : ""}${source.role.replaceAll("_", " ")} · ${source.format.toUpperCase()}`;
    select.append(option);
  }
  select.disabled = select.options.length < 2;
  document.getElementById("igv-open-source").addEventListener("click", () => {
    const source = sources.find((item) => item.sourceId === select.value && item.referenceBuild === build);
    if (!source || !sameOriginPath(source.dataURL) || !sameOriginPath(source.indexURL)) {
      setStatus("Velg en registrert kilde først.");
      return;
    }
    void openPair({ format: source.format, name: source.role, data: source.dataURL, index: source.indexURL }, false, source);
  });
  document.getElementById("igv-open-local").addEventListener("click", () => {
    try {
      const pair = selectedLocalPair();
      void openPair({ format: pair.format, name: "Lokal fil", data: pair.dataFile, index: pair.indexFile }, true);
    } catch (error) {
      setStatus(error.message);
    }
  });
  for (const input of [dataInput, indexInput]) {
    input.addEventListener("change", () => {
      activePair = null;
      if (saveButton) saveButton.disabled = true;
      if (savedState) savedState.hidden = true;
    });
  }

  if (saveButton) {
    const reportId = encodeURIComponent(panel.dataset.reportId);
    const sampleId = panel.dataset.sampleId;
    const roleSelect = document.getElementById("igv-role");
    const summary = document.getElementById("igv-save-summary");
    const baseURL = `/reports/${reportId}/alignments/`;

    function csrfToken() {
      const token = document.cookie.split(";").map((item) => item.trim())
        .find((item) => item.startsWith("csrftoken="));
      if (!token) throw new Error("CSRF-token mangler. Last inn rapporten på nytt.");
      return decodeURIComponent(token.slice("csrftoken=".length));
    }

    async function checkedFetch(url, options) {
      const response = await fetch(url, { credentials: "same-origin", cache: "no-store", ...options });
      if (!response.ok) {
        if (response.status === 409) throw new Error("Et annet filpar er allerede lagret for denne prøven og rollen.");
        throw new Error(`Lagring feilet (${response.status}). Filene er ikke lagret.`);
      }
      return response;
    }

    async function sendChunks(sessionId, component, file, totalBytes, sentBytes, signal, token) {
      for (let start = 0; start < file.size; start += 8 * 1024 * 1024) {
        const end = Math.min(start + 8 * 1024 * 1024, file.size);
        await checkedFetch(`${baseURL}save-sessions/${sessionId}/${component}/`, {
          method: "PUT", body: file.slice(start, end), signal,
          headers: { "Content-Type": "application/octet-stream",
            "Content-Range": `bytes ${start}-${end - 1}/${file.size}`,
            "X-CSRFToken": token },
        });
        uploadMeter.value = Math.round(100 * (sentBytes + end) / totalBytes);
      }
    }

    async function cancelSession(sessionId, token) {
      try {
        await fetch(`${baseURL}save-sessions/${sessionId}/`, {
          method: "DELETE", credentials: "same-origin", cache: "no-store",
          headers: { "X-CSRFToken": token },
        });
      } catch (_error) {
        // Server expiry cleanup handles an unreachable cancellation endpoint.
      }
    }

    saveButton.addEventListener("click", () => {
      if (!activePair || activePair.kind === "saved" || uploadController) return;
      saveError.hidden = true;
      const role = activePair.kind === "local" ? roleSelect.value : activePair.source.role;
      const details = activePair.kind === "local"
        ? `${activePair.dataFile.name} + ${activePair.indexFile.name} (${(
          activePair.dataFile.size + activePair.indexFile.size).toLocaleString("nb-NO")} byte)`
        : `Registrert kilde: ${activePair.source.sourceId}`;
      summary.textContent = `Prøve ${sampleId} · ${build} · ${role.replaceAll("_", " ")} · ${details}`;
      saveDialog.showModal();
    });
    document.getElementById("igv-confirm-cancel").addEventListener("click", () => saveDialog.close());
    document.getElementById("igv-cancel-upload").addEventListener("click", () => uploadController?.abort());
    document.getElementById("igv-confirm-save").addEventListener("click", async () => {
      if (!activePair || uploadController) return;
      const pair = activePair;
      saveDialog.close();
      saveButton.disabled = true;
      savedState.hidden = true;
      saveError.hidden = true;
      uploadProgress.hidden = false;
      uploadMeter.value = 0;
      uploadController = new AbortController();
      const signal = uploadController.signal;
      let token;
      try {
        token = csrfToken();
        let saved;
        if (pair.kind === "local") {
          const totalBytes = pair.dataFile.size + pair.indexFile.size;
          const start = await checkedFetch(`${baseURL}save-sessions/`, {
            method: "POST", signal,
            headers: { "Content-Type": "application/json", "X-CSRFToken": token },
            body: JSON.stringify({ confirmed: true, sampleId, referenceBuild: build,
              role: roleSelect.value, format: pair.format, dataSize: pair.dataFile.size,
              indexSize: pair.indexFile.size }),
          });
          uploadSession = (await start.json()).sessionId;
          await sendChunks(uploadSession, "data", pair.dataFile, totalBytes, 0, signal, token);
          await sendChunks(uploadSession, "index", pair.indexFile, totalBytes, pair.dataFile.size, signal, token);
          const completion = await checkedFetch(`${baseURL}save-sessions/${uploadSession}/complete/`, {
            method: "POST", signal,
            headers: { "Content-Type": "application/json", "X-CSRFToken": token },
            body: JSON.stringify({ referenceBuild: build }),
          });
          saved = await completion.json();
        } else {
          const response = await checkedFetch(`${baseURL}${encodeURIComponent(pair.source.sourceId)}/preserve/`, {
            method: "POST", signal,
            headers: { "Content-Type": "application/json", "X-CSRFToken": token },
            body: JSON.stringify({ confirmed: true }),
          });
          saved = await response.json();
        }
        if (!saved?.sourceId?.startsWith("saved-")) throw new Error("Uventet bekreftelse fra serveren.");
        activePair = { kind: "saved", source: { sourceId: saved.sourceId } };
        localState.hidden = true;
        savedState.hidden = false;
        setStatus("Lagret for senere bruk.");
      } catch (error) {
        if (uploadSession && token) await cancelSession(uploadSession, token);
        saveError.textContent = error.name === "AbortError" ? "Opplasting avbrutt. Filene er ikke lagret."
          : error.message || "Filene er ikke lagret.";
        saveError.hidden = false;
        setStatus("Ikke lagret.");
        saveButton.disabled = false;
      } finally {
        uploadSession = null;
        uploadController = null;
        uploadProgress.hidden = true;
      }
    });
  }
  function closePanel() {
    generation += 1;
    panel.hidden = true;
    if (activeBrowser && igvModule) igvModule.removeBrowser(activeBrowser);
    activeBrowser = null;
    viewer.replaceChildren();
    dataInput.value = "";
    indexInput.value = "";
    localState.hidden = true;
    activePair = null;
    if (saveButton) saveButton.disabled = true;
    if (savedState) savedState.hidden = true;
    if (saveError) saveError.hidden = true;
    setStatus("Velg en variant.");
    launcher?.focus();
  }
  document.getElementById("igv-close").addEventListener("click", closePanel);
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePanel();
  });
}
