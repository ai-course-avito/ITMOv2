import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mountShop } from './shop.js';

const response = (data, status = 200) => ({ ok: status < 400, status, json: async () => data });
const catalog = { chair: 5000, lamp: 1500 };
const query = selector => document.querySelector(selector);
const submit = () => query('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
const validForm = () => {
  query('#product').value = 'chair';
  query('#username').value = 'alice';
  query('#password').value = 'demo';
};

describe('оформление заказа', () => {
  beforeEach(() => { document.body.innerHTML = '<main id="app"></main>'; });

  it('показывает загрузку, затем доступные товары', async () => {
    let resolve;
    const loaded = mountShop(query('#app'), () => new Promise(done => { resolve = done; }));
    expect(query('#status').textContent).toContain('Загружаем');
    expect(query('button[type=submit]').disabled).toBe(true);
    resolve(response(catalog));
    await loaded;
    expect(query('#product').textContent).toContain('Стул');
    expect(query('button[type=submit]').disabled).toBe(false);
  });

  it('показывает пустой каталог и позволяет обновить его', async () => {
    await mountShop(query('#app'), async () => response({}));
    expect(query('#status').textContent).toContain('нет товаров');
    expect(query('#retry').hidden).toBe(false);
    expect(query('button[type=submit]').disabled).toBe(true);
  });

  it('даёт повторно загрузить каталог после ошибки', async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new TypeError()).mockResolvedValueOnce(response(catalog));
    await mountShop(query('#app'), fetcher);
    expect(query('[role=alert]').textContent).toContain('Каталог недоступен');
    query('#retry').click();
    await vi.waitFor(() => expect(query('#product').textContent).toContain('Лампа'));
    expect(query('[role=alert]').hidden).toBe(true);
  });

  it('не отправляет незаполненную форму', async () => {
    const fetcher = vi.fn().mockResolvedValue(response(catalog));
    await mountShop(query('#app'), fetcher);
    expect(query('form').checkValidity()).toBe(false);
    submit();
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(query('[role=alert]').textContent).toContain('Выберите товар');
  });

  it('оформляет заказ и показывает номер, блокируя повторную отправку', async () => {
    let finish;
    const fetcher = vi.fn().mockResolvedValueOnce(response(catalog)).mockResolvedValueOnce(response({token:'fixture'}))
      .mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    await mountShop(query('#app'), fetcher);
    validForm();
    submit();
    submit();
    await vi.waitFor(() => expect(finish).toBeTypeOf('function'));
    expect(query('#status').textContent).toContain('Оформляем');
    expect(query('button[type=submit]').disabled).toBe(true);
    submit();
    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(fetcher.mock.calls[2]).toEqual(['/api/orders', expect.objectContaining({body:'{"product":"chair"}',headers:expect.objectContaining({'X-Token':'fixture'})})]);
    finish(response({id:3, product:'chair', price:5000}, 201));
    await vi.waitFor(() => expect(query('#status').textContent).toContain('Заказ №3 оформлен'));
    expect(query('#password').value).toBe('');
  });

  it('показывает ошибку входа и даёт исправить пароль', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(response(catalog)).mockResolvedValueOnce(response({},401));
    await mountShop(query('#app'), fetcher);
    validForm();
    submit();
    await vi.waitFor(() => expect(query('[role=alert]').textContent).toContain('Проверьте имя'));
    expect(query('button[type=submit]').disabled).toBe(false);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
