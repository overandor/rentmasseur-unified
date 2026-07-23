#!/usr/bin/env python3
"""Quick screenshot of rentmasseur login page to diagnose what's there."""
import time, os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

opts = Options()
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--window-size=1280,900")

driver = webdriver.Chrome(options=opts)
try:
    driver.set_page_load_timeout(90)
    driver.get("https://rentmasseur.com/login")
    time.sleep(10)
    
    # Screenshot
    shot_path = "/Users/alep/Downloads/rentmasseur-optimizer/login_screenshot.png"
    driver.save_screenshot(shot_path)
    print(f"Screenshot saved: {shot_path}")
    
    # Dump page source
    html_path = "/Users/alep/Downloads/rentmasseur-optimizer/login_page.html"
    with open(html_path, "w") as f:
        f.write(driver.page_source)
    print(f"HTML saved: {html_path}")
    
    # List all inputs
    inputs = driver.execute_script("""
        return Array.from(document.querySelectorAll('input')).map(i => ({
            type: i.type, name: i.name, id: i.id, placeholder: i.placeholder,
            class: i.className, visible: i.offsetParent !== null
        }));
    """)
    print(f"\nInputs found: {len(inputs)}")
    for inp in inputs:
        print(f"  type={inp['type']} name={inp['name']} id={inp['id']} placeholder={inp['placeholder']} visible={inp['visible']}")
    
    # List all buttons
    buttons = driver.execute_script("""
        return Array.from(document.querySelectorAll('button, [role="button"], input[type="submit"]')).map(b => ({
            tag: b.tagName, text: (b.innerText||b.value||'').substring(0,50), type: b.type||''
        }));
    """)
    print(f"\nButtons found: {len(buttons)}")
    for btn in buttons:
        print(f"  {btn['tag']} text={btn['text']} type={btn['type']}")
    
    # Check for iframes
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"\nIframes: {len(iframes)}")
    for i, iframe in enumerate(iframes):
        print(f"  iframe[{i}] src={iframe.get_attribute('src')} id={iframe.get_attribute('id')}")
    
    # Current URL and title
    print(f"\nURL: {driver.current_url}")
    print(f"Title: {driver.title}")
    
    # Check for CAPTCHA
    captcha = driver.execute_script("""
        const el = document.querySelector('[class*="captcha"]') || 
                   document.querySelector('[id*="captcha"]') ||
                   document.querySelector('iframe[src*="captcha"]') ||
                   document.querySelector('iframe[src*="recaptcha"]') ||
                   document.querySelector('.g-recaptcha') ||
                   document.querySelector('#g-recaptcha');
        return el ? {tag: el.tagName, id: el.id, class: el.className, src: el.src||''} : null;
    """)
    print(f"\nCAPTCHA: {captcha}")
    
finally:
    driver.quit()
