window.renderDemoProjection = function (root, state) {
  const parameter = root.querySelector('[data-demo-parameter]');
  const status = root.querySelector('[data-demo-status], [role="status"]');
  const fallback = root.querySelector('[data-demo-fallback]');
  if (parameter) parameter.textContent = JSON.stringify(state.parameters);
  if (status) status.textContent = state.error ? state.error.message : `Состояние: ${state.status}`;
  if (fallback) fallback.hidden = false;
};
