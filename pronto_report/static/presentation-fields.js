/* Human-entered MolMDT annotations are saved with the finding's review. */
window.initPresentationFields = function ({state, changed, busy}) {
  const root=document.getElementById('presentation-annotations');
  if (!root) return;
  const labels={status:'Status',functionalEffect:'GoF / LoF',sensitive:'Sensitive',resistant:'Resistant',
    emaTumour:'EMA — patient’s tumour type',emaOther:'EMA — other tumour type',description:'Variant description'};
  const editing=()=>state.status==='DRAFT' && root.dataset.readonly!=='true'
    && document.getElementById('edit-btn')?.getAttribute('aria-pressed')==='true';
  function selected() {
    return [...state.biomarkerReviews.filter(item=>item.reportHighlight).map(item=>['metric',item.metricId,item]),
      ...state.findingReviews.filter(item=>item.reportHighlight && item.reportingDecision==='INCLUDE').map(item=>['finding',item.findingId,item]),
      ...state.variantReviews.filter(item=>item.reportHighlight && item.reportingDecision==='INCLUDE').map(item=>['variant',item.variantId,item])];
  }
  function label(kind,id) {
    if(kind==='metric') return id.toUpperCase();
    const row=Array.from(document.querySelectorAll('[data-source-id]')).find(row=>row.dataset.sourceId===id)
      || Array.from(document.querySelectorAll('#key-variant-table [data-variant-id]')).find(row=>row.dataset.variantId===id);
    return row?.dataset.sourceLabel || row?.cells?.[0]?.textContent?.trim() || id;
  }
  function sync() {
    const entries=selected();
    const key=entries.map(([kind,id])=>kind+':'+id).join('|');
    if(root.dataset.items!==key) {
      root.replaceChildren();root.dataset.items=key;
      if(!entries.length) {const empty=document.createElement('p');empty.textContent='No highlights selected.';root.append(empty);}
      entries.forEach(([kind,id])=>{
        const group=document.createElement('fieldset');group.className='presentation-annotation';
        const legend=document.createElement('legend');legend.textContent=label(kind,id);group.append(legend);
        const grid=document.createElement('div');grid.className='presentation-annotation__fields';group.append(grid);
        Object.entries(labels).filter(([field])=>kind==='metric' || field!=='status').forEach(([field,title])=>{
          const wrapper=document.createElement('label');wrapper.textContent=title;
          const input=document.createElement(field==='description'?'textarea':'input');input.dataset.presentationField=field;
          input.dataset.presentationKind=kind;input.dataset.presentationId=id;
          input.maxLength=field==='description'?50000:2000;input.disabled=root.dataset.readonly==='true';
          if(field==='description') {input.rows=3;wrapper.className='presentation-annotation__description';}
          wrapper.append(input);grid.append(wrapper);
        });root.append(group);
      });
    }
    root.querySelectorAll('[data-presentation-field]').forEach(input=>{
      input.disabled=!editing() || busy();
      const entry=entries.find(([kind,id])=>kind===input.dataset.presentationKind && id===input.dataset.presentationId);
      const value=entry?.[2].presentation?.[input.dataset.presentationField] || '';
      if(input!==document.activeElement && input.value!==value) input.value=value;
    });
  }
  root.addEventListener('input',event=>{
    const input=event.target.closest('[data-presentation-field]');
    if(!input || !editing() || busy()) return;
    const entry=selected().find(([kind,id])=>kind===input.dataset.presentationKind && id===input.dataset.presentationId);
    if(!entry) return;
    entry[2].presentation ??= {};entry[2].presentation[input.dataset.presentationField]=input.value;changed();
  });
  document.addEventListener('pronto-review-changed',sync);sync();
  document.getElementById('edit-btn')?.addEventListener('click',sync);
};
