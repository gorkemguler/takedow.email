#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
takedow.email - Professional Phishing Domain Abuse Contact Finder
Advanced cybersecurity tool for finding and reporting abuse contacts for malicious domains
"""

import os
import sqlite3
import re
import socket
from datetime import datetime
from urllib.parse import quote
import whois
import dns.resolver
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, make_response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
# from flask_wtf.csrf import CSRFProtect  # Temporarily disabled for Docker compatibility
import secrets

app = Flask(__name__)

# Configuration from environment variables
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY', 'takedown_email_professional_security_2024'),
    DATABASE_PATH=os.environ.get('DATABASE_PATH', '/app/data/takedown_logs.db' if os.path.exists('/app') else 'takedown_logs.db'),
    ADMIN_USERNAME=os.environ.get('ADMIN_USERNAME', 'secadmin'),
    ADMIN_PASSWORD=os.environ.get('ADMIN_PASSWORD', 'admin123'),
    ADMIN_URL_PATH=os.environ.get('ADMIN_URL_PATH', 'security-dashboard-x9k2m8p7q4w1'),
    HOST=os.environ.get('HOST', '0.0.0.0'),
    PORT=int(os.environ.get('PORT', 5000)),
    DEBUG=os.environ.get('FLASK_DEBUG', '0') == '1'
)

app.secret_key = app.config['SECRET_KEY']

# Security configurations
# csrf = CSRFProtect(app)  # Disabled for Docker compatibility
# Alternative security: Rate limiting + Input validation + Security headers
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
limiter.init_app(app)

# Generate secure secret key for production
if not app.config.get('SECRET_KEY'):
    app.config['SECRET_KEY'] = secrets.token_hex(32)

# Security headers
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "font-src 'self' https://cdnjs.cloudflare.com; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response

# Input validation and sanitization
def validate_domain(domain):
    """Validate domain input"""
    if not domain or not isinstance(domain, str):
        return False
    
    # Remove whitespace and convert to lowercase
    domain = domain.strip().lower()
    
    # Basic domain validation
    import re
    domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
    
    if not re.match(domain_pattern, domain):
        return False
    
    # Check for suspicious patterns
    suspicious_patterns = [
        '../', '..\\', '/etc/', '/var/', '/tmp/',
        '<script', 'javascript:', 'data:', 'vbscript:',
        'onload=', 'onerror=', 'onclick=', 'onmouseover='
    ]
    
    for pattern in suspicious_patterns:
        if pattern.lower() in domain.lower():
            return False
    
    # Length check
    if len(domain) > 253:
        return False
        
    return True

def sanitize_input(text):
    """Sanitize text input"""
    if not text:
        return ""
    
    # Remove HTML tags and suspicious content
    import html
    text = html.escape(str(text))
    
    # Remove null bytes and control characters
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n\r')
    
    return text.strip()

# Multilingual support
LANGUAGES = {
    'en': {
        'title': 'takedow.email - Phishing Domain Abuse Contact Finder',
        'subtitle': 'Find and report abuse contacts for phishing and malicious domains',
        'search_placeholder': 'Enter suspicious domain (e.g., malicious-site.com)',
        'search_btn': 'Analyze Domain',
        'loading': 'Analyzing domain, please wait...',
        'domain_info': 'Domain Information',
        'abuse_contacts': 'Found Abuse Contact Addresses',
        'abuse_info': 'Click on email addresses to send automated reports:',
        'bulk_report': 'Send Bulk Report',
        'bulk_report_info': 'To send reports to all abuse addresses simultaneously:',
        'send_to_all': 'Send to All Addresses',
        'no_abuse_found': 'No Abuse Contacts Found',
        'manual_contact': 'No abuse email addresses were automatically found for this domain. You may try contacting the domain owner manually.',
        'footer': '© 2025 takedow.email - Securing the Internet',
        'admin_panel': 'Admin Panel',
        'admin_title': 'Admin Panel - Queried Domains',
        'recent_queries': 'Recent Queries',
        'unique_domains': 'Total Queries',
        'back_to_home': '← Back to Home',
        'domain': 'Domain',
        'query_time': 'Query Time',
        'ip_address': 'IP Address',
        'found_contacts': 'Found Contacts',
        'no_data': 'No domain queries have been made yet.',
        'security_note': 'This data is stored for security purposes.',
        'language': 'Language',
        'how_it_works': 'How It Works',
        'how_it_works_desc': 'This tool helps you report phishing domains by finding the necessary abuse email addresses and enabling you to send reports directly to the responsible parties.',
        'domain_analysis': 'Domain Analysis',
        'domain_analysis_desc': 'Automatically analyzes suspicious domains using WHOIS and IP data',
        'abuse_contacts_feature': 'Abuse Contacts',
        'abuse_contacts_desc': 'Finds relevant abuse email addresses from registrars and hosting providers',
        'direct_reporting': 'Direct Reporting',
        'direct_reporting_desc': 'One-click email composition with professional abuse report templates',
        'need_help': 'Need Help?',
        'need_help_desc': 'For additional support, consultation, and business cooperation, please contact us:'
    },
    'tr': {
        'title': 'takedow.email - Phishing Domain Abuse İletişim Bulucu',
        'subtitle': 'Phishing ve kötü amaçlı domainler için abuse iletişim bilgilerini bulun ve rapor edin',
        'search_placeholder': 'Şüpheli domain girin (örn: malicious-site.com)',
        'search_btn': 'Domain Analiz Et',
        'loading': 'Domain analiz ediliyor, lütfen bekleyin...',
        'domain_info': 'Domain Bilgileri',
        'abuse_contacts': 'Bulunan Abuse İletişim Adresleri',
        'abuse_info': 'Otomatik rapor göndermek için email adreslerine tıklayın:',
        'bulk_report': 'Toplu Rapor Gönder',
        'bulk_report_info': 'Tüm abuse adreslerine aynı anda rapor göndermek için:',
        'send_to_all': 'Tüm Adreslere Gönder',
        'no_abuse_found': 'Abuse İletişimi Bulunamadı',
        'manual_contact': 'Bu domain için otomatik olarak abuse email adresi bulunamadı. Domain sahibi ile manuel iletişime geçmeyi deneyebilirsiniz.',
        'footer': '© 2025 takedow.email - İnterneti Güvence Altına Alıyoruz',
        'admin_panel': 'Yönetici Paneli',
        'admin_title': 'Yönetici Paneli - Sorgulanan Domainler',
        'recent_queries': 'Son Sorgular',
        'unique_domains': 'Toplam Sorgu',
        'back_to_home': '← Ana Sayfaya Dön',
        'domain': 'Domain',
        'query_time': 'Sorgu Zamanı',
        'ip_address': 'IP Adresi',
        'found_contacts': 'Bulunan İletişimler',
        'no_data': 'Henüz hiç domain sorgusu yapılmamış.',
        'security_note': 'Bu veriler güvenlik amaçlı saklanmaktadır.',
        'language': 'Dil',
        'how_it_works': 'Nasıl Çalışır',
        'how_it_works_desc': 'Bu araç phishing domainleri ihbar etmeniz için gerekli abuse email adreslerine ulaşır ve mail göndermenizi sağlar.',
        'domain_analysis': 'Domain Analizi',
        'domain_analysis_desc': 'WHOIS ve IP verilerini kullanarak şüpheli domainleri otomatik olarak analiz eder',
        'abuse_contacts_feature': 'Abuse İletişim',
        'abuse_contacts_desc': 'Registrar ve hosting sağlayıcılarından ilgili abuse email adreslerini bulur',
        'direct_reporting': 'Doğrudan Raporlama',
        'direct_reporting_desc': 'Profesyonel abuse rapor şablonları ile tek tıkla email oluşturma',
        'need_help': 'Yardıma mı İhtiyacınız Var?',
        'need_help_desc': 'Daha fazla destek, danışmanlık ve iş birliği için bize ulaşın:'
    }
}

def get_language():
    """Get current language from session or default to English"""
    return session.get('language', 'en')

def get_text(key):
    """Get localized text"""
    lang = get_language()
    return LANGUAGES.get(lang, LANGUAGES['en']).get(key, key)

# Veritabanı kurulumu
def init_db():
    """Veritabanını başlat"""
    # Ensure database directory exists
    db_path = app.config['DATABASE_PATH']
    db_dir = os.path.dirname(db_path)
    
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        print(f"Created database directory: {db_dir}")
    
    # Check if we can write to the directory
    if db_dir and not os.access(db_dir, os.W_OK):
        print(f"Warning: No write permission to database directory: {db_dir}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Sorgulanan domainleri kaydetmek için tablo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS domain_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            query_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            abuse_contacts TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def log_domain_query(domain, ip_address, user_agent, abuse_contacts):
    """Domain sorgusunu veritabanına kaydet"""
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO domain_queries (domain, ip_address, user_agent, abuse_contacts)
        VALUES (?, ?, ?, ?)
    ''', (domain, ip_address, user_agent, str(abuse_contacts)))
    
    conn.commit()
    conn.close()

def extract_abuse_emails_from_whois(domain):
    """WHOIS bilgilerinden abuse email adreslerini çıkar"""
    abuse_emails = set()
    
    try:
        # Ham WHOIS metnini al
        import subprocess
        result = subprocess.run(['whois', domain], capture_output=True, text=True, timeout=10)
        whois_text = result.stdout
        
        # Python WHOIS kütüphanesinden de bilgi al
        try:
            w = whois.whois(domain)
            structured_whois = str(w)
            whois_text += "\n" + structured_whois
        except:
            pass
        
        # Özel abuse satırlarını ara
        lines = whois_text.split('\n')
        for line in lines:
            line = line.strip()
            # Registrar Abuse Contact Email satırını ara
            if 'registrar abuse contact email:' in line.lower():
                email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line, re.IGNORECASE)
                if email_match:
                    abuse_emails.add(email_match.group())
            
            # Abuse-mailbox satırını ara
            if 'abuse-mailbox:' in line.lower():
                email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line, re.IGNORECASE)
                if email_match:
                    abuse_emails.add(email_match.group())
        
        # Email regex pattern'i
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, whois_text)
        
        # Abuse ile ilgili email'leri filtrele
        for email in emails:
            email_lower = email.lower()
            if any(keyword in email_lower for keyword in ['abuse', 'security', 'admin', 'hostmaster', 'postmaster']):
                abuse_emails.add(email)
        
        # Eğer abuse email bulunamazsa, genel admin emaillerini de ekle
        if not abuse_emails:
            for email in emails:
                email_lower = email.lower()
                if any(keyword in email_lower for keyword in ['admin', 'contact', 'info']):
                    abuse_emails.add(email)
                    
    except Exception as e:
        print(f"WHOIS hatası {domain}: {e}")
    
    return list(abuse_emails)

def get_domain_ip(domain):
    """Domain'in IP adresini al"""
    try:
        return socket.gethostbyname(domain)
    except:
        return None

def get_abuse_contact_from_ip(ip):
    """IP adresinden abuse contact bilgisi al"""
    abuse_emails = set()
    
    # Farklı WHOIS sunucularını dene
    whois_servers = [
        None,  # Varsayılan whois
        'whois.ripe.net',
        'whois.arin.net', 
        'whois.apnic.net'
    ]
    
    for whois_server in whois_servers:
        try:
            # IP'nin WHOIS bilgilerini al
            import subprocess
            if whois_server:
                result = subprocess.run(['whois', '-h', whois_server, ip], capture_output=True, text=True, timeout=10)
            else:
                result = subprocess.run(['whois', ip], capture_output=True, text=True, timeout=10)
            
            whois_text = result.stdout
            
            # Özel abuse satırlarını ara
            lines = whois_text.split('\n')
            for line in lines:
                line = line.strip()
                
                # "Abuse contact for 'x.x.x.x - y.y.y.y' is 'email'" formatını ara
                if 'abuse contact for' in line.lower() and 'is' in line.lower():
                    email_match = re.search(r"'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})'", line, re.IGNORECASE)
                    if email_match:
                        email = email_match.group(1)
                        if not email.lower().startswith('no-email@'):
                            abuse_emails.add(email)
                
                # abuse-mailbox satırını ara
                if 'abuse-mailbox:' in line.lower():
                    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line, re.IGNORECASE)
                    if email_match:
                        email = email_match.group()
                        if not email.lower().startswith('no-email@'):
                            abuse_emails.add(email)
                
                # e-mail: satırını ara (sadece abuse ile ilgili kısımda)
                if 'e-mail:' in line.lower():
                    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line, re.IGNORECASE)
                    if email_match:
                        email = email_match.group()
                        # Sadece abuse ile ilgili emailler
                        if 'abuse' in email.lower() or 'security' in email.lower():
                            abuse_emails.add(email)
                
                # Registrar Abuse Contact Email satırını ara
                if 'registrar abuse contact email:' in line.lower():
                    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line, re.IGNORECASE)
                    if email_match:
                        abuse_emails.add(email_match.group())
            
            # Email pattern'i ile abuse emaillerini bul
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, whois_text)
            
            for email in emails:
                email_lower = email.lower()
                if any(keyword in email_lower for keyword in ['abuse', 'security', 'admin']):
                    # no-email@apnic.net gibi geçersiz adresleri filtrele
                    if not email_lower.startswith('no-email@'):
                        abuse_emails.add(email)
                        
        except Exception as e:
            print(f"IP WHOIS hatası {ip} ({whois_server}): {e}")
            continue
    
    return list(abuse_emails)

def generate_abuse_report_template(domain, abuse_emails):
    """Generate professional abuse report email template"""
    subject = f"Abuse Report: Suspicious Domain Activity - {domain}"
    
    body = f"""Dear Abuse Team,

I am writing to report suspicious activity associated with the domain: {domain}

This domain appears to be involved in potentially malicious activities including but not limited to:
- Phishing attacks
- Fraudulent activities
- Impersonation of legitimate services
- Distribution of malicious content

Domain Details:
- Reported Domain: {domain}
- Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
- Report Source: takedow.email Professional Security Platform

We kindly request that you investigate this domain and take appropriate action according to your abuse policies. If this domain is found to be engaging in malicious activities, please consider suspending or taking down the domain to protect internet users.

Additional evidence or technical details can be provided upon request.

Thank you for your attention to this matter and your efforts in maintaining internet security.

Best regards,
Security Team
takedow.email Professional Platform

---
This is an automated report generated by takedow.email security platform.
For inquiries: security@takedow.email"""

    return {
        'subject': subject,
        'body': body,
        'mailto_link': f"mailto:{';'.join(abuse_emails)}?subject={quote(subject)}&body={quote(body)}"
    }

@app.route('/set_language/<language>')
def set_language(language):
    """Set user language preference"""
    if language in LANGUAGES:
        session['language'] = language
    return redirect(request.referrer or url_for('index'))

@app.route('/favicon.ico')
def favicon():
    """Serve favicon"""
    return app.send_static_file('favicon.ico')

@app.route('/')
def index():
    """Main page with cybersecurity professional design"""
    return render_template('index.html', 
                         get_text=get_text, 
                         current_lang=get_language(),
                         languages=LANGUAGES)

@app.route('/lookup', methods=['POST'])
@limiter.limit("10 per minute")
# @csrf.exempt  # CSRF temporarily disabled
def lookup_domain():
    """Domain sorgulama endpoint'i"""
    # Handle both JSON and form data
    if request.is_json:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'JSON verisi gerekli'}), 400
        domain = data.get('domain', '')
    else:
        domain = request.form.get('domain', '')
    
    if not domain:
        return jsonify({'error': 'Domain adresi gerekli'}), 400
        
    # Validate domain input
    if not validate_domain(domain):
        return jsonify({'error': 'Geçersiz domain formatı'}), 400
        
    domain = domain.strip().lower()
    
    # Domain'i temizle (http/https prefix'lerini kaldır)
    domain = re.sub(r'^https?://', '', domain)
    domain = re.sub(r'^www\.', '', domain)
    domain = domain.split('/')[0]  # Path kısmını kaldır
    
    try:
        # IP adresini al
        domain_ip = get_domain_ip(domain)
        
        # WHOIS'dan abuse emaillerini al
        whois_abuse_emails = extract_abuse_emails_from_whois(domain)
        
        # IP'den abuse emaillerini al
        ip_abuse_emails = []
        if domain_ip:
            ip_abuse_emails = get_abuse_contact_from_ip(domain_ip)
        
        # Tüm abuse emaillerini birleştir
        all_abuse_emails = list(set(whois_abuse_emails + ip_abuse_emails))
        
        # Eğer hiç email bulunamazsa, genel abuse adreslerini ekle
        if not all_abuse_emails:
            # Domain'in registrar'ından genel abuse adresi oluştur
            domain_parts = domain.split('.')
            if len(domain_parts) >= 2:
                tld = domain_parts[-1]
                sld = domain_parts[-2]
                all_abuse_emails.append(f'abuse@{sld}.{tld}')
                all_abuse_emails.append(f'admin@{sld}.{tld}')
        
        # Email template'ini oluştur
        email_template = generate_abuse_report_template(domain, all_abuse_emails)
        
        # Sorguyu kaydet
        user_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
        user_agent = request.environ.get('HTTP_USER_AGENT', 'unknown')
        log_domain_query(domain, user_ip, user_agent, all_abuse_emails)
        
        return jsonify({
            'domain': domain,
            'ip': domain_ip,
            'whois_abuse_emails': whois_abuse_emails,
            'ip_abuse_emails': ip_abuse_emails,
            'all_abuse_emails': all_abuse_emails,
            'email_template': email_template
        })
        
    except Exception as e:
        return jsonify({'error': f'Sorgulama hatası: {str(e)}'}), 500

@app.route(f"/{app.config['ADMIN_URL_PATH']}")
@limiter.limit("30 per minute")
def admin_logs():
    """Professional admin panel for security monitoring"""
    # Enhanced security check
    auth = request.authorization
    if not auth or auth.username != app.config['ADMIN_USERNAME'] or auth.password != app.config['ADMIN_PASSWORD']:
        return '', 401, {'WWW-Authenticate': 'Basic realm="Secure Admin Area"'}
    
    # Get pagination parameters
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(100, max(10, int(request.args.get('per_page', 20))))
    search = sanitize_input(request.args.get('search', ''))
    
    # Calculate offset
    offset = (page - 1) * per_page
    
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    
    # Build query with search filter
    base_query = '''
        FROM domain_queries
        WHERE 1=1
    '''
    params = []
    
    if search:
        base_query += ' AND (domain LIKE ? OR ip_address LIKE ? OR abuse_contacts LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])
    
    # Get total count
    cursor.execute(f'SELECT COUNT(*) {base_query}', params)
    total_count = cursor.fetchone()[0]
    
    # Get paginated results
    cursor.execute(f'''
        SELECT domain, query_time, ip_address, abuse_contacts
        {base_query}
        ORDER BY query_time DESC
        LIMIT ? OFFSET ?
    ''', params + [per_page, offset])
    
    logs = cursor.fetchall()
    conn.close()
    
    # Calculate pagination info
    total_pages = (total_count + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total_count': total_count,
        'total_pages': total_pages,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_num': page - 1 if has_prev else None,
        'next_num': page + 1 if has_next else None
    }
    
    return render_template('admin_logs.html', 
                         logs=logs,
                         pagination=pagination,
                         search=search,
                         get_text=get_text, 
                         current_lang=get_language(),
                         languages=LANGUAGES)

@app.route(f"/{app.config['ADMIN_URL_PATH']}/export")
@limiter.limit("5 per minute")
def admin_export():
    """Export query history data"""
    # Enhanced security check
    auth = request.authorization
    if not auth or auth.username != app.config['ADMIN_USERNAME'] or auth.password != app.config['ADMIN_PASSWORD']:
        return '', 401, {'WWW-Authenticate': 'Basic realm="Secure Admin Area"'}
    
    format_type = sanitize_input(request.args.get('format', 'csv')).lower()
    if format_type not in ['csv', 'json']:
        format_type = 'csv'
    search = sanitize_input(request.args.get('search', ''))
    
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    
    # Build query with search filter
    base_query = '''
        SELECT domain, query_time, ip_address, abuse_contacts
        FROM domain_queries
        WHERE 1=1
    '''
    params = []
    
    if search:
        base_query += ' AND (domain LIKE ? OR ip_address LIKE ? OR abuse_contacts LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])
    
    base_query += ' ORDER BY query_time DESC'
    
    cursor.execute(base_query, params)
    logs = cursor.fetchall()
    conn.close()
    
    if format_type == 'json':
        import json
        from datetime import datetime
        
        data = []
        for log in logs:
            data.append({
                'domain': log[0],
                'query_time': log[1],
                'ip_address': log[2],
                'abuse_contacts': log[3]
            })
        
        response = make_response(json.dumps(data, indent=2, ensure_ascii=False))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename=takedown_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
    else:  # CSV format
        import csv
        import io
        from datetime import datetime
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Domain', 'Query Time', 'IP Address', 'Abuse Contacts'])
        
        # Write data
        for log in logs:
            writer.writerow([log[0], log[1], log[2], log[3]])
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=takedown_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    return response

@app.route(f"/{app.config['ADMIN_URL_PATH']}/stats")
@limiter.limit("20 per minute")
def admin_stats():
    """Admin statistics dashboard"""
    # Enhanced security check
    auth = request.authorization
    if not auth or auth.username != app.config['ADMIN_USERNAME'] or auth.password != app.config['ADMIN_PASSWORD']:
        return '', 401, {'WWW-Authenticate': 'Basic realm="Secure Admin Area"'}
    
    conn = sqlite3.connect(app.config['DATABASE_PATH'])
    cursor = conn.cursor()
    
    # Genel istatistikler
    cursor.execute('SELECT COUNT(*) FROM domain_queries')
    total_queries = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT domain) FROM domain_queries')
    unique_domains = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT ip_address) FROM domain_queries')
    unique_ips = cursor.fetchone()[0]
    
    # Bugünkü sorgular
    cursor.execute('''
        SELECT COUNT(*) FROM domain_queries 
        WHERE DATE(query_time) = DATE('now')
    ''')
    today_queries = cursor.fetchone()[0]
    
    # Bu haftaki sorgular
    cursor.execute('''
        SELECT COUNT(*) FROM domain_queries 
        WHERE DATE(query_time) >= DATE('now', '-7 days')
    ''')
    week_queries = cursor.fetchone()[0]
    
    # En çok sorgulanan domainler (son 30 gün)
    cursor.execute('''
        SELECT domain, COUNT(*) as count, MAX(query_time) as last_query
        FROM domain_queries 
        WHERE DATE(query_time) >= DATE('now', '-30 days')
        GROUP BY domain 
        ORDER BY count DESC 
        LIMIT 10
    ''')
    top_domains = cursor.fetchall()
    
    # En aktif IP'ler (son 7 gün)
    cursor.execute('''
        SELECT ip_address, COUNT(*) as count, MAX(query_time) as last_query
        FROM domain_queries 
        WHERE DATE(query_time) >= DATE('now', '-7 days')
        GROUP BY ip_address 
        ORDER BY count DESC 
        LIMIT 10
    ''')
    top_ips = cursor.fetchall()
    
    # Günlük aktivite (son 14 gün)
    cursor.execute('''
        SELECT DATE(query_time) as date, COUNT(*) as count
        FROM domain_queries 
        WHERE DATE(query_time) >= DATE('now', '-14 days')
        GROUP BY DATE(query_time)
        ORDER BY date DESC
    ''')
    daily_activity = cursor.fetchall()
    
    # Saatlik aktivite (bugün)
    cursor.execute('''
        SELECT strftime('%H', query_time) as hour, COUNT(*) as count
        FROM domain_queries 
        WHERE DATE(query_time) = DATE('now')
        GROUP BY strftime('%H', query_time)
        ORDER BY hour
    ''')
    hourly_activity = cursor.fetchall()
    
    conn.close()
    
    stats = {
        'total_queries': total_queries,
        'unique_domains': unique_domains,
        'unique_ips': unique_ips,
        'today_queries': today_queries,
        'week_queries': week_queries,
        'top_domains': top_domains,
        'top_ips': top_ips,
        'daily_activity': daily_activity,
        'hourly_activity': hourly_activity
    }
    
    return render_template('admin_stats.html', 
                         stats=stats,
                         get_text=get_text, 
                         current_lang=get_language(),
                         languages=LANGUAGES)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template('error_404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    import uuid
    error_id = str(uuid.uuid4())[:8]
    print(f"Internal Server Error {error_id}: {str(error)}")
    return render_template('error_500.html', error_id=error_id), 500

@app.errorhandler(403)
def forbidden_error(error):
    """Handle 403 errors"""
    return render_template('error_403.html'), 403

@app.errorhandler(405)
def method_not_allowed_error(error):
    """Handle 405 errors"""
    return render_template('error_404.html'), 405

@app.errorhandler(429)
def ratelimit_handler(error):
    """Handle rate limit errors"""
    return render_template('error_500.html', error_id='RATE_LIMIT'), 429

if __name__ == '__main__':
    # Veritabanını başlat
    init_db()
    
    # Uygulamayı çalıştır
    app.run(
        host=app.config['HOST'],
        port=app.config['PORT'],
        debug=app.config['DEBUG']
    )
