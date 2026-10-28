(function () {
  const root = document.documentElement;
  const key = 'ui:preferences:v1';
  const defaults = { version: 1, theme: 'dark', gradientPreset: 'spectral', gradientIntensity: 1, reducedMotion: false, demoSpeed: 1, lastDemoState: null };
  const presets = {
    spectral: ['rgba(90,169,255,.35)', 'rgba(166,83,255,.25)', 'rgba(255,109,160,.2)'],
    oceanic: ['rgba(0,200,255,.35)', 'rgba(0,120,220,.25)', 'rgba(0,80,160,.2)'],
    aurora: ['rgba(168,255,120,.3)', 'rgba(120,220,255,.25)', 'rgba(255,180,120,.2)']
  };
  let state = { ...defaults };
  function valid(value) {
    return value && value.version === 1 && ['dark', 'light'].includes(value.theme) && Object.hasOwn(presets, value.gradientPreset) && Number.isFinite(value.gradientIntensity) && value.gradientIntensity >= 0 && value.gradientIntensity <= 1.5 && typeof value.reducedMotion === 'boolean' && [0.25, 0.5, 1, 2].includes(value.demoSpeed) && (value.lastDemoState === null || (typeof value.lastDemoState === 'object' && ['fourier-square-wave', 'chebyshev-interpolation'].includes(value.lastDemoState.demoId)));
  }
  function save() { try { localStorage.setItem(key, JSON.stringify(state)); } catch (_) {} }
  function apply() {
    if (state.theme === 'light') root.setAttribute('data-theme', 'light');
    else root.removeAttribute('data-theme');
    root.dataset.reducedMotion = state.reducedMotion ? '1' : '0';
    root.style.setProperty('--gradient-intensity', state.gradientIntensity);
    presets[state.gradientPreset].forEach((value, index) => root.style.setProperty(`--gradient-stop-${index + 1}`, value));
    document.querySelectorAll('[data-preference="theme"]').forEach((el) => { el.setAttribute('aria-pressed', String(state.theme === 'light')); el.textContent = state.theme === 'light' ? 'Тема: Светлая' : 'Тема: Тёмная'; });
  }
  try { const stored = JSON.parse(localStorage.getItem(key) || 'null'); if (valid(stored)) state = { ...state, ...stored }; } catch (_) {}
  window.sitePreferences = { get: () => ({ ...state }), set(patch) { const next = { ...state, ...patch }; if (!valid(next)) return false; state = next; apply(); save(); return true; } };
  apply();
  document.addEventListener('DOMContentLoaded', () => {
    const theme = document.querySelector('[data-preference="theme"]');
    const preset = document.querySelector('[data-preference="gradient-preset"]');
    const intensity = document.querySelector('[data-preference="gradient-intensity"]');
    const motion = document.querySelector('[data-preference="reduced-motion"]');
    theme?.addEventListener('click', () => window.sitePreferences.set({ theme: state.theme === 'light' ? 'dark' : 'light' }));
    preset?.addEventListener('change', (e) => window.sitePreferences.set({ gradientPreset: e.target.value }));
    intensity?.addEventListener('input', (e) => window.sitePreferences.set({ gradientIntensity: Number(e.target.value) }));
    motion?.addEventListener('change', (e) => window.sitePreferences.set({ reducedMotion: e.target.checked }));
    if (preset) preset.value = state.gradientPreset;
    if (intensity) intensity.value = state.gradientIntensity;
    if (motion) motion.checked = state.reducedMotion;
    apply();
  });
})();
