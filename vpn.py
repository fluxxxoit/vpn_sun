#!/usr/bin/env python3

import os
import time
import random
import string
import re
import json
import logging
import subprocess
import base64
from datetime import datetime
from pathlib import Path

os.environ['PATH'] = '/data/data/com.termux/files/usr/bin:' + os.environ.get('PATH', '')

import requests
import urllib3
urllib3.disable_warnings()

from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

RED, GREEN, YELLOW, CYAN, WHITE = '\033[91m', '\033[92m', '\033[93m', '\033[96m', '\033[97m'
BOLD, DIM, END = '\033[1m', '\033[2m', '\033[0m'

BASE = Path(__file__).parent
SUBS_DIR = BASE / 'subscriptions'
REPO_DIR = BASE

with open(BASE / 'config.json') as f:
    CFG = json.load(f)

LOG_FILE = BASE / 'vpn.log'
HISTORY_FILE = BASE / 'history.txt'

class ColorFormatter(logging.Formatter):
    COLORS = {'INFO': CYAN, 'WARNING': YELLOW, 'ERROR': RED, 'DEBUG': DIM}
    def format(self, record):
        c = self.COLORS.get(record.levelname, WHITE)
        return f'{c}[{record.levelname[0]}]{END} {record.getMessage()}'

logging.basicConfig(level=logging.INFO, handlers=[])
log = logging.getLogger('vpnbot')
log.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(ColorFormatter())
log.addHandler(ch)
fh = logging.FileHandler(LOG_FILE)
fh.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
log.addHandler(fh)


def banner():
    print(f"""
{RED}╔══════════════════════════════════════════╗{END}
{RED}║{END} {BOLD}{WHITE}       VPN BOT • VLESS FETCHER        {END}{RED}║{END}
{RED}╚══════════════════════════════════════════╝{END}
""")


def ask_names():
    print(f'{RED}[?]{END} Введи имена друзей через запятую {DIM}(например: dima,sasha){END}:')
    try:
        inp = input(f'{RED}>{END} ').strip()
    except (KeyboardInterrupt, EOFError):
        return ['default']
    if not inp:
        return ['default']
    names = []
    for n in inp.split(','):
        safe = re.sub(r'[^a-zA-Z0-9_-]', '', n.strip().lower())
        if safe:
            names.append(safe)
    return names if names else ['default']


def try_mailtm():
    try:
        s = requests.Session()
        r = s.get('https://api.mail.tm/domains', timeout=15)
        if r.status_code != 200: return None, None
        domain = r.json()['hydra:member'][0]['domain']
        u = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f'{u}@{domain}'
        pwd = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        r = s.post('https://api.mail.tm/accounts', json={'address': email, 'password': pwd}, timeout=15)
        if r.status_code not in (200, 201): return None, None
        r = s.post('https://api.mail.tm/token', json={'address': email, 'password': pwd}, timeout=15)
        if r.status_code != 200: return None, None
        s.headers.update({'Authorization': f'Bearer {r.json()["token"]}'})
        log.info(f'mail.tm: {email}')
        return email, {'session': s, 'type': 'mailtm'}
    except Exception as e:
        log.warning(f'mail.tm: {e}')
        return None, None


def try_guerrilla():
    try:
        r = requests.get('https://api.guerrillamail.com/ajax.php?f=get_email_address&lang=en', timeout=15)
        if r.status_code != 200: return None, None
        d = r.json()
        log.info(f'guerrilla: {d["email_addr"]}')
        return d['email_addr'], {'sid': d['sid_token'], 'type': 'guerrilla'}
    except Exception as e:
        log.warning(f'guerrilla: {e}')
        return None, None


def create_email():
    for name, fn in [('mail.tm', try_mailtm), ('guerrilla', try_guerrilla)]:
        try:
            e, a = fn()
            if e: return e, a, name
        except Exception as ex:
            log.warning(f'{name}: {ex}')
    return None, None, None


def make_driver():
    opts = Options()
    opts.binary_location = CFG['firefox']
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    opts.set_preference('intl.accept_languages', 'ru-RU,ru;q=0.9')
    opts.set_preference('permissions.default.image', 2)
    opts.set_preference('network.http.connection-timeout', 120)
    opts.set_preference('dom.max_script_run_time', 120)
    drv = webdriver.Firefox(service=Service(CFG['geckodriver']), options=opts)
    drv.set_page_load_timeout(120)
    return drv


def register_and_get_config(email, drv):
    try:
        log.info('Загрузка power-vps...')
        loaded = False
        for _ in range(4):
            try:
                drv.get(f'{CFG["target"]}/free-trial/')
                loaded = True
                break
            except:
                drv.execute_script('window.stop();')
                time.sleep(3)
                if drv.title and 'Problem' not in drv.title:
                    loaded = True
                    break
        if not loaded: return None
        time.sleep(3)

        clicked = False
        for a in drv.find_elements(By.TAG_NAME, 'a'):
            try:
                if a.is_displayed() and 'e-mail' in a.text.lower():
                    drv.execute_script("arguments[0].scrollIntoView({block:'center'});", a)
                    time.sleep(1)
                    drv.execute_script('arguments[0].click();', a)
                    clicked = True
                    break
            except: pass
        if not clicked:
            btns = [a for a in drv.find_elements(By.TAG_NAME, 'a') if 'получить' in a.text.lower() and a.is_displayed()]
            if len(btns) >= 2:
                drv.execute_script('arguments[0].click();', btns[1])
                clicked = True
        if not clicked: return None
        time.sleep(3)

        filled = 0
        for inp in drv.find_elements(By.TAG_NAME, 'input'):
            if not inp.is_displayed(): continue
            name = (inp.get_attribute('name') or '').lower()
            try:
                if 'email' in name or 'mail' in name:
                    inp.clear(); inp.send_keys(email); filled += 1
                elif 'text' in name or 'name' in name:
                    inp.clear(); inp.send_keys('User'); filled += 1
            except: pass
        if filled == 0: return None

        for btn in drv.find_elements(By.TAG_NAME, 'button'):
            if btn.is_displayed() and 'получить' in btn.text.lower():
                drv.execute_script('arguments[0].click();', btn)
                break

        log.info('Жду редирект...')
        try:
            WebDriverWait(drv, 60).until(lambda d: 'powerhost.pro' in d.current_url)
        except: pass
        time.sleep(3)
        url = drv.current_url
        if 's.powerhost.pro/' not in url: return None
        
        log.info('Ищу токен в cookies...')
        drv.get(url)
        time.sleep(3)
        
        token = None
        for c in drv.get_cookies():
            if 'token' in c['name'].lower() or 'auth' in c['name'].lower() or 'sub' in c['name'].lower():
                token = c['value']
                log.info(f'Токен найден: {c["name"]} = {token[:20]}...')
                break
        
        if token:
            api_url = f'https://s.powerhost.pro/api/subscription/{token}'
            try:
                r = requests.get(api_url, timeout=15)
                if r.status_code == 200:
                    text = r.text.strip()
                    try:
                        decoded = base64.b64decode(text).decode('utf-8')
                        if 'vless://' in decoded:
                            return decoded
                    except:
                        if 'vless://' in text:
                            return text
            except Exception as e:
                log.warning(f'API error: {e}')
        
        # Если токен не сработал, ищем в HTML
        page_source = drv.page_source
        vless = re.findall(r'vless://[^\s<>"\'\\]+', page_source)
        if vless:
            return '\n'.join(vless)
        
        return None
    except Exception as e:
        log.error(f'Register error: {e}')
        return None


def get_one_config(name):
    print(f"\n{RED}{'━' * 48}{END}")
    print(f"{BOLD}{WHITE} ГЕНЕРАЦИЯ ДЛЯ: {name.upper()}{END}")
    print(f"{RED}{'━' * 48}{END}\n")

    email, account, provider = create_email()
    if not email:
        log.error(f'[{name}] Почта не создана')
        return None

    drv = make_driver()
    try:
        config = register_and_get_config(email, drv)
    finally:
        try: drv.quit()
        except: pass

    if config:
        print(f"\n{GREEN}✓{END} Конфиг получен (длина: {len(config)}){END}\n")
    else:
        log.error(f'[{name}] Конфиг не получен')
    return config


def push_to_github():
    log.info('Синхронизация с GitHub...')
    try:
        subprocess.run(['git', 'add', 'subscriptions/'], cwd=REPO_DIR, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', f'Auto: {datetime.now():%Y-%m-%d %H:%M}'], cwd=REPO_DIR, check=True, capture_output=True)
        subprocess.run(['git', 'push', CFG['git_remote'], CFG['git_branch']], cwd=REPO_DIR, check=True, capture_output=True)
        log.info('✓ Запушено в GitHub')
        return True
    except subprocess.CalledProcessError as e:
        log.error(f'Git push failed: {e.stderr.decode() if e.stderr else e}')
        return False


def save_local(name, config):
    ts = datetime.now().strftime('%d.%m.%Y %H:%M')
    SUBS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SUBS_DIR / f'{name}.txt', 'w', encoding='utf-8') as f:
        f.write(config + '\n')
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {name}: config ({len(config)} bytes)\n')


def main():
    banner()
    names = ask_names()
    print(f"\n{RED}▶{END} Создаю конфиги для: {BOLD}{', '.join(names)}{END}\n")

    results = {}
    for name in names:
        config = get_one_config(name)
        if config:
            results[name] = config
            save_local(name, config)

    print(f"\n{RED}{'═' * 48}{END}")
    print(f"{BOLD}{WHITE} РЕЗУЛЬТАТ{END}")
    print(f"{RED}{'═' * 48}{END}\n")

    if not results:
        print(f"{RED}✗ Ничего не создано{END}\n")
        return

    for name, config in results.items():
        print(f"{GREEN}•{END} {BOLD}{name}{END}: {WHITE}{CFG['render_url']}/sub/{name}{END}")

    print(f"\n{GREEN}✓{END} Успешно: {BOLD}{len(results)}/{len(names)}{END}")
    if push_to_github():
        print(f"{CYAN}→{END} Сервер обновится через ~40 сек")
    else:
        print(f"{YELLOW}⚠{END} Ошибка пуша в GitHub")
    print(f"\n{RED}{'═' * 48}{END}\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f'\n{YELLOW}Прервано{END}\n')
