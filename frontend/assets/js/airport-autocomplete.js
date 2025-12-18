(function(global){
  'use strict';

  const SUGG_MAX = 80;
  let __airports = null;
  let __geo = null; // { lat, lon }

  async function loadAirports(){
    if (__airports) return __airports;
    try{
      const res = await fetch('/assets/data/airports.json');
      const data = await res.json();
      __airports = Array.isArray(data) ? data.map(a => ({
        code: (a.code || a.iata || '').toUpperCase(),
        name: a.name || a.airport || '',
        city: a.city || '',
        country: a.country || '',
        lat: a.lat, lon: a.lon
      })).filter(a => a.code && (typeof a.lat === 'number') && (typeof a.lon === 'number')) : [];
    }catch(e){ __airports = []; }
    return __airports;
  }

  function haversine(lat1, lon1, lat2, lon2){
    const R = 6371; // km
    const toRad = d => d * Math.PI / 180;
    const dLat = toRad(lat2-lat1);
    const dLon = toRad(lon2-lon1);
    const a = Math.sin(dLat/2)**2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2)**2;
    return Math.round(R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
  }

  function findNearestAirport(lat, lon){
    if (!__airports || !__airports.length) return null;
    let best = null, bestD = Infinity;
    for (const a of __airports){
      const d = haversine(lat, lon, a.lat, a.lon);
      if (d < bestD){ bestD = d; best = a; }
    }
    if (best) best._distanceKm = bestD;
    return best;
  }

  function ensureWrapper(input){
    if (!input) return null;
    if (input.parentElement && input.parentElement.classList.contains('airport-field')) return input.parentElement;
    const wrap = document.createElement('div');
    wrap.className = 'airport-field';
    input.parentElement.insertBefore(wrap, input);
    wrap.appendChild(input);
    return wrap;
  }

  function buildPanel(){
    const el = document.createElement('div');
    el.className = 'airport-sugg';
    el.setAttribute('role', 'listbox');
    el.style.display = 'none';
    return el;
  }

  function renderItems(panel, items, nearest){
    panel.innerHTML = '';
    const list = items.slice(0, SUGG_MAX);
    const frag = document.createDocumentFragment();

    // If nearest present, put it first with highlight and then all airports filtered
    if (nearest){
      const n = renderItem(nearest, true);
      frag.appendChild(n);
    }
    list.forEach(a => {
      if (nearest && a.code === nearest.code) return; // avoid duplicate
      frag.appendChild(renderItem(a, false));
    });

    panel.appendChild(frag);
    panel.style.display = list.length || nearest ? 'block' : 'none';
  }

  function renderItem(a, isNearest){
    const div = document.createElement('div');
    div.className = 'item' + (isNearest ? ' nearest' : '');
    div.setAttribute('role','option');
    div.dataset.code = a.code;
    div.dataset.city = a.city || '';
    div.dataset.name = a.name || '';

    const code = document.createElement('div'); code.className = 'code'; code.textContent = a.code;
    const meta = document.createElement('div'); meta.className = 'meta';
    const city = document.createElement('div'); city.className = 'city'; city.textContent = a.city || a.country || '';
    const name = document.createElement('div'); name.className = 'name'; name.textContent = a.name || '';
    meta.appendChild(city); meta.appendChild(name);

    div.appendChild(code);
    div.appendChild(meta);

    if (isNearest){
      const badge = document.createElement('div'); badge.className = 'badge'; badge.textContent = 'Nearest';
      div.appendChild(badge);
    }
    return div;
  }

  function buildFilter(query){
    const q = (query||'').trim().toLowerCase();
    if (!q) return (a) => true;
    return (a) => a.code.toLowerCase().startsWith(q) ||
                  (a.city||'').toLowerCase().includes(q) ||
                  (a.name||'').toLowerCase().includes(q);
  }

  async function attach(selector){
    await loadAirports();

    const input = (typeof selector === 'string') ? document.querySelector(selector) : selector;
    if (!input) return;

    const wrap = ensureWrapper(input);
    const panel = buildPanel();
    wrap.appendChild(panel);

    let selectedIndex = -1;
    let current = [];
    let nearest = null;

    // Fetch geolocation once per page
    if (!__geo && navigator.geolocation){
      try{
        navigator.geolocation.getCurrentPosition((pos)=>{
          __geo = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        }, ()=>{ __geo = null; }, { enableHighAccuracy: true, timeout: 3000, maximumAge: 600000 });
      }catch(e){ __geo = null; }
    }

    function refresh(){
      const filter = buildFilter(input.value);
      current = __airports.filter(filter);
      nearest = null;
      if (__geo){ nearest = findNearestAirport(__geo.lat, __geo.lon); }
      renderItems(panel, current, nearest);
      selectedIndex = -1;
    }

    function commitFromNode(node){
      if (!node) return;
      const code = node.dataset.code || '';
      input.value = code;
      input.dataset.iata = code;
      input.dataset.city = node.dataset.city||'';
      input.dataset.name = node.dataset.name||'';
      panel.style.display = 'none';
      input.dispatchEvent(new Event('input', { bubbles:true }));
      input.dispatchEvent(new Event('change', { bubbles:true }));
      input.focus();
    }

    input.addEventListener('focus', refresh);
    input.addEventListener('input', refresh);
    input.addEventListener('blur', function(){ setTimeout(()=>{ panel.style.display='none'; }, 180); });

    input.addEventListener('keydown', function(ev){
      if (panel.style.display === 'none') return;
      const nodes = Array.from(panel.querySelectorAll('.item'));
      if (ev.key === 'ArrowDown'){
        ev.preventDefault(); selectedIndex = Math.min(nodes.length-1, selectedIndex+1);
        nodes.forEach(n=>n.classList.remove('active')); if (nodes[selectedIndex]) nodes[selectedIndex].classList.add('active');
      } else if (ev.key === 'ArrowUp'){
        ev.preventDefault(); selectedIndex = Math.max(0, selectedIndex-1);
        nodes.forEach(n=>n.classList.remove('active')); if (nodes[selectedIndex]) nodes[selectedIndex].classList.add('active');
      } else if (ev.key === 'Enter'){
        if (selectedIndex >= 0){ ev.preventDefault(); commitFromNode(nodes[selectedIndex]); }
      } else if (ev.key === 'Escape'){
        panel.style.display = 'none';
      }
    });

    panel.addEventListener('mousedown', function(ev){
      const it = ev.target.closest('.item'); if (!it) return;
      ev.preventDefault();
      commitFromNode(it);
    });
  }

  global.AirportAutocomplete = { attach };
})(window);
