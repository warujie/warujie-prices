// A mock-up of the planned deck builder tools, drawn on the test site's real pages (preview only; nothing is saved)
window.MOCK = (() => {
  const JA = LANG !== 'en';
  const L = (ja, en) => JA ? ja : en;
  const yen = y => '¥' + Math.round(y).toLocaleString('ja-JP');
  const items = () => { const r = importState.result; return r.commander.concat(r.main); };
  const rowOf = it => (it.info && it.info.row) || rowByEnglishName(it.name);
  const lab = it => { const r = rowOf(it); return JA && r && r.name_ja ? r.name_ja.split(' // ')[0] : it.name; };
  const liOf = it => [...document.querySelectorAll('#importBody .deck-section:not(.mk-maybe) .dl-row')].find(l => ((l.querySelector('.dl-name') || {}).textContent || '').includes(it.name));
  const typeOf = row => String((row && row.type_en) || '').toLowerCase();
  const isLand = row => /\bland\b/.test(typeOf(row)) && !/creature/.test(typeOf(row));
  const isPerm = row => /creature|artifact|enchantment|planeswalker|battle/.test(typeOf(row));
  const TYPES = [['creature', 'クリーチャー', 'Creatures'], ['instant', 'インスタント', 'Instants'], ['sorcery', 'ソーサリー', 'Sorceries'],
    ['artifact', 'アーティファクト', 'Artifacts'], ['enchantment', 'エンチャント', 'Enchantments'], ['planeswalker', 'PW', 'Planeswalkers'], ['land', '土地', 'Lands']];
  const BASIC = { Plains: 'W', Island: 'U', Swamp: 'B', Mountain: 'R', Forest: 'G' };
  const COLS = 'WURBG'.split('');
  const pipImg = c => symbolImg(c, 'sym');
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  async function ready() {
    await dbReady; await loadTags(); await loadCheapest();
    for (let i = 0; i < 40 && !document.querySelector('.want-bar'); i++) await sleep(250);
  }
  const anchor = () => document.querySelector('#importBody .want-bar') || document.querySelector('#importBody .deck-head');
  function stats() {
    const its = items();
    const curve = [0, 1, 2, 3, 4, 5, 6].map(() => [0, 0]);
    const types = new Map(), need = {}, src = {};
    let mvSum = 0, mvN = 0, lands = 0, noArena = 0;
    const wc = { m: 0, r: 0, u: 0, c: 0 };
    COLS.forEach(c => { need[c] = 0; src[c] = 0; });
    its.forEach(it => {
      const row = rowOf(it); if (!row) return;
      const n = it.count || 0, ty = typeOf(row);
      const k = TYPES.find(([id]) => ty.includes(id)); if (k) types.set(k[0], (types.get(k[0]) || 0) + n);
      const cr = cheapRow(row.name_en, row);
      if (cr && cr[2]) wc[cr[2]] = (wc[cr[2]] || 0) + n; else if (!BASIC[row.name_en]) noArena += n;
      if (isLand(row)) {
        lands += n;
        const t = String(row.oracle_en || '');
        const any = /any colou?r/i.test(t) || /search your library for a (basic )?land/i.test(t);
        COLS.forEach(c => { if (BASIC[row.name_en] === c || any || t.includes(`{${c}}`) || new RegExp(`\\b${Object.keys(BASIC).find(b => BASIC[b] === c)}\\b`).test(t)) src[c] += n; });
        return;
      }
      curve[Math.min(6, Math.floor(row.cmc || 0))][isPerm(row) ? 1 : 0] += n;
      mvSum += (row.cmc || 0) * n; mvN += n;
      (String(row.mana_cost || '').match(/\{[^}]+\}/g) || []).forEach(s => COLS.forEach(c => { if (s.includes(c)) need[c] += n; }));
    });
    return { curve, types, need, src, avg: mvN ? mvSum / mvN : 0, lands, wc, noArena };
  }
  function statsHtml(s, arena) {
    const top = Math.max(1, ...s.curve.map(([a, b]) => a + b));
    const bars = s.curve.map(([sp, pm], v) => `<span class="mk-cv"><span class="mk-cvn">${sp + pm || ''}</span>`
      + `<span class="mk-cvb"><i class="pm" style="height:${pm / top * 100}%"></i><i class="sp" style="height:${sp / top * 100}%"></i></span><span class="mk-cvv">${v === 6 ? '6+' : v}</span></span>`).join('');
    const types = TYPES.filter(([id]) => s.types.get(id)).map(([id, ja, en]) => `<li><span>${L(ja, en)}</span><b>${s.types.get(id)}</b></li>`).join('');
    const needT = COLS.reduce((a, c) => a + s.need[c], 0) || 1;
    const colors = COLS.filter(c => s.need[c]).map(c => `<li>${pipImg(c)}<span class="mk-two"><span class="mk-bar"><i style="width:${s.need[c] / needT * 100}%;background:var(--mana-${c.toLowerCase()})"></i></span>`
      + `<span class="mk-bar src"><i style="width:${s.lands ? s.src[c] / s.lands * 100 : 0}%;background:var(--mana-${c.toLowerCase()})"></i></span></span><span class="mk-num">${Math.round(s.need[c] / needT * 100)}%<small>${s.src[c]}${L('枚', '')}</small></span></li>`).join('');
    const ar = false ? `<div class="mk-tile"><h3>${L('MTGアリーナ', 'MTG Arena')}</h3><ul class="mk-wc">${[['m', L('神話', 'Mythic'), 'var(--rar-mythic)'], ['r', L('レア', 'Rare'), 'var(--rar-rare)'], ['u', L('アンコモン', 'Uncommon'), 'var(--rar-uncommon)'], ['c', L('コモン', 'Common'), 'var(--rar-common)']]
      .map(([k, n, col]) => `<li><i style="background:${col}"></i>${n}<b>${s.wc[k] || 0}</b></li>`).join('')}</ul>${s.noArena ? `<p class="mk-warn">${L(`アリーナにないカード ${s.noArena}枚`, `${s.noArena} cards not on Arena`)}</p>` : ''}</div>` : '';
    return `<section class="mk-stats"><div class="mk-tile mk-curve"><h3>${L('マナカーブ', 'Mana curve')}<small>${L('平均', 'avg')} ${s.avg.toFixed(2)}</small></h3><div class="mk-cvs">${bars}</div>`
      + `<p class="mk-key"><i class="sp"></i>${L('呪文', 'Spells')}<i class="pm"></i>${L('パーマネント', 'Permanents')}</p></div>`
      + `<div class="mk-tile"><h3>${L('カードの種類', 'Card types')}</h3><ul class="mk-types">${types}</ul></div>`
      + `<div class="mk-tile"><h3>${L('色', 'Colours')}<small>${L('上：呪文のシンボル　下：その色が出る土地', 'top: symbols · bottom: lands')}</small></h3><ul class="mk-colors">${colors}</ul></div>${ar}</section>`;
  }
  // the bar: 並べ方 and サンプル手札 beside リスト / 画像
  function barTools() {
    const l = document.querySelector('#importBody .mk-stats') || anchor();
    if (!l || document.querySelector('.mk-viewbar')) return;
    l.insertAdjacentHTML('afterend', `<div class="mk-viewbar">` + `<label class="mk-sort"><span>${L('並べ方', 'Group')}</span><select class="adv-btn"><option>${L('種類別', 'By type')}</option><option>${L('マナ総量別', 'By mana value')}</option><option>${L('色別', 'By colour')}</option></select></label>`
      + `<label class="mk-sort"><select class="adv-btn"><option>${L('マナ総量順', 'Mana value')}</option><option>${L('名前順', 'Name')}</option><option>${L('価格順', 'Price')}</option></select></label>`
      + `<button type="button" class="adv-btn mk-hand-btn">${L('サンプル手札', 'Sample hand')}</button></div>`);
  }
  function sectionAfter(sel, html) { const s = [...document.querySelectorAll('#importBody .deck-section')].filter(x => !x.classList.contains('deck-curve')); s[s.length - 1].insertAdjacentHTML('afterend', html); }
  function maybeboard(names) {
    const side = [...document.querySelectorAll('#importBody .deck-section')].find(s => !s.classList.contains('deck-curve') && s.querySelector('.dl-row'));
    const sample = side.querySelector('.dl-row');
    const rows = names.map(n => {
      const row = rowByEnglishName(n); const li = sample.cloneNode(true);
      const a = li.querySelector('.dl-name'); a.innerHTML = `${esc(JA && row && row.name_ja ? row.name_ja : n)}${JA ? `<small>${esc(n)}</small>` : ''}`;
      li.querySelector('.dl-cost').innerHTML = row && row.mana_cost ? renderPips(row.mana_cost.split(' // ')[0]) : '';
      const y = row && rowPriceYen(row); li.querySelector('.dl-yen').textContent = y ? yenSmall(y) : '';
      const c = li.querySelector('.want-c'); if (c) c.textContent = L('1枚', '1');
      return li.outerHTML;
    }).join('');
    sectionAfter('', `<section class="deck-section mk-maybe"><h2>${L('考慮中', 'Maybeboard')}<span class="dg-n">${L(`${names.length}枚 · 価格・枚数・判定に含めません`, `${names.length} cards · not counted`)}</span></h2><ul class="dl">${rows}</ul></section>`);
  }
  const TOKEN_JA = { Treasure: '宝物', Food: '食物', Clue: '手掛かり', Blood: '血', Soldier: '兵士', Spirit: 'スピリット', Zombie: 'ゾンビ', Goblin: 'ゴブリン', Elf: 'エルフ', Warrior: '戦士',
    Human: '人間', Saproling: '苗木', Insect: '昆虫', Thopter: '飛行機械', Servo: '霊気装置', Construct: '構築物', Beast: 'ビースト', Squirrel: 'リス', Faerie: 'フェアリー', Elemental: 'エレメンタル', Angel: '天使', Dragon: 'ドラゴン', Bird: '鳥', Cat: '猫', Rat: 'ネズミ', Shard: '破片', Map: '地図', Powerstone: '力線石', Gold: '金' };
  function tokens() {
    const found = new Map();
    items().forEach(it => {
      const t = String((rowOf(it) || {}).oracle_en || '');
      const re = /create[sd]? (?:a|an|one|two|three|four|five|x|that many|\d+) (?:tapped )?(?:(\d+\/\d+) )?((?:white|blue|black|red|green|colorless)(?: and (?:white|blue|black|red|green))? )?((?:[A-Z][a-z]+ )+)?(?:artifact |enchantment )*(?:creature )?tokens?/g;
      let m; while ((m = re.exec(t))) {
        const kind = (m[3] || '').trim().split(' ').pop() || ''; if (!kind) continue;
        const key = `${m[1] || ''} ${kind}`.trim();
        if (!found.has(key)) found.set(key, { pt: m[1] || '', kind, col: (m[2] || '').trim(), from: lab(it) });
      }
    });
    return [...found.values()].slice(0, 8);
  }
  function tokensHtml(list) {
    if (!list.length) return '';
    const colJa = { white: '白', blue: '青', black: '黒', red: '赤', green: '緑', colorless: '無色' };
    return `<section class="deck-section mk-tokens"><h2>${L('トークン', 'Tokens')}<span class="dg-n">${L(`${list.length}種類 · 対戦に持っていくもの`, `${list.length} kinds to bring`)}</span></h2><ul class="mk-tok">${list.map(x =>
      `<li><b>${esc(JA ? (TOKEN_JA[x.kind] || x.kind) : x.kind)}</b><span>${esc([x.pt, JA ? x.col.split(' and ').map(c => colJa[c] || c).join('・') : x.col].filter(Boolean).join(' · ') || L('アーティファクト', 'artifact'))}</span><small>${esc(x.from)}</small></li>`).join('')}</ul></section>`;
  }
  async function builder({ arena = true, maybe = [] } = {}) {
    await ready();
    const s = stats();
    document.querySelector('.deck-curve') && document.querySelector('.deck-curve').remove();
    anchor().insertAdjacentHTML('afterend', statsHtml(s, arena)); barTools();
    const wc = document.querySelector('.want-bar .dcst-wc');
    if (arena && wc && s.noArena) wc.insertAdjacentHTML('beforeend', `<span class="mk-na big">${L(`アリーナにない ${s.noArena}枚`, `${s.noArena} not on Arena`)}</span>`);
    if (maybe.length) maybeboard(maybe);
    sectionAfter('', tokensHtml(tokens()));
    // not on Arena: a small mark on those rows
    if (arena) importState.result.main.concat(importState.result.side).forEach(it => {
      const row = rowOf(it); const cr = row && cheapRow(row.name_en, row); const li = liOf(it);
      if (li && row && !(cr && cr[2]) && !BASIC[row.name_en]) li.querySelector('.dl-name').insertAdjacentHTML('beforeend', `<span class="mk-na">${L('アリーナなし', 'not on Arena')}</span>`);
    });
  }
  // ---- sample hand ----
  function hand(seed = 7) {
    const pool = [];
    importState.result.main.forEach(it => { for (let i = 0; i < it.count; i++) pool.push(it); });
    let x = seed; const rnd = () => (x = (x * 9301 + 49297) % 233280) / 233280;
    for (let i = pool.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [pool[i], pool[j]] = [pool[j], pool[i]]; }
    const h = pool.slice(0, 7), next = pool[7];
    const lands = h.filter(it => isLand(rowOf(it))).length;
    const card = (it, cls = '') => { const row = rowOf(it); return `<span class="mk-hc ${cls}"><img src="${trayPic(row, 'normal')}" alt="${esc(lab(it))}"></span>`; };
    document.body.insertAdjacentHTML('beforeend', `<div class="mk-dim"></div><div class="mk-hand" role="dialog"><div class="mk-hh"><h2>${L('サンプル手札', 'Sample hand')}</h2>`
      + `<span class="mk-hs">${L(`手札7枚 · 土地${lands}枚 · ライブラリー残り${pool.length - 8}枚`, `7 cards · ${lands} lands · ${pool.length - 8} left`)}</span><button class="adv-btn mk-x">×</button></div>`
      + `<div class="mk-hcards">${h.map(it => card(it)).join('')}${card(next, 'drawn')}</div>`
      + `<div class="mk-hbtns"><button class="adv-btn primary">${L('新しい手札', 'New hand')}</button><button class="adv-btn">${L('マリガン（6枚）', 'Mulligan (6)')}</button><button class="adv-btn">${L('1枚引く', 'Draw a card')}</button><span class="mk-turn">${L('3ターン目まで引いた様子：右端が次に引くカード', 'The card at the right is your next draw')}</span></div></div>`);
  }
  // ---- Commander only ----
  const GC = new Set(['Rhystic Study', 'Cyclonic Rift', 'Smothering Tithe', 'The One Ring', 'Demonic Tutor', 'Vampiric Tutor', 'Mana Vault', 'Ancient Tomb', 'Fierce Guardianship', "Jeska's Will",
    "Teferi's Protection", 'Craterhoof Behemoth', 'Drannith Magistrate', "Gaea's Cradle", 'Grim Monolith', 'Enlightened Tutor', 'Mystical Tutor', 'Worldly Tutor', 'Imperial Seal', 'Chrome Mox',
    'Mox Diamond', 'Force of Will', 'Mana Drain', 'Necropotence', 'Bolas\'s Citadel', 'Seedborn Muse', 'Narset, Parter of Veils', 'Opposition Agent', 'Orcish Bowmasters', 'Underworld Breach',
    'Thassa\'s Oracle', 'Notion Thief', 'Survival of the Fittest', 'Trouble in Pairs', 'The Tabernacle at Pendrell Vale', 'Glacial Chasm', 'Serra\'s Sanctum', 'Coalition Victory', 'Expropriate',
    'Jin-Gitaxias, Core Augur', 'Vorinclex, Voice of Hunger', 'Urza, Lord High Artificer', 'Kinnan, Bonder Prodigy', 'Yuriko, the Tiger\'s Shadow', 'Winota, Joiner of Forces', 'Humility', 'Biorhythm',
    'Field of the Dead', 'Intuition', 'Gamble', 'Grand Arbiter Augustin IV', 'Consecrated Sphinx', 'Panoptic Mirror', 'Tergrid, God of Fright', 'Braids, Cabal Minion', 'Gifts Ungiven', 'Lion\'s Eye Diamond']);
  async function combos(names) {
    const oracles = new Set(names.map(n => (rowByEnglishName(n) || {}).oracle_id).filter(Boolean));
    const seen = new Map();
    for (const o of oracles) {
      const sh = await loadComboShard(o.slice(0, 2));
      combosFor(sh, o).forEach(c => { if (!seen.has(c.id)) seen.set(c.id, c); });
    }
    const have = [], near = [];
    seen.forEach(c => {
      if (c.templates.length || !c.cards.length) return;
      const miss = c.cards.filter(k => !oracles.has(k.oracle));
      if (!miss.length) have.push(c); else if (miss.length === 1) near.push(Object.assign(c, { miss: miss[0] }));
    });
    const by = (a, b) => b.popularity - a.popularity;
    return { have: have.sort(by), near: near.sort(by) };
  }
  const cname = k => esc(JA && k.row && k.row.name_ja ? k.row.name_ja.split(' // ')[0] : k.name);
  async function commander() {
    await ready();
    const s = stats();
    document.querySelector('.deck-curve') && document.querySelector('.deck-curve').remove();
    anchor().insertAdjacentHTML('afterend', statsHtml(s, false)); barTools();
    const its = items();
    const count = id => its.reduce((a, it) => { const r = rowOf(it); return a + (r && !isLand(r) && hasRole(r, id) ? it.count : 0); }, 0);
    const roles = [[L('土地', 'Lands'), s.lands, 36, 38, ''], [L('マナ加速', 'Ramp'), count('ramp'), 10, 12, 'ramp'], [L('ドロー', 'Card draw'), count('draw'), 10, 12, 'draw'],
      [L('除去', 'Removal'), count('removal'), 8, 10, 'removal'], [L('全体除去', 'Board wipes'), count('boardwipe'), 2, 4, 'boardwipe'], [L('除去対策', 'Protection'), count('protection'), 3, 5, 'protection']];
    const roleHtml = roles.map(([n, v, lo, hi]) => { const st = v < lo ? 'low' : v > hi ? 'high' : 'ok';
      return `<li class="${st}"><span>${n}</span><span class="mk-bar"><i style="width:${Math.min(100, v / hi * 100)}%"></i><em style="left:${lo / hi * 100}%"></em></span><b>${v}</b><small>${L(`目安 ${lo}〜${hi}`, `aim ${lo}–${hi}`)}</small><span class="mk-go">${st === 'low' ? L('探す →', 'Find →') : st === 'ok' ? '✓' : ''}</span></li>`; }).join('');
    const names = its.map(it => it.name);
    const gc = its.filter(it => GC.has((rowOf(it) || {}).name_en));
    const cb = await combos(names);
    const bracket = cb.have.some(c => true) ? 3 : gc.length ? 3 : 2;
    const comboLi = (c, near) => `<li>${c.cards.map(k => `<span class="combo-chip${near && k === c.miss ? ' mk-miss' : ''}">${near && k === c.miss ? '＋ ' : ''}${cname(k)}</span>`).join('<span class="mk-plus">+</span>')}`
      + `<small>${esc((JA ? c.results_ja : c.results).slice(0, 2).join(' · '))}</small></li>`;
    const html = `<section class="mk-cmd"><div class="mk-tile mk-roles"><h3>${L('統率者デッキのチェック', 'Commander checklist')}<small>${L('役割タグで数えた目安', 'counted by role tags')}</small></h3><ul>${roleHtml}</ul></div>`
      + `<div class="mk-tile mk-br"><h3>${L('ブラケット', 'Bracket')}</h3><p class="mk-big">${bracket}<small>${L(bracket === 2 ? 'コア（構築済み相当）' : 'アップグレード', bracket === 2 ? 'Core' : 'Upgraded')}</small></p>`
      + `<p>${L('ゲームチェンジャー', 'Game Changers')} <b>${gc.length}${L('枚', '')}</b>${gc.length ? `：${gc.map(it => esc(lab(it))).join('、')}` : ''}</p><p>${L('2枚で揃うコンボ', 'Two-card combos')} <b>${cb.have.filter(c => c.cards.length === 2).length}</b></p><p class="mk-dim2">${L('ゲームチェンジャー・コンボ・追加ターンから判定', 'From Game Changers, combos, extra turns')}</p></div>`
      + `<div class="mk-tile mk-cb"><h3>${L('コンボ', 'Combos')}<small>Commander Spellbook</small></h3>`
      + `<p class="mk-sub">${L(`このデッキにある ${cb.have.length}`, `In this deck: ${cb.have.length}`)}</p><ul>${cb.have.slice(0, 2).map(c => comboLi(c, false)).join('') || `<li class="mk-dim2">${L('なし', 'None')}</li>`}</ul>`
      + `<p class="mk-sub">${L(`あと1枚 ${cb.near.length}`, `One card away: ${cb.near.length}`)}</p><ul>${cb.near.slice(0, 3).map(c => comboLi(c, true)).join('')}</ul></div></section>`;
    document.querySelector('.mk-viewbar').insertAdjacentHTML('beforebegin', html);
    sectionAfter('', tokensHtml(tokens()));
    // cheaper alternatives for the most expensive nonland card
    await buildSimIndex();
    const priced = importState.result.main.map(it => ({ it, row: rowOf(it) })).filter(x => x.row && !isLand(x.row)).map(x => Object.assign(x, { y: rowPriceYen(x.row) || 0 })).sort((a, b) => b.y - a.y);
    const target = priced[0];
    const cols = new Set(its.flatMap(it => String((rowOf(it) || {}).colors || '').split('')));
    const inDeck = new Set(names);
    const alts = similarTo(target.row, 400).map(x => x.row).filter(r => r && !inDeck.has(r.name_en) && String(r.legal || '').includes('c') && String(r.colors || '').split('').every(c => cols.has(c)))
      .map(r => ({ r, y: rowPriceYen(r) })).filter(x => x.y && x.y < target.y * 0.4).slice(0, 4);
    const li = liOf(target.it);
    if (li) {
      li.classList.add('mk-hl');
      li.querySelector('.dl-name').insertAdjacentHTML('beforeend', ` <span class="mk-alt-btn">${L('安い代わり', 'Cheaper')}</span>`);
      li.insertAdjacentHTML('afterend', `<li class="mk-alt"><p>${L(`「${esc(lab(target.it))}」(${yen(target.y)}) と同じ役割で安いカード`, `Cards with the same role for less than ${yen(target.y)}`)}</p><ul>${alts.map(x =>
        `<li><img src="${cardArtUrl(x.r.id)}" alt=""><span>${esc(JA && x.r.name_ja ? x.r.name_ja : x.r.name_en)}</span><b>${yenSmall(x.y)}</b><span class="mk-sw">${L('入れ替える', 'Swap')}</span></li>`).join('')}</ul></li>`);
      li.scrollIntoView({ block: 'center' });
    }
  }

  // ---- slim versions (the owner, 2026-10-28: "slim down all the data") ----
  async function cmdData(s) {
    const its = items();
    const count = id => its.reduce((a, it) => { const r = rowOf(it); return a + (r && !isLand(r) && hasRole(r, id) ? it.count : 0); }, 0);
    const roles = [[L('土地', 'Lands'), s.lands, 36, 38], [L('マナ加速', 'Ramp'), count('ramp'), 10, 12], [L('ドロー', 'Draw'), count('draw'), 10, 12],
      [L('除去', 'Removal'), count('removal'), 8, 10], [L('全体除去', 'Wipes'), count('boardwipe'), 2, 4], [L('除去対策', 'Protection'), count('protection'), 3, 5]];
    const gc = its.filter(it => GC.has((rowOf(it) || {}).name_en));
    const cb = await combos(its.map(it => it.name));
    return { roles, gc, cb, bracket: cb.have.length || gc.length ? 3 : 2 };
  }
  function spark(s) {
    const top = Math.max(1, ...s.curve.map(([a, b]) => a + b));
    return `<span class="mk-spark" title="${L('マナカーブ', 'Mana curve')}">${s.curve.map(([a, b], v) => `<i style="height:${Math.max(2, (a + b) / top * 100)}%" title="${v === 6 ? '6+' : v}: ${a + b}"></i>`).join('')}</span>`;
  }
  function lineHtml(s, cd) {
    const needT = COLS.reduce((a, c) => a + s.need[c], 0) || 1;
    const short = { creature: L('クリーチャー', 'Creatures'), instant: L('インスタント', 'Instants'), sorcery: L('ソーサリー', 'Sorceries'), artifact: L('アーティファクト', 'Artifacts'), enchantment: L('エンチャント', 'Enchantments'), planeswalker: 'PW', land: L('土地', 'Lands') };
    const types = TYPES.filter(([id]) => s.types.get(id)).map(([id]) => `<span>${short[id]} <b>${s.types.get(id)}</b></span>`).join('');
    const cols = COLS.filter(c => s.need[c]).map(c => `<span class="mk-c">${pipImg(c)}${Math.round(s.need[c] / needT * 100)}%</span>`).join('');
    let html = `<div class="mk-line">${spark(s)}<span class="mk-avg">${L('平均', 'avg')} <b>${s.avg.toFixed(2)}</b></span><span class="mk-dot"></span>`
      + `<span class="mk-ty">${types}</span><span class="mk-dot"></span><span class="mk-cols">${cols}</span>`
      + `<span class="mk-line-r"><button class="mk-link">${L('詳しく ▾', 'More ▾')}</button></span></div>`;
    if (cd) {
      const chk = cd.roles.map(([n, v, lo, hi]) => `<span class="mk-chk ${v < lo ? 'low' : 'ok'}">${n} <b>${v}</b>${v < lo ? `<small>/${lo}</small>` : ''}</span>`).join('');
      html += `<div class="mk-line mk-line2"><span class="mk-lbl">${L('統率者', 'Commander')}</span>${chk}<span class="mk-dot"></span>`
        + `<span class="mk-chk">${L('ブラケット', 'Bracket')} <b>${cd.bracket}</b></span><span class="mk-chk">${L('コンボ', 'Combos')} <b>${cd.cb.have.length}</b>${cd.cb.near.length ? `<small>${L(`・あと1枚 ${cd.cb.near.length}`, ` · ${cd.cb.near.length} one away`)}</small>` : ''}</span></div>`;
    }
    return html;
  }
  function barSlim() {
    const l = document.querySelector('.want-bar .want-bar-l');
    if (!l) return;
    l.insertAdjacentHTML('beforeend', `<select class="adv-btn mk-mini" aria-label="${L('並べ方', 'Order')}"><option>${L('種類別', 'By type')}</option><option>${L('マナ総量別', 'By mana value')}</option><option>${L('色別', 'By colour')}</option><option>${L('名前順', 'By name')}</option><option>${L('価格順', 'By price')}</option></select>`
      + `<button type="button" class="adv-btn mk-mini">${L('手札を試す', 'Sample hand')}</button>`);
  }
  function tokensLine(list) {
    if (!list.length) return '';
    return `<p class="mk-tokline"><b>${L('トークン', 'Tokens')}</b>${list.map(x => `<span>${esc([x.pt, JA ? (TOKEN_JA[x.kind] || x.kind) : x.kind].filter(Boolean).join(' '))}</span>`).join('')}</p>`;
  }
  function cheaperChip() {
    const priced = importState.result.main.map(it => ({ it, row: rowOf(it) })).filter(x => x.row && !isLand(x.row)).map(x => Object.assign(x, { y: rowPriceYen(x.row) || 0 })).sort((a, b) => b.y - a.y);
    const li = priced[0] && liOf(priced[0].it);
    if (li) li.querySelector('.dl-yen').insertAdjacentHTML('afterbegin', `<span class="mk-cheap" title="${L('安い代わりを見る', 'Cheaper cards')}">${L('安く', 'Save')}</span>`);
  }
  // A: one thin line (two for Commander) under the bar; 詳しく opens the tiles
  async function slimLine({ commander: isCmd = false, maybe = [] } = {}) {
    await ready();
    const s = stats();
    document.querySelector('.deck-curve') && document.querySelector('.deck-curve').remove();
    const cd = isCmd ? await cmdData(s) : null;
    anchor().insertAdjacentHTML('afterend', lineHtml(s, cd)); barSlim();
    const wc = document.querySelector('.want-bar .dcst-wc');
    if (!isCmd && wc && s.noArena) wc.insertAdjacentHTML('beforeend', `<span class="mk-na big">${L(`アリーナなし ${s.noArena}`, `${s.noArena} not on Arena`)}</span>`);
    if (maybe.length) maybeboard(maybe);
    const last = [...document.querySelectorAll('#importBody .deck-section')].pop();
    last.insertAdjacentHTML('afterend', tokensLine(tokens()));
    if (isCmd) cheaperChip();
    scrollTo(0, 0);
  }
  // B: the numbers in a 統計 tab of the left panel (a sheet on phones); the deck side shows only the deck
  async function slimTab({ commander: isCmd = false, maybe = [], open = true } = {}) {
    await ready();
    const s = stats();
    document.querySelector('.deck-curve') && document.querySelector('.deck-curve').remove();
    const cd = isCmd ? await cmdData(s) : null;
    barSlim();
    if (maybe.length) maybeboard(maybe);
    const last = [...document.querySelectorAll('#importBody .deck-section')].pop();
    last.insertAdjacentHTML('afterend', tokensLine(tokens()));
    if (isCmd) cheaperChip();
    const tabs = document.getElementById('impTabs');
    tabs.insertAdjacentHTML('beforeend', `<button type="button" role="tab" data-pane="stats" aria-selected="false"><span>${L('統計', 'Stats')}</span>${cd && cd.roles.some(([, v, lo]) => v < lo) ? '<span class="mk-warn-dot"></span>' : ''}</button>`);
    const pb = document.getElementById('impPbar');
    const pw = document.getElementById('impPbarWant');
    if (pw) pw.insertAdjacentHTML('afterend', `<button type="button" class="adv-btn mk-pbar-stats">${L('統計', 'Stats')}</button>`);
    const roleHtml = cd ? cd.roles.map(([n, v, lo, hi]) => { const st = v < lo ? 'low' : 'ok';
      return `<li class="${st}"><span>${n}</span><span class="mk-bar"><i style="width:${Math.min(100, v / hi * 100)}%"></i><em style="left:${lo / hi * 100}%"></em></span><b>${v}</b><small>${lo}〜${hi}</small></li>`; }).join('') : '';
    const comboLi = (c, near) => `<li>${c.cards.map(k => `<span class="combo-chip${near && k === c.miss ? ' mk-miss' : ''}">${near && k === c.miss ? '＋ ' : ''}${cname(k)}</span>`).join('<span class="mk-plus">+</span>')}</li>`;
    const pane = `<div class="imp-pane mk-pane" id="impPaneStats">${statsHtml(s, false)}`
      + (cd ? `<section class="mk-cmd"><div class="mk-tile mk-roles"><h3>${L('統率者デッキのチェック', 'Commander checklist')}</h3><ul>${roleHtml}</ul></div>`
        + `<div class="mk-tile mk-br"><h3>${L('ブラケット', 'Bracket')} <b class="mk-bn">${cd.bracket}</b></h3><p>${L('ゲームチェンジャー', 'Game Changers')} <b>${cd.gc.length}</b> · ${L('2枚コンボ', 'Two-card combos')} <b>${cd.cb.have.filter(c => c.cards.length === 2).length}</b></p></div>`
        + `<div class="mk-tile mk-cb"><h3>${L('コンボ', 'Combos')}<small>${L(`あと1枚 ${cd.cb.near.length}`, `${cd.cb.near.length} one card away`)}</small></h3><ul>${cd.cb.near.slice(0, 3).map(c => comboLi(c, true)).join('')}</ul></div></section>` : '')
      + `</div>`;
    document.getElementById('impPaneText').insertAdjacentHTML('afterend', pane);
    if (open) {
      ['impPaneSearch', 'impPaneWant', 'impPaneText'].forEach(id => { document.getElementById(id).hidden = true; });
      tabs.querySelectorAll('[role=tab]').forEach(b => b.setAttribute('aria-selected', String(b.dataset.pane === 'stats')));
      if (innerWidth < 1000) setImpSheet(true);
    } else document.getElementById('impPaneStats').hidden = true;
    scrollTo(0, 0);
  }
  // ---- my decks: folders and order ----
  function decks() {
    const grid = document.getElementById('dkGrid');
    grid.insertAdjacentHTML('beforebegin', `<div class="mk-folders"><div class="mk-chips"><button class="mk-chip on">${L('すべて', 'All')} <small>4</small></button><button class="mk-chip">${L('大会用', 'Tournament')} <small>2</small></button>`
      + `<button class="mk-chip">${L('統率者', 'Commander')} <small>2</small></button><button class="mk-chip add">＋ ${L('フォルダ', 'Folder')}</button></div>`
      + `<label class="mk-sort"><span>${L('並べ替え', 'Order')}</span><select class="adv-btn"><option>${L('最近の更新順', 'Last edited')}</option><option>${L('名前順', 'Name')}</option><option>${L('フォーマット順', 'Format')}</option><option>${L('価格順', 'Price')}</option></select></label></div>`);
    grid.querySelectorAll('.dk-card:not(.dk-want)').forEach((c, i) => c.querySelector('.dk-when') && c.querySelector('.dk-when').insertAdjacentHTML('beforebegin', `<span class="mk-fold">${['大会用', '統率者', '大会用', '統率者'][i] || ''}</span>`));
  }
  return { builder, hand, commander, decks, slimLine, slimTab };
})();
