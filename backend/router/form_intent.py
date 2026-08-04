"""
form_intent.py — decides WHICH booking form a free-text message wants.

Used by the router Lambda so the user never has to click an assistant button:
they just say what they need ("I want to book a consultation call", "I need
pricing for a new fridge", "can you help us migrate to AWS?") and the router
opens the matching form after a quick yes/no confirmation.

Mapping
    angel    product / appliance consultation
    dhruv    sales leads, purchase help, callbacks about buying
    krishna  services: cloud computing, migration, technical support

Two passes:
    1. keyword scoring (free, instant, predictable)
    2. Gemini classification (only when keywords find nothing)

Pure stdlib. Reuses gemini_faq's HTTP helper and GEMINI_API_KEY, so there is
nothing new to configure. With no key the keyword pass plus a clarifying
question still cover the flow.
"""

import os
import re

import gemini_faq

BOTS = ("angel", "dhruv", "krishna")

# Human wording used in confirmation questions.
BOT_LABELS = {
    "angel":   "product consultation",
    "dhruv":   "sales / purchase call",
    "krishna": "cloud & IT services request",
}

# --------------------------------------------------------------------
# 1) Keyword pass
# --------------------------------------------------------------------

_PRODUCT_NOUNS = (
    "appliance", "refrigerator", "fridge", "washing machine", "washer",
    "dishwasher", "microwave", "oven", "air conditioner", "ac unit",
    "television", "tv", "laptop", "printer", "geyser", "water purifier",
)

# Angel = advice / service on a product you already have or are unsure about.
_KEYWORDS = {
    "angel": (
        "consultation", "consultancy", "consult", "consulting call",
        "product advice", "advice", "advise", "product help", "guidance",
        "which product", "which one should", "compare", "comparison",
        "recommend", "recommendation", "suggest", "help me choose",
        "maintenance", "servicing", "installation", "install", "repair",
        "warranty", "amc", "about product", "product about", "what product", "about your products",
    ),
    "dhruv": (
        "buy", "buying", "purchase", "price", "pricing", "cost", "quote",
        "quotation", "sales", "sale", "discount", "offer", "plan cost",
        "call me back", "callback", "call back", "talk to sales", "lead",
        "invoice", "payment", "subscription", "order", "book a fridge",
        "new fridge", "want a", "need a", "looking for a", "get a",
    ) + _PRODUCT_NOUNS,
    "krishna": (
        "cloud", "aws", "amazon web services", "azure", "gcp", "migration",
        "migrate", "devops", "server", "hosting", "database", "backup",
        "security", "cyber", "it support", "technical support", "support",
        "service request", "not working", "issue", "error", "downtime",
        "infrastructure", "kubernetes", "docker", "it", "information technology",
    ),
}


# Wording that clearly wants a booking but names no area at all.
_GENERIC_BOOKING = (
    "book", "booking", "appointment", "schedule", "reschedule", "meeting",
    "connect me", "talk to someone", "speak to", "agent", "executive",
    "i need help", "need assistance", "contact",
)

# Slot-shaped values must never trigger form classification.
_SLOT_RES = (
    re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    re.compile(r"^[+\d][\d\s\-()]{6,}$"),
    re.compile(r"^\d{1,2}[/\-.]\d{1,2}([/\-.]\d{2,4})?$"),
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^\d{1,2}(:\d{2})?\s*(am|pm)?$", re.I),
    re.compile(r"^(mon|tue|wed|thu|thur|thurs|fri|sat|sun)[a-z,]*[\s\d].*$", re.I),
)

_YES = {"yes", "y", "yeah", "yep", "yup", "ok", "okay", "sure", "please do",
        "go ahead", "correct", "right", "confirm", "confirmed", "open it",
        "open the form", "do it"}

_NO = {"no", "n", "nope", "nah", "not now", "later", "cancel", "stop",
       "something else", "no thanks", "no thank you"}

# Buying language that decides the area on its own.
_DECISIVE_SALES = (
    "buy", "buying", "purchase", "price", "pricing", "quote", "quotation",
    "cost", "discount", "talk to sales", "want a", "want to get",
    "need a", "looking for a", "order",
)

# Advice / servicing language that decides the consultation form on its own.
_DECISIVE_CONSULT = (
    "consultation", "consult", "advice", "advise", "recommend", "suggest",
    "which one", "which product", "compare", "help me choose",
    "installation", "install", "maintenance", "servicing", "repair",
)


# Courtesy / small talk that should never reach Lex or open a form.
_SMALLTALK = {
    "thanks": "You're welcome!",
    "thank you": "You're welcome!",
    "thankyou": "You're welcome!",
    "thanks a lot": "You're welcome!",
    "thank you so much": "Happy to help!",
    "ty": "You're welcome!",
    "great": "Glad that works!",
    "cool": "Glad that works!",
    "nice": "Glad that works!",
    "awesome": "Glad that works!",
    "bye": "Goodbye — have a great day!",
    "goodbye": "Goodbye — have a great day!",
    "see you": "See you soon!",
    "good night": "Good night!",
}

_DEMO_WORDS = ("demo", "demo video", "tutorial", "how it works video",
               "show me a video", "watch video", "video")


def smalltalk_reply(text):
    """Return a friendly reply for pure courtesy messages, else None."""
    key = (text or "").strip().strip("!.,?").lower()
    return _SMALLTALK.get(key)


def wants_demo(text):
    """True when the user is asking to see the demo video."""
    low = " {} ".format((text or "").strip().lower())
    return any(" {} ".format(w) in low for w in _DEMO_WORDS)


def is_yes(text):
    return (text or "").strip().strip("!.?").lower() in _YES


def is_no(text):
    return (text or "").strip().strip("!.?").lower() in _NO


def _looks_like_slot_value(raw):
    return any(rx.match(raw) for rx in _SLOT_RES)



def keyword_match(text):
    """Return (bot | None, generic_booking_bool) from the keyword pass."""
    low = " {} ".format((text or "").strip().lower())

    scores = {}
    for bot, words in _KEYWORDS.items():
        hits = sum(1 for w in words if w.strip() and w in low)
        if hits:
            scores[bot] = hits

    generic = any(w in low for w in _GENERIC_BOOKING)

    if not scores:
        return None, generic

    # Asking for advice/servicing is decisive for the consultation form, even
    # when a product noun is mentioned ("need advice on which fridge to get").
    if any(w in low for w in _DECISIVE_CONSULT):
        return "angel", generic

    # Wanting/pricing a product is decisive for the sales form: "I want a
    # fridge" is a purchase call, not a product consultation.
    if any(w in low for w in _DECISIVE_SALES) or (
            any(w in low for w in _PRODUCT_NOUNS)
            and "krishna" not in scores):
        return "dhruv", generic

    best = max(scores, key=lambda b: scores[b])
    top = scores[best]
    # A tie between two areas is not a confident match — ask instead.
    if sum(1 for b in scores if scores[b] == top) > 1:
        return None, True
    return best, generic




# --------------------------------------------------------------------
# 2) Gemini pass
# --------------------------------------------------------------------

_CLASSIFY_PROMPT = """You route messages for a booking chatbot of a cloud/IT
consulting company. Read the user's message and reply with EXACTLY ONE word,
lowercase, no punctuation, no explanation:

angel   - the user wants a product or appliance consultation, product advice,
          maintenance, installation or a demo
dhruv   - the user wants to buy, asks about price/quote/discount, is a sales
          lead, or wants a sales callback
krishna - the user wants services or support: cloud computing, AWS, migration,
          devops, hosting, security, technical issues
none    - the message is a general question, small talk, or does not request
          any of the above

Message: {message}
Answer with one word only."""


def gemini_match(text, timeout=4):
    """Classify with Gemini. Returns a bot key or None."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None

    model = (os.environ.get("GEMINI_MODEL") or gemini_faq.DEFAULT_MODEL).strip()
    payload = {
        "contents": [{
            "role": "user",
            "parts": [{"text": _CLASSIFY_PROMPT.format(message=text)}],
        }],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 8,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    data, status, body = gemini_faq._call(model, api_key, payload, timeout, "intent")
    if data is None and (status == 400 or gemini_faq._looks_like_bad_model(status, body)):
        payload["generationConfig"].pop("thinkingConfig", None)
        fallback = (gemini_faq.FALLBACK_MODEL
                    if gemini_faq._looks_like_bad_model(status, body) else model)
        data, status, body = gemini_faq._call(
            fallback, api_key, payload, timeout, "intent-retry")
    if data is None:
        return None

    try:
        parts = data["candidates"][0].get("content", {}).get("parts", []) or []
        word = "".join(p.get("text", "") for p in parts).strip().lower()
    except (KeyError, IndexError, TypeError):
        return None

    word = re.sub(r"[^a-z]", "", word)
    print("FORM_INTENT gemini -> '{}'".format(word))
    return word if word in BOTS else None


# --------------------------------------------------------------------
# 3) Public entry point
# --------------------------------------------------------------------

def classify(text, use_gemini=True):
    """
    Returns (bot | None, needs_clarification).

      bot                 -> confident enough to offer that form
      needs_clarification -> the user clearly wants something from us but the
                             area is unclear, so ask which of the three areas
    """
    raw = (text or "").strip()
    if not raw or raw.startswith(("SELECT_BOT:", "INIT_", "FORM_",
                                  "CONFIRM_BOT:", "DECLINE_BOT")):
        return None, False
    if _looks_like_slot_value(raw):
        return None, False
    if is_yes(raw) or is_no(raw):
        return None, False

    bot, generic = keyword_match(raw)
    if bot:
        print("FORM_INTENT keyword -> {}".format(bot))
        return bot, False

    if use_gemini and len(re.findall(r"[a-z']+", raw.lower())) >= 2:
        bot = gemini_match(raw)
        if bot:
            return bot, False

    return None, generic
