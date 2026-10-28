async function fetchJSON(url, options) {
  // Include user name header when available to satisfy backend contract
  const baseHeaders = { 'Content-Type': 'application/json' };
  try {
    const name = localStorage.getItem('auth_name');
    if (name && (!options || !options.headers || !('X-User-Name' in options.headers))) {
      baseHeaders['X-User-Name'] = name;
    }
  } catch {}
  const res = await fetch(url, Object.assign({
    headers: Object.assign(baseHeaders, (options && options.headers) || {})
  }, options || {}));
  const contentType = res.headers.get('content-type') || '';
  const isJSON = contentType.includes('application/json');
  const data = isJSON ? await res.json() : await res.text();
  if (!res.ok) {
    const message = isJSON ? (data.error || JSON.stringify(data)) : String(data);
    throw new Error(message || 'Request failed');
  }
  return data;
}

// --- Gamification state and helpers ---
let userProfile = null;
let emojiCatalog = [];
// Local UI-only storage for task → emojis (since backend is out of scope)
const localTaskEmojis = new Map();

function getSpinsRemaining(profile) {
  return profile ? (profile.spins_remaining ?? profile.spinsRemaining ?? 0) : 0;
}

function setSpinsRemaining(profile, value) {
  if (!profile) return;
  if ('spins_remaining' in profile) profile.spins_remaining = value;
  else profile.spinsRemaining = value;
}

function hasPerkMultiEmoji(profile) {
  return !!(profile && (profile.has_multi_emoji ?? profile.hasMultiEmoji ?? false));
}

function profileEmojis(profile) {
  return (
    profile?.emojis ||
    profile?.inventory?.emojis ||
    profile?.emoji_inventory ||
    []
  );
}

async function loadUserProfile() {
  try {
    userProfile = await fetchJSON('/api/user/profile');
  } catch (e) {
    // If unauthorized, go to login; otherwise use demo fallback
    const msg = String(e?.message || '').toLowerCase();
    if (msg.includes('not_found') || msg.includes('unauthorized') || msg.includes('401') || msg.includes('403')) {
      try { window.location.href = '/static/login.html'; } catch {}
      return;
    }
    userProfile = { name: 'demo', spins_remaining: 5, has_multi_emoji: false, reset_info: { next_midnight_utc_offset: '+00:00' }, emojis: [] };
  }
  updateSpinsIndicator();
}

function updateSpinsIndicator() {
  const el = document.getElementById('spins-indicator');
  if (!el) return;
  const spins = getSpinsRemaining(userProfile);
  el.textContent = `Крутки: ${spins}`;
  const playBtn = document.getElementById('play-button');
  if (playBtn) playBtn.disabled = spins <= 0;
}

async function loadEmojiCatalog() {
  try {
    const raw = await fetchJSON('/api/emojis/catalog');
    emojiCatalog = Array.isArray(raw) ? raw.map(normalizeEmoji) : [];
  } catch {
    emojiCatalog = [
      normalizeEmoji({ code: 'star', version: 'v1', rarity: 'rare', display_name: 'Star', glyph: '⭐' }),
      normalizeEmoji({ code: 'fire', version: 'v1', rarity: 'common', display_name: 'Fire', glyph: '🔥' }),
      normalizeEmoji({ code: 'check', version: 'v1', rarity: 'common', display_name: 'Check', glyph: '✔️' })
    ];
  }
}

function userHasEmoji(code, version) {
  const list = profileEmojis(userProfile);
  return !!list.find(e => e.code === code && (version ? e.version === version : true));
}

function displayOrCode(emoji) {
  if (!emoji) return '';
  if (emoji.glyph) return emoji.glyph;
  if (emoji.icon_ref && !(emoji.icon_ref.includes('.') || emoji.icon_ref.startsWith('http'))) return emoji.icon_ref;
  return emoji.display_name || emoji.code || '';
}

function displayEmoji(e) {
  if (!e) return '';
  const n = normalizeEmoji(e);
  if (n.glyph) return n.glyph;
  if (n.icon_ref && !(n.icon_ref.includes('.') || n.icon_ref.startsWith('http'))) return n.icon_ref;
  const fromCat = (emojiCatalog || []).find(it => it.code === n.code && (n.version ? it.version === n.version : true));
  if (fromCat) {
    if (fromCat.glyph) return fromCat.glyph;
    if (fromCat.icon_ref && !(fromCat.icon_ref.includes('.') || fromCat.icon_ref.startsWith('http'))) return fromCat.icon_ref;
    return fromCat.display_name || fromCat.code || '';
  }
  return n.display_name || n.code || '';
}

function notify(msg) { alert(msg); }

function toISOWithOffset(s) {
  const d = new Date(s);
  const tz = -d.getTimezoneOffset();
  const sign = tz >= 0 ? '+' : '-';
  const hh = String(Math.floor(Math.abs(tz)/60)).padStart(2,'0');
  const mm = String(Math.abs(tz)%60).padStart(2,'0');
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}${sign}${hh}:${mm}`;
}
function enrichWithCurrentYear(localStr) { return localStr; }

// --- Wheel overlay ---
let currentPool = null;
let wheelSegCount = 0;
let wheelAnglePer = 0;
let wheelRotation = 0; // cumulative rotation in deg

function normalizeEmoji(e) {
  if (!e || typeof e !== 'object') return {};
  return {
    code: e.code ?? e.id ?? e.key ?? null,
    version: e.version ?? e.ver ?? 'v1',
    rarity: e.rarity ?? e.tier ?? null,
    display_name: e.display_name ?? e.displayName ?? e.name ?? null,
    icon_ref: e.icon_ref ?? e.iconUrl ?? e.image_url ?? e.icon ?? null,
    glyph: e.glyph ?? e.char ?? e.unicode ?? null,
  };
}

function normalizeSegment(seg) {
  const typeRaw = seg.type ?? seg.kind ?? seg.prize_type ?? seg.category;
  const type = String(typeRaw || '').toLowerCase();
  if (type === 'emoji' || type === 'emojis' || (seg.emoji || seg.emj)) {
    const e = normalizeEmoji(seg.emoji ?? seg.emj ?? seg.item ?? seg.value ?? {});
    return { type: 'emoji', emoji: e };
  }
  // odd/other prize
  const label = seg.label ?? seg.title ?? seg.name ?? seg.text ?? 'Приз';
  return { type: 'odd_prize', label };
}

function normalizePool(pool) {
  const segments = (pool.segments ?? pool.prizes ?? pool.items ?? []).map(normalizeSegment);
  return { segments };
}

function normalizeResult(res) {
  const t = String(res.outcome_type ?? res.type ?? res.kind ?? '').toLowerCase();
  if (t === 'emoji' || res.emoji || res.emj) {
    return {
      outcome_type: 'emoji',
      emoji: normalizeEmoji(res.emoji ?? res.emj ?? res.item ?? {}),
      duplicate: !!(res.duplicate ?? res.isDuplicate ?? res.dup),
      spins_remaining: res.spins_remaining ?? res.spinsRemaining ?? getSpinsRemaining(userProfile)
    };
  }
  return {
    outcome_type: 'odd_prize',
    label: res.label ?? res.title ?? res.message ?? 'Приз',
    spins_remaining: res.spins_remaining ?? res.spinsRemaining ?? getSpinsRemaining(userProfile)
  };
}

async function openWheel() {
  if (getSpinsRemaining(userProfile) <= 0) { openSpinsBanner(); return; }
  try {
    const raw = await fetchJSON('/api/spin/pool');
    currentPool = normalizePool(raw);
  } catch {
    currentPool = { segments: [
      { type: 'emoji', emoji: normalizeEmoji({ code: 'star', version: 'v1', rarity: 'rare', display_name: 'Star', glyph: '⭐' }) },
      { type: 'emoji', emoji: normalizeEmoji({ code: 'fire', version: 'v1', rarity: 'common', display_name: 'Fire', glyph: '🔥' }) },
      { type: 'odd_prize', label: 'Скидка на задачи' },
      { type: 'odd_prize', label: 'Участие в розыгрыше' },
      { type: 'odd_prize', label: 'Промо-код на кофе' },
      { type: 'emoji', emoji: normalizeEmoji({ code: 'check', version: 'v1', rarity: 'common', display_name: 'Check', glyph: '✔️' }) },
      { type: 'odd_prize', label: 'Бессмысленный диплом' },
      { type: 'odd_prize', label: 'Улыбка от тимлида' }
    ] };
  }
  ensureAtLeastOneEmoji(currentPool);
  renderWheel(currentPool);
  const ov = document.getElementById('wheel-overlay');
  if (ov) ov.hidden = false;
}

function ensureAtLeastOneEmoji(pool) {
  const hasEmoji = (pool.segments || []).some(s => s.type === 'emoji');
  if (!hasEmoji && pool.segments && pool.segments.length) {
    pool.segments[0] = { type: 'emoji', emoji: normalizeEmoji({ code: 'fire', version: 'v1', rarity: 'common', display_name: 'Fire', glyph: '🔥' }) };
  }
}

function renderWheel(pool) {
  const wheel = document.getElementById('wheel');
  const legend = document.getElementById('wheel-legend');
  if (!wheel || !legend) return;
  wheel.innerHTML = '';
  legend.innerHTML = '';
  // reset rotation each time we (re)render the wheel to keep pointer mapping consistent
  wheelRotation = 0;
  wheel.style.transform = 'rotate(0deg)';
  const segCount = Math.max(8, pool.segments.length);
  wheelSegCount = segCount;
  wheelAnglePer = 360 / segCount;
  (pool.segments).forEach((seg, i) => {
    const label = document.createElement('div');
    label.className = 'wheel-segment-label';
    const angle = i * wheelAnglePer + wheelAnglePer / 2;
    const center = (wheel.clientWidth || 360) / 2; // dynamic center to avoid hardcoding
    const r = Math.max(0, center - 50); // keep labels within the wheel border and under center button
    const cx = center + r * Math.cos((angle-90) * Math.PI/180);
    const cy = center + r * Math.sin((angle-90) * Math.PI/180);
    label.style.left = `${cx}px`;
    label.style.top = `${cy}px`;
    label.style.transform = `translate(-50%, -50%) rotate(${angle}deg)`;
    if (seg.type === 'emoji') {
      label.classList.add('emoji');
      const ir = seg.emoji?.icon_ref;
      const glyph = seg.emoji?.glyph;
      const display = seg.emoji?.display_name || seg.emoji?.code;
      const isUrl = (u) => typeof u === 'string' && (u.startsWith('http://') || u.startsWith('https://') || u.includes('.'));
    if (isUrl(ir)) {
      const img = document.createElement('img');
      img.src = ir;
      img.alt = display || 'emoji';
      img.className = 'wheel-emoji-img';
      img.onerror = () => {
        // Fallback to glyph/text if image is missing
        label.innerHTML = '';
        label.textContent = glyph || display || '🙂';
      };
      label.appendChild(img);
    } else {
      // prefer glyph, then icon_ref as glyph, then label/code
      label.textContent = glyph || ir || display || '🙂';
    }
    } else {
      label.textContent = seg.label;
    }
    wheel.appendChild(label);
    const li = document.createElement('div');
    li.textContent = seg.type === 'emoji' ? (glyphOrRef(seg.emoji) || seg.emoji?.display_name || seg.emoji?.code || '🙂') : seg.label;
    legend.appendChild(li);
  });
  const close = document.getElementById('wheel-close'); if (close) close.onclick = () => { document.getElementById('wheel-overlay').hidden = true; };
  const spinBtn = document.getElementById('wheel-spin'); if (spinBtn) spinBtn.onclick = doSpin;
}

function glyphOrRef(e) {
  if (!e) return '';
  if (e.glyph) return e.glyph;
  const ir = e.icon_ref;
  if (ir && !(ir.includes('.') || ir.startsWith('http'))) return ir;
  return '';
}

function findSegmentIndexForResult(result) {
  if (!currentPool || !currentPool.segments) return -1;
  if (result.outcome_type === 'emoji' && result.emoji) {
    const { code, version, glyph } = result.emoji;
    let idx = currentPool.segments.findIndex(s => s.type === 'emoji' && s.emoji && s.emoji.code === code && s.emoji.version === version);
    if (idx < 0 && glyph) {
      idx = currentPool.segments.findIndex(s => s.type === 'emoji' && (s.emoji?.glyph === glyph || glyphOrRef(s.emoji) === glyph));
    }
    return idx;
  }
  if (result.outcome_type === 'odd_prize' && result.label) {
    return currentPool.segments.findIndex(s => s.type === 'odd_prize' && s.label === result.label);
  }
  return -1;
}

function ensureResultInCurrentWheel(result) {
  if (!currentPool || !Array.isArray(currentPool.segments)) return;
  const segs = currentPool.segments;
  // Helper creators
  const makeEmojiSeg = (emoji) => ({ type: 'emoji', emoji: normalizeEmoji(emoji) });
  const makeOddSeg = (label) => ({ type: 'odd_prize', label });
  // If result already present, nothing to do
  const idx = findSegmentIndexForResult(result);
  if (idx >= 0) return;
  // Prefer replacing an odd_prize slot to preserve at least one emoji invariant
  let replaced = false;
  if (result.outcome_type === 'emoji') {
    const replIdx = segs.findIndex(s => s.type === 'odd_prize');
    if (replIdx >= 0) {
      segs[replIdx] = makeEmojiSeg(result.emoji);
      replaced = true;
    }
  } else if (result.outcome_type === 'odd_prize') {
    const replIdx = segs.findIndex(s => s.type === 'odd_prize');
    if (replIdx >= 0) {
      segs[replIdx] = makeOddSeg(result.label);
      replaced = true;
    }
  }
  if (!replaced) {
    // As a fallback, replace the first segment
    segs[0] = (result.outcome_type === 'emoji') ? makeEmojiSeg(result.emoji) : makeOddSeg(result.label);
  }
}

function animateWheelToIndex(index, callback) {
  const wheel = document.getElementById('wheel'); if (!wheel) { callback && callback(); return; }
  // Pointer is at top (0deg). Segment centers at angles measured from 12 o'clock clockwise.
  const centerAngle = index >= 0 ? (index * wheelAnglePer + wheelAnglePer / 2) : (Math.random() * 360);
  const turns = 4 + Math.floor(Math.random() * 3); // 4-6 turns for longer spin
  // To land the target center at top (0deg), the wheel must rotate so that current angle + rotation ≡ -centerAngle (mod 360)
  const delta = -centerAngle - (wheelRotation % 360);
  wheelRotation = wheelRotation + turns * 360 + delta;
  const durationMs = 2600; // slower spin and deceleration
  wheel.style.transition = `transform ${durationMs/1000}s cubic-bezier(0.08, 0.6, 0.2, 1)`;
  wheel.style.transform = `rotate(${wheelRotation}deg)`;
  // Tick effect on pointer during spin
  const pointer = document.querySelector('.wheel-pointer');
  let tickTimer = null;
  if (pointer) {
    const interval = 120; // ms, slower tick cadence
    tickTimer = setInterval(() => {
      pointer.classList.add('tick');
      setTimeout(() => pointer.classList.remove('tick'), Math.min(60, interval - 10));
    }, interval);
  }
  const onEnd = () => {
    wheel.style.transition = '';
    wheel.removeEventListener('transitionend', onEnd);
    if (tickTimer) { clearInterval(tickTimer); tickTimer = null; pointer && pointer.classList.remove('tick'); }
    callback && callback();
  };
  wheel.addEventListener('transitionend', onEnd, { once: true });
}

async function doSpin() {
  const spinBtn = document.getElementById('wheel-spin'); if (spinBtn) spinBtn.disabled = true;
  try {
    // Do not refresh pool before spin; refresh only after result is shown
    let result;
    let chosenIndex = -1;
    try {
      const raw = await fetchJSON('/api/spin', { method: 'POST' });
      result = normalizeResult(raw);
      // Ensure the result exists on the current visual wheel before animating
      chosenIndex = findSegmentIndexForResult(result);
      if (chosenIndex < 0) {
        ensureResultInCurrentWheel(result);
        // Re-render wheel with the injected result, reset rotation
        renderWheel(currentPool);
        chosenIndex = findSegmentIndexForResult(result);
      }
    } catch (e) {
      const msg = String(e?.message || '').toLowerCase();
      if (msg.includes('no_spins_left') || msg.includes('limit_banner')) {
        // respect backend contract: show banner and do not fallback to random
        setSpinsRemaining(userProfile, 0);
        updateSpinsIndicator();
        openSpinsBanner();
        if (spinBtn) spinBtn.disabled = true;
        return;
      }
      if (msg.includes('pool_invalid')) {
        // try to refresh pool and return
        try {
          const raw = await fetchJSON('/api/spin/pool');
          const np = normalizePool(raw);
          ensureAtLeastOneEmoji(np);
          currentPool = np;
          renderWheel(currentPool);
        } catch {}
        if (spinBtn) spinBtn.disabled = getSpinsRemaining(userProfile) <= 0;
        return;
      }
      // Fallback demo behavior if backend unavailable: simulate spin result
      chosenIndex = Math.floor(Math.random() * (currentPool.segments.length));
      const seg = currentPool.segments[chosenIndex];
      if (seg.type === 'emoji') {
        result = normalizeResult({ outcome_type: 'emoji', emoji: seg.emoji, duplicate: userHasEmoji(seg.emoji.code, seg.emoji.version), spins_remaining: Math.max(0, getSpinsRemaining(userProfile) - 1) });
      } else {
        result = normalizeResult({ outcome_type: 'odd_prize', label: seg.label, spins_remaining: Math.max(0, getSpinsRemaining(userProfile) - 1) });
      }
    }
    animateWheelToIndex(chosenIndex, async () => {
      applySpinResult(result);
      // After showing result, refresh pool and reset wheel for consistent subsequent spins
      try {
        const raw = await fetchJSON('/api/spin/pool');
        const newPool = normalizePool(raw);
        ensureAtLeastOneEmoji(newPool);
        currentPool = newPool;
        renderWheel(currentPool);
      } catch {
        // keep currentPool if refresh fails
        renderWheel(currentPool);
      } finally {
        const noSpins = getSpinsRemaining(userProfile) <= 0;
        if (spinBtn) spinBtn.disabled = noSpins;
        if (noSpins) {
          // show banner and leave the wheel overlay
          openSpinsBanner();
        }
      }
    });
  } catch (err) { alert('Ошибка спина: ' + err.message); }
}

function applySpinResult(result) {
  if (!userProfile) return;
  setSpinsRemaining(userProfile, result.spins_remaining ?? Math.max(0, getSpinsRemaining(userProfile) - 1));
  updateSpinsIndicator();
  if (result.outcome_type === 'emoji' && result.emoji) {
    if (!result.duplicate) {
      const list = profileEmojis(userProfile);
      const { code, version, rarity, display_name, icon_ref, glyph } = result.emoji;
      if (!userHasEmoji(code, version)) list.push({ code, version, rarity, display_name, icon_ref, glyph });
      // write back list if it isn't at userProfile.emojis
      if ('emojis' in userProfile) userProfile.emojis = list;
      else if (userProfile.inventory) userProfile.inventory.emojis = list;
      notify(`Выпало эмодзи: ${glyphOrRef(result.emoji) || displayOrCode(result.emoji)}!`);
    } else {
      notify('Эмодзи уже разблокировано — дубль игнорирован.');
    }
  } else if (result.outcome_type === 'odd_prize') {
    notify(`Приз: ${result.label}. Весело, но без последствий.`);
  }
  if (getSpinsRemaining(userProfile) <= 0) openSpinsBanner();
}

function openSpinsBanner() {
  const banner = document.getElementById('spins-banner'); if (!banner) return;
  // Ensure wheel overlay is hidden so that only the banner stays visible
  const wheelOverlay = document.getElementById('wheel-overlay');
  if (wheelOverlay) wheelOverlay.hidden = true;
  banner.hidden = false;
  const btn = document.getElementById('spins-banner-close');
  if (btn) btn.onclick = () => {
    // Close banner and ensure we return to the main screen (no overlays visible)
    banner.hidden = true;
    const wheelOv = document.getElementById('wheel-overlay'); if (wheelOv) wheelOv.hidden = true;
    // refresh topbar indicator state just in case
    updateSpinsIndicator();
  };
}

function renderTask(task, opts) {
  const li = document.createElement('li');
  li.className = 'task';

  const left = document.createElement('div');
  left.className = 'task-left';

  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.checked = !!task.done;
  checkbox.addEventListener('change', async (e) => {
    e.stopPropagation(); // do not open modal when checking
    try {
      const updated = await fetchJSON(`/api/tasks/${task.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ done: checkbox.checked })
      });
      title.classList.toggle('done', !!updated.done);
      // Reorder immediately: move completed to end of list without full reload
      try {
        const liEl = li;
        const list = liEl.parentElement;
        if (list && checkbox.checked) {
          list.appendChild(liEl);
        }
      } catch {}
    } catch (e) {
      alert('Не удалось обновить задачу: ' + e.message);
      checkbox.checked = !checkbox.checked; // revert
    }
  });

  const title = document.createElement('span');
  title.className = 'task-title' + (task.done ? ' done' : '');
  title.textContent = task.title;

  // time/date label placed before title
  const timeSpan = document.createElement('span');
  timeSpan.className = 'task-time';
  let timeLabel = formatTimeLabel(task);
  if (opts && opts.context === 'calendar' && task.all_day) {
    // In calendar, do not show date for all-day tasks
    timeLabel = '';
  }
  timeSpan.textContent = timeLabel;

  left.appendChild(checkbox);
  if (timeLabel) left.appendChild(timeSpan);
  // Show emojis (up to 3) before title
  const emojiStack = document.createElement('span');
  emojiStack.className = 'emoji-stack';
  (task.emojis || localTaskEmojis.get(task.id) || []).slice(0, 3).forEach(e => {
    const ne = normalizeEmoji(e);
    // Fall back to catalog glyph if needed
    if (!ne.glyph && (!ne.icon_ref || typeof ne.icon_ref !== 'string' || ne.icon_ref.includes('.') || ne.icon_ref.startsWith('http'))) {
      const cat = (emojiCatalog || []).find(it => it.code === ne.code && it.version === ne.version);
      if (cat) {
        ne.icon_ref = cat.icon_ref;
        ne.glyph = cat.icon_ref; // catalog stores glyph
      }
    }
    const chip = document.createElement('span'); chip.className = 'emoji-chip small'; chip.textContent = displayOrCode(ne);
    emojiStack.appendChild(chip);
  });
  if ((task.emojis && task.emojis.length) || (localTaskEmojis.get(task.id) || []).length) left.appendChild(emojiStack);
  left.appendChild(title);

  li.appendChild(left);

  // Открывать модалку по клику на задачу (кроме чекбокса)
  li.addEventListener('click', (ev) => {
    if (ev.target && ev.target.tagName === 'INPUT' && ev.target.type === 'checkbox') return;
    openEditModal(task);
  });

  return li;
}

function formatTimeLabel(task) {
  try {
    if (task.all_day) {
      const d = new Date(task.all_day + 'T00:00:00Z');
      return `${d.toLocaleDateString()}`;
    }
    if (task.when) {
      const w = new Date(task.when);
      const fmt = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' });
      return `${fmt.format(w)}`;
    }
    if (task.start && task.end) {
      const s = new Date(task.start);
      const e = new Date(task.end);
      const fmt = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' });
      return `${fmt.format(s)} – ${fmt.format(e)}`;
    }
    return '';
  } catch {
    return '';
  }
}

function isoWeek(dateObj) {
  // ISO week: Thursday determines week number
  const d = new Date(Date.UTC(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate()));
  // Thursday in current week decides the year.
  d.setUTCDate(d.getUTCDate() + 3 - ((d.getUTCDay() + 6) % 7));
  const week1 = new Date(Date.UTC(d.getUTCFullYear(), 0, 4));
  return 1 + Math.round(((d - week1) / 86400000 - 3 + ((week1.getUTCDay() + 6) % 7)) / 7);
}

function startOfISOWeek(dateObj) {
  const d = new Date(dateObj);
  const day = (d.getDay() + 6) % 7; // Mon=0
  d.setDate(d.getDate() - day);
  d.setHours(0,0,0,0);
  return d;
}

let calAnchor = startOfISOWeek(new Date());

function renderCalendar(tasks) {
  const cal = document.getElementById('calendar');
  cal.innerHTML = '';
  const title = document.getElementById('cal-title');
  const weekNum = isoWeek(calAnchor);
  // Показывать только месяц (первый в неделе)
  const monthFmt = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' });
  title.textContent = `Неделя ${weekNum} — ${monthFmt.format(calAnchor)}`;

  const days = [];
  for (let i = 0; i < 7; i++) {
    const dayDate = new Date(calAnchor); dayDate.setDate(calAnchor.getDate() + i);
    const col = document.createElement('div');
    col.className = 'cal-day';
    const weekday = document.createElement('div');
    weekday.className = 'weekday';
    weekday.textContent = dayDate.toLocaleDateString(undefined, { weekday: 'long' });
    const daynum = document.createElement('div');
    daynum.className = 'daynum';
    daynum.textContent = String(dayDate.getDate()).padStart(2,'0');
    col.appendChild(weekday);
    col.appendChild(daynum);
    days.push({ date: dayDate, el: col });
    cal.appendChild(col);
  }

  const noTimeList = document.getElementById('no-time-list');
  noTimeList.innerHTML = '';

  // Сортировка: all_day сверху (без времени — вне календаря), timed по времени
  const perDay = Array.from({length:7}, () => ({ allDay: [], whens: [], timed: [] }));
  const msPerDay = 86400000;
  tasks.forEach(t => {
    if (t.all_day) {
      const d = new Date(t.all_day + 'T00:00:00Z');
      const idx = Math.floor((d - calAnchor) / msPerDay);
      if (idx>=0 && idx<7) perDay[idx].allDay.push(t);
    } else if (t.when) {
      const d = new Date(t.when);
      const idx = Math.floor((d - calAnchor) / msPerDay);
      if (idx>=0 && idx<7) perDay[idx].whens.push(t);
    } else if (t.start && t.end) {
      const d = new Date(t.start);
      const idx = Math.floor((d - calAnchor) / msPerDay);
      if (idx>=0 && idx<7) perDay[idx].timed.push(t);
    } else {
      noTimeList.appendChild(renderTask(t, { context: 'calendar' }));
    }
  });
  perDay.forEach((bucket, i) => {
    bucket.allDay.forEach(t => days[i].el.appendChild(renderTask(t, { context: 'calendar' })));
    bucket.whens.sort((a,b)=> new Date(a.when)-new Date(b.when));
    bucket.whens.forEach(t => days[i].el.appendChild(renderTask(t, { context: 'calendar' })));
    bucket.timed.sort((a,b)=> new Date(a.start)-new Date(b.start));
    bucket.timed.forEach(t => days[i].el.appendChild(renderTask(t, { context: 'calendar' })));
  });

  document.getElementById('cal-prev').onclick = () => { calAnchor.setDate(calAnchor.getDate() - 7); renderCalendar(tasks); };
  document.getElementById('cal-next').onclick = () => { calAnchor.setDate(calAnchor.getDate() + 7); renderCalendar(tasks); };
  document.getElementById('cal-today').onclick = () => { calAnchor = startOfISOWeek(new Date()); renderCalendar(tasks); };
}

async function refreshTasks() {
  try {
    const tasks = await fetchJSON('/api/tasks');
    // Attach UI-only emoji selections if present
    tasks.forEach(t => { if (!t.emojis && localTaskEmojis.has(t.id)) t.emojis = localTaskEmojis.get(t.id); });
    // list view
    const list = document.getElementById('task-list');
    list.innerHTML = '';
    // сортировка списка: без даты, затем по дню; в дне сначала all_day, затем по времени; выполненные в конце
    const msPerDay = 86400000;
    const buckets = { noTime: [], days: new Map(), done: [] };
    tasks.forEach(t => {
      if (t.done) { buckets.done.push(t); return; }
      if (!t.all_day && !(t.start && t.end)) { buckets.noTime.push(t); return; }
      // normalize to day key
      const key = t.all_day ? t.all_day : (new Date(t.start).toISOString().slice(0,10));
      if (!buckets.days.has(key)) buckets.days.set(key, { allDay: [], timed: [] });
      const bucket = buckets.days.get(key);
      if (t.all_day) bucket.allDay.push(t); else bucket.timed.push(t);
    });
    // build sorted list
    const appendAll = arr => arr.forEach(t => list.appendChild(renderTask(t)));
    appendAll(buckets.noTime);
    const dayKeys = Array.from(buckets.days.keys()).sort();
    dayKeys.forEach(k => {
      const b = buckets.days.get(k);
      appendAll(b.allDay);
      b.timed.sort((a,b)=> new Date(a.start)-new Date(b.start));
      appendAll(b.timed);
    });
    // done tasks at the end preserving internal ordering
    appendAll(buckets.done);
    // calendar view
    renderCalendar(tasks);
  } catch (e) {
    alert('Не удалось загрузить задачи: ' + e.message);
  }
}

async function addTaskWithPayload(payload) {
  try {
    const task = await fetchJSON('/api/tasks', { method: 'POST', body: JSON.stringify(payload) });
    // Assign emojis via backend per contract
    if (payload.emojis && Array.isArray(payload.emojis)) {
      for (const e of payload.emojis) {
        try {
          await fetchJSON(`/api/tasks/${task.id}/emojis`, { method: 'POST', body: JSON.stringify({ emoji: { code: e.code, version: e.version } }) });
        } catch {}
      }
    }
    refreshTasks();
  } catch (e) {
    alert('Не удалось добавить задачу: ' + e.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('new-task-form');
  const input = document.getElementById('new-task-input');
  const newMode = document.getElementById('new-time-mode');
  const newAllDay = document.getElementById('new-all-day');
  const newStart = document.getElementById('new-start');
  const newEnd = document.getElementById('new-end');
  const newWhen = document.getElementById('new-when');
  const viewList = document.getElementById('view-list');
  const viewCal = document.getElementById('view-calendar');
  const listView = document.getElementById('list-view');
  const calView = document.getElementById('calendar-view');

  // Prepopulate date/time inputs with user's current local time
  const now = new Date();
  const toLocalInput = (d) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
  if (newAllDay) newAllDay.valueAsDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  if (newWhen) newWhen.value = toLocalInput(now);
  if (newStart) newStart.value = toLocalInput(now);
  if (newEnd) {
    const in30 = new Date(now.getTime() + 30*60*1000);
    newEnd.value = toLocalInput(in30);
  }

  // Gamification init
  const playBtn = document.getElementById('play-button'); if (playBtn) playBtn.addEventListener('click', openWheel);
  loadUserProfile();
  loadEmojiCatalog();

  // New task emoji selector
  const newEmojiBtn = document.getElementById('new-emoji-btn');
  const newEmojiPanel = document.getElementById('new-emoji-panel');
  const newEmojiChips = document.getElementById('new-emoji-chips');
  const newSelectedEmojis = [];
  const hasPerk = () => hasPerkMultiEmoji(userProfile);
  const canAddMore = () => hasPerk() ? newSelectedEmojis.length < 3 : newSelectedEmojis.length < 1;
  function renderEmojiChips(container, emojis, onRemove) {
    container.innerHTML = '';
    (emojis || []).forEach((e, idx) => {
      const chip = document.createElement('span'); chip.className = 'emoji-chip'; chip.textContent = displayOrCode(normalizeEmoji(e));
      if (onRemove) { const btn = document.createElement('button'); btn.className = 'remove'; btn.type = 'button'; btn.textContent = '×'; btn.title = 'Снять эмодзи'; btn.onclick = () => onRemove(idx, e); chip.appendChild(btn); }
      container.appendChild(chip);
    });
  }
  const updateNewEmojiUI = () => {
    if (!newEmojiChips) return;
    renderEmojiChips(newEmojiChips, newSelectedEmojis, (idx) => { newSelectedEmojis.splice(idx,1); updateNewEmojiUI(); });
    if (newEmojiBtn) { newEmojiBtn.disabled = !canAddMore(); newEmojiBtn.title = canAddMore() ? '' : (hasPerk() ? 'Максимум 3 эмодзи' : 'Дополнительные эмодзи доступны с перком «мульти-эмодзи»'); }
  };
  if (newEmojiBtn && newEmojiPanel) {
    newEmojiBtn.addEventListener('click', () => {
      const expanded = newEmojiBtn.getAttribute('aria-expanded') === 'true';
      if (expanded) { newEmojiPanel.hidden = true; newEmojiBtn.setAttribute('aria-expanded', 'false'); }
      else {
        // Build panel: available items = user's unlocked emojis
        newEmojiPanel.innerHTML = '';
        (emojiCatalog || []).forEach(item => {
          const locked = !userHasEmoji(item.code, item.version);
          const it = document.createElement('div'); it.className = 'emoji-item' + (locked ? ' locked' : '');
          it.title = `${item.display_name || item.code}${locked ? ' — разблокируйте через колесо' : ''}`;
          it.textContent = displayOrCode(item);
          if (!locked) {
            it.onclick = (ev) => {
              ev.stopPropagation();
              // Close the panel regardless of selection success to avoid leaving it open
              newEmojiPanel.hidden = true;
              if (newEmojiBtn) newEmojiBtn.setAttribute('aria-expanded', 'false');
              if (!canAddMore()) return;
              // Allow selecting previously unlocked emojis even if newer ones also unlocked
              if (!newSelectedEmojis.find(e=>e.code===item.code && e.version===item.version)) {
                newSelectedEmojis.push({ code: item.code, version: item.version, display_name: item.display_name, icon_ref: item.icon_ref, glyph: item.glyph });
                updateNewEmojiUI();
              }
            };
          }
          newEmojiPanel.appendChild(it);
        });
        newEmojiPanel.hidden = false; newEmojiBtn.setAttribute('aria-expanded', 'true');
      }
    });
  }
  updateNewEmojiUI();

  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const payload = { title: input.value };
    if (newMode.value === 'all_day') {
      if (newAllDay.value) payload.all_day = newAllDay.value;
    } else if (newMode.value === 'when') {
      if (newWhen.value) payload.when = toISOWithOffset(enrichWithCurrentYear(newWhen.value));
    } else if (newMode.value === 'timed') {
      if (newStart.value && newEnd.value) {
        payload.start = toISOWithOffset(enrichWithCurrentYear(newStart.value));
        payload.end = toISOWithOffset(enrichWithCurrentYear(newEnd.value));
      }
    }
    if (newSelectedEmojis.length > 0) payload.emojis = newSelectedEmojis.slice(0, hasPerk() ? 3 : 1);
    addTaskWithPayload(payload);
    newSelectedEmojis.splice(0, newSelectedEmojis.length); updateNewEmojiUI();
    input.value = '';
    input.focus();
  });

  newMode.addEventListener('change', () => {
    const v = newMode.value;
    // Keep the time fields container visible to avoid layout jumps; toggle inputs only
    newAllDay.hidden = v !== 'all_day';
    const isWhen = v === 'when';
    newWhen.hidden = !isWhen;
    const timed = v === 'timed';
    newStart.hidden = !timed;
    newEnd.hidden = !timed;
  });

  viewList.addEventListener('click', () => {
    listView.hidden = false; calView.hidden = true;
    viewList.setAttribute('aria-pressed', 'true');
    viewCal.setAttribute('aria-pressed', 'false');
  });
  viewCal.addEventListener('click', () => {
    listView.hidden = true; calView.hidden = false;
    viewList.setAttribute('aria-pressed', 'false');
    viewCal.setAttribute('aria-pressed', 'true');
    // ensure calendar is up to date
    refreshTasks();
  });

  refreshTasks();
});

// Submit on Enter anywhere relevant (add form and edit modal)
document.addEventListener('keydown', (ev) => {
  if (ev.key === 'Enter') {
    const modal = document.getElementById('edit-modal');
    if (!modal.hidden) {
      const form = document.getElementById('edit-form');
      if (document.activeElement && document.activeElement.tagName !== 'TEXTAREA') {
        ev.preventDefault(); form.requestSubmit();
      }
    }
  }
});

// Редактирование задачи в модальном окне
function openEditModal(task) {
  const modal = document.getElementById('edit-modal');
  const form = document.getElementById('edit-form');
  const title = document.getElementById('edit-title');
  const mode = document.getElementById('edit-time-mode');
  const allDay = document.getElementById('edit-all-day');
  const when = document.getElementById('edit-when');
  const start = document.getElementById('edit-start');
  const end = document.getElementById('edit-end');
  const delBtn = document.getElementById('edit-delete');
  const cancelBtn = document.getElementById('edit-cancel');
  const editEmojiChips = document.getElementById('edit-emoji-chips');
  const editEmojiAddBtn = document.getElementById('edit-emoji-add-btn');
  const editEmojiPanel = document.getElementById('edit-emoji-panel');

  title.value = task.title || '';
  if (task.all_day) {
    mode.value = 'all_day';
    allDay.value = task.all_day;
    start.value = '';
    end.value = '';
  } else if (task.when) {
    mode.value = 'when';
    const toLocalInput = (iso) => {
      const d = new Date(iso);
      return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    };
    when.value = toLocalInput(task.when);
    allDay.value = '';
    start.value = '';
    end.value = '';
  } else if (task.start && task.end) {
    mode.value = 'timed';
    const toLocalInput = (iso) => {
      const d = new Date(iso);
      return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    };
    allDay.value = '';
    when.value = '';
    start.value = toLocalInput(task.start);
    end.value = toLocalInput(task.end);
  } else {
    mode.value = 'none';
    allDay.value = '';
    when.value = '';
    start.value = '';
    end.value = '';
  }

  const toggleFields = () => {
    allDay.parentElement.style.display = (mode.value === 'all_day') ? '' : 'none';
    when.parentElement.style.display = (mode.value === 'when') ? '' : 'none';
    const showTimed = mode.value === 'timed';
    start.parentElement.style.display = showTimed ? '' : 'none';
    end.parentElement.style.display = showTimed ? '' : 'none';
  };
  toggleFields();
  mode.onchange = toggleFields;

  // --- Emoji selection in Edit modal ---
  const initialEmojis = (task.emojis && task.emojis.length)
    ? task.emojis
    : (localTaskEmojis.get(task.id) || []);
  const editSelectedEmojis = initialEmojis.map(e => ({
    code: e.code,
    version: e.version,
    display_name: e.display_name,
    icon_ref: e.icon_ref
  }));

  const hasPerk = () => hasPerkMultiEmoji(userProfile);
  const canAddMore = () => hasPerk() ? editSelectedEmojis.length < 3 : editSelectedEmojis.length < 1;

  function renderEmojiChips(container, emojis, onRemove) {
    if (!container) return;
    container.innerHTML = '';
    (emojis || []).forEach((e, idx) => {
      const chip = document.createElement('span');
      chip.className = 'emoji-chip';
      chip.textContent = displayOrCode(e);
      if (onRemove) {
        const btn = document.createElement('button');
        btn.className = 'remove';
        btn.type = 'button';
        btn.textContent = '×';
        btn.title = 'Снять эмодзи';
        btn.onclick = (ev) => { ev.stopPropagation(); onRemove(idx, e); };
        chip.appendChild(btn);
      }
      container.appendChild(chip);
    });
  }

  const updateEditEmojiUI = () => {
    renderEmojiChips(editEmojiChips, editSelectedEmojis, (idx) => {
      editSelectedEmojis.splice(idx, 1);
      updateEditEmojiUI();
    });
    if (editEmojiAddBtn) {
      const allowed = canAddMore();
      editEmojiAddBtn.disabled = !allowed;
      editEmojiAddBtn.title = allowed ? '' : (hasPerk() ? 'Максимум 3 эмодзи' : 'Дополнительные эмодзи доступны с перком «мульти-эмодзи»');
      editEmojiAddBtn.setAttribute('aria-expanded', editEmojiPanel && !editEmojiPanel.hidden ? 'true' : 'false');
    }
  };

  async function openEditEmojiPanel() {
    if (!editEmojiPanel) return;
    editEmojiPanel.innerHTML = '';
    (emojiCatalog || []).forEach(item => {
      const locked = !userHasEmoji(item.code, item.version);
      const it = document.createElement('div');
      it.className = 'emoji-item' + (locked ? ' locked' : '');
      it.title = `${item.display_name || item.code}${locked ? ' — разблокируйте через колесо' : ''}`;
      it.textContent = displayOrCode(item);
      if (!locked) {
        it.onclick = async (ev) => {
          ev.stopPropagation();
          // Close the panel immediately on click to ensure it disappears
          editEmojiPanel.hidden = true;
          if (editEmojiAddBtn) editEmojiAddBtn.setAttribute('aria-expanded', 'false');
          if (!canAddMore()) return;
          if (!editSelectedEmojis.find(e => e.code === item.code && e.version === item.version)) {
            // Persist via backend so emojis survive refresh
            try {
              await fetchJSON(`/api/tasks/${task.id}/emojis`, { method: 'POST', body: JSON.stringify({ emoji: { code: item.code, version: item.version } }) });
            } catch {}
            editSelectedEmojis.push({ code: item.code, version: item.version, display_name: item.display_name, icon_ref: item.icon_ref, glyph: item.glyph });
            updateEditEmojiUI();
          }
        };
      }
      editEmojiPanel.appendChild(it);
    });
    editEmojiPanel.hidden = false;
    if (editEmojiAddBtn) editEmojiAddBtn.setAttribute('aria-expanded', 'true');
  }

  if (editEmojiAddBtn && editEmojiPanel) {
    editEmojiAddBtn.onclick = (ev) => {
      ev.preventDefault();
      if (!canAddMore() && editEmojiPanel.hidden) return; // cannot open when limit reached
      if (editEmojiPanel.hidden) openEditEmojiPanel();
      else {
        editEmojiPanel.hidden = true;
        editEmojiAddBtn.setAttribute('aria-expanded', 'false');
      }
    };
  }

  updateEditEmojiUI();

  modal.hidden = false;

  delBtn.onclick = async () => {
    try {
      await fetchJSON(`/api/tasks/${task.id}`, { method: 'DELETE' });
      modal.hidden = true;
      if (editEmojiPanel) editEmojiPanel.hidden = true;
      localTaskEmojis.delete(task.id);
      refreshTasks();
    } catch (e) {
      alert('Не удалось удалить: ' + e.message);
    }
  };

  cancelBtn.onclick = () => { modal.hidden = true; if (editEmojiPanel) editEmojiPanel.hidden = true; };

  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const patch = { title: title.value };
    if (mode.value === 'all_day') {
      patch.all_day = allDay.value || null;
      patch.start = null; patch.end = null;
      patch.when = null;
    } else if (mode.value === 'when') {
      const toISOWithOffset = (s) => {
        const d = new Date(s);
        const tz = -d.getTimezoneOffset();
        const sign = tz >= 0 ? '+' : '-';
        const hh = String(Math.floor(Math.abs(tz)/60)).padStart(2,'0');
        const mm = String(Math.abs(tz)%60).padStart(2,'0');
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}${sign}${hh}:${mm}`;
      };
      patch.all_day = null;
      patch.when = when.value ? toISOWithOffset(when.value) : null;
      patch.start = null; patch.end = null;
    } else if (mode.value === 'timed') {
      const toISOWithOffset = (s) => {
        const d = new Date(s);
        const tz = -d.getTimezoneOffset();
        const sign = tz >= 0 ? '+' : '-';
        const hh = String(Math.floor(Math.abs(tz)/60)).padStart(2,'0');
        const mm = String(Math.abs(tz)%60).padStart(2,'0');
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}T${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}${sign}${hh}:${mm}`;
      };
      patch.all_day = null;
      patch.when = null;
      patch.start = start.value ? toISOWithOffset(start.value) : null;
      patch.end = end.value ? toISOWithOffset(end.value) : null;
    } else {
      patch.all_day = null; patch.start = null; patch.end = null;
      patch.when = null;
    }
    try {
      // Persist emojis via backend so they survive page reloads
      const newEmojis = editSelectedEmojis.slice(0, hasPerk() ? 3 : 1);
      // Remove existing emojis first (optional: backend handles capacity/duplicates)
      // Then add current selection
      // For simplicity, just PATCH task props and rely on POST /emojis already triggered on selection
      await fetchJSON(`/api/tasks/${task.id}`, { method: 'PATCH', body: JSON.stringify(patch) });
      modal.hidden = true;
      if (editEmojiPanel) editEmojiPanel.hidden = true;
      refreshTasks();
    } catch (e) {
      alert('Не удалось сохранить: ' + e.message);
    }
  };
}
