"""
PREMIUM SIGNAL GENERATOR - PRODUCTION READY
With Admin Panel & Session Management
"""

from flask import Flask, render_template, request, jsonify, session, redirect
from flask_cors import CORS
import secrets
import time
from pyquotex.stable_api import Quotex
from market_analyzer import MarketAnalyzer
import traceback

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app)

# Production configuration
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# Global state
quotex_client = None
analyzer = None
is_connected = False
cached_pairs = []
last_cache_time = 0

@app.after_request
def add_security_headers(response):
    """Add security headers for production"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

@app.route('/admin')
def admin_panel():
    """Admin panel for Quotex login"""
    return render_template('admin.html')

@app.route('/')
def dashboard():
    """User dashboard - check if system is connected"""
    if not is_connected:
        return render_template('maintenance.html')
    return render_template('user_dashboard.html')
@app.route('/api/admin/login', methods=['POST'])
async def admin_login():
    """Admin: Connect to Quotex"""
    global quotex_client, analyzer, is_connected
    
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    try:
        print(f"Connecting to Quotex...")
        quotex_client = Quotex(email=email, password=password, lang="en")
        
        # Hardcoded session from environment
        import os
        import json
        session_json = os.environ.get('QUOTEX_SESSION', '{"cookies": "laravel_session=eyJpdiI6Inp5U0lxL3JqbXdHdUNseHMzOEpJdGc9PSIsInZhbHVlIjoiQ1Z2R1pXMVlNQmJERXdiZlowKzJjTkE5Z1hDc095cU9nTExIYVg5NTFEeC8zTkJQMHVYMVBlbFVqUlY5UXllNlY4MEViZHN0UmVMSkpsNDFPcm56d2ZqZ0RYenlubndYc0w3T3B3Yys5dW03R2JGR2FGQUk4MlkzVVJvamVybDgiLCJtYWMiOiI0MGJjMTUwNjlkYjYwZTliNTIzNGM4ZjhjYTE5YjVlYzIyYTA4YjUwNzVjYjY4OGUyOTgxNGQ1MzQwMDMwN2E3IiwidGFnIjoiIn0%3D; lang=en; remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d=eyJpdiI6IjYvM0Fqa3lrZjh3UXdoQitpaVhzQ0E9PSIsInZhbHVlIjoiVm02Titxb2x0K0wwS3R4S2trTDd6MVQyeGRrZCtlUENHMlEvUUl2QUNoL2lFZjF0Uk5Cem9OMHZMbVJLeFFGNi8rbDQrUEU0QW00czFIQ1VwK2pKL0ZBcVA0akZrQi9VZ0k0QnkwT21PR3VQZUtMOTZWUmZUc0sxZGtmU2x5c1BmTmRQWEQrWU9ISmxXRFdOOGNEQW5hQVdaeC9qdGUxUnZFbE1nemY0TWU5ZytUNTNtZXFPeG9UeHF5Y3ZUbXpTUWt1dWJ6WTE5SlBJRVZ6ZjFGRWdtWEtoVHNHRE1pYS9NcWZSaUNBekVEUHV0T0ExbEl3N3VBQXhiQXZlcmtybiIsIm1hYyI6IjdiYzM1OWFmMGQxOGEyMmRmMTEwMzI2YmY5YzdkMzZkNmM0ZDA0MjkwNjYzODVkY2Y4MTk5ZTllOTkyZTNmZWIiLCJ0YWciOiIifQ%3D%3D; last_trade=eyJpdiI6IlFtRmc1c254VDhuRlUxUW0rR0d6ZlE9PSIsInZhbHVlIjoiMFhWZ2t2SDNNS2NMeTN1WTlJWEcwWmpsWkxEUHRxandKZ1pwUDRpTlplYjFLRE81UnBObmlFZTJsekhCQ0FyNCIsIm1hYyI6ImNmYzY5N2I3YjM1YjA4MWY4OGNlMGFiZDgzODJkYjY4YTRhZjIyOGNkZjU2Y2ZlZTMzY2U0YzA2Y2I4YTJjYTEiLCJ0YWciOiIifQ%3D%3D; __cf_bm=7xZalnv7MYn.br0cctLOVGRCbY7q5DH8P0oA8rL2LnE-1776328104.1192274-1.0.1.1-PXdSUn6IC9y0zkub_1mQiE0BTcssTxgSFhO2idANQ7c5mfI7BZ1g9GnnQqQOYtibrlsDana7pDYH6RA_w9ufewJGc2_jBtx.sC_kURkRdkFYz6fKCSLfHmu_cxa7g37p; _cfuvid=gwt0IQ0sbKeVGAmq27cThXW_2uyFe5QvzJsAcOvvX.4-1776328104.1192274-1.0.1.1-IOGBZ.gW4JNyUQZwhDJKT_A9umZc7l544vnggJfEClk; __vid_l3=d28edfd9-b007-4b6b-a4eb-b107eb4ab82a", "token": "lCnrYb6xDDc4tX4NSJbJoUO798BeaxI5EUdMBXoI", "user_agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0"}')
        
        try:
            session_data = json.loads(session_json)
            quotex_client.cookies = session_data.get('cookies')
            quotex_client.token = session_data.get('token')
            quotex_client.user_agent = session_data.get('user_agent')
            print("✅ Loaded saved session")
        except:
            pass
        
        check, reason = await quotex_client.connect()
        
        if check:
            analyzer = MarketAnalyzer(quotex_client)
            is_connected = True
            session['admin'] = True
            print("✅ Connected successfully!")
            return jsonify({"success": True, "message": "Connected"})
        else:
            print(f"❌ Connection failed: {reason}")
            return jsonify({"success": False, "message": reason})
    
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/admin/status', methods=['GET'])
def admin_status():
    """Check connection status"""
    return jsonify({"connected": is_connected})

@app.route('/api/pairs', methods=['GET'])
async def get_pairs():
    """Get all trading pairs with payout and categories"""
    global cached_pairs, last_cache_time
    
    if not is_connected or not quotex_client:
        return jsonify({"error": "System offline"}), 503
    
    # Cache for 5 minutes
    if cached_pairs and (time.time() - last_cache_time) < 300:
        return jsonify({"pairs": cached_pairs})
    
    try:
        print("Fetching pairs...")
        
        # Get both asset codes and payment data
        all_assets = await quotex_client.get_all_assets()
        payment_data = quotex_client.get_payment()
        
        pairs = []
        
        # Iterate through actual asset codes
        for asset_code, asset_info in all_assets.items():
            # Find matching payment data by searching for the asset code in payment names
            display_name = None
            payout = 0
            is_open = False
            
            # Search payment data for this asset
            for pay_name, pay_info in payment_data.items():
                if not isinstance(pay_info, dict):
                    continue
                
                # Check if this payment entry matches our asset code
                # Match by checking if asset_code appears in pay_name or vice versa
                pay_name_clean = pay_name.replace('(OTC)', '').replace(' ', '').replace('/', '').upper()
                asset_code_clean = str(asset_code).replace('_otc', '').replace('_OTC', '').upper()
                
                if pay_name_clean in asset_code_clean or asset_code_clean in pay_name_clean:
                    display_name = pay_name
                    is_open = pay_info.get('open', False)
                    
                    # Get payout
                    turbo_payment = pay_info.get('turbo_payment', 0)
                    if turbo_payment and turbo_payment > 0:
                        payout = float(turbo_payment)
                    else:
                        profit_data = pay_info.get('profit', {})
                        if isinstance(profit_data, dict):
                            payout = float(profit_data.get('1M', 0))
                    break
            
            # If no display name found, use asset code
            if not display_name:
                display_name = str(asset_code)
            
            # Check if OTC
            is_otc = '(OTC)' in display_name or '_otc' in str(asset_code).lower()
            
            # Categorize
            asset_upper = str(asset_code).upper()
            display_upper = display_name.upper()
            
            category = "Currency"
            
            if any(x in asset_upper or x in display_upper for x in ['BTC', 'ETH', 'LTC', 'XRP', 'DOGE', 'ADA', 'DOT', 'LINK', 'UNI', 'SOL', 'MATIC', 'SHIB', 'AVAX', 'ATOM', 'CHAIN', 'TON', 'APT', 'COSMOS']):
                category = "Crypto"
            elif any(x in asset_upper or x in display_upper for x in ['GOLD', 'SILVER', 'OIL', 'GAS', 'CRUDE', 'BRENT', 'COPPER', 'PLATINUM', 'NATURAL']):
                category = "Commodities"
            elif any(x in asset_upper or x in display_upper for x in ['AAPL', 'GOOGL', 'GOOGLE', 'TSLA', 'TESLA', 'MSFT', 'MICROSOFT', 'AMZN', 'AMAZON', 'META', 'FACEBOOK', 'NFLX', 'NETFLIX', 'NVDA', 'NVIDIA', 'AMD', 'INTEL', 'COCA', 'MCDONALDS', 'MCD', 'NIKE', 'DISNEY']):
                category = "Stocks"
            
            pairs.append({
                "code": str(asset_code),  # This is the REAL asset code from get_all_assets()
                "name": display_name,      # This is the display name from payment data
                "payout": payout,
                "is_open": is_open,
                "is_otc": is_otc,
                "category": category
            })
        
        # Sort by payout (highest first)
        pairs.sort(key=lambda x: x['payout'], reverse=True)
        
        cached_pairs = pairs
        last_cache_time = time.time()
        
        print(f"✅ Loaded {len(pairs)} pairs")
        return jsonify({"pairs": pairs})
    
    except Exception as e:
        print(f"❌ Error getting pairs: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze/<path:asset_identifier>', methods=['GET'])
async def analyze_asset(asset_identifier):
    """Get complete analysis for asset - handles both display name and asset code"""
    if not is_connected or not analyzer:
        return jsonify({"error": "System offline"}), 503
    
    try:
        print(f"Analyzing {asset_identifier}...")
        
        # Try to find the actual asset code from display name
        asset_code = asset_identifier
        
        # Check if it's a display name (contains spaces or special chars)
        if ' ' in asset_identifier or '(' in asset_identifier:
            # Search in cached pairs
            for pair in cached_pairs:
                if pair['name'] == asset_identifier:
                    asset_code = pair['code']
                    print(f"Mapped '{asset_identifier}' → '{asset_code}'")
                    break
        
        analysis = await analyzer.get_comprehensive_analysis(asset_code)
        
        if "error" in analysis:
            return jsonify({"error": analysis["error"]}), 400
        
        print(f"✅ Analysis complete")
        return jsonify(analysis)
    
    except Exception as e:
        print(f"❌ Analysis error: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("💎 PREMIUM SIGNAL GENERATOR")
    print("=" * 60)
    print("📊 Admin Panel: http://localhost:5000/admin")
    print("👤 User Dashboard: http://localhost:5000/")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
