# Style guide

Five rules for changes to Olympiad Start. Read this before editing code.
`AGENTS.md` has the full project rules; this file is the short list that is easy to break.

## 1. Check behaviour the way a visitor sees it
- Run `sh scripts/check.sh` for the page contract (sections, counts, prices, anchors).
- Use a real browser (Playwright) for anything a person does: click every new control,
  repeat it with the keyboard, read the console, check 360px and 1280px for horizontal scroll.
- A passing runner is not proof that a form, calculator or focus order works.

## 2. Colors and spacing come from `:root` tokens
- Add a custom property in `:root` and use `var(--...)` in the rule.
- No raw hex values outside `:root` in `styles.css`. Inline SVG illustrations are the only exception.
- Class names are BEM: `block`, `block__element`, `block--modifier`.

## 3. Native HTML before JavaScript
- Prefer `<details>`, anchor links and form attributes (`required`, `type="email"`) to scripts.
- When JavaScript is needed, it goes in `script.js`, without libraries or build steps.

## 4. Never weaken the runner to get a green result
- Do not edit `scripts/check.sh` or `scripts/check_page.py` to make a failing check pass.
- If a check looks wrong, say which one and why, and ask before changing it.
- Adding checks for a new feature is fine, and expected.

## 5. Only content from the requirements
- Names, prices, counts and steps come from `docs/requirements.md`.
- Fictional copy must not contain real-world claims: addresses, results, reviews,
  guarantees, years of operation.

## Good example
The FAQ follows rules 2 and 3: a native `<details>` element with BEM classes,
no JavaScript, and colors from tokens.

```html
<details class="faq__item">
  <summary class="faq__question">Нужен ли опыт олимпиад?</summary>
  <p class="faq__answer">Нет. Программы рассчитаны на тех, кто только начинает.</p>
</details>
```

```css
.faq__question::after {
  content: "+";
  color: var(--color-margin);
}

.faq__item[open] .faq__question::after {
  content: "−";
}
```
