(function(global){
  'use strict';

  const SUGG_MAX = 50;
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
    el.className = 'airport-suggestions';
    el.setAttribute('role', 'listbox');
    el.setAttribute('aria-label', 'Airport suggestions');
    return el;
  }

  function renderItems(panel, items, nearest){
    panel.innerHTML = '';
    const frag = document.createDocumentFragment();

    // If nearest present and not already in filtered list, put it first with highlight
    if (nearest){
      const n = renderItem(nearest, true);
      frag.appendChild(n);
    }
    
    // Add filtered airports (max SUGG_MAX)
    const list = items.slice(0, SUGG_MAX);
    list.forEach(a => {
      if (nearest && a.code === nearest.code) return; // avoid duplicate
      frag.appendChild(renderItem(a, false));
    });

    panel.appendChild(frag);
    
    // Show panel if there are items
    if (list.length > 0 || nearest) {
      panel.classList.add('active');
    } else {
      panel.classList.remove('active');
    }
  }

  function renderItem(a, isNearest){
    const div = document.createElement('div');
    div.className = 'airport-suggestion-item' + (isNearest ? ' nearest-airport' : '');
    div.setAttribute('role','option');
    div.setAttribute('data-iata', a.code);
    div.dataset.code = a.code;
    div.dataset.city = a.city || '';
    div.dataset.name = a.name || '';

    // Airport code (highlighted)
    const code = document.createElement('div'); 
    code.className = 'airport-suggestion-code'; 
    code.textContent = a.code;

    // Airport info container
    const info = document.createElement('div');
    info.className = 'airport-suggestion-info';
    
    // City/country line
    const main = document.createElement('div'); 
    main.className = 'airport-suggestion-main'; 
    main.textContent = a.city ? `${a.city}, ${a.country || ''}`.trim() : a.country || 'Airport';
    
    // Airport name line
    const sub = document.createElement('div'); 
    sub.className = 'airport-suggestion-sub'; 
    sub.textContent = a.name || '';
    
    info.appendChild(main);
    info.appendChild(sub);

    div.appendChild(code);
    div.appendChild(info);

    // Add "Nearest" badge if applicable
    if (isNearest){
      const badge = document.createElement('div'); 
      badge.className = 'airport-badge'; 
      badge.textContent = '📍 Nearest';
      div.appendChild(badge);
    }
    return div;
  }

  function buildFilter(query){
    const q = (query||'').trim().toLowerCase();
    if (!q) return (a) => true;
    // Match by code (exact prefix), city name, airport name, or country
    return (a) => a.code.toLowerCase().startsWith(q) ||
                  (a.city||'').toLowerCase().includes(q) ||
                  (a.name||'').toLowerCase().includes(q) ||
                  (a.country||'').toLowerCase().includes(q);
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
    let geoRequested = false;

    // Only request geolocation on user interaction (focus)
    function ensureGeolocation(){
      if (geoRequested || !navigator.geolocation) return;
      geoRequested = true;
      try{
        navigator.geolocation.getCurrentPosition((pos)=>{
          __geo = { lat: pos.coords.latitude, lon: pos.coords.longitude };
        }, ()=>{ __geo = null; }, { enableHighAccuracy: false, maximumAge: 600000 });
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
      const code = node.dataset.code || node.getAttribute('data-iata') || '';
      input.value = code;
      input.dataset.iata = code;
      input.dataset.selected = 'true';
      input.dataset.city = node.dataset.city||'';
      input.dataset.name = node.dataset.name||'';
      panel.classList.remove('active');
      input.dispatchEvent(new Event('input', { bubbles:true }));
      input.dispatchEvent(new Event('change', { bubbles:true }));
      input.focus();
    }

    input.addEventListener('focus', function(){
      ensureGeolocation();
      refresh();
      if (!input.value.trim()){
        const filter = buildFilter('');
        current = __airports.slice(0, SUGG_MAX);
        nearest = null;
        if (__geo){ nearest = findNearestAirport(__geo.lat, __geo.lon); }
        renderItems(panel, current, nearest);
        selectedIndex = -1;
      }
    });
    
    input.addEventListener('input', refresh);
    
    // Hide only when clicking outside, not on blur (prevents flicker)
    function onDocumentHide(ev){
      try{
        if (!wrap.contains(ev.target)) {
          panel.classList.remove('active');
        }
      }catch(e){ panel.classList.remove('active'); }
    }
    document.addEventListener('mousedown', onDocumentHide);
    document.addEventListener('touchstart', onDocumentHide, { passive: true });

    input.addEventListener('keydown', function(ev){
      if (!panel.classList.contains('active')) return;
      const nodes = Array.from(panel.querySelectorAll('.airport-suggestion-item'));
      if (ev.key === 'ArrowDown'){
        ev.preventDefault(); 
        selectedIndex = Math.min(nodes.length-1, selectedIndex+1);
        nodes.forEach(n=>n.classList.remove('active')); 
        if (nodes[selectedIndex]) nodes[selectedIndex].classList.add('active');
        nodes[selectedIndex]?.scrollIntoView({ block: 'nearest' });
      } else if (ev.key === 'ArrowUp'){
        ev.preventDefault(); 
        selectedIndex = Math.max(-1, selectedIndex-1);
        nodes.forEach(n=>n.classList.remove('active')); 
        if (selectedIndex >= 0 && nodes[selectedIndex]) nodes[selectedIndex].classList.add('active');
        nodes[selectedIndex]?.scrollIntoView({ block: 'nearest' });
      } else if (ev.key === 'Enter'){
        if (selectedIndex >= 0){ 
          ev.preventDefault(); 
          commitFromNode(nodes[selectedIndex]); 
        }
      } else if (ev.key === 'Escape'){
        panel.classList.remove('active');
        input.blur();
      }
    });

    panel.addEventListener('mousedown', function(ev){
      const it = ev.target.closest('.airport-suggestion-item'); 
      if (!it) return;
      ev.preventDefault();
      commitFromNode(it);
    });
    
    // Prevent blur when clicking inside panel
    panel.addEventListener('mousedown', function(ev){
      ev.preventDefault();
    });
  }

  global.AirportAutocomplete = { attach };
})(window);
