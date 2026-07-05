# ===========================================
# FILE: NaSiir Aliiw_xd.py
# ===========================================

import random
import string
import json
import time
import requests
import uuid
import base64
import io
import struct
import sys
import os  # <-- IMPORTANT: Add os import
from flask import Flask, render_template_string, request, jsonify, session
import threading

# Crypto libraries check
try:
    from Crypto.Cipher import AES, PKCS1_v1_5
    from Crypto.PublicKey import RSA
    from Crypto.Random import get_random_bytes
except ImportError:
    print("Error: 'pycryptodome' module not found.")
    print("Run: pip install pycryptodome")
    sys.exit()

# ===========================================
# ORIGINAL CLASSES (UNCHANGED)
# ===========================================

class FacebookPasswordEncryptor:
    @staticmethod
    def get_public_key():
        try:
            url = 'https://b-graph.facebook.com/pwd_key_fetch'
            params = {
                'version': '2',
                'flow': 'CONTROLLER_INITIALIZATION',
                'method': 'GET',
                'fb_api_req_friendly_name': 'pwdKeyFetch',
                'fb_api_caller_class': 'com.facebook.auth.login.AuthOperations',
                'access_token': '438142079694454|fc0a7caa49b192f64f6f5a6d9643bb28'
            }
            response = requests.post(url, params=params).json()
            return response.get('public_key'), str(response.get('key_id', '25'))
        except Exception as e:
            raise Exception(f"Public key fetch error: {e}")

    @staticmethod
    def encrypt(password, public_key=None, key_id="25"):
        if public_key is None:
            public_key, key_id = FacebookPasswordEncryptor.get_public_key()

        try:
            rand_key = get_random_bytes(32)
            iv = get_random_bytes(12)
            
            pubkey = RSA.import_key(public_key)
            cipher_rsa = PKCS1_v1_5.new(pubkey)
            encrypted_rand_key = cipher_rsa.encrypt(rand_key)
            
            cipher_aes = AES.new(rand_key, AES.MODE_GCM, nonce=iv)
            current_time = int(time.time())
            cipher_aes.update(str(current_time).encode("utf-8"))
            encrypted_passwd, auth_tag = cipher_aes.encrypt_and_digest(password.encode("utf-8"))
            
            buf = io.BytesIO()
            buf.write(bytes([1, int(key_id)]))
            buf.write(iv)
            buf.write(struct.pack("<h", len(encrypted_rand_key)))
            buf.write(encrypted_rand_key)
            buf.write(auth_tag)
            buf.write(encrypted_passwd)
            
            encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
            return f"#PWD_FB4A:2:{current_time}:{encoded}"
        except Exception as e:
            raise Exception(f"Encryption error: {e}")


class FacebookAppTokens:
    APPS = {
        'FB_ANDROID': {'name': 'Facebook For Android', 'app_id': '350685531728'},
        'MESSENGER_ANDROID': {'name': 'Facebook Messenger For Android', 'app_id': '256002347743983'},
        'FB_LITE': {'name': 'Facebook For Lite', 'app_id': '275254692598279'},
        'MESSENGER_LITE': {'name': 'Facebook Messenger For Lite', 'app_id': '200424423651082'},
        'ADS_MANAGER_ANDROID': {'name': 'Ads Manager App For Android', 'app_id': '438142079694454'},
        'PAGES_MANAGER_ANDROID': {'name': 'Pages Manager For Android', 'app_id': '121876164619130'}
    }
    
    @staticmethod
    def get_app_id(app_key):
        app = FacebookAppTokens.APPS.get(app_key)
        return app['app_id'] if app else None
    
    @staticmethod
    def get_all_app_keys():
        return list(FacebookAppTokens.APPS.keys())
    
    @staticmethod
    def extract_token_prefix(token):
        for i, char in enumerate(token):
            if char.islower():
                return token[:i]
        return token


class FacebookLogin:
    API_URL = "https://b-graph.facebook.com/auth/login"
    ACCESS_TOKEN = "350685531728|62f8ce9f74b12f84c123cc23437a4a32"
    API_KEY = "882a8490361da98702bf97a021ddc14d"
    SIG = "214049b9f17c38bd767de53752b53946"
    
    BASE_HEADERS = {
        "content-type": "application/x-www-form-urlencoded",
        "x-fb-net-hni": "45201",
        "zero-rated": "0",
        "x-fb-sim-hni": "45201",
        "x-fb-connection-quality": "EXCELLENT",
        "x-fb-friendly-name": "authenticate",
        "x-fb-connection-bandwidth": "78032897",
        "x-tigon-is-retry": "False",
        "authorization": "OAuth null",
        "x-fb-connection-type": "WIFI",
        "x-fb-device-group": "3342",
        "priority": "u=3,i",
        "x-fb-http-engine": "Liger",
        "x-fb-client-ip": "True",
        "x-fb-server-cluster": "True"
    }
    
    def __init__(self, uid_phone_mail, password, machine_id=None, convert_token_to=None, convert_all_tokens=False):
        self.uid_phone_mail = uid_phone_mail
        
        if password.startswith("#PWD_FB4A"):
            self.password = password
        else:
            self.password = FacebookPasswordEncryptor.encrypt(password)
        
        if convert_all_tokens:
            self.convert_token_to = FacebookAppTokens.get_all_app_keys()
        elif convert_token_to:
            self.convert_token_to = convert_token_to if isinstance(convert_token_to, list) else [convert_token_to]
        else:
            self.convert_token_to = []
        
        self.session = requests.Session()
        
        self.device_id = str(uuid.uuid4())
        self.adid = str(uuid.uuid4())
        self.secure_family_device_id = str(uuid.uuid4())
        self.machine_id = machine_id if machine_id else self._generate_machine_id()
        self.jazoest = ''.join(random.choices(string.digits, k=5))
        self.sim_serial = ''.join(random.choices(string.digits, k=20))
        
        self.headers = self._build_headers()
        self.data = self._build_data()
    
    @staticmethod
    def _generate_machine_id():
        return ''.join(random.choices(string.ascii_letters + string.digits, k=24))
    
    def _build_headers(self):
        headers = self.BASE_HEADERS.copy()
        headers.update({
            "x-fb-request-analytics-tags": '{"network_tags":{"product":"350685531728","retry_attempt":"0"},"application_tags":"unknown"}',
            "user-agent": "Dalvik/2.1.0 (Linux; U; Android 9; 23113RKC6C Build/PQ3A.190705.08211809) [FBAN/FB4A;FBAV/417.0.0.33.65;FBPN/com.facebook.katana;FBLC/vi_VN;FBBV/480086274;FBCR/MobiFone;FBMF/Redmi;FBBD/Redmi;FBDV/23113RKC6C;FBSV/9;FBCA/x86:armeabi-v7a;FBDM/{density=1.5,width=1280,height=720};FB_FW/1;FBRV/0;]"
        })
        return headers
    
    def _build_data(self):
        base_data = {
            "format": "json",
            "email": self.uid_phone_mail,
            "password": self.password,
            "credentials_type": "password",
            "generate_session_cookies": "1",
            "locale": "vi_VN",
            "client_country_code": "VN",
            "api_key": self.API_KEY,
            "access_token": self.ACCESS_TOKEN
        }
        
        base_data.update({
            "adid": self.adid,
            "device_id": self.device_id,
            "generate_analytics_claim": "1",
            "community_id": "",
            "linked_guest_account_userid": "",
            "cpl": "true",
            "try_num": "1",
            "family_device_id": self.device_id,
            "secure_family_device_id": self.secure_family_device_id,
            "sim_serials": f'["{self.sim_serial}"]',
            "openid_flow": "android_login",
            "openid_provider": "google",
            "openid_tokens": "[]",
            "account_switcher_uids": f'["{self.uid_phone_mail}"]',
            "fb4a_shared_phone_cpl_experiment": "fb4a_shared_phone_nonce_cpl_at_risk_v3",
            "fb4a_shared_phone_cpl_group": "enable_v3_at_risk",
            "enroll_misauth": "false",
            "error_detail_type": "button_with_disabled",
            "source": "login",
            "machine_id": self.machine_id,
            "jazoest": self.jazoest,
            "meta_inf_fbmeta": "V2_UNTAGGED",
            "advertiser_id": self.adid,
            "encrypted_msisdn": "",
            "currently_logged_in_userid": "0",
            "fb_api_req_friendly_name": "authenticate",
            "fb_api_caller_class": "Fb4aAuthHandler",
            "sig": self.SIG
        })
        
        return base_data
    
    def _convert_token(self, access_token, target_app):
        try:
            app_id = FacebookAppTokens.get_app_id(target_app)
            if not app_id:
                return None
            
            response = requests.post(
                'https://api.facebook.com/method/auth.getSessionforApp',
                data={
                    'access_token': access_token,
                    'format': 'json',
                    'new_app_id': app_id,
                    'generate_session_cookies': '1'
                }
            )
            
            result = response.json()
            
            if 'access_token' in result:
                token = result['access_token']
                prefix = FacebookAppTokens.extract_token_prefix(token)
                
                cookies_dict = {}
                cookies_string = ""
                
                if 'session_cookies' in result:
                    for cookie in result['session_cookies']:
                        cookies_dict[cookie['name']] = cookie['value']
                        cookies_string += f"{cookie['name']}={cookie['value']}; "
                
                return {
                    'token_prefix': prefix,
                    'access_token': token,
                    'cookies': {
                        'dict': cookies_dict,
                        'string': cookies_string.rstrip('; ')
                    }
                }
            return None     
        except:
            return None
    
    def _parse_success_response(self, response_json):
        original_token = response_json.get('access_token')
        original_prefix = FacebookAppTokens.extract_token_prefix(original_token)
        
        result = {
            'success': True,
            'original_token': {
                'token_prefix': original_prefix,
                'access_token': original_token
            },
            'cookies': {}
        }
        
        if 'session_cookies' in response_json:
            cookies_dict = {}
            cookies_string = ""
            for cookie in response_json['session_cookies']:
                cookies_dict[cookie['name']] = cookie['value']
                cookies_string += f"{cookie['name']}={cookie['value']}; "
            result['cookies'] = {
                'dict': cookies_dict,
                'string': cookies_string.rstrip('; ')
            }
        
        if self.convert_token_to:
            result['converted_tokens'] = {}
            for target_app in self.convert_token_to:
                converted = self._convert_token(original_token, target_app)
                if converted:
                    result['converted_tokens'][target_app] = converted
        
        return result
    
    def _handle_2fa_manual(self, error_data):
        return {
            'requires_2fa': True,
            'login_first_factor': error_data['login_first_factor'],
            'uid': error_data['uid']
        }
    
    def login(self):
        try:
            response = self.session.post(self.API_URL, headers=self.headers, data=self.data)
            response_json = response.json()
            
            if 'access_token' in response_json:
                return self._parse_success_response(response_json)
            
            if 'error' in response_json:
                error_data = response_json.get('error', {}).get('error_data', {})
                
                # Check for 2FA requirement
                if 'login_first_factor' in error_data and 'uid' in error_data:
                    return self._handle_2fa_manual(error_data)
                
                return {
                    'success': False,
                    'error': response_json['error'].get('message', 'Unknown error'),
                    'error_user_msg': response_json['error'].get('error_user_msg')
                }
            
            return {'success': False, 'error': 'Unknown response format'}
            
        except json.JSONDecodeError:
            return {'success': False, 'error': 'Invalid JSON response'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

# ===========================================
# FLASK APPLICATION
# ===========================================

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'NaSiir Aliiw_xd_secret_key_2024')
login_sessions = {}

# HTML Template with CSS and JavaScript - NaSiir Aliiw XD Theme
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NaSiir Aliiw - Facebook Login Tool</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Rajdhani', 'Segoe UI', system-ui, sans-serif;
        }

        :root {
            --neon-cyan: #00f0ff;
            --neon-pink: #ff00e6;
            --neon-purple: #8b00ff;
            --neon-green: #00ff88;
            --dark-bg: #0a0a0f;
            --card-bg: rgba(10, 10, 20, 0.8);
            --glass-bg: rgba(255, 255, 255, 0.05);
            --text-primary: #ffffff;
            --text-secondary: #a0a0b8;
            --accent: #00f0ff;
            --success: #00ff88;
            --danger: #ff0055;
            --warning: #ffaa00;
        }

        body {
            background-color: var(--dark-bg);
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(0, 240, 255, 0.08) 0%, transparent 60%),
                radial-gradient(circle at 90% 80%, rgba(255, 0, 230, 0.08) 0%, transparent 60%),
                radial-gradient(circle at 50% 50%, rgba(139, 0, 255, 0.05) 0%, transparent 80%);
            min-height: 100vh;
            color: var(--text-primary);
            overflow-x: hidden;
            position: relative;
        }

        /* Cyberpunk Grid Background */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                linear-gradient(90deg, rgba(0, 240, 255, 0.02) 1px, transparent 1px),
                linear-gradient(rgba(0, 240, 255, 0.02) 1px, transparent 1px);
            background-size: 60px 60px;
            pointer-events: none;
            z-index: 0;
        }

        /* Glowing Orb Particles */
        .particles {
            position: fixed;
            width: 100%;
            height: 100%;
            z-index: 0;
            pointer-events: none;
        }

        .particle {
            position: absolute;
            border-radius: 50%;
            animation: floatParticle 25s infinite linear;
            opacity: 0.15;
            filter: blur(2px);
        }

        @keyframes floatParticle {
            0%, 100% { transform: translateY(0) translateX(0) scale(1); }
            25% { transform: translateY(-80px) translateX(30px) scale(1.2); }
            50% { transform: translateY(40px) translateX(-20px) scale(0.8); }
            75% { transform: translateY(-40px) translateX(50px) scale(1.1); }
        }

        /* Scanline Effect */
        body::after {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: repeating-linear-gradient(
                0deg,
                transparent 0px,
                transparent 3px,
                rgba(0, 240, 255, 0.02) 3px,
                rgba(0, 240, 255, 0.02) 4px
            );
            pointer-events: none;
            z-index: 1;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            min-height: 100vh;
            align-items: center;
            position: relative;
            z-index: 2;
        }

        @media (max-width: 768px) {
            .container {
                grid-template-columns: 1fr;
                gap: 30px;
                padding: 15px;
            }
        }

        /* ===== HERO SECTION - CYBERPUNK STYLE ===== */
        .hero-section {
            text-align: center;
            padding: 50px 40px;
            background: var(--card-bg);
            backdrop-filter: blur(30px);
            border-radius: 30px;
            border: 1px solid rgba(0, 240, 255, 0.2);
            box-shadow: 
                0 0 60px rgba(0, 240, 255, 0.05),
                inset 0 0 60px rgba(0, 240, 255, 0.03);
            position: relative;
            overflow: hidden;
            transition: all 0.5s ease;
        }

        .hero-section:hover {
            border-color: rgba(0, 240, 255, 0.4);
            box-shadow: 
                0 0 80px rgba(0, 240, 255, 0.08),
                inset 0 0 80px rgba(0, 240, 255, 0.05);
        }

        /* Animated Border Glow */
        .hero-section::before {
            content: '';
            position: absolute;
            top: -2px;
            left: -2px;
            right: -2px;
            bottom: -2px;
            background: linear-gradient(45deg, 
                var(--neon-cyan), 
                var(--neon-purple), 
                var(--neon-pink), 
                var(--neon-cyan));
            background-size: 400% 400%;
            border-radius: 32px;
            z-index: -1;
            animation: borderGlow 4s ease-in-out infinite;
            opacity: 0.5;
        }

        @keyframes borderGlow {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
        }

        .hero-section .logo {
            font-size: 5rem;
            position: relative;
            display: inline-block;
            margin-bottom: 15px;
        }

        .hero-section .logo i {
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-pink));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: none;
            filter: drop-shadow(0 0 40px rgba(0, 240, 255, 0.3));
            animation: logoPulse 3s ease-in-out infinite;
        }

        @keyframes logoPulse {
            0%, 100% { filter: drop-shadow(0 0 40px rgba(0, 240, 255, 0.3)); }
            50% { filter: drop-shadow(0 0 80px rgba(255, 0, 230, 0.4)) drop-shadow(0 0 120px rgba(0, 240, 255, 0.2)); }
        }

        .hero-section .title {
            font-family: 'Orbitron', monospace;
            font-size: 3.2rem;
            font-weight: 900;
            letter-spacing: 4px;
            text-transform: uppercase;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-pink), var(--neon-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
            text-shadow: none;
            position: relative;
        }

        .hero-section .title .xd {
            background: linear-gradient(135deg, var(--neon-pink), var(--neon-cyan));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: xdPulse 1.5s ease-in-out infinite;
        }

        @keyframes xdPulse {
            0%, 100% { filter: drop-shadow(0 0 20px rgba(255, 0, 230, 0.3)); }
            50% { filter: drop-shadow(0 0 40px rgba(0, 240, 255, 0.5)) drop-shadow(0 0 60px rgba(255, 0, 230, 0.3)); }
        }

        .hero-section .subtitle {
            font-size: 1.1rem;
            color: var(--text-secondary);
            margin-bottom: 30px;
            line-height: 1.8;
            letter-spacing: 1px;
            font-weight: 400;
        }

        .hero-section .subtitle span {
            color: var(--neon-cyan);
            font-weight: 600;
        }

        /* Glitch Text Effect for Status */
        .glitch-text {
            font-family: 'Orbitron', monospace;
            font-size: 0.8rem;
            color: var(--neon-cyan);
            letter-spacing: 2px;
            opacity: 0.6;
            margin-top: 10px;
            animation: glitchText 3s infinite;
        }

        @keyframes glitchText {
            0%, 90%, 100% { opacity: 0.6; }
            92% { opacity: 0.2; transform: translateX(-2px); }
            94% { opacity: 0.8; transform: translateX(2px); }
            96% { opacity: 0.3; transform: translateX(-1px); }
        }

        .features {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 30px;
        }

        .feature {
            background: rgba(0, 240, 255, 0.03);
            padding: 18px 15px;
            border-radius: 16px;
            border: 1px solid rgba(0, 240, 255, 0.08);
            transition: all 0.4s ease;
            position: relative;
            overflow: hidden;
        }

        .feature::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 240, 255, 0.05), transparent);
            transition: left 0.6s ease;
        }

        .feature:hover::before {
            left: 100%;
        }

        .feature:hover {
            transform: translateY(-5px) scale(1.02);
            border-color: var(--neon-cyan);
            box-shadow: 0 10px 40px rgba(0, 240, 255, 0.1);
        }

        .feature i {
            font-size: 1.8rem;
            margin-bottom: 8px;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .feature h3 {
            font-size: 0.9rem;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: var(--text-primary);
            margin-bottom: 3px;
        }

        .feature p {
            font-size: 0.75rem;
            color: var(--text-secondary);
            line-height: 1.4;
        }

        /* ===== LOGIN FORM - CYBERPUNK STYLE ===== */
        .login-form {
            background: var(--card-bg);
            backdrop-filter: blur(30px);
            padding: 45px 40px;
            border-radius: 30px;
            border: 1px solid rgba(255, 0, 230, 0.15);
            box-shadow: 
                0 0 60px rgba(255, 0, 230, 0.05),
                inset 0 0 60px rgba(255, 0, 230, 0.03);
            position: relative;
            overflow: hidden;
            transition: all 0.5s ease;
        }

        .login-form:hover {
            border-color: rgba(255, 0, 230, 0.3);
            box-shadow: 
                0 0 80px rgba(255, 0, 230, 0.08),
                inset 0 0 80px rgba(255, 0, 230, 0.05);
        }

        /* Corner Accents */
        .login-form .corner {
            position: absolute;
            width: 30px;
            height: 30px;
            border-color: var(--neon-cyan);
            border-style: solid;
            border-width: 0;
            opacity: 0.3;
        }

        .login-form .corner.tl { top: 10px; left: 10px; border-top-width: 2px; border-left-width: 2px; }
        .login-form .corner.tr { top: 10px; right: 10px; border-top-width: 2px; border-right-width: 2px; }
        .login-form .corner.bl { bottom: 10px; left: 10px; border-bottom-width: 2px; border-left-width: 2px; }
        .login-form .corner.br { bottom: 10px; right: 10px; border-bottom-width: 2px; border-right-width: 2px; }

        .form-title {
            font-family: 'Orbitron', monospace;
            font-size: 1.6rem;
            font-weight: 700;
            margin-bottom: 30px;
            color: var(--text-primary);
            text-align: center;
            letter-spacing: 2px;
            text-transform: uppercase;
            position: relative;
            padding-bottom: 15px;
        }

        .form-title::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 120px;
            height: 2px;
            background: linear-gradient(90deg, var(--neon-cyan), var(--neon-pink), var(--neon-purple));
            border-radius: 2px;
            box-shadow: 0 0 30px rgba(0, 240, 255, 0.3);
        }

        .form-title .highlight {
            background: linear-gradient(135deg, var(--neon-pink), var(--neon-cyan));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .form-group {
            position: relative;
            margin-bottom: 30px;
        }

        .form-group input {
            width: 100%;
            padding: 16px 20px 16px 50px;
            background: rgba(255, 255, 255, 0.03);
            border: 2px solid rgba(255, 255, 255, 0.06);
            border-radius: 14px;
            color: var(--text-primary);
            font-size: 1rem;
            transition: all 0.4s ease;
            font-weight: 400;
            letter-spacing: 0.5px;
        }

        .form-group input:focus {
            outline: none;
            border-color: var(--neon-cyan);
            background: rgba(0, 240, 255, 0.05);
            box-shadow: 0 0 30px rgba(0, 240, 255, 0.05), inset 0 0 30px rgba(0, 240, 255, 0.03);
        }

        .form-group input::placeholder {
            color: var(--text-secondary);
            opacity: 0.5;
        }

        .form-group .input-icon {
            position: absolute;
            left: 18px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-secondary);
            font-size: 1.1rem;
            transition: all 0.3s ease;
        }

        .form-group input:focus + .input-icon {
            color: var(--neon-cyan);
        }

        .form-group .input-icon.active {
            color: var(--neon-cyan);
        }

        .toggle-password {
            position: absolute;
            right: 18px;
            top: 50%;
            transform: translateY(-50%);
            cursor: pointer;
            color: var(--text-secondary);
            transition: all 0.3s ease;
            z-index: 5;
        }

        .toggle-password:hover {
            color: var(--neon-cyan);
        }

        .btn {
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, var(--neon-cyan), var(--neon-purple));
            color: var(--dark-bg);
            border: none;
            border-radius: 14px;
            font-size: 1.1rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.4s ease;
            text-transform: uppercase;
            letter-spacing: 2px;
            position: relative;
            overflow: hidden;
            font-family: 'Orbitron', monospace;
        }

        .btn:hover {
            transform: translateY(-3px) scale(1.01);
            box-shadow: 0 15px 50px rgba(0, 240, 255, 0.3);
        }

        .btn:active {
            transform: translateY(0) scale(0.99);
        }

        .btn::after {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(
                45deg,
                transparent 40%,
                rgba(255, 255, 255, 0.15) 50%,
                transparent 60%
            );
            animation: btnShimmer 4s infinite;
        }

        @keyframes btnShimmer {
            0% { transform: translateX(-100%) rotate(45deg); }
            100% { transform: translateX(100%) rotate(45deg); }
        }

        .btn .btn-text {
            position: relative;
            z-index: 2;
        }

        .btn .btn-loading {
            display: none;
            position: relative;
            z-index: 2;
        }

        .loading-spinner {
            display: inline-block;
            width: 22px;
            height: 22px;
            border: 3px solid rgba(10, 10, 15, 0.2);
            border-radius: 50%;
            border-top-color: var(--dark-bg);
            animation: spin 0.8s ease-in-out infinite;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        /* ===== RESULTS SECTION ===== */
        .results-section {
            display: none;
            margin-top: 30px;
            padding: 25px;
            background: rgba(0, 240, 255, 0.05);
            border-radius: 20px;
            border: 1px solid rgba(0, 240, 255, 0.15);
            animation: fadeIn 0.6s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(30px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .results-section .result-title {
            font-family: 'Orbitron', monospace;
            font-size: 1.2rem;
            color: var(--success);
            margin-bottom: 20px;
            text-align: center;
            letter-spacing: 1px;
        }

        .results-section .result-title i {
            margin-right: 10px;
        }

        .token-box {
            background: rgba(0, 0, 0, 0.4);
            padding: 15px 18px;
            border-radius: 14px;
            margin: 10px 0;
            word-break: break-all;
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
            border: 1px solid rgba(0, 240, 255, 0.08);
            transition: all 0.4s ease;
            position: relative;
        }

        .token-box:hover {
            border-color: var(--neon-cyan);
            box-shadow: 0 0 30px rgba(0, 240, 255, 0.05);
        }

        .token-box .token-title {
            font-family: 'Rajdhani', sans-serif;
            font-weight: 700;
            color: var(--neon-cyan);
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .token-box .token-title i {
            font-size: 1rem;
        }

        .token-box .token-value {
            color: var(--text-secondary);
            font-size: 0.8rem;
            line-height: 1.6;
            word-break: break-all;
        }

        .token-box .token-value.highlight {
            color: var(--neon-green);
        }

        .copy-btn {
            background: rgba(0, 240, 255, 0.1);
            border: 1px solid rgba(0, 240, 255, 0.15);
            color: var(--neon-cyan);
            padding: 4px 14px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-left: auto;
        }

        .copy-btn:hover {
            background: var(--neon-cyan);
            color: var(--dark-bg);
            box-shadow: 0 0 30px rgba(0, 240, 255, 0.2);
        }

        /* ===== ALERT ===== */
        .alert {
            padding: 14px 20px;
            border-radius: 14px;
            margin: 20px 0;
            display: none;
            animation: slideIn 0.4s ease;
            font-weight: 500;
            letter-spacing: 0.5px;
        }

        @keyframes slideIn {
            from { transform: translateX(-20px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }

        .alert-success {
            background: rgba(0, 255, 136, 0.12);
            border: 1px solid rgba(0, 255, 136, 0.2);
            color: var(--success);
        }

        .alert-error {
            background: rgba(255, 0, 85, 0.12);
            border: 1px solid rgba(255, 0, 85, 0.2);
            color: var(--danger);
        }

        .alert-warning {
            background: rgba(255, 170, 0, 0.12);
            border: 1px solid rgba(255, 170, 0, 0.2);
            color: var(--warning);
        }

        /* ===== 2FA MODAL ===== */
        .twofa-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(10, 10, 15, 0.95);
            backdrop-filter: blur(20px);
            z-index: 1000;
            align-items: center;
            justify-content: center;
            animation: modalFade 0.3s ease;
        }

        @keyframes modalFade {
            from { opacity: 0; }
            to { opacity: 1; }
        }

        .twofa-content {
            background: var(--card-bg);
            backdrop-filter: blur(30px);
            padding: 45px 40px;
            border-radius: 30px;
            border: 1px solid rgba(255, 170, 0, 0.2);
            box-shadow: 0 30px 100px rgba(0, 0, 0, 0.6), 0 0 60px rgba(255, 170, 0, 0.05);
            max-width: 500px;
            width: 90%;
            animation: modalIn 0.5s ease;
            position: relative;
            overflow: hidden;
        }

        .twofa-content::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(45deg, rgba(255, 170, 0, 0.03), transparent);
            animation: rotateBg 20s linear infinite;
        }

        @keyframes rotateBg {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        @keyframes modalIn {
            from { opacity: 0; transform: scale(0.8) translateY(-30px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
        }

        .twofa-content h2 {
            font-family: 'Orbitron', monospace;
            font-size: 1.3rem;
            color: var(--warning);
            margin-bottom: 15px;
            text-align: center;
            letter-spacing: 1px;
            text-transform: uppercase;
            position: relative;
            z-index: 2;
        }

        .twofa-content h2 i {
            margin-right: 10px;
        }

        .twofa-content p {
            color: var(--text-secondary);
            margin-bottom: 25px;
            text-align: center;
            line-height: 1.6;
            position: relative;
            z-index: 2;
        }

        .twofa-content .form-group {
            position: relative;
            z-index: 2;
        }

        .twofa-content .form-group input {
            text-align: center;
            font-size: 1.8rem;
            letter-spacing: 12px;
            padding: 18px 20px;
            font-weight: 700;
            font-family: 'Orbitron', monospace;
        }

        .twofa-content .btn-group {
            display: flex;
            gap: 15px;
            margin-top: 30px;
            position: relative;
            z-index: 2;
        }

        .twofa-content .btn-group .btn {
            flex: 1;
            font-size: 0.9rem;
        }

        .twofa-content .btn-group .btn-cancel {
            background: rgba(255, 0, 85, 0.15);
            color: var(--danger);
            border: 1px solid rgba(255, 0, 85, 0.2);
        }

        .twofa-content .btn-group .btn-cancel:hover {
            background: rgba(255, 0, 85, 0.25);
            box-shadow: 0 10px 40px rgba(255, 0, 85, 0.15);
        }

        /* ===== STATUS BAR ===== */
        .status-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            padding: 8px 20px;
            background: rgba(10, 10, 15, 0.9);
            backdrop-filter: blur(10px);
            border-top: 1px solid rgba(0, 240, 255, 0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.7rem;
            color: var(--text-secondary);
            z-index: 999;
            font-family: 'Orbitron', monospace;
            letter-spacing: 1px;
        }

        .status-bar .status-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--neon-green);
            margin-right: 8px;
            animation: dotPulse 2s infinite;
        }

        @keyframes dotPulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }

        .status-bar .status-right {
            display: flex;
            gap: 20px;
            align-items: center;
        }

        .status-bar .status-right span {
            opacity: 0.5;
        }

        /* Responsive tweaks */
        @media (max-width: 768px) {
            .hero-section .title {
                font-size: 2.2rem;
            }
            .hero-section .logo {
                font-size: 3.5rem;
            }
            .hero-section {
                padding: 30px 20px;
            }
            .login-form {
                padding: 30px 20px;
            }
            .features {
                grid-template-columns: 1fr 1fr;
                gap: 10px;
            }
            .feature {
                padding: 12px 10px;
            }
            .feature i {
                font-size: 1.3rem;
            }
            .feature h3 {
                font-size: 0.75rem;
            }
            .feature p {
                font-size: 0.65rem;
            }
            .form-title {
                font-size: 1.2rem;
            }
            .twofa-content {
                padding: 30px 20px;
            }
            .status-bar {
                font-size: 0.6rem;
                padding: 5px 15px;
                flex-wrap: wrap;
                gap: 5px;
            }
        }
    </style>
</head>
<body>
    <!-- Animated Particles Background -->
    <div class="particles" id="particles"></div>

    <div class="container">
        <!-- Hero Section -->
        <div class="hero-section">
            <div class="logo">
                <i class="fas fa-robot"></i>
            </div>
            <h1 class="title">NaSiir Aliiw <span class="xd">XD</span></h1>
            <p class="subtitle">
                <span>✦</span> Advanced Facebook Authentication <span>✦</span><br>
                <span style="font-size: 0.9rem; opacity: 0.7;">Cyberpunk Edition · Token Conversion · 2FA Support</span>
            </p>
            <div class="glitch-text">>> SYSTEM ONLINE <<</div>
            
            <div class="features">
                <div class="feature">
                    <i class="fas fa-shield-halved"></i>
                    <h3>Secure Login</h3>
                    <p>Military-grade encryption</p>
                </div>
                <div class="feature">
                    <i class="fas fa-arrows-rotate"></i>
                    <h3>Token Convert</h3>
                    <p>All Facebook apps</p>
                </div>
                <div class="feature">
                    <i class="fas fa-mobile-screen-button"></i>
                    <h3>2FA Support</h3>
                    <p>OTP verification</p>
                </div>
                <div class="feature">
                    <i class="fas fa-bolt"></i>
                    <h3>High Speed</h3>
                    <p>Fast & reliable</p>
                </div>
            </div>
        </div>

        <!-- Login Form -->
        <div class="login-form">
            <div class="corner tl"></div>
            <div class="corner tr"></div>
            <div class="corner bl"></div>
            <div class="corner br"></div>
            
            <h2 class="form-title"><span class="highlight">✦</span> Access <span class="highlight">System</span></h2>
            
            <div class="alert" id="alert"></div>
            
            <form id="loginForm">
                <div class="form-group">
                    <input type="text" id="email" placeholder="Email / Phone Number" required>
                    <i class="fas fa-user input-icon" id="emailIcon"></i>
                </div>
                
                <div class="form-group">
                    <input type="password" id="password" placeholder="Password" required>
                    <i class="fas fa-lock input-icon" id="passIcon"></i>
                    <span class="toggle-password" onclick="togglePassword()">
                        <i class="fas fa-eye" id="eyeIcon"></i>
                    </span>
                </div>
                
                <button type="submit" class="btn" id="loginBtn">
                    <span class="btn-text" id="btnText"><i class="fas fa-key"></i> Authenticate</span>
                    <span class="btn-loading" id="btnLoading"><span class="loading-spinner"></span></span>
                </button>
            </form>

            <!-- Results Section -->
            <div class="results-section" id="results">
                <div class="result-title">
                    <i class="fas fa-check-circle"></i> ACCESS GRANTED
                </div>
                
                <div class="token-box" id="originalToken">
                    <div class="token-title">
                        <i class="fas fa-key"></i> Original Token
                        <button class="copy-btn" onclick="copyToken('originalTokenText')"><i class="fas fa-copy"></i> Copy</button>
                    </div>
                    <div class="token-value highlight" id="originalTokenText"></div>
                </div>
                
                <div class="token-box" id="cookies">
                    <div class="token-title">
                        <i class="fas fa-cookie-bite"></i> Session Cookies
                        <button class="copy-btn" onclick="copyToken('cookiesText')"><i class="fas fa-copy"></i> Copy</button>
                    </div>
                    <div class="token-value" id="cookiesText"></div>
                </div>
                
                <div id="convertedTokens"></div>
            </div>
        </div>
    </div>

    <!-- 2FA Modal -->
    <div class="twofa-modal" id="twofaModal">
        <div class="twofa-content">
            <h2><i class="fas fa-shield-halved"></i> 2FA Required</h2>
            <p>
                Facebook has sent an OTP to your WhatsApp/Mobile Number.<br>
                <span style="color: var(--warning); font-weight: 600;">Enter the code to continue</span>
            </p>
            
            <div class="form-group">
                <input type="text" id="otpCode" placeholder="• • • • • •" maxlength="6" inputmode="numeric" pattern="[0-9]*">
                <i class="fas fa-sms input-icon" style="left: 18px;"></i>
            </div>
            
            <div class="btn-group">
                <button class="btn" onclick="submitOTP()">
                    <i class="fas fa-check"></i> Verify
                </button>
                <button class="btn btn-cancel" onclick="close2FAModal()">
                    <i class="fas fa-times"></i> Cancel
                </button>
            </div>
        </div>
    </div>

    <!-- Status Bar -->
    <div class="status-bar">
        <div>
            <span class="status-dot"></span>
            <span id="statusText">SYSTEM READY</span>
        </div>
        <div class="status-right">
            <span id="clockDisplay">--:--:--</span>
            <span>|</span>
            <span>v2.0</span>
        </div>
    </div>

    <script>
        // ===========================================
        // PARTICLES GENERATOR
        // ===========================================
        function createParticles() {
            const container = document.getElementById('particles');
            const colors = ['#00f0ff', '#ff00e6', '#8b00ff', '#00ff88', '#ffaa00'];
            for (let i = 0; i < 40; i++) {
                const particle = document.createElement('div');
                particle.className = 'particle';
                const size = Math.random() * 8 + 2;
                particle.style.width = `${size}px`;
                particle.style.height = `${size}px`;
                particle.style.left = `${Math.random() * 100}%`;
                particle.style.top = `${Math.random() * 100}%`;
                particle.style.background = colors[Math.floor(Math.random() * colors.length)];
                particle.style.animationDelay = `${Math.random() * 25}s`;
                particle.style.animationDuration = `${20 + Math.random() * 20}s`;
                container.appendChild(particle);
            }
        }

        // ===========================================
        // CLOCK
        // ===========================================
        function updateClock() {
            const now = new Date();
            const time = now.toTimeString().split(' ')[0];
            document.getElementById('clockDisplay').textContent = time;
        }
        setInterval(updateClock, 1000);
        updateClock();

        // ===========================================
        // ALERT
        // ===========================================
        function showAlert(message, type = 'error') {
            const alert = document.getElementById('alert');
            alert.textContent = message;
            alert.className = `alert alert-${type}`;
            alert.style.display = 'block';
            setTimeout(() => {
                alert.style.display = 'none';
            }, 5000);
        }

        // ===========================================
        // TOGGLE PASSWORD
        // ===========================================
        function togglePassword() {
            const passwordInput = document.getElementById('password');
            const eyeIcon = document.getElementById('eyeIcon');
            if (passwordInput.type === 'password') {
                passwordInput.type = 'text';
                eyeIcon.className = 'fas fa-eye-slash';
            } else {
                passwordInput.type = 'password';
                eyeIcon.className = 'fas fa-eye';
            }
        }

        // ===========================================
        // COPY TOKEN
        // ===========================================
        function copyToken(elementId) {
            const text = document.getElementById(elementId).textContent;
            if (!text || text.trim() === '') {
                showAlert('Nothing to copy!', 'warning');
                return;
            }
            navigator.clipboard.writeText(text).then(() => {
                showAlert('✅ Copied to clipboard!', 'success');
            }).catch(() => {
                // Fallback
                const textarea = document.createElement('textarea');
                textarea.value = text;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                showAlert('✅ Copied to clipboard!', 'success');
            });
        }

        // ===========================================
        // 2FA MODAL
        // ===========================================
        let twofaData = null;

        function show2FAModal(data) {
            twofaData = data;
            document.getElementById('twofaModal').style.display = 'flex';
            document.getElementById('otpCode').value = '';
            setTimeout(() => {
                document.getElementById('otpCode').focus();
            }, 100);
            document.getElementById('statusText').textContent = 'AWAITING 2FA CODE';
        }

        function close2FAModal() {
            document.getElementById('twofaModal').style.display = 'none';
            twofaData = null;
            document.getElementById('statusText').textContent = 'SYSTEM READY';
        }

        // ===========================================
        // SUBMIT OTP
        // ===========================================
        function submitOTP() {
            const otpCode = document.getElementById('otpCode').value.trim();
            if (!otpCode || otpCode.length < 6) {
                showAlert('Please enter a valid 6-digit OTP code', 'error');
                return;
            }

            document.getElementById('loginBtn').disabled = true;
            document.getElementById('btnText').style.display = 'none';
            document.getElementById('btnLoading').style.display = 'inline-block';
            document.getElementById('statusText').textContent = 'VERIFYING 2FA...';

            fetch('/verify_2fa', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: twofaData.session_id,
                    otp_code: otpCode
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showResults(data);
                    close2FAModal();
                    document.getElementById('statusText').textContent = 'ACCESS GRANTED';
                } else {
                    showAlert('❌ ' + (data.error || 'OTP verification failed'), 'error');
                    document.getElementById('statusText').textContent = '2FA FAILED';
                }
            })
            .catch(error => {
                showAlert('⚠️ Network error: ' + error, 'error');
                document.getElementById('statusText').textContent = 'NETWORK ERROR';
            })
            .finally(() => {
                document.getElementById('loginBtn').disabled = false;
                document.getElementById('btnText').style.display = 'block';
                document.getElementById('btnLoading').style.display = 'none';
            });
        }

        // ===========================================
        // SHOW RESULTS
        // ===========================================
        function showResults(data) {
            document.getElementById('originalTokenText').textContent = data.original_token.access_token || 'N/A';
            
            document.getElementById('cookiesText').textContent = data.cookies.string || 'No cookies available';
            
            const convertedDiv = document.getElementById('convertedTokens');
            if (data.converted_tokens && Object.keys(data.converted_tokens).length > 0) {
                let html = '<div style="margin-top: 15px; border-top: 1px solid rgba(0,240,255,0.1); padding-top: 15px;">';
                html += '<div class="token-title" style="font-size: 0.9rem; color: var(--neon-purple); margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; font-weight: 700;"><i class="fas fa-exchange-alt"></i> Converted Tokens</div>';
                
                const appNames = {
                    'FB_ANDROID': 'Facebook Android',
                    'MESSENGER_ANDROID': 'Messenger Android',
                    'FB_LITE': 'Facebook Lite',
                    'MESSENGER_LITE': 'Messenger Lite',
                    'ADS_MANAGER_ANDROID': 'Ads Manager',
                    'PAGES_MANAGER_ANDROID': 'Pages Manager'
                };
                
                for (const [app, tokenData] of Object.entries(data.converted_tokens)) {
                    const name = appNames[app] || app;
                    const tokenId = 'token_' + app;
                    html += `
                        <div class="token-box" style="margin: 8px 0;">
                            <div class="token-title">
                                <i class="fas fa-mobile-alt"></i> ${name}
                                <button class="copy-btn" onclick="copyToken('${tokenId}')"><i class="fas fa-copy"></i> Copy</button>
                            </div>
                            <div class="token-value" id="${tokenId}">${tokenData.access_token || 'N/A'}</div>
                        </div>
                    `;
                }
                html += '</div>';
                convertedDiv.innerHTML = html;
            } else {
                convertedDiv.innerHTML = '';
            }
            
            document.getElementById('results').style.display = 'block';
            showAlert('✅ Access granted successfully!', 'success');
        }

        // ===========================================
        // FORM SUBMISSION
        // ===========================================
        document.getElementById('loginForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const email = document.getElementById('email').value.trim();
            const password = document.getElementById('password').value.trim();
            
            if (!email || !password) {
                showAlert('Please fill in all fields', 'error');
                return;
            }

            document.getElementById('loginBtn').disabled = true;
            document.getElementById('btnText').style.display = 'none';
            document.getElementById('btnLoading').style.display = 'inline-block';
            document.getElementById('statusText').textContent = 'AUTHENTICATING...';

            fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: email,
                    password: password
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showResults(data);
                    document.getElementById('statusText').textContent = 'AUTHENTICATED';
                } else if (data.requires_2fa) {
                    show2FAModal(data);
                    showAlert('🔐 2FA Required. Enter OTP code.', 'warning');
                } else {
                    showAlert('❌ ' + (data.error || 'Login failed'), 'error');
                    document.getElementById('statusText').textContent = 'AUTH FAILED';
                }
            })
            .catch(error => {
                showAlert('⚠️ Network error: ' + error, 'error');
                document.getElementById('statusText').textContent = 'NETWORK ERROR';
            })
            .finally(() => {
                document.getElementById('loginBtn').disabled = false;
                document.getElementById('btnText').style.display = 'block';
                document.getElementById('btnLoading').style.display = 'none';
            });
        });

        // ===========================================
        // ENTER KEY FOR OTP
        // ===========================================
        document.getElementById('otpCode').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                submitOTP();
            }
        });

        // ===========================================
        // CLOSE MODAL ON ESC
        // ===========================================
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                close2FAModal();
            }
        });

        // ===========================================
        // AUTO-FOCUS OTP
        // ===========================================
        document.getElementById('otpCode').addEventListener('input', function(e) {
            // Auto-advance? Not needed, but restrict to numbers
            this.value = this.value.replace(/\D/g, '');
        });

        // ===========================================
        // INIT
        // ===========================================
        document.addEventListener('DOMContentLoaded', function() {
            createParticles();
            document.getElementById('statusText').textContent = 'SYSTEM READY';
            
            // Animate input icons
            document.querySelectorAll('.form-group input').forEach(input => {
                input.addEventListener('focus', function() {
                    const icon = this.parentElement.querySelector('.input-icon');
                    if (icon) icon.style.color = '#00f0ff';
                });
                input.addEventListener('blur', function() {
                    const icon = this.parentElement.querySelector('.input-icon');
                    if (icon && !this.value) icon.style.color = '';
                });
            });
        });
    </script>
</body>
</html>
'''

# ===========================================
# FLASK ROUTES
# ===========================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password are required'})
        
        # Create login instance
        fb_login = FacebookLogin(
            uid_phone_mail=email,
            password=password,
            convert_all_tokens=True
        )
        
        # Perform login
        result = fb_login.login()
        
        # Store session if 2FA required
        if result.get('requires_2fa'):
            session_id = str(uuid.uuid4())
            login_sessions[session_id] = {
                'fb_login': fb_login,
                'data': result,
                'timestamp': time.time()
            }
            
            # Clean old sessions (older than 10 minutes)
            for sid in list(login_sessions.keys()):
                if time.time() - login_sessions[sid]['timestamp'] > 600:
                    del login_sessions[sid]
            
            result['session_id'] = session_id
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/verify_2fa', methods=['POST'])
def verify_2fa():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        otp_code = data.get('otp_code')
        
        if not session_id or not otp_code:
            return jsonify({'success': False, 'error': 'Session ID and OTP code are required'})
        
        if session_id not in login_sessions:
            return jsonify({'success': False, 'error': 'Session expired or invalid'})
        
        session_data = login_sessions[session_id]
        fb_login = session_data['fb_login']
        twofa_data = session_data['data']
        
        # Prepare 2FA data
        data_2fa = {
            'locale': 'vi_VN',
            'format': 'json',
            'email': fb_login.uid_phone_mail,
            'device_id': fb_login.device_id,
            'access_token': fb_login.ACCESS_TOKEN,
            'generate_session_cookies': 'true',
            'generate_machine_id': '1',
            'twofactor_code': otp_code,
            'credentials_type': 'two_factor',
            'error_detail_type': 'button_with_disabled',
            'first_factor': twofa_data['login_first_factor'],
            'password': fb_login.password,
            'userid': twofa_data['uid'],
            'machine_id': twofa_data['login_first_factor']
        }
        
        # Send 2FA request
        response = fb_login.session.post(fb_login.API_URL, data=data_2fa, headers=fb_login.headers)
        response_json = response.json()
        
        if 'access_token' in response_json:
            result = fb_login._parse_success_response(response_json)
            # Clean up session
            if session_id in login_sessions:
                del login_sessions[session_id]
            return jsonify(result)
        else:
            return jsonify({
                'success': False,
                'error': response_json.get('error', {}).get('message', 'OTP Verification Failed')
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def cleanup_sessions():
    """Periodically clean up old sessions"""
    while True:
        time.sleep(300)  # Run every 5 minutes
        current_time = time.time()
        for sid in list(login_sessions.keys()):
            if current_time - login_sessions[sid]['timestamp'] > 600:  # 10 minutes
                del login_sessions[sid]

# Start session cleanup thread
cleanup_thread = threading.Thread(target=cleanup_sessions, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    print("=" * 60)
    print("  NaSiir Aliiw - Facebook Login Tool")
    print("=" * 60)
    
    # Render compatible port configuration
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    print(f"\n🚀 Server running on http://{host}:{port}")
    print("⚡ Press Ctrl+C to stop\n")
    
    app.run(debug=True, host=host, port=port)