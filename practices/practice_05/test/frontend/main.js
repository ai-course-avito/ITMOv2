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

function loadMenuSample() {
  const items = [
    { name: 'Espresso', price: 3, size: 'single' },
    { name: 'Cappuccino', price: 4, size: 'medium' },
    { name: 'Latte', price: 4.5, size: 'large' },
  ];
  const ul = document.getElementById('menu-list');
  ul.innerHTML = '';
  for (const it of items) {
    const li = document.createElement('li');
    li.textContent = `${it.name} — ${it.price} CoffeeCoin (${it.size})`;
    ul.appendChild(li);
  }
}

window.addEventListener('DOMContentLoaded', async () => {
  await loadStatus();
  loadMenuSample();
});
