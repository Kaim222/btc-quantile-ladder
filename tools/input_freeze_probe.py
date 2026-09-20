"""One short headless run of the live site with Alex's saved settings. Times every keystroke. Hard stop at 90 seconds."""
import sys, time, json, threading, os
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://kaim222.github.io/btc-quantile-ladder/"
threading.Timer(90, lambda: (print("HARD STOP at 90s", flush=True), os._exit(3))).start()
SAVED = {"bql_gap_fade": '"slow"', "bql_lk_day": "2026-12-18", "bql_lk_view": '"both"', "bql_mstx_decay": '"measured"',
         "lookupDate": "2028-01-21", "bql_mstr_details": "true"}
INIT = "try{sessionStorage.setItem('bql_ok','1');" + "".join("localStorage.setItem(%s,%s);" % (json.dumps(k), json.dumps(v)) for k, v in SAVED.items()) + """}catch(e){}
window.__long=[];try{new PerformanceObserver(l=>{for(const e of l.getEntries())window.__long.push(Math.round(e.duration))}).observe({entryTypes:['longtask']})}catch(e){}"""

def longs(page, label):
    v = page.evaluate("(() => { const a = window.__long.slice(); window.__long.length = 0; return a; })()")
    print("  %-34s long tasks %d, worst %d ms, total %d ms" % (label, len(v), max(v or [0]), sum(v)), flush=True)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    try:
        page = b.new_page(viewport={"width": 1280, "height": 900}); page.set_default_timeout(8000)
        page.add_init_script(INIT)
        page.on("pageerror", lambda e: print("  PAGE ERROR", str(e)[:200], flush=True))
        t = time.time(); page.goto(URL, wait_until="load"); page.wait_for_timeout(4000)
        print("loaded in %.1fs" % (time.time() - t), flush=True); longs(page, "load")
        for tab in ["Ladder", "Strategy", "Playbook"]:
            t = time.time()
            try:
                page.get_by_role("button", name=tab, exact=False).first.click(); page.wait_for_timeout(1500)
            except Exception as e:
                print("  tab", tab, "click failed", str(e)[:120], flush=True); continue
            print("TAB %s in %.1fs, dom nodes %d" % (tab, time.time() - t, page.evaluate("document.querySelectorAll('*').length")), flush=True); longs(page, "open " + tab)
            inputs = page.locator("input:visible")
            n = inputs.count()
            for i in range(n):
                el = inputs.nth(i)
                try:
                    typ = el.get_attribute("type") or "text"; lab = el.get_attribute("aria-label") or el.get_attribute("placeholder") or ""
                    if typ in ("range", "password", "checkbox"): continue
                    if typ == "date":
                        for v in ["2028-01-01", "0002-01-01", "0202-01-01", "20280-01-01", "2027-06-18"]:
                            t = time.time(); el.fill(v) if len(v) == 10 else el.evaluate("(e,v)=>{const s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(e,v);e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}))}", v)
                            page.wait_for_timeout(250); dt = time.time() - t - 0.25
                            if dt > 0.3: print("  SLOW date %s -> %.2fs  [%s #%d %s]" % (v, dt, tab, i, lab), flush=True)
                    else:
                        el.click(); el.press("Control+a"); el.press("Delete")
                        for ch in "1500000":
                            t = time.time(); el.press(ch); dt = time.time() - t
                            if dt > 0.3: print("  SLOW key '%s' -> %.2fs  [%s #%d %s] value now %s" % (ch, dt, tab, i, lab, el.input_value()), flush=True)
                        el.press("Control+a"); el.press("Delete");
                        for ch in "0.5":
                            t = time.time(); el.press(ch); dt = time.time() - t
                            if dt > 0.3: print("  SLOW key '%s' -> %.2fs  [%s #%d %s]" % (ch, dt, tab, i, lab), flush=True)
                        el.press("Control+a"); el.press("Delete")
                    longs(page, "%s input #%d %s %s" % (tab, i, typ, lab[:14]))
                except Exception as e:
                    print("  input #%d on %s failed: %s" % (i, tab, str(e)[:160]), flush=True)
        print("done", flush=True)
    finally:
        b.close()
os._exit(0)
