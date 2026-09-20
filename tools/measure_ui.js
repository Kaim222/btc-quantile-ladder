async (page) => {
  const measure = () => {
    const out = { wrapped: [], sentences: [], inputsNoDollar: [] };
    const seen = new Set();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walker.nextNode())) {
      const txt = n.nodeValue.replace(/\s+/g, ' ').trim();
      if (txt.length < 2) continue;
      const el = n.parentElement; if (!el || el.closest('svg') || el.closest('script') || el.closest('style')) continue;
      let hidden = false; for (let a = el; a; a = a.parentElement) { const cs = getComputedStyle(a); if (cs.display === 'none' || cs.visibility === 'hidden') { hidden = true; break; } }
      if (hidden) continue;
      const r = document.createRange(); r.selectNodeContents(n); const rects = [...r.getClientRects()].filter(x => x.width > 1);
      if (!rects.length) continue;
      const lines = new Set(rects.map(x => Math.round(x.top))).size;
      const key = txt.slice(0, 60); if (seen.has(key)) continue; seen.add(key);
      if (lines > 1) out.wrapped.push({ lines, px: getComputedStyle(el).fontSize, t: txt.slice(0, 90) });
      for (const s of txt.split(/(?<=[.!?])\s+/)) { const w = s.split(/\s+/).length, c = (s.match(/,(?!\d)/g) || []).length; if (w > 20 || c >= 2) out.sentences.push({ w, c, t: s.slice(0, 120) }); }
    }
    for (const i of document.querySelectorAll('input')) { if (['range', 'date', 'password'].includes(i.type)) continue;
      let hidden = false; for (let a = i; a; a = a.parentElement) { if (getComputedStyle(a).display === 'none') { hidden = true; break; } } if (hidden) continue;
      const lab = (i.getAttribute('aria-label') || (i.closest('label') ? i.closest('label').innerText.split('\n')[0] : '') || '').slice(0, 30);
      const box = i.parentElement ? i.parentElement.innerText : ''; const dollar = /\$/.test(box) || /\$/.test(i.value);
      if (!dollar && !/mNAV|UNITS/i.test(lab)) out.inputsNoDollar.push(lab + ' = ' + (i.value || i.placeholder)); }
    return out;
  };
  const res = {};
  for (const [name, w, h] of [['desk', 1280, 900], ['phone', 390, 844]]) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto('http://127.0.0.1:8765/index.html', { timeout: 120000 }); await page.waitForTimeout(800);
    await page.evaluate(() => { sessionStorage.setItem('bql_ok', '1'); }); await page.reload({ timeout: 120000 }); await page.waitForTimeout(9000);
    for (const tab of ['Ladder', 'Strategy', 'Playbook']) {
      await page.evaluate(t => { [...document.querySelectorAll('button')].find(b => b.textContent.trim().toLowerCase() === t.toLowerCase()).click(); }, tab);
      await page.waitForTimeout(7000);
      res[name + '-' + tab] = await page.evaluate(measure);
      res[name + '-' + tab].bad = await page.evaluate(() => (document.body.innerText.match(/NaN|undefined|Infinity|\[object|failed to load/gi) || []).length);
      res[name + '-' + tab].overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    }
  }
  // the Ladder what-if: type 95,000 and read the instrument card
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.evaluate(() => { [...document.querySelectorAll('button')].find(b => b.textContent.trim().toLowerCase() === 'ladder').click(); }); await page.waitForTimeout(4000);
  await page.locator('input[aria-label="Bitcoin price"]').fill('95000'); await page.waitForTimeout(2500);
  res.preview95k = await page.evaluate(() => { const t = document.body.innerText; const i = t.search(/INSTRUMENT AT THIS PRICE|ACTIVE INSTRUMENT/i); return t.slice(i, i + 420).replace(/\n+/g, ' | '); });
  const hd = page.locator('text=/Instrument at this price/i').first(); const b = await hd.boundingBox(); const y0 = await page.evaluate(() => window.scrollY);
  await page.screenshot({ path: '.playwright-mcp/u4-preview95k.png', fullPage: true, clip: { x: 150, y: Math.max(0, b.y + y0 - 20), width: 980, height: 560 }, timeout: 120000 });
  return res;
}
