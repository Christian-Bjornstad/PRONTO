/* IGV viewer: local Files stay browser-only until explicitly confirmed for preservation. */
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
      throw new Error(`Reference files for ${requestedBuild} are not configured on this server.`);
    }
    return { id: requestedBuild, name: requestedBuild, fastaURL: reference.fastaURL, indexURL: reference.indexURL };
  }

  function selectedLocalPair() {
    const dataFile = dataInput.files[0];
    const indexFile = indexInput.files[0];
    if (!dataFile || !indexFile || !dataFile.size || !indexFile.size) {
      throw new Error("Select a BAM/CRAM file and its index.");
    }
    const format = dataFile.name.toLowerCase().endsWith(".bam") ? "bam" :
      dataFile.name.toLowerCase().endsWith(".cram") ? "cram" : null;
    if (!format || !(format === "bam" ? /\.(bai|csi)$/i : /\.crai$/i).test(indexFile.name)) {
      throw new Error("The file format and index do not match.");
    }
    return { dataFile, indexFile, format };
  }

  async function openPair(track, isLocal, source = null) {
    if (busy || uploadController || !locus) return;
    busy = true;
    const currentGeneration = ++generation;
    const requestedLocus = locus;
    localState.hidden = true;
    if (savedState) savedState.hidden = true;
    if (saveError) saveError.hidden = true;
    if (saveButton) saveButton.disabled = true;
    activePair = null;
    setStatus("Opening IGV …");
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
      setStatus(isLocal ? "Local file opened in IGV. Not saved." : `Registered source opened: ${track.name}.`);
      localState.hidden = !isLocal;
      activePair = isLocal ? { kind: "local", dataFile: track.data, indexFile: track.index, format: track.format }
        : { kind: source.sourceId.startsWith("saved-") ? "saved" : "registered", source };
      if (savedState) savedState.hidden = activePair.kind !== "saved";
      if (saveButton) saveButton.disabled = activePair.kind === "saved";
    } catch (_error) {
      if (currentGeneration === generation) {
        viewer.replaceChildren();
        setStatus(`IGV could not open. ${_error.message || "Check the files and reference."}`);
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
          setStatus(`IGV moved to ${locus}.`);
        } catch (_error) {
          setStatus("IGV could not move to this variant.");
        }
      } else {
        setStatus(document.getElementById("igv-registry-error")
          ? "Registered sources are unavailable. Select local files or contact your administrator."
          : sources.length ? "Select a registered source or local files." : "No registered source. Select local files.");
      }
    });
  });

  for (const source of sources) {
    if (source.referenceBuild !== build || !sameOriginPath(source.dataURL) || !sameOriginPath(source.indexURL)) continue;
    const option = document.createElement("option");
    option.value = source.sourceId;
    option.textContent = `${source.sourceId.startsWith("saved-") ? "Saved · " : ""}${source.role.replaceAll("_", " ")} · ${source.format.toUpperCase()}`;
    select.append(option);
  }
  select.disabled = select.options.length < 2;
  document.getElementById("igv-open-source").addEventListener("click", () => {
    if (uploadController) return;
    const source = sources.find((item) => item.sourceId === select.value && item.referenceBuild === build);
    if (!source || !sameOriginPath(source.dataURL) || !sameOriginPath(source.indexURL)) {
      setStatus("Select a registered source first.");
      return;
    }
    void openPair({ format: source.format, name: source.role, data: source.dataURL, index: source.indexURL }, false, source);
  });
  document.getElementById("igv-open-local").addEventListener("click", () => {
    if (uploadController) return;
    try {
      const pair = selectedLocalPair();
      void openPair({ format: pair.format, name: "Local file", data: pair.dataFile, index: pair.indexFile }, true);
    } catch (error) {
      setStatus(error.message);
    }
  });
  for (const input of [dataInput, indexInput]) {
    input.addEventListener("change", () => {
      if (uploadController) return;
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
      if (!token) throw new Error("CSRF token is missing. Reload the report.");
      return decodeURIComponent(token.slice("csrftoken=".length));
    }

    async function checkedFetch(url, options) {
      const response = await fetch(url, { credentials: "same-origin", cache: "no-store", ...options });
      if (!response.ok) {
        if (response.status === 409) throw new Error("Another file pair is already saved for this sample and role.");
        throw new Error(`Save failed (${response.status}). Files were not saved.`);
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
          activePair.dataFile.size + activePair.indexFile.size).toLocaleString("en-US")} bytes)`
        : `Registered source: ${activePair.source.sourceId}`;
      summary.textContent = `Sample ${sampleId} · ${build} · ${role.replaceAll("_", " ")} · ${details}`;
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
      let finalizationStarted = false;
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
          finalizationStarted = true;
          const completion = await checkedFetch(`${baseURL}save-sessions/${uploadSession}/complete/`, {
            method: "POST", signal,
            headers: { "Content-Type": "application/json", "X-CSRFToken": token },
            body: JSON.stringify({ referenceBuild: build }),
          });
          saved = await completion.json();
        } else {
          finalizationStarted = true;
          const response = await checkedFetch(`${baseURL}${encodeURIComponent(pair.source.sourceId)}/preserve/`, {
            method: "POST", signal,
            headers: { "Content-Type": "application/json", "X-CSRFToken": token },
            body: JSON.stringify({ confirmed: true }),
          });
          saved = await response.json();
        }
        if (!saved?.sourceId?.startsWith("saved-")) throw new Error("Unexpected server response.");
        activePair = { kind: "saved", source: { sourceId: saved.sourceId } };
        localState.hidden = true;
        savedState.hidden = false;
        setStatus("Saved for later use.");
      } catch (error) {
        if (!finalizationStarted && uploadSession && token) await cancelSession(uploadSession, token);
        saveError.textContent = finalizationStarted
          ? "Save status is uncertain. Reload the report and check saved sources before retrying."
          : error.name === "AbortError" ? "Upload cancelled. Files were not saved."
            : error.message || "Files were not saved.";
        saveError.hidden = false;
        setStatus(finalizationStarted ? "Check save status." : "Not saved.");
        saveButton.disabled = false;
      } finally {
        uploadSession = null;
        uploadController = null;
        uploadProgress.hidden = true;
      }
    });
  }
  function closePanel() {
    if (uploadController) return;
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
    setStatus("Select a variant.");
    launcher?.focus();
  }
  document.getElementById("igv-close").addEventListener("click", closePanel);
  panel.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePanel();
  });
}
