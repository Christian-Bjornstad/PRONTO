  document.addEventListener('click', (event) => {
    const view=event.target.closest('[data-cnv-view]');
    if (view) {
      document.getElementById('cnv-table-view').hidden=view.dataset.cnvView !== 'table';
      document.getElementById('cnv-plots-view').hidden=view.dataset.cnvView !== 'plots';
      document.querySelectorAll('[data-cnv-view]').forEach((b) => b.setAttribute('aria-pressed',String(b===view)));
    }
    const plot=event.target.closest('[data-v3-plot]');
    if (plot) {
      document.querySelectorAll('.cnv-slide').forEach((slide) => {slide.hidden=slide.id !== plot.dataset.v3Plot;});
      document.querySelectorAll('[data-v3-plot]').forEach((b) => b.setAttribute('aria-pressed',String(b===plot)));
    }
  });
/* Linked controls for one versioned working copy; persistence remains explicit. */
window.initReviewV3 = function (api) {
  const {state, activityFor, changed, busy, setExporting, isDirty} = api;
  if (state.schemaVersion !== '3.0') return;
  function findingFor(id) {
    let item = state.findingReviews.find((value) => value.findingId === id);
    if (!item) { item = {findingId:id, reportingDecision:'UNREVIEWED', reportHighlight:false}; state.findingReviews.push(item); }
    return item;
  }
  function sourceActivity(row) {
    return row.dataset.sourceKind === 'VARIANTS' ? activityFor(row.dataset.sourceId) : findingFor(row.dataset.sourceId);
  }
  function sync() {
    const activities = new Map(state.variantReviews.map((item) => [item.variantId,item]));
    document.querySelectorAll('[data-vus-variant], [data-highlight-variant], [data-exclude-variant]').forEach((control) => {
      const id = control.dataset.vusVariant || control.dataset.highlightVariant || control.dataset.excludeVariant;
      const item = activities.get(id) || {};
      control.checked = control.hasAttribute('data-vus-variant') ? item.clinicalClassification === 'VUS'
        : control.hasAttribute('data-exclude-variant') ? item.reportingDecision === 'EXCLUDE' : !!item.reportHighlight;
    });
    document.querySelectorAll('#variant-table tr[data-occurrence-id], #key-variant-table tr[data-variant-id]').forEach((row) => {
      const id = row.dataset.variantId || row.querySelector('[data-variant-id]')?.dataset.variantId;
      row.classList.toggle('excluded-row', activities.get(id)?.reportingDecision === 'EXCLUDE');
    });
    document.querySelectorAll('tr[data-source-id]').forEach((row) => {
      const item = (row.dataset.sourceKind === 'VARIANTS' ? activities.get(row.dataset.sourceId)
        : state.findingReviews.find((value) => value.findingId === row.dataset.sourceId)) || {};
      row.querySelector('[data-source-decision]').value = item.reportingDecision || 'UNREVIEWED';
      row.querySelector('[data-source-highlight]').checked = !!item.reportHighlight;
      row.classList.toggle('excluded-row', item.reportingDecision === 'EXCLUDE');
    });
    document.querySelectorAll('[data-section-qc]').forEach((control) => {
      const assessment = control.dataset.sectionQc === 'overall' ? state.runQcAssessment : state.sectionQc[control.dataset.sectionQc];
      control.value = assessment.status;
      control.closest('.section-qc').dataset.qcStatus = assessment.status;
    });
    document.querySelectorAll('[data-metric-highlight]').forEach((control) => {
      control.checked = !!state.biomarkerReviews.find((item) => item.metricId === control.dataset.metricHighlight)?.reportHighlight;
    });
    const list = document.getElementById('v3-key-findings');
    if (list) {
      list.replaceChildren();
      state.variantReviews.filter((item) => item.reportingDecision === 'INCLUDE' && item.reportHighlight).forEach((item) => {
        const row = Array.from(document.querySelectorAll('#key-variant-table tr[data-variant-id]')).find((r) => r.dataset.variantId === item.variantId)
          || Array.from(document.querySelectorAll('#variant-table tr[data-occurrence-id]')).find((r) => r.querySelector('[data-variant-id]')?.dataset.variantId === item.variantId);
        const node = document.createElement('li'); node.textContent = `${row?.cells[0]?.textContent || item.variantId} · ${row?.cells[1]?.textContent || ''} · ${item.clinicalClassification}`; list.append(node);
      });
      const seen = new Set();
      const sourceList=document.getElementById('v3-source-findings');sourceList.replaceChildren();
      document.querySelectorAll('tr[data-source-id]').forEach((row) => {
        if (row.dataset.sourceKind === 'VARIANTS' || seen.has(row.dataset.sourceId)) return;
        const item = state.findingReviews.find((a) => a.findingId === row.dataset.sourceId);
        if (item?.reportingDecision !== 'INCLUDE') return;
        seen.add(row.dataset.sourceId);
        const node=document.createElement('li');node.textContent=`${row.dataset.sourceKind} · ${row.dataset.sourceLabel}`;sourceList.append(node);
        if(item.reportHighlight) list.append(node.cloneNode(true));
      });
      document.getElementById('v3-source-empty').hidden=sourceList.children.length>0;
      state.biomarkerReviews.filter((item) => item.reportHighlight).forEach((item) => {
        const card=document.querySelector(`[data-metric="${item.metricId}"]`);
        const node=document.createElement('li');node.textContent=`${item.metricId.toUpperCase()} · ${card?.querySelector('.metric-card__value')?.textContent || 'Not provided'}`;list.append(node);
      });
      document.getElementById('v3-key-empty').hidden = list.children.length > 0;
    }
  }
  document.addEventListener('pronto-review-changed', sync);
  document.addEventListener('change', (event) => {
    if (state.status !== 'DRAFT' || busy()) return;
    const control = event.target;
    const variantId = control.dataset.vusVariant || control.dataset.highlightVariant || control.dataset.excludeVariant;
    if (variantId) {
      const item=activityFor(variantId);
      if (control.dataset.vusVariant) item.clinicalClassification=control.checked ? 'VUS' : 'UNCLASSIFIED';
      else if (control.dataset.excludeVariant) item.reportingDecision=control.checked ? 'EXCLUDE' : 'UNREVIEWED';
      else item.reportHighlight=control.checked;
      document.querySelectorAll('#variant-table select[data-variant-id]').forEach((peer) => {
        if (peer.dataset.variantId === variantId) peer.value = item[peer.dataset.reviewField];
      });
    } else if (control.dataset.sourceDecision || control.dataset.sourceHighlight) {
      const row=control.closest('[data-source-id]');const item=sourceActivity(row);
      if (control.dataset.sourceDecision) item.reportingDecision=control.value;
      else item.reportHighlight=control.checked;
      if (row.dataset.sourceKind === 'VARIANTS') document.querySelectorAll('#variant-table select[data-variant-id]').forEach((peer) => {
        if (peer.dataset.variantId === row.dataset.sourceId) peer.value=item[peer.dataset.reviewField];
      });
    } else if (control.dataset.sectionQc) {
      const section=control.dataset.sectionQc;
      (section === 'overall' ? state.runQcAssessment : state.sectionQc[section]).status=control.value;
      if (section === 'overall') document.getElementById('qc-review-status').value=control.value;
    } else if (control.dataset.metricHighlight) {
      let item=state.biomarkerReviews.find((a) => a.metricId === control.dataset.metricHighlight);
      if (!item) {item={metricId:control.dataset.metricHighlight,reportHighlight:false};state.biomarkerReviews.push(item);}
      item.reportHighlight=control.checked;
    } else if (control.id !== 'qc-review-status') return;
    changed(); sync();
  });
  document.querySelectorAll('[data-source-search-for]').forEach((input) => input.addEventListener('input', () => {
    document.getElementById(input.dataset.sourceSearchFor).querySelectorAll('tbody tr').forEach((row) => {
      row.hidden = !row.dataset.sourceSearch.includes(input.value.toLocaleLowerCase());
    });
  }));
  sync();
  window.prontoReviewV3 = {state, changed, busy, setExporting, isDirty, sync};
  const figureList=document.getElementById('figure-list');
  const upload=document.getElementById('figure-upload');
  const figureStatus=document.getElementById('figure-upload-status');
  const figureURLs=new Map(Array.from(figureList?.querySelectorAll('[data-figure-card]') || []).map((card) => [card.dataset.figureCard,card.querySelector('img').src]));
  function renderFigures() {
    if (!figureList || state.status !== 'DRAFT' || !upload || busy()) return;
    const cards=Array.from(figureList.querySelectorAll('[data-figure-card]'));
    if(cards.length===state.presentationFigures.length && cards.every((card,index) =>
      card.dataset.figureCard===state.presentationFigures[index].figureId &&
      card.querySelector('textarea')?.value===state.presentationFigures[index].caption)) return;
    figureList.replaceChildren();
    state.presentationFigures.forEach((figure,index) => {
      const card=document.createElement('div');card.className='presentation-figure-card';card.dataset.figureCard=figure.figureId;
      const preview=document.createElement('img');preview.src=figureURLs.get(figure.figureId) || '';preview.alt=`Presentation figure ${index+1}`;
      const label=document.createElement('label');label.textContent=`Figure ${index+1} caption`;
      const caption=document.createElement('textarea');caption.maxLength=2000;caption.value=figure.caption;caption.dataset.figureEdit='';
      caption.addEventListener('input',() => {
        if(busy() || state.status!=='DRAFT') return;
        const current=state.presentationFigures.find((item) => item.figureId===figure.figureId);
        if(current) {current.caption=caption.value;changed();}
      });label.append(caption);
      card.append(preview,label);
      for (const [action,text] of [['up','Move up'],['down','Move down'],['remove','Remove']]) {
        const button=document.createElement('button');button.type='button';button.textContent=text;button.dataset.figureEdit='';
        button.disabled=(action==='up' && index===0) || (action==='down' && index===state.presentationFigures.length-1);
        button.setAttribute('aria-label',`${text} figure ${index+1}`);
        button.addEventListener('click',() => {
          if (busy()) return;
          const current=state.presentationFigures.findIndex((f) => f.figureId===figure.figureId);
          if (action==='remove') state.presentationFigures.splice(current,1);
          else {const next=current+(action==='up'?-1:1);[state.presentationFigures[current],state.presentationFigures[next]]=[state.presentationFigures[next],state.presentationFigures[current]];}
          changed();renderFigures();
        });card.append(button);
      }figureList.append(card);
    });
  }
  upload?.addEventListener('change',async () => {
    if(busy() || state.status!=='DRAFT') return;
    const files=Array.from(upload.files);if(!files.length) return;
    if(state.presentationFigures.length+files.length>30 || files.some((file) => file.size>8*1024*1024)) {
      figureStatus.textContent='Select up to 30 figures, no larger than 8 MB each.';upload.value='';return;
    }
    setExporting(true);
    try {
      for (const file of files) {
        figureStatus.textContent=`Uploading ${file.name}…`;
        const body=new FormData();body.append('image',file);
        const response=await fetch(upload.dataset.uploadUrl,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':upload.dataset.csrf},body});
        if(!response.ok) throw new Error('Image upload failed. Use PNG, JPEG or WebP within the size limit.');
        const result=await response.json();
        if(!result.figureId || !result.url?.startsWith('/reports/')) throw new Error('Invalid upload response.');
        figureURLs.set(result.figureId,result.url);
        state.presentationFigures.push({figureId:result.figureId,caption:file.name.replace(/\.[^.]+$/,'')});
        changed();renderFigures();
      }figureStatus.textContent='Figures added. Save to include them in the presentation PDF.';
    } catch(error) {figureStatus.textContent=error.message;}
    finally {upload.value='';setExporting(false);renderFigures();}
  });
  document.addEventListener('pronto-review-changed',renderFigures);
  renderFigures();
  let pendingPdf=null;
  document.querySelectorAll('[data-pdf-layout]').forEach((button) => button.addEventListener('click',async () => {
    const status=document.getElementById('pdf-export-status');
    if(busy()) return;
    if(isDirty()) {status.textContent='Save changes before exporting a PDF.';return;}
    setExporting(true);
    try {
      const initials=await window.requestDeclaredInitials('Initials for PDF export');
      if(initials===null) return;
      const layout=button.dataset.pdfLayout;
      if(!pendingPdf || pendingPdf.revision!==state.revision || pendingPdf.layout!==layout || pendingPdf.declaredInitials!==initials) {
        pendingPdf={schemaVersion:'1.0',reportId:state.reportId,revision:state.revision,layout,declaredInitials:initials,requestId:crypto.randomUUID()};
      }
      status.textContent='Preparing saved PDF…';
      const response=await fetch(button.dataset.pdfUrl,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':button.dataset.csrf},body:JSON.stringify(pendingPdf)});
      if(!response.ok || !response.headers.get('Content-Type')?.startsWith('application/pdf')) throw new Error(response.status===409?'Saved version changed. Reload the latest report.':'PDF export could not be completed. Try again.');
      const blob=await response.blob();const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;
      link.download=`InPreD-${state.reportId.replace(/[^A-Za-z0-9_-]/g,'-')}-r${state.revision}-${layout.toLowerCase()}.pdf`;
      document.body.append(link);link.click();link.remove();setTimeout(() => URL.revokeObjectURL(url),30000);
      status.textContent=`${layout==='ESMO'?'ESMO':'Presentation'} PDF exported from saved revision ${state.revision}.`;pendingPdf=null;
    }catch(error){status.textContent=error.message;}
    finally{setExporting(false);}
  }));
};
