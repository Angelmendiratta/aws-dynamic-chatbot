import json
import re
import datetime
import uuid
import os

# --- DEMO VIDEO CONFIG (env-driven; nothing hardcoded on the frontend) ---
DEMO_VIDEO_URL    = os.environ.get("DEMO_VIDEO_URL", "")
DEMO_MESSAGE      = os.environ.get(
    "DEMO_MESSAGE",
    "Here's a short demo — tap below to play it right here in the chat."
)
DEMO_BUTTON_LABEL = os.environ.get("DEMO_BUTTON_LABEL", "Watch demo")
DEMO_TRIGGERS     = [t.strip().lower() for t in os.environ.get(
    "DEMO_TRIGGERS",
    "demo,show demo,show me a demo,video,tutorial,show tutorial,how does this work,how to use"
).split(",") if t.strip()]
def _is_demo_request(text):
    if not text: return False
    t = text.strip().lower()
    return any(trig in t for trig in DEMO_TRIGGERS)

# --- PRODUCT CATALOG (matches Krishna's custom slot type "CompanyProducts") ---
VALID_PRODUCTS = [
    "Cloud Architecture & Migration",
    "Enterprise Solutions",
    "Cloud Messaging",
    "AI & ML Integration"
]

# --- Follow-up questions per product (feeds productFollowUp1 / productFollowUp2) ---
DYNAMIC_QUESTIONS = {
    "cloud architecture & migration": {
        "q1": "Which primary cloud platform are you targeting?",
        "q1_opts": [("Amazon Web Services (AWS)", "AWS"), ("Microsoft Azure", "Azure"), ("Google Cloud (GCP)", "GCP")],
        "q2": "When do you plan to begin migration?",
        "q2_opts": [("Immediate (within 1 month)", "Immediate"), ("Next 3 months", "3 Months"), ("Next 6 months+", "6 Months Plus")]
    },
    "enterprise solutions": {
        "q1": "Which industry sector are you in?",
        "q1_opts": [("Retail & E-Commerce", "Retail"), ("Banking & Finance", "Finance"), ("Healthcare & Pharma", "Healthcare"), ("Logistics & Supply", "Logistics")],
        "q2": "Roughly how many users will need access?",
        "q2_opts": [("1-50 users", "Small"), ("51-250 users", "Medium"), ("251-1000 users", "Large"), ("1000+ users", "Enterprise")]
    },
    "cloud messaging": {
        "q1": "Which messaging channel do you need?",
        "q1_opts": [("Transactional SMS", "SMS"), ("WhatsApp Business API", "WhatsApp"), ("Bulk email", "Email")],
        "q2": "What's your estimated monthly volume?",
        "q2_opts": [("Under 10k messages", "Low"), ("10k-100k messages", "Medium"), ("100k-1M messages", "High"), ("1M+ messages", "Massive")]
    },
    "ai & ml integration": {
        "q1": "What kind of AI system are you deploying?",
        "q1_opts": [("Customer support chatbot", "Chatbot"), ("Predictive sales analytics", "Predictive"), ("Computer vision", "Vision")],
        "q2": "Where is your training data currently hosted?",
        "q2_opts": [("SQL/NoSQL databases", "Database"), ("Cloud storage (S3/Blob)", "Cloud"), ("Local Excel/CSV files", "Files")]
    }
}

# --- MOCK DATABASE ---
BOOKED_APPOINTMENTS = {
    "2026-06-30": ["09:00", "14:00"],
    "2026-07-01": ["10:00", "15:00", "16:00"]
}

# --- HELPER FUNCTIONS ---
def validate_phone(phone_number):
    if not phone_number: return False
    phone_str = str(phone_number)
    if any(c.isalpha() for c in phone_str):
        return False
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone_str)
    return cleaned.isdigit() and len(cleaned) == 10

def validate_email(email_address):
    if not email_address: return False
    regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(regex, email_address))

def get_business_days():
    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    current_date = ist_now.date()
    if ist_now.hour >= 17:
        current_date += datetime.timedelta(days=1)
    valid_days = []
    button_days = []
    lookahead = 0
    while len(valid_days) < 30 and lookahead < 60:
        if current_date.weekday() < 5:
            date_str = current_date.strftime("%Y-%m-%d")
            available_times = get_available_times(date_str)
            if len(available_times) > 0:
                valid_days.append(date_str)
                if len(button_days) < 15:
                    button_days.append({
                        "text": current_date.strftime("%a, %b %d"),
                        "value": date_str
                    })
        current_date += datetime.timedelta(days=1)
        lookahead += 1
    return valid_days, button_days

def get_available_times(date_str):
    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    is_today = (date_str == ist_now.strftime("%Y-%m-%d"))
    current_hour = ist_now.hour
    booked_times = BOOKED_APPOINTMENTS.get(date_str, [])
    all_times = []
    for h in range(9, 18):
        if is_today and h <= current_hour: continue
        val_24h = f"{str(h).zfill(2)}:00"
        if val_24h in booked_times: continue
        ampm = "AM" if h < 12 else "PM"
        display_h = h if h <= 12 else h - 12
        text_12h = f"{str(display_h).zfill(2)}:00 {ampm}"
        all_times.append({"text": text_12h, "value": text_12h, "val_24h": val_24h})
    return all_times

def normalize_time(raw):
    if not raw: return ""
    raw = raw.strip()
    match_24 = re.match(r'^(\d{1,2}):(\d{2})(?::\d{2})?$', raw)
    if match_24: return f"{int(match_24.group(1)):02d}:{match_24.group(2)}"
    match_12 = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM)$', raw, re.IGNORECASE)
    if match_12:
        h = int(match_12.group(1)); m = match_12.group(2); period = match_12.group(3).upper()
        if period == "AM": h = 0 if h == 12 else h
        else: h = 12 if h == 12 else h + 12
        return f"{h:02d}:{m}"
    return raw

def _dyn_for(product):
    if not product: return None
    return DYNAMIC_QUESTIONS.get(product.strip().lower())


# =====================================================================
# DYNAMIC FORM HANDLERS (used by the web form UI, independent of Lex slots)
# =====================================================================

def _form_schema():
    valid_dates, button_days = get_business_days()
    date_options = button_days
    product_options = [{"text": p, "value": p} for p in VALID_PRODUCTS]
    time_options = [{"text": t, "value": t} for t in ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]]
 
    return {
        "title": "Schedule Your Product Consultation",
        "submitLabel": "Confirm Booking",
        "botKey": "krishna",
        "fields": [
            { "name": "firstName", "type": "text", "label": "First Name", "required": True },
            { "name": "lastName", "type": "text", "label": "Last Name", "required": True },
            { "name": "phoneNumber", "type": "tel", "label": "Phone Number", "placeholder": "10 digits", "required": True },
            { "name": "email", "type": "email", "label": "Email Address", "placeholder": "name@domain.com", "required": True },
            { "name": "productName", "type": "select", "label": "Select Product / Service", "options": product_options, "required": True },
            { "name": "message", "type": "text", "label": "Briefly describe your requirement (optional)", "placeholder": "e.g., Looking to migrate our ERP to AWS..." },
            { "name": "preferredDate", "type": "select", "label": "Preferred Call Date (optional)", "options": date_options },
            { "name": "preferredTime", "type": "select", "label": "Preferred Call Time (optional)", "options": time_options },
            { "name": "tnc", "type": "checkbox", "label": "I agree to the Terms & Conditions", "required": True }
        ]
    }
 
 
def _validate_form(values):
    errors = {}
    def req(name, label):
        if not values.get(name) or not str(values[name]).strip():
            errors[name] = f"{label} is required."
 
    req("firstName",    "First name")
    req("lastName",     "Last name")
    req("phoneNumber",  "Phone")
    req("email",        "Email")
    req("productName",  "Product")
 
    phone = values.get("phoneNumber", "")
    if phone and not validate_phone(phone):
        errors["phoneNumber"] = "Enter exactly 10 digits."
    email = values.get("email", "")
    if email and not validate_email(email):
        errors["email"] = "Enter a valid email address."
    product = values.get("productName", "")
    if product and product.lower() not in [p.lower() for p in VALID_PRODUCTS]:
        errors["productName"] = "Unsupported product."
 
    # setupCall (Lex-only) still gates date/time there. For the web form,
    # there's no setupCall question — date/time are simply optional fields;
    # if the user picked one, validate it regardless.
    if "setupCall" in values:
        req("setupCall", "Call preference")
        wants_call = str(values.get("setupCall", "")).strip().lower() == "yes"
        if wants_call:
            date_str = values.get("preferredDate", "")
            valid_dates, _ = get_business_days()
            if not date_str:
                errors["preferredDate"] = "Date is required."
            elif date_str not in valid_dates:
                errors["preferredDate"] = "That date is unavailable."
            time_str = values.get("preferredTime", "")
            if not time_str:
                errors["preferredTime"] = "Time is required."
            elif date_str:
                avail = get_available_times(date_str)
                requested_time = normalize_time(time_str)
                if not any(t["val_24h"] == requested_time for t in avail):
                    errors["preferredTime"] = "That time slot is no longer available."
    else:
        date_str = values.get("preferredDate", "")
        time_str = values.get("preferredTime", "")
        if date_str or time_str:
            valid_dates, _ = get_business_days()
            if date_str and date_str not in valid_dates:
                errors["preferredDate"] = "That date is unavailable."
            if time_str and date_str:
                avail = get_available_times(date_str)
                requested_time = normalize_time(time_str)
                if not any(t["val_24h"] == requested_time for t in avail):
                    errors["preferredTime"] = "That time slot is no longer available."
            elif time_str and not date_str:
                errors["preferredDate"] = "Please also pick a date for your preferred time."
    return errors

def _save_booking(values, session_id):
    """
    Persist the booking. Replace this stub with DynamoDB / RDS / SES calls.
    Returns a reference id.
    """
    ref = "CL-" + uuid.uuid4().hex[:8].upper()
    print(f"[krishna] booking saved ref={ref} session={session_id} values={values}")
    return ref
 
 
def _form_response(messages=None, session_attrs=None):
    return {
        "messages": messages or [],
        "sessionAttributes": session_attrs or {}
    }
 
 
def handle_form_event(event):
    action = event.get("formAction")
    if not action and event.get("invocationSource") == "FastLane":
        action = event.get("request", {}).get("type")
    action = (action or "").upper()
 
    values = event.get("values")
    if not values and event.get("invocationSource") == "FastLane":
        values = event.get("request", {}).get("data")
    values = values or {}
 
    session_id = event.get("sessionId", "")
 
    if action == "INIT":
        schema = _form_schema()
        return _form_response(
            messages=[{"contentType": "PlainText",
                       "content": "Please fill in the form below to book your consultation."}],
            session_attrs={"formSchema": json.dumps(schema)}
        )
 
    if action == "SUBMIT":
        errors = _validate_form(values)
        if errors:
            return _form_response(
                messages=[{"contentType": "PlainText",
                           "content": "Please fix the highlighted fields."}],
                session_attrs={"formErrors": json.dumps(errors)}
            )
 
        summary = {
            "title": "Confirm your consultation",
            "subtitle": "Review the details before we book.",
            "rows": [
                {"label": "Name",     "value": f"{values.get('firstName','').title()} {values.get('lastName','').title()}"},
                {"label": "Phone",    "value": values.get("phoneNumber","")},
                {"label": "Email",    "value": values.get("email","")},
                {"label": "Product",  "value": values.get("productName","")},
                {"label": "Notes",    "value": values.get("message","") or "—"}
            ]
        }
        if values.get("preferredDate") or values.get("preferredTime"):
            summary["rows"].append({"label": "Preferred Date", "value": values.get("preferredDate","") or "—"})
            summary["rows"].append({"label": "Preferred Time", "value": values.get("preferredTime","") or "—"})
        return _form_response(session_attrs={"formSummary": json.dumps(summary)})
 
    if action == "CONFIRM":
        errors = _validate_form(values)
        if errors:
            return _form_response(
                messages=[{"contentType": "PlainText",
                           "content": "Some details are no longer valid. Please review the form again."}],
                session_attrs={"formErrors": json.dumps(errors)}
            )
        ref = _save_booking(values, session_id)
        success = {
            "title":       "Inquiry submitted!",
            "message":     "Our consultant will review your requirements and get back to you shortly.",
            "referenceId": ref
        }
        return _form_response(session_attrs={"formSuccess": json.dumps(success)})
 
    return _form_response(messages=[{"contentType": "PlainText",
                                     "content": f"Unknown form action: {action}"}])


# =====================================================================
# LEX FULFILLMENT — free-text chat path (buttons + validation)
# Slot names below match Krishna's ACTUAL Lex bot exactly (camelCase, 11 slots).
# =====================================================================

KRISHNA_BASE_SLOTS = ["firstName", "lastName", "phoneNumber", "email",
                      "productName", "message", "setupCall"]
KRISHNA_CALL_SLOTS = ["preferredDate", "preferredTime"]

def _slot_val(slots, name):
    s = slots.get(name) if slots else None
    if not s: return None
    val = s.get("value", {}) or {}
    return val.get("interpretedValue") or val.get("originalValue")

def _wants_call(slots):
    v = _slot_val(slots, "setupCall")
    return (v or "").strip().lower() == "yes"

def _active_slot_order(slots):
    """
    productFollowUp1/2 only apply once a product is picked (and only if that
    product has follow-up questions defined). preferredDate/Time only apply
    if the user opted into a call via setupCall.
    """
    order = list(KRISHNA_BASE_SLOTS)
    product = _slot_val(slots, "productName")
    dyn = _dyn_for(product)
    if product and dyn:
        idx = order.index("productName") + 1
        order[idx:idx] = ["productFollowUp1", "productFollowUp2"]
    if _wants_call(slots):
        order += KRISHNA_CALL_SLOTS
    return order

def _lex_values_to_form_values(slots):
    return {
        "firstName":     _slot_val(slots, "firstName"),
        "lastName":      _slot_val(slots, "lastName"),
        "phoneNumber":   _slot_val(slots, "phoneNumber"),
        "email":         _slot_val(slots, "email"),
        "productName":   _slot_val(slots, "productName"),
        "message":       _slot_val(slots, "message"),
        "setupCall":     _slot_val(slots, "setupCall"),
        "preferredDate": _slot_val(slots, "preferredDate"),
        "preferredTime": _slot_val(slots, "preferredTime"),
    }

def _lex_error_slot(form_errors):
    for name in ["firstName", "lastName", "phoneNumber", "email",
                 "productName", "setupCall", "preferredDate", "preferredTime"]:
        if name in form_errors:
            return name
    return None

def _buttons_for(slot_name, slots):
    if slot_name == "productName":
        return [{"text": p, "value": p} for p in VALID_PRODUCTS]
    if slot_name == "productFollowUp1":
        dyn = _dyn_for(_slot_val(slots, "productName"))
        if not dyn: return []
        return [{"text": t, "value": v} for t, v in dyn["q1_opts"]]
    if slot_name == "productFollowUp2":
        dyn = _dyn_for(_slot_val(slots, "productName"))
        if not dyn: return []
        return [{"text": t, "value": v} for t, v in dyn["q2_opts"]]
    if slot_name == "setupCall":
        return [{"text": "Yes", "value": "Yes"}, {"text": "No", "value": "No"}]
    if slot_name == "preferredDate":
        _, days = get_business_days()
        return days
    if slot_name == "preferredTime":
        date_str = _slot_val(slots, "preferredDate")
        if not date_str: return []
        return [{"text": t["text"], "value": t["text"]} for t in get_available_times(date_str)]
    return []

def _prompt_for(slot_name, slots):
    if slot_name == "productFollowUp1":
        dyn = _dyn_for(_slot_val(slots, "productName"))
        return dyn["q1"] if dyn else "Please select an option for your first product question."
    if slot_name == "productFollowUp2":
        dyn = _dyn_for(_slot_val(slots, "productName"))
        return dyn["q2"] if dyn else "Please select an option for your second product question."
    return {
        "firstName":     "What's your first name?",
        "lastName":      "And your last name?",
        "phoneNumber":   "Please share a 10-digit phone number.",
        "email":         "What's your email address?",
        "productName":   "Which product or service are you inquiring about?",
        "message":       "Please enter your message or notes.",
        "setupCall":     "Would you like to set up a call? (Yes/No)",
        "preferredDate": "Which date works for you?",
        "preferredTime": "Great — pick a time slot."
    }.get(slot_name, f"Please provide {slot_name}.")

def _validate_slot(name, value, slots):
    if value is None or str(value).strip() == "":
        return None
    if name == "phoneNumber" and not validate_phone(value):
        return "That doesn't look like a valid 10-digit phone number."
    if name == "email" and not validate_email(value):
        return "That doesn't look like a valid email address."
    if name == "productName":
        if value.lower() not in [p.lower() for p in VALID_PRODUCTS]:
            return f"'{value}' isn't a service we offer. Please pick one below."
    if name == "setupCall":
        if value.strip().lower() not in ("yes", "no"):
            return "Please answer Yes or No."
    if name == "preferredDate":
        valid_dates, _ = get_business_days()
        if value not in valid_dates:
            return "That date isn't available. Please pick one below."
    if name == "preferredTime":
        date_str = _slot_val(slots, "preferredDate")
        if date_str:
            avail = get_available_times(date_str)
            requested_time = normalize_time(value)
            if not any(t["val_24h"] == requested_time for t in avail):
                return "That time slot isn't available. Please pick one below."
    return None

def _elicit(intent, slots, slot_name, message, session_attrs):
    buttons = _buttons_for(slot_name, slots)
    attrs = dict(session_attrs or {})
    attrs["uiButtons"] = json.dumps(buttons)
    intent["slots"] = slots
    return {
        "sessionState": {
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": slot_name},
            "intent": intent,
            "sessionAttributes": attrs
        },
        "messages": [{"contentType": "PlainText", "content": message}]
    }

def _confirm_prompt(intent, slots, session_attrs):
    attrs = dict(session_attrs or {})
    attrs["uiButtons"] = json.dumps([
        {"text": "Yes, submit it",  "value": "yes"},
        {"text": "No, cancel",      "value": "no"},
        {"text": "Change Product",  "value": "change product"},
        {"text": "Change Phone",    "value": "change phone"},
        {"text": "Change Email",    "value": "change email"}
    ])
    intent["confirmationState"] = "None"
    intent["slots"] = slots
    call_part = ""
    if _wants_call(slots):
        call_part = f" A call is requested on {_slot_val(slots,'preferredDate')} at {_slot_val(slots,'preferredTime')}."
    summary = (f"Please confirm: {_slot_val(slots,'firstName')} {_slot_val(slots,'lastName')}, "
               f"interested in {_slot_val(slots,'productName')} "
               f"(phone {_slot_val(slots,'phoneNumber')}, email {_slot_val(slots,'email')}).{call_part}")
    return {
        "sessionState": {
            "dialogAction": {"type": "ConfirmIntent"},
            "intent": intent,
            "sessionAttributes": attrs
        },
        "messages": [{"contentType": "PlainText", "content": summary}]
    }

_EDIT_KEYWORDS = {
    "change product": "productName", "edit product": "productName",
    "change date":     "preferredDate", "edit date":  "preferredDate",
    "change time":     "preferredTime", "edit time":  "preferredTime",
    "change phone":    "phoneNumber",   "edit phone": "phoneNumber",
    "change email":    "email",         "edit email": "email",
    "change name":     "firstName",     "edit name":  "firstName"
}
_CONFIRM_YES = {"yes", "yes, submit it", "submit it", "confirm", "confirmed", "ok", "okay"}
_CONFIRM_NO = {"no", "no, cancel", "cancel", "cancel booking", "stop"}

def _all_slots_filled(slots):
    order = _active_slot_order(slots)
    return all(_slot_val(slots, name) is not None for name in order)

def _close_confirmed(intent, slots, session_attrs, session_id):
    values = _lex_values_to_form_values(slots)
    errors = _validate_form(values)
    if errors:
        first_bad = _lex_error_slot(errors)
        if not first_bad:
            return _elicit(intent, slots, "firstName", "Some details are invalid. Let's check them again.", session_attrs)
        slots[first_bad] = None
        return _elicit(intent, slots, first_bad, errors.get(first_bad, _prompt_for(first_bad, slots)), session_attrs)

    ref = _save_booking(values, session_id)
    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {"name": intent.get('name'), "state": "Fulfilled"},
            "sessionAttributes": {
                "uiButtons": json.dumps([
                    {"text": "Need More Assistance?",
                     "value": "https://www.icloudy.co/icloudy-contact-us/"}
                ])
            }
        },
        "messages": [{"contentType": "PlainText",
                      "content": f"Your inquiry is confirmed! Reference {ref}. Our consultant will be in touch."}]
    }

def _close_cancelled(intent):
    return {
        "sessionState": {
            "dialogAction": {"type": "Close"},
            "intent": {"name": intent.get('name'), "state": "Fulfilled"},
            "sessionAttributes": {
                "uiButtons": json.dumps([
                    {"text": "Need More Assistance?",
                     "value": "https://www.icloudy.co/icloudy-contact-us/"}
                ])
            }
        },
        "messages": [{"contentType": "PlainText",
                      "content": "No problem, I've canceled the process. Let me know if you need anything else!"}]
    }

def _demo_interject(intent, slots, session_attrs):
    """
    Show the demo message + Watch-demo button without changing dialog state.
    """
    order = _active_slot_order(slots)
    pending = None
    for name in order:
        if _slot_val(slots, name) is None:
            pending = name
            break
    if pending is None:
        pending = "firstName"
    attrs = dict(session_attrs or {})
    attrs["uiButtons"] = json.dumps([
        {"text": DEMO_BUTTON_LABEL, "action": "playVideo", "url": DEMO_VIDEO_URL}
    ])
    intent["slots"] = slots
    return {
        "sessionState": {
            "dialogAction": {"type": "ElicitSlot", "slotToElicit": pending},
            "intent": intent,
            "sessionAttributes": attrs
        },
        "messages": [{"contentType": "PlainText", "content": DEMO_MESSAGE}]
    }


def lambda_handler(event, context):
    # ---- Dynamic-form bypass ----
    if isinstance(event, dict) and (event.get("formAction") or event.get("invocationSource") == "FastLane"):
        return handle_form_event(event)

    # ---- Lex flow ----
    try:
        session_state = event.get('sessionState', {})
        intent = session_state.get('intent', {})
        slots = intent.get('slots', {}) or {}
        invocation_source = event.get('invocationSource')
        session_attributes = session_state.get('sessionAttributes', {}) or {}
        input_transcript = (event.get('inputTranscript') or '').strip().lower()

        print(f"=== KRISHNA LAMBDA CALLED ===")
        print(f"Invocation Source: {event.get('invocationSource')}")
        print(f"Input Transcript: {event.get('inputTranscript')}")
        print(f"Slots: {json.dumps(event.get('sessionState', {}).get('intent', {}).get('slots', {}))}")
        print(f"Session Attributes: {json.dumps(event.get('sessionState', {}).get('sessionAttributes', {}))}")
        print(f"===========================")

        if intent.get('name') == 'CancelBooking':
            return {
                "sessionState": {
                    "dialogAction": {"type": "Close"},
                    "intent": {"name": intent.get('name'), "state": "Fulfilled"},
                    "sessionAttributes": {
                        "uiButtons": json.dumps([
                            {"text": "Need More Assistance?",
                             "value": "https://www.icloudy.co/icloudy-contact-us/"}
                        ])
                    }
                },
                "messages": [{"contentType": "PlainText",
                              "content": "No problem, I've canceled the process. Let me know if you need anything else!"}]
            }

        if invocation_source == 'DialogCodeHook':
            if _is_demo_request(input_transcript):
                return _demo_interject(intent, slots, session_attributes)

            if _all_slots_filled(slots):
                if input_transcript in _CONFIRM_YES or intent.get('confirmationState') == 'Confirmed':
                    return _close_confirmed(intent, slots, session_attributes, event.get('sessionId', ''))
                if input_transcript in _CONFIRM_NO or intent.get('confirmationState') == 'Denied':
                    return _close_cancelled(intent)

            if input_transcript in _EDIT_KEYWORDS:
                target = _EDIT_KEYWORDS[input_transcript]
                slots[target] = None
                return _elicit(intent, slots, target, _prompt_for(target, slots), session_attributes)

            active_order = _active_slot_order(slots)

            for name in active_order:
                val = _slot_val(slots, name)
                err = _validate_slot(name, val, slots)
                if err:
                    slots[name] = None
                    return _elicit(intent, slots, name, err, session_attributes)

            for name in active_order:
                if _slot_val(slots, name) is None:
                    return _elicit(intent, slots, name, _prompt_for(name, slots), session_attributes)

            return _confirm_prompt(intent, slots, session_attributes)

        if invocation_source == 'FulfillmentCodeHook':
            return _close_confirmed(intent, slots, session_attributes, event.get('sessionId', ''))

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {
            "sessionState": {
                "dialogAction": {"type": "Delegate"},
                "intent": event.get('sessionState', {}).get('intent', {})
            }
        }
