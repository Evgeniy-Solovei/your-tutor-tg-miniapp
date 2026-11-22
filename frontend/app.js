import { api } from './api.js?v=20261122-v13-landing';
import { startAtmosphere } from './atmosphere.js';
import {
  emptyRegForm,
  goalsForGrade,
  loadRegMeta,
  payloadFromForm,
  renderRegForm,
} from './registration.js';
import {
  bootTelegram,
  getDevTgId,
  getInitData,
  getUnsafeUser,
  isWebChannel,
  setDevTgId,
} from './telegram.js';
import { THEMES, getTheme, initTheme, toggleTheme } from './theme.js';
import { LEGAL_DOCS, REQUISITES } from './legal.js';
import { renderLandingPresentation } from './landing.js';

const initialRoute = (() => {
  try {
    const params = new URLSearchParams(window.location.search);
    const q = params.get('route');
    if (q && ['home', 'courses', 'practice', 'stats', 'rating', 'profile', 'tariffs', 'contacts'].includes(q)) {
      return q;
    }
    const hash = window.location.hash.replace('#', '').trim();
    if (hash && ['home', 'courses', 'practice', 'stats', 'rating', 'profile', 'tariffs', 'contacts'].includes(hash)) {
      return hash;
    }
  } catch (_) {}
  return 'home';
})();

const state = {
  route: initialRoute,
  me: null,
  daily: null,
  stats: null,
  rating: null,
  ratingScope: 'grade',
  panel: null, // scores | streak | tariffs
  scores: null,
  scoresPage: 1,
  streak: null,
  tariffs: null,
  checkoutPlan: null,
  checkoutOrder: null,
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
  authTab: 'login',
  authError: '',
  tgLinkCode: '',
  tgLinkDeeplink: '',
  devUsers: null,
  izloCatalog: null,
  izloQuery: '',
  catalog: null,
  coursesSubjectId: null,
  inCoursesCatalog: false,
  selectedGradeCurriculum: null,
  gradeTab: 'school',
  selectedExamYear: null,
  showRuleModal: false,
  exam: null,
  examTimer: null,
  /** Пошаговый маршрут по теме: учебник → доп. тренажёр → ИИ */
  practiceFlow: null,
  /** Развёрнутые темы в программе класса */
  expandedTopicIds: new Set(),
};

let citySearchTimer = null;
let schoolSearchTimer = null;

function formatDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.slice(0, 10).split('-');
  return `${d}.${m}.${y}`;
}

function shuffleArray(arr) {
  if (!Array.isArray(arr) || arr.length <= 1) return arr;
  const copy = [...arr];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
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

function escAttr(s) {
  return esc(s).replaceAll("'", '&#39;');
}

/**
 * @param {1|2|3} activeStep — текущий шаг (0 = обзор)
 * @param {{ hasExtra?: boolean }} opts
 */
function isProUser() {
  return Boolean(state.me?.is_pro || state.stats?.is_pro);
}

/** 1–4 класс: основной контент — доп. карточки с картинками, не текстовый Task-дамп. */
function isPictureGrade(grade = null) {
  const g = Number(grade ?? state.me?.grade ?? state.selectedGradeCurriculum?.grade ?? 0);
  return g >= 1 && g <= 4;
}

/** Темы программы в порядке секций (для практики «тема за темой»). */
function curriculumTopicsInOrder(cur = state.selectedGradeCurriculum) {
  const list = [];
  for (const sec of cur?.sections || []) {
    for (const top of sec.topics || []) list.push(top);
  }
  return list;
}

/** Следующая тема с доп. карточками после currentTopicId (null = первая). */
function nextPictureTopic(currentTopicId = null) {
  const topics = curriculumTopicsInOrder().filter((t) => (t.extra_task_count || 0) > 0);
  if (!topics.length) return null;
  if (!currentTopicId) return topics[0];
  const idx = topics.findIndex((t) => Number(t.id) === Number(currentTopicId));
  if (idx < 0) return topics[0];
  return topics[idx + 1] || null;
}

async function startPictureTopicPractice(topicId, topicName = '') {
  state.extraTasksReturnRoute = 'courses';
  state.practiceFlow = {
    step: 2,
    topicId: Number(topicId),
    topicName: topicName || '',
    extraCount: 0,
  };
  setRoute('extra-tasks');
  await openExtraTopic(Number(topicId));
}

async function ensureCurriculumForPractice() {
  const myGrade = Number(state.me?.grade) || 1;
  if (
    state.selectedGradeCurriculum &&
    Number(state.selectedGradeCurriculum.grade) === myGrade
  ) {
    return state.selectedGradeCurriculum;
  }
  const id = tgId();
  if (!id) return null;
  state.selectedGradeCurriculum = await api.getGradeCurriculum(myGrade, id);
  return state.selectedGradeCurriculum;
}

function renderLearningPath(activeStep, opts = {}) {
  const hasExtra = opts.hasExtra !== false;
  const pro = isProUser();
  const clickable = opts.clickable !== false;
  const steps = [
    {
      n: 1,
      icon: '📖',
      title: 'Учебник',
      sub: 'задания из книги',
      action: 'go-my-curriculum',
    },
    {
      n: 2,
      icon: '🧩',
      title: 'Доп. задания',
      sub: hasExtra ? 'закрепление темы' : 'нет по теме',
      action: hasExtra ? 'go-extra-tasks' : '',
    },
    {
      n: 3,
      icon: '🤖',
      title: 'Разбор с ИИ',
      sub: pro ? 'активировано' : 'по подписке',
      proActive: pro,
      action: pro ? 'ai-hint-pro' : 'open-tariffs',
    },
  ];
  return `
    <div class="learning-path" role="list" aria-label="Как учиться по теме">
      ${steps
        .map((s) => {
          const done = activeStep > s.n;
          const active = activeStep === s.n;
          const muted = s.n === 2 && !hasExtra;
          const proCls = s.proActive ? ' pro-on' : '';
          const canClick = clickable && s.action && !muted;
          const tag = canClick ? 'button' : 'div';
          const attrs = canClick
            ? `type="button" data-action="${escAttr(s.action)}" class="learning-step learning-step-btn${active ? ' active' : ''}${done ? ' done' : ''}${proCls}"`
            : `class="learning-step${active ? ' active' : ''}${done ? ' done' : ''}${muted ? ' muted' : ''}${proCls}" role="listitem"`;
          return `
        <${tag} ${attrs}>
          <div class="learning-step-num">${done ? '✓' : s.n}</div>
          <div class="learning-step-icon">${s.icon}</div>
          <div class="learning-step-title">${esc(s.title)}</div>
          <div class="learning-step-sub">${esc(s.sub)}</div>
        </${tag}>`;
        })
        .join('')}
    </div>`;
}

const SECTION_META = {
  home: { title: 'Главная панель', icon: '🏠', sub: 'Обзор обучения и цели на сегодня' },
  courses: { title: 'Программа обучения', icon: '📚', sub: 'Школьный курс 1–11 классов' },
  'extra-tasks': { title: 'Карточки заданий', icon: '🎨', sub: 'Интерактивные иллюстрированные задания' },
  practice: { title: 'Тренажёр заданий', icon: '⚡', sub: 'Практика с мгновенной проверкой' },
  stats: { title: 'Моя статистика', icon: '📊', sub: 'Прогресс, точность и баллы' },
  rating: { title: 'Зал славы', icon: '🏆', sub: 'Рейтинг учеников Беларуси' },
  profile: { title: 'Личный кабинет', icon: '👨‍👩‍👧', sub: 'Профиль ученика и семья' },
  family: { title: 'Кабинет семьи', icon: '👨‍👩‍👧', sub: 'Родительский контроль и отчёты' },
  tariffs: { title: 'Тарифы и подписка', icon: '💎', sub: 'Безлимитная практика и разборы' },
  contacts: { title: 'Информация и оферта', icon: '📋', sub: 'Реквизиты и правовые документы' },
  exam: { title: 'Симулятор ЦТ / ЦЭ', icon: '⏱', sub: 'Бланк ответов по шкале РИКЗ' },
};

function updateTopbarBadges() {
  const streakValEl = document.getElementById('topbar-streak-val');
  if (streakValEl) {
    const s = state.stats?.streak_days ?? state.me?.streak_days ?? 0;
    streakValEl.textContent = s;
  }
  const xpValEl = document.getElementById('topbar-xp-val');
  if (xpValEl) {
    const xp = state.stats?.total_score ?? state.me?.total_score ?? 0;
    xpValEl.textContent = xp;
  }
  const accValEl = document.getElementById('topbar-acc-val');
  if (accValEl) {
    const acc = state.stats?.accuracy_pct ?? state.me?.accuracy_pct;
    accValEl.textContent = acc != null ? `${acc}%` : '—';
  }

  // Section header on desktop
  const isExamVariants =
    (state.route === 'courses' && state.gradeTab === 'exam') ||
    state.route === 'exam';
  const meta = isExamVariants
    ? { title: 'Варианты ЦТ / ЦЭ', icon: '🎟', sub: 'Официальные экзаменационные варианты РИКЗ' }
    : (SECTION_META[state.route] || SECTION_META.home);

  const iconEl = document.getElementById('topbar-section-icon');
  const titleEl = document.getElementById('topbar-section-title');
  const subEl = document.getElementById('topbar-section-sub');
  if (iconEl) iconEl.textContent = meta.icon;
  if (titleEl) titleEl.textContent = meta.title;
  if (subEl) subEl.textContent = meta.sub;
}

function syncTabbar() {
  const isExamVariants =
    (state.route === 'courses' && state.gradeTab === 'exam') ||
    state.route === 'exam';

  document.querySelectorAll('.sidebar-btn').forEach((btn) => {
    if (btn.dataset.action === 'open-exam-variants') {
      btn.classList.toggle('active', isExamVariants);
    } else if (btn.dataset.route === 'courses') {
      btn.classList.toggle('active', state.route === 'courses' && !isExamVariants);
    } else if (btn.dataset.route) {
      const active =
        btn.dataset.route === state.route ||
        ((state.route === 'profile' || state.route === 'family') &&
          (btn.dataset.route === 'profile' || btn.dataset.route === 'family'));
      btn.classList.toggle('active', Boolean(active));
    }
  });

  document.querySelectorAll('.tab').forEach((btn) => {
    const active =
      btn.dataset.route === state.route ||
      ((state.route === 'profile' || state.route === 'family') &&
        (btn.dataset.route === 'profile' || btn.dataset.route === 'family')) ||
      (state.route === 'extra-tasks' && btn.dataset.route === 'courses');
    btn.classList.toggle('active', Boolean(active));
    if (active) {
      try {
        btn.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      } catch (_) {}
    }
  });

  updateTopbarBadges();
}

let _routeLoadSeq = 0;

function setRoute(route, force = false) {
  if (!state.me) return;
  if (!force && state.route === route && !state.panel) return;
  state.route = route;
  state.panel = null;
  if (route !== 'extra-tasks') {
    state.activeExtraTopic = null;
  }
  if (route === 'courses') {
    state.inCoursesCatalog = false;
  }
  syncTabbar();
  render();
  loadForRoute();
  try {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (_) {}
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
    } else if (panel === 'accuracy') {
      try {
        const [st, d] = await Promise.all([api.stats(id), api.dashboard(id)]);
        state.stats = st;
        state.dashboard = d;
      } catch (_) {}
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

async function turboBootstrap() {
  const token = localStorage.getItem('tutor_web_token');
  const initData = getInitData();
  const devId = getDevTgId() || getUnsafeUser()?.id;

  if (!token && !initData && !devId) {
    state.loading = false;
    state.me = null;
    render();
    return;
  }

  try {
    const boot = await api.bootstrap();
    if (boot) {
      if (boot.me) {
        state.me = boot.me;
        if (state.me.registered === false) {
          const suggested = state.me.telegram?.display_name || '';
          state.reg = emptyRegForm({ display_name: suggested });
          ensureRegForm().catch(() => {});
        }
      }
      if (boot.stats) state.stats = boot.stats;
      if (boot.dashboard) state.dashboard = boot.dashboard;
      if (boot.daily) {
        state.daily = boot.daily;
        if (state.daily?.current_task?.options) {
          state.daily.current_task.options = shuffleArray(state.daily.current_task.options);
        }
      }
      try {
        localStorage.setItem(
          'tutor_bootstrap_cache',
          JSON.stringify({
            me: boot.me,
            stats: boot.stats,
            dashboard: boot.dashboard,
            daily: boot.daily,
            ts: Date.now(),
          })
        );
      } catch (_) {}
    }
  } catch (err) {
    console.warn('Bootstrap API fallback:', err);
    if (err?.status === 401 || err?.status === 403) {
      localStorage.removeItem('tutor_web_token');
      state.me = null;
    } else if (!state.me) {
      await loadMe();
      await loadForRoute();
    }
  }

  if (state.route && state.route !== 'home') {
    await loadForRoute();
  }

  render();
}


async function loadMe() {
  const token = localStorage.getItem('tutor_web_token');
  const initData = getInitData();
  const devId = getDevTgId() || getUnsafeUser()?.id;

  if (!token && !initData && !devId) {
    state.loading = false;
    state.me = null;
    render();
    return;
  }

  if (!state.me) {
    state.loading = true;
    state.error = '';
    render();
  }
  try {
    state.me = await api.me();
    if (state.me && state.me.registered === false) {
      const suggested = state.me.telegram?.display_name || '';
      state.reg = emptyRegForm({ display_name: suggested });
      await ensureRegForm();
    } else if (state.me?.grade) {
      // Прогрев программы класса в фоне — клик «Учёба» не ждёт 10+ с
      const g = Number(state.me.grade);
      const id = tgId();
      if (g && !state.selectedGradeCurriculum) {
        api.getGradeCurriculum(g, id)
          .then((cur) => {
            if (cur && !state.selectedGradeCurriculum) {
              state.selectedGradeCurriculum = cur;
            }
          })
          .catch(() => {});
      }
    }
  } catch (e) {
    if (e?.status === 401 || e?.status === 403) {
      localStorage.removeItem('tutor_web_token');
      state.me = null;
    } else {
      state.error = e.message || 'Не удалось авторизоваться';
    }
  } finally {
    state.loading = false;
    render();
  }
}

async function loadFamily() {
  if (!state.family) {
    state.loading = true;
    render();
  }
  state.familyError = '';
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
  const currentSeq = ++_routeLoadSeq;
  if (state.route === 'tariffs') {
    if (!state.tariffs) {
      try {
        state.tariffs = await api.tariffs();
      } catch (_) {}
    }
    return;
  }

  if (state.route === 'courses') {
    const id = tgId();
    const myGrade = Number(state.me?.grade) || 11;
    if (!state.inCoursesCatalog) {
      if (!state.selectedGradeCurriculum || state.selectedGradeCurriculum.grade !== myGrade) {
        state.loading = true;
        render();
        try {
          const cur = await api.getGradeCurriculum(myGrade, id);
          if (currentSeq === _routeLoadSeq) {
            state.selectedGradeCurriculum = cur;
          }
        } catch (e) {
          toast(e.message || 'Не удалось загрузить программу твоего класса');
        } finally {
          if (currentSeq === _routeLoadSeq) {
            state.loading = false;
            render();
          }
        }
      }
    }
    await loadCatalog();
    return;
  }

  if (state.route === 'extra-tasks') {
    if (state.activeExtraTopic) return;
    const id = tgId();
    const grade = state.extraTasksGrade || Number(state.me?.grade) || 1;
    if (!state.extraTasksSummary || state.extraTasksSummary.grade !== grade) {
      state.loading = true;
      render();
    }
    try {
      const summary = await api.getExtraTasksSummary(grade, id);
      if (currentSeq === _routeLoadSeq) {
        state.extraTasksSummary = summary;
      }
    } catch (e) {
      toast(e.message || 'Ошибка загрузки заданий');
    } finally {
      if (currentSeq === _routeLoadSeq) {
        state.loading = false;
        render();
      }
    }
    return;
  }

  const id = tgId();
  if (!id || !state.me) return;

  if (state.route === 'family' || state.route === 'profile') {
    if (!state.reg) {
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
    }
    await Promise.allSettled([ensureRegForm(), loadFamily()]);
    if (currentSeq === _routeLoadSeq) render();
    return;
  }

  if (!state.me.registered) return;

  try {
    if (state.route === 'home') {
      const [statsRes, dashRes, dailyRes] = await Promise.allSettled([
        api.stats(id),
        api.dashboard(id),
        api.daily(id),
      ]);
      if (currentSeq !== _routeLoadSeq) return;
      if (statsRes.status === 'fulfilled') state.stats = statsRes.value;
      if (dashRes.status === 'fulfilled') state.dashboard = dashRes.value;
      if (dailyRes.status === 'fulfilled') {
        state.daily = dailyRes.value;
        if (state.daily?.current_task?.options) {
          state.daily.current_task.options = shuffleArray(state.daily.current_task.options);
        }
        state.selected = new Set();
        state.answerText = '';
        state.feedback = null;
      }
    } else if (state.route === 'stats') {
      const [statsRes, dashRes] = await Promise.allSettled([
        api.stats(id),
        api.dashboard(id),
      ]);
      if (currentSeq !== _routeLoadSeq) return;
      if (statsRes.status === 'fulfilled') state.stats = statsRes.value;
      if (dashRes.status === 'fulfilled') state.dashboard = dashRes.value;
    } else if (state.route === 'practice') {
      const dailyData = await api.daily(id);
      if (currentSeq !== _routeLoadSeq) return;
      state.daily = dailyData;
      if (state.daily?.current_task?.options) {
        state.daily.current_task.options = shuffleArray(state.daily.current_task.options);
      }
      state.selected = new Set();
      state.answerText = '';
      state.feedback = null;
    }
    if (state.route === 'rating') {
      await loadRating(state.ratingScope);
      return;
    }
  } catch (e) {
    if (currentSeq === _routeLoadSeq) state.error = e.message;
  }
  if (currentSeq === _routeLoadSeq) render();
}

async function loadCatalog() {
  if (!state.catalog) {
    state.loading = true;
    render();
  }
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
    if (state.loading) {
      state.loading = false;
      render();
    }
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

async function loadRating(scope, period, grade) {
  if (scope) state.ratingScope = scope;
  if (period) state.ratingPeriod = period;
  if (grade !== undefined) state.ratingGrade = grade ? Number(grade) : null;
  const s = state.ratingScope || 'grade';
  const p = state.ratingPeriod || 'week';
  const myGrade = state.me?.grade ? Number(state.me.grade) : null;
  const g = state.ratingScope === 'grade' ? (state.ratingGrade || myGrade) : null;
  state.rating = await api.leaderboard(s, {
    period: p,
    grade: g,
    city_id: state.me?.city || state.me?.filters?.city_id,
    school_id: state.me?.school || state.me?.filters?.school_id,
  });
  render();
}

function tariffShortLabel() {
  const id = state.tariffs?.current_plan_id;
  if (state.me?.is_pro || state.stats?.is_pro || id === 'pro_active') return 'Pro';
  return 'Базовый';
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

function renderAccuracyPanel() {
  const dash = state.dashboard;
  const weak = state.stats?.weak_topics || [];
  const total = dash?.total_attempts ?? 0;
  const correct = dash?.correct_attempts ?? 0;
  const wrong = Math.max(0, total - correct);
  const accuracy = dash?.accuracy_percent ?? 0;

  let accColor = '#10b981';
  let accGrade = 'Отличная точность! Так держать 👍';
  if (total === 0) {
    accGrade = 'Пока нет решенных заданий';
  } else if (accuracy < 50) {
    accColor = '#ef4444';
    accGrade = 'Много ошибок — нужно повторить правила';
  } else if (accuracy < 80) {
    accColor = '#f59e0b';
    accGrade = 'Хороший результат, но есть куда расти';
  }

  return `
    <section class="card">
      <div class="panel-head">
        <button type="button" class="linkish" data-action="close-panel">← Назад</button>
        <h2>🎯 Точность ответов</h2>
      </div>

      <div style="text-align:center; padding:18px 0 14px">
        <div style="font-size:3.2rem; font-weight:800; color:${accColor}; line-height:1; letter-spacing:-1px">
          ${accuracy}%
        </div>
        <p class="muted" style="margin-top:8px; font-weight:600; font-size:0.95rem">${accGrade}</p>
      </div>

      <div class="stats-row" style="margin:12px 0 16px">
        <div class="stat">
          <strong style="color:#10b981">${correct}</strong>
          <span>верно</span>
        </div>
        <div class="stat">
          <strong style="color:#ef4444">${wrong}</strong>
          <span>ошибок</span>
        </div>
        <div class="stat">
          <strong>${total}</strong>
          <span>всего задач</span>
        </div>
      </div>

      <div style="margin-bottom:18px">
        <div class="progress" style="height:10px; border-radius:5px; background:rgba(239, 68, 68, 0.25); overflow:hidden">
          <i style="width:${accuracy}%; background:linear-gradient(90deg, #10b981, #059669); border-radius:5px"></i>
        </div>
      </div>

      <h3 style="font-size:1.05rem; margin-bottom:10px">⚠️ Темы с наибольшим числом ошибок:</h3>
      ${weak.length ? `
        <div style="display:flex; flex-direction:column; gap:8px">
          ${weak.map((t) => `
            <div style="display:flex; align-items:center; justify-content:space-between; background:var(--bg-secondary); padding:10px 12px; border-radius:12px; border:1px solid var(--card-border)">
              <div style="flex:1; padding-right:10px">
                <div style="font-size:0.88rem; font-weight:600; line-height:1.3">${esc(t.topic_name)}</div>
                <div style="font-size:0.75rem; color:var(--muted); margin-top:3px">
                  Ошибок: <strong style="color:#ef4444">${t.wrong_count}</strong> · Точность ${Math.round((t.mastery_score || 0) * 100)}%
                </div>
              </div>
              <button type="button" class="btn secondary small" data-action="start-topic-practice" data-topic="${t.topic_id}" style="flex-shrink:0">
                ⚡ Отработать
              </button>
            </div>
          `).join('')}
        </div>
      ` : `
        <div class="empty" style="padding:16px 10px; border-radius:10px">
          <p class="muted">${total === 0 ? 'Реши несколько заданий, чтобы увидеть аналитику ошибок.' : 'Ошибок нет или их очень мало! Отличная работа 👏'}</p>
        </div>
      `}

      <button type="button" class="btn block primary" data-action="go-practice" style="margin-top:16px">
        ⚡ Перейти к тренировке
      </button>
    </section>
  `;
}

function renderTariffsPanel() {
  const pack = state.tariffs;
  if (!pack) return `<section class="card empty">Загружаем тарифы…</section>`;
  const isUserPro = state.me?.is_pro || state.stats?.is_pro || pack.current_plan_id === 'pro_active';
  return `
    <section class="card">
      <div class="panel-head">
        <button type="button" class="linkish" data-action="close-panel">← Назад</button>
        <h2>Тарифы и Подписка</h2>
      </div>
      <p class="muted">Официальная безналичная онлайн-оплата банковскими картами (МИР, Visa, Mastercard) и СБП через платёжный сервис ЮKassa.</p>
      ${isUserPro ? '<div style="margin: 12px 0; padding: 12px; background: rgba(16,185,129,0.15); border: 1px solid #10b981; border-radius: 14px;"><strong>✨ У вас активна Pro-подписка!</strong> Все задания и умные ИИ-разборы открыты.</div>' : ''}
      ${(pack.plans || [])
        .map(
          (p) => {
            const isFree = p.id === 'free';
            const isCurrent = isFree ? !isUserPro : isUserPro;
            const priceDisplay = p.price_rub_label || p.price_label;
            return `
        <article class="plan${isCurrent ? ' current' : ''}" style="margin-top:14px; border: 1px solid var(--card-border); border-radius: 16px; padding: 16px; background: var(--card);">
          <div class="plan-top" style="display:flex; justify-content:space-between; align-items:center;">
            <h3 style="margin:0; font-size:1.1rem">${esc(p.name)}</h3>
            <strong style="font-size:1.15rem; color:var(--accent)">${esc(priceDisplay)}</strong>
          </div>
          <p class="muted" style="margin:6px 0 12px; font-size:0.9rem">${esc(p.tagline)}</p>
          <ul class="plan-features" style="list-style:none; padding:0; margin:0 0 14px">
            ${(p.features || []).map((f) => `<li style="padding:3px 0; font-size:0.88rem">✓ ${esc(f)}</li>`).join('')}
            ${(p.not_included || []).map((f) => `<li class="no" style="padding:3px 0; font-size:0.88rem; opacity:0.5">✗ ${esc(f)}</li>`).join('')}
          </ul>
          ${isFree 
            ? (isUserPro ? '' : '<p class="ok" style="font-weight:600; color:var(--muted)">Ваш текущий тариф</p>')
            : (isUserPro 
                ? '<p class="ok" style="font-weight:600; color:#10b981">✓ Подписка активна</p>' 
                : `<button type="button" class="btn block primary" data-action="open-checkout" data-plan="${esc(p.id)}" data-price="${esc(priceDisplay)}" data-name="${esc(p.name)}">💳 Оформить заказ · ${esc(priceDisplay)}</button>`
              )
          }
        </article>`;
          }
        )
        .join('')}
    </section>
  `;
}

function renderTariffsPage() {
  const isUserPro = state.me?.is_pro || state.stats?.is_pro;
  return `
    <div class="tariffs-page">
      <div class="tariffs-hero">
        <h1>Тарифные планы и подписка</h1>
        <p>Интерактивная образовательная платформа «Твой Репетитор» для подготовки к ЦТ / ЦЭ и школьной программе (1–11 классы). Официальная и безопасная оплата онлайн.</p>
      </div>

      ${isUserPro ? `
        <div style="margin: 0 0 24px; padding: 16px 20px; background: rgba(16,185,129,0.15); border: 1px solid #10b981; border-radius: 16px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;">
          <div>
            <strong style="color: #10b981; font-size: 1.05rem;">✨ У вас активна Pro-подписка!</strong>
            <p style="margin: 4px 0 0; font-size: 0.9rem; color: var(--ink);">Все задания, тесты ЦТ/ЦЭ и умные разборы ИИ-репетитора доступны без ограничений.</p>
          </div>
          <span class="pay-badge badge-ssl" style="font-size: 0.85rem; padding: 6px 14px;">Безлимитный доступ</span>
        </div>
      ` : ''}

      <div class="tariffs-grid">
        <!-- Тариф Базовый -->
        <article class="tariff-card">
          <div class="tariff-head">
            <h3>Базовый</h3>
            <p class="tariff-tagline">Попробовать формат и ежедневные задания</p>
          </div>
          <div class="tariff-pricing">
            <div class="tariff-price-main">0 ₽</div>
            <div class="tariff-price-sub">Бесплатный ознакомительный доступ</div>
          </div>
          <ul class="tariff-features">
            <li><span class="check-icon">✓</span> До 15 заданий в день</li>
            <li><span class="check-icon">✓</span> Каталог школьной программы (1–11 класс)</li>
            <li><span class="check-icon">✓</span> Таблица рейтинга и серия дней</li>
            <li class="not-inc"><span class="check-icon">✕</span> Безлимитная практика по темам</li>
            <li class="not-inc"><span class="check-icon">✕</span> Умные ИИ-разборы ошибок</li>
            <li class="not-inc"><span class="check-icon">✕</span> Полные симуляции ЦТ/ЦЭ</li>
          </ul>
          <div class="tariff-action">
            <button type="button" class="btn block secondary" disabled style="opacity: 0.7;">
              ${isUserPro ? 'Базовый уровень' : '✓ Ваш текущий тариф'}
            </button>
          </div>
        </article>

        <!-- Тариф Стандарт на 1 месяц -->
        <article class="tariff-card">
          <div class="tariff-head">
            <h3>Стандарт</h3>
            <p class="tariff-tagline">1 месяц полной безлимитной практики</p>
          </div>
          <div class="tariff-pricing">
            <div class="tariff-price-main">590 ₽</div>
            <div class="tariff-price-sub">на 30 дней (~19.90 BYN)</div>
          </div>
          <ul class="tariff-features">
            <li><span class="check-icon">✓</span> <strong>Полный безлимит</strong> всех заданий</li>
            <li><span class="check-icon">✓</span> <strong>ИИ-репетитор:</strong> умный разбор ошибок</li>
            <li><span class="check-icon">✓</span> Все темы школьной программы 1–11 кл.</li>
            <li><span class="check-icon">✓</span> Тренировочные блоки ЦТ и ЦЭ</li>
            <li><span class="check-icon">✓</span> Приоритет в таблице рейтинга</li>
          </ul>
          <div class="tariff-action">
            <button type="button" class="btn block primary" data-action="open-checkout" data-plan="pro_1m" data-price="590 ₽" data-name="Тариф «Стандарт на 1 месяц»">
              Оформить подписку · 590 ₽
            </button>
          </div>
        </article>

        <!-- Тариф Четверть на 3 месяца (ХИТ) -->
        <article class="tariff-card featured">
          <div class="tariff-badge">Хит продаж</div>
          <div class="tariff-head">
            <h3>Четверть</h3>
            <p class="tariff-tagline">Оптимально для учебной четверти (экономия 16%)</p>
          </div>
          <div class="tariff-pricing">
            <div class="tariff-price-main">1 490 ₽</div>
            <div class="tariff-price-sub">на 90 дней (~49.90 BYN) · 496 ₽/мес</div>
          </div>
          <ul class="tariff-features">
            <li><span class="check-icon">✓</span> <strong>Всё из тарифа «Стандарт»</strong></li>
            <li><span class="check-icon">✓</span> <strong>3 месяца</strong> безлимитной подготовки</li>
            <li><span class="check-icon">✓</span> Подготовка к четвертным контрольным</li>
            <li><span class="check-icon">✓</span> Персональный трек устранения пробелов</li>
            <li><span class="check-icon">✓</span> Родительский отчёт успеваемости</li>
          </ul>
          <div class="tariff-action">
            <button type="button" class="btn block primary" data-action="open-checkout" data-plan="pro_3m" data-price="1 490 ₽" data-name="Тариф «Четверть на 3 месяца»">
              Оформить подписку · 1 490 ₽
            </button>
          </div>
        </article>

        <!-- Тариф Год на 12 месяцев (ВЫГОДНО) -->
        <article class="tariff-card">
          <div class="tariff-badge" style="background: #10b981; color: #fff;">Выгода 37%</div>
          <div class="tariff-head">
            <h3>Учебный год</h3>
            <p class="tariff-tagline">Комплексная подготовка на максимум баллов</p>
          </div>
          <div class="tariff-pricing">
            <div class="tariff-price-main">4 490 ₽</div>
            <div class="tariff-price-sub">на 365 дней (~149.90 BYN) · 374 ₽/мес</div>
          </div>
          <ul class="tariff-features">
            <li><span class="check-icon">✓</span> <strong>Полный доступ</strong> на 365 дней</li>
            <li><span class="check-icon">✓</span> Безлимит всех тренажёров и тестов</li>
            <li><span class="check-icon">✓</span> Полная подготовка к ЦТ и ЦЭ (части А и В)</li>
            <li><span class="check-icon">✓</span> Неограниченный персональный ИИ-репетитор</li>
            <li><span class="check-icon">✓</span> Все будущие обновления базы заданий</li>
          </ul>
          <div class="tariff-action">
            <button type="button" class="btn block primary" data-action="open-checkout" data-plan="pro_12m" data-price="4 490 ₽" data-name="Тариф «Учебный год на 12 месяцев»">
              Оформить подписку · 4 490 ₽
            </button>
          </div>
        </article>
      </div>

      <!-- Блок гарантий и безопасности ЮKassa -->
      <div class="tariffs-guarantees">
        <div class="guarantee-item">
          <span class="guarantee-icon">🔒</span>
          <div class="guarantee-text">
            <h4>Безопасная оплата</h4>
            <p>Платежи защищены по стандарту PCI DSS. Обработка через платёжный шлюз ЮKassa.</p>
          </div>
        </div>
        <div class="guarantee-item">
          <span class="guarantee-icon">⚡</span>
          <div class="guarantee-text">
            <h4>Мгновенный доступ</h4>
            <p>Подписка активируется автоматически сразу после успешного проведения платежа.</p>
          </div>
        </div>
        <div class="guarantee-item">
          <span class="guarantee-icon">📄</span>
          <div class="guarantee-text">
            <h4>Электронный чек</h4>
            <p>Официальный кассовый чек направляется на указанный e-mail в соответствии с 54-ФЗ.</p>
          </div>
        </div>
        <div class="guarantee-item">
          <span class="guarantee-icon">🔄</span>
          <div class="guarantee-text">
            <h4>Гарантия возврата</h4>
            <p>Возврат средств в течение 14 дней в соответствии с условиями Публичной оферты.</p>
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderContactsPage() {
  return `
    <div class="tariffs-page">
      <div class="tariffs-hero">
        <h1>Контакты и реквизиты</h1>
        <p>Служба заботы образовательной платформы «Твой Репетитор». Мы всегда на связи и готовы помочь по любым вопросам работы сервиса и оплаты.</p>
      </div>

      <div class="contacts-grid">
        <div class="card">
          <h2>Служба поддержки</h2>
          <div class="footer-info" style="font-size: 1rem; gap: 14px; margin-top: 16px;">
            <p><strong>Электронная почта:</strong><br/><a href="mailto:${REQUISITES.email}" style="font-size: 1.1rem;">${REQUISITES.email}</a></p>
            <p><strong>Контактный телефон:</strong><br/><a href="tel:${REQUISITES.phone.replace(/[^0-9+]/g, '')}" style="font-size: 1.1rem;">${REQUISITES.phone}</a></p>
            <p><strong>Telegram для связи:</strong><br/><a href="https://t.me/tutor_by_bot" target="_blank" style="font-size: 1.1rem;">${REQUISITES.supportBot}</a></p>
            <p><strong>График работы:</strong><br/>${REQUISITES.workingHours}</p>
          </div>
          
          <div style="margin-top: 24px; padding-top: 20px; border-top: 1px solid var(--card-border);">
            <h3 style="font-size: 1.05rem; margin: 0 0 10px;">Юридические документы</h3>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              <button type="button" class="linkish" style="text-align: left;" data-action="open-legal" data-legal="terms">📄 Публичный договор-оферта</button>
              <button type="button" class="linkish" style="text-align: left;" data-action="open-legal" data-legal="privacy">🔒 Политика обработки персональных данных</button>
              <button type="button" class="linkish" style="text-align: left;" data-action="open-legal" data-legal="refund">💳 Правила оплаты и возврата средств</button>
            </div>
          </div>
        </div>

        <div class="card">
          <h2>Реквизиты самозанятого</h2>
          <table class="req-table" style="margin-top: 14px;">
            <tbody>
              <tr><td>ФИО исполнителя</td><td><strong>${REQUISITES.seller}</strong></td></tr>
              <tr><td>Правовой статус</td><td>${REQUISITES.status}</td></tr>
              <tr><td>ИНН плательщика НПД</td><td><strong style="font-family: monospace; letter-spacing: 0.05em; font-size: 1.05rem;">${REQUISITES.inn}</strong></td></tr>
              <tr><td>Email для обращений</td><td><a href="mailto:${REQUISITES.email}">${REQUISITES.email}</a></td></tr>
              <tr><td>Telegram поддержка</td><td>${REQUISITES.supportBot}</td></tr>
              <tr><td>Официальный сайт</td><td>${REQUISITES.siteUrl}</td></tr>
              <tr><td>Наименование сервиса</td><td>${REQUISITES.serviceName}</td></tr>
            </tbody>
          </table>

          <div style="margin-top: 20px; padding: 14px; background: rgba(255,255,255,0.04); border-radius: 12px; font-size: 0.84rem; line-height: 1.45; color: var(--muted);">
            Приём онлайн-платежей на сайте осуществляется через сертифицированный платёжный сервис ЮKassa. Безопасность гарантирована сертификатом PCI DSS.
          </div>
        </div>
      </div>
    </div>
  `;
}

function openCheckoutModal(planId, priceLabel, planTitle) {
  state.checkoutPlan = {
    id: planId || 'pro_1m',
    price: priceLabel || '590 ₽',
    title: planTitle || 'Тариф «Стандарт на 1 месяц»',
  };
  state.checkoutOrder = null;
  renderCheckoutContent(1);
  const modal = document.getElementById('checkout-modal');
  if (modal) {
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
  }
}

function closeCheckoutModal() {
  const modal = document.getElementById('checkout-modal');
  if (modal) {
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
  }
}

function renderCheckoutContent(step = 1) {
  const container = document.getElementById('checkout-content');
  if (!container) return;
  const plan = state.checkoutPlan || { id: 'pro_1m', price: '590 ₽', title: 'Тариф «Стандарт на 1 месяц»' };
  const user = state.me;

  if (step === 1) {
    container.innerHTML = `
      <h2 style="font-family: var(--font-display); font-size: 1.35rem; margin: 0 0 4px; color: var(--ink);">Оформление заказа</h2>
      <p class="muted" style="font-size: 0.88rem; margin: 0;">Шаг 1 из 2: Данные покупателя</p>

      <div class="checkout-summary-box">
        <div>
          <div class="checkout-summary-name">${esc(plan.title)}</div>
          <div class="muted" style="font-size: 0.82rem; margin-top: 2px;">Полный доступ ко всем заданиям и ИИ-репетитору</div>
        </div>
        <div class="checkout-summary-price">${esc(plan.price)}</div>
      </div>

      <form id="checkout-order-form" class="checkout-form" onsubmit="event.preventDefault();">
        <div class="form-group">
          <label for="order-name">Имя и фамилия</label>
          <input type="text" id="order-name" class="form-input" placeholder="Например: Иван Иванов" value="${esc(user?.display_name || '')}" required />
        </div>

        <div class="form-group">
          <label for="order-email">Электронная почта (для чека и доступа)</label>
          <input type="email" id="order-email" class="form-input" placeholder="name@example.com" value="" required />
        </div>

        <div class="form-group">
          <label for="order-phone">Номер телефона</label>
          <input type="tel" id="order-phone" class="form-input" placeholder="+7 (999) 000-00-00" value="" required />
        </div>

        <div class="form-group">
          <label>Способ онлайн-оплаты</label>
          <div class="pay-methods-grid">
            <label class="pay-method-opt selected">
              <input type="radio" name="pay-method" value="card" checked />
              <span style="font-size: 1.3rem;">💳</span>
              <span>Карта РФ и мира</span>
            </label>
            <label class="pay-method-opt">
              <input type="radio" name="pay-method" value="sbp" />
              <span style="font-size: 1.3rem;">⚡</span>
              <span>СБП онлайн</span>
            </label>
            <label class="pay-method-opt">
              <input type="radio" name="pay-method" value="yoo" />
              <span style="font-size: 1.3rem;">🟣</span>
              <span>ЮMoney</span>
            </label>
          </div>
        </div>

        <label class="terms-checkbox-wrap">
          <input type="checkbox" id="order-terms-chk" checked required />
          <span>Нажимая кнопку, вы соглашаетесь с условиями <a data-action="open-legal" data-legal="terms">Публичной оферты</a> и даете согласие на обработку данных по <a data-action="open-legal" data-legal="privacy">Политике конфиденциальности</a>.</span>
        </label>

        <button type="button" class="btn block primary" id="btn-submit-order" style="padding: 14px; font-size: 1.05rem;" data-action="submit-checkout-step1">
          Перейти к оплате · ${esc(plan.price)}
        </button>

        <div class="pci-security-pill">
          <span>🔒</span> Оплата проходит непосредственно на сайте через защищенный шлюз ЮKassa (PCI DSS Level 1)
        </div>
      </form>
    `;
  } else if (step === 2) {
    const orderId = state.checkoutOrder?.id || `TR-${Math.floor(100000 + Math.random() * 900000)}`;
    state.checkoutOrder = { id: orderId };

    container.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
        <span style="color: #10b981; font-size: 1.2rem;">✓</span>
        <h2 style="font-family: var(--font-display); font-size: 1.35rem; margin: 0; color: var(--ink);">Заказ сформирован</h2>
      </div>
      <p class="muted" style="font-size: 0.88rem; margin: 0 0 14px;">Заказ № <strong>${esc(orderId)}</strong> на сумму <strong style="color:var(--accent)">${esc(plan.price)}</strong></p>

      <div class="in-site-payment-box">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
          <strong style="font-size: 0.95rem; color: var(--ink);">Оплата банковской картой онлайн</strong>
          <div class="footer-badges">
            <span class="pay-badge badge-mir">МИР</span>
            <span class="pay-badge badge-visa">VISA</span>
            <span class="pay-badge badge-mc">MC</span>
          </div>
        </div>

        <form id="card-pay-form" class="checkout-form" onsubmit="event.preventDefault();">
          <div class="form-group">
            <label for="card-num">Номер карты</label>
            <input type="text" id="card-num" class="form-input" placeholder="0000 0000 0000 0000" maxlength="19" value="2200 7000 1234 5678" required />
          </div>

          <div class="card-row-2">
            <div class="form-group">
              <label for="card-exp">Срок действия</label>
              <input type="text" id="card-exp" class="form-input" placeholder="ММ / ГГ" maxlength="5" value="12/28" required />
            </div>
            <div class="form-group">
              <label for="card-cvc">Код CVC / CVV</label>
              <input type="password" id="card-cvc" class="form-input" placeholder="•••" maxlength="4" value="888" required />
            </div>
          </div>

          <div class="form-group">
            <label for="card-holder">Имя держателя карты (латиницей)</label>
            <input type="text" id="card-holder" class="form-input" placeholder="CARDHOLDER NAME" value="EVGENIY SOLOVEY" required />
          </div>

          <button type="button" class="btn block primary" id="btn-pay-card" style="padding: 14px; font-size: 1.05rem; margin-top: 10px;" data-action="submit-card-pay">
            💳 Оплатить ${esc(plan.price)}
          </button>

          <div class="pci-security-pill">
            <span>🔒</span> Платёжный шлюз ЮKassa · 3-D Secure протокол · Данные зашифрованы TLS 1.3
          </div>
        </form>
      </div>
    `;
  } else if (step === 3) {
    const orderId = state.checkoutOrder?.id || 'TR-782910';
    container.innerHTML = `
      <div style="text-align: center; padding: 16px 0;">
        <div style="font-size: 3.5rem; margin-bottom: 12px; animation: modal-pop 0.3s ease;">🎉</div>
        <h2 style="font-family: var(--font-display); font-size: 1.4rem; margin: 0 0 8px; color: var(--ink);">Оплата успешно проведена!</h2>
        <p style="color: #10b981; font-weight: 600; font-size: 1.05rem; margin: 0 0 12px;">Подписка активирована на вашем аккаунте</p>
        
        <div style="background: rgba(255,255,255,0.04); border: 1px solid var(--card-border); border-radius: 14px; padding: 14px; margin: 16px 0 20px; text-align: left; font-size: 0.88rem; line-height: 1.5;">
          <div><strong>Номер заказа:</strong> ${esc(orderId)}</div>
          <div><strong>Тариф:</strong> ${esc(plan.title)}</div>
          <div><strong>Сумма:</strong> ${esc(plan.price)}</div>
          <div><strong>Статус:</strong> Оплачено онлайн (ЮKassa)</div>
          <div style="margin-top: 6px; font-size: 0.82rem; color: var(--muted);">Электронный кассовый чек отправлен на вашу почту.</div>
        </div>

        <button type="button" class="btn block primary" data-action="finish-checkout" style="padding: 14px;">
          🚀 Начать заниматься
        </button>
      </div>
    `;
  }
}

function openLegalModal(docKey) {
  const doc = LEGAL_DOCS[docKey] || LEGAL_DOCS.terms;
  const container = document.getElementById('legal-modal-content');
  if (container) {
    container.innerHTML = doc.content;
  }
  const modal = document.getElementById('legal-modal');
  if (modal) {
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
  }
}

function closeLegalModal() {
  const modal = document.getElementById('legal-modal');
  if (modal) {
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
  }
}

function renderHome() {
  if (state.panel === 'scores') return renderScoresPanel();
  if (state.panel === 'streak') return renderStreakPanel();
  if (state.panel === 'tariffs') return renderTariffsPanel();
  if (state.panel === 'accuracy') return renderAccuracyPanel();

  const name = state.me?.display_name || getUnsafeUser()?.first_name || 'ученик';
  const xp = state.stats?.xp ?? state.me?.xp ?? 0;
  const streak = state.stats?.streak_days ?? state.me?.streak_days ?? 0;
  const daily = state.daily;
  const vibe = getTheme() === 'vibe';
  const progress =
    daily?.tasks_total > 0
      ? Math.round((daily.tasks_completed / daily.tasks_total) * 100)
      : 0;
  const studentGrade = state.me?.grade ? Number(state.me.grade) : 1;

  const isPro = isProUser();
  const accuracy = state.dashboard?.accuracy ?? state.stats?.accuracy_pct ?? state.me?.accuracy_pct;
  const tasksCompleted = daily ? (daily.tasks_completed || 0) : 0;
  const tasksTotal = daily ? (daily.tasks_total || 8) : 8;
  const tasksLeft = Math.max(0, tasksTotal - tasksCompleted);

  // 7-дневный календарь стрика
  const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
  const nowDay = (new Date().getDay() + 6) % 7; // 0 = Mon, 6 = Sun
  const weekDaysHtml = dayNames.map((d, idx) => {
    const isToday = idx === nowDay;
    const isDone = streak > 0 && idx <= nowDay;
    return `
      <div class="streak-day-item${isDone ? ' active' : ''}${isToday ? ' today' : ''}">
        <span class="streak-day-badge">${isDone ? '🔥' : (isToday ? '🎯' : '○')}</span>
        <span>${d}</span>
      </div>
    `;
  }).join('');

  return `
    <div class="desktop-dashboard">
      <!-- 1. Hero Progress Banner -->
      <section class="desktop-hero-banner">
        <div class="desktop-hero-info">
          <div class="desktop-hero-pill">
            <span>🇧🇾</span>
            <span>Беларусь · ${studentGrade} класс · Русский язык · ЦТ / ЦЭ</span>
          </div>
          <h1 class="desktop-hero-title">Добро пожаловать, ${esc(name)}! 🎓</h1>
          <p class="desktop-hero-sub">
            Твой персональный образовательный портал. Подготовка к урокам, аттестации и экзаменам ЦТ / ЦЭ.
          </p>
          <div class="desktop-hero-stats">
            <button type="button" class="desktop-stat-chip clickable" data-action="go-rating">
              <span>⚡</span> <span>${xp} XP</span>
            </button>
            <button type="button" class="desktop-stat-chip clickable" data-action="open-streak">
              <span>🔥</span> <span>${streak} дн. подряд</span>
            </button>
            <button type="button" class="desktop-stat-chip clickable" data-action="open-accuracy">
              <span>🎯</span> <span>${accuracy != null ? accuracy + '% точность' : 'Точность —'}</span>
            </button>
            <button type="button" class="desktop-stat-chip clickable" data-action="open-tariffs">
              <span>💎</span> <span>${esc(tariffShortLabel())}</span>
            </button>
          </div>
        </div>

        <div class="desktop-target-card">
          <div class="desktop-target-header">
            <span>🎯 Цель на сегодня</span>
            <span style="color:var(--accent)">${tasksCompleted} из ${tasksTotal} заданий</span>
          </div>
          <div class="desktop-progress-track">
            <div class="desktop-progress-fill" style="width:${progress}%"></div>
          </div>
          ${
            daily?.can_practice === false
              ? `<p class="muted small" style="margin:0">${esc(daily.reason || 'Лимит на сегодня выполнен')}</p>`
              : (tasksLeft > 0
                ? `<button type="button" class="btn primary block" data-action="go-practice" style="padding:11px 18px">🚀 Решать задания (${tasksLeft} ост.)</button>`
                : `<button type="button" class="btn secondary block" data-action="reload-daily" style="padding:11px 18px">🎉 Цель дня закрыта! Новая подборка</button>`)
          }
        </div>
      </section>

      <!-- 2. Main Columns: Learning Pathway (Left) + Widgets (Right) -->
      <div class="desktop-home-columns">
        <!-- Левая колонка: Программа, Тренажёры, Экзамены -->
        <div class="desktop-main-col">
          <!-- Блок: Учебный маршрут -->
          <section class="card" style="padding:24px 28px">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
              <h2 style="font-size:1.2rem; margin:0">📚 Программа обучения · ${studentGrade} класс</h2>
              <span class="chip active">Школа & ЦТ</span>
            </div>
            <p class="muted" style="margin-bottom:14px; font-size:0.92rem">
              Официальный тематический курс Министерства образования РБ. Всегда в понятном порядке:
            </p>
            ${renderLearningPath(0, { hasExtra: true })}
            <button type="button" class="btn block primary" style="margin-top:16px; padding:13px" data-action="go-my-curriculum">
              📚 Открыть программу ${studentGrade} класса
            </button>
          </section>

          <!-- Блок: Экзаменационный центр и симуляторы -->
          <section class="card" style="padding:24px 28px">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
              <h2 style="font-size:1.2rem; margin:0">⚡ Практика и экзаменационный центр</h2>
            </div>
            
            <div class="action-cards-grid">
              ${
                studentGrade === 10 || studentGrade === 11
                  ? `
                  <div class="action-card">
                    <div>
                      <h3>🎓 Симулятор ЦТ / ЦЭ (РИКЗ)</h3>
                      <p>40 вопросов, таймер 180 минут, перевод первичных баллов в 100-балльную тестовую шкалу РИКЗ.</p>
                    </div>
                    <button type="button" class="btn block primary" data-action="start-exam">⏱ Запустить симулятор</button>
                  </div>
                  <div class="action-card">
                    <div>
                      <h3>🎟 Варианты ЦТ / ЦЭ</h3>
                      <p>Каталог официальных тренировочных тестов прошлых лет с бланками ответов и разбором.</p>
                    </div>
                    <button type="button" class="btn block secondary" data-action="open-exam-variants">Открыть варианты</button>
                  </div>
                  `
                  : (studentGrade >= 1 && studentGrade <= 4
                    ? `
                    <div class="action-card">
                      <div>
                        <h3>🎨 Карточки с картинками</h3>
                        <p>Интерактивные иллюстрированные задания по слогам, звукам и правилам правописания.</p>
                      </div>
                      <button type="button" class="btn block primary" data-action="go-extra-tasks">🎨 Открыть карточки</button>
                    </div>
                    <div class="action-card">
                      <div>
                        <h3>📖 Школьный учебник</h3>
                        <p>Задания из школьного учебника ${studentGrade} класса с проверкой.</p>
                      </div>
                      <button type="button" class="btn block secondary" data-action="go-my-curriculum">Открыть учебник</button>
                    </div>
                    `
                    : `
                    <div class="action-card">
                      <div>
                        <h3>⚡ Интерактивный тренажёр</h3>
                        <p>Тренировка орфографии, пунктуации и морфологии по темам ${studentGrade} класса.</p>
                      </div>
                      <button type="button" class="btn block primary" data-action="go-practice">⚡ Начать тренировку</button>
                    </div>
                    ${
                      studentGrade === 9
                        ? `
                        <div class="action-card">
                          <div>
                            <h3>📖 Изложения (сборник НИО)</h3>
                            <p>Официальные тексты Министерства образования для выпускного экзамена за 9 класс.</p>
                          </div>
                          <button type="button" class="btn block secondary" data-action="izlo-catalog">Каталог текстов</button>
                        </div>
                        `
                        : `
                        <div class="action-card">
                          <div>
                            <h3>📚 Программа по темам</h3>
                            <p>Полный список разделов и тем школьного курса с теорией.</p>
                          </div>
                          <button type="button" class="btn block secondary" data-action="go-my-curriculum">Открыть программу</button>
                        </div>
                        `
                    }
                    `)
              }
            </div>
          </section>
        </div>

        <!-- Правая колонка: Десктопные виджеты -->
        <div class="desktop-side-col">
          <!-- Виджет 1: Ударный режим / Календарь стрика -->
          <section class="card" style="padding:20px 22px">
            <div style="display:flex; justify-content:space-between; align-items:center">
              <strong style="font-size:1rem; color:var(--ink)">🔥 Ударный режим</strong>
              <span class="chip active">${streak} дн. подряд</span>
            </div>
            <p class="muted small" style="margin:6px 0 10px">
              Занимайся каждый день по 10 минут, чтобы сохранять серию и закреплять материал.
            </p>
            <div class="streak-week-tracker">
              ${weekDaysHtml}
            </div>
            <button type="button" class="btn block secondary sm" data-action="open-streak" style="margin-top:10px">
              Подробнее о стрике
            </button>
          </section>

          <!-- Виджет 2: Зал славы / Рейтинг -->
          <section class="card" style="padding:20px 22px">
            <div style="display:flex; justify-content:space-between; align-items:center">
              <strong style="font-size:1rem; color:var(--ink)">🏆 Зал славы</strong>
              <span style="font-size:0.82rem; color:var(--accent); font-weight:700">Лига ${studentGrade} кл.</span>
            </div>
            <p class="muted small" style="margin:6px 0 12px">
              Твой результат: <strong>${xp} XP</strong>. Соревнуйся с учениками своей школы и всей Беларуси!
            </p>
            <button type="button" class="btn block secondary sm" data-action="go-rating">
              🏆 Открыть полный рейтинг →
            </button>
          </section>

          <!-- Виджет 3: Кабинет семьи и родители -->
          <section class="card" style="padding:20px 22px">
            <div style="display:flex; justify-content:space-between; align-items:center">
              <strong style="font-size:1rem; color:var(--ink)">👨‍👩‍👧 Кабинет семьи</strong>
              <span style="font-size:0.8rem; color:#10b981; font-weight:700">Telegram</span>
            </div>
            <p class="muted small" style="margin:6px 0 12px">
              Подключи родителей — бот будет автоматически отправлять им еженедельный отчёт об успехах, оценках и времени занятий.
            </p>
            <button type="button" class="btn block secondary sm" data-action="go-family">
              👨‍👩‍👧 Настроить доступ родителей
            </button>
          </section>

          <!-- Виджет 4: Статус подписки -->
          <section class="card" style="padding:20px 22px; border: 1px solid rgba(200, 255, 61, 0.25)">
            <div style="display:flex; justify-content:space-between; align-items:center">
              <strong style="font-size:1rem; color:var(--ink)">💎 Подписка Pro</strong>
              <span class="chip ${isPro ? 'active' : ''}">${isPro ? 'Активна' : 'Базовый'}</span>
            </div>
            <ul class="list" style="margin:10px 0; font-size:0.83rem">
              <li><span>Безлимитный тренажёр</span> <span>✓</span></li>
              <li><span>Пошаговый разбор с ИИ</span> <span>✓</span></li>
              <li><span>Официальные бланки РИКЗ</span> <span>✓</span></li>
            </ul>
            <button type="button" class="btn block ${isPro ? 'secondary' : 'primary'} sm" data-action="open-tariffs">
              ${isPro ? 'Управление подпиской' : '⚡ Подключить Pro'}
            </button>
          </section>
        </div>
      </div>
    </div>
  `;
}

async function openExtraTopic(topicId) {
  state.loading = true;
  render();
  try {
    const res = await api.getTopicExtraTasks(topicId, tgId());
    if (res.paywall_required) {
      toast(res.detail || 'Доступно по подписке PRO');
      await openPanel('tariffs');
      return;
    }
    state.activeExtraTopic = res;
    state.extraTaskIndex = 0;
    state.extraTaskSelected = null;
    state.extraTaskText = '';
    state.extraTaskFeedback = null;
  } catch (err) {
    if (err.status === 403 || err.message?.includes('лимит') || err.message?.includes('подписк')) {
      toast('Дневной лимит 25 заданий выполнен! Оформи PRO для безлимита');
      await openPanel('tariffs');
    } else {
      toast(err.message || 'Не удалось загрузить задания');
    }
  } finally {
    state.loading = false;
    render();
  }
}

function lockExtraOptions() {
  document.querySelectorAll('[data-action="submit-extra-task"], .extra-opt-btn').forEach((el) => {
    el.disabled = true;
    el.style.pointerEvents = 'none';
  });
}

async function submitExtraTaskAnswer({ autoAdvance = true } = {}) {
  if (!state.activeExtraTopic || state.extraTaskFeedback) return;
  if (state._extraAnswerInFlight) return;
  const task = state.activeExtraTopic.tasks?.[state.extraTaskIndex];
  if (!task) return;
  const answer = (
    state.extraTaskSelected ||
    document.getElementById('extra-task-text')?.value ||
    state.extraTaskText ||
    ''
  ).trim();
  if (!answer) {
    toast('Выбери или введи ответ');
    return;
  }
  // Синхронно до первого await — второй тап уже не пройдёт.
  state._extraAnswerInFlight = true;
  state.extraSubmitting = true;
  lockExtraOptions();
  try {
    const res = await api.submitExtraTask(task.id, answer, tgId());
    state.extraTaskFeedback = res;
    if (res.user_xp !== undefined && state.me) {
      state.me.xp = res.user_xp;
    }
    if (res.free_tasks_left !== undefined && res.free_tasks_left !== null && state.activeExtraTopic) {
      state.activeExtraTopic.free_tasks_left = res.free_tasks_left;
    }
    const xpBit = res.xp_earned ? ` +${res.xp_earned} XP` : '';
    toast(res.is_correct ? `Верно!${xpBit}` : 'Неверно');
    render();
    if (autoAdvance) {
      if (state._extraAdvanceTimer) clearTimeout(state._extraAdvanceTimer);
      const delay = res.is_correct ? 650 : 1100;
      state._extraAdvanceTimer = setTimeout(() => {
        nextExtraTaskOrFinish();
      }, delay);
      // Лок держим до следующей задачи.
      return;
    }
  } catch (err) {
    state._extraAnswerInFlight = false;
    state.extraSubmitting = false;
    if (err.status === 403 || err.message?.includes('лимит') || err.message?.includes('подписк')) {
      toast('Дневной лимит 25 заданий выполнен! Оформи PRO для безлимита.');
      await openPanel('tariffs');
    } else {
      toast(err.message || 'Ошибка отправки ответа');
    }
    render();
  } finally {
    if (!autoAdvance || !state.extraTaskFeedback) {
      state._extraAnswerInFlight = false;
      state.extraSubmitting = false;
    }
  }
}

function nextExtraTask() {
  if (!state.activeExtraTopic) return;
  if (state._extraAdvanceTimer) {
    clearTimeout(state._extraAdvanceTimer);
    state._extraAdvanceTimer = null;
  }
  state.extraTaskIndex += 1;
  state.extraTaskSelected = null;
  state.extraTaskText = '';
  state.extraSubmitting = false;
  state._extraAnswerInFlight = false;
  state.extraTaskFeedback = null;
  render();
}

function nextExtraTaskOrFinish() {
  const top = state.activeExtraTopic;
  if (!top) return;
  const idx = state.extraTaskIndex || 0;
  const total = top.tasks?.length || 0;
  if (idx + 1 >= total) {
    finishExtraTopic();
  } else {
    nextExtraTask();
  }
}

async function finishExtraTopic() {
  const doneId = state.activeExtraTopic?.topic_id || state.practiceFlow?.topicId || null;
  const doneName = state.activeExtraTopic?.topic_name || state.practiceFlow?.topicName || '';
  state.activeExtraTopic = null;
  state.extraTaskFeedback = null;
  state.extraTaskSelected = null;
  state.extraTaskText = '';

  // 1–4 класс: сразу следующая тема с картинками
  if (isPictureGrade() && doneId) {
    try {
      await ensureCurriculumForPractice();
      const nxt = nextPictureTopic(doneId);
      if (nxt) {
        toast(`Тема «${doneName || 'готово'}» пройдена → дальше: ${nxt.name}`);
        await startPictureTopicPractice(nxt.id, nxt.name);
        return;
      }
    } catch (_) {
      /* fallback ниже */
    }
  }

  state.practiceFlow = null;
  toast('🎉 Отличная работа! Все задания темы пройдены!');
  if (state.extraTasksReturnRoute) {
    const retRoute = state.extraTasksReturnRoute;
    state.extraTasksReturnRoute = null;
    setRoute(retRoute);
  } else {
    await loadForRoute();
  }
}

function renderExtraTasks() {
  if (state.activeExtraTopic) {
    return renderActiveExtraTopic();
  }

  const sum = state.extraTasksSummary;
  const myGrade = Number(state.me?.grade) || 1;
  const currentGrade = myGrade;
  state.extraTasksGrade = myGrade;
  const query = (state.extraTopicsSearch || '').toLowerCase().trim();
  const allTopics = sum?.topics || [];
  const filteredTopics = query
    ? allTopics.filter(t => (t.name && t.name.toLowerCase().includes(query)) || (t.section_name && t.section_name.toLowerCase().includes(query)))
    : allTopics;

  return `
    <section class="card" style="margin-bottom:12px">
      <div class="panel-head">
        <button type="button" class="linkish" data-action="go-home">← Главная</button>
        <h2>🧩 Шаг 2 · Доп. тренажёр</h2>
      </div>
      <p class="muted">Доп. карточки для <strong>${currentGrade} класса</strong> — после учебника. Не путать с заданиями из книги.</p>

      ${
        sum
          ? `<div style="display:flex; justify-content:space-around; background:var(--bg-subtle, rgba(255,255,255,0.04)); border-radius:12px; padding:10px; margin-top:8px;">
               <div style="text-align:center">
                 <strong style="font-size:1.15rem; color:var(--accent)">${sum.total_topics || 0}</strong>
                 <div class="muted" style="font-size:0.75rem">Темы</div>
               </div>
               <div style="text-align:center">
                 <strong style="font-size:1.15rem; color:#10b981">${sum.total_extra_tasks || 0}</strong>
                 <div class="muted" style="font-size:0.75rem">Всего заданий</div>
               </div>
               <div style="text-align:center">
                 <strong style="font-size:1.15rem; color:#f59e0b">${sum.solved_tasks || 0}</strong>
                 <div class="muted" style="font-size:0.75rem">Решено</div>
               </div>
             </div>`
          : ''
      }

      ${
        sum && !sum.is_pro
          ? `<div style="margin-top:12px; padding:12px; border-radius:12px; background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.25);">
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-size:0.85rem; font-weight:600; color:#f59e0b;">Бесплатные задания на сегодня</span>
                <span style="font-size:0.85rem; font-weight:700;">${sum.total_completed_all || 0} / ${sum.free_limit || 25}</span>
              </div>
              <div style="height:6px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden; margin-bottom:8px;">
                <div style="height:100%; width:${Math.min(100, (((sum.total_completed_all || 0) / (sum.free_limit || 25)) * 100))}%; background:#f59e0b; border-radius:3px;"></div>
              </div>
              ${(sum.total_completed_all || 0) >= (sum.free_limit || 25) 
                  ? `<button type="button" class="btn block primary" style="padding:8px;" data-action="open-tariffs">⚡ Оформить PRO (безлимит)</button>` 
                  : ''}
            </div>`
          : ''
      }
    </section>

    <div style="margin: 10px 0 12px;">
      <input type="search" 
             id="extra-topics-search" 
             placeholder="🔍 Найти тему (например: жи-ши, слоги, имена)..." 
             value="${esc(state.extraTopicsSearch || '')}"
             style="width:100%; padding:10px 14px; border-radius:12px; border:1px solid var(--card-border); background:var(--card); color:var(--ink); font-size:0.92rem; box-sizing:border-box;">
    </div>

    ${
      !sum || !sum.topics || sum.topics.length === 0
        ? `<section class="card empty">Для ${currentGrade} класса доп. задания пока не загружены.</section>`
        : filteredTopics.length === 0
        ? `<section class="card empty">Ничего не найдено по запросу «${esc(state.extraTopicsSearch)}». Попробуй другое слово.</section>`
        : `<div style="display:flex; flex-direction:column; gap:10px;">
            ${filteredTopics
              .map(
                (top) => `
              <div class="card" style="padding:14px; border-radius:14px; border:1px solid var(--card-border);">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:6px;">
                  <strong style="font-size:1rem; line-height:1.3">${esc(top.name)}</strong>
                  <span style="font-size:0.75rem; background:rgba(59,130,246,0.15); color:#60a5fa; padding:2px 8px; border-radius:10px; white-space:nowrap; margin-left:8px;">
                    ${top.extra_tasks_count} зад.
                  </span>
                </div>
                <div style="font-size:0.8rem; color:var(--muted); margin-bottom:10px;">
                  ${esc(top.section_name)} · Решено: ${top.solved_count}/${top.extra_tasks_count}
                  ${top.mastery_score > 0 ? ` · Освоение: ${top.mastery_score}%` : ''}
                </div>
                <button type="button" class="btn block ${top.solved_count >= top.extra_tasks_count ? 'secondary' : 'primary'}" 
                        style="padding:8px;" 
                        data-action="open-extra-topic" 
                        data-topic-id="${top.id}">
                  ${top.solved_count >= top.extra_tasks_count ? 'Повторить задания' : 'Решать задания'}
                </button>
              </div>`
              )
              .join('')}
          </div>`
    }
  `;
}

function renderActiveExtraTopic() {
  const top = state.activeExtraTopic;
  const idx = state.extraTaskIndex || 0;
  const total = top.tasks?.length || 0;
  const task = top.tasks?.[idx];
  const fb = state.extraTaskFeedback;

  if (!task) {
    return `
      <section class="card" style="text-align:center; padding:24px;">
        <h2>🎉 Все задания темы пройдены!</h2>
        <p class="muted">Ты успешно прорешал дополнительные задания по теме «${esc(top.topic_name)}».</p>
        <button type="button" class="btn block primary" style="margin-top:14px;" data-action="finish-extra-topic">Вернуться к списку тем</button>
      </section>
    `;
  }

  const progressPct = Math.round(((idx + 1) / total) * 100);

  return `
    <section class="card">
      <div class="panel-head">
        <button type="button" class="linkish" data-action="back-from-extra-topic">← Назад</button>
        <div style="display:flex; align-items:center; gap:8px;">
          ${!top.is_pro && top.free_tasks_left !== undefined && top.free_tasks_left !== null
            ? `<span style="font-size:0.75rem; background:rgba(245,158,11,0.2); color:#f59e0b; padding:2px 8px; border-radius:8px; font-weight:600;">Бесплатно: ${top.free_tasks_left}</span>`
            : ''}
          <span class="muted" style="font-size:0.85rem">${idx + 1} из ${total}</span>
        </div>
      </div>
      ${renderLearningPath(2, { hasExtra: true })}
      <div class="progress" style="margin:8px 0 14px;"><i style="width:${progressPct}%"></i></div>
      
      <div style="margin-bottom:8px;">
        <span style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.05em; color:var(--accent);">🧩 Шаг 2 · ${esc(top.topic_name)}</span>
        ${task.difficulty ? `<span style="font-size:0.75rem; margin-left:8px; opacity:0.7">· ${task.difficulty === 'easy' ? 'базовое' : 'среднее'}</span>` : ''}
      </div>

      ${task.image ? `
        <div style="text-align:center; margin:10px 0 14px;">
          <img src="${esc(task.image)}" alt="Иллюстрация к заданию" 
               style="max-width:100%; max-height:220px; border-radius:16px; object-fit:contain; box-shadow:0 6px 20px rgba(0,0,0,0.18);" loading="lazy">
        </div>
      ` : ''}

      ${task.reading_text ? `<div style="background:var(--bg-subtle, rgba(255,255,255,0.05)); padding:12px; border-radius:10px; margin-bottom:12px; font-size:0.9rem; line-height:1.4">${esc(task.reading_text)}</div>` : ''}

      <h3 style="font-size:1.1rem; line-height:1.4; margin:0 0 16px;">${esc(task.question)}</h3>

      ${
        task.options && task.options.length
          ? `<div style="display:flex; flex-direction:column; gap:8px; margin-bottom:16px;">
              ${task.options
                .map((opt) => {
                  const isSelected = state.extraTaskSelected === opt;
                  let optCls = '';
                  if (fb) {
                    if (opt === fb.correct_answer) {
                      optCls = ' correct-ans';
                    } else if (isSelected && !fb.is_correct) {
                      optCls = ' wrong-ans';
                    }
                  } else if (isSelected) {
                    optCls = ' selected';
                  }
                  return `
                    <button type="button" 
                            class="extra-opt-btn${optCls}" 
                            ${fb ? 'disabled' : ''}
                            data-action="select-extra-opt" 
                            data-opt="${esc(opt)}">
                      ${esc(opt)}
                    </button>
                  `;
                })
                .join('')}
            </div>`
          : `<div style="margin-bottom:16px;">
              <input type="text" id="extra-task-text" placeholder="Введи ответ…" value="${esc(state.extraTaskText || '')}" ${fb ? 'disabled' : ''} style="width:100%; padding:12px; border-radius:10px; border:1px solid var(--card-border); background:var(--card); color:var(--fg);">
            </div>`
      }

      ${
        fb
          ? `<div style="margin:14px 0; padding:14px; border-radius:12px; border:1px solid ${fb.is_correct ? '#10b981' : '#ef4444'}; background:${fb.is_correct ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)'};">
              <strong style="color:${fb.is_correct ? '#10b981' : '#ef4444'}; font-size:1rem;">
                ${fb.is_correct ? '✓ Правильно! +' + fb.xp_earned + ' XP' : '✗ Неверно!'}
              </strong>
              ${!fb.is_correct && fb.correct_answer ? `<div style="margin-top:6px; font-size:0.9rem;">Правильный ответ: <strong>${esc(fb.correct_answer)}</strong></div>` : ''}
              ${fb.explanation ? `<div style="margin-top:8px; font-size:0.88rem; line-height:1.4; color:var(--fg); opacity:0.9;">${esc(fb.explanation)}</div>` : ''}
              <p class="muted" style="margin:10px 0 0; font-size:0.8rem">Сейчас следующее задание…</p>
            </div>`
          : task.options && task.options.length
            ? `<p class="muted" style="margin:0; font-size:0.85rem; text-align:center">Нажми вариант — проверка сразу</p>`
            : `<button type="button" class="btn block primary" data-action="submit-extra-task" ${state.extraSubmitting ? 'disabled' : ''}>Проверить ответ</button>`
      }
    </section>
  `;
}

function renderGradeCurriculum() {
  const cur = state.selectedGradeCurriculum;
  if (!cur) return '';
  const myGrade = Number(state.me?.grade) || null;
  const isMyGrade = myGrade === cur.grade;

  const sectionsHtml = (cur.sections || []).map((sec) => {
    const topicsHtml = (sec.topics || []).map((top) => {
      const tasks = top.task_count || 0;
      const extras = top.extra_task_count || 0;
      const solved = top.solved_count || 0;
      const pct = top.progress_percent !== undefined
        ? top.progress_percent
        : (tasks > 0 ? Math.min(100, Math.round((solved / tasks) * 100)) : 0);
      const expanded = state.expandedTopicIds.has(top.id);
      const pro = isProUser();

      let progressBorder = 'rgba(255, 255, 255, 0.12)';
      let progressTextColor = 'var(--muted)';

      if (pct > 0 && pct < 40) {
        progressBorder = 'rgba(245, 158, 11, 0.45)';
        progressTextColor = '#fbbf24';
      } else if (pct >= 40 && pct < 80) {
        progressBorder = 'rgba(99, 102, 241, 0.45)';
        progressTextColor = '#a5b4fc';
      } else if (pct >= 80) {
        progressBorder = 'rgba(16, 185, 129, 0.5)';
        progressTextColor = '#6ee7b7';
      }

      const metaBits = [];
      if (tasks > 0) metaBits.push(`📖 ${tasks}`);
      if (extras > 0) metaBits.push(`🧩 ${extras}`);
      const metaLine = metaBits.length ? metaBits.join(' · ') : 'нет заданий';

      return `
        <div class="curriculum-topic-card${expanded ? ' is-open' : ''}" style="background:var(--bg-secondary); border-radius:14px; margin-bottom:10px; border:1px solid var(--card-border); overflow:hidden">
          <button type="button" class="topic-card-head" data-action="toggle-topic" data-topic-id="${top.id}" aria-expanded="${expanded ? 'true' : 'false'}">
            <div class="topic-card-head-main">
              <strong style="font-size:0.95rem; line-height:1.3">📌 ${esc(top.name)}</strong>
              <span class="muted" style="font-size:0.78rem; margin-top:4px; display:block">${metaLine}${tasks > 0 ? ` · решено ${solved}/${tasks}` : ''}</span>
            </div>
            <div class="topic-card-head-side">
              ${tasks > 0 ? `
                <span class="topic-progress-badge" style="border:1px solid ${progressBorder}">
                  <span style="position:relative;z-index:1;font-size:0.72rem;font-weight:700;color:${progressTextColor}">
                    ${pct === 100 ? '✅ ' : ''}${pct}%
                  </span>
                </span>
              ` : ''}
              <span class="topic-chevron" aria-hidden="true">${expanded ? '▾' : '▸'}</span>
            </div>
          </button>
          ${expanded ? `
            <div class="topic-card-body">
              ${top.has_summary && top.summary_key_points ? `
                <div style="font-size:0.82rem; color:var(--muted); margin-bottom:10px">
                  💡 ${esc(top.summary_key_points.slice(0, 140))}${top.summary_key_points.length > 140 ? '…' : ''}
                </div>
              ` : ''}
              <div style="display:flex; flex-direction:column; gap:8px;">
                ${tasks > 0 ? `
                  <button type="button" class="btn block primary small"
                    data-action="start-topic-practice"
                    data-topic="${top.id}"
                    data-grade="${cur.grade}"
                    data-topic-name="${escAttr(top.name)}"
                    data-extra-count="${extras}">
                    📖 Учебник · ${tasks} ${tasks === 1 ? 'задание' : tasks < 5 ? 'задания' : 'заданий'}
                  </button>
                  <p class="muted" style="font-size:0.75rem; margin:-2px 0 0">Упражнения и материалы из официального школьного учебника</p>
                ` : ''}
                ${extras > 0 ? `
                  <button type="button" class="btn block ${tasks > 0 ? 'secondary' : 'primary'} small"
                    data-action="open-extra-topic"
                    data-topic-id="${top.id}"
                    data-topic-name="${escAttr(top.name)}">
                    🎮 Игровой тренажёр · ${extras} карточек
                  </button>
                  <p class="muted" style="font-size:0.75rem; margin:-2px 0 0">Иллюстрированные карточки с любимыми героями мультиков</p>
                ` : ''}
                ${tasks === 0 && extras === 0 ? `
                  <p class="muted" style="font-size:0.85rem; margin:0">По этой теме пока нет заданий.</p>
                ` : ''}
                ${pro
                  ? `<button type="button" class="btn block small ai-btn-active" data-action="ai-hint-pro" style="margin-top:2px">
                       🤖 Разбор с ИИ · активировано
                     </button>
                     <p class="muted" style="font-size:0.75rem; margin:-2px 0 0">Кнопка появится после ответа на задании, если нужна помощь</p>`
                  : `<button type="button" class="btn block secondary small pro-locked-btn" data-action="open-tariffs" style="margin-top:2px; opacity:0.85">
                       🤖 Разбор с ИИ · открыть по подписке
                     </button>
                     <p class="muted" style="font-size:0.75rem; margin:-2px 0 0">После ошибки на задании — персональный разбор</p>`
                }
              </div>
            </div>
          ` : ''}
        </div>
      `;
    }).join('');

    return `
      <section class="card" style="margin-bottom:12px">
        <h2 style="font-size:1.05rem; margin-bottom:10px">📖 ${esc(sec.name)}</h2>
        <div class="curriculum-topics-list">
          ${topicsHtml}
        </div>
      </section>
    `;
  }).join('');

  const hasExtra = Boolean(
    cur.has_extra_materials ||
    cur.has_ct_ce ||
    cur.has_izlozheniya ||
    (cur.collections && cur.collections.length > 0)
  );

  const currentTab = hasExtra ? (state.gradeTab || 'school') : 'school';

  const tabSwitcherHtml = hasExtra ? `
    <div class="period-row" style="margin-bottom:12px; display:flex; gap:8px">
      <button type="button" class="period-chip ${currentTab !== 'collections' ? 'active' : ''}" data-action="set-grade-tab" data-tab="school" style="flex:1; text-align:center">
        📚 Школьная программа
      </button>
      <button type="button" class="period-chip ${currentTab === 'collections' ? 'active' : ''}" data-action="set-grade-tab" data-tab="collections" style="flex:1; text-align:center">
        📦 Сборники и практикумы
      </button>
    </div>
  ` : '';

  let contentHtml = '';

  if (currentTab !== 'collections') {
    // 📚 Школьная программа по учебнику
    const textbookCnt = cur.school_textbook_tasks_count ?? cur.school_tasks_count ?? cur.total_tasks;
    contentHtml = `
      <section class="card" style="margin-bottom:12px">
        <p class="muted" style="font-size:0.88rem; margin-bottom:10px">${
          isPictureGrade(cur.grade)
            ? 'Открой тему по порядку — карточки с картинками. Практика идёт тема за темой.'
            : 'Нажми тему — учебник, доп. задания и разбор с ИИ.'
        }</p>
        ${
          isPictureGrade(cur.grade) && (cur.total_extra_tasks || 0) > 0
            ? `
          <button type="button" class="btn block primary" data-action="start-picture-sequence" data-grade="${cur.grade}">
            🖼 Учиться по порядку тем · карточки с картинками
          </button>
        `
            : `
          <button type="button" class="btn block secondary" data-action="start-grade-mix-practice" data-grade="${cur.grade}">
            🎯 Микс по учебнику · ${textbookCnt} заданий
          </button>
        `
        }
        ${
          !isPictureGrade(cur.grade) && (cur.total_extra_tasks || 0) > 0
            ? `
          <button type="button" class="btn block secondary" style="margin-top:8px" data-action="go-extra-tasks">
            🧩 Все доп. задания класса · ${cur.total_extra_tasks}
          </button>
        `
            : ''
        }
      </section>
      ${sectionsHtml || '<section class="card"><p class="muted">В этом классе темы ещё формируются.</p></section>'}
    `;
  } else {
    // 📦 Вкладка: Сборники и спецматериалы
    if (cur.grade === 11) {
      const selYear = state.selectedExamYear;
      const yData = (cur.available_years || []).find((y) => y.year === selYear);
      const yearLabel = selYear ? `${selYear} год` : 'Все годы (2003–2025)';
      const totalCnt = yData ? yData.total_tasks : (cur.total_tasks || 13345);
      const partACnt = yData ? yData.part_a_count : (cur.part_a_count || 9631);
      const partBCnt = yData ? yData.part_b_count : (cur.part_b_count || 3714);
      const varCnt = yData ? yData.variants_count : 224;

      contentHtml = `
        <section class="card" style="margin-bottom:12px; border-left: 4px solid var(--accent, #6366f1)">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px">
            <h2 style="font-size:1.1rem; margin:0">🎓 Банк заданий ЦТ и ЦЭ (РИКЗ 2003–2025)</h2>
            <span class="chip active">13 345 заданий</span>
          </div>
          <p class="muted" style="margin-bottom:12px; font-size:0.9rem">
            Выбирай официальный год тестирования РИКЗ или тренируйся по общему банку:
          </p>

          <div style="margin-bottom:14px">
            <div class="muted small" style="margin-bottom:6px; font-weight:600">📅 Год тестирования:</div>
            <div class="period-row" style="overflow-x:auto; padding-bottom:6px; display:flex; gap:6px">
              <button type="button" class="period-chip ${!state.selectedExamYear ? 'active' : ''}" data-action="select-exam-year" data-year="">
                Все годы
              </button>
              ${(cur.available_years || []).map((y) => `
                <button type="button" class="period-chip ${state.selectedExamYear === y.year ? 'active' : ''}" data-action="select-exam-year" data-year="${y.year}">
                  ${y.year}
                </button>
              `).join('')}
            </div>
          </div>

          <div style="background:var(--bg-glass, rgba(255,255,255,0.05)); border-radius:8px; padding:10px; margin-bottom:12px">
            <div style="display:flex; justify-content:space-between; margin-bottom:4px">
              <strong>✨ ${yearLabel}</strong>
              <span class="muted small">${varCnt} вариантов</span>
            </div>
            <div class="muted small">${totalCnt} заданий: ${partACnt} тестов Части А и ${partBCnt} открытых заданий Части Б</div>
          </div>

          <div style="display:flex; flex-direction:column; gap:8px">
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px">
              <button type="button" class="btn primary" data-action="start-mode-practice" data-grade="11" data-mode="part_a" ${selYear ? `data-year="${selYear}"` : ''}>
                🔘 Часть А (${partACnt})
              </button>
              <button type="button" class="btn secondary" data-action="start-mode-practice" data-grade="11" data-mode="part_b" ${selYear ? `data-year="${selYear}"` : ''}>
                ✍️ Часть Б (${partBCnt})
              </button>
            </div>
            <button type="button" class="btn block" data-action="start-exam" ${selYear ? `data-year="${selYear}"` : ''} style="background:linear-gradient(135deg, #10b981, #059669); color:#fff">
              ⏱️ Симулятор ЦТ/ЦЭ ${selYear ? `(${selYear} год)` : ''} (40 заданий · 180 мин)
            </button>
          </div>
        </section>

        <section class="card" style="margin-bottom:12px">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px">
            <h2 style="font-size:1.05rem; margin:0">📚 Сборники «ЦТ за 60 уроков» (Аверсэв)</h2>
            <span class="chip" style="opacity:0.7">Пополняется</span>
          </div>
          <p class="muted small" style="margin:0">Тематические тренажёры интенсивного повторения и систематизации правил перед экзаменом.</p>
        </section>
      `;
    } else if (cur.grade === 9) {
      contentHtml = `
        <section class="card" style="margin-bottom:12px; border-left: 4px solid var(--accent, #6366f1)">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px">
            <h2 style="font-size:1.1rem; margin:0">📖 Экзаменационные изложения (НИО)</h2>
            <span class="chip active">${cur.izlozheniya_count || 166} текстов</span>
          </div>
          <p class="muted" style="margin-bottom:12px; font-size:0.9rem">
            Официальный сборник материалов Министерства образования РБ для выпускного экзамена за 9 класс:
          </p>
          <div style="display:flex; flex-direction:column; gap:8px">
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px">
              <button type="button" class="btn primary" data-action="izlo-catalog">
                📖 Каталог текстов
              </button>
              <button type="button" class="btn secondary" data-action="izlo-random">
                🎲 Случайный текст
              </button>
            </div>
            <button type="button" class="btn block secondary small" data-action="start-mode-practice" data-grade="9" data-mode="izlozhenie">
              ⚡ Экспресс-тренинг по изложениям
            </button>
          </div>
        </section>

        <section class="card" style="margin-bottom:12px">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px">
            <h2 style="font-size:1.05rem; margin:0">✍️ Сборник экзаменационных диктантов 9 класса</h2>
            <span class="chip" style="opacity:0.7">Пополняется</span>
          </div>
          <p class="muted small" style="margin:0">Тексты контрольных диктантов и грамматические задания для итоговой аттестации.</p>
        </section>
      `;
    } else {
      const cols = cur.collections || [];
      contentHtml = cols.map((col) => `
        <section class="card" style="margin-bottom:12px">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px">
            <h2 style="font-size:1.05rem; margin:0">${esc(col.title)}</h2>
            <span class="chip ${col.status === 'available' ? 'active' : ''}" style="${col.status !== 'available' ? 'opacity:0.7' : ''}">
              ${esc(col.badge || (col.status === 'available' ? 'Доступен' : 'Скоро'))}
            </span>
          </div>
          <p class="muted small" style="margin-bottom:10px">${esc(col.description)}</p>
          ${col.status === 'available' && col.tasks_count > 0 ? `
            <button type="button" class="btn block primary small" data-action="start-mode-practice" data-grade="${cur.grade}" data-mode="school">
              ⚡ Тренировать сборник (${col.tasks_count} заданий)
            </button>
          ` : `
            <button type="button" class="btn block secondary small" disabled style="opacity:0.6">
              Материалы сборника пополняются методистами
            </button>
          `}
        </section>
      `).join('');
      if (!contentHtml) {
        contentHtml = '<section class="card"><p class="muted">Сборники для этого класса пополняются методистами.</p></section>';
      }
    }
  }

  return `
    <section class="hero" style="margin-bottom:12px">
      <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; gap:8px">
        <button type="button" class="btn secondary small" data-action="courses-back-to-catalog">← Все классы</button>
        ${isMyGrade ? `
          <span class="chip active" style="font-weight:700">⭐ Твой класс</span>
        ` : `
          <button type="button" class="btn primary small" data-action="courses-return-to-my-grade">
            ↩️ В свой класс (${myGrade || 11} кл)
          </button>
        `}
      </div>
      <h1>${esc(cur.title)}</h1>
      <p class="muted">${cur.total_topics} тем · учебник: ${cur.school_textbook_tasks_count ?? cur.total_tasks} зад.${
        cur.total_extra_tasks ? ` · доп. тренажёр: ${cur.total_extra_tasks}` : ''
      }</p>
    </section>

    ${tabSwitcherHtml}
    ${contentHtml}
  `;
}

function renderExamCenter() {
  return `
    <div class="exam-center-page">
      <section class="desktop-hero-banner" style="margin-bottom: 24px;">
        <div class="desktop-hero-info">
          <div class="desktop-hero-pill" style="border-color: #10b981; color: #10b981;">
            <span>🇧🇾</span>
            <span>Официальный экзаменационный центр · РИКЗ · ЦТ / ЦЭ</span>
          </div>
          <h1 class="desktop-hero-title">Центр подготовки к ЦТ и ЦЭ 🎓</h1>
          <p class="desktop-hero-sub">
            13 345 официальных тестовых заданий Министерства образования РБ и Республиканского института контроля знаний. Подготовка к вступительным испытаниям в ВУЗы Беларуси.
          </p>
          <div class="desktop-hero-stats">
            <span class="desktop-stat-chip"><span>📑</span> <span>40 заданий в билете</span></span>
            <span class="desktop-stat-chip"><span>⏱️</span> <span>180 минут</span></span>
            <span class="desktop-stat-chip"><span>🎯</span> <span>Шкала 0–100 баллов</span></span>
            <span class="desktop-stat-chip"><span>✅</span> <span>Мгновенный пересчёт РИКЗ</span></span>
          </div>
        </div>

        <div class="desktop-target-card" style="border-color: #10b981;">
          <div class="desktop-target-header">
            <span>⏱️ Экспресс-старт симулятора</span>
            <span style="color:#10b981">40 вопросов · 180 мин</span>
          </div>
          <p class="muted small" style="margin: 6px 0 12px; line-height: 1.4;">
            Полная имитация реального экзаменационного бланка ЦТ/ЦЭ с таймером и переводом в 100 баллов.
          </p>
          <button type="button" class="btn block" data-action="start-exam" style="background: linear-gradient(135deg, #10b981, #059669); color: #fff; padding: 13px 18px; font-weight: 700; box-shadow: 0 4px 18px rgba(16,185,129,0.35);">
            🚀 Запустить симулятор ЦТ / ЦЭ
          </button>
        </div>
      </section>

      <div class="desktop-home-columns">
        <div class="desktop-main-col">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
            <div class="card" style="border-left: 4px solid var(--accent); display:flex; flex-direction:column; justify-content:space-between;">
              <div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                  <h3 style="margin:0; font-size:1.05rem;">🔘 Часть А: Тесты</h3>
                  <span class="sidebar-badge" style="background:rgba(200,255,61,0.15); color:var(--accent);">9 631 зад.</span>
                </div>
                <p class="muted small" style="margin-bottom:12px; line-height:1.45;">
                  Задания закрытого типа с выбором одного или нескольких правильных ответов. Оцениваются в 1–2 первичных балла.
                </p>
              </div>
              <button type="button" class="btn primary block" data-action="start-mode-practice" data-grade="11" data-mode="part_a">
                Тренировать Часть А
              </button>
            </div>

            <div class="card" style="border-left: 4px solid #38bdf8; display:flex; flex-direction:column; justify-content:space-between;">
              <div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                  <h3 style="margin:0; font-size:1.05rem;">✍️ Часть Б: Открытые</h3>
                  <span class="sidebar-badge" style="background:rgba(56,189,248,0.15); color:#38bdf8;">3 714 зад.</span>
                </div>
                <p class="muted small" style="margin-bottom:12px; line-height:1.45;">
                  Задания открытого типа с кратким текстовым ответом (слово, форма слова или основа). Проверяют точное знание правил.
                </p>
              </div>
              <button type="button" class="btn secondary block" data-action="start-mode-practice" data-grade="11" data-mode="part_b" style="border-color:#38bdf8; color:#38bdf8;">
                Тренировать Часть Б
              </button>
            </div>
          </div>

          <section class="card" style="margin-top: 4px;">
            <h2>📋 Спецификация экзаменационной работы</h2>
            <p class="muted small" style="margin-bottom: 14px;">
              Структура теста по русскому языку в соответствии с официальными критериями РИКЗ:
            </p>
            <div style="display: flex; flex-direction: column; gap: 10px;">
              <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:rgba(255,255,255,0.03); border:1px solid var(--card-border); border-radius:12px;">
                <div>
                  <strong>Фонетика, орфоэпия и состав слова</strong>
                  <div class="muted small">Задания А1–А3 · Ударения, морфемы, чередования</div>
                </div>
                <span class="chip active">100% в базе</span>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:rgba(255,255,255,0.03); border:1px solid var(--card-border); border-radius:12px;">
                <div>
                  <strong>Орфография: гласные, согласные, слитно/раздельно</strong>
                  <div class="muted small">Задания А4–А10, Б1–Б4 · Правописание приставок, суффиксов, НЕ/НИ</div>
                </div>
                <span class="chip active">100% в базе</span>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:rgba(255,255,255,0.03); border:1px solid var(--card-border); border-radius:12px;">
                <div>
                  <strong>Пунктуация простого и сложного предложения</strong>
                  <div class="muted small">Задания А11–А18, Б5–Б10 · Однородные, обособленные, СПП, ССП, БСП</div>
                </div>
                <span class="chip active">100% в базе</span>
              </div>
              <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 14px; background:rgba(255,255,255,0.03); border:1px solid var(--card-border); border-radius:12px;">
                <div>
                  <strong>Текст, культура речи, стилистика и нормы</strong>
                  <div class="muted small">Задания Б11–Б22 · Анализ текста, лексическая сочетаемость, плеоназмы</div>
                </div>
                <span class="chip active">100% в базе</span>
              </div>
            </div>
          </section>
        </div>

        <div class="desktop-side-col">
          <section class="card" style="border: 1px solid rgba(16,185,129,0.3);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <h2 style="margin:0; font-size:1.1rem;">🎟 Варианты тестов</h2>
              <span class="sidebar-badge" style="background:#10b981; color:#fff;">РИКЗ</span>
            </div>
            <p class="muted small" style="margin-bottom:12px;">
              Решай реальные бланки вступительных кампаний с официальной шкалой пересчёта:
            </p>
            <div style="display:flex; flex-direction:column; gap:8px;">
              <button type="button" class="btn secondary block" data-action="start-exam" data-year="2024" style="text-align:left; display:flex; justify-content:space-between; align-items:center;">
                <span>🎯 ЦТ 2024 (Официальный билет)</span>
                <span style="font-size:0.75rem; color:var(--accent);">Начать →</span>
              </button>
              <button type="button" class="btn secondary block" data-action="start-exam" data-year="2024" style="text-align:left; display:flex; justify-content:space-between; align-items:center;">
                <span>🎯 ЦЭ 2024 (Единый экзамен)</span>
                <span style="font-size:0.75rem; color:var(--accent);">Начать →</span>
              </button>
              <button type="button" class="btn secondary block" data-action="start-exam" data-year="2023" style="text-align:left; display:flex; justify-content:space-between; align-items:center;">
                <span>🎯 ЦТ / ЦЭ 2023 (Архивный вариант)</span>
                <span style="font-size:0.75rem; color:var(--accent);">Начать →</span>
              </button>
            </div>
          </section>

          <section class="card">
            <h3>🏫 Школьная программа 1–11 классов</h3>
            <p class="muted small" style="margin-bottom:12px; line-height:1.4;">
              Изучение тем по школьным учебникам Беларуси, практические упражнения и правила для каждого класса.
            </p>
            <button type="button" class="btn secondary block" data-action="courses-return-to-my-grade">
              ← Перейти к урокам своего класса
            </button>
            <button type="button" class="btn secondary block" style="margin-top:8px;" data-action="courses-back-to-catalog">
              📚 Каталог всех классов (1–11 кл.)
            </button>
          </section>
        </div>
      </div>
    </div>
  `;
}

function renderCourses() {
  if (state.gradeTab === 'exam') {
    return renderExamCenter();
  }
  if (state.selectedGradeCurriculum && !state.inCoursesCatalog) {
    return renderGradeCurriculum();
  }
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

  const allGrades = subject?.grades || [];
  let sortedGrades = [];
  if (myGrade) {
    const myGradeObj = allGrades.find((g) => g.grade === myGrade);
    const otherGrades = allGrades.filter((g) => g.grade !== myGrade);
    if (myGradeObj) {
      sortedGrades = [myGradeObj, ...otherGrades];
    } else {
      sortedGrades = allGrades;
    }
  } else {
    sortedGrades = allGrades;
  }

  const ctCardHtml = `
    <section class="card" style="border-left: 4px solid #10b981; margin-bottom:12px">
      <div style="display:flex; align-items:center; justify-content:space-between">
        <h2 style="font-size:1.1rem">🎓 Поступление в ВУЗы: ЦТ и ЦЭ</h2>
        <span class="chip active">11 класс</span>
      </div>
      <p class="muted" style="margin-top:4px">13 345 заданий РИКЗ по спецификации вступительных испытаний:</p>
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-top:10px">
        <button type="button" class="btn secondary small" data-action="start-mode-practice" data-grade="11" data-mode="part_a">
          🔘 Часть А: Тесты (9 631)
        </button>
        <button type="button" class="btn secondary small" data-action="start-mode-practice" data-grade="11" data-mode="part_b">
          ✍️ Часть Б: Открытые (3 714)
        </button>
      </div>
      <button type="button" class="btn block small" data-action="start-exam" style="margin-top:8px; background:linear-gradient(135deg, #10b981, #059669); color:#fff">
        ⏱️ Запустить симулятор ЦТ/ЦЭ (40 вопросов · 180 мин)
      </button>
    </section>
  `;

  const izloCardHtml = `
    <section class="card" style="border-left: 4px solid #f59e0b; margin-bottom:12px">
      <div style="display:flex; align-items:center; justify-content:space-between">
        <h2 style="font-size:1.1rem">📖 Выпускной экзамен: Изложения</h2>
        <span class="chip">9 класс</span>
      </div>
      <p class="muted" style="margin-top:4px">166 официальных текстов НИО для подготовки к экзамену за курс базовой школы:</p>
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px; margin-top:10px">
        <button type="button" class="btn secondary small" data-action="izlo-catalog">
          📖 Каталог текстов
        </button>
        <button type="button" class="btn secondary small" data-action="izlo-random">
          🎲 Случайное изложение
        </button>
      </div>
    </section>
  `;

  return `
    <section class="hero">
      <h1>Учёба</h1>
      <p>Школьная программа по учебнику — отдельно от ЦТ/изложений. Твой класс: ${
        myGrade ? `<strong>${myGrade}</strong>` : 'не выбран'
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
        ? `
           ${myGrade === 9 ? izloCardHtml : ''}
           ${myGrade === 11 ? ctCardHtml : ''}

           <section class="card">
             <h2>🏫 Программа по учебнику</h2>
             <p class="muted" style="margin-bottom:12px">Открой свой класс → тему → учебник / доп. задания / разбор с ИИ.</p>
             <div class="grade-grid">
               ${sortedGrades
                 .map((g) => {
                   const active = myGrade === g.grade;
                   const locked = Boolean(myGrade) && !active;
                   const empty = !g.available;
                   return `
                     <button type="button"
                       class="grade-tile${active ? ' active my-grade' : ''}${empty ? ' empty' : ''}${locked ? ' locked' : ''}"
                       data-action="courses-pick-grade"
                       data-grade="${g.grade}"
                       data-subject="${subject.id}"
                       ${empty ? 'data-empty="1"' : ''}
                       ${locked ? 'data-locked="1"' : ''}>
                       <span class="grade-tile-title">${esc(g.title)}</span>
                       <span class="grade-tile-badge">${active ? '⭐ Твой класс' : (locked ? '🔒 Другой класс' : esc(g.badge || ''))}</span>
                       <span class="muted">${
                         locked
                           ? 'доступен только свой класс'
                           : (g.available
                             ? `${g.tasks} заданий · ${g.topics} тем`
                             : 'нет заданий')
                       }</span>
                       <span class="grade-tile-hint">${active ? esc(g.hint || '') : (locked ? 'Чтобы открыть — смени класс в профиле' : esc(g.hint || ''))}</span>
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
    const flow = state.practiceFlow;
    const flowBlock =
      flow && flow.step === 1
        ? `<section class="card" style="margin-top:12px">
            <h2>Шаг 1 готов ✓</h2>
            <p class="muted">Тема «${esc(flow.topicName || '')}» — учебник пройден. Дальше закрепи в доп. тренажёре.</p>
            ${renderLearningPath(2, { hasExtra: flow.extraCount > 0 })}
            ${
              flow.extraCount > 0 && flow.topicId
                ? `<button class="btn block primary" style="margin-top:12px" data-action="flow-open-extra" data-topic-id="${flow.topicId}">🧩 Шаг 2: доп. тренажёр</button>`
                : `<button class="btn block secondary" style="margin-top:12px" data-action="go-courses">← К программе класса</button>`
            }
          </section>`
        : `<section class="card" style="margin-top:12px">
            <p class="muted">Продолжить по программе — выбери следующую тему в разделе «Учёба».</p>
            <button class="btn block secondary" data-action="go-courses">← К программе</button>
          </section>`;
    return `
      <section class="card">
        <h2>Сессия завершена</h2>
        <p class="ok">Первичный: ${daily.primary_score}/${daily.max_primary}
        ${daily.test_score != null ? ` · тестовый ≈${daily.test_score}` : ''}</p>
        <p class="muted">XP за сессию: ${daily.xp_earned}</p>
        <button class="btn block secondary" data-action="reload-daily">Новая подборка «На сегодня»</button>
        ${
          Number(state.me?.grade) === 9
            ? `<button class="btn block" style="margin-top:8px" data-action="izlo-random">Ещё изложения</button>`
            : ''
        }
      </section>
      ${flowBlock}`;
  }

  const pct =
    daily.tasks_total > 0
      ? Math.round((daily.tasks_completed / daily.tasks_total) * 100)
      : 0;

  const multi = task.answer_format === 'multiple_choice';
  const hasOptImages = (task.options || []).some((o) => o.image_url);
  const options = (task.options || [])
    .map((o, idx) => {
      const selected = state.selected.has(String(o.id));
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
         ${
           state.practiceFlow?.step === 1
             ? `<p class="izlo-badge">📖 Шаг 1 · Учебник${state.practiceFlow.topicName ? ' · ' + esc(state.practiceFlow.topicName) : ''}</p>`
             : task.is_primary || task.image_url
               ? `<p class="izlo-badge">📖 Учебник · ${esc(String(task.grade_level || state.me?.grade || ''))} класс</p>`
               : ''
         }
         ${taskImage}
         ${readingBlock}
         <h2 class="task-question">${esc(task.question)}</h2>
       </div>`;

  const topicMeta = (task.section_name || task.topic_name)
    ? `<div style="background:var(--bg-secondary); padding:8px 12px; border-radius:10px; margin-bottom:10px; font-size:0.83rem; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px;">
         <span>🎒 <strong>${task.grade_level ? task.grade_level + ' кл.' : ''}</strong> ${task.section_name ? '· ' + esc(task.section_name) : ''} · 📌 <strong>${esc(task.topic_name || '')}</strong></span>
         <div style="display:flex; gap:6px; align-items:center;">
           ${task.topic_id ? `<button type="button" class="btn secondary small" style="padding:2px 8px; font-size:0.75rem" data-action="open-extra-topic" data-topic-id="${task.topic_id}">🧩 Шаг 2</button>` : ''}
           ${task.topic_summary ? `<button type="button" class="btn secondary small" style="padding:2px 8px; font-size:0.75rem" data-action="toggle-rule">💡 Правило</button>` : ''}
         </div>
       </div>`
    : '';

  const ruleModalHtml = (task.topic_summary && state.showRuleModal)
    ? `<div class="card" style="border:1px solid var(--accent); margin-bottom:12px; background:var(--card-bg)">
         <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px">
           <strong style="color:var(--accent); font-size:0.95rem">💡 ${esc(task.topic_summary.title || task.topic_name)}</strong>
           <button type="button" class="btn secondary small" data-action="toggle-rule">✕</button>
         </div>
         <p style="font-size:0.88rem; line-height:1.45; white-space:pre-line">${esc(task.topic_summary.content || task.topic_summary.key_points || '')}</p>
       </div>`
    : '';

  return `
    <section class="card">
      ${topicMeta}
      ${ruleModalHtml}
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
      ${
        state.feedback
          ? ''
          : `<button class="btn block" data-action="submit" ${state.loading ? 'disabled' : ''}>Ответить</button>`
      }
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
              ${state.feedback.correct_answer ? `<br><strong>Правильный ответ: ${esc(state.feedback.correct_answer)}</strong>` : ''}
            </p>
            ${
              state.feedback.can_request_ai
                ? (isProUser()
                    ? `<button class="btn block ai-btn-active" data-action="explain" style="margin-top:8px">🤖 Разбор с ИИ</button>`
                    : `<button class="btn block secondary pro-locked-btn" data-action="open-tariffs" style="margin-top:8px; opacity:0.85;">🤖 Разбор с ИИ · по подписке</button>`)
                : ''
            }
            ${
              !state.feedback.is_correct
                ? `<button class="btn block secondary" data-action="retry-task" style="margin-top:8px">🔄 Попробовать ещё раз</button>`
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
  if (state.panel === 'accuracy') return renderAccuracyPanel();

  const dash = state.dashboard;
  const weak = state.stats?.weak_topics || [];
  const sections = dash?.sections || [];
  const activity = dash?.daily_activity || [];
  const maxAct = Math.max(...activity.map((a) => a.total), 1);
  const streak = dash?.streak_days ?? state.stats?.streak_days ?? state.me?.streak_days ?? 0;
  const accuracy = dash?.accuracy_percent ?? 0;

  return `
    <section class="hero">
      <h1>📊 Статистика & Прогресс</h1>
      <p>Твой персональный образовательный дашборд успеваемости</p>
    </section>

    <div class="desktop-home-columns" style="margin-top: 14px;">
      <!-- Левая основная колонка: График активности и Разделы -->
      <div class="desktop-main-col">
        <!-- График активности за 7 дней -->
        <section class="card">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
            <h2 style="margin:0;">📈 Активность за неделю</h2>
            <span class="chip active">7 дней</span>
          </div>
          <p class="muted small">Количество решённых заданий по дням:</p>
          <div style="display:flex;align-items:flex-end;justify-content:space-between;height:120px;margin-top:18px;padding:0 8px;gap:8px">
            ${
              activity.length
                ? activity.map((a) => {
                    const h = Math.round((a.total / maxAct) * 85);
                    return `
                      <div style="display:flex;flex-direction:column;align-items:center;flex:1;height:100%;justify-content:flex-end">
                        <span style="font-size:0.75rem;margin-bottom:4px;color:var(--ink);font-weight:700;">${a.total}</span>
                        <div style="width:100%;max-width:28px;background:var(--accent,#c8ff3d);height:${Math.max(h, 6)}px;border-radius:6px 6px 0 0;opacity:${a.total > 0 ? 1 : 0.25};transition:all 0.2s ease;"></div>
                        <span style="font-size:0.72rem;margin-top:6px;color:var(--muted);">${a.date}</span>
                      </div>`;
                  }).join('')
                : '<p class="muted">Загружаем график активности…</p>'
            }
          </div>
        </section>

        <!-- Прогресс по разделам предмета -->
        ${
          sections.length
            ? `<section class="card" style="margin-top:4px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                  <h2 style="margin:0;">📚 Освоение программы</h2>
                  <span class="chip">${sections.length} разделов</span>
                </div>
                <p class="muted small" style="margin-bottom:14px;">Уровень владения темами школьного курса и ЦТ:</p>
                <div style="display:flex;flex-direction:column;gap:14px;">
                  ${sections.map((s) => `
                    <div>
                      <div style="display:flex;justify-content:space-between;font-size:0.9rem;margin-bottom:6px">
                        <strong>${esc(s.title)}</strong>
                        <span style="color:var(--accent);font-weight:700;">${s.mastery_percent}%</span>
                      </div>
                      <div class="progress" style="height:10px; border-radius:999px;"><i style="width:${s.mastery_percent}%; border-radius:999px;"></i></div>
                    </div>
                  `).join('')}
                </div>
              </section>`
            : ''
        }
      </div>

      <!-- Правая боковая колонка: Карточки метрик и слабые темы -->
      <div class="desktop-side-col">
        <div class="stats-row" style="grid-template-columns: 1fr; gap: 10px;">
          <button type="button" class="stat clickable" data-action="open-streak" style="display:flex; align-items:center; justify-content:space-between; padding:14px 18px;">
            <div style="text-align:left;">
              <span style="display:block; font-size:0.75rem; color:var(--muted);">Ударный режим</span>
              <strong>🔥 ${streak} дн.</strong>
            </div>
            <span style="font-size:0.8rem; color:var(--accent);">Подробнее →</span>
          </button>
          <button type="button" class="stat clickable" data-action="open-accuracy" style="display:flex; align-items:center; justify-content:space-between; padding:14px 18px;">
            <div style="text-align:left;">
              <span style="display:block; font-size:0.75rem; color:var(--muted);">Точность ответов</span>
              <strong>🎯 ${accuracy}%</strong>
            </div>
            <span style="font-size:0.8rem; color:var(--accent);">Аналитика →</span>
          </button>
          <button type="button" class="stat clickable" data-action="open-tariffs" style="display:flex; align-items:center; justify-content:space-between; padding:14px 18px;">
            <div style="text-align:left;">
              <span style="display:block; font-size:0.75rem; color:var(--muted);">Тарифный план</span>
              <strong>💎 ${esc(tariffShortLabel())}</strong>
            </div>
            <span style="font-size:0.8rem; color:var(--accent);">Улучшить →</span>
          </button>
        </div>

        <!-- Слабые темы -->
        <section class="card" style="margin-top:4px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <h2 style="margin:0; font-size:1.05rem;">⚠️ Слабые темы</h2>
            <span class="sidebar-badge" style="background:rgba(239,68,68,0.15); color:#ef4444;">Фокус</span>
          </div>
          <p class="muted small" style="margin-bottom:10px;">Темы, в которых чаще всего допускались ошибки:</p>
          ${
            weak.length
              ? `<ul class="list" style="margin-bottom:12px;">${weak
                  .slice(0, 5)
                  .map(
                    (t) =>
                      `<li style="padding:10px 12px; display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:0.88rem; font-weight:600;">${esc(t.topic_name)}</span>
                        <span class="muted small" style="color:#ef4444; font-weight:700;">${Math.round(t.mastery_score * 100)}% (${t.wrong_count} ош.)</span>
                      </li>`,
                  )
                  .join('')}</ul>
                 <button type="button" class="btn primary block small" data-action="go-practice">
                   ⚡ Закрыть пробелы в тренажёре
                 </button>`
              : `<p class="muted small" style="margin:0;">Отличная работа! Ошибок в текущих темах не зафиксировано.</p>`
          }
        </section>
      </div>
    </div>
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
  return renderProfileAndFamily();
}

function renderRegistration() {
  if (!state.reg) return `<section class="card empty">Готовим регистрацию…</section>`;
  return renderRegForm(state.reg, {
    title: 'Регистрация',
    subtitle: 'По шагам: класс → цель → школа.',
    submitLabel: state.reg.saving ? 'Сохраняем…' : 'Готово, начать',
    profileMode: false,
  });
}

function renderFamily() {
  return renderProfileAndFamily();
}

function renderProfileAndFamily() {
  const pack = state.family;
  const isParent = Boolean((!state.me && pack?.is_parent) || state.me?.is_parent);

  // ЭКРАН ДЛЯ РОДИТЕЛЯ
  if (isParent) {
    if (!pack && state.loading) {
      return `<section class="card empty">Загружаем кабинет родителя…</section>`;
    }
    if (!pack) {
      return `<section class="card empty">
        <p>${esc(state.familyError || 'Не удалось загрузить данные родителя.')}</p>
        <button type="button" class="btn secondary" data-action="family-retry">Попробовать ещё раз</button>
      </section>`;
    }
    const children = pack.children || [];
    const periods = pack.periods || [];

    const kidsBlock =
      children.length === 0
        ? `<p class="muted">У вас пока нет привязанных детей. Введите код от ребёнка ниже.</p>`
        : children
            .map(
              (c) => `
          <div class="child-card">
            <div>
              <strong>${esc(c.display_name)}</strong>
              <span class="muted"> · ${c.grade} кл. · 🔥 ${c.streak_days} дн.</span>
              ${c.city_name ? `<br><span class="muted">${esc(c.city_name)}${c.school_name ? ' · ' + esc(c.school_name) : ''}</span>` : ''}
            </div>
            <button type="button" class="btn secondary sm" data-action="pick-child" data-id="${c.id}">
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
        <p class="muted">Введите код, который отображается в профиле вашего ребёнка.</p>
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
          <p class="muted">Выберите период — готовый отчёт отправится вам прямо в диалог с ботом.</p>
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

  // ЭКРАН ДЛЯ УЧЕНИКА: ПРОФИЛЬ & СЕМЬЯ
  const parents = pack?.parents || [];
  const p1 = parents[0] || null;
  const p2 = parents[1] || null;

  const slot1Html = p1
    ? `
      <div class="parent-slot">
        <div class="parent-slot-info">
          <span class="parent-slot-title">👩 Родитель 1: ${esc(p1.display_name || 'Родитель')}</span>
          <span class="parent-slot-status linked">✓ Привязан(а) · Еженедельные отчёты в бот</span>
        </div>
        <button type="button" class="btn danger sm" data-action="family-student-unlink" data-parent-id="${p1.id}">Отвязать</button>
      </div>`
    : `
      <div class="parent-slot">
        <div class="parent-slot-info">
          <span class="parent-slot-title">👩 Родитель 1 (Мама)</span>
          <span class="parent-slot-status">Пока не привязана</span>
        </div>
        <button type="button" class="btn sm" data-action="family-invite-telegram" data-role="маму">📩 Пригласить</button>
      </div>`;

  const slot2Html = p2
    ? `
      <div class="parent-slot">
        <div class="parent-slot-info">
          <span class="parent-slot-title">👨 Родитель 2: ${esc(p2.display_name || 'Родитель')}</span>
          <span class="parent-slot-status linked">✓ Привязан(а) · Еженедельные отчёты в бот</span>
        </div>
        <button type="button" class="btn danger sm" data-action="family-student-unlink" data-parent-id="${p2.id}">Отвязать</button>
      </div>`
    : `
      <div class="parent-slot">
        <div class="parent-slot-info">
          <span class="parent-slot-title">👨 Родитель 2 (Папа)</span>
          <span class="parent-slot-status">${p1 ? 'Второй родитель пока не привязан' : 'Пока не привязан'}</span>
        </div>
        <button type="button" class="btn sm" data-action="family-invite-telegram" data-role="папу">📩 Пригласить</button>
      </div>`;

  const notifActive = state.me?.notifications_enabled !== false;

  const parentCard = `
    <section class="card" style="margin-bottom:12px">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
        <h2>👨‍👩‍👧 Родительский контроль</h2>
        <span class="chip" style="font-size:0.75rem;padding:4px 10px">${parents.length} / 2</span>
      </div>
      <p class="muted" style="margin:4px 0 10px">Пригласи родителей в Telegram: они смогут следить за твоим прогрессом, серией ударного режима и радоваться твоим успехам.</p>
      ${slot1Html}
      ${slot2Html}
      <p class="muted" style="font-size:0.76rem;margin-top:12px;line-height:1.4">💡 Нажми «Пригласить», чтобы открыть окно Telegram для выбора мамы или папы. Бот сразу отправит персональную ссылку и привяжет родителя в один клик.</p>
    </section>
  `;

  const notifCard = `
    <section class="card" style="margin-bottom:12px">
      <h2>🔔 Уведомления в Telegram</h2>
      <p class="muted">Ежедневный вызов «5 заданий дня» и напоминания об ударном режиме в бот.</p>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-top:10px">
        <span>Напоминания в бот:</span>
        <button type="button" class="btn ${notifActive ? 'success' : 'secondary'} sm" data-action="toggle-notifications">
          ${notifActive ? '🔔 Включены' : '🔕 Отключены'}
        </button>
      </div>
    </section>
  `;

  const isLinked = Boolean(state.me?.is_telegram_linked);
  const tgUser = state.me?.username ? `@${state.me.username}` : (state.me?.telegram?.username ? `@${state.me.telegram.username}` : '');

  const telegramLinkCard = `
    <section class="card" style="margin-bottom:12px; border-left: 4px solid ${isLinked ? '#10b981' : '#3b82f6'}">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
        <h2>✈️ Связь с Telegram</h2>
        <span class="chip ${isLinked ? 'active' : ''}" style="font-size:0.75rem; ${isLinked ? 'background:rgba(16,185,129,0.15);color:#10b981' : 'background:rgba(239,68,68,0.15);color:#ef4444'}">
          ${isLinked ? '✓ Связан' : 'Не привязан'}
        </span>
      </div>
      <p class="muted" style="margin:4px 0 10px; font-size:0.86rem; line-height:1.4">
        ${isLinked
          ? `Ваш аккаунт связан с Telegram <strong>${esc(tgUser || 'ID: ' + state.me.tg_id)}</strong>. Все результаты, баллы и статистика синхронизируются в реальном времени.`
          : 'Свяжите аккаунт с Telegram-ботом, чтобы открывать платформу прямо в мессенджере и получать уведомления о занятиях.'
        }
      </p>
      ${isLinked ? `
        <div style="margin-top:10px">
          <button type="button" class="btn danger sm" data-action="unlink-telegram">Отвязать Telegram</button>
        </div>
      ` : state.tgLinkCode ? `
        <div style="background:rgba(59,130,246,0.08); border:1.5px dashed #3b82f6; border-radius:12px; padding:12px; text-align:center; margin:10px 0">
          <div style="font-size:12px; color:var(--text-muted, #94a3b8); margin-bottom:4px">Одноразовый код привязки (15 минут):</div>
          <div style="font-size:24px; font-weight:800; letter-spacing:2px; color:#38bdf8; margin-bottom:8px">${esc(state.tgLinkCode)}</div>
          <div style="display:flex; gap:8px; justify-content:center; flex-wrap:wrap">
            <a href="${escAttr(state.tgLinkDeeplink || '#')}" target="_blank" class="btn primary sm" style="text-decoration:none">🚀 Открыть бота</a>
            <button type="button" class="btn secondary sm" data-action="copy-tg-code" data-code="${escAttr(state.tgLinkCode)}">📋 Скопировать</button>
          </div>
          <p class="muted" style="font-size:11px; margin:8px 0 0">Или напишите боту в чат: <code>/link ${esc(state.tgLinkCode)}</code></p>
        </div>
      ` : `
        <button type="button" class="btn primary sm" style="margin-top:6px" data-action="request-telegram-link">🔗 Получить код привязки</button>
      `}
    </section>
  `;

  const regFormHtml = state.reg
    ? renderRegForm(state.reg, {
        title: '⚙️ Настройки профиля',
        subtitle: 'Класс обучения, цель, имя, город и школа.',
        submitLabel: state.reg.saving ? 'Сохраняем…' : 'Сохранить изменения',
        profileMode: true,
      })
    : '<section class="card empty">Загружаем настройки…</section>';

  return `
    <section class="hero">
      <h1>⚙️ Профиль и семья</h1>
      <p>Родительский контроль, класс обучения и личные настройки</p>
    </section>
    <div class="profile-bento">
      <div class="profile-col-left">
        ${regFormHtml}
      </div>
      <div class="profile-col-right">
        ${telegramLinkCard}
        ${parentCard}
        ${notifCard}
      </div>
    </div>
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
  const scope = state.ratingScope || 'grade';
  const period = state.ratingPeriod || 'week';
  const myGrade = state.me?.grade ? Number(state.me.grade) : (filters.grade || 1);
  const league = state.rating?.active_league;

  let filterNote = '';
  if (scope === 'grade') {
    filterNote = myGrade ? `🏆 Рейтинг среди учеников ${myGrade} класса` : '🏆 Рейтинг среди учеников твоего класса';
  } else if (scope === 'country') {
    filterNote = '🌍 Общий рейтинг среди всех учеников Беларуси';
  } else if (scope === 'city') {
    filterNote = filters.city_name ? `🏙️ Ученики г. ${esc(filters.city_name)}` : 'Рейтинг твоего города';
  } else if (scope === 'school') {
    filterNote = filters.school_name ? `🏫 Ученики ${esc(filters.school_name)}` : 'Рейтинг твоей школы';
  }

  const leaguePrizesHtml = renderLeaguePrizes(league);

  return `
    <section class="hero">
      <h1>🏆 Зал славы & Рейтинг</h1>
      <p>Таблица лидеров образования Беларуси по заработанному опыту (XP)</p>
    </section>

    <!-- Фильтр периода: Неделя / Месяц / Всё время -->
    <div class="filters" style="margin-bottom:14px;display:flex;gap:8px">
      <button type="button" class="chip${period === 'week' ? ' active' : ''}" data-action="rating-period" data-period="week">⚡ Неделя</button>
      <button type="button" class="chip${period === 'month' ? ' active' : ''}" data-action="rating-period" data-period="month">📅 Месяц</button>
      <button type="button" class="chip${period === 'all' ? ' active' : ''}" data-action="rating-period" data-period="all">🏆 Всё время</button>
    </div>

    <div class="desktop-home-columns">
      <!-- Основная колонка: Список лидеров -->
      <div class="desktop-main-col">
        <section class="card">
          <div class="filters" style="display:flex;gap:6px;flex-wrap:wrap">
            <button type="button" class="chip${scope === 'grade' ? ' active' : ''}" data-action="rating-scope" data-scope="grade">🎒 Мой класс${myGrade ? ` (${myGrade} кл)` : ''}</button>
            <button type="button" class="chip${scope === 'country' ? ' active' : ''}" data-action="rating-scope" data-scope="country">🌍 Вся страна</button>
            <button type="button" class="chip${scope === 'city' ? ' active' : ''}" data-action="rating-scope" data-scope="city" ${filters.has_city ? '' : 'disabled'} title="${filters.has_city ? esc(filters.city_name || '') : 'Город не указан в профиле'}">🏙️ Город</button>
            <button type="button" class="chip${scope === 'school' ? ' active' : ''}" data-action="rating-scope" data-scope="school" ${filters.has_school ? '' : 'disabled'} title="${filters.has_school ? esc(filters.school_name || '') : 'Школа не указана в профиле'}">🏫 Школа</button>
          </div>

          <p class="filter-note" style="margin:14px 0 12px; font-size:0.88rem; color:var(--muted)">${filterNote}</p>

          ${
            entries.length
              ? `<ul class="list">${entries
                  .map(
                    (e, i) => {
                      const rank = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `${i + 1}.`;
                      const scoreVal = period === 'all' ? (e.xp ?? 0) : (e.period_xp ?? e.xp ?? 0);
                      const streakHtml = e.streak_days > 1 ? `<span style="font-size:0.75rem; color:#f59e0b; margin-left:5px" title="Серия дней подряд">🔥 ${e.streak_days}</span>` : '';
                      return `
                        <li class="${e.is_me ? 'me' : ''}" style="display:flex; align-items:center; justify-content:space-between; padding:12px 14px">
                          <div style="display:flex; align-items:center; gap:10px; overflow:hidden">
                            <span style="font-weight:800; min-width:28px; font-size:1.05rem; text-align:center">${rank}</span>
                            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:${e.is_me ? '700' : '600'}; font-size:0.92rem;">
                              ${esc(e.display_name)}${e.is_me ? ' <strong style="color:var(--accent); font-weight:800">(ты)</strong>' : ''}${streakHtml}
                            </span>
                          </div>
                          <span style="font-weight:800; color:var(--accent); flex-shrink:0; margin-left:8px; font-size:0.95rem;">
                            ⚡ ${scoreVal} XP
                          </span>
                        </li>
                      `;
                    }
                  )
                  .join('')}</ul>`
              : `<div class="empty" style="padding:24px 16px; border-radius:12px">
                   <p class="muted">${esc(state.rating?.empty_reason || 'Пока в этом рейтинге нет активных учеников. Реши пару заданий и займи 1-е место!')}</p>
                 </div>`
          }
        </section>
      </div>

      <!-- Боковая колонка: Призы лиги и правила XP -->
      <div class="desktop-side-col">
        ${leaguePrizesHtml}

        <section class="card">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <h3 style="margin:0; font-size:1.05rem;">⚡ Как получать больше XP</h3>
            <span class="chip active">Бонусы</span>
          </div>
          <div style="display:flex; flex-direction:column; gap:8px; font-size:0.86rem; line-height:1.45;">
            <div style="padding:8px 12px; background:rgba(255,255,255,0.03); border-radius:10px; border:1px solid var(--card-border);">
              <strong>+10 XP</strong> за каждое правильно решённое задание
            </div>
            <div style="padding:8px 12px; background:rgba(255,255,255,0.03); border-radius:10px; border:1px solid var(--card-border);">
              <strong>+25 XP</strong> за серию из 5 заданий подряд без ошибок
            </div>
            <div style="padding:8px 12px; background:rgba(255,255,255,0.03); border-radius:10px; border:1px solid var(--card-border);">
              <strong>+50 XP</strong> за закрытие ежедневной цели дня
            </div>
            <div style="padding:8px 12px; background:rgba(255,255,255,0.03); border-radius:10px; border:1px solid var(--card-border);">
              <strong>+100 XP</strong> за прохождение полного варианта ЦТ / ЦЭ
            </div>
          </div>
          <button type="button" class="btn primary block" style="margin-top:14px;" data-action="go-practice">
            🚀 Зарабатывать опыт в тренажёре
          </button>
        </section>
      </div>
    </div>
  `;
}
async function startExamSimulator(variantId = null, year = null) {
  const id = tgId();
  if (!id) return;
  state.loading = true;
  render();
  try {
    const data = await api.startExam(id, { variant_id: variantId, year: year });
    state.exam = {
      session_id: data.session_id,
      title: data.title || (year ? `Симулятор ЦТ/ЦЭ (${year} год)` : 'Симулятор ЦТ/ЦЭ'),
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

async function startTelegramFastLogin(btn) {
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Подготовка…';
  }
  try {
    const res = await api.createTelegramSession();
    state.tgAuthSession = res.session_id;
    state.tgAuthDeeplink = res.deeplink;
    state.tgAuthCommand = res.command;
    state.authError = '';
    render();

    try {
      window.open(res.deeplink, '_blank');
    } catch (_) {}

    if (state.tgAuthTimer) clearInterval(state.tgAuthTimer);
    state.tgAuthTimer = setInterval(async () => {
      if (!state.tgAuthSession) {
        clearInterval(state.tgAuthTimer);
        return;
      }
      try {
        const check = await api.checkTelegramSession(state.tgAuthSession);
        if (check && check.status === 'confirmed' && check.token) {
          clearInterval(state.tgAuthTimer);
          state.tgAuthSession = null;
          state.tgAuthTimer = null;
          localStorage.setItem('tutor_web_token', check.token);
          state.me = check.student;
          state.loading = false;
          document.body.classList.remove('unauthenticated');
          toast('Вход через Telegram успешно выполнен! 🎉');
          await turboBootstrap();
        } else if (check && check.status === 'expired') {
          clearInterval(state.tgAuthTimer);
          state.tgAuthSession = null;
          state.tgAuthTimer = null;
          state.authError = 'Срок действия сессии входа истёк. Попробуйте снова.';
          render();
        }
      } catch (_) {}
    }, 1500);
  } catch (err) {
    state.authError = err.message || 'Ошибка подключения к Telegram';
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Войти через Telegram';
    }
    render();
  }
}

function renderTelegramAuthBlock(isReg = false) {
  if (state.tgAuthSession) {
    return `
      <div style="background:rgba(34,158,217,0.1);border:1.5px dashed #229ED9;border-radius:14px;padding:16px;text-align:center;margin-bottom:20px">
        <div style="font-size:14px;font-weight:700;color:#38bdf8;margin-bottom:6px">⏳ Ожидание подтверждения…</div>
        <p class="muted" style="font-size:12px;margin:0 0 12px;line-height:1.4">
          Мы открыли Telegram-бота. Нажмите <strong>«Запустить»</strong> в боте для мгновенного входа:
        </p>
        <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-bottom:10px">
          <a href="${escAttr(state.tgAuthDeeplink || '#')}" target="_blank" class="btn primary sm" style="background:#229ED9;text-decoration:none">🚀 Открыть Telegram-бота</a>
          <button type="button" class="btn secondary sm" data-action="cancel-tg-auth">Войти по паролю</button>
        </div>
        <p class="muted" style="font-size:11px;margin:0">
          Или отправьте команду боту в чат: <code>${esc(state.tgAuthCommand || '')}</code>
        </p>
      </div>
    `;
  }

  return `
    <button type="button" class="btn block" data-action="telegram-fast-login" style="background:#229ED9;color:#fff;font-weight:700;padding:12px 16px;border-radius:12px;display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:18px;border:none;cursor:pointer;font-size:14.5px;box-shadow:0 4px 14px rgba(34,158,217,0.3);width:100%;box-sizing:border-box">
      <span style="font-size:18px;line-height:1">✈️</span>
      <span>${isReg ? 'Быстрая регистрация через Telegram' : 'Войти через Telegram'}</span>
    </button>

    <div style="display:flex;align-items:center;gap:12px;margin-bottom:18px">
      <div style="flex:1;height:1px;background:rgba(255,255,255,0.1)"></div>
      <span class="muted" style="font-size:12px;font-weight:600">${isReg ? 'или заполните форму' : 'или по логину и паролю'}</span>
      <div style="flex:1;height:1px;background:rgba(255,255,255,0.1)"></div>
    </div>
  `;
}

function renderAuthCard(state) {
  const isReg = state.authTab === 'register';
  return `
    <div class="card auth-card" style="width:100%;max-width:440px;padding:32px 28px;border-radius:20px;box-shadow:0 20px 50px rgba(0,0,0,0.18);border:1px solid rgba(255,255,255,0.08);background:var(--card);box-sizing:border-box">
      <div style="text-align:center;margin-bottom:24px">
        <div style="font-size:42px;margin-bottom:8px">🎓</div>
        <h2 style="font-size:24px;font-weight:800;margin:0 0 6px 0;letter-spacing:-0.5px">Твой Репетитор</h2>
        <p class="muted" style="margin:0;font-size:13.5px;line-height:1.4">
          Единая образовательная платформа: подготовка к ЦТ, ЦЭ и школьная программа Беларуси
        </p>
      </div>

      <div style="display:flex;gap:6px;background:rgba(255,255,255,0.06);padding:5px;border-radius:12px;margin-bottom:22px">
        <button type="button" class="btn ${!isReg ? 'primary' : 'secondary'}" data-action="set-auth-tab" data-tab="login" style="flex:1;border-radius:9px;padding:9px;font-weight:600">Вход</button>
        <button type="button" class="btn ${isReg ? 'primary' : 'secondary'}" data-action="set-auth-tab" data-tab="register" style="flex:1;border-radius:9px;padding:9px;font-weight:600">Регистрация</button>
      </div>

      ${state.authError ? `
        <div class="alert danger" style="margin-bottom:18px;padding:12px 14px;border-radius:10px;font-size:13.5px;line-height:1.4">
          ⚠️ ${esc(state.authError)}
        </div>
      ` : ''}

      ${renderTelegramAuthBlock(isReg)}

      ${isReg ? `
        <form id="auth-register-form">
          <div style="margin-bottom:14px">
            <label style="display:block;font-size:13px;font-weight:600;margin-bottom:5px;color:var(--text-muted, #94a3b8)">Логин</label>
            <input type="text" id="reg-login" required minlength="3" maxlength="50" placeholder="Придумайте логин (например, student2026)" class="input" style="width:100%;box-sizing:border-box;padding:11px 14px;border-radius:10px;font-size:14px" autocomplete="username" />
          </div>

          <div style="margin-bottom:14px">
            <label style="display:block;font-size:13px;font-weight:600;margin-bottom:5px;color:var(--text-muted, #94a3b8)">Пароль</label>
            <input type="password" id="reg-password" required minlength="6" placeholder="Минимум 6 символов" class="input" style="width:100%;box-sizing:border-box;padding:11px 14px;border-radius:10px;font-size:14px" autocomplete="new-password" />
          </div>

          <div style="margin-bottom:14px">
            <label style="display:block;font-size:13px;font-weight:600;margin-bottom:5px;color:var(--text-muted, #94a3b8)">Имя или никнейм</label>
            <input type="text" id="reg-name" required maxlength="100" placeholder="Как вас называть в рейтинге" class="input" style="width:100%;box-sizing:border-box;padding:11px 14px;border-radius:10px;font-size:14px" />
          </div>

          <div style="display:flex;gap:10px;margin-bottom:22px">
            <div style="flex:1">
              <label style="display:block;font-size:13px;font-weight:600;margin-bottom:5px;color:var(--text-muted, #94a3b8)">Класс</label>
              <select id="reg-grade" class="input" style="width:100%;box-sizing:border-box;padding:11px 10px;border-radius:10px;font-size:13.5px">
                <option value="11" selected>11 класс</option>
                <option value="10">10 класс</option>
                <option value="9">9 класс</option>
                <option value="8">8 класс</option>
                <option value="7">7 класс</option>
                <option value="6">6 класс</option>
                <option value="5">5 класс</option>
              </select>
            </div>
            <div style="flex:1.4">
              <label style="display:block;font-size:13px;font-weight:600;margin-bottom:5px;color:var(--text-muted, #94a3b8)">Цель обучения</label>
              <select id="reg-goal" class="input" style="width:100%;box-sizing:border-box;padding:11px 10px;border-radius:10px;font-size:13.5px">
                <option value="ct" selected>Подготовка к ЦТ</option>
                <option value="ce">Подготовка к ЦЭ</option>
                <option value="attestat">Экзамен (9 кл.)</option>
                <option value="improve">Подтянуть предмет</option>
              </select>
            </div>
          </div>

          <button type="submit" class="btn primary block" style="padding:13px;font-size:15px;font-weight:700;border-radius:12px;width:100%">
            Создать аккаунт
          </button>
        </form>
      ` : `
        <form id="auth-login-form">
          <div style="margin-bottom:16px">
            <label style="display:block;font-size:13px;font-weight:600;margin-bottom:6px;color:var(--text-muted, #94a3b8)">Логин</label>
            <input type="text" id="login-username" required placeholder="Введите ваш логин" class="input" style="width:100%;box-sizing:border-box;padding:12px 14px;border-radius:10px;font-size:14px" autocomplete="username" />
          </div>

          <div style="margin-bottom:24px">
            <label style="display:block;font-size:13px;font-weight:600;margin-bottom:6px;color:var(--text-muted, #94a3b8)">Пароль</label>
            <input type="password" id="login-password" required placeholder="Введите пароль" class="input" style="width:100%;box-sizing:border-box;padding:12px 14px;border-radius:10px;font-size:14px" autocomplete="current-password" />
          </div>

          <button type="submit" class="btn primary block" style="padding:13px;font-size:15px;font-weight:700;border-radius:12px;width:100%">
            Войти на платформу
          </button>
        </form>
      `}

      <div style="margin-top:22px;padding-top:16px;border-top:1px solid rgba(255,255,255,0.08);text-align:center">
        <p class="muted" style="font-size:12.5px;margin:0 0 4px 0;font-weight:600;color:var(--text-muted, #94a3b8)">
          🔒 Единый аккаунт для сайта и Telegram
        </p>
        <p class="muted" style="font-size:12px;margin:0;line-height:1.4">
          Вы можете входить любым удобным способом: через Telegram или по логину и паролю. Все задания, статистика и рейтинг сохраняются.
        </p>
      </div>
    </div>
  `;
}

function renderAuthScreen() {
  return renderLandingPresentation(state, renderAuthCard(state));
}

function render() {
  const root = view();
  if (!root) return;

  try {
    const theme = THEMES[getTheme()] || THEMES.vibe;
    const themeLabelEl = document.getElementById('theme-toggle-label');
    if (themeLabelEl) themeLabelEl.textContent = theme.label;
    const myGrade = Number(state.me?.grade) || 0;
    const brandSubEl = document.getElementById('brand-sub');
    if (brandSubEl) {
      if (myGrade > 0 && myGrade <= 9) {
        brandSubEl.textContent = `${myGrade} класс · Школьная программа`;
      } else if (myGrade >= 10) {
        brandSubEl.textContent = 'ЦТ · ЦЭ · Подготовка';
      } else {
        brandSubEl.textContent = theme.sub;
      }
    }

    const isAuth = Boolean(state.me);
    document.body.classList.toggle('unauthenticated', !isAuth);

    const logoutBtn = document.getElementById('sidebar-logout-btn');
    if (logoutBtn) {
      logoutBtn.style.display = isAuth ? 'inline-flex' : 'none';
    }

    // Обновляем состояние полноформатного десктоп-сайдбара
    const sidebarNameEl = document.getElementById('sidebar-user-name');
    if (sidebarNameEl) {
      sidebarNameEl.textContent = state.me?.display_name || (state.loading ? 'Загрузка…' : 'Вход в аккаунт');
    }
    const sidebarGradeEl = document.getElementById('sidebar-user-grade');
    if (sidebarGradeEl) {
      const g = state.me?.grade ? `${state.me.grade} класс` : (state.me ? 'Беларусь' : 'Гость');
      const pro = state.me?.is_pro ? ' · Pro ✅' : '';
      sidebarGradeEl.textContent = `${g}${pro}`;
    }
    const sidebarAvatarEl = document.getElementById('sidebar-user-avatar');
    if (sidebarAvatarEl) {
      sidebarAvatarEl.textContent = state.me?.display_name ? state.me.display_name.charAt(0).toUpperCase() : '👤';
    }

    if (state.loading && !state.me) {
      root.innerHTML = `<div class="card empty" style="max-width:400px;margin:80px auto;text-align:center">Загрузка платформы…</div>`;
      return;
    }

    if (!state.me) {
      root.innerHTML = renderAuthScreen();
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
    else if (state.route === 'exam') root.innerHTML = renderExamSimulator();
    else if (state.route === 'extra-tasks') root.innerHTML = renderExtraTasks();
    else if (state.route === 'practice') root.innerHTML = renderPractice();
    else if (state.route === 'stats') root.innerHTML = renderStats();
    else if (state.route === 'rating') root.innerHTML = renderRating();
    else if (state.route === 'tariffs') root.innerHTML = renderTariffsPage();
    else if (state.route === 'contacts') root.innerHTML = renderContactsPage();
    else if (state.route === 'family' || state.route === 'profile') {
      root.innerHTML = renderProfileAndFamily();
      bindRegInputs();
    } else {
      root.innerHTML = renderHome();
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

    syncTabbar();
  } catch (renderErr) {
    console.error('Critical render error:', renderErr);
    root.innerHTML = `
      <section class="card" style="margin:20px 12px;padding:24px;text-align:center">
        <h2>⚡ Ошибка отображения</h2>
        <p class="muted" style="margin:12px 0 16px">${esc(renderErr?.message || 'Не удалось отрисовать экран')}</p>
        <button type="button" class="btn primary" onclick="location.reload()">🔄 Перезапустить</button>
      </section>
    `;
  }
}

async function submitAnswer() {
  const id = tgId();
  const task = state.daily?.current_task;
  if (!id || !task) return;

  let answer = state.answerText.trim();
  let selectedOptionIds = [];
  if (task.options?.length) {
    selectedOptionIds = [...state.selected]
      .map((x) => Number(x))
      .filter((id) => Number.isInteger(id) && id > 0);
    const selectedOpts = (task.options || []).filter((o) => selectedOptionIds.includes(Number(o.id)));
    answer = selectedOpts.map((o) => o.order || o.text || o.id).join(',');
  }
  if (!answer) {
    toast('Выбери или введи ответ');
    return;
  }

  state.loading = true;
  render();
  try {
    state.feedback = await api.submit(
      id,
      task.session_task_id,
      answer,
      selectedOptionIds,
    );
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

function handleOptionSelect(t) {
  const task = state.daily?.current_task;
  const optId = String(t.dataset.opt || '');
  if (!task || !optId) return;
  if (task.answer_format === 'multiple_choice') {
    if (state.selected.has(optId)) state.selected.delete(optId);
    else state.selected.add(optId);
  } else {
    state.selected = new Set([optId]);
  }
  render();
}

async function handleAction(action, t, e) {
  if (action === 'open-checkout') {
    openCheckoutModal(t.dataset.plan, t.dataset.price, t.dataset.name);
    return;
  }
  if (action === 'close-checkout') {
    closeCheckoutModal();
    return;
  }
  if (action === 'open-legal') {
    openLegalModal(t.dataset.legal);
    return;
  }
  if (action === 'close-legal') {
    closeLegalModal();
    return;
  }
  if (action === 'submit-checkout-step1') {
    const name = document.getElementById('order-name')?.value.trim();
    const email = document.getElementById('order-email')?.value.trim();
    const phone = document.getElementById('order-phone')?.value.trim();
    const terms = document.getElementById('order-terms-chk')?.checked;
    if (!name) { toast('Введите ваше имя'); return; }
    if (!email || !email.includes('@')) { toast('Введите корректный email для чека'); return; }
    if (!phone) { toast('Введите контактный телефон'); return; }
    if (!terms) { toast('Необходимо согласие с условиями оферты'); return; }
    renderCheckoutContent(2);
    return;
  }
  if (action === 'submit-card-pay') {
    const num = document.getElementById('card-num')?.value.trim();
    const exp = document.getElementById('card-exp')?.value.trim();
    const cvc = document.getElementById('card-cvc')?.value.trim();
    if (!num || num.length < 16) { toast('Введите корректный номер карты'); return; }
    if (!exp || exp.length < 4) { toast('Введите срок действия карты'); return; }
    if (!cvc || cvc.length < 3) { toast('Введите CVC / CVV'); return; }
    t.disabled = true;
    t.innerHTML = '⏳ Обработка в ЮKassa…';
    setTimeout(() => {
      if (state.me) state.me.is_pro = true;
      renderCheckoutContent(3);
      toast('🎉 Оплата подтверждена!');
      render();
    }, 1200);
    return;
  }
  if (action === 'finish-checkout') {
    closeCheckoutModal();
    setRoute('home');
    render();
    return;
  }
  if (action === 'set-auth-tab') {
    state.authTab = t.dataset.tab;
    state.authError = '';
    render();
    return;
  }
  if (action === 'telegram-fast-login') {
    await startTelegramFastLogin(t);
    return;
  }
  if (action === 'cancel-tg-auth') {
    if (state.tgAuthTimer) clearInterval(state.tgAuthTimer);
    state.tgAuthSession = null;
    state.tgAuthTimer = null;
    state.authError = '';
    render();
    return;
  }
  if (action === 'landing-nav') {
    const targetId = t.dataset.target;
    const el = document.getElementById(targetId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
    return;
  }
  if (action === 'landing-scroll-top') {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    return;
  }
  if (action === 'landing-go-auth') {
    const tab = t.dataset.tab || 'login';
    state.authTab = tab;
    state.authError = '';
    render();
    const anchor = document.getElementById('auth-section');
    if (anchor) {
      anchor.scrollIntoView({ behavior: 'smooth' });
    }
    return;
  }
  if (action === 'auth-logout') {
    if (confirm('Вы уверены, что хотите выйти из аккаунта?')) {
      try {
        await api.authLogout();
      } catch (_) {}
      if (state.tgAuthTimer) clearInterval(state.tgAuthTimer);
      state.tgAuthSession = null;
      state.tgAuthTimer = null;
      localStorage.removeItem('tutor_web_token');
      localStorage.removeItem('tutor_bootstrap_cache');
      state.me = null;
      state.authTab = 'login';
      state.authError = '';
      document.body.classList.add('unauthenticated');
      render();
      toast('Вы вышли из аккаунта');
    }
    return;
  }
  if (action === 'request-telegram-link') {
    t.disabled = true;
    t.textContent = 'Генерация кода…';
    try {
      const res = await api.issueTelegramLink();
      state.tgLinkCode = res.code;
      state.tgLinkDeeplink = res.deeplink;
      render();
    } catch (e) {
      toast(e.message || 'Ошибка генерации кода');
      t.disabled = false;
      t.textContent = '🔗 Получить код привязки';
    }
    return;
  }
  if (action === 'copy-tg-code') {
    const code = t.dataset.code;
    if (navigator.clipboard) {
      navigator.clipboard.writeText(code);
      toast(`Код ${code} скопирован в буфер!`);
    } else {
      toast(`Код: ${code}`);
    }
    return;
  }
  if (action === 'unlink-telegram') {
    if (confirm('Вы действительно хотите отвязать Telegram от этого аккаунта?')) {
      try {
        await api.unlinkTelegram();
        if (state.me) state.me.is_telegram_linked = false;
        state.tgLinkCode = '';
        toast('Telegram успешно отвязан.');
        render();
      } catch (e) {
        toast(e.message || 'Ошибка при отвязке');
      }
    }
    return;
  }
  if (action === 'dev-login') {
      setDevTgId(t.dataset.tg);
      state.error = '';
      await loadMe();
      await loadForRoute();
      return;
    }
    if (action === 'rating-scope') {
      await loadRating(t.dataset.scope, state.ratingPeriod, state.ratingGrade);
      return;
    }
    if (action === 'rating-period') {
      await loadRating(state.ratingScope, t.dataset.period, state.ratingGrade);
      return;
    }
    if (action === 'rating-grade') {
      const g = Number(t.dataset.grade);
      await loadRating('grade', state.ratingPeriod, g);
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
    if (action === 'go-rating') {
      state.panel = null;
      setRoute('rating');
      return;
    }
    if (action === 'open-tariffs') {
      await openPanel('tariffs');
      return;
    }
    if (action === 'open-accuracy') {
      await openPanel('accuracy');
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
    if (action === 'buy-plan') {
      const planCode = t.dataset.plan || 'pro_1m';
      if (state.loading) return;
      t.disabled = true;
      t.textContent = 'Подготовка счёта…';
      state.loading = true;
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
    if (action === 'go-my-curriculum') {
      const myGrade = state.me?.grade ? Number(state.me.grade) : 1;
      setRoute('courses');
      state.inCoursesCatalog = false;
      state.loading = true;
      render();
      try {
        state.selectedGradeCurriculum = await api.getGradeCurriculum(myGrade, tgId());
      } catch (err) {
        console.error('Ошибка загрузки программы:', err);
      } finally {
        state.loading = false;
        render();
      }
      return;
    }
    if (action === 'open-exam-variants') {
      state.route = 'courses';
      state.inCoursesCatalog = true;
      state.gradeTab = 'exam';
      syncTabbar();
      render();
      await loadCatalog();
      return;
    }
    if (action === 'go-extra-tasks') {
      state.activeExtraTopic = null;
      state.extraTopicsSearch = '';
      state.extraTasksGrade = Number(state.me?.grade) || 1;
      setRoute('extra-tasks');
      return;
    }
    if (action === 'change-extra-grade') {
      const myGrade = Number(state.me?.grade) || 1;
      const asked = Number(t.dataset.grade);
      if (asked !== myGrade) {
        toast(`Доступен только твой класс (${myGrade}). Сменить можно в профиле.`);
        return;
      }
      state.extraTasksGrade = myGrade;
      state.activeExtraTopic = null;
      state.extraTopicsSearch = '';
      await loadForRoute();
      return;
    }
    if (action === 'toggle-topic') {
      const tid = Number(t.dataset.topicId);
      if (!tid) return;
      if (state.expandedTopicIds.has(tid)) state.expandedTopicIds.delete(tid);
      else state.expandedTopicIds.add(tid);
      render();
      return;
    }
    if (action === 'ai-hint-pro') {
      toast('Ответь на задание — кнопка разбора появится после проверки');
      return;
    }
    if (action === 'open-extra-topic') {
      const topicId = Number(t.dataset.topicId || t.dataset.topic);
      const topicName = t.dataset.topicName || state.practiceFlow?.topicName || '';
      state.practiceFlow = {
        step: 2,
        topicId,
        topicName,
        extraCount: state.practiceFlow?.extraCount || 0,
      };
      if (state.route !== 'extra-tasks') {
        state.extraTasksReturnRoute = state.route;
        state.route = 'extra-tasks';
        syncTabbar();
      }
      await openExtraTopic(topicId);
      return;
    }
    if (action === 'back-from-extra-topic') {
      state.activeExtraTopic = null;
      state.extraTaskFeedback = null;
      state.extraTaskSelected = null;
      state.extraTaskText = '';
      if (state.extraTasksReturnRoute) {
        const retRoute = state.extraTasksReturnRoute;
        state.extraTasksReturnRoute = null;
        setRoute(retRoute);
      } else {
        await loadForRoute();
      }
      return;
    }
    if (action === 'select-extra-opt') {
      if (state.extraTaskFeedback || state.extraSubmitting || state._extraAnswerInFlight) return;
      state.extraTaskSelected = t.dataset.opt;
      await submitExtraTaskAnswer({ autoAdvance: true });
      return;
    }
    if (action === 'submit-extra-task') {
      await submitExtraTaskAnswer({ autoAdvance: true });
      return;
    }
    if (action === 'next-extra-task') {
      nextExtraTaskOrFinish();
      return;
    }
    if (action === 'finish-extra-topic') {
      await finishExtraTopic();
      return;
    }
    if (action === 'go-practice') {
      setRoute('practice');
      return;
    }
    if (action === 'start-picture-sequence') {
      state.loading = true;
      render();
      try {
        await ensureCurriculumForPractice();
        const first = nextPictureTopic(null);
        if (!first) {
          toast('Нет тем с карточками');
          return;
        }
        await startPictureTopicPractice(first.id, first.name);
      } catch (err) {
        toast(err.message || 'Не удалось начать');
      } finally {
        state.loading = false;
        render();
      }
      return;
    }
    if (action === 'go-family') setRoute('family');
    if (action === 'go-home') setRoute('home');
    if (action === 'go-profile') setRoute('profile');
    if (action === 'go-courses') setRoute('courses');
    if (action === 'go-rating') setRoute('rating');
    if (action === 'go-stats') setRoute('stats');
    if (action === 'courses-subject') {
      state.coursesSubjectId = Number(t.dataset.id);
      render();
      return;
    }
    if (action === 'toggle-rule') {
      state.showRuleModal = !state.showRuleModal;
      render();
      return;
    }
    if (action === 'set-grade-tab') {
      state.gradeTab = t.dataset.tab;
      render();
      return;
    }
    if (action === 'select-exam-year') {
      state.selectedExamYear = t.dataset.year ? Number(t.dataset.year) : null;
      render();
      return;
    }
    if (action === 'courses-back-to-catalog') {
      state.inCoursesCatalog = true;
      state.selectedGradeCurriculum = null;
      state.selectedExamYear = null;
      render();
      if (!state.catalog) {
        state.loading = true;
        render();
        loadCatalog().finally(() => {
          state.loading = false;
          render();
        });
      }
      return;
    }
    if (action === 'courses-return-to-my-grade') {
      const myGrade = Number(state.me?.grade) || 11;
      state.loading = true;
      state.inCoursesCatalog = false;
      state.selectedExamYear = null;
      render();
      try {
        const id = tgId();
        state.selectedGradeCurriculum = await api.getGradeCurriculum(myGrade, id);
      } catch (err) {
        toast(err.message || 'Не удалось загрузить программу класса');
      } finally {
        state.loading = false;
        render();
      }
      return;
    }
    if (action === 'courses-pick-grade') {
      const grade = Number(t.dataset.grade);
      if (!grade) return;
      const myGrade = Number(state.me?.grade) || null;
      if (myGrade && grade !== myGrade) {
        toast(`Открыт только твой класс (${myGrade}). Другой класс — через смену класса в профиле.`);
        return;
      }
      if (t.dataset.empty === '1') {
        toast('В этом классе пока нет заданий');
        return;
      }
      state.loading = true;
      state.inCoursesCatalog = false;
      state.selectedExamYear = null;
      state.expandedTopicIds = new Set();
      render();
      try {
        const id = tgId();
        state.selectedGradeCurriculum = await api.getGradeCurriculum(grade, id);
      } catch (err) {
        toast(err.message || 'Не удалось загрузить программу класса');
      } finally {
        state.loading = false;
        render();
      }
      return;
    }
    if (action === 'flow-open-extra') {
      const topicId = Number(t.dataset.topicId);
      if (topicId) await openExtraTopic(topicId);
      return;
    }
    if (action === 'start-topic-practice') {
      const topicId = Number(t.dataset.topic);
      const id = tgId();
      if (!id) return;
      const extras = Number(t.dataset.extraCount) || 0;
      state.loading = true;
      render();
      try {
        state.practiceFlow = {
          step: 1,
          topicId,
          topicName: t.dataset.topicName || '',
          extraCount: extras,
        };
        state.daily = await api.startTopicPractice(id, topicId, 'school');
        if (state.daily?.current_task?.options) {
          state.daily.current_task.options = shuffleArray(state.daily.current_task.options);
        }
        state.selected = new Set();
        state.answerText = '';
        state.feedback = null;
        setRoute('practice');
      } catch (err) {
        toast(err.message || 'Не удалось запустить тренировку по теме');
      } finally {
        state.loading = false;
        render();
      }
      return;
    }
    if (action === 'start-grade-mix-practice') {
      const grade = Number(t.dataset.grade);
      const id = tgId();
      if (!id) return;
      const myGrade = Number(state.me?.grade) || null;
      if (myGrade && grade && grade !== myGrade) {
        toast(`Можно решать только задания своего класса (${myGrade}).`);
        return;
      }
      if (isPictureGrade(myGrade || grade)) {
        state.loading = true;
        render();
        try {
          await ensureCurriculumForPractice();
          const first = nextPictureTopic(null);
          if (!first) {
            toast('Нет карточек с картинками');
            return;
          }
          await startPictureTopicPractice(first.id, first.name);
        } catch (err) {
          toast(err.message || 'Не удалось начать');
        } finally {
          state.loading = false;
          render();
        }
        return;
      }
      state.loading = true;
      render();
      try {
        state.daily = await api.startTopicPractice(id, null, 'school', myGrade || grade);
        if (state.daily?.current_task?.options) {
          state.daily.current_task.options = shuffleArray(state.daily.current_task.options);
        }
        state.selected = new Set();
        state.answerText = '';
        state.feedback = null;
        setRoute('practice');
      } catch (err) {
        toast(err.message || 'Не удалось запустить тренировку');
      } finally {
        state.loading = false;
        render();
      }
      return;
    }

    if (action === 'start-mode-practice') {
      const mode = t.dataset.mode;
      const targetGrade = Number(t.dataset.grade) || 11;
      const year = t.dataset.year ? Number(t.dataset.year) : (state.selectedExamYear || null);
      const id = tgId();
      if (!id) return;
      state.loading = true;
      render();
      try {
        state.daily = await api.startTopicPractice(id, null, mode, targetGrade, year);
        if (state.daily?.current_task?.options) {
          state.daily.current_task.options = shuffleArray(state.daily.current_task.options);
        }
        state.selected = new Set();
        state.answerText = '';
        state.feedback = null;
        state.selectedGradeCurriculum = null;
        setRoute('practice');
      } catch (err) {
        toast(err.message || 'Не удалось запустить тренировку');
      } finally {
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
      state.reg.step = state.reg.role ? 2 : 1;
      state.reg.error = '';
      render();
      return;
    }
    if (action === 'reg-back') {
      if (!state.reg) return;
      if (state.reg.step <= 2) {
        state.reg.role = null;
        state.reg.step = 1;
      } else {
        state.reg.step = Math.max(2, Number(state.reg.step) - 1);
      }
      state.reg.error = '';
      render();
      return;
    }
    if (action === 'reg-next') {
      if (!state.reg) return;
      syncRegInputsFromDom();
      const step = Number(state.reg.step) || 2;
      if (step <= 2) {
        if (!state.reg.display_name?.trim()) {
          state.reg.error = 'Укажи имя для рейтинга';
          render();
          return;
        }
        if (!state.reg.grade) {
          state.reg.error = 'Выбери свой класс';
          render();
          return;
        }
        state.reg.step = 3;
        state.reg.error = '';
        render();
        return;
      }
      if (step === 3) {
        if (!state.reg.goal) {
          state.reg.error = 'Выбери цель подготовки';
          render();
          return;
        }
        if (!state.reg.subject_id) {
          state.reg.error = 'Выбери предмет';
          render();
          return;
        }
        state.reg.step = 4;
        state.reg.error = '';
        render();
        return;
      }
      return;
    }
    if (action === 'family-invite-telegram') {
      const role = t.dataset.role || 'родителя';
      const id = tgId();
      if (!id) return;
      let code = state.family?.invite?.code;
      if (!code) {
        try {
          const res = await api.familyInvite(id);
          code = res.code;
          if (state.family) {
            state.family.invite = res;
          }
        } catch (err) {
          console.error('Invite error:', err);
        }
      }
      if (!code) {
        toast('Не удалось получить ссылку приглашения. Попробуй ещё раз.');
        return;
      }
      const botUsername = 'tutor_by_bot';
      const link = `https://t.me/${botUsername}?start=parent_${code}`;
      const text = `Привет! Подключись к моему профилю в «Твой Репетитор», чтобы следить за моими успехами и оценками: ${link}`;
      const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`;

      toast(`Открываем Telegram для выбора ${role}...`);
      if (window.Telegram?.WebApp?.openTelegramLink) {
        window.Telegram.WebApp.openTelegramLink(shareUrl);
      } else {
        window.open(shareUrl, '_blank');
      }
      return;
    }
    if (action === 'family-student-unlink') {
      const parentId = Number(t.dataset.parentId);
      const id = tgId();
      if (!id || !parentId) return;
      if (!confirm('Отвязать этого родителя? Он больше не будет получать отчёты об успеваемости.')) return;
      try {
        await api.familyStudentUnlink(id, parentId);
        toast('Родитель отвязан');
        await loadFamily();
        render();
      } catch (err) {
        toast(err.message || 'Ошибка отвязки родителя');
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
        if (!state.reg.grade) {
          toast('Выбери класс');
          return;
        }
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
        const isProfileEdit =
          state.me?.registered &&
          (state.route === 'profile' || state.route === 'family');
        const data = isProfileEdit
          ? await api.updateProfile(payload)
          : await api.register(payload);
        state.me = { ...state.me, ...data, registered: true };
        state.selectedGradeCurriculum = null;
        state.inCoursesCatalog = false;
        state.ratingGrade = state.me.grade;
        if (isProfileEdit) {
          toast('Настройки сохранены');
          render();
        } else {
          toast('Готово!');
          state.route = 'home';
          document.querySelectorAll('.tab').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.route === 'home');
          });
          await loadForRoute();
        }
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
    if (action === 'retry-task') {
      const task = state.daily?.current_task;
      state.feedback = null;
      state.selected = new Set();
      state.answerText = '';
      if (task?.options?.length) {
        task.options = shuffleArray(task.options);
      }
      render();
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
      const year = t.dataset.year ? Number(t.dataset.year) : (state.selectedExamYear || null);
      state.route = 'exam';
      syncTabbar();
      render();
      await startExamSimulator(null, year);
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
  }

function bindUi() {
  document.addEventListener('click', async (e) => {
    // 1. Theme toggle
    if (e.target.closest('#theme-toggle')) {
      e.preventDefault();
      const next = toggleTheme();
      startAtmosphere(next);
      render();
      toast(THEMES[next]?.toast || `Тема: ${next}`);
      return;
    }

    // 2. Modals backdrop clicks
    if (e.target.id === 'checkout-modal') {
      closeCheckoutModal();
      return;
    }
    if (e.target.id === 'legal-modal') {
      closeLegalModal();
      return;
    }

    // 3. Payment radio option select
    const payOpt = e.target.closest('.pay-method-opt');
    if (payOpt) {
      document.querySelectorAll('.pay-method-opt').forEach((o) => o.classList.remove('selected'));
      payOpt.classList.add('selected');
      const radio = payOpt.querySelector('input[type="radio"]');
      if (radio) radio.checked = true;
      return;
    }

    // 4. Action buttons (FIRST PRIORITY - handles actions everywhere: sidebar, topbar, view, modal)
    const actionEl = e.target.closest('[data-action]');
    if (actionEl) {
      e.preventDefault();
      const action = actionEl.dataset.action;
      await handleAction(action, actionEl, e);
      return;
    }

    // 5. Option buttons in practice tasks
    const optionEl = e.target.closest('.option');
    if (optionEl) {
      e.preventDefault();
      handleOptionSelect(optionEl);
      return;
    }

    // 6. Route navigation (tabs, sidebar buttons, links, cards)
    const routeEl = e.target.closest('[data-route]');
    if (routeEl) {
      e.preventDefault();
      setRoute(routeEl.dataset.route);
      return;
    }
  });

  // Global delegated input listener
  document.addEventListener('input', (e) => {
    if (e.target && e.target.id === 'extra-task-text') {
      state.extraTaskText = e.target.value;
    }
    if (e.target && e.target.id === 'extra-topics-search') {
      state.extraTopicsSearch = e.target.value;
      render();
      const el = document.getElementById('extra-topics-search');
      if (el) {
        el.focus();
        el.selectionStart = el.selectionEnd = el.value.length;
      }
    }
  });

  // Global delegated keydown listener
  document.addEventListener('keydown', async (e) => {
    if (e.target && e.target.id === 'extra-task-text' && e.key === 'Enter') {
      e.preventDefault();
      await submitExtraTaskAnswer();
    }
  });

  // Global delegated submit listener for Web Login and Registration
  document.addEventListener('submit', async (e) => {
    if (e.target && e.target.id === 'auth-login-form') {
      e.preventDefault();
      const login = document.getElementById('login-username')?.value.trim();
      const password = document.getElementById('login-password')?.value.trim();
      if (!login || !password) {
        state.authError = 'Заполните логин и пароль';
        render();
        return;
      }
      state.loading = true;
      state.authError = '';
      render();
      try {
        const res = await api.authLogin({ login, password });
        localStorage.setItem('tutor_web_token', res.token);
        state.me = res.student;
        state.loading = false;
        await turboBootstrap();
      } catch (err) {
        state.loading = false;
        state.authError = err.message || 'Неверный логин или пароль';
        render();
      }
      return;
    }

    if (e.target && e.target.id === 'auth-register-form') {
      e.preventDefault();
      const login = document.getElementById('reg-login')?.value.trim();
      const password = document.getElementById('reg-password')?.value.trim();
      const name = document.getElementById('reg-name')?.value.trim();
      const grade = document.getElementById('reg-grade')?.value;
      const goal = document.getElementById('reg-goal')?.value;

      if (!login || !password || !name) {
        state.authError = 'Пожалуйста, заполните все обязательные поля';
        render();
        return;
      }
      if (password.length < 6) {
        state.authError = 'Пароль должен быть не менее 6 символов';
        render();
        return;
      }

      state.loading = true;
      state.authError = '';
      render();
      try {
        const res = await api.authRegister({
          login,
          password,
          display_name: name,
          grade: Number(grade) || 11,
          goal: goal || 'ct',
        });
        localStorage.setItem('tutor_web_token', res.token);
        state.me = res.student;
        state.loading = false;
        await turboBootstrap();
      } catch (err) {
        state.loading = false;
        state.authError = err.message || 'Ошибка регистрации';
        render();
      }
      return;
    }
  });
}

async function main() {
  try {
    bootTelegram();
    const theme = initTheme();
    startAtmosphere(theme);
    bindUi();

    // 1. INSTANT PAINT: Мгновенное восстановление из LocalStorage до сетевых запросов
    try {
      const cached = localStorage.getItem('tutor_bootstrap_cache');
      if (cached) {
        const data = JSON.parse(cached);
        if (data.me) state.me = data.me;
        if (data.stats) state.stats = data.stats;
        if (data.dashboard) state.dashboard = data.dashboard;
        if (data.daily) state.daily = data.daily;
        render();
        // Моментально скрываем сплэш (через 60мс)
        setTimeout(() => {
          if (typeof window.__TUTOR_HIDE_SPLASH__ === 'function') {
            window.__TUTOR_HIDE_SPLASH__();
          }
        }, 60);
      }
    } catch (_) {}

    // Автопроверка статуса (например, после возврата из оплаты в браузере)
    window.addEventListener('focus', async () => {
      if (state.me && !state.me.is_pro) {
        try {
          const id = tgId();
          if (id) {
            const fresh = await api.me(id);
            if (fresh && fresh.is_pro) {
              state.me = fresh;
              toast('🎉 Подписка успешно активирована!');
              render();
            }
          }
        } catch (_) {}
      }
    });

    await turboBootstrap();
  } catch (err) {
    console.error('App init error:', err);
    state.error = err.message || 'Ошибка запуска приложения';
    render();
  } finally {
    if (typeof window.__TUTOR_HIDE_SPLASH__ === 'function') {
      window.__TUTOR_HIDE_SPLASH__();
    } else {
      const splash = document.getElementById('app-splash');
      if (splash) {
        splash.classList.add('hidden');
        setTimeout(() => splash.remove(), 400);
      }
    }
  }
}

main();
