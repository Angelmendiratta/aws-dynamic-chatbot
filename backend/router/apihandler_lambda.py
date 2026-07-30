"""
LexApiHandler.py  —  updated router

Adds bypass logic for the dynamic-form protocol:
  - "INIT_ANGEL" / "INIT_DHRUV"      → invoke the business Lambda directly (no Lex).
  - "FORM_SUBMIT:<json>"              → validate + save via business Lambda.
  - "FORM_CONFIRM:<json>"             → final confirm via business Lambda.

Everything else keeps the original Lex flow untouched.

Also adds a Gemini-powered FAQ layer (gemini_faq.py):
  - Company / cloud-IT questions are answered by Gemini instead of Lex,
    both before a bot is selected and mid-conversation.
  - Lex is NOT called on those turns, so slot state stays intact; the last
    bot prompt is re-asked so the booking flow resumes cleanly.

ENV VARS EXPECTED:
  ANGEL_BOT_ID, DHRUV_BOT_ID, REGION           (as before)
  ANGEL_LAMBDA_ARN, DHRUV_LAMBDA_ARN           (for direct Lambda invoke)
  GEMINI_API_KEY                               (new — FAQ layer; optional,
                                                without it FAQ falls back to Lex)
  GEMINI_MODEL, COMPANY_NAME                   (new — optional overrides)
"""

import json
import boto3
import uuid
import os

import gemini_faq



# --------------------------------------------------------------------
# Registry — one entry per bot. Reads its Lex ids and target Lambda ARN
# from env vars set on the router Lambda in the AWS Console.
# --------------------------------------------------------------------
def get_registry():
    return {
        'angel': {
            'botId':      os.environ.get('ANGEL_BOT_ID', ''),
            'botAliasId': 'TSTALIASID',
            'localeId':   'en_US',
            'region':     os.environ.get('REGION', 'ap-southeast-1'),
            'lambdaArn':  os.environ.get('ANGEL_LAMBDA_ARN', '')
        },
        'dhruv': {
            'botId':      os.environ.get('DHRUV_BOT_ID', ''),
            'botAliasId': 'TSTALIASID',
            'localeId':   'en_US',
            'region':     os.environ.get('REGION', 'ap-southeast-1'),
            'lambdaArn':  os.environ.get('DHRUV_LAMBDA_ARN', '')
        },
       'krishna': {
            'botId':      os.environ.get('KRISHNA_BOT_ID', ''),
            'botAliasId': 'TSTALIASID',
            'localeId':   'en_US',
            'region':     os.environ.get('REGION', 'ap-southeast-1'),
            'lambdaArn':  os.environ.get('KRISHNA_LAMBDA_ARN', '')
}
    }


CORS_HEADERS = {
    'Access-Control-Allow-Origin':  '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, OPTIONS'
}


def _ok(body):
    return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': json.dumps(body)}


def _err_response(session_id, active_bot, text):
    return _ok({
        'messages': [{'contentType': 'PlainText', 'content': text}],
        'sessionId': session_id, 'activeBot': active_bot, 'sessionAttributes': {}
    })


def _invoke_business_lambda(lambda_arn, region, payload):
    """
    Direct-invoke the target business Lambda (Angel or Dhruv) with a form event.
    The router does NOT know or duplicate the form schema — it is a pure proxy.
    """
    client = boto3.client('lambda', region_name=region)
    resp = client.invoke(
        FunctionName=lambda_arn,
        InvocationType='RequestResponse',
        Payload=json.dumps(payload).encode('utf-8')
    )
    raw = resp['Payload'].read()
    try:
        return json.loads(raw)
    except Exception:
        return {'error': 'invalid lambda response', 'raw': raw.decode('utf-8', 'ignore')}


NO_BOT_NUDGE = ("To book a consultation, please select an assistant above "
                "and I'll take it from there.")
FORM_NUDGE = "Your form is still open above — carry on whenever you're ready."

FORM_ALSO_NUDGE = "Your form is also still open above."

IDLE_NUDGE = ("You can fill in the form above, or type 'hi' to start the "
              "booking chat.")



def _faq_reply(session_id, active_bot, question, last_prompt, form_open):
    """
    Build the FAQ response.

    Lex is never invoked on this turn, so any pending slot elicitation is
    preserved exactly — we only re-show the question the bot last asked.
    If Gemini is unavailable we still answer here with a failsafe message
    instead of sending the question to Lex (which would reply
    "I didn't catch that" and could disturb the flow).
    """
    text = gemini_faq.answer(question) or gemini_faq.local_answer(question)

    messages = [{'contentType': 'PlainText', 'content': text}]

    if not active_bot:
        messages.append({'contentType': 'PlainText', 'content': NO_BOT_NUDGE})
    elif last_prompt:
        # A pending Lex question always wins — re-ask it so the booking flow
        # resumes exactly where it left off, even if the form is also open.
        messages.append({
            'contentType': 'PlainText',
            'content': "Now, back to where we were — {}".format(last_prompt)
        })
        if form_open:
            messages.append({'contentType': 'PlainText',
                             'content': FORM_ALSO_NUDGE})
    elif form_open:
        messages.append({'contentType': 'PlainText', 'content': FORM_NUDGE})
    else:
        messages.append({'contentType': 'PlainText', 'content': IDLE_NUDGE})

    # Always echo lastPrompt back (even when empty) so the frontend keeps the
    # pending question across consecutive FAQ turns.
    attrs = {'lastPrompt': last_prompt}

    return _ok({
        'messages': messages,
        'sessionId': session_id,
        'activeBot': active_bot,
        'sessionAttributes': attrs
    })

# --------------------------------------------------------------------
# Handler
# --------------------------------------------------------------------
def lambda_handler(event, context):
    try:
        body         = json.loads(event['body'])
        user_message = body.get('message', '')
        session_id   = body.get('sessionId', str(uuid.uuid4()))
        active_bot   = body.get('activeBot', '')
        # Echoed back by the frontend: the last question the bot asked, and
        # whether the dynamic form is currently on screen.
        last_prompt  = (body.get('lastPrompt') or '').strip()
        form_open    = bool(body.get('formOpen'))

        print(f"=== INCOMING REQUEST ===")
        print(f"Active Bot: {active_bot}")
        print(f"Message: {user_message}")
        print(f"Session ID: {session_id}")
        print(f"Full Payload: {json.dumps(body)}")
        print(f"========================")

        BOT_REGISTRY = get_registry()

        is_protocol = user_message.startswith(('SELECT_BOT:', 'INIT_', 'FORM_'))

         # ---------------- Gemini self-test ----------------
        # Type "GEMINI_DIAG" in the chat to see whether the live Gemini call
        # works and, if not, the exact reason (missing key, 401, 404, quota).
        if user_message.strip().upper() == 'GEMINI_DIAG':
            return _ok({
                'messages': [{'contentType': 'PlainText',
                              'content': gemini_faq.diagnose()}],
                'sessionId': session_id,
                'activeBot': active_bot,
                'sessionAttributes': {}
            })
        # ---------------- Gemini FAQ layer ----------------
        # Runs for free-text only. Conservative gate: anything that looks like
        # a slot answer or a booking utterance goes straight to Lex.
        if not is_protocol and gemini_faq.is_knowledge_question(
            user_message, has_pending_prompt=bool(last_prompt) or form_open
        ):
            print(f"FAQ: routing to Gemini (bot='{active_bot}', formOpen={form_open})")
            return _faq_reply(session_id, active_bot, user_message, last_prompt, form_open)

        # ---------------- No bot selected yet ----------------
        if not active_bot and not is_protocol:
            return _ok({
                'messages': [], 'sessionId': session_id,
                'activeBot': '', 'sessionAttributes': {}
            })


        # ---------------- SELECT_BOT ----------------
        if user_message.startswith('SELECT_BOT:'):
            selected = user_message.split(':')[1].lower()
            if selected not in BOT_REGISTRY:
                selected = 'angel'
            return _ok({
                'messages': [{
                    'contentType': 'PlainText',
                    'content': f"Hi! You are now connected to {selected.title()}'s assistant. "
                               f"You can fill in the form below or type 'Book an appointment'."
                }],
                'sessionId': session_id,
                'activeBot': selected,
                'sessionAttributes': {}
            })

        # ---------------- DYNAMIC FORM BYPASS ----------------
        # INIT_ANGEL / INIT_DHRUV → get form schema
        if user_message.startswith('INIT_'):
            bot_key = user_message.replace('INIT_', '').lower()
            if bot_key not in BOT_REGISTRY:
                return _ok({'messages': [], 'sessionId': session_id,
                            'activeBot': active_bot, 'sessionAttributes': {}})
            cfg = BOT_REGISTRY[bot_key]
            if not cfg['lambdaArn']:
                return _err_response(session_id, bot_key,
                    f"{bot_key.title()} Lambda ARN not configured on the router.")
            result = _invoke_business_lambda(cfg['lambdaArn'], cfg['region'], {
                'formAction': 'INIT', 'bot': bot_key, 'sessionId': session_id
            })
            return _ok({
                'messages': result.get('messages', []),
                'sessionId': session_id, 'activeBot': bot_key,
                'sessionAttributes': result.get('sessionAttributes', {})
            })

        # FORM_SUBMIT:<json>  /  FORM_CONFIRM:<json>
        if user_message.startswith('FORM_SUBMIT:') or user_message.startswith('FORM_CONFIRM:'):
            action, _, raw = user_message.partition(':')
            try:
                payload = json.loads(raw)
            except Exception:
                return _ok({'messages': [{'contentType': 'PlainText',
                                          'content': 'Malformed form payload.'}],
                            'sessionId': session_id, 'activeBot': active_bot,
                            'sessionAttributes': {}})
            bot_key = (payload.get('bot') or active_bot or '').lower()
            if bot_key not in BOT_REGISTRY:
                return _ok({'messages': [{'contentType': 'PlainText',
                                          'content': 'Unknown assistant for form submission.'}],
                            'sessionId': session_id, 'activeBot': active_bot,
                            'sessionAttributes': {}})
            cfg = BOT_REGISTRY[bot_key]
            result = _invoke_business_lambda(cfg['lambdaArn'], cfg['region'], {
                'formAction': action.replace('FORM_', ''),   # SUBMIT or CONFIRM
                'bot': bot_key,
                'sessionId': session_id,
                'values': payload.get('values', {})
            })
            return _ok({
                'messages': result.get('messages', []),
                'sessionId': session_id, 'activeBot': bot_key,
                'sessionAttributes': result.get('sessionAttributes', {})
            })

        # ---------------- Normal Lex routing (unchanged) ----------------
        if active_bot not in BOT_REGISTRY:
            active_bot = 'angel'
        config = BOT_REGISTRY[active_bot]

        client = boto3.client('lexv2-runtime', region_name=config['region'])
        response = client.recognize_text(
            botId=config['botId'],
            botAliasId=config['botAliasId'],
            localeId=config['localeId'],
            sessionId=f"{active_bot}-{session_id}",
            text=user_message
        )

        messages      = response.get('messages', [])
        session_attrs = response.get('sessionState', {}).get('sessionAttributes', {}) or {}

        if messages:
            last_message = messages[-1].get('content', '')
            # Remember the question the bot just asked, so if the user
            # interrupts with an FAQ question we can re-ask it afterwards.
            dialog_type = (response.get('sessionState', {})
                                   .get('dialogAction', {})
                                   .get('type', ''))
            if last_message and (dialog_type in ('ElicitSlot', 'ElicitIntent', 'ConfirmIntent')
                                 or last_message.strip().endswith('?')):
                session_attrs['lastPrompt'] = last_message
            else:
                session_attrs['lastPrompt'] = ''

            if ("Your request has been noted"      in last_message or
                "Our executive will call you"      in last_message or
                "our executive will arrange a call" in last_message):
                session_attrs["uiButtons"] = json.dumps([
                    {"text": "Need More Assistance?",
                     "value": "https://www.icloudy.co/icloudy-contact-us/"}
                ])

        return _ok({
            'messages': messages,
            'sessionId': session_id,
            'activeBot': active_bot,
            'sessionAttributes': session_attrs
        })

    except Exception as e:
        print(f"ERROR: {str(e)}")
        return {'statusCode': 500,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': str(e)})}
