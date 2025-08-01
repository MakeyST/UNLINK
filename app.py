import os
import uuid
import json
from flask import Flask, send_file, abort, request
from datetime import datetime

app = Flask(__name__)
UPLOAD_FOLDER = './uploads'
LINKS_DB = './links.json'
LOG_FILE = './download_logs.txt'

def load_links():
    if not os.path.exists(LINKS_DB):
        return {}
    with open(LINKS_DB, 'r') as f:
        return json.load(f)

def save_links(links):
    with open(LINKS_DB, 'w') as f:
        json.dump(links, f)

def create_one_time_link(filename):
    links = load_links()
    link_id = str(uuid.uuid4())
    links[link_id] = filename
    save_links(links)
    return f"http://localhost:5000/download/{link_id}"  # Замени домен

def log_download(link_id, filename):
    ip = request.remote_addr or 'Unknown IP'
    user_agent = request.headers.get('User-Agent', 'Unknown UA')
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

    log_line = f"{timestamp} | LinkID: {link_id} | File: {filename} | IP: {ip} | UA: {user_agent}\n"

    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line)

@app.route('/download/<link_id>')
def download_file(link_id):
    links = load_links()
    if link_id not in links:
        return abort(404)

    # Запрет докачки с помощью заголовка Range
    if 'Range' in request.headers:
        # Можно отклонить докачку, так как ссылка одноразовая
        return abort(403, "Докачивание файлов запрещено для одноразовых ссылок")

    filename = links.pop(link_id)
    save_links(links)
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.exists(file_path):
        return abort(404)

    log_download(link_id, filename)

    return send_file(file_path, as_attachment=True,
                     download_name=filename,
                     mimetype='application/octet-stream')

@app.route('/generate/<filename>')
def generate_link(filename):
    if not os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        return f"Файл {filename} не найден в папке uploads"
    return create_one_time_link(filename)

if __name__ == '__main__':
    app.run(debug=False)
