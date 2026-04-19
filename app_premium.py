"""
PREMIUM SIGNAL GENERATOR - RENDER DEPLOYMENT
With proxy rotation to bypass Quotex datacenter IP block
"""

from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import secrets
import time
import os
import json
import traceback
import asyncio
from market_analyzer import MarketAnalyzer
from pyquotex.stable_api import Quotex

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
CORS(app)

app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# Writable path on Render
ROOT_PATH = "/tmp/quotex"
os.makedirs(ROOT_PATH, exist_ok=True)
os.makedirs(os.path.join(ROOT_PATH, "browser"), exist_ok=True)
os.makedirs(os.path.join(ROOT_PATH, "settings"), exist_ok=True)

# Prevent pyquotex from calling input() on a server
with open(os.path.join(ROOT_PATH, "settings", "config.ini"), "w") as _f:
    _f.write("[settings]\nemail=placeholder@email.com\npassword=placeholder\n")

# Write session.json from env variable if present
QUOTEX_SESSION = os.environ.get("QUOTEX_SESSION")
if QUOTEX_SESSION:
    with open(os.path.join(ROOT_PATH, "session.json"), "w") as _f:
        _f.write(QUOTEX_SESSION)
    print("Session file written from environment variable")

# ─────────────────────────────────────────────────────────────
# PROXY LIST — all 10 Webshare proxies with auto-rotation
# Format: (host, port, username, password)
# ─────────────────────────────────────────────────────────────
PROXIES = [
    ("31.59.20.176",      6754, "gixtiejj", "x7n4hi71ksvo"),
    ("198.23.239.134",    6540, "gixtiejj", "x7n4hi71ksvo"),
    ("45.38.107.97",      6014, "gixtiejj", "x7n4hi71ksvo"),
    ("107.172.163.27",    6543, "gixtiejj", "x7n4hi71ksvo"),
    ("198.105.121.200",   6462, "gixtiejj", "x7n4hi71ksvo"),
    ("216.10.27.159",     6837, "gixtiejj", "x7n4hi71ksvo"),
    ("142.111.67.146",    5611, "gixtiejj", "x7n4hi71ksvo"),
    ("191.96.254.138",    6185, "gixtiejj", "x7n4hi71ksvo"),
    ("31.58.9.4",         6077, "gixtiejj", "x7n4hi71ksvo"),
    ("23.26.71.145",      5628, "gixtiejj", "x7n4hi71ksvo"),
]

# Global state
quotex_client   = None
analyzer        = None
is_connected    = False
cached_pairs    = []
last_cache_time = 0


def run_async(coro):
    """Run async coroutine from sync gunicorn worker"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result(timeout=60)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options']        = 'SAMEORIGIN'
    response.headers['X-XSS-Protection']       = '1; mode=block'
    return response

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────

@app.route('/admin')
def admin_panel():
    return render_template('admin.html')

@app.route('/')
def dashboard():
    if not is_connected:
        return render_template('admin.html')
    return render_template('user_dashboard.html')


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    global quotex_client, analyzer, is_connected

    data     = request.json or {}
    email    = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({"success": False, "message": "Email and password required"})

    async def try_connect_with_proxy(host, port, user, pwd):
        """Attempt connection through a single proxy"""
        try:
            proxy_url = f"http://{user}:{pwd}@{host}:{port}"
            print(f"Trying proxy {host}:{port}...")

            client = Quotex(
                email=email,
                password=password,
                lang="en",
                root_path=ROOT_PATH,
                proxy=proxy_url
            )
            check, reason = await client.connect()
            if check:
                return client, "Connected"
            else:
                print(f"  Proxy {host}:{port} failed: {reason}")
                return None, str(reason)
        except Exception as e:
            print(f"  Proxy {host}:{port} exception: {e}")
            return None, str(e)

    async def do_connect():
        global quotex_client, analyzer, is_connected

        last_error = "All proxies failed"

        for (host, port, user, pwd) in PROXIES:
            client, message = await try_connect_with_proxy(host, port, user, pwd)
            if client:
                quotex_client = client
                analyzer      = MarketAnalyzer(quotex_client)
                is_connected  = True
                print(f"Connected via proxy {host}:{port}")
                return True, f"Connected via {host}"
            last_error = message
            # Small delay before trying next proxy
            await asyncio.sleep(1)

        # Last resort: try without proxy
        print("All proxies failed, trying direct connection...")
        try:
            client = Quotex(
                email=email,
                password=password,
                lang="en",
                root_path=ROOT_PATH
            )
            check, reason = await client.connect()
            if check:
                quotex_client = client
                analyzer      = MarketAnalyzer(quotex_client)
                is_connected  = True
                print("Connected directly (no proxy)")
                return True, "Connected"
            last_error = str(reason)
        except Exception as e:
            last_error = str(e)

        print(f"All connection attempts failed. Last error: {last_error}")
        return False, last_error

    try:
        success, message = run_async(do_connect())
        if success:
            session['admin'] = True
            return jsonify({"success": True, "message": message})
        return jsonify({"success": False, "message": message})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": f"Server error: {str(e)}"})


@app.route('/api/admin/status', methods=['GET'])
def admin_status():
    return jsonify({"connected": is_connected})


@app.route('/api/admin/logout', methods=['POST'])
def admin_logout():
    global quotex_client, analyzer, is_connected
    is_connected  = False
    quotex_client = None
    analyzer      = None
    session.clear()
    return jsonify({"success": True})


# ─────────────────────────────────────────────────────────────
# TRADING PAIRS
# ─────────────────────────────────────────────────────────────

@app.route('/api/pairs', methods=['GET'])
def get_pairs():
    global cached_pairs, last_cache_time

    if not is_connected or not quotex_client:
        return jsonify({"error": "System offline"}), 503

    if cached_pairs and (time.time() - last_cache_time) < 300:
        return jsonify({"pairs": cached_pairs})

    async def fetch_pairs():
        all_assets   = await quotex_client.get_all_assets()
        payment_data = quotex_client.get_payment()
        pairs = []

        for asset_code, _ in all_assets.items():
            display_name = None
            payout  = 0
            is_open = False

            for pay_name, pay_info in payment_data.items():
                if not isinstance(pay_info, dict):
                    continue
                pay_clean   = pay_name.replace('(OTC)','').replace(' ','').replace('/','').upper()
                asset_clean = str(asset_code).replace('_otc','').replace('_OTC','').upper()
                if pay_clean in asset_clean or asset_clean in pay_clean:
                    display_name = pay_name
                    is_open      = pay_info.get('open', False)
                    turbo        = pay_info.get('turbo_payment', 0)
                    if turbo and turbo > 0:
                        payout = float(turbo)
                    else:
                        profit = pay_info.get('profit', {})
                        if isinstance(profit, dict):
                            payout = float(profit.get('1M', 0))
                    break

            if not display_name:
                display_name = str(asset_code)

            is_otc   = '(OTC)' in display_name or '_otc' in str(asset_code).lower()
            a_up     = str(asset_code).upper()
            d_up     = display_name.upper()
            category = "Currency"

            if any(x in a_up or x in d_up for x in [
                'BTC','ETH','LTC','XRP','DOGE','ADA','DOT','LINK','UNI',
                'SOL','MATIC','SHIB','AVAX','ATOM','CHAIN','TON','APT','COSMOS']):
                category = "Crypto"
            elif any(x in a_up or x in d_up for x in [
                'GOLD','SILVER','OIL','GAS','CRUDE','BRENT','COPPER','PLATINUM','NATURAL']):
                category = "Commodities"
            elif any(x in a_up or x in d_up for x in [
                'AAPL','GOOGL','GOOGLE','TSLA','TESLA','MSFT','MICROSOFT','AMZN',
                'AMAZON','META','FACEBOOK','NFLX','NETFLIX','NVDA','NVIDIA',
                'AMD','INTEL','COCA','MCDONALDS','MCD','NIKE','DISNEY']):
                category = "Stocks"

            pairs.append({
                "code": str(asset_code), "name": display_name,
                "payout": payout, "is_open": is_open,
                "is_otc": is_otc, "category": category
            })

        pairs.sort(key=lambda x: x['payout'], reverse=True)
        return pairs

    try:
        pairs           = run_async(fetch_pairs())
        cached_pairs    = pairs
        last_cache_time = time.time()
        print(f"Loaded {len(pairs)} pairs")
        return jsonify({"pairs": pairs})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# ANALYSIS
# ─────────────────────────────────────────────────────────────

@app.route('/api/analyze/<path:asset_identifier>', methods=['GET'])
def analyze_asset(asset_identifier):
    if not is_connected or not analyzer:
        return jsonify({"error": "System offline"}), 503

    async def do_analysis():
        asset_code = asset_identifier
        if ' ' in asset_identifier or '(' in asset_identifier:
            for pair in cached_pairs:
                if pair['name'] == asset_identifier:
                    asset_code = pair['code']
                    break
        return await analyzer.get_comprehensive_analysis(asset_code)

    try:
        print(f"Analyzing {asset_identifier}...")
        analysis = run_async(do_analysis())
        if "error" in analysis:
            return jsonify({"error": analysis["error"]}), 400
        print("Analysis complete")
        return jsonify(analysis)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("="*60)
    print("PREMIUM SIGNAL GENERATOR")
    print("Admin: http://localhost:5000/admin")
    print("="*60)
    app.run(host='0.0.0.0', port=5000, debug=False)
