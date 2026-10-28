/* Explicit report text overrides; source values and annotations remain intact. */
window.initPresentationFields = function ({state, changed, busy}) {
  const root=document.getElementById('presentation-annotations');
  if (!root) return;
  const sources=JSON.parse(document.getElementById('presentation-source-data')?.textContent || '{}');
  const labels={displayName:'Gene / molecular marker',alteration:'Alteration',effect:'Effect / event',
    value:'VAF / CN / score',functionalEffect:'GoF / LoF',sensitive:'Sensitive',resistant:'Resistant',
    emaTumour:'EMA — patient’s tumour type',emaOther:'EMA — other tumour type'};
  const editing=()=>state.status==='DRAFT' && root.dataset.readonly!=='true'
    && document.getElementById('edit-btn')?.getAttribute('aria-pressed')==='true';
  function selected() {
    return [...state.biomarkerReviews.filter(item=>item.reportHighlight).map(item=>['metric',item.metricId,item]),
      ...state.findingReviews.filter(item=>item.reportHighlight && item.reportingDecision==='INCLUDE').map(item=>['finding',item.findingId,item]),
      ...state.variantReviews.filter(item=>item.reportHighlight && item.reportingDecision==='INCLUDE').map(item=>['variant',item.variantId,item])];
  }
  function activity(kind,id,create=false) {
    const entries=kind==='metric'?state.biomarkerReviews:kind==='finding'?state.findingReviews:state.variantReviews;
    const field=kind==='metric'?'metricId':kind==='finding'?'findingId':'variantId';
    let item=entries.find(entry=>entry[field]===id);
    if(!item && create && kind==='metric') {item={metricId:id,reportHighlight:false};entries.push(item);}
    return item;
  }
  function source(kind,id) {
    const value={...(sources[id] || {})};
    const manual=state.manualCnvRows?.find(item=>item.findingId===id);
    const review=activity(kind,id);
    if(manual) Object.assign(value,{label:manual.geneSymbol,alteration:'CNV',value:Object.hasOwn(manual,'tumorCn')?manual.tumorCn:manual.tumorFc});
    if(review?.cnChange) value.effect=review.cnChange==='UNREVIEWED'?'':review.cnChange;
    if(review?.tumorCn!==undefined && review.tumorCn!==null) value.value=review.tumorCn;
    return value;
  }
  function control(field,kind,id,title,placeholder='') {
    const input=document.createElement(['description','functionalEffect','sensitive','resistant','emaTumour','emaOther'].includes(field)?'textarea':'input');
    input.dataset.presentationField=field;input.dataset.presentationKind=kind;input.dataset.presentationId=id;
    input.setAttribute('aria-label',title);input.placeholder=placeholder || '';
    input.maxLength=field==='description'?50000:2000;
    if(input.tagName==='TEXTAREA') input.rows=field==='description'?3:2;
    return input;
  }
  function sync() {
    const entries=selected();
    const key=entries.map(([kind,id])=>kind+':'+id).join('|');
    if(root.dataset.items!==key) {
      root.replaceChildren();root.dataset.items=key;
      const signatures=document.createElement('fieldset');signatures.className='signature-status-fields';
      const legend=document.createElement('legend');legend.textContent='Mutational signature status';signatures.append(legend);
      Object.entries(sources).filter(([,item])=>item.kind==='metric').forEach(([id,item])=>{
        const label=document.createElement('label');label.textContent=item.label;
        label.append(control('status','metric',id,item.label+' status'));signatures.append(label);
      });root.append(signatures);
      if(!entries.length) {
        const empty=document.createElement('p');empty.textContent='Select “Key relevant findings” on the findings to add report rows.';root.append(empty);
      } else {
        const scroll=document.createElement('div');scroll.className='table-scroll';scroll.tabIndex=0;
        scroll.setAttribute('role','region');scroll.setAttribute('aria-label','Edit key relevant findings');
        const table=document.createElement('table');table.className='presentation-editor';
        const head=table.createTHead().insertRow();
        Object.values(labels).forEach(title=>{const th=document.createElement('th');th.scope='col';th.textContent=title;head.append(th);});
        const body=table.createTBody();
        entries.forEach(([kind,id])=>{
          const data=source(kind,id),row=body.insertRow();
          Object.entries(labels).forEach(([field,title])=>{
            const cell=row.insertCell();
            if(field==='value') {cell.dataset.presentationValue=id;cell.dataset.kind=kind;}
            else cell.append(control(field,kind,id,`${data.label || id}: ${title}`,data[field==='displayName'?'label':field]));
          });
          const description=body.insertRow().insertCell();description.colSpan=9;description.className='presentation-editor__description';
          const label=document.createElement('label');label.textContent='Variant description';
          label.append(control('description',kind,id,`${data.label || id}: Variant description`));description.append(label);
        });scroll.append(table);root.append(scroll);
      }
    }
    root.querySelectorAll('[data-presentation-field]').forEach(input=>{
      input.disabled=!editing() || busy();
      const kind=input.dataset.presentationKind,id=input.dataset.presentationId,field=input.dataset.presentationField;
      const data=source(kind,id),value=activity(kind,id)?.presentation?.[field] || '';
      input.placeholder=data[field==='displayName'?'label':field] || '';
      if(input!==document.activeElement && input.value!==value) input.value=value;
    });
    root.querySelectorAll('[data-presentation-value]').forEach(cell=>{
      const value=source(cell.dataset.kind,cell.dataset.presentationValue).value;
      cell.textContent=value===null || value===undefined || value===''?'—':String(value);
    });
  }
  root.addEventListener('input',event=>{
    const input=event.target.closest('[data-presentation-field]');
    if(!input || !editing() || busy()) return;
    const entry=activity(input.dataset.presentationKind,input.dataset.presentationId,true);
    if(!entry) return;
    entry.presentation ??= {};entry.presentation[input.dataset.presentationField]=input.value;changed();
  });
  document.addEventListener('pronto-review-changed',sync);sync();
  document.getElementById('edit-btn')?.addEventListener('click',sync);
};
