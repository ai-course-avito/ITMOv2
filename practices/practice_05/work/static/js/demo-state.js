window.createDemoState = function (initial, validate, render, normalize) {
  let state = structuredClone({ ...initial });
  const listeners = new Set();
  let revision = 0;
  function update(patch) {
    const candidate = { ...state, ...patch };
    const validation = validate(candidate);
    if (validation !== true && validation !== undefined) return validation;
    if (validation === false) return { ok: false, error: { code: 'VALIDATION_ERROR', field: 'parameters', message: 'Проверьте параметры демонстрации.', constraint: 'значения должны входить в документированный диапазон', retryable: false } };
    const next = normalize ? normalize(candidate) : candidate;
    state = structuredClone({ ...next, revision: ++revision });
    render(state);
    listeners.forEach((fn) => fn({ ...state }));
    return { ok: true, state: structuredClone(state) };
  }
  return { get: () => structuredClone(state), subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }, update, reset() { return update(initial); } };
};
