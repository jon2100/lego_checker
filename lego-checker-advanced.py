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
    for pattern in ['/tmp/lego_*.html', '/tmp/lego_*.txt']:
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
            with open(f'/tmp/lego_{product_name}.html', 'w') as f:
                f.write(html)
            with open(f'/tmp/lego_{product_name}.txt', 'w') as f:
                f.write(f"Title: {title}\n\n{body_text[:10000]}")

            await context.close()
            await browser.close()

            # Check if blocked
            if 'cloudflare' in body_text.lower() or 'verify you are human' in body_text.lower():
                return 'BLOCKED', None, None

            # Check status
            text_lower = body_text.lower()

            if 'available now' in text_lower or 'add to bag' in text_lower:
                status = 'AVAILABLE'
            elif 'pre-order' in text_lower:
                status = 'PRE_ORDER'
            elif 'coming soon' in text_lower:
                status = 'COMING_SOON'
            elif 'backorder' in text_lower:
                status = 'BACKORDER'
            elif 'retired' in text_lower:
                status = 'RETIRED'
            elif 'temporarily out of stock' in text_lower:
                status = 'TEMP_OUT'
            elif 'sold out' in text_lower:
                status = 'SOLD_OUT'
            else:
                status = 'UNKNOWN'

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
            print(f"    ✗ Error: {error}")
        elif status == 'BLOCKED':
            print(f"    🛑 Cloudflare blocked - check /tmp/lego_{product_name}.txt")
        else:
            emoji = {'AVAILABLE':'✅','PRE_ORDER':'📅','COMING_SOON':'🔜','BACKORDER':'⏳','RETIRED':'🚫','TEMP_OUT':'⏸️','SOLD_OUT':'❌','UNKNOWN':'❓'}
            print(f"    {emoji.get(status,'?')} {status}")

            if status in ['AVAILABLE','PRE_ORDER','BACKORDER']:
                if send_email(config, f"🎉 LEGO {status} - {product_name}", f"URL: {url}\nStatus: {status}"):
                    print(f"       ✉️  Email sent")

        await asyncio.sleep(delay)


    print("\n" + "=" * 70)
    print("Check /tmp/lego_*.txt to see what was extracted")

if __name__ == '__main__':
    asyncio.run(main())
