// Mockups only (never shipped): the deck page on computers laid out like a deck in the デッキ tab
window.__mock2 = (kind, side) => {
  const cur = deckState.current, view = document.getElementById('deckView'), body = document.getElementById('deckBody');
  const css = document.createElement('style');
  css.textContent = `
  #deckView.wrap { max-width: 1280px; }
  .mk-dg { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 24px; align-items: start; }
  .mk-side { position: sticky; top: calc(var(--stick-top, 0px) + 12px); max-height: calc(100vh - var(--stick-top, 0px) - 24px); overflow-y: auto;
    padding: 12px; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; display: flex; flex-direction: column; gap: 8px; }
  .mk-stabs { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 2px; padding: 3px; border-radius: var(--btn-r); background: var(--surface-2); flex: none; }
  .mk-stabs span { display: flex; align-items: center; justify-content: center; gap: 4px; min-height: 36px; border-radius: var(--btn-r-s); font-size: 13px; font-weight: 700; color: var(--text-2); }
  .mk-stabs span small { font-weight: 500; font-size: 11px; opacity: .75; }
  .mk-stabs span.on { background: var(--accent); color: var(--accent-ink); }
  .mk-side .dls-row { padding: 8px 10px; }
  .mk-side .dls-1 { font-size: 13.5px; } .mk-side .dls-2 { font-size: 11.5px; }
  .mk-side .deck-section { margin: 0; }
  .mk-side .deck-mu h2, .mk-side .deck-mv h2 { font-size: 15px; }
  .mk-side .mu-row { grid-template-columns: minmax(0, 1fr) 90px 38px !important; }
  .mk-side .mu-rec { display: none; }
  .mk-side .mu-axis { display: none; }
  .mk-tile { padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--page); flex: none; }
  .mk-tile h3 { margin: 0 0 8px; font-size: 13px; font-weight: 800; }
  .mk-tile .deck-section, .mk-tile .deck-curve { margin: 0 !important; }
  .mk-tile h2 { display: none; }
  .mk-tile .deck-sub { display: none; }
  .mk-tile .trend-chart { width: 100%; height: auto; }
  .mk-tile .mu-sum { margin: 0; }
  .mk-main .deck-head .deck-cost { margin-top: 8px; }
  .mk-strip .dlp-tile { width: 140px; }
  `;
  document.head.appendChild(css);
  const grid = document.createElement('div'); grid.className = 'mk-dg';
  const aside = document.createElement('aside'); aside.className = 'mk-side';
  const main = document.createElement('div'); main.className = 'mk-main';
  view.insertBefore(grid, view.firstChild); grid.append(aside, main); main.append(view.querySelector('.back-row'), body);
  const tabs = body.querySelector('.deck-tabs');
  const listPane = body.querySelector('.deck-pane[data-pane="list"]');
  listPane.hidden = false;
  body.querySelectorAll('.deck-pane:not([data-pane="list"])').forEach(p => p.hidden = true);
  if (kind === 'A') {
    // A: the left panel holds the sample lists (and 相性 / 増減 / 推移 as its tabs); the deck always on the right
    tabs.remove(); const bar = body.querySelector('.deck-pick-bar'); if (bar) bar.remove();
    const tab = (k, label, small) => `<span class="${k === side ? 'on' : ''}">${label}${small ? `<small>${small}</small>` : ''}</span>`;
    aside.innerHTML = `<div class="mk-stabs">${tab('list', 'リスト', cur.choices.length)}${tab('mu', '相性')}${tab('mv', '増減')}${tab('trend', '推移')}</div>`;
    if (side === 'list') {
      aside.insertAdjacentHTML('beforeend', cur.choices.map((c, i) => {
        const b = listBits(c), on = i === cur.pick;
        return `<button type="button" class="dls-row${on ? ' current' : ''}"><span class="dls-1"><b>${esc(b.top)}</b>${b.date ? `<span class="dls-date">${esc(b.date)}</span>` : ''}${b.yen ? `<span class="dls-yen">${esc(b.yen)}</span>` : ''}</span><span class="dls-2">${esc(b.sub)}</span></button>`;
      }).join(''));
    } else {
      const sec = document.querySelector(side === 'mu' ? '.deck-mu' : side === 'mv' ? '.deck-mv' : '.deck-trend');
      if (sec) { sec.closest('.deck-pane').hidden = false; aside.appendChild(sec); }
    }
  } else {
    // B: the left panel is a 統計-like column (price, Arena, curve, share, matchups); lists stay a strip above the deck
    const tile = (h, el) => { const d = document.createElement('section'); d.className = 'mk-tile'; d.innerHTML = `<h3>${h}</h3>`; if (el) d.appendChild(el); aside.appendChild(d); return d; };
    const cost = body.querySelector('.deck-cost');
    if (cost) tile('価格・MTGアリーナ', cost);
    const curve = body.querySelector('.deck-curve'); if (curve) tile('マナカーブ', curve);
    const tr = document.querySelector('.deck-trend'); if (tr) { tr.closest('.deck-pane').hidden = false; tile('使用率の推移', tr); }
    const sum = document.querySelector('.deck-mu .mu-sum'); if (sum) tile('相性', sum.cloneNode(true));
    const mv = document.querySelector('.deck-mv'); if (mv) { const ups = [...mv.querySelectorAll('.mv-col.up .mv-row')].slice(0, 4); const ul = document.createElement('ul'); ul.className = 'mv-list'; ups.forEach(u => ul.appendChild(u.cloneNode(true))); tile('最近増えたカード', ul); }
    tabs.querySelectorAll('[data-dtab="trend"]').forEach(b => b.remove());
    body.querySelector('.deck-pick-bar').classList.add('mk-strip');
  }
  window.scrollTo(0, 0);
};
