#!/usr/bin/env python3
"""Локальный тест Mini App.

Режимы:
  1) Браузер (всегда, без HTTPS):
       python scripts/local_miniapp.py
     → http://127.0.0.1:8000/app/

  2) Telegram через туннель (если есть cloudflared или ngrok):
       python scripts/local_miniapp.py --tunnel
     → обновит WEB_APP_URL и нужно перезапустить telegram.py

ngrok из РБ часто блокируется (ERR_NGROK_9040) — предпочти cloudflared:
  brew install cloudflared
  или положи бинарь в bin/cloudflared
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / '.env'
PORT = int(os.environ.get('PORT', '8000'))
DEFAULT_DEV_TG = '777842796'


def update_env(key: str, value: str) -> None:
    text = ENV_PATH.read_text(encoding='utf-8') if ENV_PATH.exists() else ''
    pattern = re.compile(rf'^{re.escape(key)}=.*$', re.M)
    line = f'{key}={value}'
    if pattern.search(text):
        text = pattern.sub(line, text)
    else:
        text = text.rstrip() + '\n' + line + '\n'
    ENV_PATH.write_text(text, encoding='utf-8')


def find_bin(name: str) -> str | None:
    candidates = [
        ROOT / 'bin' / name,
        Path('/opt/homebrew/bin') / name,
        Path('/usr/local/bin') / name,
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    which = subprocess.run(['which', name], capture_output=True, text=True)
    if which.returncode == 0 and which.stdout.strip():
        return which.stdout.strip()
    return None


def port_open(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(('127.0.0.1', port)) == 0


def wait_http(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as resp:
                if resp.status < 500:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def wait_ngrok_https(timeout: float = 25.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels', timeout=2) as resp:
                data = json.load(resp)
            for t in data.get('tunnels', []):
                url = t.get('public_url') or ''
                if url.startswith('https://'):
                    return url.rstrip('/')
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            pass
        time.sleep(0.5)
    raise RuntimeError('ngrok не отдал https URL')


def start_cloudflared(bin_path: str, port: int) -> tuple[subprocess.Popen, str]:
    proc = subprocess.Popen(
        [bin_path, 'tunnel', '--url', f'http://127.0.0.1:{port}'],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    deadline = time.time() + 40
    public = ''
    assert proc.stdout is not None
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        if 'trycloudflare.com' in line or 'https://' in line:
            m = re.search(r'https://[a-zA-Z0-9.-]+\.trycloudflare\.com', line)
            if m:
                public = m.group(0).rstrip('/')
                break
    if not public:
        proc.terminate()
        raise RuntimeError('cloudflared не выдал URL')
    return proc, public


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--tunnel', action='store_true', help='Подняыть HTTPS-туннель для Telegram')
    parser.add_argument('--no-server', action='store_true', help='Не стартовать Django (уже запущен)')
    args = parser.parse_args()

    update_env('TELEGRAM_AUTH_BYPASS', 'True')
    update_env('DEBUG', 'True')

    children: list[subprocess.Popen] = []

    def shutdown(*_a):
        for p in children:
            if p.poll() is None:
                p.send_signal(signal.SIGTERM)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    venv_python = ROOT / 'venv' / 'bin' / 'python'
    py = str(venv_python if venv_python.exists() else sys.executable)

    if not args.no_server and not port_open(PORT):
        print(f'→ Django http://127.0.0.1:{PORT}')
        children.append(subprocess.Popen([py, 'manage.py', 'runserver', str(PORT)], cwd=str(ROOT)))
    else:
        print(f'→ Django уже слушает :{PORT}' if port_open(PORT) else '→ сервер не стартуем (--no-server)')

    if not wait_http(f'http://127.0.0.1:{PORT}/app/', timeout=25):
        print('Django не отвечает на /app/. Запусти: python manage.py runserver')
        return 1

    browser = f'http://127.0.0.1:{PORT}/app/?dev_tg_id={DEFAULT_DEV_TG}'
    print()
    print('=' * 56)
    print('БРАУЗЕР (можно прямо сейчас):')
    print(browser)
    print('=' * 56)

    if not args.tunnel:
        print()
        print('Для теста из Telegram позже:')
        print('  python scripts/local_miniapp.py --tunnel')
        print('(нужен cloudflared — ngrok из РБ часто блокируют)')
        if children:
            print('Ctrl+C — остановить Django')
            while True:
                time.sleep(1)
                for p in children:
                    if p.poll() is not None:
                        return p.returncode or 1
        return 0

    # --- tunnel ---
    public = ''
    cf = find_bin('cloudflared')
    ng = find_bin('ngrok')
    try:
        if cf:
            print('→ cloudflared quick tunnel…')
            proc, public = start_cloudflared(cf, PORT)
            children.append(proc)
        elif ng:
            print('→ ngrok… (из РБ может не работать)')
            children.append(
                subprocess.Popen(
                    [ng, 'http', str(PORT), '--log=stdout'],
                    cwd=str(ROOT),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                )
            )
            public = wait_ngrok_https()
        else:
            print('Нет cloudflared/ngrok. Браузер-режим уже работает выше.')
            print('Поставь: brew install cloudflared')
            return 0
    except Exception as exc:
        print('Туннель не поднялся:', exc)
        print('Оставайся на браузер-ссылке выше — для UI этого хватает.')
        return 0

    update_env('WEB_APP_URL', public)
    update_env(
        'CORS_ALLOWED_ORIGINS',
        f'http://localhost:{PORT},http://127.0.0.1:{PORT},{public}',
    )
    # дублируем в AppSettings — бот и мини-апп читают оттуда
    try:
        subprocess.run(
            [
                py,
                '-c',
                (
                    'import os,django; os.environ.setdefault("DJANGO_SETTINGS_MODULE","tutor_bot.settings"); '
                    'django.setup(); from core.models import AppSettings; '
                    f'a=AppSettings.get_settings(); a.web_app_url="{public}"; '
                    'a.save(update_fields=["web_app_url"]); print("AppSettings.web_app_url OK")'
                ),
            ],
            cwd=str(ROOT),
            check=False,
        )
    except Exception as exc:
        print('Не удалось записать AppSettings.web_app_url:', exc)
    print()
    print('TELEGRAM:')
    print(f'  {public}/app/')
    print('Перезапусти бота:  python telegram.py')
    print('Ctrl+C — стоп')
    while True:
        time.sleep(1)
        for p in children:
            if p.poll() is not None:
                return p.returncode or 1


if __name__ == '__main__':
    raise SystemExit(main())
