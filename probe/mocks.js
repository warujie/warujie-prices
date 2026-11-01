// Mock-ups of UX ideas drawn over the real test site (a throwaway probe; nothing here is the site's code)
window.mkArt = id => `https://cards.scryfall.io/art_crop/front/${id[0]}/${id[1]}/${id}.jpg`;
window.mkRow = en => LOCAL_DB.find(r => r.name_en === en);
window.mkStyle = css => { const s = document.createElement('style'); s.textContent = css; document.head.appendChild(s); };
// 1. a stat clicked: the deck shows only those cards
window.mockHighlight = () => {
  const byName = new Map(LOCAL_DB.map(r => [r.name_en, r]));
  const col = [...document.querySelectorAll('#impPaneStats .st-cv')].find(c => c.querySelector('.st-cvv').textContent.trim() === '2');
  if (col) { col.style.outline = '2px solid var(--accent)'; col.style.outlineOffset = '3px'; col.style.borderRadius = '6px'; col.style.background = 'var(--hl)'; }
  let n = 0;
  document.querySelectorAll('#importBody .imp-card').forEach(c => {
    const b = c.querySelector('[data-in]'); const r = b && byName.get(b.dataset.in);
    const hit = r && Math.round(r._cmc) === 2 && !/Land/.test(r.type_en) && b.dataset.ip === 'main';
    if (hit) n += Number((c.querySelector('.dc-count') || { textContent: '1' }).textContent.replace(/\D/g, '')) || 1;
    else c.style.opacity = '.16';
  });
  const sec = document.querySelector('#importBody .deck-section');
  sec.insertAdjacentHTML('beforebegin', `<div style="display:flex;align-items:center;gap:10px;margin:0 0 14px;padding:9px 12px;border-radius:12px;background:var(--hl);color:var(--text);font-size:14px">`
    + `<b>マナ総量 2</b><span>のカード ${n}枚だけを表示中（統計の数字・種類・色を押すと絞れます）</span>`
    + `<span style="margin-left:auto;padding:5px 10px;border-radius:8px;background:var(--surface-2)">✕ 全部表示</span></div>`);
};
// 2. quick add: type "4 いなず", Enter adds to the main deck
window.mockQuickAdd = () => {
  mkStyle(`.mk-qa{position:relative;margin:0 0 16px}.mk-qa-box{display:flex;align-items:center;gap:10px;height:46px;padding:0 14px;border:1px solid var(--accent);border-radius:12px;background:var(--field);font-size:16px;color:var(--text)}
  .mk-qa-box i{font-style:normal;color:var(--muted);margin-left:auto;font-size:12.5px}.mk-qa-box b{color:var(--accent);font-weight:700}
  .mk-sugg{position:absolute;left:0;right:0;top:50px;z-index:5;margin:0;padding:6px;list-style:none;border-radius:12px;background:var(--surface);box-shadow:var(--shadow);border:1px solid var(--line)}
  .mk-sugg li{display:flex;align-items:center;gap:10px;padding:6px 8px;border-radius:8px;font-size:14px;color:var(--text)}.mk-sugg li.on{background:var(--hl)}
  .mk-sugg img{width:46px;height:34px;object-fit:cover;border-radius:5px}.mk-sugg small{color:var(--muted);font-size:12px;display:block}.mk-sugg em{margin-left:auto;font-style:normal;font-size:12.5px;color:var(--muted)}
  .mk-sugg li.on em{color:var(--text)}`);
  const rows = ['Lightning Bolt', 'Lightning Axe', 'Chain Lightning', 'Lightning Helix'].map(mkRow).filter(Boolean);
  const sec = document.querySelector('#importBody .deck-section');
  sec.insertAdjacentHTML('beforebegin', `<div class="mk-qa"><div class="mk-qa-box"><span style="color:var(--muted)">＋</span><span>4 いなず<span style="border-left:2px solid var(--text);margin-left:1px"></span></span>`
    + `<i>Enter でメインへ ・「SB 2 …」でサイドボードへ ・ ↑↓ で選ぶ</i></div><ul class="mk-sugg">`
    + rows.map((r, i) => `<li class="${i ? '' : 'on'}"><img src="${mkArt(r.id)}" alt=""><span>${r.name_ja || r.name_en}<small>${r.name_en} ・ ${r.type_ja || r.type_en}</small></span><em>${i ? '' : '4枚をメインへ ⏎'}</em></li>`).join('')
    + `</ul></div>`);
};
// 3. phones: hold a card to see it big
window.mockHold = () => {
  const tile = document.querySelectorAll('#importBody a.deck-card')[1];
  const img = tile.querySelector('img');
  const src = (img.currentSrc || img.src).replace(/\/(small|normal|large)\//, '/normal/');
  const r = tile.getBoundingClientRect();
  document.body.insertAdjacentHTML('beforeend', `<div style="position:fixed;inset:0;z-index:95;background:rgba(0,0,0,.62);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px">`
    + `<img src="${src}" style="width:78vw;max-width:340px;aspect-ratio:488/680;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.6)">`
    + `<span style="color:#fff;font-size:14px;background:rgba(0,0,0,.4);padding:6px 12px;border-radius:8px">指を離すと閉じます ・ そのままタップでカードのページ</span></div>`
    + `<span style="position:fixed;z-index:96;left:${r.left + r.width / 2 - 22}px;top:${r.top + r.height / 2 - 22}px;width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,.35);border:2px solid rgba(255,255,255,.8)"></span>`);
};
// 4. the peek with the card's price and formats under the picture
window.mockPeekInfo = (en) => {
  const p = document.getElementById('cardPeek'); if (!p || p.hidden) return 'no peek';
  const a = document.querySelector('#importBody a.deck-card:hover') || document.querySelectorAll('#importBody a.deck-card')[3];
  const id = a.dataset.card; const r = LOCAL_DB.find(x => x.id === id) || mkRow(a.title);
  const yen = (a.querySelector('.dc-yen') || { textContent: '' }).textContent;
  const F = [['s', 'St'], ['p', 'Pi'], ['m', 'Mo'], ['l', 'Lg'], ['v', 'Vt'], ['a', 'Pa'], ['c', 'Cm']];
  const leg = r ? String(r.legal || '') : '';
  p.style.flexDirection = 'column';
  p.insertAdjacentHTML('beforeend', `<div style="width:250px;box-sizing:border-box;padding:10px 12px;border-radius:12px;background:var(--surface);border:1px solid var(--line);box-shadow:var(--shadow);color:var(--text);font-size:13px">`
    + `<div style="display:flex;justify-content:space-between;align-items:baseline"><span style="color:var(--muted)">この版</span><b style="font-size:15px">${yen || '¥—'}</b></div>`
    + `<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:3px"><span style="color:var(--muted)">いちばん安い版</span><b style="color:var(--ok)">${yen ? '¥' + Math.max(10, Math.round(Number(yen.replace(/[^\d]/g, '')) * 0.62 / 10) * 10).toLocaleString() : '¥—'}</b></div>`
    + `<div style="display:flex;gap:4px;margin-top:9px">${F.map(([k, l]) => `<span style="flex:1;text-align:center;font-size:11px;padding:3px 0;border-radius:5px;${leg.includes(k) ? 'background:var(--ok-bg);color:var(--ok)' : 'background:var(--surface-2);color:var(--muted);text-decoration:line-through'}">${l}</span>`).join('')}</div></div>`);
  return 'ok';
};
