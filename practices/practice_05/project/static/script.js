async function fetchJSON(url, options) {
  const res = await fetch(url, Object.assign({
    headers: { 'Content-Type': 'application/json' }
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
    const list = document.getElementById('task-list');
    list.prepend(renderTask(task));
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
    addTaskWithPayload(payload);
    input.value = '';
    input.focus();
  });

  newMode.addEventListener('change', () => {
    const v = newMode.value;
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

  modal.hidden = false;

  delBtn.onclick = async () => {
    try {
      await fetchJSON(`/api/tasks/${task.id}`, { method: 'DELETE' });
      modal.hidden = true;
      refreshTasks();
    } catch (e) {
      alert('Не удалось удалить: ' + e.message);
    }
  };

  cancelBtn.onclick = () => { modal.hidden = true; };

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
      await fetchJSON(`/api/tasks/${task.id}`, { method: 'PATCH', body: JSON.stringify(patch) });
      modal.hidden = true;
      refreshTasks();
    } catch (e) {
      alert('Не удалось сохранить: ' + e.message);
    }
  };
}
