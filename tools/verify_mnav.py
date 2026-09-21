"""Headless site acceptance with a hard 90 second process tree deadline."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(tempfile.gettempdir()) / 'mnav-browser-check'
OUT.mkdir(exist_ok=True)


def kill():
    subprocess.run(['taskkill', '/PID', str(os.getpid()), '/T', '/F'], capture_output=True)


def main():
    timer = threading.Timer(90, kill)
    timer.daemon = True
    timer.start()
    server = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '--bind', '127.0.0.1'],
                              cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    report = {'errors': [], 'widths': {}, 'slowest_key_seconds': 0}
    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for width in (1280, 390):
                    page = browser.new_page(viewport={'width': width, 'height': 900})
                    page.set_default_timeout(12000)
                    page.on('pageerror', lambda err: report['errors'].append(str(err)))
                    page.add_init_script("sessionStorage.setItem('bql_ok','1');localStorage.setItem('bql_tab','mstr');")
                    page.goto('http://127.0.0.1:8765', wait_until='domcontentloaded')
                    page.get_by_text('PROJECTED PRICE', exact=True).wait_for()
                    page.wait_for_timeout(3500)
                    card = page.get_by_text('PROJECTED PRICE', exact=True).locator('..')
                    inputs = card.locator('input')
                    for i, value in enumerate(('81526.74', '155.77', '19.20', '98.7')):
                        inputs.nth(i).fill(value)
                    page.wait_for_timeout(100)
                    snapshots = {'81526.74': card.inner_text()}
                    # Check the actual card prices against the source data, including the 2x link.
                    cfg = json.loads((ROOT/'data/mstr-config.json').read_text())
                    model = json.loads((ROOT/'data/mstr-model.json').read_text())
                    def check_card(bitcoin):
                        body = card.inner_text()
                        nav = float(re.search(r'that mNAV times \$([\d,.]+)', body)[1].replace(',', ''))
                        fit = cfg['fit']
                        base = min(2, fit['a']+fit['b']*(bitcoin-75000)/2500+fit['c']*(100-98.7))
                        want = nav*base*(1+model['premium']['average'])
                        actual = float(re.search(r'FAIR VALUE MSTR\n\$([\d,.]+)',body)[1].replace(',', ''))
                        fund = float(re.search(r'FAIR VALUE MSTX\n\$([\d,.]+)',body)[1].replace(',', ''))
                        assert abs(actual-want)<.02, (actual,want)
                        assert abs(fund-19.2*(1+2*(actual/155.77-1)))<.01
                        return re.search(r'VERDICT\n(\w+)',body)[1]
                    verdict = check_card(81526.74)
                    for value in ('85000', '150000'):
                        inputs.nth(0).fill(value)
                        snapshots[value] = card.inner_text()
                        assert check_card(float(value)) == verdict
                    inputs.nth(0).fill('200000')
                    assert 'Fair value mNAV 2.00' in card.inner_text()
                    cap_text = card.inner_text()
                    cap_price = float(re.search(r'FAIR VALUE MSTR\n\$([\d,.]+)', cap_text)[1].replace(',', ''))
                    cap_nav = float(re.search(r'that mNAV times \$([\d,.]+)', cap_text)[1].replace(',', ''))
                    premium = json.loads((ROOT/'data/mstr-model.json').read_text())['premium']
                    assert abs(cap_price - 2*cap_nav*(1+premium['average'])) <= .02
                    inputs.nth(0).fill('')
                    keys = []
                    for digit in '150000':
                        start = time.perf_counter()
                        inputs.nth(0).press(digit)
                        page.evaluate('() => new Promise(requestAnimationFrame)')
                        keys.append(time.perf_counter() - start)
                    report['slowest_key_seconds'] = max(report['slowest_key_seconds'], *keys)
                    assert inputs.nth(0).input_value().replace(',', '') == '150000'
                    tabs = {}
                    for label in ('STRATEGY', 'LADDER', 'PLAYBOOK'):
                        page.get_by_role('button', name=re.compile('^'+label+'$', re.I)).click()
                        if label == 'STRATEGY':
                            page.get_by_role('button', name='show monitor, alerts and history', exact=True).click()
                        # Expansion can expose another more button, so continue until all are open.
                        for _ in range(60):
                            more = page.get_by_role('button', name='more', exact=True)
                            visible = [b for b in more.all() if b.is_visible()]
                            if not visible:
                                break
                            visible[0].click()
                        text = page.locator('body').inner_text()
                        (OUT / f'{width}-{label}.txt').write_text(text, encoding='utf-8')
                        hits = [line for line in text.splitlines() if re.search(r'rule|formula|0\.90|0\.025', line, re.I)]
                        punctuation = [line for line in text.splitlines() if re.search(r'[;()]|(?<!\d):(?!\d)|(?<!\d)[\-\u2010-\u2015\u2212](?!\$?\d)', line)]
                        size = page.evaluate('({width:innerWidth, scroll:document.documentElement.scrollWidth})')
                        sentences = [line for line in text.splitlines() if line.endswith('.')]
                        prose = [line for line in sentences if len(line.split()) > 20 or len(re.findall(r'(?<!\d),|,(?!\d)', line)) > 1]
                        tabs[label] = dict(size=size, hits=hits, punctuation=punctuation, prose=prose)
                        page.screenshot(path=str(OUT / f'{width}-{label}.png'), full_page=True)
                    report['widths'][str(width)] = dict(cards=snapshots, keys=keys, tabs=tabs)
                    assert all(t['size']['scroll'] <= width for t in tabs.values()), tabs
                    assert all(not t['hits'] and not t['punctuation'] and not t['prose'] for t in tabs.values()), tabs
                    assert max(keys) < .3, keys
                    page.close()
                assert not report['errors'], report['errors']
            finally:
                browser.close()
                browser = None
    finally:
        server.terminate()
        server.wait(timeout=5)
        timer.cancel()
        (OUT / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
