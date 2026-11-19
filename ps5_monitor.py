import json
import os
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = 'https://altex.ro/consola-playstation-5-pro-digital-edition-ps5-2tb-white/cpd/CNSPS5PRO2TB/'
PRODUCT_CODE = 'CNSPS5PRO2TB'
MAX_PRICE = 5300.0
STATE_FILE = Path('state.json')
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'ro-RO,ro;q=0.9'}


def notify(message):
    token = os.environ['TELEGRAM_BOT_TOKEN']
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    response = requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json={
        'chat_id': chat_id, 'text': message, 'disable_web_page_preview': True,
    }, timeout=20)
    response.raise_for_status()
    if not response.json().get('ok'):
        raise RuntimeError('Telegram did not accept the message')


def check():
    response = requests.get(URL, headers=HEADERS, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    for element in soup(['script', 'style', 'nav', 'footer']):
        element.decompose()
    text = re.sub(r'\s+', ' ', soup.get_text(' ', strip=True))
    code = re.search(r'cod\s+produs\s*:\s*' + PRODUCT_CODE, text, re.I)
    if not code:
        return 'UNKNOWN', None
    section = text[code.end():code.end() + 1500].lower()
    # Strict positive signals; a missing out-of-stock phrase is NOT sufficient.
    match = re.search(r'((?:\d{1,3}(?:[. ]\d{3})+|\d{4,5})[,\.]\d{2})\s*lei', section)
    price = float(match.group(1).replace('.', '').replace(' ', '').replace(',', '.')) if match else None
    if 'stoc epuizat' in section or 'indisponibil' in section:
        return 'OUT', price
    positive = any(s in section for s in ('in stoc', 'în stoc', 'adauga in cos', 'adaugă în coș'))
    if not positive or price is None:
        return 'UNKNOWN', price
    return ('IN' if price <= MAX_PRICE else 'OVER'), price


def main():
    if os.environ.get('TEST_NOTIFICATION') == 'true':
        notify('✅ Test PS5 Restock Bot: notificarea Telegram funcționează!')
        print('Test message sent')
        return

    previous = 'UNKNOWN'
    try:
        previous = json.loads(STATE_FILE.read_text(encoding='utf-8')).get('status', 'UNKNOWN')
    except (OSError, ValueError):
        pass

    status, price = check()
    print('First check:', status, price)
    if status == 'IN':
        time.sleep(12)
        confirmation, second_price = check()
        print('Confirmation:', confirmation, second_price)
        if confirmation != 'IN':
            status = 'UNKNOWN'
        else:
            price = second_price

    if status == 'UNKNOWN':
        print('Cannot verify stock. No notification or state change.')
        return
    if status == 'IN' and previous != 'IN':
        notify(f'🚨 PS5 PRO 2TB posibil în stoc la Altex!\n💰 Preț detectat: {price:.2f} lei\n🛒 {URL}\nVerifică pe site înainte de comandă.')
        print('Restock alert sent')
    else:
        print('No new availability to announce')

    STATE_FILE.write_text(json.dumps({'status': status, 'price': price}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
