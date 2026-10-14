document.getElementById('start-new-revision')?.addEventListener('click',async()=> {
  const config=JSON.parse(document.getElementById('working-config').textContent);
  const active=window.prontoWorkingConfig || config;
  if(window.prontoReviewV3?.isDirty() && !confirm('Discard unsaved changes and start from the selected saved report?')) return;
  if(active.version && !confirm('Replace the active working draft with a new revision?')) return;
  const button=document.getElementById('start-new-revision');button.disabled=true;
  const message=document.getElementById('working-message');
  try {
    const response=await fetch(config.url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':config.csrf},body:JSON.stringify({
      schemaVersion:'2.0',reportId:config.reportId,action:'REOPEN',baseRevision:active.revision,
      expectedVersion:active.version,sourceRevision:active.sourceRevision,replaceWorking:true})});
    if(!response.ok) throw new Error(response.status===409 ? 'Working draft changed. Reload before starting a revision.' : 'Could not start a new revision.');
    location.href=config.url.replace('working/','');
  } catch(error) {message.textContent=error.message;button.disabled=false;}
});
