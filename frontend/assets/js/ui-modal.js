(function(window, document){
  'use strict';
  if (window.SMFModal) return;
  const tpl = `
    <div id="smf-modal" class="smf-modal" role="dialog" aria-modal="true" aria-hidden="true" style="display:none">
      <div class="smf-modal-backdrop"></div>
      <div class="smf-modal-panel" role="document" tabindex="-1">
        <header class="smf-modal-header"><h3 id="smf-modal-title"></h3></header>
        <div id="smf-modal-body" class="smf-modal-body"></div>
        <footer class="smf-modal-footer">
          <button id="smf-modal-cancel" class="btn">Cancel</button>
          <button id="smf-modal-confirm" class="btn primary">Confirm</button>
        </footer>
      </div>
    </div>
  `;
  // inject styles
  const css = `
  .smf-modal { position:fixed; inset:0; z-index:2000; display:flex; align-items:center; justify-content:center; }
  .smf-modal-backdrop { position:absolute; inset:0; background:rgba(0,0,0,0.45); }
  .smf-modal-panel { position:relative; background:#fff; border-radius:10px; padding:18px; max-width:520px; width:92%; box-shadow:0 10px 40px rgba(2,8,20,0.35); z-index:2001; }
  .smf-modal-header h3{ margin:0 0 8px 0; font-size:18px }
  .smf-modal-body{ max-height:60vh; overflow:auto; margin-bottom:12px; color:#123 }
  .smf-modal-hero{ display:flex; gap:12px; align-items:flex-start; margin-bottom:12px }
  .smf-modal-hero img{ width:56px; height:56px; object-fit:contain; border-radius:8px; background:#fff; box-shadow:0 1px 3px rgba(0,0,0,0.06) }
  .smf-modal-summary{ color:#445; font-size:13px; margin-top:6px }
  .smf-modal-dates{ display:flex; align-items:center; gap:8px; color:#334; font-size:13px; margin-top:8px }
  .smf-modal-dates::before{ content: ""; display:inline-block; width:18px; height:18px; background-size:18px 18px; background-repeat:no-repeat; background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="%23066" d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.1 0-2 .9-2 2v13c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 15H5V9h14v10zM7 11h5v5H7z"/></svg>'); }
  .smf-modal-panel:focus-within { box-shadow: 0 0 0 4px rgba(3,102,166,0.12); outline: none; }
  .smf-modal-footer button:focus{ outline: 3px solid rgba(3,102,166,0.18); outline-offset:2px }
  .smf-modal-footer{ display:flex; gap:8px; justify-content:flex-end }
  `;
  try{ const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s); }catch(e){}
  // attach DOM
  try{ const div = document.createElement('div'); div.innerHTML = tpl; document.body.appendChild(div.firstElementChild); }catch(e){}

  const modal = document.getElementById('smf-modal');
  const titleEl = document.getElementById('smf-modal-title');
  const bodyEl = document.getElementById('smf-modal-body');
  const cancelBtn = document.getElementById('smf-modal-cancel');
  const confirmBtn = document.getElementById('smf-modal-confirm');
  let resolveCb = null;
  function open(opts){
    if (!modal) return Promise.resolve(false);
    titleEl.textContent = opts && opts.title ? opts.title : '';
    // Build modal body with optional logo and summary
    try{
      const mHtml = (opts && typeof opts.html !== 'undefined') ? String(opts.html) : (opts && opts.text ? String(opts.text) : '');
      const logo = opts && opts.logo ? String(opts.logo) : '';
      const summary = opts && opts.summary ? String(opts.summary) : '';
      let hero = '';
      if (logo){
        // simple img with onerror fallback (hide)
        const esc = function(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); };
        hero = `<div class="smf-modal-hero"><div><img src="${esc(logo)}" alt="" onerror="this.style.display='none'"/></div><div>${mHtml}</div></div>`;
      }
      bodyEl.innerHTML = hero + (hero ? (summary ? `<div class="smf-modal-summary">${summary}</div>` : '') : mHtml);
    }catch(e){ try{ bodyEl.innerHTML = opts && opts.html ? opts.html : (opts && opts.text ? opts.text : ''); }catch(e){ bodyEl.textContent = opts && opts.text ? opts.text : ''; } }
    modal.style.display = 'flex'; modal.setAttribute('aria-hidden','false');
    // focus management
    setTimeout(()=>{ try{ confirmBtn.focus(); }catch(e){} },60);
    return new Promise((resolve)=>{ resolveCb = resolve; });
  }
  function close(result){ if (!modal) return; modal.style.display='none'; modal.setAttribute('aria-hidden','true'); if (resolveCb) { try{ resolveCb(result); }catch(e){} resolveCb = null; } }
  cancelBtn && cancelBtn.addEventListener('click', ()=> close(false));
  confirmBtn && confirmBtn.addEventListener('click', ()=> close(true));
  // keyboard
  document.addEventListener('keydown', function(e){ if (!modal || modal.style.display==='none') return; if (e.key === 'Escape') { e.preventDefault(); close(false); } if (e.key === 'Enter') { /* let buttons handle it */ } });
  window.SMFModal = { open: open, close: close };
})(window, document);
