"""Offline UI legibility smoke using Chromium.set_content; no RPC/network/wallet."""
from pathlib import Path
import re
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'docs/index.html').read_text()
html=re.sub(r'<script\b[^>]*>.*?</script>','',html,flags=re.I|re.S)
html=re.sub(r'<link\b[^>]*rel="stylesheet"[^>]*>','',html,flags=re.I)
css=(ROOT/'docs/styles.css').read_text()
js=(ROOT/'docs/readability.js').read_text()
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    for name,w,h in [('desktop',1440,900),('iphone',390,844),('small',320,690)]:
        page=browser.new_page(viewport={'width':w,'height':h},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(html)
        page.add_style_tag(content=css)
        page.add_script_tag(content=js)
        page.locator('#fontToggle').click()
        assert page.locator('html').get_attribute('data-font-size')=='large'
        page.locator('#translateHelp').click()
        assert page.locator('#translatePanel').is_visible()
        page.locator('#closeTranslatePanel').click()
        assert not page.locator('#translatePanel').is_visible()
        assert page.locator('html').get_attribute('lang')=='vi'
        assert page.title() == 'GUARDIAN 360 — LOCAL BETA | NOT AUDITED | V2.4.1'
        assert page.locator('.beta-banner').is_visible()
        assert page.locator('.audit-badge').inner_text() == 'NOT AUDITED'
        copy=page.locator('.footer-copyright')
        assert copy.inner_text() == '© 2026 @SpaceAIFinance. All rights reserved.'
        assert copy.is_visible()
        rect=copy.bounding_box()
        assert abs((rect['x']+rect['width']/2)-w/2)<10, (name,rect,w)
        dims=page.evaluate('({sw:document.documentElement.scrollWidth, cw:document.documentElement.clientWidth})')
        assert dims['sw']<=dims['cw']+1,(name,dims)
        page.screenshot(path=str(ROOT/'qa'/f'ui-v241-{name}.png'),full_page=False)
        assert not errors, errors
        print(name,'PASS',dims)
        page.close()
    browser.close()
