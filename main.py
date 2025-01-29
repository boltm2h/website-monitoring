import threading
import time
import requests
import socket
import ssl
from flask import Flask, request, jsonify
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import validators

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = "8076351581:AAHfLgDDmhP-BpO4r6kekp6F-67iAa8jRSY"
TELEGRAM_CHANNEL_USERNAME = "@M2HCcScrapping"

# Enhanced thread-safe storage
websites = {}
downtime_history = []
check_history = []
data_lock = threading.Lock()

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_USERNAME,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Failed to send message to Telegram: {response.text}")
        else:
            print("Message sent to Telegram successfully!")
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")

def get_ssl_info(url):
    try:
        if not url.startswith('https://'):
            return None

        hostname = url.split('//')[1].split('/')[0]
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                expires = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                return {
                    'valid': True,
                    'days_left': (expires - datetime.utcnow()).days,
                    'issuer': dict(x[0] for x in cert['issuer'])['organizationName'],
                    'subject': dict(x[0] for x in cert['subject'])['commonName']
                }
    except Exception as e:
        return {'valid': False, 'error': str(e)}

def monitor_website(url):
    config = websites[url]
    error = None
    content_matched = None
    status_code = None
    response_time = None
    ssl_info = None

    try:
        start = time.time()
        response = requests.get(url, timeout=5, 
                              headers={'User-Agent': 'WebMonitor/3.0'},
                              allow_redirects=config.get('follow_redirects', True))
        response_time = round((time.time() - start) * 1000, 2)
        status_code = response.status_code

        # Content check
        content_check = config.get('content_check')
        if content_check:
            content_matched = content_check in response.text

        # Status determination
        status = 'UP' if response.status_code == 200 else 'WARNING'
        if config.get('expected_status') and response.status_code != config['expected_status']:
            status = 'DOWN'

        # Response time threshold check
        if config.get('response_threshold') and response_time > config['response_threshold']:
            status = 'WARNING'

        ssl_info = get_ssl_info(url) if url.startswith('https') else None
    except Exception as e:
        status = 'DOWN'
        error = str(e)

    with data_lock:
        prev_status = websites[url].get('status')
        history = websites[url].get('history', [])[-99:] + [status]
        up_count = history.count('UP')
        uptime = round((up_count / len(history)) * 100, 1) if history else 0

        # Downtime tracking
        if prev_status != status:
            if status == 'DOWN':
                downtime_history.append({
                    'url': url,
                    'start': datetime.utcnow().isoformat(),
                    'end': None
                })
                # Send Telegram alert for downtime
                send_to_telegram(f"🚨 *Website Down*: {url}\nStatus: {status}\nError: {error or 'Unknown error'}")
            elif prev_status == 'DOWN':
                if downtime_history:
                    downtime_history[-1]['end'] = datetime.utcnow().isoformat()
                # Send Telegram alert for recovery
                send_to_telegram(f"✅ *Website Recovered*: {url}\nStatus: {status}\nResponse Time: {response_time}ms")

        websites[url].update({
            'status': status,
            'status_code': status_code,
            'response_time': response_time,
            'last_checked': datetime.utcnow().isoformat(),
            'history': history,
            'uptime': uptime,
            'ssl_info': ssl_info,
            'error': error,
            'content_matched': content_matched
        })

def monitoring_loop():
    with ThreadPoolExecutor(max_workers=10) as executor:
        while True:
            with data_lock:
                urls = list(websites.keys())
                if urls:
                    executor.map(monitor_website, urls)
                    check_history.extend([{
                        'url': url,
                        'time': datetime.utcnow().isoformat(),
                        'status': websites[url]['status']
                    } for url in urls])
                    check_history[:] = check_history[-1000:]
            time.sleep(30)

monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
monitor_thread.start()

@app.route('/')
def dashboard():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Website Monitor Pro+ By M2HGamerz</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            :root {
                --primary: #6366f1;
                --success: #22c55e;
                --warning: #f59e0b;
                --danger: #ef4444;
                --background: #0f172a;
                --glass: rgba(255, 255, 255, 0.08);
                --gradient: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
            }

            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: 'Inter', sans-serif;
            }

            body {
                background: var(--background);
                color: white;
                min-height: 100vh;
                padding: 1rem;
                display: flex;
                flex-direction: column;
            }

            .container {
                max-width: 1400px;
                margin: 0 auto;
                flex: 1;
            }

            .header {
                display: flex;
                flex-direction: column;
                gap: 1rem;
                margin-bottom: 2rem;
                padding: 2rem;
                background: var(--glass);
                backdrop-filter: blur(16px);
                border-radius: 1.5rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                background-image: var(--gradient);
                background-blend-mode: overlay;
            }

            .header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 1rem 2rem;
                background: var(--glass);
                backdrop-filter: blur(16px);
                border-radius: 1.5rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                background-image: var(--gradient);
                background-blend-mode: overlay;
            }

            .navbar {
                display: flex;
                gap: 1.5rem;
                align-items: center;
            }

            .navbar a {
                color: white;
                text-decoration: none;
                font-weight: 500;
                transition: color 0.2s ease;
            }

            .navbar a:hover {
                color: var(--primary);
            }

            .hamburger {
                display: none;
                font-size: 1.5rem;
                cursor: pointer;
            }

            @media (max-width: 768px) {
                .hamburger {
                    display: block;
                }

                .navbar {
                    display: none;
                    flex-direction: column;
                    position: absolute;
                    top: 4rem;
                    right: 1rem;
                    background: var(--glass);
                    backdrop-filter: blur(16px);
                    border-radius: 1rem;
                    padding: 1rem;
                    border: 1px solid rgba(255, 255, 255, 0.1);
                }

                .navbar.active {
                    display: flex;
                }
            }

            .add-form {
                display: flex;
                gap: 0.5rem;
                width: 100%;
                position: relative;
                flex-wrap: wrap;
            }

            .advanced-options {
                display: none;
                gap: 0.5rem;
                flex-wrap: wrap;
                margin-top: 0.5rem;
                width: 100%;
            }

            .advanced-toggle {
                background: none;
                border: none;
                color: white;
                cursor: pointer;
                padding: 0.5rem;
            }

            input, .btn, select {
                padding: 1rem 1.5rem;
                border-radius: 0.75rem;
                font-size: 1rem;
                transition: all 0.2s ease;
                flex: 1;
                min-width: 200px;
            }

            input {
                background: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: white;
            }

            .btn {
                background: rgba(255, 255, 255, 0.15);
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.1);
                cursor: pointer;
                display: flex;
                align-items: center;
                gap: 0.5rem;
                backdrop-filter: blur(10px);
                justify-content: center;
            }

            .dashboard-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 1.5rem;
                padding: 0 1rem;
            }

            .website-card {
                background: var(--glass);
                backdrop-filter: blur(16px);
                border-radius: 1.5rem;
                padding: 1.5rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
                animation: cardEntrance 0.6s ease forwards;
                box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
                position: relative;
            }

            .status {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.75rem 1.25rem;
                border-radius: 2rem;
                width: fit-content;
                font-weight: 600;
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
            }

            .metrics {
                margin-top: 1.5rem;
                display: grid;
                gap: 1rem;
            }

            .metric {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 1rem;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 0.75rem;
                font-size: 0.95rem;
            }

            .ssl-details {
                margin-top: 1rem;
                padding: 1rem;
                background: rgba(34, 197, 94, 0.05);
                border-radius: 0.75rem;
                border: 1px solid rgba(34, 197, 94, 0.1);
            }

            .remove-icon {
                position: absolute;
                top: 1rem;
                right: 1rem;
                cursor: pointer;
                color: var(--danger);
                background: rgba(239, 68, 68, 0.1);
                padding: 0.5rem;
                border-radius: 50%;
                transition: all 0.2s ease;
            }

            .remove-icon:hover {
                background: rgba(239, 68, 68, 0.2);
            }

            .footer {
                text-align: center;
                padding: 1rem;
                margin-top: 2rem;
                background: var(--glass);
                backdrop-filter: blur(16px);
                border-radius: 1.5rem;
                border: 1px solid rgba(255, 255, 255, 0.1);
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            }

            @media (max-width: 768px) {
                .header {
                    padding: 1rem;
                    border-radius: 1rem;
                }

                .add-form {
                    flex-direction: column;
                }

                input, .btn, select {
                    width: 100%;
                    padding: 0.75rem;
                }

                .dashboard-grid {
                    grid-template-columns: 1fr;
                }

                .website-card {
                    padding: 1rem;
                    margin: 0.5rem 0;
                }

                .website-card .metrics {
                    grid-template-columns: 1fr;
                }
            }

            @keyframes cardEntrance {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>
                    <i class="fas fa-shield-alt"></i> SiteWatch Pro M2H
                </h1>
                <form class="add-form" onsubmit="addWebsite(event)">
                    <input type="url" id="newUrl" placeholder="https://example.com" required>
                    <button type="button" class="advanced-toggle" onclick="toggleAdvanced()">
                        <i class="fas fa-cog"></i> Advanced
                    </button>
                    <div class="advanced-options" id="advancedOptions">
                        <input type="number" id="expectedStatus" placeholder="Expected Status Code">
                        <input type="number" id="responseThreshold" placeholder="Max Response Time (ms)">
                        <input type="text" id="contentCheck" placeholder="Required Content">
                        <select id="redirects" style="background: rgba(255, 255, 255, 0.15); color: white; border: 1px solid rgba(255, 255, 255, 0.1);">
                            <option value="true">Follow Redirects</option>
                            <option value="false">No Redirects</option>
                        </select>
                    </div>
                    <button type="submit" class="btn">
                        <i class="fas fa-plus"></i> Add Monitor
                    </button>
                </form>
            </div>

            <div class="dashboard-grid" id="dashboard"></div>
        </div>

        <div class="footer">
            <p>© 2025 SiteWatch Pro. All rights reserved.</p>
        </div>

        <script>
            function toggleAdvanced() {
                const options = document.getElementById('advancedOptions');
                options.style.display = options.style.display === 'flex' ? 'none' : 'flex';
            }

            function addWebsite(e) {
                e.preventDefault();
                const config = {
                    url: document.getElementById('newUrl').value,
                    expected_status: document.getElementById('expectedStatus').value,
                    response_threshold: document.getElementById('responseThreshold').value,
                    content_check: document.getElementById('contentCheck').value,
                    follow_redirects: document.getElementById('redirects').value
                };

                const params = new URLSearchParams();
                params.append('url', config.url);
                if (config.expected_status) params.append('expected_status', config.expected_status);
                if (config.response_threshold) params.append('response_threshold', config.response_threshold);
                if (config.content_check) params.append('content_check', config.content_check);
                params.append('follow_redirects', config.follow_redirects);

                fetch('/add?' + params)
                    .then(response => response.json())
                    .then(data => {
                        if (!data.success) {
                            alert('Error: ' + (data.error || 'Failed to add website'));
                        }
                        updateDashboard();
                        document.getElementById('newUrl').value = '';
                    })
                    .catch(error => console.error('Error:', error));
            }

            function removeWebsite(url) {
                fetch('/remove?url=' + encodeURIComponent(url))
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            updateDashboard();
                        } else {
                            alert('Error: Failed to remove website');
                        }
                    })
                    .catch(error => console.error('Error:', error));
            }

            function updateDashboard() {
                fetch('/status')
                    .then(r => r.json())
                    .then(data => {
                        let html = '';
                        for (const [url, info] of Object.entries(data)) {
                            const statusColor = info.status === 'UP' ? 'var(--success)' : 
                                              info.status === 'WARNING' ? 'var(--warning)' : 'var(--danger)';

                            html += `
                            <div class="website-card">
                                                            <div class="status" style="background: ${statusColor}20; color: ${statusColor};">
                                <i class="fas fa-${info.status === 'UP' ? 'check' : 'times'}"></i>
                                ${info.status}
                            </div>
                            <h3 style="margin: 1rem 0; word-break: break-all;">${url}</h3>
                            <div class="metrics">
                                <div class="metric">
                                    <span>Uptime:</span>
                                    <span>${info.uptime}%</span>
                                </div>
                                <div class="metric">
                                    <span>Response:</span>
                                    <span>${info.response_time || 'N/A'}ms</span>
                                </div>
                                ${info.status_code ? `
                                <div class="metric">
                                    <span>Status Code:</span>
                                    <span>${info.status_code}</span>
                                </div>` : ''}
                                ${info.content_matched !== null ? `
                                <div class="metric">
                                    <span>Content Match:</span>
                                    <span style="color: ${info.content_matched ? 'var(--success)' : 'var(--danger)'}">
                                        ${info.content_matched ? '✓' : '✗'}
                                    </span>
                                </div>` : ''}
                            </div>
                            ${info.ssl_info ? `
                            <div class="ssl-details">
                                <div class="metric">
                                    <span>SSL Valid:</span>
                                    <span style="color: ${info.ssl_info.valid ? 'var(--success)' : 'var(--danger)'}">
                                        ${info.ssl_info.valid ? 'Yes' : 'No'}
                                    </span>
                                </div>
                                ${info.ssl_info.days_left ? `
                                <div class="metric">
                                    <span>Days Left:</span>
                                    <span>${info.ssl_info.days_left}</span>
                                </div>` : ''}
                            </div>` : ''}
                            <div class="remove-icon" onclick="removeWebsite('${url}')">
                                <i class="fas fa-trash"></i>
                            </div>
                        </div>`;
                    }
                    document.getElementById('dashboard').innerHTML = html;
                });
        }

        // Initial load and periodic refresh
        document.addEventListener('DOMContentLoaded', updateDashboard);
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
'''

@app.route('/add')
def add_site():
    url = request.args.get('url')
    if not url:
        return jsonify(success=False, error='URL is required'), 400

    if not url.startswith(('http://', 'https://')):
        return jsonify(success=False, error='URL must start with http:// or https://'), 400

    if not validators.url(url):
        return jsonify(success=False, error='Invalid URL format'), 400

    config = {
        'expected_status': request.args.get('expected_status', type=int),
        'response_threshold': request.args.get('response_threshold', type=int),
        'content_check': request.args.get('content_check'),
        'follow_redirects': request.args.get('follow_redirects', 'true') == 'true'
    }

    with data_lock:
        if url in websites:
            return jsonify(success=False, error='URL already monitored'), 400

        websites[url] = {
            'status': 'CHECKING',
            'status_code': None,
            'response_time': None,
            'history': [],
            'uptime': 0,
            'ssl_info': None,
            'error': None,
            'content_matched': None,
            **{k: v for k, v in config.items() if v is not None}
        }

    return jsonify(success=True)

@app.route('/status')
def get_status():
    with data_lock:
        return jsonify(websites)

@app.route('/remove')
def remove_site():
    url = request.args.get('url')
    with data_lock:
        if url in websites:
            del websites[url]
    return jsonify(success=True)

@app.route('/downtime')
def get_downtime():
    url = request.args.get('url')
    return jsonify([entry for entry in downtime_history if entry['url'] == url])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
