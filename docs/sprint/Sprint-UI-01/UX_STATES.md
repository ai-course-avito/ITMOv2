# UX States — Gamification UI (practice_05)

This document summarizes key UX states we implemented and how they manifest in the UI. Use it for QA and future polish.

Scope:
- Spins indicator and Play button states
- Wheel overlay, animation, and outcome messaging
- Emoji selection (new task and edit modal), limitations, and disabled states
- Limit banner UX

1) Play button and spins indicator
- Normal: “ИГРАТЬ” enabled, spins indicator shows remaining spins (e.g., “Крутки: 5”).
- Zero spins: button disabled; clicking opens limit banner instead of wheel.
- A11y: indicator updates with aria-live=polite; button has aria-label.

2) Wheel overlay
- Overlay opens on Play. Shows pointer, segmented labels (min 8), legend list.
- Animation first, then result message. Rotation stops at the winning segment (pointer at top).
- Long labels: constrained width, center alignment, ellipsis.
- Close via “Закрыть”.

3) Spin outcomes
- Emoji: message “Выпало эмодзи: <emoji>!”. If duplicate → “Эмодзи уже разблокировано — дубль игнорирован.” No duplicates added to inventory.
- Odd prize: friendly message without functional impact.
- Spins decrement after spin; at zero, limit banner opens.

4) Emoji selection — New task
- “Добавить эмодзи” opens panel of catalog items.
- Unlocked emojis: active; Locked: greyed (locked class), non-interactive, tooltip suggests unlocking via wheel.
- Limits: without perk → max 1 emoji; with perk (has_multi_emoji) → up to 3. Button disabled when limit reached with tooltip reason.
- Selected emojis appear as chips; each chip can be removed.

5) Emoji selection — Edit modal
- Chips show current selection (task.emojis or local UI mapping). Remove via × on chip.
- “Добавить ещё эмодзи” toggles panel; same locked/active rules as above.
- Limits enforced: 1 or 3 depending on perk. Save writes selection to UI-local store and PATCH payload.

6) Spins limit banner
- Full-screen overlay with dimmed background and blur for focus.
- Title “Лимит круток исчерпан”, copy explains reset after midnight; Close dismisses.
- High contrast, large type, top z-index.

Known caveats (UI demo mode)
- When backend endpoints are unavailable, demo data are used for profile, emoji catalog, spin pool, and spin results. Task–emoji assignments persist only on the client for demo.

QA checklist
- FR-002/007: Play disabled at 0 spins; banner opens on click.
- FR-003/012: Wheel has ≥1 emoji; min 8 segments; labels readable.
- FR-004: Spins decrement; result shown after animation; segment and message match.
- FR-006/006a/006b: Emoji panel shows locked states; chips render; removal works; tooltips present.
- FR-014/014a: Add-more disabled without perk; up to 3 with perk in both new and edit flows.
