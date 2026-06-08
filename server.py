"""
server.py - Monte Villa Admin Server
=====================================
Local : python server.py
Deploy: gunicorn server:app
"""

import os
import json
import secrets
import gspread
from datetime import datetime
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from google.oauth2.service_account import Credentials
from google.oauth2 import service_account
from functools import wraps

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.environ.get('SECRET_KEY', 'monte-villa-secret-key-2026')

# ===== CORS (อนุญาต Netlify เรียก API) =====
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:8000')
CORS(app, supports_credentials=True, origins=[FRONTEND_URL, 'http://localhost:8000'])

# Session cookie ข้ามโดเมน
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE']   = True

# ===== Google Sheets Setup =====
SHEET_URL = 'https://docs.google.com/spreadsheets/d/1rC169tp5xl8zh3H8YBe-8Rz5qhiEpQDA6CLra5jFJPA/edit'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']

def get_sheet(sheet_name):
    # Render: อ่านจาก environment variable GOOGLE_CREDENTIALS (JSON string)
    # Local:  อ่านจากไฟล์ credentials.json
    creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    if creds_json:
        info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds_file = os.path.join(os.path.dirname(__file__), 'credentials.json')
        creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_url(SHEET_URL).worksheet(sheet_name)

# ===== Auth Decorator =====
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# ===== Static Files =====
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('.', filename)

# ===== Auth API =====
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = str(data.get('password', '')).strip()
    try:
        ws = get_sheet('login')
        records = ws.get_all_records()
        for row in records:
            if str(row.get('name', '')).strip() == username and \
               str(row.get('pass', '')).strip() == password:
                session['logged_in'] = True
                session['username'] = username
                return jsonify({'success': True, 'username': username})
        return jsonify({'success': False, 'message': 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    return jsonify({
        'logged_in': session.get('logged_in', False),
        'username': session.get('username', '')
    })

# ===== Homes API (pool-villa) =====
@app.route('/api/homes', methods=['GET'])
def get_homes():
    try:
        ws = get_sheet('data')
        headers = ws.row_values(1)
        records = ws.get_all_records()
        return jsonify({'success': True, 'data': records, 'headers': headers})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/homes', methods=['POST'])
@login_required
def add_home():
    try:
        data = request.json
        ws = get_sheet('data')
        headers = ws.row_values(1)
        row = [str(data.get(h, '')) for h in headers]
        ws.append_row(row)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/homes/<int:row_index>', methods=['PUT'])
@login_required
def update_home(row_index):
    try:
        data = request.json
        ws = get_sheet('data')
        headers = ws.row_values(1)
        sheet_row = row_index + 2
        for col_idx, h in enumerate(headers, start=1):
            ws.update_cell(sheet_row, col_idx, str(data.get(h, '')))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/homes/<int:row_index>', methods=['DELETE'])
@login_required
def delete_home(row_index):
    try:
        ws = get_sheet('data')
        ws.delete_rows(row_index + 2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ===== Generic Sheet API (promotions, reviews) =====
@app.route('/api/sheet/<sheet_name>', methods=['GET'])
def get_sheet_data(sheet_name):
    try:
        ws = get_sheet(sheet_name)
        headers = ws.row_values(1)
        records = ws.get_all_records()
        return jsonify({'success': True, 'data': records, 'headers': headers})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sheet/<sheet_name>', methods=['POST'])
@login_required
def add_sheet_row(sheet_name):
    try:
        data = request.json
        ws = get_sheet(sheet_name)
        headers = ws.row_values(1)
        row = [str(data.get(h, '')) for h in headers]
        ws.append_row(row)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sheet/<sheet_name>/<int:row_index>', methods=['PUT'])
@login_required
def update_sheet_row(sheet_name, row_index):
    try:
        data = request.json
        ws = get_sheet(sheet_name)
        headers = ws.row_values(1)
        sheet_row = row_index + 2
        for col_idx, h in enumerate(headers, start=1):
            ws.update_cell(sheet_row, col_idx, str(data.get(h, '')))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/sheet/<sheet_name>/<int:row_index>', methods=['DELETE'])
@login_required
def delete_sheet_row(sheet_name, row_index):
    try:
        ws = get_sheet(sheet_name)
        ws.delete_rows(row_index + 2)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ===== Reviews API (public submit, token-based edit/delete) =====
@app.route('/api/reviews', methods=['POST'])
def add_review():
    """Public — ใครก็ส่งรีวิวได้ ไม่ต้อง login"""
    try:
        data = request.json or {}
        ws = get_sheet('review')
        headers = ws.row_values(1)
        token = secrets.token_urlsafe(16)
        today = datetime.now().strftime('%d/%m/%Y')
        row_data = {}
        for h in headers:
            if h == 'token':
                row_data[h] = token
            elif h == 'Date':
                row_data[h] = today
            else:
                row_data[h] = str(data.get(h, ''))
        ws.append_row([row_data.get(h, '') for h in headers])
        return jsonify({'success': True, 'token': token})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/reviews/<int:row_index>', methods=['PUT'])
def update_review(row_index):
    """แก้ไขรีวิว — ต้องมี token เจ้าของ หรือ admin session"""
    try:
        data = request.json or {}
        token = data.get('token', '')
        is_admin = session.get('logged_in', False)
        ws = get_sheet('review')
        headers = ws.row_values(1)
        sheet_row = row_index + 2
        if not is_admin:
            if 'token' not in headers:
                return jsonify({'success': False, 'message': 'ไม่พบคอลัมน์ token'}), 403
            stored = ws.cell(sheet_row, headers.index('token') + 1).value
            if stored != token:
                return jsonify({'success': False, 'message': 'ไม่มีสิทธิ์แก้ไขรีวิวนี้'}), 403
        for col_idx, h in enumerate(headers, start=1):
            if h not in ('token', 'Date') and h in data:
                ws.update_cell(sheet_row, col_idx, str(data.get(h, '')))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/reviews/<int:row_index>', methods=['DELETE'])
def delete_review(row_index):
    """ลบรีวิว — ต้องมี token เจ้าของ หรือ admin session"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        token = data.get('token', '')
        is_admin = session.get('logged_in', False)
        ws = get_sheet('review')
        headers = ws.row_values(1)
        sheet_row = row_index + 2
        if not is_admin:
            if 'token' not in headers:
                return jsonify({'success': False, 'message': 'ไม่พบคอลัมน์ token'}), 403
            stored = ws.cell(sheet_row, headers.index('token') + 1).value
            if stored != token:
                return jsonify({'success': False, 'message': 'ไม่มีสิทธิ์ลบรีวิวนี้'}), 403
        ws.delete_rows(sheet_row)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print("=" * 40)
    print("  Monte Villa Admin Server")
    print("  เปิดเว็บ: http://localhost:8000")
    print("  กด Ctrl+C เพื่อหยุด")
    print("=" * 40)
    app.run(host='0.0.0.0', port=8000, debug=False)
