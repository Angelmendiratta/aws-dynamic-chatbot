"""
DhruvLambda.py — original Lex fulfillment PLUS dynamic-form handlers.
Same protocol as AngelLambda:
  event = { "formAction": "INIT"|"SUBMIT"|"CONFIRM",
            "bot": "dhruv", "sessionId": "...", "values": {...} }
"""
import json
import re
import datetime
import uuid

# --- MOCK DATABASE ---
BOOKED_APPOINTMENTS = {
    "2026-06-30": ["09:00", "14:00"],
    "2026-07-01": ["10:00", "15:00", "16:00"]
}

VALID_PRODUCTS = ["Refrigerator", "Television", "Washing Machine", "Dishwasher"]

# --- HELPER FUNCTIONS ---
def validate_phone(phone_number):
    if not phone_number: return False
    cleaned = ''.join(filter(str.isdigit, phone_number))
    return len(cleaned) == 10

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


# =====================================================================
# DYNAMIC FORM HANDLERS 
# =====================================================================

def _form_schema():
    valid_dates, button_days = get_business_days()
    date_options = button_days # Already formatted as [{"text": "...", "value": "..."}]

    product_options = [{"text": p, "value": p} for p in VALID_PRODUCTS]
    time_options = [{"text": t, "value": t} for t in ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]]

    return {
        "title": "Schedule Your Purchase Consultation",
        "submitLabel": "Confirm Booking",
        "botKey": "dhruv",
        "fields": [
            { "name": "firstName", "type": "text", "label": "First Name", "required": True },
            { "name": "lastName", "type": "text", "label": "Last Name", "required": True },
            { "name": "phone", "type": "phone", "label": "Phone Number", "placeholder": "10 digits", "required": True },
            { "name": "email", "type": "email", "label": "Email Address", "placeholder": "name@domain.com", "required": True },
            { "name": "demoVideo", "type": "video-button", "label": "Watch Form Tutorial (YouTube)", "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ" },
            { "name": "appliance", "type": "select", "label": "Select Product", "options": product_options, "required": True },
            { "name": "billImage", "type": "file", "label": "Upload Bill/Proof Image", "accept": "image/*" },
            { "name": "problem", "type": "text", "label": "Briefly describe the issue (optional)", "placeholder": "e.g., The fridge stopped cooling..." },
            { "name": "prefDate", "type": "select", "label": "Preferred Date", "options": date_options, "required": True },
            { "name": "prefTime", "type": "select", "label": "Preferred Time", "options": time_options, "required": True },
            { "name": "notifyPref", "type": "radio", "label": "How would you like your confirmation?", "options": ["📱 WhatsApp", "📧 Email", "Both"], "required": True },
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
    req("phone",        "Phone")
    req("email",        "Email")
    req("appliance",    "Product")
    req("prefDate",     "Date")
    req("prefTime",     "Time")

    phone = values.get("phone", "")
    if phone and not validate_phone(phone):
        errors["phone"] = "Enter exactly 10 digits."
    email = values.get("email", "")
    if email and not validate_email(email):
        errors["email"] = "Enter a valid email address."
    product = values.get("appliance", "")
    if product and product.lower() not in [p.lower() for p in VALID_PRODUCTS]:
        errors["appliance"] = "Unsupported product."
    date_str = values.get("prefDate", "")
    valid_dates, _ = get_business_days()
    if date_str and date_str not in valid_dates:
        errors["prefDate"] = "That date is unavailable."
    time_str = values.get("prefTime", "")
    if date_str and time_str:
        avail = get_available_times(date_str)
        requested_time = normalize_time(time_str)
        if not any(t["val_24h"] == requested_time for t in avail):
            errors["prefTime"] = "That time slot is no longer available."
    return errors


def _save_booking(values, session_id):
    """
    Persist the booking. Replace this stub with DynamoDB / RDS / SES calls.
    Returns a reference id.
    """
    ref = "DH-" + uuid.uuid4().hex[:8].upper()
    print(f"[dhruv] booking saved ref={ref} session={session_id} values={values}")
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
            session_attrs={"formSchema": json.dumps(schema)} # Matches your JS exactly
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
                {"label": "Phone",    "value": values.get("phone","")},
                {"label": "Email",    "value": values.get("email","")},
                {"label": "Product",  "value": values.get("appliance","")},
                {"label": "Date",     "value": values.get("prefDate","")},
                {"label": "Time",     "value": values.get("prefTime","")},
                {"label": "Notif",    "value": values.get("notifyPref","")}
            ]
        }
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
            "title":       "Booking confirmed!",
            "message":     "Our executive will call you at the scheduled time.",
            "referenceId": ref
        }
        return _form_response(session_attrs={"formSuccess": json.dumps(success)})

    return _form_response(messages=[{"contentType": "PlainText",
                                     "content": f"Unknown form action: {action}"}])


# =====================================================================
# LEX FULFILLMENT — free-text chat path (buttons + validation)
# =====================================================================

DHRUV_SLOT_ORDER = ["FirstName", "LastName", "PhoneNumber",
                    "Email", "ProductName", "PreferredDate", "PreferredTime"]

LEX_TO_FORM_FIELD = {
    "FirstName": "firstName",
    "LastName": "lastName",
    "PhoneNumber": "phone",
    "Email": "email",
    "ProductName": "appliance",
    "PreferredDate": "prefDate",
    "PreferredTime": "prefTime"
}

FORM_TO_LEX_SLOT = {form_name: slot_name for slot_name, form_name in LEX_TO_FORM_FIELD.items()}

def _slot_val(slots, name):
    s = slots.get(name) if slots else None
    if not s: return None
    val = s.get("value", {}) or {}
    return val.get("interpretedValue") or val.get("originalValue")

def _lex_values_to_form_values(slots):
    return {form_name: _slot_val(slots, slot_name)
            for slot_name, form_name in LEX_TO_FORM_FIELD.items()}

def _lex_error_slot(form_errors):
    for form_name in form_errors:
        slot_name = FORM_TO_LEX_SLOT.get(form_name)
        if slot_name:
            return slot_name
    return None

def _buttons_for(slot_name, slots):
    if slot_name == "ProductName":
        return [{"text": p, "value": p} for p in VALID_PRODUCTS]
    if slot_name == "PreferredDate":
        _, days = get_business_days()
        return days
    if slot_name == "PreferredTime":
        date_str = _slot_val(slots, "PreferredDate")
        if not date_str: return []
        return [{"text": t["text"], "value": t["text"]} for t in get_available_times(date_str)]
    return []

def _prompt_for(slot_name):
    return {
        "FirstName":    "What's your first name?",
        "LastName":     "And your last name?",
        "PhoneNumber":  "Please share a 10-digit phone number.",
        "Email":        "What's your email address?",
        "ProductName":  "Which product are you interested in?",
        "PreferredDate": "Which date works for you?",
        "PreferredTime": "Great — pick a time slot."
    }.get(slot_name, f"Please provide {slot_name}.")

def _validate_slot(name, value, slots):
    if value is None or str(value).strip() == "":
        return None
    if name == "PhoneNumber" and not validate_phone(value):
        return "That doesn't look like a valid 10-digit phone number."
    if name == "Email" and not validate_email(value):
        return "That doesn't look like a valid email address."
    if name == "ProductName":
        if value.lower() not in [p.lower() for p in VALID_PRODUCTS]:
            return f"'{value}' isn't a product we service. Please pick one below."
    if name == "PreferredDate":
        valid_dates, _ = get_business_days()
        if value not in valid_dates:
            return "That date isn't available. Please pick one below."
    if name == "PreferredTime":
        date_str = _slot_val(slots, "PreferredDate")
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
        {"text": "Yes, book it",   "value": "yes"},
        {"text": "No, cancel",     "value": "no"},
        {"text": "Change Product", "value": "change product"},
        {"text": "Change Date",    "value": "change date"},
        {"text": "Change Time",    "value": "change time"},
        {"text": "Change Phone",   "value": "change phone"},
        {"text": "Change Email",   "value": "change email"}
    ])
    intent["confirmationState"] = "None"
    intent["slots"] = slots
    summary = (f"Please confirm: {_slot_val(slots,'FirstName')} {_slot_val(slots,'LastName')}, "
               f"{_slot_val(slots,'ProductName')} on {_slot_val(slots,'PreferredDate')} at {_slot_val(slots,'PreferredTime')} "
               f"(phone {_slot_val(slots,'PhoneNumber')}, email {_slot_val(slots,'Email')}).")
    return {
        "sessionState": {
            "dialogAction": {"type": "ConfirmIntent"},
            "intent": intent,
            "sessionAttributes": attrs
        },
        "messages": [{"contentType": "PlainText", "content": summary}]
    }

_EDIT_KEYWORDS = {
    "change product": "ProductName", "edit product": "ProductName",
    "change date":    "PreferredDate", "edit date":  "PreferredDate",
    "change time":    "PreferredTime", "edit time":  "PreferredTime",
    "change phone":   "PhoneNumber", "edit phone":   "PhoneNumber",
    "change email":   "Email",       "edit email":   "Email",
    "change name":    "FirstName",   "edit name":    "FirstName"
}
_CONFIRM_YES = {"yes", "yes, book it", "book it", "confirm", "confirmed", "ok", "okay"}
_CONFIRM_NO = {"no", "no, cancel", "cancel", "cancel booking", "stop"}

def _all_slots_filled(slots):
    return all(_slot_val(slots, name) is not None for name in DHRUV_SLOT_ORDER)

def _close_confirmed(intent, slots, session_attrs, session_id):
    values = _lex_values_to_form_values(slots)
    errors = _validate_form(values)
    if errors:
        first_bad = _lex_error_slot(errors)
        if not first_bad:
            return _elicit(intent, slots, "FirstName", "Some details are invalid. Let's check them again.", session_attrs)
        slots[first_bad] = None
        return _elicit(intent, slots, first_bad, errors.get(LEX_TO_FORM_FIELD[first_bad], _prompt_for(first_bad)), session_attrs)

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
                      "content": f"Your booking is confirmed! Reference {ref}. Our executive will call you."}]
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
            if _all_slots_filled(slots):
                if input_transcript in _CONFIRM_YES or intent.get('confirmationState') == 'Confirmed':
                    return _close_confirmed(intent, slots, session_attributes, event.get('sessionId', ''))
                if input_transcript in _CONFIRM_NO or intent.get('confirmationState') == 'Denied':
                    return _close_cancelled(intent)

            if input_transcript in _EDIT_KEYWORDS:
                target = _EDIT_KEYWORDS[input_transcript]
                slots[target] = None
                return _elicit(intent, slots, target, _prompt_for(target), session_attributes)

            for name in DHRUV_SLOT_ORDER:
                val = _slot_val(slots, name)
                err = _validate_slot(name, val, slots)
                if err:
                    slots[name] = None
                    return _elicit(intent, slots, name, err, session_attributes)

            for name in DHRUV_SLOT_ORDER:
                if _slot_val(slots, name) is None:
                    return _elicit(intent, slots, name, _prompt_for(name), session_attributes)

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
