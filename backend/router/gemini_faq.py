"""
gemini_faq.py — knowledge/FAQ layer for the router Lambda.

Answers general company / cloud-IT questions with Gemini Flash so the chatbot
can respond to things Lex was never trained on ("what is cloud computing?",
"what does your company do?") WITHOUT touching the Lex conversation state.

Deploy: drop this file next to apihandler_lambda.py in the router Lambda.
Pure stdlib (urllib) — no extra layer or dependency needed.

ENV VARS (set on the router Lambda in the AWS Console):
    GEMINI_API_KEY   required. Your Google AI Studio key.
    GEMINI_MODEL     optional. Default: gemini-2.5-flash
    COMPANY_NAME     optional. Default: iCloudy / Cloud Ladder Consulting
"""

import json
import os
import re
import urllib.request
import urllib.error

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

# Primary model: free tier, current standard Flash. It is a reasoning model, so
# thinking MUST be disabled or the visible answer gets truncated.
DEFAULT_MODEL = "gemini-flash-latest"

# Safety net: no thinking at all, generous free quota, very stable.
FALLBACK_MODEL = "gemini-2.5-flash-lite"

COMPANY_NAME = os.environ.get("COMPANY_NAME", "iCloudy / Cloud Ladder Consulting")

# Reason the last answer() call failed (empty when it succeeded). Read by
# diagnose() so the failure is visible without digging through CloudWatch.
LAST_ERROR = ""


OFF_TOPIC_REPLY = (
    "I can only help with questions about our company and cloud/IT topics. "
    "Ask me anything in that space, or let's continue with your booking."
)

SYSTEM_PROMPT = """You are the knowledge assistant for {company}, a cloud and IT
consulting company. You sit inside a booking chatbot.

RULES:
- Answer ONLY questions about {company}, its services, or general cloud / IT /
  technology topics (cloud computing, AWS, migration, DevOps, security, support).
- If the question is about anything else (sports, politics, cooking, personal
  advice, other companies, general chit-chat), reply with EXACTLY this sentence
  and nothing else: "{offtopic}"
- Keep every answer to at most 3 short sentences. Plain text only, no markdown,
  no bullet lists, no headings, no emojis.
- Never invent prices, availability, names or commitments. If you do not know a
  company-specific detail, say the team can confirm it on the consultation call.
- Never ask the user for personal details; the booking flow handles that.
""".format(company=COMPANY_NAME, offtopic=OFF_TOPIC_REPLY)


# --------------------------------------------------------------------
# 1) Intent gate — is this a knowledge question, or Lex/booking input?
# --------------------------------------------------------------------

# Anything that looks like a slot answer must NEVER be intercepted.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^[+\d][\d\s\-()]{6,}$")
_DATE_RE = re.compile(
    r"^(\d{1,2}[/\-.]\d{1,2}([/\-.]\d{2,4})?|\d{4}-\d{2}-\d{2}|"
    r"(mon|tue|wed|thu|fri|sat|sun)[a-z]*|today|tomorrow)$",
    re.I,
)
_TIME_RE = re.compile(r"^\d{1,2}(:\d{2})?\s*(am|pm)?$", re.I)

_YES_NO = {
    "yes", "no", "y", "n", "yeah", "yep", "nope", "ok", "okay", "sure",
    "confirm", "confirmed", "cancel", "done", "next", "back", "restart",
}

# Booking / Lex intent utterances — always go to Lex.
_BOOKING_HINTS = (
    "book", "booking", "appointment", "schedule", "reschedule", "consultation",
    "callback", "call me", "talk to", "connect me", "agent", "executive",
    "complaint", "order", "buy", "purchase", "repair", "service request",
)

# Question shapes that indicate a knowledge question.
_QUESTION_STARTS = (
    "what", "why", "how", "who", "when", "where", "which", "whats", "what's",
    "can you explain", "tell me", "explain", "describe", "define", "is there",
    "are there", "do you", "does your", "difference between", "meaning of",
)


def is_knowledge_question(text, has_pending_prompt=False):
    """
    True  -> answer with Gemini (do NOT call Lex this turn).
    False -> pass through to Lex exactly as before.

    Deliberately conservative: when in doubt we prefer Lex, because a
    misrouted slot answer breaks the booking flow, while a missed FAQ
    just gets a normal Lex reply.
    """
    if not text:
        return False

    raw = text.strip()
    low = raw.lower()

    # Protocol messages are handled before this is ever called, but be safe.
    if raw.startswith(("SELECT_BOT:", "INIT_", "FORM_")):
        return False

    # Slot-answer shapes.
    if _EMAIL_RE.match(raw) or _PHONE_RE.match(raw) or _DATE_RE.match(low) or _TIME_RE.match(low):
        return False
    if low.strip("!.? ") in _YES_NO:
        return False

    words = re.findall(r"[a-z']+", low)

    # Very short input while a slot question is pending is almost certainly
    # the answer to that slot (a name, a city, a product).
    if has_pending_prompt and len(words) <= 3 and not low.endswith("?"):
        return False

    # Explicit booking intent always wins over the FAQ layer.
    if any(hint in low for hint in _BOOKING_HINTS):
        return False

    if low.endswith("?"):
        return True
    if low.startswith(_QUESTION_STARTS):
        return True

    return False


# --------------------------------------------------------------------
# 2) Gemini call — with a model/config fallback ladder
# --------------------------------------------------------------------

def _call(model, api_key, payload, timeout, attempt):
    """
    POST to Gemini. Returns (data, status, body).
      data   -> parsed JSON on success, else None
      status -> HTTP status (0 for timeout/network/parse failures)
      body   -> error body text (lowercased) or ""
    """
    url = GEMINI_ENDPOINT.format(model=model)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            print("GEMINI attempt={} model={} status=200".format(attempt, model))
            return json.loads(resp.read().decode("utf-8")), 200, ""
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:500]
        print("GEMINI attempt={} model={} status={} body={}".format(
            attempt, model, e.code, body))
        return None, e.code, body.lower()
    except Exception as e:  # timeout, DNS, malformed JSON…
        print("GEMINI attempt={} model={} status=0 error={}".format(attempt, model, e))
        return None, 0, str(e).lower()


def _looks_like_bad_model(status, body):
    """True when the failure is about the model name, not the request body."""
    if status == 404:
        return True
    return any(marker in body for marker in (
        "not_found",
        "is not found",
        "model not found",
        "not supported",
        "unsupported model",
        "is not supported for generatecontent",
    ))


def _extract(data):
    """Pull the answer text out of a Gemini response, or None."""
    try:
        candidate = data["candidates"][0]
        parts = candidate.get("content", {}).get("parts", []) or []
        text = "".join(p.get("text", "") for p in parts).strip()
        finish = candidate.get("finishReason", "")
    except (KeyError, IndexError, TypeError):
        print("GEMINI: unexpected response shape: {}".format(json.dumps(data)[:500]))
        return None

    if finish == "MAX_TOKENS" and text:
        # Trim back to the last complete sentence so the user never sees a
        # dangling half-sentence.
        cut = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
        if cut > 40:
            text = text[:cut + 1]
        else:
            print("GEMINI: truncated with no usable sentence")
            return None

    return text or None


def answer(question, timeout=5):
    """
    Returns the model's answer text, or None on any failure / missing key.
    Callers MUST fall back to local_answer() when None is returned.

    Every failure reason is also recorded in LAST_ERROR so `diagnose()` can
    report exactly why the hardcoded backup answers are being served.

    Fallback ladder (max 3 HTTP calls, each capped at `timeout` seconds so the
    whole chain stays inside the Lambda budget):
      1. configured model + thinkingConfig
      2. on HTTP 400 -> same model, thinkingConfig stripped
      3. on 404 / model-not-found -> FALLBACK_MODEL, no thinkingConfig
    """
    global LAST_ERROR
    LAST_ERROR = ""

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        LAST_ERROR = ("GEMINI_API_KEY is not set on this Lambda "
                      "(env var missing or empty)")
        print("GEMINI: no GEMINI_API_KEY configured — using local answers")
        return None

    model = (os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL).strip()

    def build(with_thinking):
        cfg = {"temperature": 0.3, "maxOutputTokens": 512}
        if with_thinking:
            # Reasoning-capable Flash models spend the output budget on
            # internal thinking tokens first, which truncates the visible
            # answer. Turn that off — these are 3-sentence FAQ replies.
            cfg["thinkingConfig"] = {"thinkingBudget": 0}
        return {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": question}]}],
            "generationConfig": cfg,
        }

    # --- Attempt 1: configured model, thinking off -------------------
    data, status, body = _call(model, api_key, build(True), timeout, 1)
    if data is not None:
        text = _extract(data)
        if text:
            return text
        LAST_ERROR = "model '{}' returned no usable text".format(model)
        return None

    LAST_ERROR = "model '{}' -> HTTP {} {}".format(model, status, body[:200])
    bad_model = _looks_like_bad_model(status, body)

    # --- Attempt 2: same model without thinkingConfig ----------------
    # Only worth trying when the model itself is valid but rejected the body.
    if status == 400 and not bad_model:
        data, status, body = _call(model, api_key, build(False), timeout, 2)
        if data is not None:
            text = _extract(data)
            if text:
                return text
            LAST_ERROR = "model '{}' returned no usable text".format(model)
            return None
        LAST_ERROR = "model '{}' (no thinkingConfig) -> HTTP {} {}".format(
            model, status, body[:200])
        bad_model = _looks_like_bad_model(status, body)

    # --- Attempt 3: known-good fallback model ------------------------
    # Covers a bad GEMINI_MODEL value, a retired model, or a wrong API version.
    if bad_model and model != FALLBACK_MODEL:
        print("GEMINI: model '{}' unusable — falling back to '{}'".format(
            model, FALLBACK_MODEL))
        data, status, body = _call(FALLBACK_MODEL, api_key, build(False), timeout, 3)
        if data is not None:
            text = _extract(data)
            if text:
                return text
            LAST_ERROR = "fallback model returned no usable text"
            return None
        LAST_ERROR = "fallback model '{}' -> HTTP {} {}".format(
            FALLBACK_MODEL, status, body[:200])

    # 401/403 (bad key), 429 (quota), timeouts and anything else land here.
    return None


# --------------------------------------------------------------------
# 2b) Self-test — surfaces WHY local answers are being used
# --------------------------------------------------------------------

def diagnose(timeout=5):
    """
    Live self-test. Returns a short human-readable status string.
    Triggered from chat by sending the message: GEMINI_DIAG
    """
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = (os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL).strip()

    lines = [
        "Gemini diagnostics",
        "GEMINI_API_KEY: {}".format(
            "set (length {}, ends '{}')".format(len(key), key[-4:]) if key else "NOT SET"),
        "GEMINI_MODEL: {}".format(model),
    ]

    if not key:
        lines.append("Result: no key -> local backup answers are used. "
                     "Add GEMINI_API_KEY to the router Lambda env vars.")
        return "\n".join(lines)

    text = answer("Say the word OK.", timeout=timeout)
    if text:
        lines.append("Result: LIVE — Gemini replied: {}".format(text[:120]))
    else:
        lines.append("Result: FAILED — {}".format(LAST_ERROR or "unknown error"))
    return "\n".join(lines)




# --------------------------------------------------------------------
# 3) Local backup answers
# --------------------------------------------------------------------

def local_answer(question):
    """
    Deterministic fallback used when Gemini is unavailable, misconfigured,
    rate-limited, or times out. This prevents users from seeing a generic
    "couldn't look that up" error for common company/cloud questions.
    """
    low = (question or "").strip().lower()

    if any(phrase in low for phrase in (
        "your company", "company about", "what do you do", "who are you",
        "about your company", "about company", "icloudy", "cloud ladder"
    )):
        return (
            "Cloud Ladder Consulting, also known as iCloudy, helps businesses with cloud and IT consulting. "
            "The team can support cloud strategy, migration, AWS guidance, DevOps, security, and technical support. "
            "For exact requirements, the team can confirm the best solution on a consultation call."
        )

    if "cloud computing" in low or ("cloud" in low and any(word in low for word in ("what", "explain", "define", "meaning"))):
        return (
            "Cloud computing means using internet-based servers, storage, databases, and software instead of running everything on local machines. "
            "It helps businesses scale faster, reduce hardware maintenance, and pay for resources as they use them. "
            "Common examples include AWS hosting, cloud storage, backups, and managed applications."
        )

    if "aws" in low or "amazon web services" in low:
        return (
            "AWS is Amazon's cloud platform for hosting applications, storing data, running databases, and managing infrastructure. "
            "It is commonly used for scalable websites, backups, analytics, security, and automation. "
            "The team can help choose the right AWS services for your business needs."
        )

    if "migration" in low or "move to cloud" in low or "migrate" in low:
        return (
            "Cloud migration means moving applications, data, or servers from existing systems into a cloud platform. "
            "A good migration plan checks cost, security, downtime, backups, and performance before anything is moved. "
            "The team can review your current setup and suggest a safe migration approach."
        )

    if "devops" in low:
        return (
            "DevOps connects development and operations so software can be built, tested, deployed, and monitored more reliably. "
            "It often includes CI/CD pipelines, automation, cloud infrastructure, logging, and release management. "
            "The team can confirm the right DevOps setup for your project on a consultation call."
        )

    if "security" in low or "secure" in low or "cyber" in low:
        return (
            "Cloud security focuses on protecting applications, data, users, and infrastructure in cloud environments. "
            "It can include access control, backups, monitoring, encryption, network protection, and compliance reviews. "
            "The team can assess your requirements and recommend practical security improvements."
        )

    if any(word in low for word in ("service", "services", "support", "help")):
        return (
            "The company helps with cloud consulting, AWS guidance, migration planning, DevOps, IT support, and cloud security. "
            "If your need is specific, the team can confirm the right service and next steps during a consultation call."
        )

    return (
        "I can help with questions about Cloud Ladder Consulting, iCloudy, and general cloud or IT topics. "
        "Please ask about cloud consulting, AWS, migration, DevOps, security, or technical support."
    )
