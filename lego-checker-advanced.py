#!/usr/bin/env python3
"""
LEGO Stock Checker - Firefox headless with anti-detection
Uses Firefox instead of Chromium for better stealth in headless mode
"""

import asyncio
import smtplib
import os
import glob
import configparser
from email.mime.text import MIMEText
from datetime import datetime
from playwright.async_api import async_playwright

CONFIG_FILE = "lego-config.ini"
URL_FILE = "lego-urls.txt"

def cleanup_temp_files():
    """Clean up old log files from the logs directory"""
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    for pattern in ['logs/lego_*.html', 'logs/lego_*.txt']:
        for f in glob.glob(pattern):
            try:
                os.remove(f)
            except:
                pass

def load_config():
    config = configparser.ConfigParser()
    defaults = {
        'email': {
            'recipient': 'jdhwiz@gmail.com',
            'smtp_server': 'localhost',
            'from_address': 'lego-checker@localhost'
        },
        'settings': {
            'check_delay': '15',
            'page_wait': '20',
            'timeout': '60'
        }
    }
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    else:
        config.read_dict(defaults)
    return config

def load_urls():
    if not os.path.exists(URL_FILE):
        return []
    with open(URL_FILE) as f:
        urls = []
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append((line, line_num))
        return urls

def get_product_name(url):
    parts = url.rstrip('/').split('/')
    return parts[-1] if parts else url

async def check_lego_status(url, page_wait=20):
    """Simple check - just be patient"""

    async with async_playwright() as p:
        # Launch browser with stealth settings for headless mode
        browser = await p.firefox.launch(
            headless=True,
            firefox_user_prefs={
                'dom.webdriver.enabled': False,
                'useAutomationExtension': False,
                'general.platform.override': 'Linux x86_64',
                'general.useragent.override': 'Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
            }
        )

        # Create context with realistic settings
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0',
            locale='en-US',
            timezone_id='America/New_York',
        )

        # Add extra headers
        await context.set_extra_http_headers({
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        page = await context.new_page()

        try:
            print(f"    Loading...")
            await page.goto(url, timeout=60000, wait_until='domcontentloaded')

            print(f"    Waiting {page_wait}s for content...")
            await page.wait_for_timeout(page_wait * 1000)

            body_text = await page.inner_text('body')
            title = await page.title()

            product_name = get_product_name(url)
            html = await page.content()
            with open(f'logs/lego_{product_name}.html', 'w') as f:
                f.write(html)
            with open(f'logs/lego_{product_name}.txt', 'w') as f:
                f.write(f"Title: {title}\n\n{body_text[:10000]}")

            await context.close()
            await browser.close()

            # Check if blocked
            if 'cloudflare' in body_text.lower() or 'verify you are human' in body_text.lower():
                return 'BLOCKED', None, None

            # Check status - prioritize specific statuses over generic "available"
            text_lower = body_text.lower()

            # Debug: find what status indicators are present
            found_indicators = []
            indicators = {
                'retired': 'retired',
                'coming soon': 'coming soon',
                'sold out': 'sold out',
                'out of stock': 'out of stock',
                'temporarily out of stock': 'temporarily out of stock',
                'pre-order': 'pre-order',
                'backorder': 'backorder',
                'available now': 'available now',
                'add to bag': 'add to bag',
                'notify me': 'notify me',
            }

            for key, label in indicators.items():
                if key in text_lower:
                    found_indicators.append(label)

            # Check in priority order (most specific first)
            if 'retired' in text_lower or 'no longer available' in text_lower:
                status = 'RETIRED'
            elif 'coming soon' in text_lower and 'add to bag' not in text_lower:
                status = 'COMING_SOON'
            elif 'sold out' in text_lower:
                status = 'SOLD_OUT'
            elif 'temporarily out of stock' in text_lower:
                status = 'TEMP_OUT'
            elif 'out of stock' in text_lower and 'notify me' in text_lower:
                status = 'OUT_OF_STOCK'
            elif 'pre-order' in text_lower:
                status = 'PRE_ORDER'
            elif 'backorder' in text_lower:
                status = 'BACKORDER'
            elif 'add to bag' in text_lower or 'available now' in text_lower:
                status = 'AVAILABLE'
            else:
                status = 'UNKNOWN'

            # Save debug info
            with open(f'logs/lego_{product_name}_debug.txt', 'w') as f:
                f.write(f"Status: {status}\n")
                f.write(f"Found indicators: {', '.join(found_indicators) if found_indicators else 'none'}\n")

            return status, title, None

        except Exception as e:
            try:
                await context.close()
                await browser.close()
            except:
                pass
            return None, None, str(e)

def send_email(config, subject, body):
    recipient = config['email']['recipient']
    smtp_server = config['email']['smtp_server']
    from_addr = config['email']['from_address']

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = recipient


    try:
        with smtplib.SMTP(smtp_server) as smtp:
            smtp.send_message(msg)
        return True
    except:
        return False

async def main():
    cleanup_temp_files()

    config = load_config()
    urls = load_urls()

    if not urls:
        print(f"No URLs. Add to {URL_FILE}")
        return

    delay = int(config['settings']['check_delay'])
    page_wait = int(config['settings']['page_wait'])

    print(f"LEGO Checker - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Checking {len(urls)} products (patient mode)")
    print("=" * 70)

    for url, line_num in urls:
        product_name = get_product_name(url)
        print(f"\n[{line_num}] {product_name}")

        status, title, error = await check_lego_status(url, page_wait)

        if error:
            print(f"    ERROR: {error}")
        elif status == 'BLOCKED':
            print(f"    BLOCKED: Cloudflare blocked - check logs/lego_{product_name}.txt")
        else:
            print(f"    STATUS: {status}")

            # Read debug info to show what was found
            try:
                with open(f'logs/lego_{product_name}_debug.txt', 'r') as f:
                    debug_lines = f.readlines()
                    if len(debug_lines) > 1:
                        print(f"    Found: {debug_lines[1].strip().replace('Found indicators: ', '')}")
            except:
                pass

            if status in ['AVAILABLE','PRE_ORDER','BACKORDER']:
                if send_email(config, f"LEGO {status} - {product_name}", f"URL: {url}\nStatus: {status}"):
                    print(f"    Email sent")

        await asyncio.sleep(delay)


    print("\n" + "=" * 70)
    print("Check logs/lego_*.txt to see what was extracted")

if __name__ == '__main__':
    asyncio.run(main())
