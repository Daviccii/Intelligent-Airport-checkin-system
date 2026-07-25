const api = {
    list: "/api/passengers",
    register: "/api/register"
};

function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
}

const fieldValidators = {
    name: (v) => /^[a-zA-Z\s'-]{2,60}$/.test(v),
    passport: (v) => /^[A-Z0-9]{6,12}$/i.test(v),
    flight: (v) => /^[A-Z]{2,3}\d{3,4}$/i.test(v) // Align with backend: 2-3 letters, 3-4 digits, no hyphen.
};

function validateInput(id, validator, errorMsg) {
    const elInput = document.getElementById(id);
    const elErr = document.getElementById(`err-${id}`);
    const val = elInput.value.trim();

    if (!validator(val)) {
        elInput.classList.add("input-error");
        if (elErr) elErr.textContent = errorMsg;
        return false;
    } else {
        elInput.classList.remove("input-error");
        if (elErr) elErr.textContent = "";
        return true;
    }
}

async function fetchPassengers() {
    try {
        const res = await fetch(api.list);
        const data = await res.json();
        return res.ok ? (data.passengers || []) : [];
    } catch (e) {
        return [];
    }
}

function renderTable(data) {
    const container = document.getElementById("passengerList");
    container.innerHTML = "";
    if (!data.length) {
        container.appendChild(el("div", "empty", "No passengers yet."));
        return;
    }
    const table = el("table", "pass-table");
    const thead = el("thead");
    thead.innerHTML = "<tr><th>#</th><th>Name</th><th>Passport</th><th>Flight</th><th>Seat</th></tr>";
    table.appendChild(thead);
    const tbody = el("tbody");
    data.forEach((p, i) => {
        const tr = el("tr");
        tr.innerHTML = `<td>${i + 1}</td><td>${escapeHtml(p.name)}</td><td>${escapeHtml(p.passport)}</td><td>${escapeHtml(p.flight)}</td><td>${escapeHtml(p.seat || 'N/A')}</td>`;
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
}

function escapeHtml(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]); }

async function refreshList() {
    const all = await fetchPassengers();
    const filter = document.getElementById("filterFlight").value.trim().toLowerCase();
    const filtered = filter ? all.filter(p => p.flight && p.flight.toLowerCase().includes(filter)) : all;
    renderTable(filtered);
}

async function submitForm(e) {
    e.preventDefault();

    const validName = validateInput("name", fieldValidators.name, "Enter a valid full name.");
    const validPassport = validateInput("passport", fieldValidators.passport, "Enter a 6-12 alphanumeric passport #.");
    const validFlight = validateInput("flight", fieldValidators.flight, "Enter a valid flight code (e.g. KQ482).");

    const msg = document.getElementById("message");
    msg.textContent = "";

    if (!validName || !validPassport || !validFlight) {
        msg.textContent = "Please fix the validation errors above.";
        msg.className = "message error";
        return;
    }

    const name = document.getElementById("name").value.trim();
    const passport = document.getElementById("passport").value.trim();
    const flight = document.getElementById("flight").value.trim();

    try {
        const res = await fetch(api.register, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, passport, flight })
        });
        const body = await res.json();
        if (!res.ok) {
            const errorDetail = body.errors ? Object.values(body.errors).join(' ') : (body.detail || "Registration failed");
            msg.textContent = errorDetail;
            msg.className = "message error";
            return;
        }
        msg.textContent = `Registered ${escapeHtml(body.name)} — seat ${escapeHtml(body.seat)} on ${escapeHtml(body.flight)}`;
        msg.className = "message success";
        document.getElementById("registerForm").reset();
        await refreshList();
    } catch (err) {
        msg.textContent = "Network error. Please try again.";
        msg.className = "message error";
    }
}

function checkCheckinFormValidity() {
    const nameValid = fieldValidators.name(document.getElementById('name').value.trim());
    const passportValid = fieldValidators.passport(document.getElementById('passport').value.trim());
    const flightValid = fieldValidators.flight(document.getElementById('flight').value.trim());
    const submitBtn = document.getElementById('registerForm').querySelector('button[type="submit"]');

    if (nameValid && passportValid && flightValid) {
        submitBtn.disabled = false;
        submitBtn.classList.remove('disabled');
    } else {
        submitBtn.disabled = true;
        submitBtn.classList.add('disabled');
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("registerForm");
    form.addEventListener("submit", submitForm);

    // Add real-time validation on input
    ['name', 'passport', 'flight'].forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.addEventListener('input', () => {
                if (id === 'name') {
                    validateInput("name", fieldValidators.name, "Enter a valid full name.");
                } else if (id === 'passport') {
                    validateInput("passport", fieldValidators.passport, "Enter a 6-12 alphanumeric passport #.");
                } else { // flight
                    validateInput("flight", fieldValidators.flight, "Enter a valid flight code (e.g. KQ482).");
                }
                checkCheckinFormValidity();
            });
        }
    });

    document.getElementById("refreshBtn").addEventListener("click", refreshList);
    document.getElementById("filterFlight").addEventListener("input", refreshList);
    document.getElementById("clearBtn").addEventListener("click", () => {
        form.reset();
        document.querySelectorAll('.input-error').forEach(e => e.classList.remove('input-error'));
        document.querySelectorAll('.field-error').forEach(e => e.textContent = '');
        document.getElementById("message").textContent = '';
        checkCheckinFormValidity(); // Re-check after clearing
    });
    refreshList();
    checkCheckinFormValidity(); // Initial check on load
});