(function () {
  const root = document.querySelector('[data-demo-id="fourier-square-wave"]');
  if (!root || !window.createDemoState) return;
  const slider = root.querySelector('[data-testid="fourier-slider"]');
  const label = root.querySelector('[data-testid="fourier-N-label"]');
  const path = root.querySelector('[data-testid="fourier-plot"]');
  const status = root.querySelector('[data-status]');
  const play = root.querySelector('[data-action="play"]');
  const step = root.querySelector('[data-action="step"]');
  const reset = root.querySelector('[data-action="reset"]');
  const speed = root.querySelector('[data-speed]');
  let timer = null;
  const initial = {
    contract_version: 'v1', demo_id: 'fourier-square-wave', status: 'idle',
    parameters: { order: 10, speed: 1 }, time: 0, frame: 0,
    formula_highlight: null,
    calculation: { mode: 'local', status: 'ready', operation: 'fourier_partial_sum' }, error: null,
  };
  function sum(x, order) {
    let result = 0;
    for (let k = 0; k < order; k += 1) {
      const odd = 2 * k + 1;
      result += Math.sin(odd * x) / odd;
    }
    return 4 / Math.PI * result;
  }
  function render(state) {
    const order = state.parameters.order;
    let d = '';
    for (let i = 0; i <= 512; i += 1) {
      const x = -Math.PI + 2 * Math.PI * i / 512;
      const y = sum(x, order);
      d += `${i ? 'L' : 'M'}${(600 * i / 512).toFixed(2)},${(150 - y * 70).toFixed(2)}`;
    }
    slider.value = String(order);
    label.textContent = `N = ${order}`;
    path.setAttribute('d', d);
    status.textContent = `Состояние: ${state.status}; N = ${order}`;
  }
  const state = window.createDemoState(initial, (candidate) => {
    const order = Number(candidate.parameters.order);
    return Number.isInteger(order) && order >= 1 && order <= 50;
  }, render, (candidate) => ({
    ...candidate,
    parameters: { ...candidate.parameters, order: Number(candidate.parameters.order) },
  }));
  slider.addEventListener('input', () => state.update({ status: 'stepping', parameters: { ...state.get().parameters, order: slider.value } }));
  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
    if (play) { play.textContent = 'Пуск'; play.setAttribute('aria-pressed', 'false'); }
  }
  if (step) step.addEventListener('click', () => {
    stop();
    state.update({ status: 'stepping', parameters: { ...state.get().parameters, order: Math.min(50, state.get().parameters.order + 1) } });
  });
  if (reset) reset.addEventListener('click', () => { stop(); state.update({ status: 'idle', parameters: { ...state.get().parameters, order: 1 } }); });
  if (play) play.addEventListener('click', () => {
    if (timer) { stop(); state.update({ status: 'paused' }); return; }
    if (document.documentElement.dataset.reducedMotion === '1') { status.textContent = 'Автовоспроизведение отключено при уменьшенной анимации'; return; }
    play.textContent = 'Пауза'; play.setAttribute('aria-pressed', 'true');
    timer = setInterval(() => {
      const order = Math.min(50, state.get().parameters.order + 1);
      state.update({ status: order === 50 ? 'completed' : 'playing', parameters: { ...state.get().parameters, order } });
      if (order === 50) stop();
    }, Math.max(100, 400 / Number(speed ? speed.value : 1)));
  });
  if (speed) speed.addEventListener('change', () => { status.textContent = `Скорость: ${speed.value}x`; });
  root.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowRight' && step) step.click();
    if (event.key === 'ArrowLeft') {
      stop();
      state.update({ status: 'stepping', parameters: { ...state.get().parameters, order: Math.max(1, state.get().parameters.order - 1) } });
    }
  });
  state.update({});
})();
