(function () {
  const root = document.querySelector('[data-demo-id="chebyshev-interpolation"]');
  if (!root) return;
  const slider = root.querySelector('[data-node-count]');
  const label = root.querySelector('[data-node-label]');
  const path = root.querySelector('[data-plot]');
  const status = root.querySelector('[role="status"]');
  const initial = { contract_version: 'v1', demo_id: 'chebyshev-interpolation', status: 'idle', parameters: { node_count: 5 }, time: 0, frame: 0, formula_highlight: null, calculation: { mode: 'local', status: 'ready', operation: 'chebyshev_values' }, error: null };
  function render(state) {
    const n = state.parameters.node_count; label.textContent = `n = ${n}`;
    let d = ''; for (let i = 0; i <= 240; i += 1) { const x = -1 + i / 120; const y = Math.cos(n * Math.acos(Math.max(-1, Math.min(1, x)))); const px = i * 3; const py = 125 - y * 90; d += `${i ? 'L' : 'M'}${px.toFixed(2)},${py.toFixed(2)}`; }
    path.setAttribute('d', d); status.textContent = `График обновлён: число узлов n = ${n}`;
    if (window.renderDemoProjection) window.renderDemoProjection(root, state);
  }
  const state = window.createDemoState(initial, (candidate) => Number.isInteger(Number(candidate.parameters.node_count)) && Number(candidate.parameters.node_count) >= 1 && Number(candidate.parameters.node_count) <= 20, render, (candidate) => ({ ...candidate, parameters: { node_count: Number(candidate.parameters.node_count) } }));
  slider.addEventListener('input', () => state.update({ status: 'stepping', parameters: { node_count: slider.value } })); state.update({});
})();
