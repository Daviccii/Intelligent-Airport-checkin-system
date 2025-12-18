// Accessible mega-menu: keyboard navigation, focus management and ARIA state
// Migrated from frontend/index.html
(function(){
    function init(){
        const tabs = document.querySelectorAll('.header-tabs .tab-link');
        const megaContainer = document.querySelector('.header-mega');
        if(!tabs || !megaContainer) return;
        let openMenu = null; let openTab = null;

        function setMenuItemsTabindex(menu, val){
            if(!menu) return;
            const items = Array.from(menu.querySelectorAll('[role="menuitem"]'));
            items.forEach(i => {
                try { i.setAttribute('tabindex', String(val)); } catch(e){}
            });
            return items;
        }

        function openMega(key, tab, focusFirst = true){
            closeMega(false);
            const menu = document.getElementById('mega-' + key);
            if(!menu) return;
            menu.classList.add('show');
            // remove inert so assistive tech can access
            try { megaContainer.removeAttribute('inert'); } catch(e){}
            megaContainer.setAttribute('aria-hidden','false');
            tab.setAttribute('aria-expanded','true');
            openMenu = menu; openTab = tab;
            // make items keyboard-focusable when open
            const items = setMenuItemsTabindex(menu, 0);
            if(focusFirst && items && items.length){ try{ items[0].focus(); }catch(e){} }
        }

        function closeMega(returnFocus = true){
            if(!openMenu) return;
            openMenu.classList.remove('show');
            // mark as hidden and inert to prevent keyboard focus
            try { megaContainer.setAttribute('inert',''); } catch(e){}
            megaContainer.setAttribute('aria-hidden','true');
            // remove focusability from menu items when closed
            try { setMenuItemsTabindex(openMenu, -1); } catch(e){}
            if(openTab) openTab.setAttribute('aria-expanded','false');
            if(returnFocus && openTab) try { openTab.focus(); } catch(e){}
            openMenu = null; openTab = null;
        }

        tabs.forEach(tab => {
            const key = tab.dataset.key;
            tab.setAttribute('aria-expanded','false');

            // ensure any menu items start off not tabbable while container is aria-hidden
            try {
                const menu = document.getElementById('mega-' + key);
                if (menu && megaContainer && megaContainer.getAttribute('aria-hidden') === 'true') setMenuItemsTabindex(menu, -1);
            } catch(e){}

            tab.addEventListener('mouseenter', () => openMega(key, tab, false));
            tab.addEventListener('focus', () => openMega(key, tab, true));

            tab.addEventListener('mouseleave', () => {
                setTimeout(()=>{
                    if(!openMenu) return;
                    if(!openMenu.matches(':hover') && !tab.matches(':hover')) closeMega(false);
                }, 150);
            });

            tab.addEventListener('click', (e) => {
                if(tab.getAttribute('aria-expanded') === 'true'){
                    closeMega();
                } else {
                    openMega(key, tab, true);
                }
                e.preventDefault();
            });

            tab.addEventListener('keydown', (e) => {
                if(e.key === 'ArrowDown' || e.key === 'Down'){
                    e.preventDefault();
                    openMega(key, tab, true);
                }
                if(e.key === 'Escape'){
                    closeMega();
                }
            });
        });

        document.addEventListener('keydown', (e) => {
            if(!megaContainer) return;
            if(!document.querySelector('.mega-menu.show')) return;
            const open = document.querySelector('.mega-menu.show');
            if(!open) return;
            const items = Array.from(open.querySelectorAll('[role="menuitem"]'));
            const idx = items.indexOf(document.activeElement);
            if(e.key === 'ArrowDown' || e.key === 'Down'){
                e.preventDefault();
                const next = items[(idx + 1) % items.length]; if(next) next.focus();
            }
            if(e.key === 'ArrowUp' || e.key === 'Up'){
                e.preventDefault();
                const prev = items[(idx - 1 + items.length) % items.length]; if(prev) prev.focus();
            }
            if(e.key === 'Home'){
                e.preventDefault(); if(items[0]) items[0].focus();
            }
            if(e.key === 'End'){
                e.preventDefault(); if(items[items.length-1]) items[items.length-1].focus();
            }
            if(e.key === 'Escape'){
                e.preventDefault();
                const evt = new Event('closeMega'); document.dispatchEvent(evt);
            }
        });

        // close on outside click
        document.addEventListener('click', (e) => {
            if(!megaContainer.contains(e.target) && !e.target.classList.contains('tab-link')){
                // close all
                const open = document.querySelector('.mega-menu.show');
                if(open){ open.classList.remove('show'); megaContainer.setAttribute('aria-hidden','true'); }
                tabs.forEach(t=>t.setAttribute('aria-expanded','false'));
            }
        });

        // close when focus moves outside the menu/tab
        document.addEventListener('focusin', (e) => {
            const open = document.querySelector('.mega-menu.show');
            if(!open) return;
            const tab = document.querySelector('.header-tabs .tab-link[aria-expanded="true"]');
            if(!megaContainer.contains(e.target) && !(tab && tab.contains(e.target))){
                open.classList.remove('show'); megaContainer.setAttribute('aria-hidden','true'); if(tab) tab.setAttribute('aria-expanded','false');
            }
        });
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
