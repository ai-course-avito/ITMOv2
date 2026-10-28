(function () {
  const root = document.querySelector('[data-demo-id="chebyshev-interpolation"]');
  if (!root) return;
  const slider = root.querySelector('[data-node-count]');
  const label = root.querySelector('[data-node-label]');
  const path = root.querySelector('[data-plot]');
  const status = root.querySelector('[role="status"]');
  function render() {
    const n = Number(slider.value); label.textContent = `n = ${n}`;
    let d = ''; for (let i = 0; i <= 240; i += 1) { const x = -1 + i / 120; const y = Math.cos(n * Math.acos(Math.max(-1, Math.min(1, x)))); const px = i * 3; const py = 125 - y * 90; d += `${i ? 'L' : 'M'}${px.toFixed(2)},${py.toFixed(2)}`; }
    path.setAttribute('d', d); status.textContent = `График обновлён: n = ${n}`;
  }
  slider.addEventListener('input', render); render();
})();
