#!/usr/bin/env python3

import os
import sys
import time
import random
import string
import re
import json
import logging
import subprocess
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

# Цвета для консоли
RED, GREEN, YELLOW, CYAN, WHITE = '\033[91m', '\033[92m', '\033[93m', '\033[96m', '\033[97m'
BOLD, DIM, END = '\033[1m', '\033[2m', '\033[0m'

BASE = Path(__file__).parent
REPO_DIR = Path('/data/data/com.termux/files/home/vpn_sun')

# Загружаем настройки
with open(BASE / 'config.json', 'r') as f:
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
{RED}║{END} {BOLD}{WHITE}       VPN BOT • HAPP TRIAL           {END}{RED}║{END}
{RED}╚══════════════════════════════════════════╝{END}
""")


def ask_count():
    while True:
        try:
            n = int(input(f'{RED}[?]{END} Сколько ссылок создать? {DIM}(1-10){END}: ').strip())
            if 1 <= n <= 10:
                return n
            print(f'{YELLOW}[!]{END} Введи 1-10')
        except (ValueError, KeyboardInterrupt, EOFError):
            return 1


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


def register(email, drv):
    try:
        log.info('Загрузка сайта power-vps...')
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
        if not loaded:
            log.error('Не загрузилось')
            return None
        time.sleep(3)

        # Ищем кнопку E-mail
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
                
        if not clicked:
            log.error('Кнопка E-mail не найдена')
            return None
        time.sleep(3)

        # Заполняем форму
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
            
        if filled == 0:
            log.error('Поля не заполнены')
            return None

        # Отправляем
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
        log.info(f'URL: {url}')
        
        if 's.powerhost.pro/' not in url:
            return None
        return url
    except Exception as e:
        log.error(f'Register error: {e}')
        return None


def get_one_link(idx, total):
    print(f"\n{RED}{'━' * 48}{END}")
    print(f"{BOLD}{WHITE} ССЫЛКА {idx}/{total}{END}")
    print(f"{RED}{'━' * 48}{END}\n")

    email, account, provider = create_email()
    if not email:
        log.error('Почта не создана')
        return None

    drv = make_driver()
    try:
        link = register(email, drv)
    finally:
        try: drv.quit()
        except: pass

    if link:
        print(f"\n{GREEN}✓{END} {BOLD}{link}{END}\n")
    else:
        log.error('Не получено')
    return link


def push_to_github(links):
    if not REPO_DIR.exists():
        log.warning(f'Repo {REPO_DIR} не найден, пропускаю push')
        return False
    
    log.info('Обновляю alive_configs.txt в репозитории...')
    config_path = REPO_DIR / 'alive_configs.txt'
    
    # Записываем ссылки (каждую с новой строки)
    with open(config_path, 'w', encoding='utf-8') as f:
        for l in links:
            f.write(l + '\n')
            
    try:
        subprocess.run(['git', 'add', 'alive_configs.txt'], cwd=REPO_DIR, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', f'Auto: {len(links)} links {datetime.now():%Y-%m-%d %H:%M}'], cwd=REPO_DIR, check=True, capture_output=True)
        subprocess.run(['git', 'push', CFG['git_remote'], CFG['git_branch']], cwd=REPO_DIR, check=True, capture_output=True)
        log.info(f'✓ Запушено {len(links)} ссылок в GitHub')
        return True
    except subprocess.CalledProcessError as e:
        log.error(f'Git push failed: {e.stderr.decode() if e.stderr else e}')
        return False


def save_local(links):
    ts = datetime.now().strftime('%d.%m.%Y %H:%M')
    with open(BASE / 'happ_link.txt', 'w', encoding='utf-8') as f:
        f.write(f'Дата: {ts}\nВсего: {len(links)}\n\n')
        for i, l in enumerate(links, 1):
            f.write(f'[{i}] {l}\n')
    with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
        for l in links:
            f.write(f'[{ts}] {l}\n')


def main():
    banner()
    try:
        count = ask_count()
    except KeyboardInterrupt:
        print(f'\n{YELLOW}Отменено{END}')
        return

    print(f"\n{RED}▶{END} Создаю {BOLD}{count}{END} ссылк{'у' if count == 1 else 'и' if count < 5 else 'ек'}...\n")

    links = []
    for i in range(1, count + 1):
        link = get_one_link(i, count)
        if link:
            links.append(link)

    print(f"\n{RED}{'═' * 48}{END}")
    print(f"{BOLD}{WHITE} РЕЗУЛЬТАТ{END}")
    print(f"{RED}{'═' * 48}{END}\n")

    if not links:
        print(f"{RED}✗ Ни одной ссылки не создано{END}\n")
        return

    for i, l in enumerate(links, 1):
        print(f"{GREEN}{i}.{END} {WHITE}{l}{END}")

    print(f"\n{GREEN}✓{END} Успешно: {BOLD}{len(links)}/{count}{END}")
    save_local(links)

    log.info('Синхронизация с GitHub...')
    pushed = push_to_github(links)

    if pushed:
        print(f"{CYAN}→{END} Сервер обновится через ~40 сек")
        print(f"{CYAN}→{END} Твоя подписка: {WHITE}{CFG['render_url']}/sub{END}\n")
    else:
        print(f"{YELLOW}⚠{END} Не удалось запушить в GitHub (проверь токен)\n")
        
    print(f"{RED}{'═' * 48}{END}\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f'\n{YELLOW}Прервано{END}\n')
