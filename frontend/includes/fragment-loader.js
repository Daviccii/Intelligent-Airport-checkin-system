/* fragment-loader.js
   Loads header/footer fragments and injects font/favicon into head.
*/
async function loadFragment(path){
  try{
    const res = await fetch(path);
    if (!res.ok) return null;
    return await res.text();
  }catch(e){ console.warn('fragment load failed', path, e); return null; }
}

document.addEventListener('DOMContentLoaded', async ()=>{
  // inject font + favicon if not present
  if (!document.querySelector('link[href*="fonts.googleapis.com"]')){
    const lf = document.createElement('link'); lf.rel='stylesheet'; lf.href='https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap'; document.head.appendChild(lf);
  }
  if (!document.querySelector('link[rel="icon"][href$="favicon.svg"]')){
    const f = document.createElement('link'); f.rel='icon'; f.href='/frontend/favicon.svg'; f.type='image/svg+xml'; document.head.appendChild(f);
  }

  // header
  if (!document.querySelector('.main-nav')){
    const headerHTML = await loadFragment('/frontend/includes/header.html');
    if (headerHTML) document.body.insertAdjacentHTML('afterbegin', headerHTML);
  }
  // footer
  if (!document.querySelector('footer')){
    const footerHTML = await loadFragment('/frontend/includes/footer.html');
    if (footerHTML) document.body.insertAdjacentHTML('beforeend', footerHTML);
  }

  // wire theme toggle inside fragment (if present)
  const btn = document.getElementById('theme-toggle-frag') || document.getElementById('theme-toggle');
  if (btn){
    btn.addEventListener('click', (e)=>{ e.preventDefault(); const cur = document.body.classList.contains('dark') ? 'dark' : 'light'; const next = cur === 'dark' ? 'light' : 'dark'; if (next==='dark') document.body.classList.add('dark'); else document.body.classList.remove('dark'); localStorage.setItem('smartfly-theme', next); });
  }
});
