/** Регистрация и профиль в Mini App. */

import { api } from './api.js';

const DEFAULT_GRADE_HINTS = {
  1: 'Буквы и слоги, задания с картинками',
  2: 'Слова и предложения, с картинками',
  3: 'Части речи, состав слова',
  4: 'Орфография и предложение',
  5: 'Фонетика, лексика, морфология',
  6: 'Текст, стили, морфология',
  7: 'Причастие, деепричастие',
  8: 'Синтаксис простого предложения',
  9: 'Сложное предложение + изложение (аттестат)',
  10: 'Подготовка к старшей школе / база к ЦТ',
  11: 'ЦТ и ЦЭ — тестовый банк',
};

export function emptyRegForm(prefill = {}) {
  return {
    step: 1,
    role: prefill.role || null, // 'student' | 'parent'
    display_name: prefill.display_name || '',
    grade: prefill.grade || 9,
    goal: prefill.goal || 'improve',
    subject_id: prefill.subject_id || prefill.subject || null,
    city_id: prefill.city_id || prefill.city || null,
    city_name: prefill.city_name || '',
    school_id: prefill.school_id || prefill.school || null,
    school_name: prefill.school_name || '',
    cityQuery: '',
    schoolQuery: '',
    cityResults: [],
    schoolResults: [],
    subjects: [],
    goals: [],
    grades: Array.from({ length: 11 }, (_, i) => i + 1),
    gradeHints: { ...DEFAULT_GRADE_HINTS },
    allGoals: [],
    webAppUrl: '',
    canEditDomain: false,
    saving: false,
    error: '',
  };
}

export async function loadRegMeta(form) {
  const [cfg, subjects] = await Promise.all([api.config(), api.subjects()]);
  form.allGoals = cfg.goals || [];
  form.grades = cfg.grades || listRange(1, 12);
  form.gradeHints = { ...DEFAULT_GRADE_HINTS, ...(cfg.grade_hints || {}) };
  form.webAppUrl = cfg.web_app_url || '';
  form.canEditDomain = Boolean(cfg.debug && cfg.auth_bypass);
  form.subjects = subjects || [];
  if (!form.subject_id && form.subjects[0]) {
    form.subject_id = form.subjects[0].id;
  }
  form.goals = goalsForGrade(form.allGoals, form.grade);
  if (!form.goals.find((g) => g.id === form.goal)) {
    form.goal = form.goals[0]?.id || 'improve';
  }
  return form;
}

function listRange(from, toExclusive) {
  return Array.from({ length: toExclusive - from }, (_, i) => from + i);
}

export function goalsForGrade(allGoals, grade) {
  const g = Number(grade);
  return (allGoals || []).filter((goal) => {
    if (!goal.grades || !goal.grades.length) return true;
    return goal.grades.map(Number).includes(g);
  });
}

export function renderRegForm(form, { title, subtitle, submitLabel }) {
  if (!form.role) {
    return `
      <section class="hero">
        <h1>Добро пожаловать!</h1>
        <p>Выберите, кто вы, чтобы настроить удобный интерфейс:</p>
      </section>
      <section class="card goal-list" style="margin-top:12px">
        <button type="button" class="goal-card" data-action="reg-set-role" data-role="student" style="padding:18px;text-align:left">
          <div style="font-size:24px;margin-bottom:6px">🎓 Я ученик</div>
          <strong>Решаю тесты, качаю XP и готовлюсь к ЦТ/ЦЭ</strong>
          <p class="muted" style="margin-top:4px">Учеба, практика, статистика и турнирный рейтинг</p>
        </button>
        <button type="button" class="goal-card" data-action="reg-set-role" data-role="parent" style="padding:18px;text-align:left;margin-top:10px">
          <div style="font-size:24px;margin-bottom:6px">👨‍👩‍👧 Я родитель</div>
          <strong>Хочу следить за успеваемостью ребёнка</strong>
          <p class="muted" style="margin-top:4px">Отчёты в Telegram, прогресс, балл и активность</p>
        </button>
      </section>
    `;
  }

  const cityList = (form.cityResults || [])
    .map(
      (c) =>
        `<button type="button" class="pick-row" data-action="pick-city" data-id="${c.id}" data-name="${escAttr(c.name)}">${esc(c.name)}${c.region ? ` <span class="muted">${esc(c.region)}</span>` : ''}</button>`,
    )
    .join('');

  if (form.role === 'parent') {
    return `
      <section class="hero">
        <h1>Профиль родителя</h1>
        <p>Укажите имя и город для получения отчётов об успеваемости ребёнка</p>
      </section>
      <button type="button" class="linkish" data-action="reg-set-role" data-role="" style="margin-bottom:12px;display:inline-block">← Сменить роль (${form.role === 'parent' ? 'Родитель' : 'Ученик'})</button>
      ${form.error ? `<p class="err">${esc(form.error)}</p>` : ''}
      <section class="card">
        <label class="field-label">Ваше имя (как обращаться)
          <input class="family-input" id="reg-name" maxlength="100" placeholder="Например: Ольга Викторовна" value="${escAttr(form.display_name)}" />
        </label>
      </section>
      <section class="card">
        <h2>Ваш город</h2>
        <p class="muted">${form.city_name ? `Выбрано: ${esc(form.city_name)}` : 'Найдите и выберите город из списка'}</p>
        <input class="family-input" id="city-q" value="${escAttr(form.cityQuery)}" placeholder="Начни вводить город…" style="width:100%;margin:8px 0" />
        <div class="pick-list">${cityList || (form.cityQuery ? '<p class="muted">Ничего не найдено</p>' : '')}</div>
        ${form.city_id ? `<button type="button" class="linkish" data-action="clear-city">Сбросить город</button>` : ''}
        <p class="muted" style="margin-top:10px;font-size:12px">Если не нашли свой город, обратитесь в поддержку.</p>
      </section>
      <button type="button" class="btn block" data-action="reg-submit" ${form.saving ? 'disabled' : ''}>Сохранить и продолжить</button>
    `;
  }

  const goals = goalsForGrade(form.allGoals || form.goals || [], form.grade);
  form.goals = goals;
  const subjects = form.subjects || [];
  const gradeHint = form.gradeHints?.[String(form.grade)] || form.gradeHints?.[form.grade] || '';
  const activeGoal = goals.find((g) => g.id === form.goal);
  const schoolList = (form.schoolResults || [])
    .map(
      (s) =>
        `<button type="button" class="pick-row" data-action="pick-school" data-id="${s.id}" data-name="${escAttr(s.name)}">${esc(s.name)}</button>`,
    )
    .join('');

  const cityCard = form.city_id
    ? `<section class="card">
        <h2>Город</h2>
        <div style="display:flex;align-items:center;justify-content:space-between;margin-top:8px">
          <span style="font-size:17px;font-weight:700;color:var(--accent)">✓ ${esc(form.city_name)}</span>
          <button type="button" class="linkish" data-action="clear-city">Изменить город</button>
        </div>
      </section>`
    : `<section class="card">
        <h2>Город</h2>
        <p class="muted">Найдите и выберите свой город из списка</p>
        <input class="family-input" id="city-q" value="${escAttr(form.cityQuery)}" placeholder="Начни вводить город…" style="width:100%;margin:8px 0" />
        <div class="pick-list">${cityList || (form.cityQuery ? '<p class="muted">Ничего не найдено</p>' : '')}</div>
        <p class="muted" style="margin-top:10px;font-size:12px">Если не нашли свой город, обратитесь в поддержку.</p>
      </section>`;

  let schoolCard = '';
  if (!form.city_id) {
    schoolCard = `<section class="card"><h2>Школа</h2><p class="muted">Сначала выбери город выше</p></section>`;
  } else if (form.school_id) {
    schoolCard = `<section class="card">
      <h2>Школа</h2>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-top:8px">
        <span style="font-size:17px;font-weight:700;color:var(--accent)">✓ ${esc(form.school_name)}</span>
        <button type="button" class="linkish" data-action="clear-school">Изменить школу</button>
      </div>
    </section>`;
  } else {
    schoolCard = `<section class="card">
      <h2>Школа</h2>
      <p class="muted">Выбери свою школу из списка ниже</p>
      <input class="family-input" id="school-q" value="${escAttr(form.schoolQuery)}" placeholder="Номер или название школы…" style="width:100%;margin:8px 0" />
      <div class="pick-list">${schoolList || (form.schoolQuery ? '<p class="muted">Ничего не найдено</p>' : '')}</div>
      <p class="muted" style="margin-top:10px;font-size:12px">Если не нашли свою школу, обратитесь в поддержку.</p>
    </section>`;
  }

  return `
    <section class="hero">
      <h1>${esc(title)}</h1>
      <p>${esc(subtitle)}</p>
    </section>
    <button type="button" class="linkish" data-action="reg-set-role" data-role="" style="margin-bottom:12px;display:inline-block">← Сменить роль (${form.role === 'parent' ? 'Родитель' : 'Ученик'})</button>
    ${form.error ? `<p class="err">${esc(form.error)}</p>` : ''}
    <section class="card">
      <label class="field-label">Имя в рейтинге
        <input class="family-input" id="reg-name" maxlength="100" value="${escAttr(form.display_name)}" />
      </label>

      <p class="field-label" style="margin-top:14px">Класс обучения</p>
      <p class="muted" style="margin:4px 0 8px">Выбери класс, по которому будешь заниматься сейчас.</p>
      <div class="period-row grade-row">
        ${(form.grades || listRange(1, 12))
          .map(
            (g) =>
              `<button type="button" class="period-chip${Number(form.grade) === g ? ' active' : ''}" data-action="reg-grade" data-grade="${g}">${g}</button>`,
          )
          .join('')}
      </div>
      ${gradeHint ? `<div class="hint-box"><strong>${esc(form.grade)} класс:</strong> ${esc(gradeHint)}</div>` : ''}

      <p class="field-label" style="margin-top:14px">Цель подготовки</p>
      <p class="muted" style="margin:4px 0 8px">От цели зависит формат: школа, изложение или тесты ЦТ/ЦЭ.</p>
      <div class="goal-list">
        ${goals
          .map(
            (g) => `
            <button type="button" class="goal-card${form.goal === g.id ? ' active' : ''}" data-action="reg-goal" data-goal="${escAttr(g.id)}">
              <strong>${esc(g.label)}</strong>
              <span class="muted">${esc(g.hint || '')}</span>
            </button>`,
          )
          .join('')}
      </div>
      ${
        activeGoal?.hint
          ? `<div class="hint-box ok-tint">Сейчас выбрано: <strong>${esc(activeGoal.label)}</strong> — ${esc(activeGoal.hint)}</div>`
          : ''
      }

      <p class="field-label" style="margin-top:14px">Предмет</p>
      <div class="period-row">
        ${
          subjects.length
            ? subjects
                .map(
                  (s) =>
                    `<button type="button" class="period-chip${Number(form.subject_id) === s.id ? ' active' : ''}" data-action="reg-subject" data-id="${s.id}">${esc(s.name)}</button>`,
                )
                .join('')
            : `<p class="muted">Предметы ещё не загружены</p>`
        }
      </div>
    </section>
    ${cityCard}
    ${schoolCard}
    <button type="button" class="btn block" data-action="reg-submit" ${form.saving ? 'disabled' : ''}>${esc(submitLabel)}</button>
    <button type="button" class="btn secondary block" style="margin-top:8px" data-action="go-courses">Сначала посмотреть курсы</button>
  `;
}

export function payloadFromForm(form) {
  return {
    role: form.role || 'student',
    display_name: form.display_name,
    grade: form.grade,
    goal: form.goal,
    subject_id: form.subject_id,
    city_id: form.city_id,
    school_id: form.school_id,
  };
}

function esc(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function escAttr(s) {
  return esc(s).replaceAll("'", '&#39;');
}
