"""
kite_executor.py -- Zerodha OptionSelling Engine | Kite Connect API Wrapper
=========================================================================
mimics the exact signature of hdfc_executor.py for drop-in compatibility.

Responsibilities:
  - Daily login via automated headless credentials login OR Streamlit redirect flow
  - Place / Cancel / Modify orders via Zerodha Kite Connect API
  - Fetch order status + trade book + positions
  - Search option contract symbols using daily instruments CSV dump
"""

import sys
import os
import time
import requests
import pyotp
import pandas as pd
from typing import Optional
from datetime import datetime
import pytz
from kiteconnect import KiteConnect, exceptions
from html.parser import HTMLParser

class ZerodhaConsentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.form_action = None
        self.inputs = {}
        self.in_form = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "form":
            self.in_form = True
            self.form_action = attrs_dict.get("action")
        elif tag == "input" and self.in_form:
            name = attrs_dict.get("name")
            value = attrs_dict.get("value", "")
            if name:
                self.inputs[name] = value

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_form = False


def _extract_request_token(response) -> str:
    """
    Scan all redirect history + final response for a request_token in
    the URL or Location header.  Returns the token string, or "".
    """
    for resp in (response.history or []) + [response]:
        for candidate in (resp.headers.get("Location", ""), resp.url):
            if "request_token=" in candidate:
                return candidate.split("request_token=")[1].split("&")[0].split("#")[0].strip()
    return ""


def _follow_to_request_token(sess, start_url: str) -> str:
    """
    Manually follows redirect chain from start_url hop-by-hop (allow_redirects=False).
    When Zerodha redirects to the app's redirect_url (e.g. http://46.224.133.16:9007/...),
    we read the request_token directly from the Location header WITHOUT connecting
    to the redirect host — which avoids 'connection refused' errors.

    Intercepts redirects to: 127.0.0.1, localhost, and the configured VPS IP.
    If we land on a consent page (/connect/authorize), we submit it and continue.
    Returns the request_token string, or "" on failure.
    """
    from urllib.parse import urlparse

    # Build a set of IPs/hosts that are OUR redirect targets — don't connect to these
    try:
        import db as _db
        vps_ip = _db.get("VPS_IP", "5.75.250.104").strip()
    except Exception:
        vps_ip = "5.75.250.104"
    intercept_hosts = {"127.0.0.1", "localhost", vps_ip}

    current_url = start_url
    max_hops = 12

    for hop in range(max_hops):
        # ── If current URL already has the token, extract immediately ─────
        if "request_token=" in current_url:
            token = current_url.split("request_token=")[1].split("&")[0].split("#")[0].strip()
            print(f"[EXECUTOR] Token found in URL at hop {hop}: {token[:8]}...")
            return token

        # ── If we're about to hit an intercept host, stop before connecting ─
        parsed_cur = urlparse(current_url)
        if parsed_cur.hostname in intercept_hosts:
            if "request_token=" in current_url:
                token = current_url.split("request_token=")[1].split("&")[0].split("#")[0].strip()
                print(f"[EXECUTOR] Token extracted from redirect URL ({parsed_cur.hostname}): {token[:8]}...")
                return token
            print(f"[EXECUTOR] Reached redirect host ({parsed_cur.hostname}) without token: {current_url}")
            return ""

        try:
            resp = sess.get(current_url, allow_redirects=False, timeout=15)
        except Exception as e:
            print(f"[EXECUTOR] Hop {hop} GET error for {current_url[:60]}: {e}")
            return ""

        status   = resp.status_code
        location = resp.headers.get("Location", "")
        print(f"[EXECUTOR] Hop {hop}: status={status} url={current_url[:70]} -> location={location[:80]}")

        # ── Token in Location header? Extract immediately — no need to follow ─
        if "request_token=" in location:
            token = location.split("request_token=")[1].split("&")[0].split("#")[0].strip()
            print(f"[EXECUTOR] Token extracted from Location header: {token[:8]}...")
            return token

        # ── Redirect to one of our intercept hosts — stop, don't connect ──
        if location:
            loc_host = urlparse(location).hostname or ""
            if loc_host in intercept_hosts:
                # Token should have been in Location above; if not, it's an error
                print(f"[EXECUTOR] Redirect to intercept host {loc_host} but no token in Location: {location}")
                return ""

        # ── Normal redirect — follow it ────────────────────────────────────
        if status in (301, 302, 303, 307, 308) and location:
            if location.startswith("/"):
                parsed = urlparse(current_url)
                current_url = f"{parsed.scheme}://{parsed.netloc}{location}"
            else:
                current_url = location
            continue

        # ── Possibly a consent page (JS-rendered or HTML form) ─────────────
        if "connect/authorize" in resp.url or "connect/authorize" in current_url:
            token = _submit_consent_form(sess, resp)
            if token:
                return token
            return ""

        # ── Non-redirect, non-consent: scan body/history as last resort ────
        token = _extract_request_token(resp)
        if token:
            return token

        print(f"[EXECUTOR] Hop {hop}: No redirect and no token. Stopping.")
        break

    print(f"[EXECUTOR] _follow_to_request_token: exhausted {max_hops} hops without finding token.")
    return ""


def _submit_consent_form(sess, consent_response) -> str:
    """
    Parse and submit the Zerodha /connect/authorize consent form.

    KEY FIX: Zerodha's consent POST replies with  302 → your redirect_url
    (e.g. http://127.0.0.1/?request_token=xxx).  With allow_redirects=True
    requests tries to *connect* to 127.0.0.1 which either times-out or
    returns garbage — we never see the token.

    Solution: POST with allow_redirects=False and read the Location header
    of the 302 directly.  Only if that fails do we try following redirects.
    """
    print("[EXECUTOR] Consent page detected. Submitting authorization form...")

    parser = ZerodhaConsentParser()
    parser.feed(consent_response.text)

    # Debug: log what the parser found
    print(f"[EXECUTOR] Consent form action : {parser.form_action}")
    print(f"[EXECUTOR] Consent form inputs : {parser.inputs}")
    print(f"[EXECUTOR] Consent HTML snippet: {consent_response.text[:800]}")

    if not parser.form_action:
        # No <form> found — maybe JS-rendered.  Try a direct POST to the
        # authorize endpoint using query-string params from the URL.
        print("[EXECUTOR] No form found in consent page HTML. Trying direct authorize POST...")
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(consent_response.url)
        qs = parse_qs(parsed.query)
        post_data = {k: v[0] for k, v in qs.items()}  # api_key, sess_id, etc.
        action = "https://kite.zerodha.com/connect/authorize"
    else:
        action = parser.form_action
        if action.startswith("/"):
            action = "https://kite.zerodha.com" + action
        post_data = dict(parser.inputs)

    # Build headers that match a real browser submitting the form
    post_headers = {
        "Referer":      consent_response.url,
        "Origin":       "https://kite.zerodha.com",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    # ── ATTEMPT 1: allow_redirects=False ─────────────────────────────────
    # This is the correct approach: grab the 302 Location before requests
    # tries to follow it to an unreachable redirect_url.
    try:
        r4 = sess.post(
            action,
            data=post_data,
            headers=post_headers,
            allow_redirects=False,
            timeout=15,
        )
        print(f"[EXECUTOR] Consent POST (no-redirect) status={r4.status_code} location={r4.headers.get('Location','')}")
        loc = r4.headers.get("Location", "")
        if "request_token=" in loc:
            token = loc.split("request_token=")[1].split("&")[0].split("#")[0].strip()
            print(f"[EXECUTOR] ✅ request_token extracted from 302 Location: {token[:8]}...")
            return token
    except Exception as e:
        print(f"[EXECUTOR] Consent POST (no-redirect) exception: {e}")

    # ── ATTEMPT 2: allow_redirects=True ──────────────────────────────────
    # Fallback — maybe the redirect_url IS reachable (e.g. VPS callback server).
    try:
        r4b = sess.post(
            action,
            data=post_data,
            headers=post_headers,
            allow_redirects=True,
            timeout=15,
        )
        token = _extract_request_token(r4b)
        if token:
            print(f"[EXECUTOR] ✅ request_token extracted from followed redirect: {token[:8]}...")
            return token
        print(f"[EXECUTOR] Consent POST (follow-redirect) final_url={r4b.url} status={r4b.status_code}")
    except Exception as e:
        print(f"[EXECUTOR] Consent POST (follow-redirect) exception: {e}")

    return ""


# Force UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import db
import config as cfg

EXCHANGE        = "NFO"          # NFO for Zerodha derivatives
INSTR_SEGMENT   = "NFO-OPT"      # NIFTY index options
PRODUCT         = "NRML"         # Multi-day holding in Zerodha
IST             = pytz.timezone("Asia/Kolkata")

ORDER_RATE_LIMIT      = 10
ORDER_RATE_WINDOW_SEC = 1.0
_order_timestamps: list = []


def _ist_now() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def _check_rate_limit() -> bool:
    global _order_timestamps
    now = time.time()
    _order_timestamps = [t for t in _order_timestamps if now - t < ORDER_RATE_WINDOW_SEC]
    if len(_order_timestamps) >= ORDER_RATE_LIMIT:
        print(f"[EXECUTOR] RATE LIMIT: {ORDER_RATE_LIMIT} orders/sec exceeded. Cooling down...")
        time.sleep(ORDER_RATE_WINDOW_SEC)
        return False
    _order_timestamps.append(now)
    return True


class KiteExecutor:
    """
    Zerodha Kite Connect API executor.
    Executes orders via Kite Connect.
    """

    def __init__(self):
        self.access_token: Optional[str] = None
        self.request_token: Optional[str] = None
        self.is_logged_in: bool = False
        self.login_time: Optional[float] = None
        self.kite: Optional[KiteConnect] = None
        self._instruments_cache: Optional[pd.DataFrame] = None
        self._instruments_date: str = ""

    def load_session_from_db(self) -> None:
        """Loads access token and login state from SQLite database settings."""
        token = db.get("kite_access_token", "")
        req_token = db.get("kite_request_token", "")
        login_time_str = db.get("kite_login_time", "")
        is_logged_in_str = db.get("kite_is_logged_in", "False")

        api_key = self._api_key()
        if api_key:
            self.kite = KiteConnect(api_key=api_key)

        if token and self.kite:
            self.access_token = token
            self.request_token = req_token
            self.is_logged_in = (is_logged_in_str == "True")
            self.kite.set_access_token(token)
            try:
                self.login_time = float(login_time_str) if login_time_str else None
            except ValueError:
                self.login_time = None

    def _api_key(self) -> str:
        return db.get("KITE_API_KEY", "")

    def _api_secret(self) -> str:
        return db.get("KITE_API_SECRET", "")

    def _is_token_fresh(self) -> bool:
        """Access token lasts 24 hours. Check if still valid."""
        self.load_session_from_db()
        if not self.login_time or not self.is_logged_in or not self.access_token:
            return False
        elapsed_hrs = (time.time() - self.login_time) / 3600
        return elapsed_hrs < 23.5  # 30-min buffer

    def ensure_logged_in(self) -> bool:
        """Ensures session is active. Re-logs if token is stale."""
        if not self._is_token_fresh():
            return self.login()
        return True

    def validate_token_and_login(self, request_token: str) -> bool:
        """
        Manually connects using a redirect request token.
        Used by Streamlit URL redirect callback.
        """
        api_key = self._api_key()
        api_secret = self._api_secret()
        if not api_key or not api_secret:
            print("[EXECUTOR] Missing KITE_API_KEY or KITE_API_SECRET")
            return False

        try:
            self.kite = KiteConnect(api_key=api_key)
            session = self.kite.generate_session(request_token.strip(), api_secret=api_secret)
            access_token = session["access_token"]
            
            self.access_token = access_token
            self.request_token = request_token
            self.is_logged_in = True
            self.login_time = time.time()
            self.kite.set_access_token(access_token)

            db.set("kite_access_token", access_token)
            db.set("kite_request_token", request_token)
            db.set("kite_login_time", str(self.login_time))
            db.set("kite_is_logged_in", "True")
            db.set("last_login_time", _ist_now())
            db.set("kite_login_status", "OK")

            print(f"[EXECUTOR] manual login success at {_ist_now()}")
            return True
        except Exception as e:
            print(f"[EXECUTOR] manual login failed: {e}")
            db.set("kite_login_status", "FAILED")
            return False

    def login(self) -> bool:
        """
        Runs automated headless credentials login to get request token,
        then exchanges it for access token.
        """
        if self._is_token_fresh():
            return True

        client_code = db.get("KITE_CLIENT_CODE", "").strip()
        password    = db.get("KITE_PASSWORD", "").strip()
        totp_key    = db.get("KITE_TOTP_KEY", "").strip()
        api_key     = self._api_key().strip()
        api_secret  = self._api_secret().strip()

        if not all([client_code, password, totp_key, api_key, api_secret]):
            print("[EXECUTOR] Automated login skipped: Missing KITE credentials in secrets.txt")
            return False

        if "YOUR_" in (client_code.upper() + password.upper() + totp_key.upper() + api_key.upper() + api_secret.upper()):
            print("[EXECUTOR] Automated login skipped: Placeholder keys detected in secrets.txt")
            return False

        print(f"[EXECUTOR] Starting Zerodha automated headless login at {_ist_now()}...")

        try:
            # Step 1: Headless session to submit user ID + password
            sess = requests.Session()
            sess.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            })
            sess.get("https://kite.zerodha.com/")

            payload1 = {"user_id": client_code, "password": password}
            r1 = sess.post("https://kite.zerodha.com/api/login", data=payload1, timeout=15)
            data1 = r1.json()
            if data1.get("status") != "success":
                print(f"[EXECUTOR] Automated login Step 1 failed: {data1.get('message')}")
                return False

            request_id = data1["data"]["request_id"]

            # Step 2: Generate TOTP code and submit
            totp = pyotp.TOTP(totp_key.replace(" ", "")).now()
            payload2 = {
                "user_id": client_code,
                "request_id": request_id,
                "twofa_value": totp,
                "twofa_type": "totp"
            }
            r2 = sess.post("https://kite.zerodha.com/api/twofa", data=payload2, timeout=15)
            data2 = r2.json()
            if data2.get("status") != "success":
                print(f"[EXECUTOR] Automated login Step 2 failed: {data2.get('message')}")
                return False

            # Step 3: Authorize on developer portal to get request_token
            # Use hop-by-hop redirect follower so we intercept the final
            # redirect to the redirect_url (127.0.0.1:PORT) without connecting.
            auth_url = f"https://kite.trade/connect/login?api_key={api_key}"
            request_token = _follow_to_request_token(sess, auth_url)

            if not request_token:
                print(f"[EXECUTOR] Automated login failed: Could not parse request_token from redirect chain.")
                return False

            # Step 4: Exchange for access token
            return self.validate_token_and_login(request_token)

        except Exception as e:
            print(f"[EXECUTOR] Headless login exception: {e}")
            db.set("kite_login_status", "FAILED")
            return False

    def request_login_otp(self) -> Optional[dict]:
        """
        Submits client credentials to Zerodha to trigger the 2FA OTP.
        Returns a dict containing request_id, session object, cookies dict, and twofa_type on success,
        or None on failure.
        """
        client_code = db.get("KITE_CLIENT_CODE", "").strip()
        password    = db.get("KITE_PASSWORD", "").strip()

        if not all([client_code, password]):
            print("[EXECUTOR] Request OTP failed: Missing client_code or password in secrets.txt")
            return None

        print(f"[EXECUTOR] Requesting Zerodha OTP for {client_code}...")
        try:
            sess = requests.Session()
            sess.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://kite.zerodha.com/",
                "Origin": "https://kite.zerodha.com"
            })
            sess.get("https://kite.zerodha.com/")

            payload1 = {"user_id": client_code, "password": password}
            r1 = sess.post("https://kite.zerodha.com/api/login", data=payload1, timeout=15)
            data1 = r1.json()
            if data1.get("status") != "success":
                print(f"[EXECUTOR] Request OTP login step failed: {data1.get('message')}")
                return None

            request_id = data1["data"]["request_id"]
            twofa_type = data1["data"].get("twofa_type", "sms")
            cookies = requests.utils.dict_from_cookiejar(sess.cookies)

            return {
                "request_id": request_id,
                "session": sess,
                "cookies": cookies,
                "twofa_type": twofa_type
            }
        except Exception as e:
            print(f"[EXECUTOR] Request OTP exception: {e}")
            return None

    def complete_login_with_otp(self, request_id: str, session_or_cookies, otp_code: str, twofa_type: str = "totp") -> tuple:
        """
        Completes the login using a previously received request_id and session cookies / session object,
        by submitting the manual otp_code.
        Returns a tuple of (bool, str) representing (success, message).
        """
        client_code = db.get("KITE_CLIENT_CODE", "").strip()
        api_key     = self._api_key().strip()

        otp_code = otp_code.strip().replace(" ", "")
        if not otp_code or not otp_code.isdigit() or len(otp_code) != 6:
            msg = f"Invalid OTP code '{otp_code}'. Must be a 6-digit number."
            print(f"[EXECUTOR] Complete manual OTP login failed: {msg}")
            return False, msg

        try:
            if isinstance(session_or_cookies, requests.Session):
                sess = session_or_cookies
            else:
                sess = requests.Session()
                sess.headers.update({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://kite.zerodha.com/",
                    "Origin": "https://kite.zerodha.com"
                })
                # Restore cookies
                requests.utils.cookiejar_from_dict(session_or_cookies, cookiejar=sess.cookies)

            # Submit OTP
            payload2 = {
                "user_id": client_code,
                "request_id": request_id,
                "twofa_value": otp_code,
                "twofa_type": twofa_type
            }
            r2 = sess.post("https://kite.zerodha.com/api/twofa", data=payload2, timeout=15)
            data2 = r2.json()
            if data2.get("status") != "success":
                msg = data2.get("message", "2FA Verification Failed")
                print(f"[EXECUTOR] Complete manual OTP login Step 2 failed: {msg}")
                return False, msg

            # Step 3: Authorize on developer portal to get request_token
            # Use hop-by-hop redirect follower so we intercept the final
            # redirect to the redirect_url (127.0.0.1:PORT) without connecting.
            auth_url = f"https://kite.trade/connect/login?api_key={api_key}"
            request_token = _follow_to_request_token(sess, auth_url)

            if not request_token:
                msg = "Could not parse request_token from redirect chain. Check API key and Zerodha developer app settings."
                print(f"[EXECUTOR] Complete manual OTP login failed: {msg}")
                return False, msg

            # Step 4: Exchange for access token
            ok = self.validate_token_and_login(request_token)
            if ok:
                return True, "Login successful!"
            else:
                return False, "Failed to exchange request_token for access_token."
        except Exception as e:
            msg = str(e)
            print(f"[EXECUTOR] Complete manual OTP login exception: {msg}")
            db.set("kite_login_status", "FAILED")
            return False, msg

    def login_with_otp(self, otp_code: str) -> tuple:
        """
        Backward compatible wrapper for direct 6-digit OTP login.
        Returns a tuple of (bool, str) representing (success, message).
        """
        res = self.request_login_otp()
        if not res:
            return False, "Failed to submit client credentials for login request."
        return self.complete_login_with_otp(res["request_id"], res["session"], otp_code, res["twofa_type"])

    # ─────────────────────────────────────────────────────────────────────────
    # PLACE ORDER
    # ─────────────────────────────────────────────────────────────────────────
    def place_order(self, *args, **kwargs) -> Optional[str]:
        transaction_type = None
        trading_symbol = None
        symbol_token = None
        qty = None
        order_type = "MARKET"
        price = 0.0
        trigger_price = 0.0

        if "transaction_type" in kwargs:
            transaction_type = kwargs.get("transaction_type")
        if "trading_symbol" in kwargs:
            trading_symbol = kwargs.get("trading_symbol")
        if "symbol_token" in kwargs:
            symbol_token = kwargs.get("symbol_token")
        if "qty" in kwargs:
            qty = kwargs.get("qty")
        if "order_type" in kwargs:
            order_type = kwargs.get("order_type")
        if "price" in kwargs:
            price = kwargs.get("price")
        if "trigger_price" in kwargs:
            trigger_price = kwargs.get("trigger_price")

        # Map positional args
        if len(args) >= 4:
            transaction_type = args[0]
            arg1 = str(args[1]).strip()
            arg2 = str(args[2]).strip()
            arg3 = args[3]

            if arg1.isdigit() or arg1.startswith("MOCK_"):
                symbol_token = arg1
                qty = int(arg2) if str(arg2).isdigit() else arg2
                trading_symbol = str(arg3)
            else:
                trading_symbol = arg1
                symbol_token = arg2
                qty = int(arg3) if str(arg3).isdigit() else arg3

            if len(args) >= 5:
                order_type = args[4]
            if len(args) >= 6:
                price = float(args[5])
            if len(args) >= 7:
                trigger_price = float(args[6])
        elif len(args) == 3:
            transaction_type = args[0]
            symbol_token = args[1]
            qty = args[2]

        if not self.ensure_logged_in():
            print("[EXECUTOR] Cannot place order -- not logged in.")
            return None

        _check_rate_limit()

        # Convert MARKET order to LIMIT to protect client execution slippage
        if order_type.upper() == "MARKET":
            ltp = self.get_ltp(symbol_token, trading_symbol)
            if ltp <= 0:
                # Fallback to get LTP directly
                ltp = self.get_live_ltp(symbol_token, trading_symbol)
            if ltp <= 0:
                ltp = 50.0  # Safe fallback

            # Add buffer for buy cover, subtract for sell short
            if transaction_type.upper() in ("BUY", "HEDGE_BUY"):
                limit_price = ltp + max(2.0, ltp * 0.10)
            else:
                limit_price = max(0.05, ltp - max(2.0, ltp * 0.10))
            
            limit_price = round(limit_price * 20) / 20
            order_type = "LIMIT"
            price = limit_price
            print(f"[EXECUTOR] Converted MARKET order to LIMIT: LTP={ltp} -> Limit Price={limit_price}")

        # Map transaction type for Kite Connect
        tx_type_map = {
            "BUY": self.kite.TRANSACTION_TYPE_BUY,
            "HEDGE_BUY": self.kite.TRANSACTION_TYPE_BUY,
            "SELL": self.kite.TRANSACTION_TYPE_SELL
        }
        kite_tx_type = tx_type_map.get(transaction_type.upper(), self.kite.TRANSACTION_TYPE_BUY)

        order_type_map = {
            "LIMIT": self.kite.ORDER_TYPE_LIMIT,
            "MARKET": self.kite.ORDER_TYPE_MARKET
        }
        kite_order_type = order_type_map.get(order_type.upper(), self.kite.ORDER_TYPE_MARKET)

        try:
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.kite.EXCHANGE_NFO,
                tradingsymbol=trading_symbol.upper(),
                transaction_type=kite_tx_type,
                quantity=int(qty),
                product=self.kite.PRODUCT_NRML,
                order_type=kite_order_type,
                price=float(price) if kite_order_type == self.kite.ORDER_TYPE_LIMIT else None,
                trigger_price=float(trigger_price) if trigger_price > 0 else None
            )
            print(f"[EXECUTOR] ✅ Zerodha order placed: {order_id} | {transaction_type} {qty} {trading_symbol}")
            return str(order_id)
        except Exception as e:
            print(f"[EXECUTOR] ❌ Place order failed for {trading_symbol}: {e}")
            return None

    def cancel_order(self, order_id: str, variety: str = "regular") -> bool:
        if not self.ensure_logged_in():
            return False
        try:
            self.kite.cancel_order(variety=self.kite.VARIETY_REGULAR, order_id=order_id)
            print(f"[EXECUTOR] Order {order_id} cancelled successfully.")
            return True
        except Exception as e:
            print(f"[EXECUTOR] Cancel order {order_id} failed: {e}")
            return False

    def get_order_status(self, order_id: str) -> str:
        if not self.ensure_logged_in():
            return "FAILED"
        try:
            history = self.kite.order_history(order_id=order_id)
            if not history:
                return "FAILED"
            
            # The last item in order history is the current state
            current_state = history[-1]
            status = current_state.get("status", "").upper()

            if status == "COMPLETE":
                return "SUCCESS"
            elif status in ("REJECTED", "CANCELLED", "FAILED"):
                return "FAILED"
            else:
                return "PENDING"
        except Exception as e:
            print(f"[EXECUTOR] Exception in get_order_status for {order_id}: {e}")
            return "FAILED"

    def poll_order_fill(self, order_id: str, max_attempts: int = 10, delay_sec: float = 3.0) -> bool:
        print(f"[EXECUTOR] Polling order {order_id} for fill (max {max_attempts} attempts)...")
        for attempt in range(1, max_attempts + 1):
            status = self.get_order_status(order_id)
            print(f"[EXECUTOR]   Attempt {attempt}/{max_attempts}: {order_id} -> {status}")
            if status == "SUCCESS":
                return True
            elif status == "FAILED":
                return False
            time.sleep(delay_sec)
        return False

    def get_all_orders(self) -> list:
        if not self.ensure_logged_in():
            return []
        try:
            return self.kite.orders()
        except Exception as e:
            print(f"[EXECUTOR] Exception in get_all_orders: {e}")
            return []

    def get_trade_book(self) -> list:
        if not self.ensure_logged_in():
            return []
        try:
            return self.kite.trades()
        except Exception as e:
            print(f"[EXECUTOR] Exception in get_trade_book: {e}")
            return []

    def get_positions(self) -> list:
        if not self.ensure_logged_in():
            return []
        try:
            # positions() returns {"net": [...], "day": [...]}
            return self.kite.positions().get("net", [])
        except Exception as e:
            print(f"[EXECUTOR] Exception in get_positions: {e}")
            return []

    def get_live_ltp(self, symbol_token: str, trading_symbol: str = "") -> float:
        if not self.ensure_logged_in():
            return 0.0
        try:
            # Zerodha ltp queries take list of "EXCHANGE:SYMBOL" or instrument tokens
            query = f"NFO:{trading_symbol}" if trading_symbol else str(symbol_token)
            res = self.kite.ltp(query)
            if query in res:
                return float(res[query].get("last_price", 0.0))
        except Exception as e:
            print(f"[EXECUTOR] Exception in get_live_ltp for {trading_symbol or symbol_token}: {e}")
        return 0.0

    def get_ltp(self, symbol_token: str, trading_symbol: str = "") -> float:
        """Mimics get_ltp using Zerodha ltp() call."""
        if not self.ensure_logged_in():
            return 0.0

        # Try live query first
        ltp = self.get_live_ltp(symbol_token, trading_symbol)
        if ltp > 0:
            return ltp

        # Fallback from position book
        try:
            positions = self.get_positions()
            for pos in positions:
                if (
                    str(pos.get("instrument_token")) == str(symbol_token)
                    or pos.get("tradingsymbol", "").upper() == trading_symbol.upper()
                ):
                    return float(pos.get("last_price", 0.0))
        except Exception as e:
            print(f"[EXECUTOR] Fallback positions lookup failed: {e}")

        return 0.0

    # ─────────────────────────────────────────────────────────────────────────
    # SECURITY MASTER — Instruments download for Zerodha
    # ─────────────────────────────────────────────────────────────────────────
    def _load_security_master(self) -> pd.DataFrame:
        """
        Downloads and parses Zerodha's instruments CSV.
        Cached locally in folder to avoid downloading multiple times per day.
        """
        today = datetime.now(IST).strftime("%Y-%m-%d")
        cache_file = os.path.join(cfg.BASE_DIR, "zerodha_instruments.csv")

        # If cache is fresh, load it
        if self._instruments_cache is not None and self._instruments_date == today:
            return self._instruments_cache

        if os.path.exists(cache_file):
            mtime = datetime.fromtimestamp(os.path.getmtime(cache_file), IST).strftime("%Y-%m-%d")
            if mtime == today:
                try:
                    df = pd.read_csv(cache_file)
                    self._instruments_cache = df
                    self._instruments_date = today
                    print(f"[EXECUTOR][SM] Loaded {len(df):,} instruments from local cache.")
                    return df
                except Exception as e:
                    print(f"[EXECUTOR][SM] Failed to read cached csv: {e}")

        # Download from Zerodha Kite API
        url = "https://api.kite.trade/instruments"
        print(f"[EXECUTOR][SM] Downloading instruments CSV from {url}...")
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(resp.text)
                
                df = pd.read_csv(cache_file)
                self._instruments_cache = df
                self._instruments_date = today
                print(f"[EXECUTOR][SM] Downloaded and cached {len(df):,} instruments.")
                return df
            else:
                print(f"[EXECUTOR][SM] Error downloading instruments: HTTP {resp.status_code}")
        except Exception as e:
            print(f"[EXECUTOR][SM] Instrument download exception: {e}")

        if os.path.exists(cache_file):
            print("[EXECUTOR][SM] Loading stale instruments cache file as fallback...")
            try:
                df = pd.read_csv(cache_file)
                self._instruments_cache = df
                return df
            except Exception:
                pass

        return pd.DataFrame()

    def search_option_symbol(self, *args, **kwargs) -> Optional[dict]:
        """
        Searches Zerodha instruments cache for the correct option symbol.
        Returns: {"token": instrument_token, "trading_symbol": tradingsymbol}
        """
        expiry_date  = None
        strike_price = None
        option_type  = None
        symbol       = "NIFTY"

        if "expiry_date" in kwargs or "strike_price" in kwargs or "option_type" in kwargs:
            expiry_date  = kwargs.get("expiry_date")
            strike_price = kwargs.get("strike_price")
            option_type  = kwargs.get("option_type")
            symbol       = kwargs.get("symbol", "NIFTY")
        elif "expiry" in kwargs:
            expiry_date  = kwargs.get("expiry")
            strike_price = kwargs.get("strike_price")
            option_type  = kwargs.get("option_type")
            symbol       = kwargs.get("symbol", "NIFTY")
        elif len(args) >= 3:
            expiry_date  = args[0]
            strike_price = args[1]
            option_type  = args[2]

        if not expiry_date or not strike_price or not option_type:
            print("[EXECUTOR] search_option_symbol: missing expiry/strike/option_type")
            return None

        strike_price = int(float(strike_price))
        option_type  = str(option_type).strip().upper()

        # Normalise expiry to YYYY-MM-DD (Zerodha formats expiry date as YYYY-MM-DD in CSV)
        expiry_str = str(expiry_date).strip()
        expiry_yyyy_mm_dd = None
        expiry_yyyymmdd = None

        # Robust, locale-independent parser for DD-Mon-YYYY or DD-Month-YYYY
        parts = expiry_str.split("-")
        if len(parts) == 3 and parts[0].isdigit() and parts[2].isdigit():
            try:
                day = int(parts[0])
                mon_str = parts[1].upper()
                year = int(parts[2])
                months = {
                    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
                    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
                    "JANUARY": 1, "FEBRUARY": 2, "MARCH": 3, "APRIL": 4, "JUNE": 6,
                    "JULY": 7, "AUGUST": 8, "SEPTEMBER": 9, "OCTOBER": 10, "NOVEMBER": 11, "DECEMBER": 12
                }
                if mon_str in months:
                    month = months[mon_str]
                    from datetime import datetime as dt_class
                    dt = dt_class(year, month, day)
                    expiry_yyyy_mm_dd = dt.strftime("%Y-%m-%d")
                    expiry_yyyymmdd = dt.strftime("%Y%m%d")
            except Exception:
                pass

        if not expiry_yyyy_mm_dd:
            for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    dt = datetime.strptime(expiry_str, fmt)
                    expiry_yyyy_mm_dd = dt.strftime("%Y-%m-%d")
                    expiry_yyyymmdd = dt.strftime("%Y%m%d")
                    break
                except ValueError:
                    continue


        if not expiry_yyyy_mm_dd:
            expiry_yyyy_mm_dd = expiry_str
            expiry_yyyymmdd = expiry_str.replace("-", "")

        df = self._load_security_master()
        if df.empty:
            print("[EXECUTOR][SM] Instruments table is empty.")
            return None

        # Filter: name == NIFTY (or name == "NIFTY 50" / starts with NIFTY), exchange == NFO, option_type, expiry, strike
        # In Kite instruments, name is "NIFTY" for Nifty options.
        filtered = df[
            (df["name"].str.upper() == "NIFTY") &
            (df["exchange"].str.upper() == "NFO") &
            (df["expiry"] == expiry_yyyy_mm_dd) &
            (df["strike"] == float(strike_price)) &
            (df["instrument_type"].str.upper() == option_type)
        ]

        if not filtered.empty:
            row = filtered.iloc[0]
            token = str(row["instrument_token"])
            tradingsymbol = str(row["tradingsymbol"])
            lot_size = int(row["lot_size"])

            # Cache metadata for placing orders later
            self._last_sym_meta = {
                "expiry_yyyymmdd": expiry_yyyymmdd,
                "strike_price": strike_price,
                "option_type": option_type,
                "lot_size": lot_size
            }

            print(f"[EXECUTOR][SM] Found contract: {tradingsymbol} | Token={token}")
            return {
                "token": token,
                "trading_symbol": tradingsymbol,
                "security_id": token,
                "underlying": "NIFTY 50",
            }

        print(f"[EXECUTOR][SM] Option NOT found: NIFTY {expiry_yyyy_mm_dd} {strike_price} {option_type}")
        return None

    def test_connection(self) -> dict:
        if not self.ensure_logged_in():
            return {
                "status":  "FAILED",
                "mode":    "LIVE",
                "message": "Zerodha login failed. Verify KITE credentials in secrets.txt.",
            }

        try:
            positions = self.get_positions()
            return {
                "status":    "OK",
                "mode":      "LIVE",
                "message":   f"Zerodha API connected. Open positions: {len(positions)}",
                "positions": len(positions),
            }
        except Exception as e:
            return {
                "status":  "FAILED",
                "mode":    "LIVE",
                "message": f"Connection test error: {e}",
            }

    def get_order_fill_price(self, order_id: str) -> float:
        if not self.ensure_logged_in():
            return 0.0
        try:
            trades = self.get_trade_book()
            for t in trades:
                if str(t.get("order_id")) == str(order_id):
                    return float(t.get("average_price") or t.get("price") or 0.0)
            
            orders = self.get_all_orders()
            for o in orders:
                if str(o.get("order_id")) == str(order_id):
                    return float(o.get("average_price") or o.get("price") or 0.0)
        except Exception as e:
            print(f"[EXECUTOR] Error getting fill price for order {order_id}: {e}")
        return 0.0

    def execute_sell_and_confirm(self, trading_symbol: str, symbol_token: str, qty: int, limit_price: float = 0.0) -> tuple:
        order_type = "LIMIT" if limit_price > 0 else "MARKET"
        order_id = self.place_order(
            transaction_type = "SELL",
            trading_symbol   = trading_symbol,
            symbol_token     = symbol_token,
            qty              = qty,
            order_type       = order_type,
            price            = limit_price,
        )
        if not order_id:
            return None, False

        filled = self.poll_order_fill(order_id)
        return order_id, filled

    def execute_buy_and_confirm(self, trading_symbol: str, symbol_token: str, qty: int, limit_price: float = 0.0) -> tuple:
        order_type = "LIMIT" if limit_price > 0 else "MARKET"
        order_id = self.place_order(
            transaction_type = "BUY",
            trading_symbol   = trading_symbol,
            symbol_token     = symbol_token,
            qty              = qty,
            order_type       = order_type,
            price            = limit_price,
        )
        if not order_id:
            return None, False

        filled = self.poll_order_fill(order_id)
        return order_id, filled


# Singleton instance
kite_executor = KiteExecutor()
