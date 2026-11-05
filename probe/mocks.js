// Mockups only (never shipped): other designs for the deck page's list picker and extra data on phones
window.__mock = (kind) => {
  const cur = deckState.current, bar = document.querySelector('#deckBody .deck-pick-bar');
  const info = cur.choices.map((c, i) => {
    const l = c.list || {};
    const cost = deckCost((c.main || []).concat(c.side || []));
    return { i, place: l.avg ? '平均' : placeShort(l.result), date: l.avg ? '' : listMd(l.date), yen: cost.priced ? yenRound(cost.yen) : '',
      ev: l.avg ? `${fmtNum(l.avg)}件のリストから` : (l.event || ''), on: i === cur.pick };
  });
  const me = info[cur.pick];
  const css = document.createElement('style');
  css.textContent = `
  .mk-chips { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; padding: 2px 0; }
  .mk-chips::-webkit-scrollbar { display: none; }
  .mk-chip { flex: none; height: 32px; padding: 0 11px; border-radius: 8px; background: var(--surface-2); display: inline-flex; align-items: center; gap: 6px; font-size: 12.5px; font-weight: 700; white-space: nowrap; }
  .mk-chip small { font-weight: 400; opacity: .75; font-size: 11px; }
  .mk-chip.on { background: var(--accent); color: var(--accent-ink); }
  .mk-cap { display: flex; align-items: center; gap: 8px; margin-top: 6px; font-size: 12px; color: var(--text-2); }
  .mk-cap span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .mk-cap a { margin-left: auto; flex: none; color: var(--accent); }
  .mk-step { display: grid; grid-template-columns: 40px minmax(0,1fr) 40px; gap: 6px; align-items: stretch; }
  .mk-step button { border: 0; border-radius: 8px; background: var(--surface-2); color: var(--text); font-size: 20px; height: 48px; }
  .mk-mid { min-width: 0; border-radius: 8px; background: var(--surface-2); padding: 5px 10px; display: flex; flex-direction: column; justify-content: center; }
  .mk-l1 { display: flex; align-items: baseline; gap: 8px; font-size: 13.5px; font-weight: 800; }
  .mk-l1 .mk-n { margin-left: auto; font-size: 11px; font-weight: 400; color: var(--muted); }
  .mk-l1 .mk-y { color: var(--accent); }
  .mk-l2 { font-size: 11.5px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .mk-dots { display: flex; justify-content: center; gap: 4px; margin-top: 6px; }
  .mk-dots i { width: 6px; height: 6px; border-radius: 3px; background: var(--line); }
  .mk-dots i.on { width: 16px; background: var(--accent); }
  .mk-sel { width: 100%; display: flex; align-items: center; gap: 10px; height: 48px; padding: 0 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); color: var(--text); text-align: left; }
  .mk-sel .mk-tx { min-width: 0; flex: 1; }
  .mk-sel .mk-ar { width: 8px; height: 8px; border-right: 2px solid var(--text-2); border-bottom: 2px solid var(--text-2); transform: rotate(45deg); margin: 0 4px 4px; }
  .mk-sheet-bg { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 90; }
  .mk-sheet { position: fixed; left: 0; right: 0; bottom: 0; max-height: 72vh; overflow: auto; z-index: 91; background: var(--surface); border-radius: 16px 16px 0 0; padding: 8px 14px 24px; }
  .mk-grab { width: 40px; height: 4px; border-radius: 2px; background: var(--line); margin: 4px auto 10px; }
  .mk-sh { font-weight: 800; font-size: 16px; margin: 0 0 8px; }
  .mk-row { display: grid; grid-template-columns: 52px minmax(0,1fr) auto; gap: 8px; align-items: center; padding: 10px 8px; border-radius: 8px; }
  .mk-row + .mk-row { border-top: 1px solid var(--line); }
  .mk-row.on { background: var(--accent); color: var(--accent-ink); border-color: transparent; }
  .mk-row b { font-size: 14px; } .mk-row .mk-e { font-size: 12px; opacity: .8; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .mk-row .mk-p { font-weight: 800; font-size: 13px; }
  .mk-tabs { display: flex; gap: 3px; padding: 3px; border-radius: 10px; background: var(--surface-2); margin: 8px 0 4px; }
  .mk-tabs span { flex: 1; text-align: center; padding: 8px 0; border-radius: 8px; font-size: 13px; font-weight: 700; color: var(--text-2); }
  .mk-tabs span.on { background: var(--accent); color: var(--accent-ink); }
  `;
  document.head.appendChild(css);
  const src = '<a>出典 ↗</a>';
  if (kind === 'A') {
    bar.innerHTML = `<div class="mk-chips">${info.map(x => `<span class="mk-chip${x.on ? ' on' : ''}">${esc(x.place)}${x.date ? `<small>${esc(x.date)}</small>` : ''}${x.yen ? `<small>${esc(x.yen)}</small>` : ''}</span>`).join('')}</div>
      <div class="mk-cap"><span>${esc(me.ev)}${me.date ? '・' + esc(me.date) : ''}</span>${src}</div>`;
    const on = bar.querySelector('.mk-chip.on'); bar.querySelector('.mk-chips').scrollLeft = on.offsetLeft - 60;
  } else if (kind === 'B') {
    bar.innerHTML = `<div class="mk-step"><button>‹</button><div class="mk-mid"><div class="mk-l1"><span>${esc(me.place)}</span><span class="mk-y">${esc(me.yen)}</span><span class="mk-n">${cur.pick + 1} / ${info.length}</span></div>
      <div class="mk-l2">${esc(me.ev)}${me.date ? '・' + esc(me.date) : ''}・出典 ↗</div></div><button>›</button></div>
      <div class="mk-dots">${info.slice(0, 9).map(x => `<i class="${x.on ? 'on' : ''}"></i>`).join('')}</div>`;
  } else if (kind === 'C' || kind === 'C2') {
    bar.innerHTML = `<button class="mk-sel"><span class="mk-tx"><div class="mk-l1"><span>${esc(me.place)}</span><span class="mk-y">${esc(me.yen)}</span><span class="mk-n">リストを選ぶ（${info.length}）</span></div><div class="mk-l2">${esc(me.ev)}${me.date ? '・' + esc(me.date) : ''}</div></span><span class="mk-ar"></span></button>`;
    if (kind === 'C2') {
      document.body.insertAdjacentHTML('beforeend', `<div class="mk-sheet-bg"></div><div class="mk-sheet"><div class="mk-grab"></div><p class="mk-sh">サンプルリスト（${info.length}）</p>${info.map(x => `<div class="mk-row${x.on ? ' on' : ''}"><b>${esc(x.place)}</b><span class="mk-e">${esc(x.ev)}${x.date ? '<br>' + esc(x.date) : ''}</span><span class="mk-p">${esc(x.yen)}</span></div>`).join('')}</div>`);
    }
  } else if (kind === 'T') {
    // tabs instead of the slide-down panel: リスト / 相性 / 増減 / 推移, 相性 chosen
    const head = document.querySelector('#deckBody .deck-head');
    head.insertAdjacentHTML('afterend', `<div class="mk-tabs"><span>リスト</span><span class="on">相性</span><span>カードの増減</span><span>推移</span></div>`);
    const mu = document.querySelector('#deckBody .deck-mu');
    document.querySelectorAll('#deckBody > *').forEach(e => { if (!e.classList.contains('deck-head') && !e.classList.contains('mk-tabs')) e.style.display = 'none'; });
    document.querySelector('#deckBody .mk-tabs').after(mu); mu.style.display = '';
  }
};
