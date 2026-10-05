// Feature B: sign-up form with live price calculation and client-side validation.
// No network requests: a valid submit replaces the form with a summary.

(function () {
  const form = document.getElementById('signup-form');
  if (!form) return;

  const DISCOUNTS = { 1: 0, 3: 5, 6: 10 };
  const DURATION_LABELS = { 1: '1 месяц', 3: '3 месяца', 6: '6 месяцев' };
  const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const program = form.elements.program;
  const grade = form.elements.grade;
  const parentName = form.elements.parent_name;
  const email = form.elements.email;
  const consent = form.elements.consent;

  const output = {
    monthly: document.getElementById('signup-monthly'),
    discount: document.getElementById('signup-discount'),
    total: document.getElementById('signup-total'),
    hint: document.getElementById('signup-price-hint'),
  };

  // Russian style: 4-digit numbers stay unsplit (4410), longer ones are grouped (26 460).
  function formatRub(value) {
    const digits = String(value);
    const grouped = value >= 10000 ? digits.replace(/\B(?=(\d{3})+(?!\d))/g, ' ') : digits;
    return grouped + ' ₽';
  }

  function selectedProgram() {
    const option = program.selectedOptions[0];
    if (!option || !option.value) return null;
    return {
      value: option.value,
      name: option.textContent.split(' (')[0],
      accusative: option.dataset.accusative,
      price: Number(option.dataset.price),
      grades: option.dataset.grades.split(' '),
    };
  }

  function months() {
    return Number(form.elements.duration.value) || 1;
  }

  function calculate(chosen) {
    const count = months();
    const percent = DISCOUNTS[count];
    const monthly = Math.round(chosen.price * (100 - percent) / 100);
    const total = monthly * count;
    return { count, percent, monthly, total, discount: chosen.price * count - total };
  }

  function updatePrice() {
    const chosen = selectedProgram();
    output.hint.hidden = Boolean(chosen);
    if (!chosen) {
      output.monthly.textContent = '—';
      output.discount.textContent = '—';
      output.total.textContent = '—';
      return;
    }
    const price = calculate(chosen);
    const sign = price.percent ? '−' : '';
    output.monthly.textContent = formatRub(price.monthly);
    output.discount.textContent = `${sign}${price.percent}% (${sign}${formatRub(price.discount)})`;
    output.total.textContent = formatRub(price.total);
  }

  function errorElement(field) {
    return document.getElementById(field.getAttribute('aria-describedby'));
  }

  function setError(field, message) {
    const element = errorElement(field);
    element.textContent = message;
    field.setAttribute('aria-invalid', 'true');
    return element;
  }

  function clearError(field) {
    errorElement(field).textContent = '';
    field.removeAttribute('aria-invalid');
  }

  function choose(value) {
    program.value = value;
    clearError(program);
    updatePrice();
  }

  function showMismatch(gradeValue) {
    const right = program.querySelector(`option[data-grades~="${gradeValue}"]`);
    const element = setError(program, `Для ${gradeValue} класса подходит «${right.textContent.split(' (')[0]}». `);
    const fix = document.createElement('button');
    fix.type = 'button';
    fix.className = 'signup-form__fix';
    fix.textContent = `Выбрать «${right.dataset.accusative}»`;
    fix.addEventListener('click', function () {
      choose(right.value);
      program.focus();
    });
    element.append(fix);
  }

  // Each validator returns an error message or '' when the field is valid.
  const validators = [
    [program, () => (program.value ? '' : 'Выберите программу.')],
    [grade, () => (grade.value ? '' : 'Выберите класс ребёнка.')],
    [parentName, () => (parentName.value.trim() ? '' : 'Укажите имя родителя.')],
    [email, () => {
      const value = email.value.trim();
      if (!value) return 'Укажите email родителя.';
      return EMAIL_PATTERN.test(value) ? '' : 'Проверьте email: например, name@example.ru.';
    }],
    [consent, () => (consent.checked ? '' : 'Нужно согласие на обработку данных.')],
  ];

  function validate() {
    const invalid = [];
    validators.forEach(function ([field, rule]) {
      const message = rule();
      if (message) {
        setError(field, message);
        invalid.push(field);
      } else {
        clearError(field);
      }
    });

    const chosen = selectedProgram();
    if (chosen && grade.value && !chosen.grades.includes(grade.value)) {
      showMismatch(grade.value);
      invalid.unshift(program);
    }
    return invalid;
  }

  function showSummary() {
    const chosen = selectedProgram();
    const price = calculate(chosen);
    const summary = document.createElement('div');
    summary.className = 'signup-summary';
    summary.innerHTML = `
      <h3 class="signup-summary__title" tabindex="-1">Спасибо, заявка готова!</h3>
      <dl class="signup-summary__list">
        <div class="signup-summary__row"><dt>Программа</dt><dd></dd></div>
        <div class="signup-summary__row"><dt>Срок</dt><dd></dd></div>
        <div class="signup-summary__row"><dt>Итого</dt><dd></dd></div>
      </dl>
      <p class="signup-summary__text">Мы свяжемся с вами по email</p>`;
    const values = summary.querySelectorAll('dd');
    values[0].textContent = `«${chosen.name}»`;
    values[1].textContent = DURATION_LABELS[price.count];
    values[2].textContent = formatRub(price.total);
    form.replaceWith(summary);
    summary.querySelector('.signup-summary__title').focus();
  }

  form.addEventListener('change', function (event) {
    if (event.target === program || event.target.name === 'duration') updatePrice();
    // Once an error is shown, re-check that field as the user fixes it.
    if (event.target.getAttribute('aria-invalid') === 'true') validate();
  });

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    const invalid = validate();
    if (invalid.length) {
      invalid[0].focus();
      return;
    }
    showSummary();
  });

  document.querySelectorAll('.program-card__pick').forEach(function (link) {
    link.addEventListener('click', function () {
      if (!form.isConnected) return;
      choose(link.dataset.program);
      // The anchor still scrolls to #signup. Fragment navigation resets focus after this
      // handler, so move keyboard focus to the preselected field once it is done.
      setTimeout(function () {
        program.focus({ preventScroll: true });
      }, 0);
    });
  });

  updatePrice();
})();
