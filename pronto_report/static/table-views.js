/* Change visibility on the original table: inputs, sorting and search stay shared. */
(() => {
  const managed=new WeakMap();let sequence=0;
  const normalize=text=>text.trim().toLocaleLowerCase().replace(/[^a-z0-9]/g,'');
  const common=new Set(['reportreview','reporthighlight','includexclude','keyrelevantfindings','review','report','exclude',
    'reviewnote','manualqc','sourceqchighlight','igvqc','reviewcomment','igv']);
  const cnv=new Set(['genesymbol','genename','chromosome','cytoband','tumorcn','tumorfc','adjustedtumorcn','cngainloss','highconfidencegene']);
  const rna=new Set(['genea','geneb','provisionaleventtype','eventid','exona','exonb','eventsupportdeduppercentage','qcverdict']);
  const shortLabels={genesymbol:'Gene',genename:'Gene',chromosome:'Chr',tumorcn:'Tumour CN',tumorfc:'Tumour FC',
    adjustedtumorcn:'Adjusted CN',highconfidencegene:'High confidence',genea:'Gene A',geneb:'Gene B',
    provisionaleventtype:'Event',eventid:'Event ID',exona:'Exon / intron A',exonb:'Exon / intron B',
    eventsupportdeduppercentage:'Read support (%)',qcverdict:'Source QC'};
  function enhance(table) {
    if(managed.has(table) || !table.tHead || table.closest('template')) return;
    const headers=Array.from(table.tHead.rows[0]?.cells || []);
    // Grouped headings and merged cells do not have a one-to-one column mapping.
    if(!headers.length || table.tHead.rows.length!==1 || headers.some(cell=>cell.colSpan!==1 || cell.rowSpan!==1)) return;
    const kind=table.querySelector('[data-source-kind]')?.dataset.sourceKind;
    const originalLabels=headers.map(header=>header.textContent);
    const secondary=headers.map((header,index)=>{
      const label=normalize(header.textContent);
      if(common.has(label) || !label) return false;
      if(table.id==='variant-table') return index>=7 || label==='oncokb';
      if(kind==='CNV') return !cnv.has(label);
      if(kind==='RNA') return !rna.has(label);
      // Summary and report-field tables already have a concise, purposeful set.
      return table.classList.contains('presentation-editor') || headers.length<=12 ? false : index>=8;
    });
    if(!table.id) table.id=`report-table-${++sequence}`;
    const toolbar=document.createElement('div');toolbar.className='table-view-controls';
    toolbar.setAttribute('role','group');toolbar.setAttribute('aria-label','Table columns');
    const buttons=['Table','Full table'].map((text,index)=>{
      const button=document.createElement('button');button.type='button';button.textContent=text;
      button.dataset.tableView=index?'full':'compact';button.setAttribute('aria-controls',table.id);
      toolbar.append(button);return button;
    });
    const status=document.createElement('span');status.className='table-view-count';status.setAttribute('role','status');toolbar.append(status);
    let workspace=table.closest('.source-table-block');
    if(!workspace) {
      let scroll=table.closest('.table-scroll');
      if(!scroll) {
        scroll=document.createElement('div');scroll.className='table-scroll';scroll.tabIndex=0;
        scroll.setAttribute('role','region');scroll.setAttribute('aria-label','Report table');
        table.before(scroll);scroll.append(table);
      }
      workspace=document.createElement('div');workspace.className='table-view-workspace';
      scroll.before(workspace);workspace.append(scroll);
    }
    workspace.prepend(toolbar);
    function mark(row) {
      // Detail/description rows span the table and must remain visible in both views.
      if(row.cells.length!==headers.length || Array.from(row.cells).some(cell=>cell.colSpan!==1)) return;
      Array.from(row.cells).forEach((cell,index)=>cell.classList.toggle('table-column-secondary',secondary[index]));
    }
    function setMode(mode) {
      table.dataset.tableView=mode;table.classList.toggle('table-mode-compact',mode==='compact');
      buttons.forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.tableView===mode)));
      const count=mode==='compact'?secondary.filter(value=>!value).length:headers.length;
      status.textContent=`${count} of ${headers.length} columns`;
      if(kind==='CNV' || kind==='RNA') headers.forEach((header,index)=>{
        header.textContent=mode==='compact'?(shortLabels[normalize(originalLabels[index])] || originalLabels[index]):originalLabels[index];
      });
      table.dispatchEvent(new CustomEvent('pronto-table-view',{bubbles:true}));
    }
    Array.from(table.rows).forEach(mark);
    const columns=Array.from(table.querySelectorAll(':scope > colgroup > col'));
    if(columns.length===headers.length) columns.forEach((col,index)=>col.classList.toggle('table-column-secondary',secondary[index]));
    managed.set(table,{mark});buttons.forEach(button=>button.addEventListener('click',()=>setMode(button.dataset.tableView)));
    // A validation error in a hidden technical column must become reachable.
    table.addEventListener('invalid',()=>setMode('full'),true);
    setMode('compact');
  }
  function added(node) {
    if(node.nodeType!==Node.ELEMENT_NODE) return;
    if(node.matches('table')) enhance(node);
    node.querySelectorAll('table').forEach(enhance);
    const table=node.closest('table');const entry=table && managed.get(table);
    if(entry) {
      if(node.matches('tr')) entry.mark(node);
      node.querySelectorAll('tr').forEach(entry.mark);
    }
  }
  function init() {
    document.querySelectorAll('table').forEach(enhance);
    new MutationObserver(changes=>changes.forEach(change=>change.addedNodes.forEach(added)))
      .observe(document.body,{childList:true,subtree:true});
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init);else init();
})();
