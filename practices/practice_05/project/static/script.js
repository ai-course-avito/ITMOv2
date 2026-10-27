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

function renderTask(task) {
  const li = document.createElement('li');
  li.className = 'task';

  const left = document.createElement('div');
  left.className = 'task-left';

  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.checked = !!task.done;
  checkbox.addEventListener('change', async () => {
    try {
      const updated = await fetchJSON(`/api/tasks/${task.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ done: checkbox.checked })
      });
      title.classList.toggle('done', !!updated.done);
    } catch (e) {
      alert('Не удалось обновить задачу: ' + e.message);
      checkbox.checked = !checkbox.checked; // revert
    }
  });

  const title = document.createElement('span');
  title.className = 'task-title' + (task.done ? ' done' : '');
  title.textContent = task.title;

  left.appendChild(checkbox);
  left.appendChild(title);

  const actions = document.createElement('div');
  actions.className = 'task-actions';

  const del = document.createElement('button');
  del.className = 'delete';
  del.textContent = 'Удалить';
  del.addEventListener('click', async () => {
    if (!confirm('Удалить задачу?')) return;
    try {
      await fetchJSON(`/api/tasks/${task.id}`, { method: 'DELETE' });
      li.remove();
    } catch (e) {
      alert('Не удалось удалить: ' + e.message);
    }
  });

  actions.appendChild(del);

  li.appendChild(left);
  li.appendChild(actions);

  return li;
}

async function refreshTasks() {
  try {
    const tasks = await fetchJSON('/api/tasks');
    const list = document.getElementById('task-list');
    list.innerHTML = '';
    tasks.forEach(t => list.appendChild(renderTask(t)));
  } catch (e) {
    alert('Не удалось загрузить задачи: ' + e.message);
  }
}

async function addTask(title) {
  const trimmed = (title || '').trim();
  if (!trimmed) return;
  try {
    const task = await fetchJSON('/api/tasks', {
      method: 'POST',
      body: JSON.stringify({ title: trimmed })
    });
    const list = document.getElementById('task-list');
    list.prepend(renderTask(task));
  } catch (e) {
    alert('Не удалось добавить задачу: ' + e.message);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('new-task-form');
  const input = document.getElementById('new-task-input');

  form.addEventListener('submit', (ev) => {
    ev.preventDefault();
    addTask(input.value);
    input.value = '';
    input.focus();
  });

  refreshTasks();
});
