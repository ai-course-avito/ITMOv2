window.createDemoState = function (initial, validate, render) {
  let state = { ...initial };
  const listeners = new Set();
  function update(patch) {
    const next = { ...state, ...patch };
    if (!validate(next)) return false;
    state = next;
    render(state);
    listeners.forEach((fn) => fn({ ...state }));
    return true;
  }
  return { get: () => ({ ...state }), subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }, update, reset() { return update(initial); } };
};
