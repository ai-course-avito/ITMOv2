# Preference Contract

Preferences use one versioned JSON value under `ui:preferences:v1` in `localStorage`.

```json
{
  "version": 1,
  "theme": "dark",
  "gradientPreset": "spectral",
  "gradientIntensity": 1,
  "reducedMotion": false,
  "demoSpeed": 1,
  "lastDemoState": {"demoId": "fourier-square-wave", "order": 10}
}
```

The bootstrap reads and validates the value before non-critical scripts run. Storage exceptions, malformed JSON, unsupported versions, and invalid fields fall back to system preferences and in-memory state without console errors. Changes are written after successful state changes. No personal data is stored.
