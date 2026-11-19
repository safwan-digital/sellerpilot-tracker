#!/usr/bin/env python3
"""Small, polite scheduled price checker for public pages with accessible price metadata.
No browser fingerprint spoofing, CAPTCHA bypass, authenticated scraping or proxy rotation.
"""
import datetime as dt
import ipaddress
import json
import os
import re
import socket
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPHandler, HTTPSHandler
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = ROOT / 'config' / 'watchlist.json'
OUTPUT = ROOT / 'docs' / 'latest.json'
HISTORY = ROOT / 'docs' / 'history.json'
USER_AGENT = 'SellerPilotPriceWatch/0.2 (+scheduled public-price metadata checker)'
MAX_PRODUCTS = 100
MAX_BYTES = 1_000_000


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def public_url(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None, 443):
        return False
    host = parsed.hostname.lower().strip('.')
    if host in ('localhost', 'localhost.localdomain') or host.endswith(('.local', '.internal', '.localhost')):
        return False
    try:
        for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


class NoRedirect(HTTPHandler, HTTPSHandler):
    pass


# Prevent redirect targets from unexpectedly switching hosts (or entering private networks).
from urllib.request import HTTPRedirectHandler
class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect not followed; verify the canonical product URL')


OPENER = build_opener(RejectRedirects())


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}
        self.jsonld = []
        self._is_jsonld = False
        self._chunks = []
        self.title = ''
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta':
            key = (a.get('property') or a.get('name') or a.get('itemprop') or '').lower()
            if key and a.get('content'):
                self.meta.setdefault(key, a['content'].strip())
        if tag == 'script' and 'ld+json' in (a.get('type') or '').lower():
            self._is_jsonld = True
            self._chunks = []
        if tag == 'title':
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == 'script' and self._is_jsonld:
            self.jsonld.append(''.join(self._chunks))
            self._is_jsonld = False
        if tag == 'title':
            self._in_title = False

    def handle_data(self, data):
        if self._is_jsonld:
            self._chunks.append(data)
        if self._in_title:
            self.title += data


def parse_price(value):
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        s = re.sub(r'[^\d.,]', '', str(value))
        if not s:
            return None
        if ',' in s and '.' in s:
            decimal = ',' if s.rfind(',') > s.rfind('.') else '.'
            s = s.replace('.' if decimal == ',' else ',', '').replace(decimal, '.')
        elif ',' in s:
            parts = s.split(',')
            s = s.replace(',', '.') if len(parts) == 2 and len(parts[-1]) <= 2 else s.replace(',', '')
        elif s.count('.') == 1 and len(s.split('.')[-1]) == 3 and len(s.split('.')[0]) <= 3:
            s = s.replace('.', '')
        try:
            number = float(s)
        except ValueError:
            return None
    return round(number, 2) if 0 < number < 1e12 else None


def collect_offers(node, output):
    if isinstance(node, list):
        for entry in node:
            collect_offers(entry, output)
    elif isinstance(node, dict):
        types = node.get('@type', [])
        types = [types] if isinstance(types, str) else types
        if any(str(t).lower() == 'product' for t in types):
            offers = node.get('offers', [])
            offers = offers if isinstance(offers, list) else [offers]
            for offer in offers:
                if isinstance(offer, dict):
                    price = parse_price(offer.get('price', offer.get('lowPrice')))
                    currency = str(offer.get('priceCurrency', '')).upper()
                    if price is not None and re.fullmatch(r'[A-Z]{3,6}', currency):
                        output.append((price, currency, 'JSON-LD Product offers'))
        for key in ('@graph', 'mainEntity'):
            if key in node:
                collect_offers(node[key], output)


def extract_price(html, expected_currency=''):
    page = PageParser()
    page.feed(html)
    candidates = []
    for raw in page.jsonld:
        try:
            collect_offers(json.loads(raw), candidates)
        except (ValueError, TypeError):
            continue
    price = page.meta.get('product:price:amount') or page.meta.get('og:price:amount') or page.meta.get('price')
    currency = (page.meta.get('product:price:currency') or page.meta.get('og:price:currency') or expected_currency or '').upper()
    if price and re.fullmatch(r'[A-Z]{3,6}', currency):
        parsed = parse_price(price)
        if parsed is not None:
            candidates.append((parsed, currency, 'HTML metadata'))
    if expected_currency:
        candidates = [c for c in candidates if c[1] == expected_currency]
    if not candidates:
        return None
    return candidates[0]


def read_page(url):
    if not public_url(url):
        raise ValueError('URL must be a public HTTPS product page')
    parsed = urlparse(url)
    robots_url = f'{parsed.scheme}://{parsed.netloc}/robots.txt'
    robots = RobotFileParser()
    robots.set_url(robots_url)
    try:
        robots.read()
    except Exception as exc:
        raise ValueError('Could not verify robots.txt permissions') from exc
    if not robots.can_fetch(USER_AGENT, url):
        raise ValueError('robots.txt disallows automated access')
    request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'})
    with OPENER.open(request, timeout=12) as response:
        content_type = response.headers.get_content_type()
        if content_type not in ('text/html', 'application/xhtml+xml'):
            raise ValueError('Response is not HTML')
        html = response.read(MAX_BYTES + 1)
        if len(html) > MAX_BYTES:
            raise ValueError('Page exceeds 1 MB safety limit')
        charset = response.headers.get_content_charset() or 'utf-8'
        return html.decode(charset, errors='replace')


def main():
    data = json.loads(WATCHLIST.read_text(encoding='utf8'))
    products = data.get('products', [])
    if not isinstance(products, list) or len(products) > MAX_PRODUCTS:
        raise ValueError('watchlist.products must be a list with at most 100 entries')
    previous = json.loads(HISTORY.read_text(encoding='utf8')) if HISTORY.exists() else {'schema_version': 1, 'products': []}
    old = {p['url']: p for p in previous.get('products', []) if isinstance(p, dict) and 'url' in p}
    results = []
    histories = []
    for entry in products:
        if not isinstance(entry, dict) or not isinstance(entry.get('url'), str):
            continue
        url = entry['url']
        title = str(entry.get('title') or url)[:250]
        currency = str(entry.get('currency') or '').upper()
        checked_at = utc_now()
        result = {'url': url, 'title': title, 'checked_at': checked_at, 'status': 'error'}
        try:
            if not re.fullmatch(r'[A-Z]{3,6}', currency):
                raise ValueError('Missing/invalid expected currency code')
            page = read_page(url)
            offer = extract_price(page, currency)
            if not offer:
                raise ValueError('No matching product price metadata found')
            price, currency, source = offer
            result.update(status='ok', price=price, currency=currency, source=source)
            print(f'OK {urlparse(url).hostname}: {currency} {price}')
        except (ValueError, HTTPError, URLError, TimeoutError, OSError) as exc:
            result['error'] = str(exc)[:180]
            print(f'SKIPPED {urlparse(url).hostname}: {result["error"]}')
        results.append(result)
        history = old.get(url, {'url': url, 'checks': []})
        if result['status'] == 'ok':
            history['checks'].append({'checked_at': checked_at, 'price': result['price'], 'currency': currency, 'source': result['source']})
        history['checks'] = history['checks'][-120:]
        histories.append(history)
        time.sleep(0.5)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({'schema_version': 1, 'generated_at': utc_now(), 'products': results}, indent=2, ensure_ascii=False)+'\n', encoding='utf8')
    HISTORY.write_text(json.dumps({'schema_version': 1, 'products': histories}, indent=2, ensure_ascii=False)+'\n', encoding='utf8')
    print(f'Finished: {sum(p["status"]=="ok" for p in results)} of {len(results)} prices found')
    return 0


if __name__ == '__main__':
    sys.exit(main())
