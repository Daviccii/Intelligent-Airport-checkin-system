// Passenger wizard (modular)
(function(){
    const wizard = document.getElementById('wizard');
    if (!wizard) return;

    const steps = Array.from(wizard.querySelectorAll('#steps .step')) || Array.from(wizard.querySelectorAll('.step'));
    const panes = Array.from(wizard.querySelectorAll('.pane'));

    function showStepByName(name){
        steps.forEach(s => s.classList.toggle('active', s.dataset.step === name));
        panes.forEach(p => {
            try{
                const is = (p.id === name);
                p.classList.toggle('active', is);
                p.hidden = !is;
                p.setAttribute('aria-hidden', String(!is));
            }catch(e){}
        });
    }

    // initialize: show the active step if present, otherwise first
    const initial = steps.find(s => s.classList.contains('active'))?.dataset.step || steps[0]?.dataset.step;
    if (initial) showStepByName(initial);

    // step navigation by clicking steps
    steps.forEach(s => s.addEventListener('click', ()=> showStepByName(s.dataset.step)));

    // simple helpers for buttons inside panes
    function toStep(name){ showStepByName(name); try{ window.scrollTo(0, wizard.offsetTop - 20); } catch(e){} }

    const toAuth = document.getElementById('toAuth');
    if (toAuth) toAuth.addEventListener('click', ()=> toStep('auth'));

    // wire generic next/prev if elements use data-next/data-prev
    wizard.addEventListener('click', (e)=>{
        const btn = e.target.closest('[data-next], [data-prev]');
        if (!btn) return;
        const next = btn.getAttribute('data-next');
        const prev = btn.getAttribute('data-prev');
        if (next) toStep(next);
        if (prev) toStep(prev);
    });

    // auth/lookup forms: simple client-side placeholders to progress the wizard
    const authForm = document.getElementById('authForm');
    if (authForm){
        authForm.addEventListener('submit', (e)=>{
            e.preventDefault();
            // fake validation and move to lookup step
            showStepByName('lookup');
        });
    }

    const lookupForm = document.getElementById('lookupForm');
    if (lookupForm){
        lookupForm.addEventListener('submit', (e)=>{
            e.preventDefault();
            // attempt to advance to select
            showStepByName('select');
        });
    }

    // expose helper to other modules
    window.SMFPassengerWizard = {
        showStep: showStepByName
    };
})();
