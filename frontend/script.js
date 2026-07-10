/**
 * ApplianceCare — script.js  (frontend only; no business logic)
 * ────────────────────────────────────────────────────────────────
 * This file is intentionally "dumb":
 *   • It sends the user's actions to the backend.
 *   • It renders whatever the backend returns.
 *   • It does NOT know the form schema, field labels, product list,
 *     dates, times, or any validation rules — all of that lives in
 *     the AWS Lambdas (AngelLambda.py / DhruvLambda.py).
 *
 * Message protocol (see aws-lambdas/LexApiHandler.py):
 *   1. User picks a bot → we send  `SELECT_BOT:<bot>`  then  `INIT_<BOT>`
 *      → Lambda returns { sessionAttributes.formSchema } → we render it.
 *   2. User clicks Continue → we send `FORM_SUBMIT:<json>`
 *      → Lambda returns either { sessionAttributes.formErrors } (show inline)
 *        or  { sessionAttributes.formSummary } (render review card).
 *   3. User clicks Confirm → we send `FORM_CONFIRM:<json>`
 *      → Lambda returns { sessionAttributes.formSuccess } (render success card).
 *   4. Free-text chat is forwarded to AWS Lex, unchanged.
 */

const API_URL = (typeof CONFIG !== 'undefined' && CONFIG.API_URL) || '';

const BOT_META = {
    angel:   { label: "Angel's Assistant",   color: '#7c6bff', initial: 'A' },
    krishna: { label: "Krishna's Assistant", color: '#ff8c42', initial: 'K' },
    dhruv:   { label: "Dhruv's Assistant",   color: '#00c4a7', initial: 'D' }
};

const state = {
    sessionId:  makeId(),
    activeBot:  '',
    loading:    false,
    formSchema: null,
    formValues: {},
    formSummary: null
};

function makeId() {
    return 'sess-' + Date.now() + '-' + Math.random().toString(36).slice(2, 6);
}

const $ = id => document.getElementById(id);

function scrollBottom() {
    const m = $('messages');
    if (m) m.scrollTop = m.scrollHeight;
}

function setBadge(botKey) {     /**Updates the bot badge in the topbar**/
    const badge = $('botBadge');
    const dot   = $('botBadgeDot');
    const name  = $('botBadgeName');
    if (!botKey || !BOT_META[botKey]) { badge.style.display = 'none'; return; }
    dot.style.background = BOT_META[botKey].color;
    name.textContent     = BOT_META[botKey].label;
    badge.style.display  = 'flex';
}

function addDateDivider() {
    const box = $('messages');
    const div = document.createElement('div');
    div.className = 'date-divider';
    div.textContent = new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' });
    box.appendChild(div);
}

function renderUser(text) {     /**Shows user's message in the chat */
    const box = $('messages');
    const row = document.createElement('div');
    row.className = 'row user';
    row.innerHTML = `<div class="bubble">${esc(text)}</div>`;
    box.appendChild(row);     /**appendChild() - Adds it to the messages area */
    scrollBottom();
}

/**
 * Build the small circular avatar shown next to bot messages.
 * Uses the currently-selected bot's initial & color, or a neutral fallback.
 * Centralized so we don't repeat the same DOM/style code in every renderer
 * (text bubble, card, form, typing indicator).
 */
function buildAvatar() {
    /**Creates avatar (colored circle with letter) */
    const av = document.createElement('div');
    av.className = 'avatar';
    if (state.activeBot && BOT_META[state.activeBot]) {
        av.textContent      = BOT_META[state.activeBot].initial;
        av.style.background = `linear-gradient(135deg, ${BOT_META[state.activeBot].color}, #0070f3)`;
    } else {
        av.textContent = '⚙';
        av.style.background = 'linear-gradient(135deg, #00c4a7, #0070f3)';
    }
    return av;
}
function renderBot(content) {
    const box = $('messages');
    const row = document.createElement('div');
    row.className = 'row bot';
    const av = buildAvatar();
    /**creates message content */
    let inner;
    if (content.type === 'welcome')     inner = buildWelcomeCard();
    else if (content.type === 'card')   inner = buildCardBubble(content.title, content.buttons);
    else {
        inner = document.createElement('div');
        inner.className = 'bubble';
        let safeText = esc(content.text || '');
        safeText = safeText.replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" style="color: var(--accent-text); text-decoration: underline;">$1</a>');
        inner.innerHTML = safeText;
    }

    row.appendChild(av);
    row.appendChild(inner);
    box.appendChild(row);
    scrollBottom();
}

/**Creates the initial welcome screen */
function buildWelcomeCard() {
    const card = document.createElement('div');
    card.className = 'welcome-card';
    card.innerHTML = `
        <p class="welcome-eyebrow">Appliance Consultation</p>
        <h2 class="welcome-title">Welcome To Cloud Ladder Consulting</h2>
        <p class="welcome-sub">Choose an assistant to get started. Each assistant handles refrigerator, TV, washing machine, and dishwasher bookings.</p>
        <div class="bot-picker" id="botPicker">
            <button class="bot-pick-btn" data-bot="angel" onclick="Chat.pickBot('angel', this)">
                <div class="pick-avatar" style="background:linear-gradient(135deg,#7c6bff,#5b4fd8)">A</div>
                <div class="pick-info">
                    <div class="pick-name">Consultancy Help</div>
                    <div class="pick-sub">Maintenance Help · Available now</div>
                </div>
                <span class="pick-arrow">→</span>
            </button>
            <button class="bot-pick-btn" data-bot="krishna" onclick="Chat.pickBot('krishna', this)">
                <div class="pick-avatar" style="background:linear-gradient(135deg,#ff8c42,#e05f00)">K</div>
                <div class="pick-info">
                    <div class="pick-name">Krishna's Assistant</div>
                    <div class="pick-sub">Technical Support · Currently not Available</div>
                </div>
                <span class="pick-arrow">→</span>
            </button>
            <button class="bot-pick-btn" data-bot="dhruv" onclick="Chat.pickBot('dhruv', this)">
                <div class="pick-avatar" style="background:linear-gradient(135deg,#00c4a7,#007a68)">D</div>
                <div class="pick-info">
                    <div class="pick-name">Purchase Help</div>
                    <div class="pick-sub">Purchase Help · Available now</div>
                </div>
                <span class="pick-arrow">→</span>
            </button>
        </div>`;
    return card;
}

/**it creates ANY buttons the Lambda tells it to create */
function buildCardBubble(title, buttons) {
    const wrap = document.createElement('div');
    wrap.className = 'card-bubble';
    const q = document.createElement('p');
    q.className = 'card-question';
    q.textContent = title;
    wrap.appendChild(q);
    if (buttons && buttons.length > 0) {
        const btns = document.createElement('div');
        btns.className = 'card-btns';
        buttons.forEach(b => {
            const btn = document.createElement('button');
            btn.className = 'card-btn';
            btn.textContent = b.text;
            btn.onclick = () => {
                if (typeof b.value === 'string' && (b.value.startsWith('http://') || b.value.startsWith('https://'))) {
                    window.open(b.value, '_blank'); return;
                }
                btns.querySelectorAll('.card-btn').forEach(x => x.disabled = true);
                Chat.sendRaw(b.value, b.text);
            };
            btns.appendChild(btn);
        });
        wrap.appendChild(btns);
    }
    return wrap;
}

/**Bot is typing... animation comes from here */
function showTyping() {
    const box = $('messages');
    const row = document.createElement('div');
    row.className = 'row bot'; row.id = 'typing';
    const av = buildAvatar();
    const t = document.createElement('div');
    t.className = 'typing';
    t.innerHTML = '<div class="tdot"></div><div class="tdot"></div><div class="tdot"></div>';
    row.appendChild(av); row.appendChild(t);
    box.appendChild(row);
    scrollBottom();
}
function hideTyping() { $('typing')?.remove(); }
function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

/*API MANAGER — one endpoint for everything*/
/**bridge between your website (the frontend) and your AWS backend */

async function callAPI(message) {
    if (!API_URL) throw new Error('API_URL not configured (edit public/config.js).');
    const res = await fetch(API_URL, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, sessionId: state.sessionId, activeBot: state.activeBot })
    });
    if (!res.ok) {
        const body = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status} from ${API_URL} — ${body.slice(0, 200)}`);
    }
    return res.json();
}

/**
 * Route the backend response to the right renderer.
 * The Lambda uses `sessionAttributes` to piggyback structured payloads:
 *   formSchema   → render the input form
 *   formErrors   → highlight fields the Lambda rejected
 *   formSummary  → render the review card
 *   formSuccess  → render the confirmation card
 *   uiButtons    → attach quick-reply buttons to the last chat message
 */
function handleResponse(data) {
    if (data.activeBot) { state.activeBot = data.activeBot; setBadge(data.activeBot); }

    const attrs = data.sessionAttributes || {};
    const messages = data.messages || [];

    if (attrs.formSchema) {
        try { FormFlow.openWithSchema(JSON.parse(attrs.formSchema)); } catch (e) { console.error('bad formSchema', e); }
        return;
    }
    if (attrs.formErrors) {
        try { FormFlow.showErrors(JSON.parse(attrs.formErrors)); } catch (e) { console.error('bad formErrors', e); }
        // Also let any accompanying text bubbles render below.
    }
    if (attrs.formSummary) {
        try { FormFlow.showSummary(JSON.parse(attrs.formSummary)); } catch (e) { console.error('bad formSummary', e); }
        return;
    }
    if (attrs.formSuccess) {
        try { FormFlow.showSuccess(JSON.parse(attrs.formSuccess)); } catch (e) { console.error('bad formSuccess', e); }
        return;
    }

    if (messages.length === 0 && !attrs.formErrors) {
        renderBot({ type: 'text', text: "I didn't catch that. Could you try again?" });
        return;
    }
/**unpacks hidden buttons sent by the backend and attaches them directly underneath the very last text bubble in the chat. */
    let uiButtons = [];
    try { const raw = attrs.uiButtons; if (raw) uiButtons = JSON.parse(raw); } catch (e) { uiButtons = []; }

    messages.forEach((msg, idx) => {
        if (msg.contentType !== 'PlainText') return;
        const isLast = idx === messages.length - 1;
        if (isLast && uiButtons.length > 0) renderBot({ type: 'card', title: msg.content, buttons: uiButtons });
        else                                 renderBot({ type: 'text', text: msg.content });
    });
}

/* FORM RENDERER — dumb schema → HTML converter
   Field types supported: text, email, phone, select, chips, date-grid, time-grid.
   The Lambda decides labels, options, order and requiredness.*/
function appendChatForm(cardEl, slotId) {
    document.querySelectorAll('.chat-form-slot').forEach(n => n.remove());

    const box = $('messages');
    const row = document.createElement('div');
    row.className = 'row bot chat-form-slot';
    if (slotId) row.id = slotId;

    row.appendChild(buildAvatar());
    row.appendChild(cardEl);
    box.appendChild(row);
    scrollBottom();
}

/**Main function to render the form
 * Saves schema to state for later
 */
const FormRenderer = {
    build(schema) {
        state.formSchema = schema;
        state.formValues = {};

        const card = document.createElement('div');
        card.className = 'form-card chat-form-card';

        /**Title + progress bar */
        const header = document.createElement('div');
        header.className = 'form-header';
        header.innerHTML = `
            <p class="form-eyebrow">${esc(BOT_META[schema.botKey]?.label || 'Assistant')}</p>
            <div class="form-title">${esc(schema.title || 'Booking form')}</div>
            ${schema.subtitle ? `<div class="form-sub">${esc(schema.subtitle)}</div>` : ''}
            <div class="form-progress"><div class="form-progress-bar" id="formProgress"></div></div>
        `;
        card.appendChild(header);

        /**Form fields */
        const body = document.createElement('div');
        body.className = 'form-body';
        schema.fields.forEach(f => body.appendChild(this.buildField(f)));
        card.appendChild(body);

        /**cancel/continue buttons */
        const footer = document.createElement('div');
        footer.className = 'form-footer';
        footer.innerHTML = `
            <button class="form-btn secondary" onclick="FormFlow.cancel()">Cancel</button>
            <button class="form-btn primary" id="formSubmitBtn" onclick="FormFlow.submit()" disabled>Continue</button>
        `;                                                                       /**continue is disabled initially */
        card.appendChild(footer);

        appendChatForm(card, 'chatFormSlot');
        this.updateProgress();
    },
   /**Lambda backend sends the JSON blueprint, this function takes those instructions and physically builds that specific field piece-by-piece. */
   /**Label + Input + Hint + Error Box*/
buildField(field) {
        const wrap = document.createElement('div');
        wrap.className = 'form-field';
        wrap.dataset.name = field.name;
        
        // Hide standard label for checkboxes and video buttons
        if (field.type !== 'checkbox' && field.type !== 'video-button') {
            const label = document.createElement('label');
            label.className = 'form-label';
            label.innerHTML = `${esc(field.label)}${field.required ? ' <span class="req">*</span>' : ''}`;
            wrap.appendChild(label);
        }
        
        let input;
        switch (field.type) {
            case 'chips':       input = this.buildChips(field); break;
            case 'date-grid':   input = this.buildDateGrid(field); break;
            case 'time-grid':   input = this.buildTimeGrid(field); break;
            case 'select':      input = this.buildSelect(field); break;
            case 'checkbox':    input = this.buildCheckbox(field); break;     // NEW
            case 'video-button': input = this.buildVideoButton(field); break; // NEW
            case 'radio':       input = this.buildRadio(field); break;        // NEW
            default:            input = this.buildInput(field);
        }
        wrap.appendChild(input);
        
        if (field.hint) {
            const h = document.createElement('div');
            h.className = 'form-hint'; h.textContent = field.hint;
            wrap.appendChild(h);
        }
        const err = document.createElement('div');
        err.className = 'form-error-msg';
        wrap.appendChild(err);
        return wrap;
    },
    /**Creates a simple text/email/phone input */
    buildInput(field) {
        const el = document.createElement('input');
        if (field.type === 'file') {
            el.type = 'file';
            el.className = 'form-input file-input';
            el.accept = field.accept || '*/*';
            // Only send the file name string to AWS memory, not the whole file blob
            el.onchange = () => FormFlow.setValue(field.name, el.files[0] ? el.files[0].name : '');
        } else {
            el.className = 'form-input';
            el.type = (field.type === 'email') ? 'email' : (field.type === 'phone' ? 'tel' : 'text');
            el.placeholder = field.placeholder || '';
            if (field.maxLength) el.maxLength = field.maxLength;
            el.oninput = () => FormFlow.setValue(field.name, el.value);
        }
        return el;
    },
    
    /**selecting from options */
    buildSelect(field) {
        const el = document.createElement('select');
        el.className = 'form-select';
        el.innerHTML = `<option value="">Select…</option>` +
            (field.options || []).map(o => `<option value="${esc(o.value)}">${esc(o.text)}</option>`).join('');
        el.onchange = () => FormFlow.setValue(field.name, el.value);
        return el;
    },

    buildCheckbox(field) {
        const cWrap = document.createElement('div');
        cWrap.className = 'checkbox-group';
        cWrap.innerHTML = `
            <input type="checkbox" id="chk_${field.name}" name="${field.name}" class="checkbox-input" value="Yes" ${field.required ? 'required' : ''}>
            <label for="chk_${field.name}" class="checkbox-label">${esc(field.label)} ${field.required ? '<span class="req">*</span>' : ''}</label>
        `;
        const chk = cWrap.querySelector('input');
        chk.onchange = () => FormFlow.setValue(field.name, chk.checked ? 'Yes' : '');
        return cWrap;
    },

    buildVideoButton(field) {
        const vBtn = document.createElement('button');
        vBtn.type = 'button';
        vBtn.className = 'video-btn';
        vBtn.innerHTML = `▶ ${esc(field.label)}`;
        vBtn.onclick = () => window.open(field.url, '_blank');
        FormFlow.setValue(field.name, 'Clicked'); // Auto-fills state so it doesn't block the submit button
        return vBtn;
    },

    buildRadio(field) {
        const rWrap = document.createElement('div');
        rWrap.className = 'radio-group';
        (field.options || []).forEach((opt, idx) => {
            const rId = `radio_${field.name}_${idx}`;
            rWrap.innerHTML += `
                <input type="radio" id="${rId}" name="${field.name}" value="${opt}" class="radio-input">
                <label for="${rId}" class="radio-label">${esc(opt)}</label>
            `;
        });
        rWrap.querySelectorAll('input').forEach(radio => {
            radio.onchange = () => FormFlow.setValue(field.name, radio.value);
        });
        return rWrap;
    },

/**Creates selectable buttons (like product options: "Refrigerator", "TV", "Washing Machine") */
    buildChips(field) {
        const grid = document.createElement('div');
        grid.className = 'chip-grid';
        (field.options || []).forEach(o => {
            const b = document.createElement('button');
            b.type = 'button'; b.className = 'chip';
            b.textContent = o.text; b.dataset.value = o.value;
            b.onclick = () => {
                grid.querySelectorAll('.chip').forEach(c => c.classList.remove('selected'));
                b.classList.add('selected');
                FormFlow.setValue(field.name, o.value);
            };
            grid.appendChild(b);
        });
        return grid;
    },

    /**Creates a calendar-like grid of dates */
    buildDateGrid(field) {
        const grid = document.createElement('div');
        grid.className = 'date-grid';
        (field.options || []).forEach(o => {
            const parts = (o.text || '').split(/[, ]+/);
            const dow = parts[0] || '', mon = parts[1] || '', day = parts[2] || '';
            const card = document.createElement('button');
            card.type = 'button'; card.className = 'date-card';
            card.dataset.value = o.value;
            card.innerHTML = `<span class="dow">${esc(dow)}</span><span class="day">${esc(day)}</span><span class="mon">${esc(mon)}</span>`;
            card.onclick = () => {
                grid.querySelectorAll('.date-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                FormFlow.setValue(field.name, o.value);
            };
            grid.appendChild(card);
        });
        return grid;
    },
    /**Creates time slot buttons (like "09:00 AM", "10:00 AM", etc.) */
    buildTimeGrid(field) {
        const grid = document.createElement('div');
        grid.className = 'time-grid';
        (field.options || []).forEach(o => {
            const b = document.createElement('button');
            b.type = 'button'; b.className = 'time-btn';
            b.textContent = o.text; b.dataset.value = o.value;
            b.onclick = () => {
                grid.querySelectorAll('.time-btn').forEach(c => c.classList.remove('selected'));
                b.classList.add('selected');
                FormFlow.setValue(field.name, o.value);
            };
            grid.appendChild(b);
        });
        return grid;
    },

    /**
     * Progress bar + Submit button gating.
     * We ONLY check that required fields have a non-empty value — no format
     * checks, no regex, no product/date matching. The Lambda owns all real
     * validation and returns `formErrors` if anything is wrong.
     */
    updateProgress() {
        const schema = state.formSchema; if (!schema) return;
        const required = (schema.fields || []).filter(f => f.required);
        const isFilled = v => v !== null && v !== undefined && String(v).trim() !== '';
        const filled = required.filter(f => isFilled(state.formValues[f.name])).length;
        const pct = required.length ? Math.round((filled / required.length) * 100) : 100;
        const bar = $('formProgress'); if (bar) bar.style.width = pct + '%';
        const btn = $('formSubmitBtn'); if (btn) btn.disabled = pct < 100;
    },
    
    /**Shows error message below a field */
    showError(name, message) {
        const wrap = document.querySelector(`.form-field[data-name="${CSS.escape(name)}"]`);
        if (!wrap) return;
        wrap.classList.toggle('error', !!message);
        wrap.classList.toggle('valid', !message);
        const el = wrap.querySelector('.form-error-msg');
        if (el) el.textContent = message || '';
    },

    clearAllErrors() {
        document.querySelectorAll('.form-field').forEach(w => {
            w.classList.remove('error');
            const el = w.querySelector('.form-error-msg');
            if (el) el.textContent = '';
        });
    },
    
    /**Checkout screen */
    renderSummary(summary) {
        const card = document.createElement('div');
        card.className = 'form-card chat-form-card';
        const rows = (summary.rows || []).map(r =>
            `<div class="summary-row"><span class="k">${esc(r.label)}</span><span class="v">${esc(r.value)}</span></div>`
        ).join('');
        card.innerHTML = `
            <div class="form-header">
                <p class="form-eyebrow">Review</p>
                <div class="form-title">${esc(summary.title || 'Confirm your details')}</div>
                <div class="form-sub">${esc(summary.subtitle || 'Please check everything is correct.')}</div>
            </div>
            <div class="form-body"><div class="summary-card">${rows}</div></div>
            <div class="form-footer">
                <button class="form-btn secondary" onclick="FormFlow.editAgain()">Edit</button>
                <button class="form-btn primary" onclick="FormFlow.confirm()">Confirm booking</button>
            </div>`;
        appendChatForm(card, 'chatFormSlot');
    },
    
    /**final receipt */
    renderSuccess(res) {
        const card = document.createElement('div');
        card.className = 'form-card chat-form-card';
        card.innerHTML = `
            <div class="form-body">
                <div class="success-card">
                    <div class="success-icon">✓</div>
                    <div class="success-title">${esc(res.title || 'Booking confirmed!')}</div>
                    <div class="success-sub">${esc(res.message || 'Our executive will reach out shortly.')}</div>
                    ${res.referenceId ? `<div class="success-ref">Ref: ${esc(res.referenceId)}</div>` : ''}
                </div>
            </div>
            <div class="form-footer">
                <button class="form-btn primary" onclick="FormFlow.finishSuccess(this)">Done</button>
            </div>`;
        appendChatForm(card, 'chatFormSlot');
    }
};

/* FORM FLOW (workflow manager for the form)
   All decisions happen server-side; this just moves data around. */
const FormFlow = {
    openWithSchema(schema) { FormRenderer.build(schema); },
    /**Called when user fills any field */
    setValue(name, value) {
        state.formValues[name] = value;
        FormRenderer.updateProgress();
        // Clear any previous server-side error on this field once the user edits it.
        FormRenderer.showError(name, '');
    },

    /**user clicks continue and it creates payload and sends to lambda */
    async submit() {
        const btn = $('formSubmitBtn');
        if (btn) { btn.disabled = true; btn.textContent = 'Submitting…'; }
        FormRenderer.clearAllErrors();
        try {
            const payload = { bot: state.activeBot, values: state.formValues };
            const data = await callAPI('FORM_SUBMIT:' + JSON.stringify(payload));
            handleResponse(data);
        } catch (e) {
            console.error('form submit failed', e);
            renderBot({ type: 'text', text: '⚠ Could not submit the form. Please try again.' });
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = 'Continue'; }
        }
    },

    showErrors(errors) {
        Object.entries(errors || {}).forEach(([name, msg]) => FormRenderer.showError(name, msg));
    },
    
    /**review card before submission */
    showSummary(summary) {
        state.formSummary = summary;
        FormRenderer.renderSummary(summary);
    },

    editAgain() { if (state.formSchema) FormRenderer.build(state.formSchema); },

    /**called when booking is confirmed, lambda returns success message */
    async confirm() {
        try {
            const payload = { bot: state.activeBot, values: state.formValues, confirmed: true };
            const data = await callAPI('FORM_CONFIRM:' + JSON.stringify(payload));
            handleResponse(data);
        } catch (e) {
            console.error('form confirm failed', e);
            renderBot({ type: 'text', text: '⚠ Could not confirm the booking. Please try again.' });
        }
    },

    showSuccess(res) { FormRenderer.renderSuccess(res); },

    cancel() { this.close(); },
    /**clicked done */
    finishSuccess(btnEl) {
        document.querySelectorAll('.chat-form-slot').forEach(n => n.classList.remove('chat-form-slot'));
        if (btnEl) { btnEl.disabled = true; btnEl.textContent = 'Done ✓'; }
        state.formSchema = null;
        state.formValues = {};
        state.formSummary = null;
        renderBot({ type: 'text', text: "You're all set. Tap ↺ New Booking above if you'd like to book another consultation." });
    },

    close() {
        document.querySelectorAll('.chat-form-slot').forEach(n => n.remove());
        state.formSchema = null;
        state.formValues = {};
        state.formSummary = null;
    }
};

/* ═══════════════════════════════════════════════
   CHAT MANAGER
════════════════════════════════════════════════ */
const Chat = {
    async pickBot(botKey, btnEl) {
        document.querySelectorAll('.bot-pick-btn').forEach(b => b.disabled = true);
        state.activeBot = botKey;
        setBadge(botKey);
        renderUser(BOT_META[botKey].label);
        showTyping();
        state.loading = true;
        try {
            // 1) Tell the router which bot is active (unlocks the Lex path).
            const selectRes = await callAPI(`SELECT_BOT:${botKey}`);
            hideTyping();
            handleResponse(selectRes);

            // 2) Ask the business Lambda for its form schema.
            if (botKey === 'angel' || botKey === 'dhruv') {
                showTyping();
                const initRes = await callAPI(`INIT_${botKey.toUpperCase()}`);
                hideTyping();
                handleResponse(initRes);
            }
        } catch (e) {
            hideTyping();
            renderBot({ type: 'text', text: '⚠ Could not reach the server. Check your connection and try again.' });
            console.error(e);
        } finally {
            state.loading = false;
        }
    },

    send() {
        const inp  = $('userInput');
        const text = inp?.value.trim();
        if (!text || state.loading) return;
        inp.value = '';
        this.sendRaw(text, text);
    },

    async sendRaw(lexValue, displayText) {
        if (state.loading) return;
        state.loading = true;
        const inp = $('userInput'); const btn = $('sendBtn');
        if (inp) inp.disabled = true; if (btn) btn.disabled = true;
        if (displayText) renderUser(displayText);
        showTyping();
        try {
            const data = await callAPI(lexValue);
            hideTyping();
            handleResponse(data);
        } catch (e) {
            hideTyping();
            renderBot({ type: 'text', text: '⚠ Could not reach the server. Check your connection and try again.' });
            console.error('API error:', e);
        } finally {
            state.loading = false;
            if (inp) { inp.disabled = false; inp.focus(); }
            if (btn) btn.disabled = false;
        }
    },

    handleKey(e) { if (e.key === 'Enter') this.send(); },

    reset() { const m = $('restartModal'); if (m) m.style.display = 'flex'; },
    cancelRestart() { const m = $('restartModal'); if (m) m.style.display = 'none'; },
    confirmRestart() {
        const m = $('restartModal'); if (m) m.style.display = 'none';
        state.sessionId = makeId();
        state.activeBot = '';
        state.loading   = false;
        setBadge('');
        $('messages').innerHTML = '';
        FormFlow.close();
        addDateDivider();
        renderBot({ type: 'welcome' });
    }
};

window.addEventListener('DOMContentLoaded', () => {
    addDateDivider();
    renderBot({ type: 'welcome' });
});
