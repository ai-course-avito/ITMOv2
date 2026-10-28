# UI Demonstration Contract

Each demo exposes a root with `data-demo-id`, a visible `role="status"` region with `aria-live="polite"`, keyboard-operable controls, an accessible SVG/Canvas label and description, and a static fallback/error region.

## Atomic state update

```json
{
  "demoId": "fourier-square-wave",
  "status": "stepping",
  "time": 0.2,
  "order": 10,
  "speed": 1,
  "formulaHighlight": 2,
  "errorCode": null
}
```

One update drives the visible label, plot, formula highlight, and live status. Failed updates do not partially update outputs.

## Controls

- Play and pause are keyboard- and pointer-operable and expose current state.
- Step forward is available in every non-error state.
- Reset returns to the documented initial state.
- Speed offers exactly `0.25x`, `0.5x`, `1x`, and `2x`.
- Left/Right arrows step backward/forward within the demo control group.
- Reduced motion disables autoplay but preserves explicit stepping.
