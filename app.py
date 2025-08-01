import os
import secrets
import json
from flask import Flask, send_file, abort, request, after_this_request, make_response
from datetime import datetime, timedelta
from user_agents import parse
from collections import defaultdict

app = Flask(__name__)
UPLOAD_FOLDER = './uploads'
LINKS_DB = './links.json'
LOG_FILE = './download_logs.txt'

rate_limit_records = defaultdict(list)
BLOCK_TIME = timedelta(hours=1)
MAX_REQUESTS_PER_DAY = 5


def load_links():
    """
    Загружает словарь одноразовых ссылок из файла LINKS_DB.
    Если файл отсутствует, возвращает пустой словарь.
    """
    if not os.path.exists(LINKS_DB):
        return {}
    with open(LINKS_DB, 'r') as f:
        return json.load(f)


def save_links(links):
    """
    Сохраняет словарь одноразовых ссылок в файл LINKS_DB в формате JSON с отступами.
    """
    with open(LINKS_DB, 'w') as f:
        json.dump(links, f, indent=2)


def create_one_time_link(filename):
    """
    Создаёт новую одноразовую ссылку для указанного имени файла.
    Генерирует случайный URL-safe токен длиной 32 байта.
    Сохраняет в словарь links и записывает в файл.
    Возвращает полный URL для скачивания.
    """
    links = load_links()
    link_id = secrets.token_urlsafe(32)
    links[link_id] = filename
    save_links(links)
    return f"http://hwidmakey.duckdns.org/download/{link_id}"


def log_access(link_id, filename, ip, user_agent_str, device, os_family, os_version, browser_family, browser_version,
               status):
    """
    Логирует попытку доступа к ссылке скачивания.
    В логе фиксируются дата и время, ID ссылки, имя файла, IP клиента,
    статус запроса, а также данные User-Agent: устройство, ОС, браузер и строка UA.
    Запись добавляется в файл LOG_FILE.
    """
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    log_line = (
        f"{timestamp} | LinkID: {link_id} | File: {filename} | IP: {ip} | Status: {status}\n"
        f"  Device: {device}\n"
        f"  OS: {os_family} {os_version}\n"
        f"  Browser: {browser_family} {browser_version}\n"
        f"  UA: {user_agent_str}\n"
        "-----------------------------\n"
    )
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line)


def clean_rate_limits():
    """
    Очищает записи о запросах в rate_limit_records старше 24 часов,
    чтобы поддерживать актуальность данных для ограничения частоты запросов.
    """
    cutoff = datetime.utcnow() - timedelta(days=1)
    for ip in list(rate_limit_records.keys()):
        rate_limit_records[ip] = [ts for ts in rate_limit_records[ip] if ts > cutoff]
        if not rate_limit_records[ip]:
            del rate_limit_records[ip]


def is_ip_blocked(ip):
    """
    Проверяет, заблокирован ли IP-адрес из-за превышения лимита запросов.
    Если количество запросов за последние сутки превысило MAX_REQUESTS_PER_DAY,
    и последний запрос был менее часа назад, возвращает True (заблокирован).
    Иначе блокировка снимается.
    """
    clean_rate_limits()
    timestamps = rate_limit_records.get(ip, [])
    if len(timestamps) > MAX_REQUESTS_PER_DAY:
        last_request = timestamps[-1]
        if datetime.utcnow() - last_request < BLOCK_TIME:
            return True
        else:
            rate_limit_records[ip] = []
            return False
    return False


def register_request(ip):
    """
    Регистрирует текущий запрос от IP-адреса, добавляя временную метку в rate_limit_records.
    Перед добавлением очищает устаревшие записи.
    """
    clean_rate_limits()
    rate_limit_records[ip].append(datetime.utcnow())


@app.route('/download/<link_id>')
def download_file(link_id):
    """
    Обрабатывает запрос на скачивание файла по одноразовой ссылке.
    Проверяет блокировку IP, регистрирует запрос.
    При успешной отдаче файла удаляет ссылку из словаря (инвалидирует).
    Запрещает докачку (HTTP Range-запросы).
    Логирует все попытки доступа и результаты.
    Возвращает файл или соответствующий HTTP-ответ с ошибкой.
    """
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        ip = forwarded_for.split(',')[0].strip()
    else:
        ip = request.remote_addr or 'Unknown IP'

    if is_ip_blocked(ip):
        return make_response(
            "В целях безопасности вы были временно заблокированы на данном ресурсе",
            429
        )

    register_request(ip)

    links = load_links()
    if link_id not in links:
        log_access(link_id, 'N/A', ip, 'N/A', 'N/A', 'N/A', 'N/A', 'N/A', '404 NOT FOUND')
        return abort(404, "Нечего тут лазить, ничего не найдешь, гуляй, все зашифровано")

    if 'Range' in request.headers:
        log_access(link_id, links[link_id], ip, request.headers.get('User-Agent', 'Unknown UA'), 'N/A', 'N/A', 'N/A',
                   'N/A', '403 RANGE NOT ALLOWED')
        return abort(403,
                     "Докачивание файлов запрещено для одноразовых ссылок. Если попробуешь ещё раз — получишь перманентный бан на этом ресурсе и больше ничего не сможешь купить. Будь адекватен.")

    filename = links[link_id]
    file_path = os.path.join(UPLOAD_FOLDER, filename)

    if not os.path.exists(file_path):
        log_access(link_id, filename, ip, request.headers.get('User-Agent', 'Unknown UA'), 'N/A', 'N/A', 'N/A', 'N/A',
                   '404 FILE NOT FOUND')
        return abort(404, "Нечего тут лазить, ничего не найдешь, гуляй, все зашифровано")

    user_agent_str = request.headers.get('User-Agent', 'Unknown UA')
    user_agent = parse(user_agent_str)
    device = ('Mobile' if user_agent.is_mobile else
              'Tablet' if user_agent.is_tablet else
              'PC' if user_agent.is_pc else
              'Bot' if user_agent.is_bot else 'Unknown')
    os_family = user_agent.os.family
    os_version = user_agent.os.version_string
    browser_family = user_agent.browser.family
    browser_version = user_agent.browser.version_string

    @after_this_request
    def remove_link_and_log(response):
        if response.status_code == 200:
            current_links = load_links()
            if link_id in current_links:
                current_links.pop(link_id)
                save_links(current_links)
            log_access(link_id, filename, ip, user_agent_str, device, os_family, os_version,
                       browser_family, browser_version, "200 SUCCESS")
        else:
            log_access(link_id, filename, ip, user_agent_str, device, os_family, os_version,
                       browser_family, browser_version, f"{response.status_code} ERROR")
        return response

    return send_file(file_path, as_attachment=True,
                     download_name=filename,
                     mimetype='application/octet-stream')


@app.route('/generate/<filename>')
def generate_link(filename):
    """
    Создаёт одноразовую ссылку на скачивание указанного файла, если файл существует в папке uploads.
    Возвращает ссылку или сообщение об ошибке, если файла нет.
    """
    if not os.path.exists(os.path.join(UPLOAD_FOLDER, filename)):
        return f"Файл {filename} не найден в папке uploads"
    return create_one_time_link(filename)


if __name__ == '__main__':
    app.run(debug=False)
