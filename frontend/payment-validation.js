document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('payment-form');
    if (!form) return;

    // Luhn Algorithm for card number validation
    const luhnCheck = (val) => {
        let sum = 0;
        let shouldDouble = false;
        for (let i = val.length - 1; i >= 0; i--) {
            let digit = parseInt(val.charAt(i));
            if (shouldDouble) {
                if ((digit *= 2) > 9) digit -= 9;
            }
            sum += digit;
            shouldDouble = !shouldDouble;
        }
        return (sum % 10) === 0;
    };

    const paymentValidators = {
        'card-holder': (val) => {
            const v = val.trim();
            if (v === '') return 'Card holder name is required.';
            if (!/^[a-zA-Z\s\-'.]{2,100}$/.test(v)) return 'Please enter a valid name.';
            return true;
        },
        'card-number': (val) => {
            const v = val.replace(/[\s-]/g, '');
            if (v === '') return 'Card number is required.';
            if (!/^\d{13,19}$/.test(v)) return 'Card number must be 13-19 digits.';
            if (!luhnCheck(v)) return 'Invalid card number.';
            return true;
        },
        'card-expiry': (val) => {
            const v = val.trim();
            if (v === '') return 'Expiry date is required.';
            if (!/^(0[1-9]|1[0-2])\s?\/\s?\d{2}$/.test(v)) return 'Invalid format. Use MM/YY.';

            const [month, year] = v.split('/').map(s => parseInt(s.trim(), 10));
            const expiryDate = new Date(`20${year}`, month, 1); // Check against the first day of the next month
            const now = new Date();
            const currentDate = new Date(now.getFullYear(), now.getMonth(), 1);

            if (expiryDate <= currentDate) return 'Card has expired.';
            return true;
        },
        'card-cvv': (val) => {
            const v = val.trim();
            if (v === '') return 'CVV is required.';
            if (!/^\d{3,4}$/.test(v)) return 'CVV must be 3 or 4 digits.';
            return true;
        },
        'mpesa-phone': (val) => {
            const v = val.trim().replace(/\s+/g, '');
            if (v === '') return 'MPESA phone number is required.';
            if (!/^(?:\+254|254|0)?(7\d{8})$/.test(v)) return 'Enter a valid Kenyan phone number.';
            return true;
        },
        'paypal-email': (val) => {
            const v = val.trim();
            if (v === '') return 'PayPal email is required.';
            if (!/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(v)) return 'Enter a valid email address.';
            return true;
        },
        'bank-account-name': (val) => {
            const v = val.trim();
            if (v === '') return 'Account holder name is required.';
            if (!/^[a-zA-Z\s\-'.]{2,100}$/.test(v)) return 'Please enter a valid name.';
            return true;
        },
        'bank-account-number': (val) => {
            const v = val.trim().replace(/\s+/g, '');
            if (v === '') return 'Account number is required.';
            if (!/^\d{8,17}$/.test(v)) return 'Account number must be 8-17 digits.';
            return true;
        },
        'bank-name': (val) => {
            const v = val.trim();
            if (v === '') return 'Bank name is required.';
            if (!/^[a-zA-Z0-9\s\-&.,']{2,100}$/.test(v)) return 'Please enter a valid bank name.';
            return true;
        }
    };

    const fieldsToValidate = {
        'card-holder': { validator: paymentValidators['card-holder'], paymentMethod: 'card' },
        'card-number': { validator: paymentValidators['card-number'], paymentMethod: 'card' },
        'card-expiry': { validator: paymentValidators['card-expiry'], paymentMethod: 'card' },
        'card-cvv': { validator: paymentValidators['card-cvv'], paymentMethod: 'card' },
        'mpesa-phone': { validator: paymentValidators['mpesa-phone'], paymentMethod: 'mpesa' },
        'paypal-email': { validator: paymentValidators['paypal-email'], paymentMethod: 'paypal' },
        'bank-account-name': { validator: paymentValidators['bank-account-name'], paymentMethod: 'bank' },
        'bank-account-number': { validator: paymentValidators['bank-account-number'], paymentMethod: 'bank' },
        'bank-name': { validator: paymentValidators['bank-name'], paymentMethod: 'bank' }
    };

    function getSelectedMethod() {
        const methodInput = document.getElementById('active-payment-method');
        return methodInput ? methodInput.value : 'card';
    }

    function validateField(field) {
        const { input, group, validator } = field;
        const result = validator(input.value);
        const errorEl = group.querySelector('.invalid-feedback');

        if (result !== true) {
            group.classList.add('invalid');
            if (errorEl) errorEl.textContent = result;
            return false;
        } else {
            group.classList.remove('invalid');
            if (errorEl) errorEl.textContent = '';
            return true;
        }
    }

    function checkPaymentFormValidity() {
        const submitBtn = form.querySelector('button[type="submit"]');
        const selectedMethod = getSelectedMethod();
        let isFormValid = true;

        for (const id in fieldsToValidate) {
            const field = fieldsToValidate[id];
            if (!field.input || !field.group) continue;
            // Only validate fields for the selected payment method
            if (field.paymentMethod === selectedMethod) {
                if (!validateField(field)) {
                    isFormValid = false;
                }
            } else {
                // Clear errors from other payment method fields
                field.group.classList.remove('invalid');
                const errorEl = field.group.querySelector('.invalid-feedback');
                if (errorEl) errorEl.textContent = '';
            }
        }

        submitBtn.disabled = !isFormValid;
        return isFormValid;
    }
    // Exposed so selectMethod() in payment.html can re-check validity when the
    // payment method tab changes.
    window.checkPaymentFormValidity = checkPaymentFormValidity;

    // Initialize fields and attach listeners
    for (const id in fieldsToValidate) {
        const field = fieldsToValidate[id];
        field.input = document.getElementById(id);
        field.group = field.input ? field.input.closest('.form-group') : null;

        if (field.input && field.group) {
            if (!field.group.querySelector('.invalid-feedback')) {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'invalid-feedback';
                errorDiv.style.color = 'var(--error, #EF4444)';
                errorDiv.style.fontSize = '0.75rem';
                errorDiv.style.marginTop = '0.35rem';
                errorDiv.style.fontWeight = '500';
                field.group.appendChild(errorDiv);
            }
            field.input.addEventListener('input', checkPaymentFormValidity);
        }
    }

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        if (checkPaymentFormValidity()) {
            submitPayment(getSelectedMethod());
        } else {
            console.log('❌ Payment form is invalid. Submission blocked.');
            const firstInvalid = form.querySelector('.form-group.invalid input');
            if (firstInvalid) {
                firstInvalid.focus();
            }
        }
    });

    // Initial check
    checkPaymentFormValidity();

    function showPaymentError(message) {
        let errorBox = document.getElementById('payment-error-banner');
        if (!errorBox) {
            errorBox = document.createElement('div');
            errorBox.id = 'payment-error-banner';
            errorBox.style.cssText = 'background:#FEF2F2;color:#B91C1C;border:1px solid #FCA5A5;' +
                'padding:0.85rem 1rem;border-radius:6px;margin-bottom:1rem;font-size:0.85rem;font-weight:600;';
            form.parentNode.insertBefore(errorBox, form);
        }
        errorBox.textContent = message;
        errorBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    function submitPayment(method) {
        const loader = document.getElementById('loader');
        const bookingSession = window.bookingSession || {};
        const flight = bookingSession.selectedFlight || {};
        const passenger = (bookingSession.passengers && bookingSession.passengers[0]) || {};
        const search = bookingSession.searchParams || {};

        if (loader) loader.style.display = 'flex';

        // Generated here so the receipt can show it immediately, distinct from the
        // booking_ref/PNR the server assigns when it actually creates the record.
        const transactionId = 'TXN-' + Date.now().toString(36).toUpperCase() + Math.floor(1000 + Math.random() * 9000);

        const payload = Object.assign({}, bookingSession, {
            paymentMethod: method.toUpperCase(),
            paymentStatus: 'Paid',
            transactionId
        });

        // POST to /api/bookings — this is the public checkout flow, so it's an
        // unauthenticated request; the backend's POST branch doesn't require a
        // staff/admin session (only GET does).
        fetch('/api/bookings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
            .then((res) => res.json()
                .catch(() => ({}))
                .then((body) => ({ ok: res.ok, status: res.status, body })))
            .then(({ ok, status, body }) => {
                if (loader) loader.style.display = 'none';

                if (!ok) {
                    showPaymentError(body.error
                        ? `Payment could not be completed: ${body.error}`
                        : `Payment could not be completed (HTTP ${status}). Please try again.`);
                    return;
                }

                const booking = body.booking || {};
                const now = new Date();
                const formattedTimestamp = now.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) +
                    ', ' + now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                const passengerName = `${passenger.firstName || ''} ${passenger.lastName || ''}`.trim();
                const pnr = booking.booking_ref || booking.id || 'N/A';

                document.getElementById('receipt-pnr').innerText = pnr;
                document.getElementById('receipt-txn').innerText = transactionId;
                document.getElementById('receipt-timestamp').innerText = formattedTimestamp;
                document.getElementById('receipt-passenger-name').innerText = passengerName;
                document.getElementById('receipt-route').innerText = `${search.origin || ''} → ${search.destination || ''}`;
                document.getElementById('receipt-method').innerText = method.toUpperCase();
                document.getElementById('receipt-amount').innerText = `Ksh ${Number(flight.price || 0).toLocaleString()}`;

                // Persist the confirmed, server-acknowledged state so a later
                // check-in step can read it back.
                bookingSession.paymentStatus = 'Paid';
                bookingSession.transactionId = transactionId;
                bookingSession.paymentMethod = method.toUpperCase();
                bookingSession.pnr = pnr;
                window.bookingSession = bookingSession;
                sessionStorage.setItem('smartflyBookingSession', JSON.stringify(bookingSession));

                document.getElementById('receipt-modal').style.display = 'flex';
            })
            .catch((err) => {
                if (loader) loader.style.display = 'none';
                showPaymentError('Network error — could not reach the payment server. Please check your connection and try again.');
                console.error('Booking submission failed:', err);
            });
    }
});