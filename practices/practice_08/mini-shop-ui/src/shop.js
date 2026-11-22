const names = { chair: 'Стул', lamp: 'Лампа' };
const money = new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 });

export function mountShop(root, fetcher = globalThis.fetch) {
  root.innerHTML = `
    <header class="mb-4"><h1>Mini Shop</h1><p class="lead">Выберите товар и оформите заказ.</p></header>
    <section class="card mb-3"><div class="card-body">
      <form id="checkout">
        <label class="form-label" for="product">Товар</label>
        <select class="form-select" id="product" name="product" required disabled></select>
        <div class="row g-3 mt-1">
          <div class="col-sm-6"><label class="form-label" for="username">Имя пользователя</label><input class="form-control" id="username" autocomplete="username" required></div>
          <div class="col-sm-6"><label class="form-label" for="password">Пароль</label><input type="password" class="form-control" id="password" autocomplete="current-password" required></div>
        </div>
        <button class="btn btn-primary mt-4" type="submit" disabled>Оформить заказ</button>
      </form>
    </div></section>
    <p id="status" role="status" aria-live="polite"></p>
    <p id="error" class="alert alert-danger" role="alert" hidden></p>
    <button id="retry" class="btn btn-outline-secondary" type="button" hidden>Обновить каталог</button>
  `;
  const form = root.querySelector('#checkout');
  const product = root.querySelector('#product');
  const username = root.querySelector('#username');
  const password = root.querySelector('#password');
  const button = form.querySelector('button');
  const status = root.querySelector('#status');
  const error = root.querySelector('#error');
  const retry = root.querySelector('#retry');
  let submitting = false;
  let available = new Map();

  async function request(path, body, token) {
    const options = body ? {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { 'X-Token': token } : {}) },
      body: JSON.stringify(body),
    } : {};
    const response = await fetcher('/api' + path, options);
    if (!response.ok) {
      throw new Error(response.status === 401 && path === '/login'
        ? 'Проверьте имя пользователя и пароль.' : 'Не удалось выполнить запрос. Попробуйте ещё раз.');
    }
    return response.json();
  }

  function showError(message) {
    error.textContent = message;
    error.hidden = !message;
  }

  async function loadCatalog() {
    showError('');
    product.disabled = button.disabled = true;
    retry.hidden = true;
    status.textContent = 'Загружаем каталог…';
    try {
      const data = await request('/products');
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error();
      available = new Map(Object.entries(data).filter(([, price]) => Number.isFinite(price) && price >= 0));
      product.replaceChildren(new Option('Выберите товар', ''));
      for (const [key, price] of available) {
        product.add(new Option((names[key] ?? key) + ' · ' + money.format(price), key));
      }
      product.disabled = button.disabled = available.size === 0;
      status.textContent = available.size ? '' : 'В каталоге пока нет товаров.';
      retry.hidden = available.size > 0;
    } catch {
      available.clear();
      status.textContent = '';
      showError('Каталог недоступен. Попробуйте обновить его.');
      retry.hidden = false;
    }
  }

  retry.addEventListener('click', loadCatalog);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (submitting || button.disabled) return;
    showError('');
    const login = username.value.trim();
    const key = product.value;
    if (!login || !password.value || !available.has(key)) {
      showError('Выберите товар и заполните имя пользователя и пароль.');
      return;
    }
    submitting = true;
    button.disabled = true;
    status.textContent = 'Оформляем заказ…';
    try {
      const session = await request('/login', { username: login, password: password.value });
      if (typeof session?.token !== 'string' || !session.token) throw new Error();
      const order = await request('/orders', { product: key }, session.token);
      if (!Number.isSafeInteger(order?.id) || !Number.isFinite(order?.price) || order.product !== key) throw new Error();
      status.textContent = 'Заказ №' + order.id + ' оформлен. ' + (names[key] ?? key) + ' · ' + money.format(order.price) + '.';
      password.value = '';
    } catch (failure) {
      status.textContent = '';
      showError(failure.message || 'Не удалось оформить заказ. Попробуйте ещё раз.');
    } finally {
      submitting = false;
      button.disabled = false;
    }
  });

  return loadCatalog();
}
