/* One live table and one working copy, shared by compact and expanded views. */
window.initReviewV4 = function ({state, changed, busy}) {
  const editing = () => state.status==='DRAFT' && !busy() && document.getElementById('edit-btn')?.getAttribute('aria-pressed')==='true';
  const finding = id => {
    let item=state.findingReviews.find(i=>i.findingId===id);
    if (!item) {item={findingId:id,reportingDecision:'UNREVIEWED',reportHighlight:false};state.findingReviews.push(item);}
    return item;
  };
  function refresh() {
    document.querySelectorAll('[data-source-action],[data-cn-change],[data-v4-edit]').forEach(control=> {
      const row=control.closest('[data-source-id]');
      const item=row ? state.findingReviews.find(i=>i.findingId===row.dataset.sourceId) : null;
      if(control.dataset.sourceAction) control.setAttribute('aria-pressed',String(item?.reportingDecision===control.dataset.sourceAction));
      if(control.dataset.cnChange) control.setAttribute('aria-pressed',String(item?.cnChange===control.dataset.cnChange));
      control.disabled=!editing();
    });
    document.querySelectorAll('[data-section-qc-comment]').forEach(control=> {
      const value=state.sectionQc[control.dataset.sectionQcComment]?.comment || '';
      if(control.value!==value) control.value=value;
    });
  }
  function updateLabel(row) {
    const manual=state.manualCnvRows.find(i=>i.findingId===row.dataset.sourceId);
    if(manual) {
      row.dataset.sourceLabel=`${manual.geneSymbol} · CN ${(Object.hasOwn(manual,'tumorCn')?manual.tumorCn:manual.tumorFc) ?? ''}`;
      row.dataset.sourceSearch=row.dataset.sourceLabel.toLocaleLowerCase();
    }
  }
  function numberValue(control) {
    const text=control.value.trim().replace(',','.');const value=text==='' ? null : Number(text);
    const valid=value===null || Number.isFinite(value) && value>=0 && value<=1e9;
    control.setCustomValidity(valid ? '' : 'Enter a non-negative number.');
    return {valid,value};
  }
  document.addEventListener('input',event=> {
    const control=event.target;
    if(!editing()) return;
    if(control.dataset.sectionQcComment) {
      state.sectionQc[control.dataset.sectionQcComment].comment=control.value;
    } else if(control.hasAttribute('data-rna-comment')) {
      finding(control.closest('tr').dataset.sourceId).comment=control.value;
    } else if(control.dataset.cnField) {
      const item=finding(control.closest('tr').dataset.sourceId);
      if(control.dataset.cnField==='tumorCn') {
        const result=numberValue(control);if(!result.valid) return;
        if(result.value===null) delete item.tumorCn;else item.tumorCn=result.value;
      } else item[control.dataset.cnField]=control.value;
    } else if(control.dataset.manualField) {
      const row=control.closest('tr'); const item=state.manualCnvRows.find(i=>i.findingId===row.dataset.sourceId);
      if(control.dataset.manualField==='Gene_Symbol') item.geneSymbol=control.value;
      else {
        const result=numberValue(control);if(!result.valid) return;
        item[control.dataset.manualField==='Tumor_CN'?'tumorCn':'tumorFc']=result.value;
      }
      updateLabel(row);
    } else return;
    changed();refresh();
  });
  document.addEventListener('click',event=> {
    const control=event.target.closest('[data-source-action],[data-cn-change],[data-add-cnv],[data-remove-cnv],#use-source-defaults,#apply-exclusion-rules');
    if(!control || !editing()) return;
    const row=control.closest('[data-source-id]');
    if(control.dataset.sourceAction) {
      const select=row.querySelector('[data-source-decision]');
      select.value=select.value===control.dataset.sourceAction ? 'UNREVIEWED' : control.dataset.sourceAction;
      select.dispatchEvent(new Event('change',{bubbles:true}));
    } else if(control.dataset.cnChange) {
      const item=finding(row.dataset.sourceId);
      item.cnChange=item.cnChange===control.dataset.cnChange ? 'UNREVIEWED' : control.dataset.cnChange;
    } else if(control.dataset.addCnv) {
      if(state.manualCnvRows.length>=200) {alert('Maximum 200 manual CNV rows.');return;}
      const id='manual-cnv-'+crypto.randomUUID();
      const fresh=document.getElementById('template-'+control.dataset.addCnv).content.firstElementChild.cloneNode(true);
      fresh.querySelectorAll('*').forEach(node=>Array.from(node.attributes).forEach(attr=> {
        if(attr.value.includes('manual-cnv-template')) node.setAttribute(attr.name,attr.value.replaceAll('manual-cnv-template',id));
      }));
      fresh.dataset.sourceId=id;
      fresh.querySelectorAll('input,button').forEach(node=>node.disabled=false);
      state.manualCnvRows.unshift({findingId:id,geneSymbol:'',tumorFc:null,tumorCn:null});
      document.getElementById(control.dataset.addCnv).querySelector('tbody').prepend(fresh);
      fresh.querySelector('[data-manual-field]').focus();
    } else if(control.hasAttribute('data-remove-cnv')) {
      state.manualCnvRows=state.manualCnvRows.filter(i=>i.findingId!==row.dataset.sourceId);
      state.findingReviews=state.findingReviews.filter(i=>i.findingId!==row.dataset.sourceId);row.remove();
    } else if(control.id==='apply-exclusion-rules') {
      const excluded=JSON.parse(document.getElementById('exclusion-defaults').textContent);
      if(!confirm(`Exclude ${excluded.length} variants matching the reporting filters? Other review choices are kept.`)) return;
      excluded.forEach(id=> {
        let item=state.variantReviews.find(i=>i.variantId===id);
        if(!item) {item={variantId:id,clinicalClassification:'UNCLASSIFIED',igvAssessment:'NOT_REVIEWED',reportHighlight:false};state.variantReviews.push(item);}
        item.reportingDecision='EXCLUDE';item.reportHighlight=false;
      });
      document.querySelectorAll('#variant-table select[data-review-field]').forEach(select=> {
        const item=state.variantReviews.find(i=>i.variantId===select.dataset.variantId);
        if(item) select.value=item[select.dataset.reviewField];
      });
    } else {
      if(!confirm('Replace variant Report review and Review choices with source defaults?')) return;
      const defaults=JSON.parse(document.getElementById('source-defaults').textContent);
      state.variantReviews.forEach(item=> {
        const source=defaults[item.variantId];
        if(source) {item.reportingDecision=source.reportingDecision;item.clinicalClassification=source.clinicalClassification;}
      });
      document.querySelectorAll('#variant-table select[data-review-field]').forEach(select=> {
        const item=state.variantReviews.find(i=>i.variantId===select.dataset.variantId);
        if(item) select.value=item[select.dataset.reviewField];
      });
    }
    changed();window.prontoReviewV3?.sync();refresh();
  });
  document.getElementById('edit-btn')?.addEventListener('click',refresh);
  document.addEventListener('pronto-review-changed',refresh);
  refresh();
};

document.addEventListener('DOMContentLoaded',()=> {
  if(!document.querySelector('[data-expand-table]')) return;
  const dialog=document.createElement('dialog');dialog.className='table-focus';dialog.setAttribute('aria-label','Expanded review table');
  dialog.innerHTML='<div class="table-focus-toolbar"><label>Zoom <input type="range" min="75" max="150" step="5" value="100" aria-label="Table zoom"></label><output>100%</output><button type="button" data-zoom-reset>Reset zoom</button><button type="button" data-table-max>Full screen</button><button type="button" data-table-close>Close table</button></div><div class="table-focus-content"></div>';
  document.body.append(dialog);
  const content=dialog.querySelector('.table-focus-content');let moved=[],opener;
  function close() {dialog.close();}
  dialog.addEventListener('close',()=> {
    content.querySelectorAll('table').forEach(table=>table.style.removeProperty('zoom'));
    moved.forEach(([node,marker])=>marker.replaceWith(node));moved=[];
    document.querySelectorAll('[data-expand-table]').forEach(b=>b.hidden=false);opener?.focus();
  });
  document.addEventListener('click',event=> {
    const button=event.target.closest('[data-expand-table]');if(!button) return;
    const table=document.getElementById(button.dataset.expandTable);if(!table) return;
    const workspace=table.closest('.source-table-block') || table.closest('.table-scroll');
    const nodes=[workspace];
    if(table.id==='variant-table') nodes.unshift(document.querySelector('#panel-variant-review .table-toolbar'));
    moved=nodes.filter(Boolean).map(node=> {const marker=document.createComment('table position');node.before(marker);content.append(node);return [node,marker];});
    opener=button;button.hidden=true;dialog.showModal();setZoom(Number(zoom.value));
  });
  dialog.querySelector('[data-table-close]').addEventListener('click',close);
  const zoom=dialog.querySelector('input');
  function freezeIdentity() {
    content.querySelectorAll('table').forEach(table=> {
      let left=0;
      Array.from(table.querySelectorAll('thead th')).forEach((header,index)=> {
        if(!['Gene','Gene_Symbol','Gene_A','Gene_B','Chromosome'].includes(header.textContent.trim())) return;
        table.querySelectorAll('tr').forEach(row=> {const cell=row.children[index];if(cell) {cell.classList.add('frozen-identity');cell.style.left=`${left}px`;}});
        left+=header.getBoundingClientRect().width/(Number(zoom.value)/100);
      });
    });
  }
  function setZoom(value) {
    zoom.value=value;
    content.querySelectorAll('table').forEach(table=>table.style.zoom=String(value/100));
    dialog.querySelector('output').textContent=`${value}%`;freezeIdentity();
  }
  zoom.addEventListener('input',()=>setZoom(Number(zoom.value)));
  dialog.querySelector('[data-zoom-reset]').addEventListener('click',()=>setZoom(100));
  dialog.querySelector('[data-table-max]').addEventListener('click',()=>dialog.classList.toggle('maximized'));
});
