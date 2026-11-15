# bot_pulse_profit.py
# Pulse Profit™ — Complete Telegram Earning Bot
# HTML | SQLite | Refer ₦50 | Force-Join → CAPTCHA → Menu
# Bank verification: Mansa (NUBAN format) → NU-ALT (name enquiry)

import os
import asyncio
import logging
import sqlite3
import random
import time
import uuid
import re
import json
import traceback
import requests
from datetime import datetime
from typing import Dict, Optional, List
from contextlib import contextmanager

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from dotenv import load_dotenv

load_dotenv()

# ======================== CONFIG ========================
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
ADMIN_IDS = [7713987088, 1234567890]

SUPPORT_BOT = "https://t.me/PulseProfitSupportBot"
PAYOUT_CHANNEL = "@PulseProfitWithdrawals"

FORCED_CHANNELS = [
    {'username': '@PulseProfit012', 'link': 'https://t.me/PulseProfit012', 'name': 'Pulse Profit Channel'},
    {'username': '@NCK_Dev', 'link': 'https://t.me/NCK_Dev', 'name': 'NCK Dev Channel'},
    {'username': '@PulseProfitWithdrawals', 'link': 'https://t.me/PulseProfitWithdrawals', 'name': 'Payout Channel'},
    {'username': '@moneyplugngx', 'link': 'https://t.me/moneyplugngx', 'name': 'Money Plug NGX'},
    {'username': '@aidropupdatesx', 'link': 'https://t.me/aidropupdatesx', 'name': 'Airdrop Updates'},
]

REFERRAL_REWARD = 50.0
REFERRAL_MIN_TASK_FOR_PAYOUT = 1
DAILY_CHECKIN_MIN = 10.0
DAILY_CHECKIN_MAX = 50.0
MIN_WITHDRAWAL = 5000.0
MAX_WITHDRAWAL = 50000.0

BOT_NAME = "Pulse Profit™"
CURRENCY = "₦"
DB_FILE = 'pulse_profit.db'

CAPTCHA_MAX_ATTEMPTS = 3
SESSION_TTL_SECONDS = 1800
CANCEL_TEXT = '🔙 Cancel'

# ======================== APIS ========================
MANSA_API_KEY = os.getenv('MANSA_API_KEY', '')
MANSA_BASE = "https://mansaapi.com/api/v1"

NUALT_KEY_FILE = os.getenv('NUALT_KEY_FILE', 'nualt_api_key.txt')
NUALT_API_KEY = os.getenv('NUALT_API_KEY', '')
if os.path.exists(NUALT_KEY_FILE):
    try:
        with open(NUALT_KEY_FILE, encoding='utf-8') as _f:
            NUALT_API_KEY = _f.read().strip() or NUALT_API_KEY
    except OSError:
        pass
# Comma-separated list; the bot tries each in order if one is unreachable (DNS/network)
NUALT_BASES = [b.strip().rstrip('/') for b in
               os.getenv('NUALT_BASE', "https://api.nualt.app/v1,https://nu-alt.shop/v1").split(',') if b.strip()]
NUALT_BASE = NUALT_BASES[0]
# Browser fallback (Playwright): logs in to YOUR own nuAlt dashboard with the session
# code ("sess_...") and uses its "Test it" form when the API is unreachable.
NUALT_SESSION = os.getenv('NUALT_SESSION', '').strip()
NUALT_DASHBOARD_URL = os.getenv('NUALT_DASHBOARD_URL', 'https://nu-alt.shop/dashboard')
MAILTM_BASE = "https://api.mail.tm"
MAILTM_FILE = os.getenv('MAILTM_FILE', 'mailtm_account.json')        # the ONE mailbox, created once and reused
BROWSER_STATE_FILE = os.getenv('BROWSER_STATE_FILE', 'nualt_browser_state.json')  # keeps the dashboard login

# ======================== STATES ========================
BANK_SELECT, BANK_ACCOUNT_NAME, BANK_ACCOUNT_NUMBER = range(3)
WITHDRAW_AMOUNT = 100
TASK_TITLE, TASK_DESC, TASK_REWARD, TASK_TYPE, TASK_REQUIREMENT, TASK_IMAGE = range(6)
BROADCAST_IMAGE, BROADCAST_CAPTION, BROADCAST_BUTTONS, BROADCAST_CONFIRM = range(4)
SEND_COINS_USER_ID, SEND_COINS_AMOUNT = range(2)

# ======================== SESSIONS ========================
_SESSIONS: Dict[int, Dict] = {}

def new_session(user_id):
    sid = uuid.uuid4().hex[:12]
    old = _SESSIONS.get(user_id)
    _SESSIONS[user_id] = {"sid": sid, "created": time.time(), "data": old["data"] if old else {}}
    return sid

def get_session(user_id):
    s = _SESSIONS.get(user_id)
    if not s:
        return None
    if time.time() - s["created"] > SESSION_TTL_SECONDS:
        _SESSIONS.pop(user_id, None)
        return None
    return s["sid"]

def session_data(user_id):
    s = _SESSIONS.get(user_id)
    if not s:
        new_session(user_id)
        s = _SESSIONS[user_id]
    return s["data"]

def is_valid_session(user_id, sid):
    return get_session(user_id) == sid

def clear_session(user_id):
    _SESSIONS.pop(user_id, None)

# ======================== CAPTCHA ========================
CAPTCHA_CHALLENGES = [
    ("Select the angry face", "😡", ["😊", "😎", "🥳"]),
    ("Pick the crying face", "😢", ["😂", "😀", "😍"]),
    ("Which one is a heart?", "❤️", ["⭐", "🔥", "🎵"]),
    ("Identify the apple", "🍎", ["🚗", "🐶", "🌙"]),
    ("Which is a dog?", "🐶", ["🐱", "🐭", "🐰"]),
    ("Pick the fire emoji", "🔥", ["❄️", "🌊", "🌪️"]),
    ("Select the star", "⭐", ["🌙", "☀️", "☁️"]),
    ("Which one is a car?", "🚗", ["✈️", "🚢", "🚲"]),
    ("Pick the watermelon", "🍉", ["🍌", "🍇", "🍓"]),
    ("Identify the clock", "⏰", ["📱", "💻", "📺"]),
    ("Which is a soccer ball?", "⚽", ["🏀", "🎾", "🏈"]),
    ("Pick the sun", "☀️", ["🌙", "⭐", "☁️"]),
    ("Which one is a tree?", "🌳", ["🌹", "🍄", "🌷"]),
    ("Select the pizza", "🍕", ["🍔", "🌮", "🍣"]),
    ("Pick the rabbit", "🐰", ["🐶", "🐱", "🐻"]),
    ("Which is a gift box?", "🎁", ["🎈", "🎉", "🎂"]),
    ("Identify the book", "📚", ["🖊️", "📎", "✂️"]),
    ("Pick the rainbow", "🌈", ["☁️", "⛈️", "❄️"]),
    ("Which one is money?", "💰", ["📦", "🧧", "💳"]),
    ("Select the rocket", "🚀", ["✈️", "🛸", "🎈"]),
    ("Which one is a cat?", "🐱", ["🐶", "🐻", "🐭"]),
    ("Pick the moon", "🌙", ["⭐", "☀️", "☁️"]),
    ("Select the diamond", "💎", ["⭐", "🔷", "🔶"]),
    ("Which is a banana?", "🍌", ["🍎", "🍇", "🍓"]),
    ("Pick the crown", "👑", ["⭐", "💎", "🔔"]),
]

def generate_emoji_captcha():
    q, correct, decoys = random.choice(CAPTCHA_CHALLENGES)
    picked = random.sample(decoys, k=2)
    options = [correct, *picked]
    random.shuffle(options)
    return q, correct, options, options.index(correct)

def captcha_prompt_html(question):
    return (
        f"<b>🔒 Security Verification</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"To keep <b>{BOT_NAME}</b> safe from automated abuse,\n"
        f"please complete this quick human verification.\n\n"
        f"<b>📋 Challenge:</b> {esc(question)}\n\n"
        f"<b>👇 Tap the correct emoji below to continue:</b>"
    )

# ======================== LOGGING ========================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ======================== HELPERS ========================
def is_admin(user_id):
    return user_id in ADMIN_IDS

def fmt(amount):
    return f"{CURRENCY}{amount:,.2f}"

def esc(text):
    if text is None:
        return ""
    return (str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))

def get_daily_checkin_reward():
    return round(random.uniform(DAILY_CHECKIN_MIN, DAILY_CHECKIN_MAX), 2)

def bank_rows(banks):
    names = [b['bank_name'] for b in banks]
    return [names[i:i + 2] for i in range(0, len(names), 2)]

def is_cancel(text):
    return (text or '').strip() == CANCEL_TEXT

async def send_html(target, text, **kwargs):
    try:
        if hasattr(target, 'message') and target.message is not None:
            return await target.message.reply_text(text, parse_mode='HTML', **kwargs)
        return await target.reply_text(text, parse_mode='HTML', **kwargs)
    except Exception as e:
        logger.warning(f"HTML failed: {e}")
        try:
            if hasattr(target, 'message') and target.message is not None:
                return await target.message.reply_text(text, parse_mode=None, **kwargs)
            return await target.reply_text(text, parse_mode=None, **kwargs)
        except Exception as e2:
            logger.error(f"Plain failed: {e2}")
            return None

async def send_html_photo(target, photo, caption=None, **kwargs):
    try:
        if hasattr(target, 'message') and target.message is not None:
            return await target.message.reply_photo(photo, caption=caption, parse_mode='HTML', **kwargs)
        return await target.reply_photo(photo, caption=caption, parse_mode='HTML', **kwargs)
    except Exception as e:
        logger.warning(f"Photo failed: {e}")
        if caption:
            return await send_html(target, caption, **kwargs)
        return None

# ======================== MANSA API ========================
WALLET_BANK_CODES = {'altbank', '100004', '100033', '090405', '090267', '999991', '50515', '50211'}  # OPay, PalmPay, Moniepoint (old codes)
WALLET_BANK_NAMES = {'opay', 'palmpay', 'moniepoint', 'kuda bank', 'altbank'}

def mansa_validate_nuban(account, bank_code):
    """True = valid, False = definitely invalid, None = could not check (skip)."""
    if bank_code in WALLET_BANK_CODES:
        return None  # OPay/PalmPay/Moniepoint numbers are phone-style, not NUBAN - checksum doesn't apply
    if not MANSA_API_KEY:
        logger.warning("MANSA_API_KEY not set - skipping NUBAN format check")
        return None
    mansa_code_map = {
        '100004': '999992',  # OPay
        '999991': '999991',  # PalmPay
        '50515': '50515',    # Moniepoint
    }
    target_code = mansa_code_map.get(bank_code, bank_code)
    try:
        r = requests.get(
            f"{MANSA_BASE}/identity/nuban/validate",
            params={'account': account, 'bank_code': target_code},
            headers={'Authorization': f'Bearer {MANSA_API_KEY}'},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            return bool(data.get('data', {}).get('valid', False))
        logger.warning(f"Mansa NUBAN HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.error(f"Mansa validate error: {e}")
    return None

def mansa_get_nigerian_banks():
    try:
        r = requests.get(
            f"{MANSA_BASE}/identity/banks",
            params={'country': 'NG'},
            headers={'Authorization': f'Bearer {MANSA_API_KEY}'},
            timeout=15
        )
        if r.status_code == 200:
            data = r.json()
            banks = data.get('data', [])
            return [
                {'code': b.get('code'), 'name': b.get('name')}
                for b in banks
                if b.get('code') and b.get('name')
            ]
        logger.warning(f"Mansa banks HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.error(f"Mansa banks error: {e}")
    return []

# ======================== NU-ALT API ========================
def _nualt_get(path, params=None, timeout=60):
    """GET against each configured base URL until one is reachable."""
    headers = {"Authorization": f"Bearer {NUALT_API_KEY}", "Accept": "application/json"}
    last_exc = None
    for base in NUALT_BASES:
        try:
            return requests.get(f"{base}{path}", headers=headers, params=params, timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"NU-ALT base {base} unreachable: {str(e)[:120]}")
            last_exc = e
    raise last_exc

def _find_account_name(obj):
    if isinstance(obj, dict):
        for k in ('account_name', 'accountName', 'accountname'):
            v = obj.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for v in obj.values():
            found = _find_account_name(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_account_name(v)
            if found:
                return found
    return None

def nualt_resolve_account(account, bank_code, bank_name=None):
    """Returns (account_name or None, reason). Sends only the nuAlt bank code.
    Lookups use a rotating proxy pool, so allow 60s and retry on 502/timeouts."""
    if not NUALT_API_KEY:
        logger.warning("NU-ALT API key not configured (set NUALT_API_KEY in .env)")
        return None, "NUALT_API_KEY is not set in the bot's .env file"
    url = f"{NUALT_BASE}/resolve"
    headers = {"Authorization": f"Bearer {NUALT_API_KEY}", "Accept": "application/json"}
    params = {'acc_no': account, 'bank': bank_code}
    reason = "unknown error"
    for attempt in range(1, 4):
        try:
            logger.info(f"NU-ALT request: bank={bank_code} acc={account} attempt={attempt}")
            resp = _nualt_get('/resolve', params, 60)
        except Exception as e:
            logger.error(f"NU-ALT network error: {e}")
            if 'Name or service not known' in str(e) or 'NameResolutionError' in str(e):
                return None, 'this server cannot reach nuAlt (' + ', '.join(b.split('/')[2] for b in NUALT_BASES) + ') - hosting/network issue'
            reason = f"network error ({e.__class__.__name__})"
            time.sleep(2)
            continue
        logger.info(f"NU-ALT HTTP {resp.status_code}: {resp.text[:300]}")
        if resp.status_code == 200:
            try:
                data = resp.json()
            except ValueError:
                return None, "non-JSON response"
            if isinstance(data, dict) and data.get('ok') is False:
                return None, "API returned ok=false"
            name = _find_account_name(data)
            return (name, "ok") if name else (None, "response had no account name")
        if resp.status_code == 401:
            return None, "API key missing/invalid/revoked (401)"
        if resp.status_code == 429:
            return None, "daily limit reached (429, free tier = 100/day)"
        if resp.status_code == 422:
            return None, "validation failed (422) - account must be 10 chars"
        if resp.status_code == 404:
            return None, f"bank code '{bank_code}' not recognised by nuAlt (404) - run /checkbanks"
        reason = f"HTTP {resp.status_code}"
        time.sleep(2)  # 502 etc: proxy pool exhausted, retry
    return None, reason

def nualt_list_banks():
    """Returns (list of {'bank_name','code'}, reason)."""
    if not NUALT_API_KEY:
        return [], "NUALT_API_KEY is not set"
    try:
        r = _nualt_get('/banks', None, 60)
        if r.status_code != 200:
            return [], f"HTTP {r.status_code}"
        return r.json().get('banks', []), "ok"
    except Exception as e:
        return [], str(e)[:150]

# ---------- mail.tm: one persistent mailbox ----------
def mailtm_get_account():
    """Returns (address, password). Creates the mailbox once, then always reuses it."""
    if os.path.exists(MAILTM_FILE):
        with open(MAILTM_FILE, encoding='utf-8') as f:
            d = json.load(f)
        return d['address'], d['password']
    domains = requests.get(f"{MAILTM_BASE}/domains", timeout=20).json().get('hydra:member', [])
    if not domains:
        raise RuntimeError("mail.tm returned no domains")
    domain = domains[0]['domain']
    for _ in range(3):
        address = f"pp{uuid.uuid4().hex[:10]}@{domain}"
        password = uuid.uuid4().hex + "Aa1!"
        r = requests.post(f"{MAILTM_BASE}/accounts", json={"address": address, "password": password}, timeout=20)
        if r.status_code == 201:
            with open(MAILTM_FILE, 'w', encoding='utf-8') as f:
                json.dump({"address": address, "password": password}, f)
            logger.info(f"mail.tm mailbox created: {address}")
            return address, password
        logger.warning(f"mail.tm create failed HTTP {r.status_code}: {r.text[:150]}")
    raise RuntimeError("could not create mail.tm mailbox")

def _mailtm_headers():
    address, password = mailtm_get_account()
    r = requests.post(f"{MAILTM_BASE}/token", json={"address": address, "password": password}, timeout=20)
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['token']}"}

def mailtm_message_ids():
    h = _mailtm_headers()
    r = requests.get(f"{MAILTM_BASE}/messages", headers=h, timeout=20)
    return {m['id'] for m in r.json().get('hydra:member', [])} if r.status_code == 200 else set()

_CODE_RE = re.compile(r'sess_[A-Za-z0-9_\-\.]+')
_LINK_RE = re.compile(r'https?://[^\s"<>\']*(?:nu-alt|nualt)[^\s"<>\']*')

def mailtm_wait_for_magic(ignore_ids, timeout=120):
    """Waits for a NEW email and returns a 'sess_...' code, or a magic-link URL, or None."""
    h = _mailtm_headers()
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{MAILTM_BASE}/messages", headers=h, timeout=20)
        if r.status_code == 200:
            for m in r.json().get('hydra:member', []):
                if m['id'] in ignore_ids:
                    continue
                full = requests.get(f"{MAILTM_BASE}/messages/{m['id']}", headers=h, timeout=20).json()
                body = (full.get('text') or '') + ' ' + ' '.join(full.get('html') or [])
                code = _CODE_RE.search(body)
                if code:
                    return code.group(0)
                link = _LINK_RE.search(body)
                if link:
                    return link.group(0).replace('&amp;', '&')
        time.sleep(4)
    return None

# ---------- browser fallback ----------
_BROWSER_LOCK = None

async def _dashboard_state(page):
    await page.wait_for_function(
        "() => { const d=document.getElementById('dash-view'), a=document.getElementById('auth-view');"
        " return (d && getComputedStyle(d).display!=='none') || (a && getComputedStyle(a).display!=='none'); }",
        timeout=20000)
    return await page.is_visible('#dash-view')

async def _use_code_or_link(page, value):
    if value.startswith('http'):
        await page.goto(value, timeout=45000)
        if not await page.is_visible('#dash-view'):
            await page.goto(NUALT_DASHBOARD_URL, timeout=45000)
    else:
        await page.fill('#code', value)
        await page.click('#verify-btn')
    try:
        await page.wait_for_selector('#dash-view', state='visible', timeout=15000)
        return True
    except Exception:
        return False

async def _browser_login(page):
    """Returns (ok, reason). Order: saved login -> NUALT_SESSION code -> mail.tm magic link."""
    if await _dashboard_state(page):
        return True, "saved login"
    if NUALT_SESSION and await _use_code_or_link(page, NUALT_SESSION):
        return True, "session code"
    await page.goto(NUALT_DASHBOARD_URL, timeout=45000)
    await _dashboard_state(page)
    # The one mail.tm mailbox is used for everything (lookup login and key creation)
    email = (await asyncio.to_thread(mailtm_get_account))[0]
    before = await asyncio.to_thread(mailtm_message_ids)
    await page.fill('#email', email)
    await page.click('#signin-btn')
    magic = await asyncio.to_thread(mailtm_wait_for_magic, before, 120)
    if not magic:
        return False, "no magic-link email arrived within 2 minutes"
    if await _use_code_or_link(page, magic):
        return True, "mail.tm magic link"
    return False, "magic link/code rejected"

async def nualt_browser_resolve(account, bank_code):
    """Fallback: drive the nuAlt dashboard in a headless browser. Returns (name, reason)."""
    global _BROWSER_LOCK
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None, "playwright not installed"
    if _BROWSER_LOCK is None:
        _BROWSER_LOCK = asyncio.Lock()
    async with _BROWSER_LOCK:  # one browser lookup at a time (memory friendly)
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
                try:
                    state = BROWSER_STATE_FILE if os.path.exists(BROWSER_STATE_FILE) else None
                    context = await browser.new_context(storage_state=state)
                    page = await context.new_page()
                    await page.goto(NUALT_DASHBOARD_URL, timeout=45000)
                    ok, how = await _browser_login(page)
                    if not ok:
                        return None, f"browser login failed: {how}"
                    logger.info(f"Browser login ok via {how}")
                    await context.storage_state(path=BROWSER_STATE_FILE)
                    await page.fill('#t-acc', account)
                    await page.fill('#t-bank', bank_code)
                    await page.evaluate("() => { const o = document.getElementById('test-out'); if (o) o.innerText = ''; }")
                    await page.click('#test-btn')
                    await page.wait_for_function(
                        "() => { const o = document.getElementById('test-out'); return o && o.innerText.trim().length > 0; }",
                        timeout=60000)
                    text = (await page.inner_text('#test-out')).strip()
                finally:
                    await browser.close()
        except Exception as e:
            logger.error(f"Browser fallback error: {e}")
            return None, f"browser error ({e.__class__.__name__})"
    logger.info(f"Browser fallback output: {text[:300]}")
    try:
        name = _find_account_name(json.loads(text))
    except ValueError:
        name = None
    return (name, "ok") if name else (None, "dashboard returned no account name")

_LAST_KEY_CREATE = 0.0

async def nualt_browser_create_key():
    """Click '+ Create new key' on the dashboard and capture the key (shown in full once).
    Returns (key or None, reason)."""
    global _BROWSER_LOCK
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None, "playwright not installed"
    if _BROWSER_LOCK is None:
        _BROWSER_LOCK = asyncio.Lock()
    find_js = ("() => { const re=/nualt_[A-Za-z0-9_\\-]{20,}/g; "
               "const t=document.body.innerText+' '+[...document.querySelectorAll('[data-copy]')]"
               ".map(e=>e.getAttribute('data-copy')).join(' '); return t.match(re) || []; }")
    async with _BROWSER_LOCK:
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
                try:
                    state = BROWSER_STATE_FILE if os.path.exists(BROWSER_STATE_FILE) else None
                    context = await browser.new_context(storage_state=state)
                    page = await context.new_page()
                    await page.goto(NUALT_DASHBOARD_URL, timeout=45000)
                    ok, how = await _browser_login(page)
                    if not ok:
                        return None, f"browser login failed: {how}"
                    await context.storage_state(path=BROWSER_STATE_FILE)
                    before = set(await page.evaluate(find_js))
                    await page.click('#new-key-btn')
                    key = None
                    for _ in range(40):  # up to ~20s
                        await asyncio.sleep(0.5)
                        new = [k for k in await page.evaluate(find_js) if k not in before]
                        if new:
                            key = new[0]
                            break
                finally:
                    await browser.close()
        except Exception as e:
            logger.error(f"Create-key error: {e}")
            return None, f"browser error ({e.__class__.__name__})"
    if not key:
        return None, "new key not found on the page"
    return key, "ok"

async def nualt_ensure_new_key():
    """Create + store a new API key (at most once per hour). Only for missing/invalid keys."""
    global NUALT_API_KEY, _LAST_KEY_CREATE
    if time.time() - _LAST_KEY_CREATE < 3600:
        logger.warning("Key creation skipped (cooldown)")
        return False
    _LAST_KEY_CREATE = time.time()
    key, reason = await nualt_browser_create_key()
    if not key:
        logger.error(f"Could not create nuAlt key: {reason}")
        return False
    with open(NUALT_KEY_FILE, 'w', encoding='utf-8') as f:
        f.write(key)
    NUALT_API_KEY = key
    logger.info("New nuAlt API key created and saved")
    return True

async def nualt_lookup(account, bank_code, bank_name):
    """API -> (new key if key missing/invalid) -> browser fallback. Returns (name, reason)."""
    name, reason = await asyncio.to_thread(nualt_resolve_account, account, bank_code, bank_name)
    if not name and ('(401)' in reason or 'NUALT_API_KEY is not set' in reason):
        if await nualt_ensure_new_key():
            name, reason = await asyncio.to_thread(nualt_resolve_account, account, bank_code, bank_name)
    if not name and not any(x in reason for x in ('(404)', '(422)')):
        logger.warning(f"API lookup failed ({reason}); trying browser fallback")
        name2, reason2 = await nualt_browser_resolve(account, bank_code)
        if name2:
            return name2, "browser fallback ok"
        reason = f"{reason}; browser fallback: {reason2}"
    return name, reason

# ======================== DATABASE ========================
class Database:
    def __init__(self, db_file):
        self.db_file = db_file
        self._init_database()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_database(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT, first_name TEXT, last_name TEXT,
                    full_name TEXT, language_code TEXT, is_bot INTEGER DEFAULT 0,
                    balance REAL DEFAULT 0,
                    total_referrals INTEGER DEFAULT 0,
                    referral_code TEXT UNIQUE,
                    referred_by INTEGER,
                    bank_name TEXT, bank_code TEXT,
                    account_number TEXT, account_name TEXT,
                    bank_verified INTEGER DEFAULT 0,
                    last_checkin TEXT, checkin_streak INTEGER DEFAULT 0,
                    total_tasks_completed INTEGER DEFAULT 0,
                    total_earned REAL DEFAULT 0, total_withdrawn REAL DEFAULT 0,
                    joined_date TEXT, last_active TEXT,
                    created_at TEXT, updated_at TEXT
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT, description TEXT, reward REAL,
                    type TEXT, requirement TEXT, image_id TEXT,
                    is_active INTEGER DEFAULT 1, created_at TEXT
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS completions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER, task_id INTEGER,
                    reward_earned REAL, status TEXT, completed_at TEXT
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS withdrawals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER, amount REAL,
                    bank_name TEXT, bank_code TEXT,
                    account_number TEXT, account_name TEXT,
                    status TEXT, requested_at TEXT, approved_at TEXT,
                    rejected_at TEXT, rejection_reason TEXT,
                    processed_by INTEGER, ref_id TEXT UNIQUE
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS banks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_code TEXT UNIQUE, bank_name TEXT
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER NOT NULL,
                    referred_id INTEGER NOT NULL UNIQUE,
                    status TEXT DEFAULT 'pending',
                    reward REAL DEFAULT 0,
                    created_at TEXT, completed_at TEXT
                )
            ''')
            cur.execute('''
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER, image_id TEXT, caption TEXT,
                    buttons TEXT, total_sent INTEGER DEFAULT 0,
                    total_failed INTEGER DEFAULT 0, sent_at TEXT
                )
            ''')
            cur.execute('CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id)')

            try:
                cur.execute("PRAGMA table_info(users)")
                cols = [r[1] for r in cur.fetchall()]
                if 'bank_code' not in cols:
                    cur.execute("ALTER TABLE users ADD COLUMN bank_code TEXT")
            except Exception:
                pass
            try:
                cur.execute("PRAGMA table_info(withdrawals)")
                cols = [r[1] for r in cur.fetchall()]
                if 'bank_code' not in cols:
                    cur.execute("ALTER TABLE withdrawals ADD COLUMN bank_code TEXT")
            except Exception:
                pass

            try:
                cur.execute("PRAGMA table_info(users)")
                ucols = [r[1] for r in cur.fetchall()]
                if 'captcha_verified' not in ucols:
                    cur.execute("ALTER TABLE users ADD COLUMN captcha_verified INTEGER DEFAULT 0")
            except Exception:
                pass

            # Always reset to the curated bank list (earlier versions overwrote it
            # with a different code system, which broke name resolution)
            cur.execute('DELETE FROM banks')
            if True:
                # CBN Codes expected by NU-ALT
                banks = [
                    ('044', 'Access Bank'), ('011', 'First Bank'), ('058', 'GTBank'),
                    ('033', 'UBA'), ('057', 'Zenith Bank'), ('070', 'Fidelity Bank'),
                    ('035', 'Wema Bank'), ('232', 'Sterling Bank'), ('214', 'FCMB'),
                    ('032', 'Union Bank'), ('050', 'Ecobank'), ('221', 'Stanbic IBTC'),
                    ('090267', 'Kuda Bank'),
                    ('100004', 'OPay'),       # Correct for NU-ALT
                    ('100033', 'PalmPay'),
                    ('090405', 'Moniepoint'),
                    ('altbank', 'AltBank'),  # no numeric code: nuAlt matches this name fragment
                    ('00003', 'Titan Trust Bank'), ('00004', 'Taj Bank'),
                    ('00005', 'Globus Bank'), ('100001', 'VFD Micro Finance Bank'),
                ]
                cur.executemany('INSERT INTO banks (bank_code, bank_name) VALUES (?, ?)', banks)
            conn.commit()

    def is_captcha_verified(self, user_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT captcha_verified FROM users WHERE user_id = ?', (user_id,))
            r = cur.fetchone()
            return bool(r and r['captcha_verified'])

    def set_captcha_verified(self, user_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('UPDATE users SET captcha_verified = 1 WHERE user_id = ?', (user_id,))
            conn.commit()

    def try_deduct_balance(self, user_id, amount):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('UPDATE users SET balance = balance - ?, updated_at = ? WHERE user_id = ? AND balance >= ?',
                        (amount, datetime.now().isoformat(), user_id, amount))
            conn.commit()
            return cur.rowcount > 0

    def get_user(self, user_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            r = cur.fetchone()
            return dict(r) if r else None

    def create_user(self, user_id, username='', first_name='', last_name='', language_code='en'):
        now = datetime.now().isoformat()
        full_name = f"{first_name} {last_name}".strip() or first_name or username or str(user_id)
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT OR IGNORE INTO users
                (user_id, username, first_name, last_name, full_name, language_code,
                 referral_code, joined_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, full_name, language_code,
                  str(user_id), now, now, now))
            conn.commit()
            return self.get_user(user_id)

    def update_user_balance(self, user_id, amount):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('UPDATE users SET balance = balance + ?, updated_at = ? WHERE user_id = ?',
                        (amount, datetime.now().isoformat(), user_id))
            conn.commit()
            cur.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            r = cur.fetchone()
            return r['balance'] if r else 0.0

    def update_user_bank_selection(self, user_id, bank_name, bank_code):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('UPDATE users SET bank_name = ?, bank_code = ?, updated_at = ? WHERE user_id = ?',
                        (bank_name, bank_code, datetime.now().isoformat(), user_id))
            conn.commit()

    def update_user_bank(self, user_id, bank_name, bank_code, account_number, account_name, verified=True):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                UPDATE users SET bank_name = ?, bank_code = ?, account_number = ?, 
                                account_name = ?, bank_verified = ?, updated_at = ?
                WHERE user_id = ?
            ''', (bank_name, bank_code, account_number, account_name, 1 if verified else 0,
                  datetime.now().isoformat(), user_id))
            conn.commit()

    def get_bank_by_name(self, name):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM banks WHERE bank_name = ?', (name,))
            r = cur.fetchone()
            return dict(r) if r else None

    def get_bank_by_code(self, code):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM banks WHERE bank_code = ?', (code,))
            r = cur.fetchone()
            return dict(r) if r else None

    def get_bank_code_by_name(self, name):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT bank_code FROM banks WHERE bank_name = ?', (name,))
            r = cur.fetchone()
            return r['bank_code'] if r else None

    def update_bank_code(self, old_code, new_code):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('UPDATE banks SET bank_code = ? WHERE bank_code = ?', (new_code, old_code))
            conn.commit()

    def get_banks(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM banks ORDER BY bank_name')
            return [dict(r) for r in cur.fetchall()]

    def cache_banks(self, banks_list):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('DELETE FROM banks')
            for b in banks_list:
                try:
                    cur.execute('INSERT OR IGNORE INTO banks (bank_code, bank_name) VALUES (?, ?)',
                                (b['code'], b['name']))
                except Exception:
                    pass
            conn.commit()

    def get_all_users(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM users')
            return [dict(r) for r in cur.fetchall()]

    def get_total_users(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) as c FROM users')
            r = cur.fetchone()
            return r['c'] if r else 0

    def increment_referrals(self, user_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('UPDATE users SET total_referrals = total_referrals + 1 WHERE user_id = ?', (user_id,))
            conn.commit()

    def set_referred_by(self, user_id, referrer_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (referrer_id, user_id))
            conn.commit()

    def update_last_checkin(self, user_id, streak):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('UPDATE users SET last_checkin = ?, checkin_streak = ? WHERE user_id = ?',
                        (datetime.now().isoformat(), streak, user_id))
            conn.commit()

    def get_last_checkin(self, user_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT last_checkin, checkin_streak FROM users WHERE user_id = ?', (user_id,))
            r = cur.fetchone()
            return dict(r) if r else None

    def create_task(self, title, description, reward, task_type, requirement, image_id=None):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO tasks (title, description, reward, type, requirement, image_id, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            ''', (title, description, reward, task_type, requirement, image_id, datetime.now().isoformat()))
            conn.commit()
            return cur.lastrowid

    def get_task(self, task_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
            r = cur.fetchone()
            return dict(r) if r else None

    def get_active_tasks(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM tasks WHERE is_active = 1 ORDER BY task_id')
            return [dict(r) for r in cur.fetchall()]

    def get_all_tasks(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM tasks ORDER BY task_id')
            return [dict(r) for r in cur.fetchall()]

    def update_task_status(self, task_id, is_active):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('UPDATE tasks SET is_active = ? WHERE task_id = ?', (1 if is_active else 0, task_id))
            conn.commit()

    def delete_task(self, task_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
            conn.commit()

    def get_task_completion_count(self, task_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as c FROM completions WHERE task_id = ? AND status = 'completed'", (task_id,))
            r = cur.fetchone()
            return r['c'] if r else 0

    def is_task_completed(self, user_id, task_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM completions WHERE user_id = ? AND task_id = ? AND status = 'completed'",
                        (user_id, task_id))
            return cur.fetchone() is not None

    def complete_task(self, user_id, task_id, reward):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO completions (user_id, task_id, reward_earned, status, completed_at)
                VALUES (?, ?, ?, 'completed', ?)
            ''', (user_id, task_id, reward, datetime.now().isoformat()))
            cur.execute('''
                UPDATE users SET total_tasks_completed = total_tasks_completed + 1,
                                 total_earned = total_earned + ?
                WHERE user_id = ?
            ''', (reward, user_id))
            conn.commit()

    def get_user_completed_tasks(self, user_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT * FROM completions WHERE user_id = ? AND status = 'completed'
                ORDER BY completed_at DESC
            ''', (user_id,))
            return [dict(r) for r in cur.fetchall()]

    def create_withdrawal(self, user_id, amount, bank_name, bank_code, account_number, account_name):
        ref_id = f"PP{int(time.time())}{random.randint(1000, 9999)}"
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO withdrawals (user_id, amount, bank_name, bank_code,
                                         account_number, account_name,
                                         status, requested_at, ref_id)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            ''', (user_id, amount, bank_name, bank_code, account_number, account_name,
                  datetime.now().isoformat(), ref_id))
            conn.commit()
            return cur.lastrowid, ref_id

    def get_pending_withdrawals(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM withdrawals WHERE status = 'pending' ORDER BY requested_at ASC")
            return [dict(r) for r in cur.fetchall()]

    def get_withdrawal(self, wid):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM withdrawals WHERE id = ?', (wid,))
            r = cur.fetchone()
            return dict(r) if r else None

    def approve_withdrawal(self, wid, admin_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE withdrawals SET status = 'approved', approved_at = ?, processed_by = ? "
                        "WHERE id = ? AND status = 'pending'",
                        (datetime.now().isoformat(), admin_id, wid))
            ok = cur.rowcount > 0
            if ok:
                cur.execute('SELECT user_id, amount FROM withdrawals WHERE id = ?', (wid,))
                w = cur.fetchone()
                if w:
                    cur.execute('UPDATE users SET total_withdrawn = COALESCE(total_withdrawn, 0) + ? WHERE user_id = ?',
                                (w['amount'], w['user_id']))
            conn.commit()
            return ok

    def reject_withdrawal(self, wid, admin_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE withdrawals SET status = 'rejected', rejected_at = ?, processed_by = ? "
                        "WHERE id = ? AND status = 'pending'",
                        (datetime.now().isoformat(), admin_id, wid))
            conn.commit()
            return cur.rowcount > 0

    def get_total_withdrawn(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT SUM(amount) as t FROM withdrawals WHERE status = 'approved'")
            r = cur.fetchone()
            return r['t'] if r and r['t'] else 0.0

    def get_total_completions(self):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as c FROM completions WHERE status = 'completed'")
            r = cur.fetchone()
            return r['c'] if r else 0

    def create_referral(self, referrer_id, referred_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute('''
                    INSERT INTO referrals (referrer_id, referred_id, status, created_at)
                    VALUES (?, ?, 'pending', ?)
                ''', (referrer_id, referred_id, datetime.now().isoformat()))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_referral_by_referred(self, referred_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM referrals WHERE referred_id = ?', (referred_id,))
            r = cur.fetchone()
            return dict(r) if r else None

    def mark_referral_paid(self, referred_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                UPDATE referrals SET status = 'paid', reward = ?, completed_at = ?
                WHERE referred_id = ? AND status != 'paid'
            ''', (REFERRAL_REWARD, datetime.now().isoformat(), referred_id))
            conn.commit()

    def get_referrer_stats(self, referrer_id):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN status = 'paid' THEN 1 ELSE 0 END) as paid,
                       SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                       COALESCE(SUM(CASE WHEN status = 'paid' THEN reward ELSE 0 END), 0) as earned
                FROM referrals WHERE referrer_id = ?
            ''', (referrer_id,))
            r = cur.fetchone()
            if not r:
                return {'total': 0, 'paid': 0, 'pending': 0, 'earned': 0}
            return {'total': r['total'] or 0, 'paid': r['paid'] or 0,
                    'pending': r['pending'] or 0, 'earned': r['earned'] or 0}

    def get_referrer_list(self, referrer_id, limit=20):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT r.*, u.first_name, u.username
                FROM referrals r
                LEFT JOIN users u ON u.user_id = r.referred_id
                WHERE r.referrer_id = ?
                ORDER BY r.created_at DESC LIMIT ?
            ''', (referrer_id, limit))
            return [dict(r) for r in cur.fetchall()]

    def save_broadcast(self, admin_id, image_id, caption, buttons, sent, failed):
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO broadcasts (admin_id, image_id, caption, buttons, total_sent, total_failed, sent_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (admin_id, image_id, caption, buttons, sent, failed, datetime.now().isoformat()))
            conn.commit()

db = Database(DB_FILE)

# ======================== USER HELPERS ========================
def get_or_create_user(update):
    try:
        u = update.effective_user
        existing = db.get_user(u.id)
        if not existing:
            db.create_user(u.id, u.username or '', u.first_name or '', u.last_name or '', u.language_code or 'en')
            existing = db.get_user(u.id)
        return existing
    except Exception as e:
        logger.error(f"get_or_create_user: {e}")
        return None

def get_user_display(user_id):
    try:
        u = db.get_user(user_id)
        if u:
            return u.get('full_name') or u.get('first_name') or u.get('username') or str(user_id)
    except Exception:
        pass
    return str(user_id)

async def check_forced_channels(context, user_id):
    not_joined = []
    for ch in FORCED_CHANNELS:
        try:
            username = ch['username'].lstrip('@')
            m = await context.bot.get_chat_member(f'@{username}', user_id)
            if m.status not in ['member', 'administrator', 'creator']:
                not_joined.append(ch)
        except Exception as e:
            logger.warning(f"Channel check failed {ch['username']}: {e}")
            not_joined.append(ch)
    return not_joined

async def process_referral_payout(context, referred_id):
    try:
        if REFERRAL_MIN_TASK_FOR_PAYOUT == 0:
            return
        referral = db.get_referral_by_referred(referred_id)
        if not referral or referral['status'] == 'paid':
            return
        user = db.get_user(referred_id)
        if not user or (user.get('total_tasks_completed') or 0) < REFERRAL_MIN_TASK_FOR_PAYOUT:
            return
        referrer_id = referral['referrer_id']
        db.update_user_balance(referrer_id, REFERRAL_REWARD)
        db.mark_referral_paid(referred_id)
        try:
            ref = db.get_user(referrer_id)
            bal = ref['balance'] if ref else 0
            await context.bot.send_message(
                chat_id=referrer_id,
                text=(f"💸 <b>Referral Bonus Unlocked!</b>\n\n"
                      f"Your invitee completed their first task.\n"
                      f"💰 Earned: {fmt(REFERRAL_REWARD)}\n"
                      f"💳 New Balance: {fmt(bal)}"),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.warning(f"Ref notify failed: {e}")
        try:
            await context.bot.send_message(
                chat_id=referred_id,
                text=(f"🎁 <b>Referral Bonus Activated!</b>\n\n"
                      f"Your referrer earned {fmt(REFERRAL_REWARD)} for bringing you in.\n"
                      f"Keep completing tasks! 🚀"),
                parse_mode='HTML'
            )
        except Exception:
            pass
    except Exception as e:
        logger.error(f"process_referral_payout: {e}")

# ======================== KEYBOARDS ========================
def get_main_keyboard(user_id):
    kb = [
        ['⭐ Dashboard', '🏆 Performance'],
        ['📝 Earn Tasks', '📅 Daily Check-in'],
        ['🏦 Set Bank', '👤 My Account'],
        ['👥 Refer & Earn', '💰 Withdraw'],
    ]
    if is_admin(user_id):
        kb.insert(0, ['🔧 Admin Panel'])
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        ['➕ Add Task', '📋 View Tasks'],
        ['✏️ Toggle Task', '🗑 Delete Task'],
        ['📊 Statistics', '💰 Manage Withdrawals'],
        ['📢 Broadcast', '🎁 Send Coins'],
        ['🔙 Back to Menu'],
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup([[CANCEL_TEXT]], resize_keyboard=True)

# ======================== CAPTCHA ========================
async def issue_captcha(target_message, context, user_id):
    try:
        sid = get_session(user_id) or new_session(user_id)
        question, correct, options, correct_index = generate_emoji_captcha()
        session_data(user_id)['captcha_correct'] = correct
        session_data(user_id)['captcha_question'] = question
        session_data(user_id)['captcha_attempts'] = 0
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(opt, callback_data=f"cp_{sid}_{i}")
            for i, opt in enumerate(options)
        ]])
        await target_message.reply_text(
            captcha_prompt_html(question),
            parse_mode='HTML',
            reply_markup=kb
        )
    except Exception as e:
        logger.error(f"issue_captcha: {e}")

async def captcha_answer_callback(update, context):
    try:
        q = update.callback_query
        await q.answer()
        user_id = q.from_user.id

        try:
            parts = q.data.split("_", 2)
            sid = parts[1]
            chosen_index = int(parts[2])
        except Exception as e:
            logger.error(f"Captcha parse error: {e} | data: {q.data}")
            await q.edit_message_text("❌ Invalid selection. Please use /start again.", parse_mode='HTML')
            return

        if not is_valid_session(user_id, sid):
            await q.edit_message_text(
                "⚠️ <b>Session expired.</b>\n\nPlease use /start again.",
                parse_mode='HTML'
            )
            return

        data = session_data(user_id)
        correct = data.get('captcha_correct')
        question = data.get('captcha_question', 'Security Check')

        if not correct:
            await q.edit_message_text("⚠️ No active challenge. Use /start.", parse_mode='HTML')
            return

        try:
            chosen_emoji = q.message.reply_markup.inline_keyboard[0][chosen_index].text
        except Exception as e:
            logger.error(f"Emoji extraction error: {e} | chosen_index: {chosen_index}")
            await q.edit_message_text("❌ Invalid selection. Please use /start again.", parse_mode='HTML')
            return

        if chosen_emoji == correct:
            data.pop('captcha_correct', None)
            data.pop('captcha_question', None)
            data.pop('captcha_attempts', None)
            data['captcha_verified'] = True
            db.set_captcha_verified(user_id)

            await q.edit_message_text(
                f"<b>✅ Verification Successful</b>\n\n"
                f"You have been verified as human.\n\n"
                f"Welcome to <b>{BOT_NAME}</b>! 🎉",
                parse_mode='HTML'
            )
            user_data = db.get_user(user_id)
            stats = db.get_referrer_stats(user_id)
            await q.message.reply_text(
                f"<b>⭐ WELCOME TO {BOT_NAME}! ⭐</b>\n\n"
                f"👋 Hello {esc(q.from_user.first_name or 'User')}!\n\n"
                f"💰 <b>Balance:</b> {fmt(user_data['balance'] if user_data else 0)}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 <b>Earning Opportunities:</b>\n"
                f"• 📝 Complete tasks for rewards\n"
                f"• 📅 Daily check-in: {fmt(DAILY_CHECKIN_MIN)} – {fmt(DAILY_CHECKIN_MAX)}\n"
                f"• 👥 Refer friends: {fmt(REFERRAL_REWARD)} each\n\n"
                f"💳 <b>Withdrawal:</b>\n"
                f"• Minimum: {fmt(MIN_WITHDRAWAL)}\n"
                f"• Maximum: {fmt(MAX_WITHDRAWAL)}\n\n"
                f"👥 <b>Your Referrals:</b> {stats['total']} "
                f"(Paid: {stats['paid']} | Pending: {stats['pending']})\n\n"
                f"🆘 <b>Support:</b> {SUPPORT_BOT}",
                parse_mode='HTML',
                reply_markup=get_main_keyboard(user_id)
            )
            return

        attempts = data.get('captcha_attempts', 0) + 1
        data['captcha_attempts'] = attempts

        if attempts >= CAPTCHA_MAX_ATTEMPTS:
            data['captcha_attempts'] = 0
            _, new_correct, new_options, _ = generate_emoji_captcha()
            data['captcha_correct'] = new_correct
            new_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(opt, callback_data=f"cp_{sid}_{i}")
                for i, opt in enumerate(new_options)
            ]])
            await q.edit_message_text(
                f"<b>❌ Verification Failed</b>\n\n"
                f"Too many incorrect attempts.\n\n"
                f"Please solve the new challenge below:",
                parse_mode='HTML',
                reply_markup=new_kb
            )
            return

        remaining = CAPTCHA_MAX_ATTEMPTS - attempts
        await q.edit_message_text(
            f"<b>❌ Incorrect Selection</b>\n\n"
            f"<b>📋 Challenge:</b> {esc(question)}\n\n"
            f"⚠️ You have <b>{remaining}</b> attempt{'s' if remaining != 1 else ''} remaining.\n\n"
            f"<b>👇 Tap the correct emoji:</b>",
            parse_mode='HTML',
            reply_markup=q.message.reply_markup
        )
    except Exception as e:
        logger.error(f"captcha_answer_callback: {e}\n{traceback.format_exc()}")
        await q.edit_message_text("❌ An error occurred. Please use /start again.")

# ======================== FORCE JOIN ========================
async def show_force_join_message(update, context):
    try:
        not_joined = await check_forced_channels(context, update.effective_user.id)
        if not not_joined:
            return True
        sid = get_session(update.effective_user.id) or new_session(update.effective_user.id)
        text = (f"<b>⭐ Access Restricted ⭐</b>\n\n"
                f"Hello {esc(update.effective_user.first_name or 'User')},\n\n"
                f"To use <b>{BOT_NAME}</b>, you must join our channels first.\n\n"
                f"<b>📢 Please join:</b>\n")
        kb = []
        for ch in not_joined:
            text += f"\n• {esc(ch['name'])}: {ch['link']}"
            kb.append([InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch['link'])])
        text += "\n\n⚠️ <b>After joining, click to verify:</b>"
        kb.append([InlineKeyboardButton("✅ I've Joined — Check Again", callback_data=f"join_{sid}")])
        kb.append([InlineKeyboardButton("🆘 Support", url=SUPPORT_BOT)])
        await send_html(update, text, reply_markup=InlineKeyboardMarkup(kb))
        return False
    except Exception as e:
        logger.error(f"show_force_join_message: {e}")
        await send_html(update, "⭐ Welcome!", reply_markup=get_main_keyboard(update.effective_user.id))
        return True

async def show_force_join_callback(update, context):
    try:
        q = update.callback_query
        await q.answer()
        user_id = q.from_user.id
        try:
            _, sid = q.data.split("_", 1)
        except ValueError:
            sid = get_session(user_id)
        if not sid or not is_valid_session(user_id, sid):
            await q.edit_message_text("⚠️ Session expired. Use /start again.", parse_mode='HTML')
            return

        not_joined = await check_forced_channels(context, user_id)
        if not not_joined:
            await q.edit_message_text(
                "✅ <b>All channels joined!</b>\n\nProceeding to verification...",
                parse_mode='HTML'
            )
            await issue_captcha(q.message, context, user_id)
            return

        text = (f"<b>⭐ Access Restricted ⭐</b>\n\n"
                f"To use <b>{BOT_NAME}</b>, you must join our channels first.\n\n"
                f"<b>📢 Please join:</b>\n")
        kb = []
        for ch in not_joined:
            text += f"\n• {esc(ch['name'])}: {ch['link']}"
            kb.append([InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch['link'])])
        text += "\n\n⚠️ <b>After joining, click to verify:</b>"
        kb.append([InlineKeyboardButton("✅ I've Joined — Check Again", callback_data=f"join_{sid}")])
        kb.append([InlineKeyboardButton("🆘 Support", url=SUPPORT_BOT)])
        await q.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))
    except Exception as e:
        logger.error(f"show_force_join_callback: {e}")

async def gate(update, context):
    """Force-join + CAPTCHA check for entry points that live outside handle_menu."""
    user_id = update.effective_user.id
    if await check_forced_channels(context, user_id):
        await show_force_join_message(update, context)
        return False
    if not db.is_captcha_verified(user_id):
        await issue_captcha(update.message, context, user_id)
        return False
    return True

# ======================== START ========================
async def start_command(update, context):
    try:
        user = update.effective_user
        user_id = user.id
        logger.info(f"Start from {user_id}")
        user_data = get_or_create_user(update)
        if not user_data:
            await send_html(update, "❌ Error creating user. Please try again.")
            return

        context.user_data.clear()
        new_session(user_id)

        args = context.args
        if args and args[0].isdigit():
            referrer_id = int(args[0])
            if referrer_id != user_id and db.get_user(referrer_id):
                current = db.get_user(user_id)
                if not current.get('referred_by'):
                    if db.create_referral(referrer_id, user_id):
                        db.increment_referrals(referrer_id)
                        db.set_referred_by(user_id, referrer_id)
                        if REFERRAL_MIN_TASK_FOR_PAYOUT == 0:
                            db.update_user_balance(referrer_id, REFERRAL_REWARD)
                            db.mark_referral_paid(user_id)
                            await send_html(
                                update,
                                f"🎉 <b>Welcome!</b>\n\n"
                                f"You were referred by {esc(get_user_display(referrer_id))}.\n"
                                f"🎁 They earned {fmt(REFERRAL_REWARD)}!"
                            )
                        else:
                            await send_html(
                                update,
                                f"🎉 <b>Welcome!</b>\n\n"
                                f"You were referred by {esc(get_user_display(referrer_id))}.\n\n"
                                f"📝 Complete your first task to unlock their {fmt(REFERRAL_REWARD)} bonus!"
                            )

        not_joined = await check_forced_channels(context, user_id)
        if not_joined:
            await show_force_join_message(update, context)
            return

        if not db.is_captcha_verified(user_id):
            await issue_captcha(update.message, context, user_id)
            return

        user_data = db.get_user(user_id)
        stats = db.get_referrer_stats(user_id)
        await send_html(
            update,
            f"<b>⭐ WELCOME TO {BOT_NAME}! ⭐</b>\n\n"
            f"👋 Hello {esc(user.first_name or 'User')}!\n\n"
            f"💰 <b>Balance:</b> {fmt(user_data['balance'])}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Earning Opportunities:</b>\n"
            f"• 📝 Complete tasks for rewards\n"
            f"• 📅 Daily check-in: {fmt(DAILY_CHECKIN_MIN)} – {fmt(DAILY_CHECKIN_MAX)}\n"
            f"• 👥 Refer friends: {fmt(REFERRAL_REWARD)} each\n\n"
            f"💳 <b>Withdrawal:</b>\n"
            f"• Minimum: {fmt(MIN_WITHDRAWAL)}\n"
            f"• Maximum: {fmt(MAX_WITHDRAWAL)}\n\n"
            f"👥 <b>Your Referrals:</b> {stats['total']} (Paid: {stats['paid']} | Pending: {stats['pending']})\n\n"
            f"🆘 <b>Support:</b> {SUPPORT_BOT}",
            reply_markup=get_main_keyboard(user_id)
        )
    except Exception as e:
        logger.error(f"start_command: {e}\n{traceback.format_exc()}")
        await send_html(update, "❌ An error occurred. Please try again.")

_CONVERSATION_BUTTONS = {'🏦 Set Bank', '💰 Withdraw', '➕ Add Task', '📢 Broadcast', '🎁 Send Coins'}
MENU_TEXTS = (
    {getattr(b, 'text', b) for row in get_main_keyboard(0).keyboard for b in row}
    | {getattr(b, 'text', b) for row in get_admin_keyboard().keyboard for b in row}
) - _CONVERSATION_BUTTONS | {'🔧 Admin Panel'}

# ======================== HELP / BALANCE / REFERRAL ========================
async def help_command(update, context):
    try:
        if await check_forced_channels(context, update.effective_user.id):
            await show_force_join_message(update, context)
            return
        await send_html(
            update,
            f"<b>📖 {BOT_NAME} Help</b>\n\n"
            f"<b>How to Earn:</b>\n"
            f"1. 📝 Complete tasks from Earn Tasks\n"
            f"2. 📅 Daily check-in: {fmt(DAILY_CHECKIN_MIN)} – {fmt(DAILY_CHECKIN_MAX)}\n"
            f"3. 👥 Refer friends: {fmt(REFERRAL_REWARD)} each\n\n"
            f"<b>How to Withdraw:</b>\n"
            f"1. 🏦 Set your bank account\n"
            f"2. 💰 Minimum: {fmt(MIN_WITHDRAWAL)}\n"
            f"3. 📋 Wait for admin approval\n\n"
            f"<b>Support:</b> {SUPPORT_BOT}"
        )
    except Exception as e:
        logger.error(f"help_command: {e}")

async def balance_command(update, context):
    try:
        if await check_forced_channels(context, update.effective_user.id):
            await show_force_join_message(update, context)
            return
        user = db.get_user(update.effective_user.id)
        if not user:
            await send_html(update, "❌ Please use /start first.")
            return
        await send_html(
            update,
            f"<b>💰 Your Balance</b>\n\n"
            f"Current: {fmt(user['balance'])}\n"
            f"Total Earned: {fmt(user.get('total_earned') or 0)}\n"
            f"Total Withdrawn: {fmt(user.get('total_withdrawn') or 0)}\n"
            f"Referrals: {user['total_referrals']}\n\n"
            f"💳 Minimum Withdrawal: {fmt(MIN_WITHDRAWAL)}"
        )
    except Exception as e:
        logger.error(f"balance_command: {e}")

async def referral_command(update, context):
    try:
        user_id = update.effective_user.id
        if await check_forced_channels(context, user_id):
            await show_force_join_message(update, context)
            return
        user = db.get_user(user_id)
        if not user:
            await send_html(update, "❌ Please use /start first.")
            return
        stats = db.get_referrer_stats(user_id)
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user['referral_code']}"
        await send_html(
            update,
            f"<b>👥 Refer &amp; Earn</b>\n\n"
            f"💰 Earn <b>{fmt(REFERRAL_REWARD)}</b> for every successful referral!\n\n"
            f"📊 <b>Your Stats:</b>\n"
            f"• Total: {stats['total']}\n"
            f"• Paid: {stats['paid']}\n"
            f"• Pending: {stats['pending']}\n"
            f"• Earned: {fmt(stats['earned'])}\n\n"
            f"🔗 <b>Your Referral Link:</b>\n"
            f"<code>{referral_link}</code>\n\n"
            f"📢 Share — you get paid when your invitee completes a task!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={referral_link}")],
                [InlineKeyboardButton("📋 Copy Link", callback_data="copy_referral_link")],
                [InlineKeyboardButton("👥 View Referrals", callback_data="view_referrals")],
            ])
        )
    except Exception as e:
        logger.error(f"referral_command: {e}")

# ======================== MENU ========================
async def handle_menu(update, context):
    try:
        user_id = update.effective_user.id
        text = update.message.text
        logger.info(f"Menu '{text}' from {user_id}")

        if text not in MENU_TEXTS:
            return  # free text (bank names, account numbers, ...) belongs to conversations

        if text != '🔧 Admin Panel':
            if await check_forced_channels(context, user_id):
                await show_force_join_message(update, context)
                return
            if not db.is_captcha_verified(user_id):
                await issue_captcha(update.message, context, user_id)
                return

        if text == '🔧 Admin Panel' and is_admin(user_id):
            await send_html(update, "🔧 <b>Admin Panel</b>\n\nSelect an option:", reply_markup=get_admin_keyboard())
            return
        if text == '🔙 Back to Menu':
            await send_html(update, "⭐ <b>Main Menu</b>", reply_markup=get_main_keyboard(user_id))
            return
        if text == '⭐ Dashboard':
            await dashboard(update, context); return
        if text == '🏆 Performance':
            await performance(update, context); return
        if text == '📝 Earn Tasks':
            await show_tasks(update, context); return
        if text == '📅 Daily Check-in':
            await daily_checkin(update, context); return
        if text == '👤 My Account':
            await my_account(update, context); return
        if text == '👥 Refer & Earn':
            await referral_command(update, context); return

        if text == '📋 View Tasks' and is_admin(user_id):
            await view_all_tasks(update, context); return
        if text == '📊 Statistics' and is_admin(user_id):
            await admin_statistics(update, context); return
        if text == '💰 Manage Withdrawals' and is_admin(user_id):
            await manage_withdrawals(update, context); return
        if text == '🗑 Delete Task' and is_admin(user_id):
            await delete_task_start(update, context); return
        if text == '✏️ Toggle Task' and is_admin(user_id):
            await toggle_task_start(update, context); return
    except Exception as e:
        logger.error(f"handle_menu: {e}\n{traceback.format_exc()}")
        await send_html(update, "❌ An error occurred.")

# ======================== DASHBOARD / PERFORMANCE ========================
async def dashboard(update, context):
    try:
        user = db.get_user(update.effective_user.id)
        if not user:
            await send_html(update, "❌ Please use /start first.")
            return
        completed = db.get_user_completed_tasks(user['user_id'])
        total_completed = len(completed)
        total_earned = sum(t.get('reward_earned', 0) for t in completed)
        stats = db.get_referrer_stats(user['user_id'])
        last_ci = user.get('last_checkin')
        try:
            last_ci = datetime.fromisoformat(last_ci).strftime('%Y-%m-%d %H:%M') if last_ci else 'Never'
        except Exception:
            last_ci = 'Never'
        await send_html(
            update,
            f"<b>📊 Your Dashboard</b>\n\n"
            f"👤 {esc(update.effective_user.first_name or 'User')}\n"
            f"💰 Balance: {fmt(user['balance'])}\n"
            f"📝 Tasks: {total_completed}\n"
            f"🏆 Total Earned: {fmt(total_earned)}\n"
            f"👥 Referrals: {user['total_referrals']}\n"
            f"💸 Referral Earnings: {fmt(stats['earned'])}\n"
            f"📅 Last Check-in: {last_ci}\n\n"
            f"💳 Min Withdrawal: {fmt(MIN_WITHDRAWAL)}\n"
            f"🆘 Support: {SUPPORT_BOT}"
        )
    except Exception as e:
        logger.error(f"dashboard: {e}")

async def performance(update, context):
    try:
        await send_html(
            update,
            f"<b>🏆 {BOT_NAME} Performance</b>\n\n"
            f"📊 Total Users: {db.get_total_users()}\n"
            f"💰 Total Withdrawals Paid: {fmt(db.get_total_withdrawn())}\n\n"
            f"🔄 Active Tasks: {len(db.get_active_tasks())}\n"
            f"📝 Total Completions: {db.get_total_completions()}\n\n"
            f"⭐ Powered by {BOT_NAME}"
        )
    except Exception as e:
        logger.error(f"performance: {e}")

# ======================== TASKS ========================
async def show_tasks(update, context):
    try:
        user_id = update.effective_user.id
        tasks = db.get_active_tasks()
        logger.info(f"User {user_id} viewing {len(tasks)} tasks")
        if not tasks:
            await send_html(update, "📝 <b>Task Center</b>\n\nNo tasks available. Check back later!")
            return
        type_map = {
            'join_channel': '📢 Join Channel',
            'visit_link': '🔗 Visit Link',
            'watch_video': '🎬 Watch Video',
            'simple': '✅ Simple Task',
        }
        sid = get_session(user_id) or new_session(user_id)
        for task in tasks:
            completed = db.is_task_completed(user_id, task['task_id'])
            status = "✅" if completed else "⭐"
            type_display = type_map.get(task['type'], task['type'])
            text = (f"{status} <b>{esc(task['title'])}</b>\n\n"
                    f"📝 {esc(task['description'])}\n"
                    f"💰 Reward: {fmt(task['reward'])}\n"
                    f"📌 Type: {type_display}")
            kb = []
            if not completed:
                kb.append([InlineKeyboardButton(
                    f"▶️ Start {task['title']}",
                    callback_data=f"t_{sid}_{task['task_id']}"
                )])
            if task.get('image_id'):
                caption = text + ("\n\n✅ <b>Completed!</b>" if completed else "")
                await send_html_photo(update, photo=task['image_id'], caption=caption,
                                      reply_markup=InlineKeyboardMarkup(kb) if kb else None)
            else:
                if completed:
                    text += "\n\n✅ <b>Completed!</b>"
                await send_html(update, text, reply_markup=InlineKeyboardMarkup(kb) if kb else None)
    except Exception as e:
        logger.error(f"show_tasks: {e}\n{traceback.format_exc()}")
        await send_html(update, "❌ Error loading tasks. Please try again.")

async def task_callback(update, context):
    try:
        q = update.callback_query
        await q.answer()
        user_id = q.from_user.id
        try:
            _, sid, task_id_str = q.data.split("_", 2)
            task_id = int(task_id_str)
        except Exception:
            await q.edit_message_text("❌ Invalid task.")
            return
        if not is_valid_session(user_id, sid):
            await q.edit_message_text("⚠️ Session expired. Use /start again.", parse_mode='HTML')
            return
        if await check_forced_channels(context, user_id):
            await q.edit_message_text(
                "⚠️ <b>Please join all required channels first.</b>\n\nUse /start to verify.",
                parse_mode='HTML'
            )
            return
        if not db.is_captcha_verified(user_id):
            await q.edit_message_text(
                "⚠️ <b>Please verify you are human first.</b>\n\nUse /start to complete verification.",
                parse_mode='HTML'
            )
            return
        task = db.get_task(task_id)
        if not task:
            await q.edit_message_text("❌ Task not found.")
            return
        if db.is_task_completed(user_id, task_id):
            await q.edit_message_text("✅ You've already completed this task!")
            return

        if task['type'] == 'join_channel':
            text = (f"<b>📢 Join Channel Task</b>\n\n"
                    f"📝 {esc(task['description'])}\n\n"
                    f"🔗 Please join: {esc(task['requirement'])}\n\n"
                    f"After joining, click below to verify:")
            await q.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Verify Join", callback_data=f"vj_{sid}_{task_id}")
            ]]))
        elif task['type'] in ['visit_link', 'watch_video']:
            emoji = "🔗" if task['type'] == 'visit_link' else "🎬"
            label = "Visit" if task['type'] == 'visit_link' else "Watch"
            text = (f"<b>{emoji} {label} Link Task</b>\n\n"
                    f"📝 {esc(task['description'])}\n\n"
                    f"🌐 Link: {esc(task['requirement'])}\n\n"
                    f"After {label.lower()}ing, click below to verify:")
            await q.edit_message_text(text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"✅ Verify {label}", callback_data=f"vv_{sid}_{task_id}")
            ]]))
        else:
            db.complete_task(user_id, task_id, task['reward'])
            new_bal = db.update_user_balance(user_id, task['reward'])
            await q.edit_message_text(
                f"✅ <b>Task Completed!</b>\n\n"
                f"💰 Earned: {fmt(task['reward'])}\n"
                f"💳 New Balance: {fmt(new_bal)}",
                parse_mode='HTML'
            )
            await process_referral_payout(context, user_id)
    except Exception as e:
        logger.error(f"task_callback: {e}\n{traceback.format_exc()}")
        try:
            await update.callback_query.edit_message_text("❌ An error occurred.")
        except Exception:
            pass

async def verify_join_callback(update, context):
    try:
        q = update.callback_query
        await q.answer()
        user_id = q.from_user.id
        try:
            _, sid, task_id_str = q.data.split("_", 2)
            task_id = int(task_id_str)
        except Exception:
            await q.edit_message_text("❌ Invalid task.")
            return
        if not is_valid_session(user_id, sid):
            await q.edit_message_text("⚠️ Session expired. Use /start again.", parse_mode='HTML')
            return
        task = db.get_task(task_id)
        if not task:
            await q.edit_message_text("❌ Task not found.")
            return
        if db.is_task_completed(user_id, task_id):
            await q.edit_message_text("✅ You've already completed this task!")
            return
        try:
            ch = task['requirement'].lstrip('@').strip()
            m = await context.bot.get_chat_member(f'@{ch}', user_id)
            if m.status in ['member', 'administrator', 'creator']:
                db.complete_task(user_id, task_id, task['reward'])
                new_bal = db.update_user_balance(user_id, task['reward'])
                await q.edit_message_text(
                    f"✅ <b>Verified! Task Completed!</b>\n\n"
                    f"💰 Earned: {fmt(task['reward'])}\n"
                    f"💳 New Balance: {fmt(new_bal)}",
                    parse_mode='HTML'
                )
                await process_referral_payout(context, user_id)
            else:
                await q.edit_message_text(
                    f"❌ You haven't joined {esc(task['requirement'])} yet.\nPlease join and try again.",
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.warning(f"verify_join check: {e}")
            await q.edit_message_text(
                f"❌ Could not verify. Please join {esc(task['requirement'])} and try again.",
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"verify_join_callback: {e}")

async def verify_visit_callback(update, context):
    try:
        q = update.callback_query
        await q.answer()
        user_id = q.from_user.id
        try:
            _, sid, task_id_str = q.data.split("_", 2)
            task_id = int(task_id_str)
        except Exception:
            await q.edit_message_text("❌ Invalid task.")
            return
        if not is_valid_session(user_id, sid):
            await q.edit_message_text("⚠️ Session expired. Use /start again.", parse_mode='HTML')
            return
        task = db.get_task(task_id)
        if not task:
            await q.edit_message_text("❌ Task not found.")
            return
        if db.is_task_completed(user_id, task_id):
            await q.edit_message_text("✅ You've already completed this task!")
            return
        db.complete_task(user_id, task_id, task['reward'])
        new_bal = db.update_user_balance(user_id, task['reward'])
        await q.edit_message_text(
            f"✅ <b>Task Completed!</b>\n\n"
            f"💰 Earned: {fmt(task['reward'])}\n"
            f"💳 New Balance: {fmt(new_bal)}",
            parse_mode='HTML'
        )
        await process_referral_payout(context, user_id)
    except Exception as e:
        logger.error(f"verify_visit_callback: {e}")

# ======================== DAILY CHECK-IN ========================
async def daily_checkin(update, context):
    try:
        user_id = update.effective_user.id
        user = db.get_user(user_id)
        if not user:
            await send_html(update, "❌ Please use /start first.")
            return
        info = db.get_last_checkin(user_id)
        today = datetime.now().date()
        if info and info.get('last_checkin'):
            try:
                last_date = datetime.fromisoformat(info['last_checkin']).date()
                if last_date == today:
                    await send_html(
                        update,
                        f"⏰ <b>Already checked in today!</b>\n\n"
                        f"Come back tomorrow! 🌟\n"
                        f"📅 Range: {fmt(DAILY_CHECKIN_MIN)} – {fmt(DAILY_CHECKIN_MAX)}"
                    )
                    return
            except Exception:
                pass
        streak = 1
        if info and info.get('last_checkin'):
            try:
                last_date = datetime.fromisoformat(info['last_checkin']).date()
                if (today - last_date).days == 1:
                    streak = (info.get('checkin_streak') or 0) + 1
            except Exception:
                streak = 1
        reward = get_daily_checkin_reward()
        db.update_last_checkin(user_id, streak)
        new_bal = db.update_user_balance(user_id, reward)
        await send_html(
            update,
            f"✅ <b>Check-in Successful!</b>\n\n"
            f"💰 +{fmt(reward)}\n"
            f"🔥 Streak: {streak} day{'s' if streak > 1 else ''}\n"
            f"💳 New Balance: {fmt(new_bal)}\n\n"
            f"Come back tomorrow! 🌟"
        )
    except Exception as e:
        logger.error(f"daily_checkin: {e}")

# ======================== BANK SETUP ========================
async def set_bank_start(update, context):
    try:
        user_id = update.effective_user.id
        if not await gate(update, context):
            return ConversationHandler.END
        context.user_data.clear()

        banks = db.get_banks()
        if not banks:
            await send_html(
                update,
                "❌ <b>Bank list unavailable.</b> Please try again later.",
                reply_markup=get_main_keyboard(user_id)
            )
            return ConversationHandler.END

        kb = bank_rows(banks)
        kb.append([CANCEL_TEXT])
        await send_html(
            update,
            "🏦 <b>Set Bank Account — Step 1 of 2</b>\n\nPlease select your bank:",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
        )
        return BANK_SELECT
    except Exception as e:
        logger.error(f"set_bank_start: {e}")
        return ConversationHandler.END

async def set_bank_name(update, context):
    try:
        if is_cancel(update.message.text):
            await send_html(
                update,
                "❌ <b>Bank setup cancelled.</b>",
                reply_markup=get_main_keyboard(update.effective_user.id)
            )
            context.user_data.clear()
            clear_session(update.effective_user.id)
            return ConversationHandler.END

        bank_name = update.message.text.strip()
        bank = db.get_bank_by_name(bank_name)

        if not bank:
            await send_html(
                update,
                "❌ <b>Invalid bank.</b> Please choose from the list below:",
                reply_markup=ReplyKeyboardMarkup(
                    bank_rows(db.get_banks()) + [[CANCEL_TEXT]],
                    resize_keyboard=True
                )
            )
            return BANK_SELECT

        bank_code = bank.get('bank_code') or ''
        context.user_data['bank_name'] = bank_name
        context.user_data['bank_code'] = bank_code

        user = update.effective_user
        db.update_user_bank_selection(user.id, bank_name, bank_code)

        await send_html(
            update,
            f"🏦 <b>Step 2 of 2</b>\n\n"
            f"Selected: <b>{esc(bank_name)}</b>\n"
            f"🏷️ Bank Code: <code>{esc(bank_code)}</code>\n\n"
            f"Enter your <b>10-digit account number</b>:\n\n"
            f"<i>Tap 🔙 Cancel to abort</i>",
            reply_markup=cancel_kb()
        )
        return BANK_ACCOUNT_NUMBER
    except Exception as e:
        logger.error(f"set_bank_name: {e}")
        return ConversationHandler.END

async def set_account_number(update, context):
    try:
        if is_cancel(update.message.text):
            await send_html(
                update,
                "❌ <b>Bank setup cancelled.</b>",
                reply_markup=get_main_keyboard(update.effective_user.id)
            )
            context.user_data.clear()
            clear_session(update.effective_user.id)
            return ConversationHandler.END

        account_number = update.message.text.strip()
        if not account_number.isdigit() or len(account_number) != 10:
            await send_html(
                update,
                "❌ <b>Invalid account number.</b>\n\n"
                "Please enter a valid <b>10-digit</b> number,\n"
                "or tap 🔙 Cancel to abort.",
                reply_markup=cancel_kb()
            )
            return BANK_ACCOUNT_NUMBER

        user = update.effective_user

        # Recover bank_name / bank_code from context or DB
        bank_name = context.user_data.get('bank_name')
        bank_code = context.user_data.get('bank_code')

        if not bank_name or not bank_code:
            user_data = db.get_user(user.id)
            if user_data:
                bank_name = bank_name or user_data.get('bank_name')
                bank_code = bank_code or user_data.get('bank_code')
                if not bank_code and bank_name:
                    bank_code = db.get_bank_code_by_name(bank_name)

        if not bank_name or not bank_code:
            await send_html(
                update,
                "❌ <b>Bank selection lost.</b>\n\n"
                "Please restart by tapping 🏦 Set Bank.",
                reply_markup=get_main_keyboard(user.id)
            )
            context.user_data.clear()
            return ConversationHandler.END

        # Enforce name ↔ code pairing
        cached = db.get_bank_by_code(bank_code)
        if not cached or cached.get('bank_name') != bank_name:
            by_name = db.get_bank_by_name(bank_name)
            if by_name:
                bank_code = by_name.get('bank_code') or bank_code
            else:
                await send_html(
                    update,
                    "❌ <b>Bank data mismatch.</b> Please restart bank setup.",
                    reply_markup=get_main_keyboard(user.id)
                )
                context.user_data.clear()
                return ConversationHandler.END

        await send_html(
            update,
            "⏳ <b>Validating account format...</b>\n\n"
            "Tap 🔙 Cancel to abort.",
            reply_markup=cancel_kb()
        )

        # Step 1: Mansa NUBAN check (None = service unavailable, so skip it)
        valid = None if bank_name.lower() in WALLET_BANK_NAMES else await asyncio.to_thread(mansa_validate_nuban, account_number, bank_code)
        if valid is False:
            await send_html(
                update,
                f"❌ <b>Invalid Account Number</b>\n\n"
                f"🏦 Bank: {esc(bank_name)}\n"
                f"🔢 Account: {account_number}\n\n"
                f"This account number does not match the selected bank.\n\n"
                f"Please try again or tap 🔙 Cancel to abort.",
                reply_markup=cancel_kb()
            )
            return BANK_ACCOUNT_NUMBER

        # Step 2: NU-ALT name enquiry
        await send_html(update, "⏳ <b>Resolving account name...</b>\n\nThis can take up to a minute.")
        account_name, reason = await nualt_lookup(account_number, bank_code, bank_name)

        if account_name:
            context.user_data['account_name'] = account_name
            db.update_user_bank(user.id, bank_name, bank_code, account_number, account_name, verified=True)
            await send_html(
                update,
                f"✅ <b>Bank Account Verified!</b>\n\n"
                f"🏦 Bank: {esc(bank_name)}\n"
                f"🏷️ Code: <code>{esc(bank_code)}</code>\n"
                f"👤 Account Name: <b>{esc(account_name)}</b>\n"
                f"🔢 Account Number: {account_number}\n\n"
                f"You can now withdraw! 💰",
                reply_markup=get_main_keyboard(user.id)
            )
            context.user_data.clear()
            clear_session(user.id)
            return ConversationHandler.END

        # Fallback: manual name entry
        logger.warning(f"Name resolve failed for {bank_code}/{account_number}: {reason}")
        admin_note = f"\n🛠 <i>Admin info: {esc(reason)}</i>\n" if is_admin(user.id) else ""
        await send_html(
            update,
            "⚠️ <b>Automatic Name Resolution Unavailable</b>\n\n"
            "We couldn't fetch the account name automatically.\n\n"
            f"🏦 Bank: {esc(bank_name)}\n"
            f"🏷️ Code: <code>{esc(bank_code)}</code>\n"
            f"🔢 Account: {account_number}\n"
            f"{admin_note}\n"
            "Please type your <b>full account name</b>,\n"
            "or tap 🔙 Cancel to abort:",
            reply_markup=cancel_kb()
        )
        context.user_data['pending_account_number'] = account_number
        return BANK_ACCOUNT_NAME
    except Exception as e:
        logger.error(f"set_account_number: {e}")
        await send_html(
            update,
            "❌ An error occurred. Please try again.",
            reply_markup=get_main_keyboard(update.effective_user.id)
        )
        context.user_data.clear()
        return ConversationHandler.END

async def set_account_name(update, context):
    try:
        if is_cancel(update.message.text):
            await send_html(
                update,
                "❌ <b>Bank setup cancelled.</b>",
                reply_markup=get_main_keyboard(update.effective_user.id)
            )
            context.user_data.clear()
            clear_session(update.effective_user.id)
            return ConversationHandler.END

        account_name = update.message.text.strip()
        if len(account_name) < 2:
            await send_html(
                update,
                "❌ Please enter a valid account name (≥2 characters),\n"
                "or tap 🔙 Cancel to abort:",
                reply_markup=cancel_kb()
            )
            return BANK_ACCOUNT_NAME

        user = update.effective_user
        bank_name = context.user_data.get('bank_name')
        bank_code = context.user_data.get('bank_code')
        account_number = context.user_data.get('pending_account_number')

        if not bank_name or not bank_code:
            user_data = db.get_user(user.id)
            if user_data:
                bank_name = bank_name or user_data.get('bank_name')
                bank_code = bank_code or user_data.get('bank_code')
                if not bank_code and bank_name:
                    bank_code = db.get_bank_code_by_name(bank_name)

        if not bank_name:
            await send_html(
                update,
                "❌ Bank selection lost. Please restart bank setup.",
                reply_markup=get_main_keyboard(user.id)
            )
            context.user_data.clear()
            return ConversationHandler.END

        if not account_number:
            await send_html(update, "❌ Account number lost. Please restart bank setup.",
                            reply_markup=get_main_keyboard(user.id))
            context.user_data.clear()
            return ConversationHandler.END

        cached = db.get_bank_by_code(bank_code or '')
        if not cached or cached.get('bank_name') != bank_name:
            by_name = db.get_bank_by_name(bank_name)
            if by_name:
                bank_code = by_name.get('bank_code') or bank_code

        db.update_user_bank(user.id, bank_name, bank_code or '', account_number, account_name, verified=False)

        await send_html(
            update,
            f"✅ <b>Bank Account Saved</b>\n\n"
            f"🏦 Bank: {esc(bank_name)}\n"
            f"🏷️ Code: <code>{esc(bank_code or 'N/A')}</code>\n"
            f"👤 Account Name: {esc(account_name)}\n"
            f"🔢 Account Number: {account_number}\n\n"
            f"You can now withdraw! 💰",
            reply_markup=get_main_keyboard(user.id)
        )
        context.user_data.clear()
        clear_session(user.id)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"set_account_name: {e}")
        context.user_data.clear()
        return ConversationHandler.END

async def cancel_bank_setup(update, context):
    await send_html(
        update,
        "❌ <b>Bank setup cancelled.</b>",
        reply_markup=get_main_keyboard(update.effective_user.id)
    )
    context.user_data.clear()
    clear_session(update.effective_user.id)
    return ConversationHandler.END

# ======================== MY ACCOUNT ========================
async def my_account(update, context):
    try:
        user = db.get_user(update.effective_user.id)
        if not user:
            await send_html(update, "❌ Please use /start first.")
            return
        if user.get('bank_name') and user.get('account_number') and user.get('account_name'):
            bank_details = (f"🏦 Bank: {esc(user['bank_name'])}\n"
                            f"🏷️ Code: <code>{esc(user.get('bank_code') or 'N/A')}</code>\n"
                            f"👤 Name: {esc(user['account_name'])}\n"
                            f"🔢 Account: {esc(user['account_number'])}\n"
                            f"{'✅ Status: Verified' if user.get('bank_verified') else '⚠️ Status: Unverified (name entered manually)'}")
        else:
            bank_details = "❌ Not set"
        try:
            joined = datetime.fromisoformat(user['created_at']).strftime('%Y-%m-%d')
        except Exception:
            joined = 'Unknown'
        stats = db.get_referrer_stats(user['user_id'])
        await send_html(
            update,
            f"<b>👤 My Account</b>\n\n"
            f"💰 Balance: {fmt(user['balance'])}\n"
            f"👥 Referrals: {user['total_referrals']} (Paid: {stats['paid']})\n"
            f"💸 Referral Earnings: {fmt(stats['earned'])}\n\n"
            f"<b>🏦 Bank Details:</b>\n{bank_details}\n\n"
            f"📅 Joined: {joined}\n\n"
            f"🆘 Support: {SUPPORT_BOT}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 My Tasks", callback_data="my_tasks")],
                [InlineKeyboardButton("📊 History", callback_data="history")],
            ])
        )
    except Exception as e:
        logger.error(f"my_account: {e}")

# ======================== WITHDRAWAL ========================
async def withdraw_menu(update, context):
    try:
        if not await gate(update, context):
            return ConversationHandler.END
        user = db.get_user(update.effective_user.id)
        if not user:
            await send_html(update, "❌ Please use /start first.")
            return ConversationHandler.END
        if not (user.get('bank_name') and user.get('account_number') and user.get('account_name')):
            await send_html(
                update,
                "❌ Please set your bank account first using <b>🏦 Set Bank</b>.\n\n"
                "You need:\n• Bank Name\n• Account Name\n• Account Number",
                reply_markup=get_main_keyboard(update.effective_user.id)
            )
            return ConversationHandler.END
        if user['balance'] < MIN_WITHDRAWAL:
            await send_html(
                update,
                f"❌ <b>Insufficient balance</b>\n\n"
                f"💰 Current: {fmt(user['balance'])}\n"
                f"💳 Minimum: {fmt(MIN_WITHDRAWAL)}\n\n"
                f"Complete more tasks!"
            )
            return ConversationHandler.END
        await send_html(
            update,
            f"<b>💰 Withdrawal Request</b>\n\n"
            f"💳 Balance: {fmt(user['balance'])}\n"
            f"📉 Minimum: {fmt(MIN_WITHDRAWAL)}\n"
            f"📈 Maximum: {fmt(MAX_WITHDRAWAL)}\n\n"
            f"🏦 Bank: {esc(user['bank_name'])}\n"
            f"🏷️ Code: <code>{esc(user.get('bank_code') or 'N/A')}</code>\n"
            f"👤 Account Name: {esc(user['account_name'])}\n"
            f"🔢 Account: {esc(user['account_number'])}\n\n"
            f"Enter the amount you want to withdraw:\n\n"
            f"<i>Tap 🔙 Cancel to abort</i>",
            reply_markup=cancel_kb()
        )
        return WITHDRAW_AMOUNT
    except Exception as e:
        logger.error(f"withdraw_menu: {e}")
        await send_html(update, "❌ An error occurred.")
        return ConversationHandler.END

async def process_withdrawal_amount(update, context):
    try:
        if is_cancel(update.message.text):
            await send_html(
                update,
                "❌ <b>Withdrawal cancelled.</b>",
                reply_markup=get_main_keyboard(update.effective_user.id)
            )
            context.user_data.clear()
            return ConversationHandler.END

        user_id = update.effective_user.id
        try:
            amount = float(update.message.text.strip().replace(',', ''))
        except ValueError:
            await send_html(
                update,
                "❌ Please enter a valid number, or tap 🔙 Cancel:",
                reply_markup=cancel_kb()
            )
            return WITHDRAW_AMOUNT

        if amount < MIN_WITHDRAWAL:
            await send_html(
                update,
                f"❌ Minimum withdrawal is {fmt(MIN_WITHDRAWAL)}. Try again or tap 🔙 Cancel:",
                reply_markup=cancel_kb()
            )
            return WITHDRAW_AMOUNT
        if amount > MAX_WITHDRAWAL:
            await send_html(
                update,
                f"❌ Maximum withdrawal is {fmt(MAX_WITHDRAWAL)}. Try again or tap 🔙 Cancel:",
                reply_markup=cancel_kb()
            )
            return WITHDRAW_AMOUNT

        user = db.get_user(user_id)
        if amount > user['balance']:
            await send_html(
                update,
                "❌ Insufficient balance. Try again or tap 🔙 Cancel:",
                reply_markup=cancel_kb()
            )
            return WITHDRAW_AMOUNT

        if not db.try_deduct_balance(user['user_id'], amount):
            await send_html(update, "❌ Insufficient balance. Try again or tap 🔙 Cancel:",
                            reply_markup=cancel_kb())
            return WITHDRAW_AMOUNT
        wid, ref_id = db.create_withdrawal(
            user['user_id'], amount, user['bank_name'], user.get('bank_code') or '',
            user['account_number'], user['account_name']
        )
        new_balance = (db.get_user(user['user_id']) or {}).get('balance', 0.0)

        await send_html(
            update,
            f"✅ <b>Withdrawal Request Submitted!</b>\n\n"
            f"💰 Amount: {fmt(amount)}\n"
            f"🏦 Bank: {esc(user['bank_name'])}\n"
            f"🏷️ Code: <code>{esc(user.get('bank_code') or 'N/A')}</code>\n"
            f"👤 Account Name: {esc(user['account_name'])}\n"
            f"🔢 Account: {esc(user['account_number'])}\n"
            f"💳 New Balance: {fmt(new_balance)}\n"
            f"📋 Ref ID: <code>{ref_id}</code>\n\n"
            f"📋 Status: Pending Admin Approval\n"
            f"⏰ Processing time: 24-48 hours\n\n"
            f"Thank you for using {BOT_NAME}! 🙏",
            reply_markup=get_main_keyboard(user_id)
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"💰 <b>New Withdrawal Request</b>\n\n"
                    f"👤 User: {esc(update.effective_user.first_name or 'User')}\n"
                    f"🆔 ID: {update.effective_user.id}\n"
                    f"💰 Amount: {fmt(amount)}\n"
                    f"📋 Ref: <code>{ref_id}</code>\n"
                    f"🏦 Bank: {esc(user['bank_name'])} (<code>{esc(user.get('bank_code') or 'N/A')}</code>)\n"
                    f"👤 Name: {esc(user['account_name'])}\n"
                    f"🔢 Account: {esc(user['account_number'])}",
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Notify admin {admin_id}: {e}")
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"process_withdrawal_amount: {e}")
        await send_html(update, "❌ An error occurred.")
        return ConversationHandler.END

async def cancel_withdrawal(update, context):
    await send_html(update, "❌ Withdrawal cancelled.", reply_markup=get_main_keyboard(update.effective_user.id))
    return ConversationHandler.END

# ======================== ADMIN — TASK CREATION ========================
async def add_task_start(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data.clear()
    await send_html(update, "⭐ <b>Add New Task</b>\n\nEnter the task <b>title</b>:\n\n<i>Tap 🔙 Cancel to abort</i>", reply_markup=cancel_kb())
    return TASK_TITLE

async def add_task_title(update, context):
    if is_cancel(update.message.text):
        await send_html(update, "❌ Task creation cancelled.", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    context.user_data['task_title'] = update.message.text.strip()
    await send_html(update, "Enter the task <b>description</b>:", reply_markup=cancel_kb())
    return TASK_DESC

async def add_task_desc(update, context):
    if is_cancel(update.message.text):
        await send_html(update, "❌ Task creation cancelled.", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    context.user_data['task_desc'] = update.message.text.strip()
    await send_html(update, "Enter the <b>reward amount</b> (in NGN):", reply_markup=cancel_kb())
    return TASK_REWARD

async def add_task_reward(update, context):
    if is_cancel(update.message.text):
        await send_html(update, "❌ Task creation cancelled.", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    try:
        reward = float(update.message.text.strip())
        if reward <= 0:
            await send_html(update, "❌ Reward must be > 0:", reply_markup=cancel_kb())
            return TASK_REWARD
        context.user_data['task_reward'] = reward
        kb = [['join_channel', 'visit_link'], ['watch_video', 'simple'], [CANCEL_TEXT]]
        await send_html(
            update,
            "Select <b>task type</b>:\n\n"
            "• join_channel — Join a Telegram channel\n"
            "• visit_link — Visit a website\n"
            "• watch_video — Watch a video\n"
            "• simple — Simple click",
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True, one_time_keyboard=True)
        )
        return TASK_TYPE
    except ValueError:
        await send_html(update, "❌ Please enter a valid number:", reply_markup=cancel_kb())
        return TASK_REWARD

async def add_task_type(update, context):
    if is_cancel(update.message.text):
        await send_html(update, "❌ Task creation cancelled.", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    ttype = update.message.text.strip().lower()
    valid = ['join_channel', 'visit_link', 'watch_video', 'simple']
    if ttype not in valid:
        await send_html(update, f"❌ Invalid type. Choose from: {', '.join(valid)}", reply_markup=cancel_kb())
        return TASK_TYPE
    context.user_data['task_type'] = ttype
    if ttype in ['join_channel', 'visit_link', 'watch_video']:
        await send_html(
            update,
            f"Enter the {'channel username (e.g. @channel)' if ttype == 'join_channel' else 'URL'}:",
            reply_markup=cancel_kb()
        )
        return TASK_REQUIREMENT
    await ask_task_image(update, context)
    return TASK_IMAGE

async def add_task_requirement(update, context):
    if is_cancel(update.message.text):
        await send_html(update, "❌ Task creation cancelled.", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    context.user_data['task_requirement'] = update.message.text.strip()
    await ask_task_image(update, context)
    return TASK_IMAGE

async def ask_task_image(update, context):
    await send_html(
        update,
        "🖼️ <b>Optional: Task Image</b>\n\n"
        "Send a photo, or:\n"
        "• /skip — continue without image\n"
        "• 🔙 Cancel — abort task creation",
        reply_markup=ReplyKeyboardMarkup([['/skip', CANCEL_TEXT]], resize_keyboard=True, one_time_keyboard=True)
    )

async def add_task_image(update, context):
    if is_cancel(update.message.text) or update.message.text == '/cancel':
        await send_html(update, "❌ Task creation cancelled.", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    if update.message.text == '/skip':
        image_id = None
    elif update.message.photo:
        image_id = update.message.photo[-1].file_id
    else:
        await send_html(update, "❌ Please send a photo, /skip, or tap 🔙 Cancel:",
                        reply_markup=ReplyKeyboardMarkup([['/skip', CANCEL_TEXT]], resize_keyboard=True))
        return TASK_IMAGE
    await finish_task_creation(update, context, image_id)
    return ConversationHandler.END

async def finish_task_creation(update, context, image_id=None):
    try:
        ttype = context.user_data.get('task_type', 'simple')
        req = context.user_data.get('task_requirement', 'N/A') if ttype != 'simple' else 'N/A'
        task_id = db.create_task(
            context.user_data['task_title'], context.user_data['task_desc'],
            context.user_data['task_reward'], ttype, req, image_id
        )
        title = context.user_data.get('task_title', 'Unknown')
        reward = context.user_data.get('task_reward', 0)
        context.user_data.clear()
        await send_html(
            update,
            f"✅ <b>Task Added Successfully!</b>\n\n"
            f"📋 ID: {task_id}\n"
            f"📝 Title: {esc(title)}\n"
            f"💰 Reward: {fmt(reward)}\n"
            f"📌 Type: {ttype}\n"
            f"🔗 Requirement: {esc(req)}\n"
            f"🖼️ Image: {'✅ Added' if image_id else '❌ Not added'}\n\n"
            f"Task is now active! 🎉",
            reply_markup=get_admin_keyboard()
        )
    except Exception as e:
        logger.error(f"finish_task_creation: {e}")
        await send_html(update, "❌ Error creating task.", reply_markup=get_admin_keyboard())

# ======================== ADMIN — VIEW / TOGGLE / DELETE ========================
async def view_all_tasks(update, context):
    if not is_admin(update.effective_user.id):
        return
    try:
        tasks = db.get_all_tasks()
        if not tasks:
            await send_html(update, "📋 No tasks found.", reply_markup=get_admin_keyboard())
            return
        text = "<b>📋 All Tasks</b>\n\n"
        for t in tasks:
            status = "✅ Active" if t.get('is_active', 1) else "❌ Inactive"
            completions = db.get_task_completion_count(t['task_id'])
            text += (f"<b>ID: {t['task_id']}</b>\n"
                     f"📝 {esc(t['title'])}\n"
                     f"💰 {fmt(t['reward'])} | {status}\n"
                     f"📌 Type: {t['type']}\n"
                     f"🖼️ Image: {'✅' if t.get('image_id') else '❌'}\n"
                     f"📊 Completions: {completions}\n"
                     f"{'─' * 20}\n")
        await send_html(update, text, reply_markup=get_admin_keyboard())
    except Exception as e:
        logger.error(f"view_all_tasks: {e}")

async def toggle_task_start(update, context):
    if not is_admin(update.effective_user.id):
        return
    tasks = db.get_all_tasks()
    if not tasks:
        await send_html(update, "No tasks found.", reply_markup=get_admin_keyboard())
        return
    sid = new_session(update.effective_user.id)
    kb = []
    for t in tasks:
        st = "✅" if t.get('is_active', 1) else "❌"
        kb.append([InlineKeyboardButton(
            f"{st} {t['title']} (ID: {t['task_id']})",
            callback_data=f"tg_{sid}_{t['task_id']}"
        )])
    await send_html(update, "Select a task to toggle:", reply_markup=InlineKeyboardMarkup(kb))

async def toggle_task_callback(update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized")
        return
    try:
        _, sid, tid = q.data.split("_", 2)
        task_id = int(tid)
    except Exception:
        await q.edit_message_text("❌ Invalid.")
        return
    if not is_valid_session(user_id, sid):
        await q.edit_message_text("⚠️ Session expired. Please tap ✏️ Toggle Task again.")
        return
    task = db.get_task(task_id)
    if not task:
        await q.edit_message_text("❌ Task not found")
        return
    new_status = not task.get('is_active', 1)
    db.update_task_status(task_id, new_status)
    await q.edit_message_text(
        f"✅ Task <b>{esc(task['title'])}</b> is now "
        f"{'Active' if new_status else 'Inactive'}",
        parse_mode='HTML', reply_markup=get_admin_keyboard()
    )

async def delete_task_start(update, context):
    if not is_admin(update.effective_user.id):
        return
    tasks = db.get_all_tasks()
    if not tasks:
        await send_html(update, "No tasks found.", reply_markup=get_admin_keyboard())
        return
    sid = new_session(update.effective_user.id)
    kb = []
    for t in tasks:
        kb.append([InlineKeyboardButton(
            f"❌ {t['title']} (ID: {t['task_id']})",
            callback_data=f"dl_{sid}_{t['task_id']}"
        )])
    await send_html(update, "Select a task to delete:", reply_markup=InlineKeyboardMarkup(kb))

async def delete_task_callback(update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized")
        return
    try:
        _, sid, tid = q.data.split("_", 2)
        task_id = int(tid)
    except Exception:
        await q.edit_message_text("❌ Invalid.")
        return
    if not is_valid_session(user_id, sid):
        await q.edit_message_text("⚠️ Session expired. Please tap 🗑 Delete Task again.")
        return
    task = db.get_task(task_id)
    if not task:
        await q.edit_message_text("❌ Task not found")
        return
    db.delete_task(task_id)
    await q.edit_message_text(
        f"✅ Task <b>{esc(task['title'])}</b> deleted!",
        parse_mode='HTML', reply_markup=get_admin_keyboard()
    )

# ======================== ADMIN — STATS & WITHDRAWALS ========================
async def admin_statistics(update, context):
    if not is_admin(update.effective_user.id):
        return
    await send_html(
        update,
        f"<b>📊 {BOT_NAME} Statistics</b>\n\n"
        f"👥 Total Users: {db.get_total_users()}\n"
        f"📝 Total Tasks: {len(db.get_all_tasks())}\n"
        f"✅ Completions: {db.get_total_completions()}\n\n"
        f"💰 Withdrawals:\n"
        f"• Paid: {fmt(db.get_total_withdrawn())}\n"
        f"• Pending: {len(db.get_pending_withdrawals())}",
        reply_markup=get_admin_keyboard()
    )

async def manage_withdrawals(update, context):
    if not is_admin(update.effective_user.id):
        return
    pending = db.get_pending_withdrawals()
    if not pending:
        await send_html(update, "✅ No pending withdrawals.", reply_markup=get_admin_keyboard())
        return
    sid = new_session(update.effective_user.id)
    text = "<b>💰 Pending Withdrawals</b>\n\n"
    kb = []
    for w in pending[:10]:
        u = db.get_user(w['user_id'])
        name = u.get('first_name', 'Unknown') if u else 'Unknown'
        text += (f"• {esc(name)} (ID: {w['user_id']}): {fmt(w['amount'])}\n"
                 f"  Ref: <code>{esc(w['ref_id'])}</code>\n"
                 f"  Bank: {esc(w['bank_name'])} (<code>{esc(w.get('bank_code') or 'N/A')}</code>)\n"
                 f"  Account: {esc(w['account_number'])}\n"
                 f"  Name: {esc(w['account_name'])}\n\n")
        kb.append([
            InlineKeyboardButton(f"✅ Approve #{w['id']}", callback_data=f"ap_{sid}_{w['id']}"),
            InlineKeyboardButton(f"❌ Reject #{w['id']}", callback_data=f"rj_{sid}_{w['id']}")
        ])
    await send_html(update, text, reply_markup=InlineKeyboardMarkup(kb))

async def approve_withdrawal(update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized")
        return
    try:
        _, sid, wid_str = q.data.split("_", 2)
        wid = int(wid_str)
    except Exception:
        await q.edit_message_text("❌ Invalid.")
        return
    if not is_valid_session(user_id, sid):
        await q.edit_message_text("⚠️ Session expired. Please tap 💰 Manage Withdrawals again.")
        return
    w = db.get_withdrawal(wid)
    if not w:
        await q.edit_message_text("❌ Withdrawal not found")
        return
    if not db.approve_withdrawal(wid, user_id):
        await q.edit_message_text(f"⚠️ Withdrawal #{wid} was already processed.")
        return
    try:
        u = db.get_user(w['user_id'])
        if u:
            full_name = u.get('full_name') or u.get('first_name') or u.get('username', 'Unknown')
            try:
                await context.bot.send_message(
                    chat_id=PAYOUT_CHANNEL,
                    text=(f"<b>⭐ WITHDRAWAL SUCCESSFUL ⭐</b>\n\n"
                          f"👤 <b>User:</b> {esc(full_name)}\n"
                          f"💰 <b>Amount:</b> {fmt(w['amount'])}\n"
                          f"🕐 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                          f"📋 <b>Ref:</b> <code>{esc(w['ref_id'])}</code>\n\n"
                          f"🏦 <b>Bank:</b>\n"
                          f"• {esc(w['bank_name'])}\n"
                          f"• Code: <code>{esc(w.get('bank_code') or 'N/A')}</code>\n"
                          f"• {esc(w['account_number'])}\n"
                          f"• {esc(w['account_name'])}\n\n"
                          f"✅ <b>Status:</b> Approved\n\n"
                          f"━━━━━━━━━━━━━━━━━━━\n"
                          f"⭐ {BOT_NAME}"),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Payout channel send: {e}")
            try:
                await context.bot.send_message(
                    chat_id=w['user_id'],
                    text=(f"✅ <b>Withdrawal Approved!</b>\n\n"
                          f"💰 Amount: {fmt(w['amount'])}\n"
                          f"📋 Ref: <code>{esc(w['ref_id'])}</code>\n"
                          f"🏦 Bank: {esc(w['bank_name'])}\n"
                          f"🏷️ Code: <code>{esc(w.get('bank_code') or 'N/A')}</code>\n"
                          f"👤 Name: {esc(w['account_name'])}\n"
                          f"🔢 Account: {esc(w['account_number'])}\n\n"
                          f"Your withdrawal has been processed! 🎉"),
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"User approve notify: {e}")
    except Exception as e:
        logger.error(f"approve flow: {e}")
    await q.edit_message_text(
        f"✅ Withdrawal #{wid} approved\n💰 {fmt(w['amount'])}\n📋 Ref: <code>{esc(w['ref_id'])}</code>",
        parse_mode='HTML', reply_markup=get_admin_keyboard()
    )

async def reject_withdrawal(update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized")
        return
    try:
        _, sid, wid_str = q.data.split("_", 2)
        wid = int(wid_str)
    except Exception:
        await q.edit_message_text("❌ Invalid.")
        return
    if not is_valid_session(user_id, sid):
        await q.edit_message_text("⚠️ Session expired. Please tap 💰 Manage Withdrawals again.")
        return
    w = db.get_withdrawal(wid)
    if not w:
        await q.edit_message_text("❌ Withdrawal not found")
        return
    if not db.reject_withdrawal(wid, user_id):
        await q.edit_message_text(f"⚠️ Withdrawal #{wid} was already processed.")
        return
    db.update_user_balance(w['user_id'], w['amount'])
    try:
        await context.bot.send_message(
            chat_id=w['user_id'],
            text=(f"❌ <b>Withdrawal Rejected</b>\n\n"
                  f"💰 Amount: {fmt(w['amount'])}\n"
                  f"📋 Ref: <code>{esc(w['ref_id'])}</code>\n"
                  f"🏦 Bank: {esc(w['bank_name'])}\n"
                  f"👤 Name: {esc(w['account_name'])}\n"
                  f"🔢 Account: {esc(w['account_number'])}\n\n"
                  f"Amount refunded to your balance.\n"
                  f"Contact: {SUPPORT_BOT}"),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"User reject notify: {e}")
    await q.edit_message_text(
        f"❌ Withdrawal #{wid} rejected\n💰 Refunded: {fmt(w['amount'])}",
        parse_mode='HTML', reply_markup=get_admin_keyboard()
    )

# ======================== ADMIN — BROADCAST ========================
async def broadcast_start(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data.clear()
    await send_html(update, "📢 <b>Broadcast</b>\n\nSend a photo, /skip, or 🔙 Cancel:", reply_markup=ReplyKeyboardMarkup([['/skip', CANCEL_TEXT]], resize_keyboard=True))
    return BROADCAST_IMAGE

async def broadcast_image(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    if is_cancel(update.message.text):
        await send_html(update, "❌ Broadcast cancelled.", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    if update.message.photo:
        context.user_data['broadcast_image'] = update.message.photo[-1].file_id
    elif update.message.text == '/skip':
        context.user_data['broadcast_image'] = None
    else:
        await send_html(update, "Please send a photo, /skip, or tap 🔙 Cancel:",
                        reply_markup=ReplyKeyboardMarkup([['/skip', CANCEL_TEXT]], resize_keyboard=True))
        return BROADCAST_IMAGE
    await send_html(update, "Send the <b>caption</b>, or tap 🔙 Cancel:", reply_markup=cancel_kb())
    return BROADCAST_CAPTION

async def broadcast_caption(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    if is_cancel(update.message.text):
        await send_html(update, "❌ Broadcast cancelled.", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    context.user_data['broadcast_caption'] = update.message.text
    await send_html(
        update,
        "Send inline buttons <code>Text:URL</code> (one per line), /skip, or 🔙 Cancel:",
        reply_markup=ReplyKeyboardMarkup([['/skip', CANCEL_TEXT]], resize_keyboard=True)
    )
    return BROADCAST_BUTTONS

async def broadcast_buttons(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    if is_cancel(update.message.text):
        await send_html(update, "❌ Broadcast cancelled.", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    if update.message.text == '/skip':
        context.user_data['broadcast_buttons'] = []
    else:
        buttons = []
        for line in update.message.text.split('\n'):
            if ':' in line:
                t, url = line.split(':', 1)
                buttons.append([t.strip(), url.strip()])
        context.user_data['broadcast_buttons'] = buttons

    caption = context.user_data.get('broadcast_caption', 'No caption')
    image = context.user_data.get('broadcast_image')
    kb_btns = [[InlineKeyboardButton(b[0], url=b[1])]
               for b in context.user_data.get('broadcast_buttons', [])]
    preview = f"📢 <b>Broadcast Preview</b>\n\n{caption}"
    if image:
        await send_html_photo(update, photo=image, caption=preview,
                              reply_markup=InlineKeyboardMarkup(kb_btns) if kb_btns else None)
    else:
        await send_html(update, preview,
                        reply_markup=InlineKeyboardMarkup(kb_btns) if kb_btns else None)

    sid = new_session(update.effective_user.id)
    await send_html(
        update, "Send this broadcast to all users?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Send", callback_data=f"bc_{sid}_send")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"bc_{sid}_cancel")],
        ])
    )
    return BROADCAST_CONFIRM

async def broadcast_confirm(update, context):
    q = update.callback_query
    await q.answer()
    user_id = q.from_user.id
    if not is_admin(user_id):
        await q.edit_message_text("❌ Unauthorized")
        return ConversationHandler.END
    try:
        _, sid, action = q.data.split("_", 2)
    except Exception:
        await q.edit_message_text("❌ Invalid.")
        return ConversationHandler.END
    if not is_valid_session(user_id, sid):
        await q.edit_message_text("⚠️ Session expired. Please tap 📢 Broadcast again.")
        return ConversationHandler.END

    if action == "cancel":
        await q.edit_message_text("❌ Broadcast cancelled.")
        await q.message.reply_text("🔙 Back to Admin Panel", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END

    users = db.get_all_users()
    total = len(users)
    sent = 0
    failed = 0
    image = context.user_data.get('broadcast_image')
    caption = context.user_data.get('broadcast_caption', '')
    buttons = context.user_data.get('broadcast_buttons', [])
    kb_btns = [[InlineKeyboardButton(b[0], url=b[1])] for b in buttons]

    await q.edit_message_text(
        f"📢 <b>Sending...</b>\n\nTotal: {total}\nProgress: 0/{total}",
        parse_mode='HTML'
    )
    for i, u in enumerate(users):
        try:
            if image:
                await context.bot.send_photo(
                    chat_id=u['user_id'], photo=image, caption=caption,
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(kb_btns) if kb_btns else None
                )
            else:
                await context.bot.send_message(
                    chat_id=u['user_id'], text=caption, parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(kb_btns) if kb_btns else None
                )
            sent += 1
        except Exception as e:
            failed += 1
            logger.warning(f"Broadcast {u['user_id']} failed: {e}")
        await asyncio.sleep(0.05)
        if (i + 1) % 10 == 0:
            try:
                await q.edit_message_text(
                    f"📢 <b>Sending...</b>\n\nTotal: {total}\nProgress: {i+1}/{total}\n✅ {sent}\n❌ {failed}",
                    parse_mode='HTML'
                )
            except Exception:
                pass

    db.save_broadcast(user_id, image or '', caption, str(buttons), sent, failed)
    await q.edit_message_text(
        f"✅ <b>Broadcast Complete!</b>\n\n"
        f"Total: {total}\n✅ Sent: {sent}\n❌ Failed: {failed}\n\n"
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode='HTML'
    )
    await q.message.reply_text("🔙 Back to Admin Panel", reply_markup=get_admin_keyboard())
    context.user_data.clear()
    clear_session(user_id)
    return ConversationHandler.END

# ======================== ADMIN — SEND COINS ========================
async def send_coins_start(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data.clear()
    await send_html(update, "🎁 <b>Send Coins</b>\n\nEnter the user ID, or tap 🔙 Cancel:",
                    reply_markup=cancel_kb())
    return SEND_COINS_USER_ID

async def send_coins_user_id(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    if is_cancel(update.message.text):
        await send_html(update, "❌ Send coins cancelled.", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    try:
        uid = int(update.message.text.strip())
        u = db.get_user(uid)
        if not u:
            await send_html(update, "❌ User not found. Enter another ID or tap 🔙 Cancel:",
                            reply_markup=cancel_kb())
            return SEND_COINS_USER_ID
        context.user_data['sc_uid'] = uid
        context.user_data['sc_user'] = u
        await send_html(
            update,
            f"👤 {esc(u.get('first_name', 'Unknown'))}\n"
            f"💰 Balance: {fmt(u['balance'])}\n\nEnter amount or tap 🔙 Cancel:",
            reply_markup=cancel_kb()
        )
        return SEND_COINS_AMOUNT
    except ValueError:
        await send_html(update, "❌ Invalid user ID. Try again or tap 🔙 Cancel:",
                        reply_markup=cancel_kb())
        return SEND_COINS_USER_ID

async def send_coins_amount(update, context):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    if is_cancel(update.message.text):
        await send_html(update, "❌ Send coins cancelled.", reply_markup=get_admin_keyboard())
        context.user_data.clear()
        return ConversationHandler.END
    try:
        amount = float(update.message.text.strip())
        uid = context.user_data.get('sc_uid')
        u = context.user_data.get('sc_user')
        if not uid or not u:
            await send_html(update, "❌ Session lost. Please tap 🎁 Send Coins again.",
                            reply_markup=get_admin_keyboard())
            context.user_data.clear()
            return ConversationHandler.END
        if amount <= 0:
            await send_html(update, "❌ Amount must be > 0:", reply_markup=cancel_kb())
            return SEND_COINS_AMOUNT
        new_bal = db.update_user_balance(uid, amount)
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(f"🎁 <b>Coins Received!</b>\n\n"
                      f"💰 Amount: {fmt(amount)}\n"
                      f"💳 New Balance: {fmt(new_bal)}\n\n"
                      f"Thank you for using {BOT_NAME}! 🎉"),
                parse_mode='HTML'
            )
        except Exception as e:
            logger.warning(f"Coins notify: {e}")
        await send_html(
            update,
            f"✅ <b>Coins Sent!</b>\n\n"
            f"👤 {esc(u.get('first_name', 'Unknown'))}\n"
            f"🆔 {uid}\n"
            f"💰 {fmt(amount)}\n"
            f"💳 New Balance: {fmt(new_bal)}",
            reply_markup=get_admin_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await send_html(update, "❌ Invalid amount. Try again or tap 🔙 Cancel:",
                        reply_markup=cancel_kb())
        return SEND_COINS_AMOUNT

# ======================== CALLBACK ROUTER ========================
async def callback_handler(update, context):
    q = update.callback_query
    await q.answer()
    data = q.data
    logger.info(f"Callback '{data}' from {q.from_user.id}")

    if data.startswith("cp_"):
        await captcha_answer_callback(update, context); return
    if data.startswith("join_"):
        await show_force_join_callback(update, context); return
    if data.startswith("t_"):
        await task_callback(update, context); return
    if data.startswith("vj_"):
        await verify_join_callback(update, context); return
    if data.startswith("vv_"):
        await verify_visit_callback(update, context); return
    if data.startswith("tg_"):
        await toggle_task_callback(update, context); return
    if data.startswith("dl_"):
        await delete_task_callback(update, context); return
    if data.startswith("ap_"):
        await approve_withdrawal(update, context); return
    if data.startswith("rj_"):
        await reject_withdrawal(update, context); return
    if data.startswith("bc_"):
        await broadcast_confirm(update, context); return

    # Static callbacks
    if data == "copy_referral_link":
        u = db.get_user(q.from_user.id)
        if not u:
            await q.edit_message_text("❌ Please use /start first.")
            return
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start={u['referral_code']}"
        await q.edit_message_text(
            f"✅ <b>Referral Link:</b>\n<code>{link}</code>\n\n"
            f"Share to earn {fmt(REFERRAL_REWARD)} per successful referral!",
            parse_mode='HTML'
        )
        return
    if data == "view_referrals":
        uid = q.from_user.id
        stats = db.get_referrer_stats(uid)
        recent = db.get_referrer_list(uid, limit=20)
        text = (f"<b>👥 Your Referrals</b>\n\n"
                f"📊 Total: {stats['total']}\n"
                f"✅ Paid: {stats['paid']}\n"
                f"⏳ Pending: {stats['pending']}\n"
                f"💸 Earned: {fmt(stats['earned'])}\n\n")
        if recent:
            text += "<b>Recent:</b>\n"
            for r in recent:
                icon = "✅" if r['status'] == 'paid' else "⏳"
                name = r.get('first_name') or r.get('username') or 'User'
                text += f"{icon} {esc(name)}\n"
        else:
            text += "No referrals yet."
        await q.edit_message_text(text, parse_mode='HTML')
        return
    if data == "my_tasks":
        completions = db.get_user_completed_tasks(q.from_user.id)
        if not completions:
            await q.edit_message_text("📝 You haven't completed any tasks yet.")
            return
        text = "<b>📝 Completed Tasks</b>\n\n"
        for c in completions:
            t = db.get_task(c['task_id'])
            if t:
                text += f"• {esc(t['title'])} — {fmt(c['reward_earned'])}\n"
        await q.edit_message_text(text, parse_mode='HTML')
        return
    if data == "history":
        await q.edit_message_text("📊 <b>History</b>\n\nComing soon! 🔄", parse_mode='HTML')
        return

BANK_NAME_HINTS = {  # our name -> text to look for in nuAlt's bank name
    'uba': 'united bank for africa', 'gtbank': 'guaranty trust', 'first bank': 'first bank of nigeria',
    'fcmb': 'first city monument', 'stanbic ibtc': 'stanbic', 'union bank': 'union bank',
    'kuda bank': 'kuda', 'titan trust bank': 'titan', 'taj bank': 'taj', 'globus bank': 'globus',
    'vfd micro finance bank': 'vfd', 'opay': 'opay', 'palmpay': 'palmpay', 'moniepoint': 'moniepoint',
}
BANK_OVERRIDES_FILE = os.getenv('BANK_OVERRIDES_FILE', 'bank_code_overrides.json')

def sync_bank_codes_with_nualt():
    """Fix any bank whose code nuAlt doesn't recognise, by matching names against nuAlt's /banks.
    Returns (changes, unresolved, reason)."""
    nu_banks, reason = nualt_list_banks()
    if not nu_banks:
        return [], [], reason
    nu_codes = {str(b.get('code')) for b in nu_banks}
    changes, unresolved = [], []
    for b in db.get_banks():
        if b['bank_code'] in nu_codes:
            continue
        key = BANK_NAME_HINTS.get(b['bank_name'].lower(), b['bank_name'].lower())
        cands = [x for x in nu_banks if key in str(x.get('bank_name', '')).lower()]
        exact = [x for x in cands if str(x.get('bank_name', '')).lower() == key]
        pick = exact[0] if len(exact) == 1 else (cands[0] if len(cands) == 1 else None)
        if pick:
            db.update_bank_code(b['bank_code'], str(pick['code']))
            changes.append((b['bank_name'], b['bank_code'], str(pick['code'])))
        else:
            unresolved.append((b['bank_name'], b['bank_code'],
                               [f"{x.get('bank_name')} = {x.get('code')}" for x in cands[:4]]))
    if changes:
        try:
            with open(BANK_OVERRIDES_FILE, 'w', encoding='utf-8') as f:
                json.dump({n: new for n, _, new in changes}, f)
        except OSError:
            pass
    return changes, unresolved, "ok"

def apply_bank_overrides():
    if not os.path.exists(BANK_OVERRIDES_FILE):
        return
    try:
        with open(BANK_OVERRIDES_FILE, encoding='utf-8') as f:
            ov = json.load(f)
        for b in db.get_banks():
            if b['bank_name'] in ov and b['bank_code'] != ov[b['bank_name']]:
                db.update_bank_code(b['bank_code'], ov[b['bank_name']])
    except Exception as e:
        logger.warning(f"Could not apply bank overrides: {e}")

async def syncbanks_command(update, context):
    if not is_admin(update.effective_user.id):
        return
    await send_html(update, "⏳ Syncing bank codes with nuAlt...")
    changes, unresolved, reason = await asyncio.to_thread(sync_bank_codes_with_nualt)
    if reason != "ok":
        await send_html(update, f"❌ Could not fetch nuAlt bank list: {esc(reason)}")
        return
    out = []
    for n, old, new in changes:
        out.append(f"✅ <b>{esc(n)}</b>: {esc(old)} → <code>{esc(new)}</code>")
    for n, old, c in unresolved:
        out.append(f"⚠️ <b>{esc(n)}</b> ({esc(old)}): " + esc('; '.join(c) or 'no match in nuAlt'))
    await send_html(update, "\n".join(out) if out else "✅ All bank codes already match nuAlt.")

async def checkbanks_command(update, context):
    if not is_admin(update.effective_user.id):
        return
    await send_html(update, "⏳ Checking bank codes against nuAlt...")
    nu_banks, reason = await asyncio.to_thread(nualt_list_banks)
    if not nu_banks:
        await send_html(update, f"❌ Could not fetch nuAlt bank list: {esc(reason)}")
        return
    nu_codes = {str(b.get('code')) for b in nu_banks}
    lines = []
    for b in db.get_banks():
        if b['bank_code'] in nu_codes:
            continue
        key = b['bank_name'].split()[0].lower()
        cands = [f"{x.get('bank_name')} = {x.get('code')}" for x in nu_banks
                 if key in str(x.get('bank_name', '')).lower()][:4]
        lines.append(f"❌ <b>{esc(b['bank_name'])}</b> ({esc(b['bank_code'])}) → "
                     f"{esc('; '.join(cands) or 'no match')}")
    if lines:
        await send_html(update, "<b>Codes nuAlt does not recognise:</b>\n\n" + "\n".join(lines))
    else:
        await send_html(update, f"✅ All {len(db.get_banks())} bank codes exist in nuAlt.")

async def mailtm_command(update, context):
    if not is_admin(update.effective_user.id):
        return
    try:
        address, _ = await asyncio.to_thread(mailtm_get_account)
        await send_html(update, f"📧 <b>Fallback mailbox (mail.tm)</b>\n\n<code>{esc(address)}</code>\n\n"
                                "Used for the nuAlt dashboard login. Created once and reused.")
    except Exception as e:
        await send_html(update, f"❌ mail.tm error: {esc(str(e)[:150])}")

async def newkey_command(update, context):
    if not is_admin(update.effective_user.id):
        return
    await send_html(update, "⏳ Creating a new nuAlt API key via the dashboard...")
    global _LAST_KEY_CREATE
    _LAST_KEY_CREATE = 0.0  # admin request bypasses the cooldown
    ok = await nualt_ensure_new_key()
    if ok:
        await send_html(update, f"✅ New key saved to <code>{esc(NUALT_KEY_FILE)}</code> "
                                f"(ends …{esc(NUALT_API_KEY[-6:])}) and is now in use.")
    else:
        await send_html(update, "❌ Could not create a key. Check the bot log.")

# ======================== POST-INIT ========================
async def post_init(application):
    # Delete webhook to ensure clean polling and stop duplicate updates
    await application.bot.delete_webhook(drop_pending_updates=True)

    # Make bank codes match nuAlt's list (saved overrides first, then a live sync)
    apply_bank_overrides()
    try:
        changes, unresolved, reason = await asyncio.to_thread(sync_bank_codes_with_nualt)
        for n, old, new in changes:
            logger.info(f"Bank code synced with nuAlt: {n} {old} -> {new}")
        for n, old, c in unresolved:
            logger.warning(f"Bank '{n}' ({old}) not found in nuAlt: {c}")
        if reason != "ok":
            logger.warning(f"Bank sync skipped: {reason}")
    except Exception as e:
        logger.warning(f"Bank sync error: {e}")
    
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help"),
        BotCommand("balance", "Check your balance"),
        BotCommand("referral", "Refer & Earn — get your link"),
    ])

# ======================== MAIN ========================
_conflict_logged = False

async def on_error(update, context):
    global _conflict_logged
    err = context.error
    if err.__class__.__name__ == 'Conflict':
        if not _conflict_logged:
            _conflict_logged = True
            logger.error("Telegram Conflict: ANOTHER instance of this bot (same BOT_TOKEN) is running "
                         "somewhere else. Stop the other copy (old host, local PC, duplicate deploy) "
                         "- only one may poll at a time.")
        return
    if err.__class__.__name__ in ('NetworkError', 'TimedOut'):
        logger.warning(f"Network hiccup: {err}")
        return
    logger.error("Unhandled error", exc_info=err)

def main():
    if not BOT_TOKEN or BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("❌ ERROR: Please set BOT_TOKEN in .env")
        return

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    application.add_error_handler(on_error)

    # Commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("referral", referral_command))
    application.add_handler(CommandHandler("checkbanks", checkbanks_command))
    application.add_handler(CommandHandler("syncbanks", syncbanks_command))
    application.add_handler(CommandHandler("mailtm", mailtm_command))
    application.add_handler(CommandHandler("newkey", newkey_command))

    # Bank setup
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🏦 Set Bank$'), set_bank_start)],
        states={
            BANK_SELECT: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), cancel_bank_setup),
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_bank_name),
            ],
            BANK_ACCOUNT_NUMBER: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), cancel_bank_setup),
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_account_number),
            ],
            BANK_ACCOUNT_NAME: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), cancel_bank_setup),
                MessageHandler(filters.TEXT & ~filters.COMMAND, set_account_name),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), cancel_bank_setup)],
        allow_reentry=True,
    ))

    # Withdrawal
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^💰 Withdraw$'), withdraw_menu)],
        states={
            WITHDRAW_AMOUNT: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), cancel_withdrawal),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdrawal_amount),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), cancel_withdrawal)],
        allow_reentry=True,
    ))

    # Task creation
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^➕ Add Task$'), add_task_start)],
        states={
            TASK_TITLE: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_title),
            ],
            TASK_DESC: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_desc),
            ],
            TASK_REWARD: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_reward),
            ],
            TASK_TYPE: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_type),
            ],
            TASK_REQUIREMENT: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_requirement),
            ],
            TASK_IMAGE: [
                MessageHandler(filters.PHOTO, add_task_image),
                MessageHandler(filters.Regex('^/skip$'), add_task_image),
                MessageHandler(filters.Regex('^/cancel$'), add_task_image),
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_image),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel)]
    ))

    # Broadcast
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^📢 Broadcast$'), broadcast_start)],
        states={
            BROADCAST_IMAGE: [
                MessageHandler(filters.PHOTO, broadcast_image),
                MessageHandler(filters.Regex('^/skip$'), broadcast_image),
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_image),
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
            ],
            BROADCAST_CAPTION: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_caption),
            ],
            BROADCAST_BUTTONS: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_buttons),
            ],
            BROADCAST_CONFIRM: [CallbackQueryHandler(broadcast_confirm, pattern='^bc_')],
        },
        fallbacks=[MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel)]
    ))

    # Send coins
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^🎁 Send Coins$'), send_coins_start)],
        states={
            SEND_COINS_USER_ID: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_coins_user_id),
            ],
            SEND_COINS_AMOUNT: [
                MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND, send_coins_amount),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(f'^{CANCEL_TEXT}$'), finish_cancel)]
    ))

    # Callbacks
    application.add_handler(CallbackQueryHandler(callback_handler))

    # Menu (fallback) - Group 1 ensures it runs AFTER conversations (Group 0)
    # This prevents double-answering when inside a ConversationHandler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu), group=1)

    logger.info(f"⭐ {BOT_NAME} started")
    logger.info(f"Admins: {ADMIN_IDS}")
    logger.info(f"Forced channels: {len(FORCED_CHANNELS)}")
    logger.info(f"Payout channel: {PAYOUT_CHANNEL}")
    logger.info(f"Referral reward: {fmt(REFERRAL_REWARD)}")
    logger.info(f"CAPTCHA challenges: {len(CAPTCHA_CHALLENGES)}")
    logger.info(f"Mansa configured: {bool(MANSA_API_KEY)}")
    logger.info(f"NU-ALT configured: {bool(NUALT_API_KEY)}")
    if not NUALT_API_KEY:
        logger.warning("NUALT_API_KEY is empty - account names can NOT be auto-fetched. Add it to .env")
    logger.info(f"Browser fallback: session code={bool(NUALT_SESSION)}, mail.tm auto-login=on")
    if not MANSA_API_KEY:
        logger.warning("MANSA_API_KEY is empty - NUBAN format check will be skipped. Add it to .env")

    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

async def finish_cancel(update, context):
    await send_html(update, "❌ Action cancelled.", reply_markup=get_admin_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

if __name__ == '__main__':
    main()