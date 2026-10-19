async function fetchJSON(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path} -> ${r.status}`);
  return await r.json();
}

async function loadStatus() {
  try {
    const health = await fetchJSON('/health');
    document.getElementById('health').textContent = `Health: ${health.status}`;
    document.getElementById('health').className = health.status === 'ok' ? 'ok' : 'warn';
  } catch (e) {
    document.getElementById('health').textContent = 'Health: error';
    document.getElementById('health').className = 'warn';
  }
  try {
    const ready = await fetchJSON('/ready');
    document.getElementById('ready').textContent = `Ready: ${ready.ready ? 'yes' : 'no'}`;
    document.getElementById('ready').className = ready.ready ? 'ok' : 'warn';
  } catch (e) {
    document.getElementById('ready').textContent = 'Ready: error';
    document.getElementById('ready').className = 'warn';
  }
}

async function loadMenu() {
  const ul = document.getElementById('menu-list');
  ul.innerHTML = '';
  try {
    const items = await fetchJSON('/api/v1/menu/');
    if (items.length === 0) {
      ul.innerHTML = '<li><em>No items yet</em></li>';
      return;
    }
    for (const it of items) {
      const li = document.createElement('li');
      li.textContent = `${it.name} — ${it.priceCoffeeCoin} CoffeeCoin (${(it.sizes||[]).join(', ') || 'n/a'})`;
      ul.appendChild(li);
    }
  } catch (e) {
    ul.innerHTML = '<li class="warn">Failed to load menu</li>';
  }
}

window.addEventListener('DOMContentLoaded', async () => {
  await loadStatus();
  await loadMenu();
});
