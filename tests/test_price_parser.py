import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_prices import extract_price, parse_price, public_url


class ParserTests(unittest.TestCase):
    def test_jsonld(self):
        html = '''<html><script type="application/ld+json">{"@type":"Product","offers":{"price":"84.99","priceCurrency":"AED"}}</script></html>'''
        self.assertEqual(extract_price(html, 'AED')[:2], (84.99, 'AED'))

    def test_metadata(self):
        html = '<meta property="product:price:amount" content="1,234.50"><meta property="product:price:currency" content="INR">'
        self.assertEqual(extract_price(html, 'INR')[:2], (1234.50, 'INR'))

    def test_currency_mismatch(self):
        html = '<meta property="product:price:amount" content="99"><meta property="product:price:currency" content="USD">'
        self.assertIsNone(extract_price(html, 'AED'))

    def test_parsing(self):
        self.assertEqual(parse_price('AED 1,999.00'), 1999.00)
        self.assertIsNone(parse_price('sold out'))

    def test_private_urls_rejected(self):
        self.assertFalse(public_url('http://localhost/item'))
        self.assertFalse(public_url('https://127.0.0.1/item'))
        self.assertFalse(public_url('file:///secret'))


if __name__ == '__main__':
    unittest.main()
