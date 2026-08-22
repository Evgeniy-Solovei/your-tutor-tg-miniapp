import { api } from './api.js';
import { startAtmosphere } from './atmosphere.js';
import {
  emptyRegForm,
  goalsForGrade,
  loadRegMeta,
  payloadFromForm,
  renderRegForm,
} from './registration.js';
import { bootTelegram, getDevTgId, getUnsafeUser, setDevTgId } from './telegram.js';
import { THEMES, getTheme, initTheme, toggleTheme } from './theme.js';

const state = {
  route: 'home',
  me: null,
  daily: null,
  stats: null,
  rating: null,
  ratingScope: 'country',
  panel: null, // scores | streak | tariffs
  scores: null,
  scoresPage: 1,
  streak: null,
  tariffs: null,
  family: null,
  familyError: '',
  familyCode: '',
  reportChildId: null,
  reportPeriod: 'week',
  reportFrom: '',
  reportTo: '',
  reg: null,
  selected: new Set(),
  answerText: '',
  feedback: null,
  loading: false,
  error: '',
  devUsers: null,
  izloCatalog: null,
  izloQuery: '',
  catalog: null,
  coursesSubjectId: null,
  exam: null,
  examTimer: null,
};

let citySearchTimer = null;
let schoolSearchTimer = null;

function formatDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${d}.${m}.${y}`;
}

const view = () => document.getElementById('view');

function tgId() {
  return state.me?.telegram?.id || state.me?.tg_id || getUnsafeUser()?.id;
}

function toast(text) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = text;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 2200);
}

function esc(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function setRoute(route) {
  state.route = route;
  state.panel = null;
  document.querySelectorAll('.tab').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.route === route);
  });
  render();
  loadForRoute();
}

async function openPanel(panel) {
  const id = tgId();
  if (!id) return;
  state.panel = panel;
  state.loading = true;
  render();
  try {
    if (panel === 'scores') {
      state.scoresPage = 1;
      state.scores = await api.scores(id, 1);
    } else if (panel === 'streak') {
      state.streak = await api.streak(id);
    } else if (panel === 'tariffs') {
      state.tariffs = await api.tariffs();
    }
  } catch (e) {
    toast(e.message);
    state.panel = null;
  } finally {
    state.loading = false;
    render();
  }
}

async function loadScoresPage(page) {
  const id = tgId();
  if (!id) return;
  state.loading = true;
  render();
  try {
    state.scores = await api.scores(id, page);
    state.scoresPage = state.scores.page;
  } catch (e) {
    toast(e.message);
  } finally {
    state.loading = false;
    render();
  }
}

async function loadMe() {
  state.loading = true;
  state.error = '';
  render();
  try {
    if (!getDevTgId() && !getUnsafeUser()?.id) {
      try {
        const pack = await api.devUsers();
        state.devUsers = pack.users || [];
        if (state.devUsers[0]) setDevTgId(state.devUsers[0].tg_id);
        else setDevTgId(777842796); // новый пользователь для локальной регистрации
      } catch (_) {
        setDevTgId(777842796);
      }
    }
    state.me = await api.me();
    if (state.me && state.me.registered === false) {
      const suggested = state.me.telegram?.display_name || '';
      state.reg = emptyRegForm({ display_name: suggested });
      await ensureRegForm();
    }
  } catch (e) {
    state.error = e.message || 'Не удалось авторизоваться';
    try {
      const pack = await api.devUsers();
      state.devUsers = pack.users || [];
    } catch (_) {
      /* ignore */
    }
  } finally {
    state.loading = false;
    render();
  }
}

async function loadFamily() {
  state.loading = true;
  state.family = null;
  state.familyError = '';
  render();
  try {
    state.family = await api.family();
    const kids = state.family.children || [];
    if (!state.reportChildId && kids[0]) state.reportChildId = kids[0].id;
  } catch (e) {
    state.familyError = e.message || 'Не удалось загрузить семью';
    toast(e.message);
  } finally {
    state.loading = false;
    render();
  }
}

async function loadForRoute() {
  if (state.route === 'courses') {
    await loadCatalog();
    return;
  }

  const id = tgId();
  if (!id || !state.me) return;

  if (state.route === 'family') {
    await loadFamily();
    return;
  }

  if (state.route === 'profile') {
    state.reg = emptyRegForm({
      display_name: state.me.display_name,
      grade: state.me.grade,
      goal: state.me.goal,
      subject_id: state.me.subject,
      city_id: state.me.city,
      city_name: state.me.city_name,
      school_id: state.me.school,
      school_name: state.me.school_name,
    });
    await ensureRegForm();
    render();
    return;
  }

  if (!state.me.registered) return;

  try {
    if (state.route === 'home' || state.route === 'stats') {
      state.stats = await api.stats(id);
      try {
        state.dashboard = await api.dashboard(id);
      } catch (err) {
        console.error('Dashboard load error:', err);
      }
    }
    if (state.route === 'practice' || state.route === 'home') {
      state.daily = await api.daily(id);
      state.selected = new Set();
      state.answerText = '';
      state.feedback = null;
    }
    if (state.route === 'rating') {
      await loadRating(state.ratingScope);
      return;
    }
  } catch (e) {
    state.error = e.message;
  }
  render();
}

async function loadCatalog() {
  state.loading = true;
  render();
  try {
    state.catalog = await api.catalog();
    const items = state.catalog?.items || state.catalog?.subjects || [];
    if (!state.coursesSubjectId && items[0]) {
      state.coursesSubjectId = items[0].id;
    }
    if (state.me?.subject && items.some((s) => s.id === state.me.subject)) {
      state.coursesSubjectId = state.me.subject;
    }
  } catch (e) {
    toast(e.message);
  } finally {
    state.loading = false;
    render();
  }
}

function goalForGradeSwitch(grade, currentGoal) {
  const g = Number(grade);
  if (g <= 8) return 'improve';
  if (g === 9) return 'attestat';
  if (currentGoal === 'ct' || currentGoal === 'ce' || currentGoal === 'improve') {
    return currentGoal;
  }
  return 'ct';
}

async function loadRating(scope, period) {
  if (scope) state.ratingScope = scope;
  if (period) state.ratingPeriod = period;
  const s = state.ratingScope || 'country';
  const p = state.ratingPeriod || 'week';
  state.rating = await api.leaderboard(s, {
    period: p,
    city_id: state.me?.city || state.me?.filters?.city_id,
    school_id: state.me?.school || state.me?.filters?.school_id,
  });
  render();
}

function tariffShortLabel() {
  const id = state.tariffs?.current_plan_id;
  if (state.me?.is_pro || state.stats?.is_pro) return 'Разбор с ИИ';
  if (id === 'focus') return 'Ускорение';
  if (id === 'mentor') return 'Разбор с ИИ';
  return 'Старт';
}

function renderScoresPanel() {
  const pack = state.scores;
  if (!pack) return `<section class="card empty">Загружаем результаты…</section>`;
  const rows = pack.results || [];
  return `
    <section class="card">
      <div class="panel-head">
        <button type="button" class="linkish" data-action="close-panel">← Назад</button>
        <h2>Результаты</h2>
      </div>
      <p class="muted">От лучшего тестового балла к худшему</p>
      ${
        rows.length
          ? `<ul class="list">${rows
              .map(
                (r) => `<li>
                  <span>
                    <strong>${r.test_score ?? '—'}</strong>
                    <span class="muted"> · ${esc(r.kind_label)} · ${formatDate(r.date)}</span>
                    <br><span class="muted">первичный ${r.primary_score}/${r.max_primary}</span>
                  </span>
                </li>`,
              )
              .join('')}</ul>`
          : `<p class="muted">Пока нет сессий с баллами. Реши несколько заданий.</p>`
      }
      <div class="pager">
        <button type="button" class="btn secondary" data-action="scores-prev" ${pack.page <= 1 ? 'disabled' : ''}>←</button>
        <span class="muted">${pack.page} / ${pack.pages}</span>
        <button type="button" class="btn secondary" data-action="scores-next" ${pack.page >= pack.pages ? 'disabled' : ''}>→</button>
      </div>
    </section>
  `;
}

function renderStreakPanel() {
  const pack = state.streak;
  if (!pack) return `<section class="card empty">Загружаем серию…</section>`;
  const dates = pack.streak_dates || [];
  return `
    <section class="card">
      <div class="panel-head">
        <button type="button" class="linkish" data-action="close-panel">← Назад</button>
        <h2>Дней подряд</h2>
      </div>
      <p class="hero-inline"><strong>${pack.streak_days}</strong> <span class="muted">${pack.streak_days === 1 ? 'день' : pack.streak_days < 5 ? 'дня' : 'дней'}</span></p>
      ${
        dates.length
          ? `<p class="muted">Даты текущей серии:</p>
             <ul class="date-chips">${dates.map((d) => `<li>${formatDate(d)}</li>`).join('')}</ul>`
          : `<p class="muted">Серии пока нет — зайди завтра после практики, и пойдёт отсчёт.</p>`
      }
    </section>
  `;
}

function renderTariffsPanel() {
  const pack = state.tariffs;
  if (!pack) return `<section class="card empty">Загружаем тарифы…</section>`;
  return `
    <section class="card">
      <div class="panel-head">
        <button type="button" class="linkish" data-action="close-panel">← Назад</button>
        <h2>Тарифы и Подписка</h2>
      </div>
      <p class="muted">Безналичная оплата через ЕРИП и карты Беларуси (bePaid).</p>
      ${(pack.plans || [])
        .map(
          (p) => `
        <article class="plan${p.is_current ? ' current' : ''}">
          <div class="plan-top">
            <h3>${esc(p.name)}</h3>
            <strong>${esc(p.price_label)}</strong>
          </div>
          <p class="muted">${esc(p.tagline)}</p>
          <ul class="plan-features">
            ${(p.features || []).map((f) => `<li>✓ ${esc(f)}</li>`).join('')}
            ${(p.not_included || []).map((f) => `<li class="no">✗ ${esc(f)}</li>`).join('')}
          </ul>
          ${p.is_current ? '<p class="ok">Твой текущий тариф</p>' : `<button type="button" class="btn block" data-action="buy-plan" data-plan="${esc(p.id)}">💳 Оплатить через ЕРИП / Карткой</button>`}
        </article>`,
        )
        .join('')}
    </section>
  `;
}

function renderHome() {
  if (state.panel === 'scores') return renderScoresPanel();
  if (state.panel === 'streak') return renderStreakPanel();
  if (state.panel === 'tariffs') return renderTariffsPanel();

  const name = state.me?.display_name || getUnsafeUser()?.first_name || 'ученик';
  const score = state.stats?.best_test_score ?? 0;
  const streak = state.stats?.streak_days ?? state.me?.streak_days ?? 0;
  const daily = state.daily;
  const vibe = getTheme() === 'vibe';
  const progress =
    daily?.tasks_total > 0
      ? Math.round((daily.tasks_completed / daily.tasks_total) * 100)
      : 0;

  return `
    <section class="hero">
      <h1>${vibe ? `Йоу, ${esc(name)}` : `Привет, ${esc(name)}`}</h1>
      <p>${vibe ? 'Давай разберём пару заданий — и погнали дальше.' : 'Продолжим подготовку.'}${
        state.me?.grade ? ` · ${state.me.grade} класс` : ''
      }</p>
    </section>
    <div class="stats-row">
      <button type="button" class="stat clickable" data-action="open-scores"><strong>${score}</strong><span>лучший балл</span></button>
      <button type="button" class="stat clickable" data-action="open-streak"><strong>${streak}</strong><span>дней подряд</span></button>
      <button type="button" class="stat clickable" data-action="open-tariffs"><strong>${esc(tariffShortLabel())}</strong><span>тариф</span></button>
    </div>
    <section class="card">
      <h2>На сегодня</h2>
      ${
        daily?.can_practice === false
          ? `<p class="muted">${esc(daily.reason || 'Лимит на сегодня')}</p>`
          : `<p class="muted">${daily ? `${daily.tasks_completed} из ${daily.tasks_total}` : '—'} заданий</p>
             <div class="progress"><i style="width:${progress}%"></i></div>
             <button class="btn block" data-action="go-practice">${vibe ? 'Погнали' : 'Решать'}</button>`
      }
    </section>
    <section class="card" style="margin-top:12px">
      <h2>🎓 Симулятор ЦТ/ЦЭ</h2>
      <p class="muted">Полноразмерный билет из 40 вопросов с таймером на 180 минут и итоговым бланком результатов РИКЗ.</p>
      <button class="btn block" data-action="start-exam">Запустить симулятор (40 вопросов)</button>
    </section>
    <section class="card" style="margin-top:12px">
      <h2>Курсы и классы</h2>
      <p class="muted">Все предметы и классы 1–11: что уже есть в приложении и что можно выбрать.</p>
      <button class="btn block" data-action="go-courses">Смотреть курсы</button>
    </section>
    ${
      Number(state.me?.grade) === 9
        ? `<section class="card" style="margin-top:12px">
             <h2>Изложения</h2>
             <p class="muted">Официальный сборник НИО — тексты для выпускного экзамена 9 класса.</p>
             <button class="btn block" data-action="izlo-random">3 случайных текста</button>
             <button class="btn block secondary" style="margin-top:8px" data-action="izlo-catalog">Каталог текстов</button>
           </section>`
        : ''
    }
    <button type="button" class="btn secondary block" style="margin-top:12px" data-action="go-profile">Профиль и настройки</button>
  `;
}

function renderCourses() {
  const catalog = state.catalog;
  if (!catalog) {
    return `<div class="card empty">${state.loading ? 'Загружаем курсы…' : 'Не удалось загрузить каталог'}</div>`;
  }
  const items = catalog.items || catalog.subjects || [];
  const subject =
    items.find((s) => s.id === Number(state.coursesSubjectId)) || items[0] || null;
  const myGrade = Number(state.me?.grade) || null;
  const how = (catalog.how_it_works || [])
    .map((line) => `<li>${esc(line)}</li>`)
    .join('');

  return `
    <section class="hero">
      <h1>Курсы</h1>
      <p>Выбери класс, как у репетитора. Сейчас у тебя: ${
        myGrade ? `<strong>${myGrade} класс</strong>` : 'класс не выбран'
      }.</p>
    </section>
    ${how ? `<section class="card"><ol class="how-list">${how}</ol></section>` : ''}
    <section class="card">
      <p class="field-label">Предмет</p>
      <div class="period-row">
        ${items
          .map(
            (s) =>
              `<button type="button" class="period-chip${
                subject && s.id === subject.id ? ' active' : ''
              }" data-action="courses-subject" data-id="${s.id}">${esc(s.name)}</button>`,
          )
          .join('')}
      </div>
    </section>
    ${
      subject
        ? `<section class="card">
             <h2>${esc(subject.name)} · классы</h2>
             <div class="grade-grid">
               ${(subject.grades || [])
                 .map((g) => {
                   const active = myGrade === g.grade;
                   const empty = !g.available;
                   return `
                     <button type="button"
                       class="grade-tile${active ? ' active' : ''}${empty ? ' empty' : ''}"
                       data-action="courses-pick-grade"
                       data-grade="${g.grade}"
                       data-subject="${subject.id}"
                       ${empty ? 'data-empty="1"' : ''}>
                       <span class="grade-tile-title">${esc(g.title)}</span>
                       <span class="grade-tile-badge">${esc(g.badge || '')}</span>
                       <span class="muted">${
                         g.available
                           ? `${g.tasks} заданий · ${g.topics} тем`
                           : 'скоро'
                       }</span>
                       <span class="grade-tile-hint">${esc(g.hint || '')}</span>
                       ${active ? '<span class="grade-tile-now">твой класс</span>' : ''}
                     </button>`;
                 })
                 .join('')}
             </div>
           </section>`
        : `<section class="card"><p class="muted">Предметы ещё не загружены в базу.</p></section>`
    }
  `;
}

function renderPractice() {
  if (state.panel === 'izlo-catalog') return renderIzloCatalog();

  const daily = state.daily;
  if (!daily) return `<div class="card empty">Загружаем задание…</div>`;
  if (daily.can_practice === false) {
    return `<div class="card"><h2>Пауза</h2><p class="muted">${esc(daily.reason)}</p></div>`;
  }
  const task = daily.current_task;
  if (!task) {
    if (daily.content_available === false || (daily.tasks_total || 0) === 0) {
      return `
      <section class="card">
        <h2>Пока нет заданий</h2>
        <p class="muted">${esc(daily.empty_reason || `Для ${daily.practice_grade || state.me?.grade || 'этого'} класса задания ещё загружаются.`)}</p>
        <button class="btn block secondary" data-action="reload-daily">Обновить</button>
      </section>`;
    }
    return `
      <section class="card">
        <h2>Сессия закрыта</h2>
        <p class="ok">Первичный: ${daily.primary_score}/${daily.max_primary}
        ${daily.test_score != null ? ` · тестовый ≈${daily.test_score}` : ''}</p>
        <p class="muted">XP за сессию: ${daily.xp_earned}</p>
        <button class="btn block secondary" data-action="reload-daily">Обновить</button>
        ${
          Number(state.me?.grade) === 9
            ? `<button class="btn block" style="margin-top:8px" data-action="izlo-random">Ещё изложения</button>`
            : ''
        }
      </section>`;
  }

  const pct =
    daily.tasks_total > 0
      ? Math.round((daily.tasks_completed / daily.tasks_total) * 100)
      : 0;

  const multi = task.answer_format === 'multiple_choice';
  const hasOptImages = (task.options || []).some((o) => o.image_url);
  const options = (task.options || [])
    .map((o, idx) => {
      const selected = state.selected.has(String(o.id)) || state.selected.has(String(idx + 1));
      const pic = o.image_url
        ? `<img class="option-img" src="${esc(o.image_url)}" alt="${esc(o.text)}" />`
        : '';
      return `<button type="button" class="option${multi ? ' multi' : ''}${hasOptImages ? ' with-pic' : ''}${selected ? ' selected' : ''}" data-opt="${esc(o.id)}" data-order="${idx + 1}">${pic}<span>${esc(o.text)}</span></button>`;
    })
    .join('');

  const taskImage = task.image_url
    ? `<img class="task-img" src="${esc(task.image_url)}" alt="" />`
    : '';

  const readingText = task.reading_text || '';
  const readingBlock = readingText
    ? `<div class="reading-passage-card">
         <div class="reading-passage-header">📖 Текст к заданию</div>
         <div class="reading-passage-body">${esc(readingText)}</div>
       </div>`
    : '';

  const izloBlock = task.is_izlozhenie
    ? `<div class="izlo-card">
         <p class="izlo-badge">Официальный сборник · изложение</p>
         <h2>${esc(task.title || 'Изложение')}</h2>
         <p class="muted">${task.word_count ? `~${task.word_count} слов` : ''} · ${esc(task.topic_name)}</p>
         <p class="izlo-instruction">${esc(task.instruction || '')}</p>
         <div class="stimulus">${esc(task.stimulus_text || '')}</div>
       </div>`
    : `<div class="task-block${task.is_primary || task.image_url ? ' primary' : ''}">
         ${task.is_primary || task.image_url ? `<p class="izlo-badge">Картинка · ${esc(String(state.me?.grade || ''))} класс</p>` : ''}
         ${taskImage}
         ${readingBlock}
         <h2 class="task-question">${esc(task.question)}</h2>
       </div>`;

  return `
    <section class="card">
      <p class="muted">${esc(task.is_izlozhenie ? 'Изложение' : task.topic_name)} · ${daily.tasks_completed}/${daily.tasks_total}</p>
      <div class="progress"><i style="width:${pct}%"></i></div>
      ${izloBlock}
      ${
        options
          ? `<div class="options${hasOptImages ? ' pic-grid' : ''}">${options}</div>`
          : (task.answer_format === 'text'
            ? `<textarea class="input" id="free-answer" rows="8" placeholder="${task.is_izlozhenie ? 'Напиши подробное изложение…' : 'Напиши ответ…'}">${esc(state.answerText)}</textarea>`
            : `<input class="input" id="free-answer" placeholder="Введи ответ" value="${esc(state.answerText)}" />`)
      }
      <button class="btn block" data-action="submit" ${state.loading ? 'disabled' : ''}>Ответить</button>
      ${
        state.feedback
          ? `<p class="${state.feedback.is_correct ? 'ok' : 'bad'}" style="margin-top:12px">
              ${
                state.feedback.is_correct
                  ? '✅ Принято'
                  : state.feedback.points_earned > 0
                    ? '🟡 Частично'
                    : '❌ Нужно доработать'
              }
              ${
                state.feedback.max_points != null
                  ? ` · ${state.feedback.points_earned}/${state.feedback.max_points} перв.`
                  : ''
              }
              ${state.feedback.hint ? `<br>${esc(state.feedback.hint)}` : ''}
              ${state.feedback.correct_answer ? `<br>Эталон: ${esc(state.feedback.correct_answer)}` : ''}
            </p>
            ${
              state.feedback.can_request_ai
                ? (state.me?.is_pro
                    ? `<button class="btn block secondary" data-action="explain" style="margin-top:8px">🤖 Разбор с ИИ</button>`
                    : `<button class="btn block secondary pro-locked-btn" data-action="open-tariffs" style="margin-top:8px; opacity:0.65;">🤖 Разбор с ИИ 🔒 (В тарифе Pro)</button>`)
                : ''
            }
            <button class="btn block" data-action="next" style="margin-top:8px">Дальше</button>`
          : ''
      }
      ${state.feedback?.explanation ? `<p class="muted" style="margin-top:10px">${esc(state.feedback.explanation)}</p>` : ''}
    </section>
  `;
}

function renderIzloCatalog() {
  const items = state.izloCatalog?.items || [];
  const list = items
    .map(
      (it) => `
      <button type="button" class="list-row" data-action="izlo-pick" data-task-id="${it.id}">
        <span>${esc(it.title)}</span>
        <span class="muted">${it.word_count ? `~${it.word_count} сл.` : ''}</span>
      </button>`,
    )
    .join('');
  return `
    <section class="card">
      <button type="button" class="btn secondary" data-action="izlo-back">← Назад</button>
      <h2 style="margin-top:12px">Каталог изложений</h2>
      <p class="muted">${esc(state.izloCatalog?.source || '')} · ${items.length} текстов</p>
      <input class="input" id="izlo-search" placeholder="Поиск по названию" value="${esc(state.izloQuery)}" />
      <button class="btn block secondary" data-action="izlo-search">Найти</button>
      <div class="list" style="margin-top:12px">${list || '<p class="muted">Ничего не найдено</p>'}</div>
    </section>
  `;
}

function renderStats() {
  if (state.panel === 'scores') return renderScoresPanel();
  if (state.panel === 'streak') return renderStreakPanel();
  if (state.panel === 'tariffs') return renderTariffsPanel();

  const dash = state.dashboard;
  const weak = state.stats?.weak_topics || [];
  const sections = dash?.sections || [];
  const activity = dash?.daily_activity || [];
  const maxAct = Math.max(...activity.map((a) => a.total), 1);

  return `
    <section class="hero">
      <h1>Статистика & Прогресс</h1>
      <p>Твой личный дашборд успеваемости</p>
    </section>
    <div class="stats-row">
      <button type="button" class="stat clickable" data-action="open-scores">
        <strong>${dash?.best_test_score ?? state.stats?.best_test_score ?? '—'}</strong>
        <span>лучший балл</span>
      </button>
      <button type="button" class="stat clickable" data-action="open-streak">
        <strong>${dash?.accuracy_percent ?? 0}%</strong>
        <span>точность ответов</span>
      </button>
      <button type="button" class="stat clickable" data-action="open-tariffs">
        <strong>${esc(tariffShortLabel())}</strong>
        <span>тариф</span>
      </button>
    </div>

    <!-- График активности за 7 дней -->
    <section class="card" style="margin-top:12px">
      <h2>📈 Активность за неделю</h2>
      <p class="muted">Заданий решено по дням</p>
      <div style="display:flex;align-items:flex-end;justify-content:space-between;height:100px;margin-top:16px;padding:0 8px;gap:8px">
        ${
          activity.length
            ? activity.map((a) => {
                const h = Math.round((a.total / maxAct) * 70);
                return `
                  <div style="display:flex;flex-direction:column;align-items:center;flex:1;height:100%;justify-content:flex-end">
                    <span style="font-size:0.7rem;margin-bottom:4px;color:var(--text-muted, #888)">${a.total}</span>
                    <div style="width:100%;max-width:24px;background:var(--accent,#3b82f6);height:${Math.max(h, 4)}px;border-radius:4px 4px 0 0;opacity:${a.total > 0 ? 1 : 0.25}"></div>
                    <span style="font-size:0.7rem;margin-top:6px;color:var(--text-muted, #888)">${a.date}</span>
                  </div>`;
              }).join('')
            : '<p class="muted">Загружаем график…</p>'
        }
      </div>
    </section>

    <!-- Прогресс по разделам предмета -->
    ${
      sections.length
        ? `<section class="card" style="margin-top:12px">
            <h2>📚 Освоение разделов</h2>
            <div style="display:flex;flex-direction:column;gap:12px;margin-top:12px">
              ${sections.map((s) => `
                <div>
                  <div style="display:flex;justify-content:space-between;font-size:0.88rem;margin-bottom:4px">
                    <strong>${esc(s.title)}</strong>
                    <span class="muted">${s.mastery_percent}%</span>
                  </div>
                  <div class="progress" style="height:8px"><i style="width:${s.mastery_percent}%"></i></div>
                </div>
              `).join('')}
            </div>
          </section>`
        : ''
    }

    <!-- Слабые темы -->
    <section class="card" style="margin-top:12px">
      <h2>⚠️ Слабые темы</h2>
      ${
        weak.length
          ? `<ul class="list">${weak
              .map(
                (t) =>
                  `<li><span>${esc(t.topic_name)}</span><span class="muted">${Math.round(t.mastery_score * 100)}% · ошибок ${t.wrong_count}</span></li>`,
              )
              .join('')}</ul>`
          : `<p class="muted">Пока мало данных — реши несколько заданий.</p>`
      }
    </section>
  `;
}

async function ensureRegForm(prefill) {
  if (!state.reg) {
    state.reg = emptyRegForm(prefill || {});
  }
  if (!state.reg.subjects?.length || !state.reg.goals?.length) {
    try {
      await loadRegMeta(state.reg);
    } catch (e) {
      state.reg.error = e.message;
    }
  }
}

function syncRegInputsFromDom() {
  if (!state.reg) return;
  const name = document.getElementById('reg-name');
  if (name) state.reg.display_name = name.value.trim();
  const cq = document.getElementById('city-q');
  if (cq) state.reg.cityQuery = cq.value;
  const sq = document.getElementById('school-q');
  if (sq) state.reg.schoolQuery = sq.value;
}

function bindRegInputs() {
  const name = document.getElementById('reg-name');
  if (name) {
    name.addEventListener('input', (e) => {
      state.reg.display_name = e.target.value;
    });
  }
  const cq = document.getElementById('city-q');
  if (cq) {
    cq.addEventListener('input', (e) => {
      state.reg.cityQuery = e.target.value;
      clearTimeout(citySearchTimer);
      citySearchTimer = setTimeout(() => searchCities(), 280);
    });
  }
  const sq = document.getElementById('school-q');
  if (sq) {
    sq.addEventListener('input', (e) => {
      state.reg.schoolQuery = e.target.value;
      clearTimeout(schoolSearchTimer);
      schoolSearchTimer = setTimeout(() => searchSchools(), 280);
    });
  }
}

async function searchCities() {
  if (!state.reg) return;
  const q = (state.reg.cityQuery || '').trim();
  if (q.length < 2) {
    state.reg.cityResults = [];
    render();
    return;
  }
  try {
    const pack = await api.cities(q);
    state.reg.cityResults = pack.results || [];
  } catch (e) {
    toast(e.message);
  }
  render();
}

async function searchSchools() {
  if (!state.reg?.city_id) return;
  const q = (state.reg.schoolQuery || '').trim();
  try {
    const pack = await api.schools(state.reg.city_id, q);
    state.reg.schoolResults = pack.results || [];
  } catch (e) {
    toast(e.message);
  }
  render();
}

function renderProfile() {
  if (!state.reg) return `<section class="card empty">Загружаем профиль…</section>`;
  const notifActive = state.me?.notifications_enabled !== false;
  return `
    <button type="button" class="linkish" data-action="go-home" style="margin-bottom:8px">← На главную</button>
    <section class="card" style="margin-bottom:12px">
      <h2>🔔 Уведомления в Telegram</h2>
      <p class="muted">Ежедневный вызов «5 заданий дня» в Telegram-бот.</p>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-top:10px">
        <span>Напоминания в бот:</span>
        <button type="button" class="btn ${notifActive ? 'success' : 'secondary'}" data-action="toggle-notifications">
          ${notifActive ? '🔔 Включены' : '🔕 Отключены'}
        </button>
      </div>
    </section>
    ${renderRegForm(state.reg, {
      title: 'Профиль',
      subtitle: 'Можно сменить город, школу и предмет.',
      submitLabel: state.reg.saving ? 'Сохраняем…' : 'Сохранить',
    })}
  `;
}

function renderRegistration() {
  if (!state.reg) return `<section class="card empty">Готовим регистрацию…</section>`;
  return renderRegForm(state.reg, {
    title: 'Регистрация',
    subtitle: 'Имя, класс, цель, предмет, город и школа — всё обязательно.',
    submitLabel: state.reg.saving ? 'Сохраняем…' : 'Готово, начать',
  });
}

function renderFamily() {
  const pack = state.family;
  if (!pack && state.loading) {
    return `<section class="card empty">Загружаем семью…</section>`;
  }
  if (!pack) {
    return `<section class="card empty">
      <p>${esc(state.familyError || 'Не удалось загрузить семью.')}</p>
      <button type="button" class="btn secondary" data-action="family-retry">Попробовать ещё раз</button>
    </section>`;
  }

  const isParent = Boolean(pack.is_parent || (state.me && state.me.is_parent));
  const invite = pack.invite;
  const children = pack.children || [];
  const parents = pack.parents || [];
  const periods = pack.periods || [];

  // ЭКРАН ДЛЯ РОДИТЕЛЯ
  if (isParent) {
    const kidsBlock =
      children.length === 0
        ? `<p class="muted">У вас пока нет привязанных детей. Введите 6-значный код от ребёнка выше.</p>`
        : children
            .map(
              (c) => `
          <div class="child-card">
            <div>
              <strong>${esc(c.display_name)}</strong>
              <span class="muted"> · ${c.grade} кл. · серия ${c.streak_days} дн.</span>
              ${c.city_name ? `<br><span class="muted">${esc(c.city_name)}${c.school_name ? ' · ' + esc(c.school_name) : ''}</span>` : ''}
            </div>
            <button type="button" class="btn secondary" data-action="pick-child" data-id="${c.id}">
              ${state.reportChildId === c.id ? '✓ Выбран' : 'Выбрать'}
            </button>
          </div>`,
            )
            .join('');

    const customDates =
      state.reportPeriod === 'custom'
        ? `<div class="date-fields">
            <label>С <input type="date" id="report-from" value="${esc(state.reportFrom)}" /></label>
            <label>По <input type="date" id="report-to" value="${esc(state.reportTo)}" /></label>
          </div>`
        : '';

    return `
      <section class="hero">
        <h1>👨‍👩‍👧 Кабинет родителя</h1>
        <p>Следите за успехами детей и получайте регулярные отчёты в Telegram</p>
      </section>
      <section class="card">
        <h2>Привязать ребёнка</h2>
        <p class="muted">Введите 6-значный код, который отображается в Mini App у вашего ребёнка.</p>
        <input class="family-input" id="family-code" maxlength="8" placeholder="Код, например A3K7X2" value="${esc(state.familyCode)}" style="width:100%;margin:8px 0 10px;text-transform:uppercase" />
        <button type="button" class="btn block" data-action="family-link">Привязать ребёнка</button>
      </section>
      <section class="card">
        <h2>Мои дети (${children.length})</h2>
        <div style="margin-top:8px">${kidsBlock}</div>
      </section>
      ${
        children.length
          ? `<section class="card">
          <h2>Сформировать отчёт</h2>
          <p class="muted">Выберите период — готовый отчёт отравится вам прямо в диалог с ботом.</p>
          <div class="period-row">
            ${periods
              .map(
                (p) =>
                  `<button type="button" class="period-chip${state.reportPeriod === p.id ? ' active' : ''}" data-action="report-period" data-period="${p.id}">${esc(p.label)}</button>`,
              )
              .join('')}
          </div>
          ${customDates}
          <button type="button" class="btn block" data-action="family-report" ${state.reportChildId ? '' : 'disabled'}>Отправить отчёт в бот</button>
        </section>`
          : ''
      }
    `;
  }

  // ЭКРАН ДЛЯ УЧЕНИКА
  const inviteBlock = invite
    ? `<section class="card" style="text-align:center">
        <h2>Ваш код для родителя</h2>
        <p class="muted">Покажите этот код родителю или отправьте приглашение. Введя этот код во вкладке «Семья», родитель будет получать отчёты о вашем прогрессе.</p>
        <p class="invite-code" style="font-size:2.2rem;font-weight:800;letter-spacing:4px;color:var(--accent);margin:14px 0">${esc(invite.code)}</p>
        <button type="button" class="btn block" data-action="family-share-code" data-code="${escAttr(invite.code)}">📱 Скопировать приглашение</button>
        <button type="button" class="btn secondary block" style="margin-top:8px" data-action="family-new-code">Обновить код</button>
      </section>`
    : `<section class="card">
        <h2>Код для родителя</h2>
        <p class="muted">Генерируем ваш личный код...</p>
        <button type="button" class="btn block" data-action="family-new-code">Получить код</button>
      </section>`;

  const parentsList = parents.length
    ? parents
        .map(
          (p) => `
        <div class="child-card">
          <div>
            <strong>👨‍👩‍👧 ${esc(p.display_name || 'Родитель')}</strong>
            <br><span class="muted">Привязан · Еженедельные отчёты включены</span>
          </div>
        </div>`,
        )
        .join('')
    : `<p class="muted">Родители пока не привязаны.</p>`;

  return `
    <section class="hero">
      <h1>🎓 Семья и родительский контроль</h1>
      <p>Поделитесь кодом с родителями, чтобы они видели ваши достижения!</p>
    </section>
    ${inviteBlock}
    <section class="card">
      <h2>Привязанные родители</h2>
      ${parentsList}
    </section>
  `;
}

function renderLeaguePrizes(league) {
  if (!league || !league.has_prizes) return '';
  return `
    <section class="card" style="margin-bottom:12px;background:linear-gradient(135deg,rgba(255,215,0,0.12),rgba(255,140,0,0.08));border:1px solid rgba(255,215,0,0.4)">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <h2 style="margin:0;font-size:1.05rem;color:#d4af37">🏆 ${esc(league.title)}</h2>
        <span class="chip active" style="font-size:0.75rem">${esc(league.period_type === 'month' ? 'Месяц' : 'Неделя')}</span>
      </div>
      <div style="font-size:0.88rem;line-height:1.5;display:flex;flex-direction:column;gap:4px">
        ${league.prize_first_place ? `<div>${esc(league.prize_first_place)}</div>` : ''}
        ${league.prize_second_place ? `<div>${esc(league.prize_second_place)}</div>` : ''}
        ${league.prize_third_place ? `<div>${esc(league.prize_third_place)}</div>` : ''}
        ${league.prizes_text ? `<p class="muted" style="margin-top:6px;font-size:0.8rem">${esc(league.prizes_text)}</p>` : ''}
      </div>
    </section>
  `;
}

function renderRating() {
  const entries = state.rating?.entries || [];
  const filters = state.rating?.filters || {};
  const scope = state.ratingScope || 'country';
  const period = state.ratingPeriod || 'week';
  const league = state.rating?.active_league;

  return `
    <section class="hero">
      <h1>Рейтинг</h1>
      <p>${esc(state.rating?.title || 'По баллу')} · тестовый балл</p>
    </section>

    <!-- Фильтр периода: Неделя / Месяц / Всё время -->
    <div class="filters" style="margin-bottom:12px;display:flex;gap:6px">
      <button type="button" class="chip${period === 'week' ? ' active' : ''}" data-action="rating-period" data-period="week">⚡ Неделя</button>
      <button type="button" class="chip${period === 'month' ? ' active' : ''}" data-action="rating-period" data-period="month">📅 Месяц</button>
      <button type="button" class="chip${period === 'all' ? ' active' : ''}" data-action="rating-period" data-period="all">🏆 Всё время</button>
    </div>

    ${renderLeaguePrizes(league)}

    <section class="card">
      <div class="filters">
        <button type="button" class="chip${scope === 'country' ? ' active' : ''}" data-action="rating-scope" data-scope="country">Страна</button>
        <button type="button" class="chip${scope === 'grade' ? ' active' : ''}" data-action="rating-scope" data-scope="grade">🎒 Мой класс</button>
        <button type="button" class="chip${scope === 'city' ? ' active' : ''}" data-action="rating-scope" data-scope="city" ${filters.has_city ? '' : 'disabled'} title="${filters.has_city ? esc(filters.city_name || '') : 'Город не указан в профиле'}">Город</button>
        <button type="button" class="chip${scope === 'school' ? ' active' : ''}" data-action="rating-scope" data-scope="school" ${filters.has_school ? '' : 'disabled'} title="${filters.has_school ? esc(filters.school_name || '') : 'Школа не указана в профиле'}">Школа</button>
      </div>
      <p class="filter-note">${
        scope === 'grade' && filters.grade
          ? `${filters.grade} класс`
          : scope === 'city' && filters.city_name
            ? esc(filters.city_name)
            : scope === 'school' && filters.school_name
              ? esc(filters.school_name)
              : 'Сортировка: лучший тестовый балл, затем первичные'
      }</p>
      ${
        entries.length
          ? `<ul class="list">${entries
              .map(
                (e, i) =>
                  `<li class="${e.is_me ? 'me' : ''}"><span>${i + 1}. ${esc(e.display_name)}${e.is_me ? ' (ты)' : ''}</span><span class="muted">${e.test_score ?? 0}</span></li>`,
              )
              .join('')}</ul>`
          : `<p class="muted">${esc(state.rating?.empty_reason || 'Пока пусто.')}</p>`
      }
    </section>
  `;
}
async function startExamSimulator(variantId = null) {
  const id = tgId();
  if (!id) return;
  state.loading = true;
  render();
  try {
    const data = await api.startExam(id, { variant_id: variantId });
    state.exam = {
      session_id: data.session_id,
      title: data.title || 'Симулятор ЦТ/ЦЭ',
      time_limit_seconds: data.time_limit_seconds || 10800,
      time_remaining: data.time_limit_seconds || 10800,
      time_spent_seconds: 0,
      tasks: data.tasks || [],
      currentIndex: 0,
      answers: {},
      protocol: null,
    };
    startExamTimer();
  } catch (e) {
    toast(e.message || 'Не удалось запустить симулятор');
    state.route = 'home';
  } finally {
    state.loading = false;
    render();
  }
}

function startExamTimer() {
  if (state.examTimer) clearInterval(state.examTimer);
  state.examTimer = setInterval(() => {
    if (!state.exam || state.exam.protocol) {
      clearInterval(state.examTimer);
      return;
    }
    state.exam.time_spent_seconds++;
    state.exam.time_remaining = Math.max(
      0,
      state.exam.time_limit_seconds - state.exam.time_spent_seconds,
    );
    const timerEl = document.getElementById('exam-timer-display');
    if (timerEl) {
      timerEl.textContent = `⏱️ ${formatExamTimer(state.exam.time_remaining)}`;
      if (state.exam.time_remaining < 600) timerEl.classList.add('warning');
    }
    if (state.exam.time_remaining <= 0) {
      clearInterval(state.examTimer);
      toast('Время вышло! Автоматическая сдача бланка...');
      submitExamSimulator();
    }
  }, 1000);
}

function formatExamTimer(sec) {
  const h = String(Math.floor(sec / 3600)).padStart(2, '0');
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, '0');
  const s = String(sec % 60).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function saveCurrentExamAnswer() {
  if (!state.exam || !state.exam.tasks) return;
  const task = state.exam.tasks[state.exam.currentIndex];
  if (!task) return;
  const input = document.getElementById('exam-short-text');
  if (input) {
    state.exam.answers[task.session_task_id] = input.value.trim();
  }
}

async function submitExamSimulator() {
  const id = tgId();
  if (!id || !state.exam) return;
  saveCurrentExamAnswer();
  if (state.examTimer) clearInterval(state.examTimer);
  state.loading = true;
  render();
  try {
    const answersPayload = Object.entries(state.exam.answers).map(
      ([stId, text]) => ({
        session_task_id: Number(stId),
        answer_text: text,
      }),
    );
    const protocol = await api.submitExam(id, {
      session_id: state.exam.session_id,
      answers: answersPayload,
      time_spent_seconds: state.exam.time_spent_seconds,
    });
    state.exam.protocol = protocol;
  } catch (e) {
    toast(e.message || 'Ошибка сдачи бланка');
  } finally {
    state.loading = false;
    render();
  }
}

function renderExamSimulator() {
  const ex = state.exam;
  if (!ex) return '<div class="card empty">Нет активной сессии симулятора</div>';
  if (ex.protocol) return renderExamProtocol();

  const currentTask = ex.tasks[ex.currentIndex];
  if (!currentTask) return '<div class="card empty">Нет доступных вопросов</div>';

  const currentStId = currentTask.session_task_id;
  const currentAnswer = ex.answers[currentStId] || '';

  const gridHtml = ex.tasks
    .map((t, idx) => {
      const stId = t.session_task_id;
      const isAnswered = Boolean(ex.answers[stId]);
      const isActive = idx === ex.currentIndex;
      return `<button type="button" class="exam-grid-btn ${isAnswered ? 'answered' : ''} ${isActive ? 'active' : ''}" data-action="exam-jump" data-index="${idx}">${idx + 1}</button>`;
    })
    .join('');

  const readingText = currentTask.reading_text || currentTask.task?.reading_text || '';
  const readingBlock = readingText
    ? `<div class="reading-passage-card">
         <div class="reading-passage-header">📖 Текст к заданию</div>
         <div class="reading-passage-body">${esc(readingText)}</div>
       </div>`
    : '';

  const options = currentTask.options || [];
  const fmt = currentTask.answer_format || 'single_choice';
  let inputHtml = '';

  if (fmt === 'single_choice') {
    inputHtml = options
      .map(
        (opt) => `
        <button type="button" class="option ${currentAnswer === opt.key ? 'selected' : ''}" data-action="exam-select-single" data-key="${opt.key}">
          <strong>${esc(opt.key)}</strong>. ${esc(opt.text)}
        </button>`,
      )
      .join('');
  } else if (fmt === 'multiple_choice') {
    const selectedKeys = new Set(currentAnswer ? currentAnswer.split(',') : []);
    inputHtml = options
      .map((opt) => {
        const sel = selectedKeys.has(opt.key);
        return `
        <button type="button" class="option ${sel ? 'selected' : ''}" data-action="exam-toggle-multi" data-key="${opt.key}">
          <strong>${sel ? '☑' : '☐'} ${esc(opt.key)}</strong>. ${esc(opt.text)}
        </button>`;
      })
      .join('');
  } else {
    inputHtml = `
      <input type="text" class="input" id="exam-short-text" placeholder="Введи краткий ответ..." value="${esc(currentAnswer)}">
      <button class="btn block secondary" data-action="exam-save-short">Сохранить ответ</button>`;
  }

  return `
    <div class="exam-header">
      <div>
        <h2 style="margin:0; font-size:1rem">🎓 ${esc(ex.title)}</h2>
        <span class="muted">Вопрос ${ex.currentIndex + 1} из ${ex.tasks.length}</span>
      </div>
      <div class="exam-timer ${ex.time_remaining < 600 ? 'warning' : ''}" id="exam-timer-display">
        ⏱️ ${formatExamTimer(ex.time_remaining)}
      </div>
    </div>

    <div class="exam-grid">
      ${gridHtml}
    </div>

    <section class="card">
      ${readingBlock}
      <div class="task-question">${esc(currentTask.question)}</div>
      <div style="margin-top:14px">${inputHtml}</div>

      <div style="display:flex; gap:10px; margin-top:16px">
        <button type="button" class="btn secondary block" data-action="exam-prev" ${ex.currentIndex === 0 ? 'disabled' : ''}>← Назад</button>
        <button type="button" class="btn block" data-action="exam-next" ${ex.currentIndex === ex.tasks.length - 1 ? 'disabled' : ''}>Далее →</button>
      </div>
      <button type="button" class="btn secondary block" style="margin-top:10px; border-color:var(--danger); color:var(--danger)" data-action="exam-submit-confirm">📋 Сдать бланк экзамена</button>
    </section>
  `;
}

function renderExamProtocol() {
  const p = state.exam?.protocol;
  if (!p) return '<div class="card empty">Нет бланка результатов</div>';

  const mins = Math.floor(p.time_spent_seconds / 60);
  const secs = p.time_spent_seconds % 60;

  const resultItems = (p.results || [])
    .map((r) => {
      const cls = r.is_correct ? 'correct' : r.points_earned > 0 ? 'partial' : 'wrong';
      const icon = r.is_correct ? '✅' : r.points_earned > 0 ? '🟡' : '❌';
      return `
      <div class="exam-result-item ${cls}">
        <div>
          <strong>${icon} №${r.order} (${esc(r.task_number)})</strong>
          <div class="muted" style="font-size:0.8rem; margin-top:2px">Твой ответ: ${esc(r.user_answer || '—')}</div>
        </div>
        <div style="font-weight:700; font-size:0.95rem">
          ${r.points_earned}/${r.max_points} б.
        </div>
      </div>`;
    })
    .join('');

  return `
    <section class="card exam-protocol-card">
      <h2 style="margin:0; font-size:1.2rem">📋 Итоговый Бланк Результатов</h2>
      <p class="muted" style="margin-top:4px">Официальный пересчёт по шкале РИКЗ</p>

      <div class="exam-score-big">${p.test_score} / 100</div>
      <div class="exam-score-sub">Первичный балл: <strong>${p.primary_score} из ${p.max_primary}</strong></div>

      <div class="exam-level-badge">🎯 ${esc(p.level_description)}</div>
      <div class="muted" style="font-size:0.85rem">⏱️ Время выполнения: ${mins} мин ${secs} сек</div>

      <button class="btn block" style="margin-top:16px" data-action="exam-exit">Завершить симулятор</button>
    </section>

    <section class="card">
      <h2>Детализация бланка (40 вопросов)</h2>
      <div class="exam-result-list">
        ${resultItems}
      </div>
    </section>
  `;
}

function render() {
  const root = view();
  if (!root) return;

  const theme = THEMES[getTheme()];
  document.getElementById('theme-toggle-label').textContent = theme.nextLabel;
  document.getElementById('brand-sub').textContent = theme.sub;

  if (state.loading && !state.me) {
    root.innerHTML = `<div class="card empty">Подключаем Telegram…</div>`;
    return;
  }

  if (state.error && !state.me) {
    const users = state.devUsers || [];
    root.innerHTML = `
      <section class="card">
        <h2>Локальный вход</h2>
        <p class="muted">${esc(state.error)}</p>
        ${
          users.length
            ? `<p class="muted">Выбери ученика:</p>
               ${users
                 .map(
                   (u) =>
                     `<button class="btn block secondary" style="margin-top:8px" data-action="dev-login" data-tg="${u.tg_id}">${esc(u.display_name)} · ${u.tg_id}</button>`,
                 )
                 .join('')}`
            : `<p class="muted">Включи TELEGRAM_AUTH_BYPASS=True и открой <code>/app/?dev_tg_id=...</code></p>`
        }
      </section>`;
    return;
  }

  if (
    state.me &&
    state.me.registered === false &&
    state.route !== 'family' &&
    state.route !== 'courses'
  ) {
    root.innerHTML = renderRegistration();
    bindRegInputs();
    return;
  }

  if (state.route === 'home') root.innerHTML = renderHome();
  else if (state.route === 'courses') root.innerHTML = renderCourses();
  else if (state.route === 'practice') root.innerHTML = renderPractice();
  else if (state.route === 'exam') root.innerHTML = renderExamSimulator();
  else if (state.route === 'stats') root.innerHTML = renderStats();
  else if (state.route === 'rating') root.innerHTML = renderRating();
  else if (state.route === 'family') root.innerHTML = renderFamily();
  else if (state.route === 'profile') {
    root.innerHTML = renderProfile();
    bindRegInputs();
  }

  // bind free answer if present
  const free = document.getElementById('free-answer');
  if (free) {
    free.addEventListener('input', (e) => {
      state.answerText = e.target.value;
    });
  }
  const codeInput = document.getElementById('family-code');
  if (codeInput) {
    codeInput.addEventListener('input', (e) => {
      state.familyCode = e.target.value.toUpperCase();
    });
  }
  const fromEl = document.getElementById('report-from');
  const toEl = document.getElementById('report-to');
  if (fromEl) {
    fromEl.addEventListener('change', (e) => {
      state.reportFrom = e.target.value;
    });
  }
  if (toEl) {
    toEl.addEventListener('change', (e) => {
      state.reportTo = e.target.value;
    });
  }
}

async function submitAnswer() {
  const id = tgId();
  const task = state.daily?.current_task;
  if (!id || !task) return;

  let answer = state.answerText.trim();
  if (task.options?.length) {
    const orders = [...state.selected]
      .map((x) => Number(x))
      .filter(Boolean)
      .sort((a, b) => a - b);
    // selected stores option ids; map to order by clicking dataset
    const chosenOrders = [];
    document.querySelectorAll('.option.selected').forEach((el) => {
      chosenOrders.push(el.dataset.order);
    });
    answer = chosenOrders.sort((a, b) => Number(a) - Number(b)).join(',');
  }
  if (!answer) {
    toast('Выбери или введи ответ');
    return;
  }

  state.loading = true;
  render();
  try {
    state.feedback = await api.submit(id, task.session_task_id, answer);
    toast(state.feedback.is_correct ? 'Верно' : 'Есть ошибки');
  } catch (e) {
    toast(e.message);
  } finally {
    state.loading = false;
    render();
  }
}

async function explain() {
  const id = tgId();
  const task = state.daily?.current_task;
  if (!id || !task) return;
  try {
    const data = await api.explain(id, task.session_task_id);
    state.feedback = { ...state.feedback, explanation: data.explanation };
    render();
  } catch (e) {
    toast(e.message);
  }
}

function bindUi() {
  document.getElementById('theme-toggle')?.addEventListener('click', () => {
    const next = toggleTheme();
    startAtmosphere(next);
    render();
    toast(next === 'vibe' ? 'Тема: Вайб' : 'Тема: Спокойная');
  });

  document.querySelectorAll('.tab').forEach((btn) => {
    btn.addEventListener('click', () => setRoute(btn.dataset.route));
  });

  document.getElementById('view')?.addEventListener('click', async (e) => {
    const t = e.target.closest('[data-action], .option');
    if (!t) return;

    if (t.classList.contains('option')) {
      const task = state.daily?.current_task;
      const order = t.dataset.order;
      if (!task) return;
      if (task.answer_format === 'multiple_choice') {
        if (state.selected.has(order)) state.selected.delete(order);
        else state.selected.add(order);
      } else {
        state.selected = new Set([order]);
      }
      render();
      return;
    }

    const action = t.dataset.action;
    if (action === 'dev-login') {
      setDevTgId(t.dataset.tg);
      state.error = '';
      await loadMe();
      await loadForRoute();
      return;
    }
    if (action === 'rating-scope') {
      await loadRating(t.dataset.scope, state.ratingPeriod);
      return;
    }
    if (action === 'rating-period') {
      await loadRating(state.ratingScope, t.dataset.period);
      return;
    }
    if (action === 'open-scores') {
      await openPanel('scores');
      return;
    }
    if (action === 'open-streak') {
      await openPanel('streak');
      return;
    }
    if (action === 'open-tariffs') {
      await openPanel('tariffs');
      return;
    }
    if (action === 'close-panel') {
      state.panel = null;
      render();
      return;
    }
    if (action === 'scores-prev') {
      await loadScoresPage(Math.max(1, (state.scores?.page || 1) - 1));
      return;
    }
    if (action === 'scores-next') {
      await loadScoresPage((state.scores?.page || 1) + 1);
      return;
    }
    if (action === 'tariff-soon' || action === 'buy-plan') {
      const planCode = t.dataset.plan === 'mentor' ? 'pro_3m' : (t.dataset.plan === 'focus' ? 'pro_12m' : 'pro_1m');
      state.loading = true;
      render();
      try {
        const order = await api.createCheckout(planCode);
        if (order.checkout_url) {
          toast(`Счёт на ${order.amount_byn} BYN создан! Переходим к оплате…`);
          if (window.Telegram?.WebApp?.openLink) {
            window.Telegram.WebApp.openLink(order.checkout_url);
          } else {
            window.open(order.checkout_url, '_blank');
          }
        }
      } catch (e) {
        toast(e.message || 'Ошибка создания счёта');
      } finally {
        state.loading = false;
        render();
      }
      return;
    }
    if (action === 'go-practice') setRoute('practice');
    if (action === 'go-family') setRoute('family');
    if (action === 'go-home') setRoute('home');
    if (action === 'go-profile') setRoute('profile');
    if (action === 'go-courses') setRoute('courses');
    if (action === 'courses-subject') {
      state.coursesSubjectId = Number(t.dataset.id);
      render();
      return;
    }
    if (action === 'courses-pick-grade') {
      const grade = Number(t.dataset.grade);
      const subjectId = Number(t.dataset.subject);
      if (!grade || !state.me?.registered) {
        toast('Сначала пройди регистрацию');
        return;
      }
      if (t.dataset.empty === '1') {
        toast('Для этого класса заданий пока мало — скоро добавим');
      }
      if (Number(state.me.grade) === grade && Number(state.me.subject) === subjectId) {
        toast(`Уже занимаешься в ${grade} классе`);
        setRoute('practice');
        return;
      }
      state.loading = true;
      render();
      try {
        const goal = goalForGradeSwitch(grade, state.me.goal);
        const data = await api.updateProfile({
          grade,
          goal,
          subject_id: subjectId || state.me.subject,
        });
        state.me = { ...state.me, ...data, registered: true };
        toast(`Класс: ${grade}. Можно решать.`);
        state.daily = null;
        setRoute('practice');
      } catch (err) {
        toast(err.message);
        state.loading = false;
        render();
      }
      return;
    }
    if (action === 'toggle-notifications') {
      const current = state.me?.notifications_enabled !== false;
      const nextVal = !current;
      if (state.me) state.me.notifications_enabled = nextVal;
      try {
        await api.updateProfile({ notifications_enabled: nextVal });
        toast(nextVal ? '🔔 Напоминания включены' : '🔕 Напоминания отключены');
      } catch (e) {
        toast(e.message || 'Не удалось обновить настройки');
      }
      render();
      return;
    }
    if (action === 'izlo-random') {
      const id = tgId();
      if (!id) return;
      state.loading = true;
      render();
      try {
        state.daily = await api.startIzlozhenie(id, { count: 3 });
        state.feedback = null;
        state.answerText = '';
        state.selected = new Set();
        state.panel = null;
        setRoute('practice');
      } catch (e) {
        toast(e.message);
      } finally {
        state.loading = false;
        render();
      }
    }
    if (action === 'izlo-catalog') {
      const id = tgId();
      if (!id) return;
      state.loading = true;
      state.panel = 'izlo-catalog';
      setRoute('practice');
      try {
        state.izloCatalog = await api.izlozheniya(id, state.izloQuery);
      } catch (e) {
        toast(e.message);
        state.panel = null;
      } finally {
        state.loading = false;
        render();
      }
    }
    if (action === 'izlo-search') {
      const id = tgId();
      const input = document.getElementById('izlo-search');
      state.izloQuery = input?.value?.trim() || '';
      if (!id) return;
      state.loading = true;
      render();
      try {
        state.izloCatalog = await api.izlozheniya(id, state.izloQuery);
      } catch (e) {
        toast(e.message);
      } finally {
        state.loading = false;
        render();
      }
    }
    if (action === 'izlo-pick') {
      const id = tgId();
      const taskId = Number(t.dataset.taskId);
      if (!id || !taskId) return;
      state.loading = true;
      render();
      try {
        state.daily = await api.startIzlozhenie(id, { task_id: taskId });
        state.feedback = null;
        state.answerText = '';
        state.selected = new Set();
        state.panel = null;
        setRoute('practice');
      } catch (e) {
        toast(e.message);
      } finally {
        state.loading = false;
        render();
      }
    }
    if (action === 'izlo-back') {
      state.panel = null;
      render();
    }
    if (action === 'reg-set-role') {
      state.reg.role = t.dataset.role || null;
      render();
      return;
    }
    if (action === 'family-share-code') {
      const code = t.dataset.code || '';
      const text = `Привет! Привяжи меня в боте «Твой Репетитор» по коду: ${code}\nПерейди в бота: https://t.me/tutor_by_bot`;
      if (navigator.clipboard) {
        navigator.clipboard.writeText(text);
        toast('Приглашение скопировано в буфер!');
      } else {
        toast(`Ваш код для родителя: ${code}`);
      }
      return;
    }
    if (action === 'reg-grade') {
      state.reg.grade = Number(t.dataset.grade);
      const allowed = goalsForGrade(state.reg.allGoals || state.reg.goals || [], state.reg.grade);
      state.reg.goals = allowed;
      if (!allowed.find((g) => g.id === state.reg.goal)) {
        state.reg.goal = allowed[0]?.id || 'improve';
      }
      render();
      return;
    }
    if (action === 'reg-goal') {
      state.reg.goal = t.dataset.goal;
      render();
      return;
    }
    if (action === 'reg-subject') {
      state.reg.subject_id = Number(t.dataset.id);
      render();
      return;
    }
    if (action === 'pick-city') {
      state.reg.city_id = Number(t.dataset.id);
      state.reg.city_name = t.dataset.name || '';
      state.reg.cityQuery = state.reg.city_name;
      state.reg.cityResults = [];
      state.reg.school_id = null;
      state.reg.school_name = '';
      state.reg.schoolQuery = '';
      state.reg.schoolResults = [];
      render();
      searchSchools();
      return;
    }
    if (action === 'pick-school') {
      state.reg.school_id = Number(t.dataset.id);
      state.reg.school_name = t.dataset.name || '';
      state.reg.schoolQuery = state.reg.school_name;
      state.reg.schoolResults = [];
      render();
      return;
    }
    if (action === 'clear-city') {
      state.reg.city_id = null;
      state.reg.city_name = '';
      state.reg.cityQuery = '';
      state.reg.cityResults = [];
      state.reg.school_id = null;
      state.reg.school_name = '';
      state.reg.schoolQuery = '';
      state.reg.schoolResults = [];
      render();
      return;
    }
    if (action === 'clear-school') {
      state.reg.school_id = null;
      state.reg.school_name = '';
      state.reg.schoolQuery = '';
      state.reg.schoolResults = [];
      render();
      return;
    }
    if (action === 'reg-submit') {
      syncRegInputsFromDom();
      if (!state.reg.display_name) {
        toast('Укажи имя');
        return;
      }
      if (state.reg.role !== 'parent') {
        if (!state.reg.subject_id) {
          toast('Выбери предмет');
          return;
        }
        if (!state.reg.city_id) {
          toast('Выбери город из списка');
          return;
        }
        if (!state.reg.school_id) {
          toast('Выбери школу из списка');
          return;
        }
      }
      state.reg.saving = true;
      state.reg.error = '';
      render();
      try {
        const payload = payloadFromForm(state.reg);
        const data =
          state.me?.registered && state.route === 'profile'
            ? await api.updateProfile(payload)
            : await api.register(payload);
        state.me = { ...state.me, ...data, registered: true };
        toast(state.route === 'profile' ? 'Профиль сохранён' : 'Готово!');
        state.route = 'home';
        document.querySelectorAll('.tab').forEach((btn) => {
          btn.classList.toggle('active', btn.dataset.route === 'home');
        });
        await loadForRoute();
      } catch (err) {
        state.reg.error = err.message;
        toast(err.message);
      } finally {
        state.reg.saving = false;
        render();
      }
      return;
    }
    if (action === 'submit') await submitAnswer();
    if (action === 'explain') await explain();
    if (action === 'open-tariffs') {
      setRoute('tariffs');
      return;
    }
    if (action === 'next' || action === 'reload-daily') {
      state.feedback = null;
      await loadForRoute();
    }
    if (action === 'family-new-code') {
      const id = tgId();
      if (!id) return;
      try {
        const data = await api.familyInvite(id);
        toast(data.message || 'Новый код');
        await loadFamily();
      } catch (err) {
        toast(err.message);
      }
      return;
    }
    if (action === 'family-retry') {
      await loadFamily();
      return;
    }
    if (action === 'family-link') {
      const code = (state.familyCode || document.getElementById('family-code')?.value || '').trim();
      if (!code) {
        toast('Введи код');
        return;
      }
      try {
        const data = await api.familyLink(code);
        toast(data.message || 'Готово');
        state.familyCode = '';
        await loadFamily();
      } catch (err) {
        toast(err.message);
      }
      return;
    }
    if (action === 'pick-child') {
      state.reportChildId = Number(t.dataset.id);
      render();
      return;
    }
    if (action === 'report-period') {
      state.reportPeriod = t.dataset.period;
      render();
      return;
    }
    if (action === 'start-exam') {
      state.route = 'exam';
      await startExamSimulator();
      return;
    }
    if (action === 'exam-jump') {
      const idx = Number(t.dataset.index);
      saveCurrentExamAnswer();
      state.exam.currentIndex = idx;
      render();
      return;
    }
    if (action === 'exam-select-single') {
      const key = t.dataset.key;
      const currentTask = state.exam.tasks[state.exam.currentIndex];
      if (currentTask) {
        state.exam.answers[currentTask.session_task_id] = key;
        render();
      }
      return;
    }
    if (action === 'exam-toggle-multi') {
      const key = t.dataset.key;
      const currentTask = state.exam.tasks[state.exam.currentIndex];
      if (currentTask) {
        const stId = currentTask.session_task_id;
        const current = state.exam.answers[stId] ? state.exam.answers[stId].split(',') : [];
        const set = new Set(current);
        if (set.has(key)) set.delete(key);
        else set.add(key);
        state.exam.answers[stId] = Array.from(set).sort().join(',');
        render();
      }
      return;
    }
    if (action === 'exam-save-short') {
      saveCurrentExamAnswer();
      toast('Ответ сохранён');
      render();
      return;
    }
    if (action === 'exam-prev') {
      saveCurrentExamAnswer();
      state.exam.currentIndex = Math.max(0, state.exam.currentIndex - 1);
      render();
      return;
    }
    if (action === 'exam-next') {
      saveCurrentExamAnswer();
      state.exam.currentIndex = Math.min(state.exam.tasks.length - 1, state.exam.currentIndex + 1);
      render();
      return;
    }
    if (action === 'exam-submit-confirm') {
      saveCurrentExamAnswer();
      if (confirm('Сдать бланк ответов и завершить экзамен?')) {
        await submitExamSimulator();
      }
      return;
    }
    if (action === 'exam-exit') {
      if (state.examTimer) clearInterval(state.examTimer);
      state.exam = null;
      setRoute('home');
      return;
    }
    if (action === 'family-report') {
      if (!state.reportChildId) {
        toast('Выбери ребёнка');
        return;
      }
      const payload = {
        student_id: state.reportChildId,
        period: state.reportPeriod,
      };
      if (state.reportPeriod === 'custom') {
        payload.date_from = state.reportFrom || document.getElementById('report-from')?.value;
        payload.date_to = state.reportTo || document.getElementById('report-to')?.value;
        if (!payload.date_from || !payload.date_to) {
          toast('Укажи обе даты');
          return;
        }
      }
      try {
        const data = await api.familyReport(payload);
        toast(data.message || 'Отчёт в боте');
      } catch (err) {
        toast(err.message);
      }
    }
  });
}

async function main() {
  bootTelegram();
  const theme = initTheme();
  startAtmosphere(theme);
  bindUi();
  await loadMe();
  await loadForRoute();
}

main();
