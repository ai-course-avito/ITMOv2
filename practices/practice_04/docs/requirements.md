# Olympiad Start — requirements

## Product
Olympiad Start is a fictional teaching landing page for a math olympiad training camp for kids who are just starting out.
UI language: Russian.
Stack: vanilla HTML, CSS and JavaScript. No JS frameworks or runtime npm dependencies.
Everything lives on one page: `index.html`.

Do not invent factual claims about a real business: real addresses, real coaches, olympiad results or medals,
student or parent reviews, guarantees or years of operation.

## Feature A — one-page landing
Build one responsive `index.html` with:
- Header: Olympiad Start wordmark, anchor navigation and CTA «Записаться».
- Hero: clear value proposition (start olympiad math from zero, no competition experience needed), primary CTA to programs and secondary CTA to «Как проходят занятия».
- Exactly 3 benefits.
- «Для кого»: grades 5–9, comfortable with school math, no olympiad experience required.
- Exactly 3 program cards:
  - Старт (5–6 класс) — 4900 ₽ / month;
  - Основа (7–8 класс) — 5900 ₽ / month;
  - Интенсив (9 класс) — 6900 ₽ / month.
- Each program has short fictional copy, topics covered and format (group size, lessons per week).
- «Как проходят занятия»: 3 steps — choose a program, take a short entry quiz, attend a free trial lesson.
- Exactly 3 coach cards with fictional names and short bios; illustrated avatars, no photos.
- FAQ: exactly 4 questions as expandable items (`<details>` / `<summary>`).
- Final CTA linking to the sign-up section on the same page (`#signup`, built in Feature B).

## Feature B — sign-up and price calculator
Add a `#signup` section to `index.html` with a sign-up form and live price calculation:
- Fields: program (Старт / Основа / Интенсив), child's grade (5–9), duration (1, 3 or 6 months),
  parent's name, parent's email, consent checkbox for data processing.
- Price updates live when program or duration changes:
  - 1 month — full price;
  - 3 months — 5% discount;
  - 6 months — 10% discount.
- Show monthly price, discount and total in ₽.
- Validation on submit:
  - all fields required, consent must be checked;
  - email must be a valid format;
  - grade must match the program (Старт 5–6, Основа 7–8, Интенсив 9); otherwise suggest the right program.
- Errors appear next to the field, in Russian, and are announced to screen readers (`aria-live` or `aria-describedby`).
- On valid submit: no network request; replace the form with a confirmation summary
  (program, duration, total, «Мы свяжемся с вами по email»).
- «Выбрать» buttons on program cards scroll to `#signup` and preselect that program.
- JavaScript lives in `script.js`.
- Feature A must keep working: all sections, counts, anchors and CTAs unchanged.

Shared requirements:
- One page only: `index.html`.
- One stylesheet: `styles.css`.
- Semantic header/nav/main/section/footer.
- Keyboard-accessible links and controls.
- Responsive desktop/mobile layout.
- Friendly, encouraging tone for kids; clear and credible for parents.
- No photos of real children; use illustrations or simple shapes.
