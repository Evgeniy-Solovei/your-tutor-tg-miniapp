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
  ratingScope: 'grade',
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
  inCoursesCatalog: false,
  selectedGradeCurriculum: null,
  gradeTab: 'school',
  selectedExamYear: null,
  showRuleModal: false,
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

function syncTabbar() {
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
}

function setRoute(route) {
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
    const id = tgId();
    const myGrade = Number(state.me?.grade) || 11;
    if (!state.inCoursesCatalog) {
      if (!state.selectedGradeCurriculum || state.selectedGradeCurriculum.grade !== myGrade) {
        state.loading = true;
        render();
        try {
          state.selectedGradeCurriculum = await api.getGradeCurriculum(myGrade, id);
        } catch (e) {
          toast(e.message || 'Не удалось загрузить программу твоего класса');
        } finally {
          state.loading = false;
          render();
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
    state.loading = true;
    render();
    try {
      state.extraTasksSummary = await api.getExtraTasksSummary(grade, id);
    } catch (e) {
      toast(e.message || 'Ошибка загрузки заданий');
    } finally {
      state.loading = false;
      render();
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
      <p class="muted">Безналичная официальная оплата через ЕРИП и банковские карты Беларуси (bePaid).</p>
      ${isUserPro ? '<div style="margin: 12px 0; padding: 12px; background: rgba(16,185,129,0.15); border: 1px solid #10b981; border-radius: 14px;"><strong>✨ У вас активна Pro-подписка!</strong> Все задания и умные ИИ-разборы открыты.</div>' : ''}
      ${(pack.plans || [])
        .map(
          (p) => {
            const isFree = p.id === 'free';
            const isCurrent = isFree ? !isUserPro : isUserPro;
            return `
        <article class="plan${isCurrent ? ' current' : ''}" style="margin-top:14px; border: 1px solid var(--card-border); border-radius: 16px; padding: 16px; background: var(--card);">
          <div class="plan-top" style="display:flex; justify-content:space-between; align-items:center;">
            <h3 style="margin:0; font-size:1.1rem">${esc(p.name)}</h3>
            <strong style="font-size:1.15rem; color:var(--accent)">${esc(p.price_label)}</strong>
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
                : `<button type="button" class="btn block primary" data-action="buy-plan" data-plan="${esc(p.id)}">💳 Оплатить ${esc(p.price_label)}</button>`
              )
          }
        </article>`;
          }
        )
        .join('')}
    </section>
  `;
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

  return `
    <section class="hero">
      <h1>${vibe ? `Йоу, ${esc(name)}` : `Привет, ${esc(name)}`}</h1>
      <p>${vibe ? 'Давай разберём пару заданий — и погнали дальше.' : 'Продолжим подготовку.'} · ${studentGrade} класс</p>
    </section>
    <div class="stats-row">
      <button type="button" class="stat clickable" data-action="go-rating"><strong>⚡ ${xp}</strong><span>опыт XP</span></button>
      <button type="button" class="stat clickable" data-action="open-streak"><strong>🔥 ${streak}</strong><span>дней подряд</span></button>
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

    <!-- Школьная программа для класса ученика -->
    <section class="card" style="margin-top:12px">
      <h2>📚 Школьная программа · ${studentGrade} класс</h2>
      <p class="muted">Учебные темы, правила и уроки программы ${studentGrade} класса.</p>
      <button class="btn block" data-action="go-my-curriculum">Перейти к программе (${studentGrade} класс)</button>
    </section>

    <!-- Дополнительные задания по темам программы -->
    <section class="card" style="margin-top:12px">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h2>🧩 Дополнительные задания</h2>
        <span class="chip active" style="font-size:0.72rem; padding:2px 8px;">PRO</span>
      </div>
      <p class="muted">Банк иллюстрированных карточек по темам ${studentGrade} класса: закрепляй правила вместе с забавными персонажами!</p>
      ${studentGrade === 1 ? `<div style="font-size:0.85rem; color:var(--accent); font-weight:700; margin:6px 0 10px;">✨ 58 тем · 2 900 заданий с цветными карточками</div>` : ''}
      <button class="btn block secondary" data-action="go-extra-tasks">🧩 Открыть банк доп. заданий (${studentGrade} класс)</button>
    </section>

    ${
      studentGrade === 11
        ? `<section class="card" style="margin-top:12px">
             <h2>🎓 Симулятор ЦТ/ЦЭ</h2>
             <p class="muted">Полноразмерный экзаменационный билет из 40 вопросов с таймером на 180 минут и бланком ответов РИКЗ.</p>
             <button class="btn block secondary" data-action="start-exam">Запустить симулятор (40 вопросов)</button>
           </section>`
        : ''
    }

    ${
      studentGrade === 9
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
      toast('10 бесплатных заданий выполнено! Оформи PRO');
      await openPanel('tariffs');
    } else {
      toast(err.message || 'Не удалось загрузить задания');
    }
  } finally {
    state.loading = false;
    render();
  }
}

async function submitExtraTaskAnswer() {
  if (!state.activeExtraTopic) return;
  const task = state.activeExtraTopic.tasks?.[state.extraTaskIndex];
  if (!task) return;
  const answer = (state.extraTaskSelected || document.getElementById('extra-task-text')?.value || state.extraTaskText || '').trim();
  if (!answer) {
    toast('Выбери или введи ответ');
    return;
  }
  state.loading = true;
  render();
  try {
    const res = await api.submitExtraTask(task.id, answer, tgId());
    state.extraTaskFeedback = res;
    if (res.user_xp !== undefined && state.me) {
      state.me.xp = res.user_xp;
    }
    if (res.free_tasks_left !== undefined && res.free_tasks_left !== null && state.activeExtraTopic) {
      state.activeExtraTopic.free_tasks_left = res.free_tasks_left;
    }
    if (res.free_tasks_left !== undefined && res.free_tasks_left !== null && !res.is_pro) {
      if (res.free_tasks_left === 0) {
        toast(res.is_correct ? `Верно! +${res.xp_earned} XP · Лимит бесплатных заданий исчерпан` : 'Неверно · Лимит бесплатных заданий исчерпан');
      } else {
        toast(res.is_correct ? `Верно! +${res.xp_earned} XP (осталось ${res.free_tasks_left} беспл.)` : `Есть ошибка (осталось ${res.free_tasks_left} беспл.)`);
      }
    } else {
      toast(res.is_correct ? `Верно! +${res.xp_earned} XP` : 'Есть ошибка');
    }
  } catch (err) {
    if (err.status === 403 || err.message?.includes('лимит') || err.message?.includes('подписк')) {
      toast('10 заданий выполнено! Оформи PRO для продолжения.');
      await openPanel('tariffs');
    } else {
      toast(err.message || 'Ошибка отправки ответа');
    }
  } finally {
    state.loading = false;
    render();
  }
}

function nextExtraTask() {
  if (!state.activeExtraTopic) return;
  state.extraTaskIndex += 1;
  state.extraTaskSelected = null;
  state.extraTaskText = '';
  state.extraTaskFeedback = null;
  render();
}

async function finishExtraTopic() {
  state.activeExtraTopic = null;
  state.extraTaskFeedback = null;
  state.extraTaskSelected = null;
  state.extraTaskText = '';
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
  const currentGrade = state.extraTasksGrade || Number(state.me?.grade) || 1;
  const grades = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
  const query = (state.extraTopicsSearch || '').toLowerCase().trim();
  const allTopics = sum?.topics || [];
  const filteredTopics = query
    ? allTopics.filter(t => (t.name && t.name.toLowerCase().includes(query)) || (t.section_name && t.section_name.toLowerCase().includes(query)))
    : allTopics;

  return `
    <section class="card" style="margin-bottom:12px">
      <div class="panel-head">
        <button type="button" class="linkish" data-action="go-home">← Главная</button>
        <h2>🧩 Дополнительные задания</h2>
      </div>
      <p class="muted">Банк сгенерированных заданий по темам программы для углублённого закрепления и проверки знаний.</p>
      
      <!-- Grade selector pills -->
      <div class="grade-pills-row">
        ${grades
          .map(
            (g) => `
          <button type="button" 
                  class="btn ${g === currentGrade ? 'primary' : 'secondary'}" 
                  style="padding:6px 14px; font-size:0.85rem; border-radius:20px; white-space:nowrap; flex-shrink:0;"
                  data-action="change-extra-grade" 
                  data-grade="${g}">
            ${g} класс
          </button>`
          )
          .join('')}
      </div>

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
                <span style="font-size:0.85rem; font-weight:600; color:#f59e0b;">Бесплатные задания</span>
                <span style="font-size:0.85rem; font-weight:700;">${sum.total_completed_all || 0} / ${sum.free_limit || 10}</span>
              </div>
              <div style="height:6px; background:rgba(255,255,255,0.1); border-radius:3px; overflow:hidden; margin-bottom:8px;">
                <div style="height:100%; width:${Math.min(100, (((sum.total_completed_all || 0) / (sum.free_limit || 10)) * 100))}%; background:#f59e0b; border-radius:3px;"></div>
              </div>
              ${(sum.total_completed_all || 0) >= (sum.free_limit || 10) 
                  ? `<button type="button" class="btn block primary" style="padding:8px;" data-action="open-tariffs">⚡ Оформить подписку PRO</button>` 
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
        ? `<section class="card empty">Для ${currentGrade} класса задания сейчас генерируются. Выбери другой класс выше.</section>`
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
      <div class="progress" style="margin:8px 0 14px;"><i style="width:${progressPct}%"></i></div>
      
      <div style="margin-bottom:8px;">
        <span style="font-size:0.75rem; text-transform:uppercase; letter-spacing:0.05em; color:var(--accent);">Тема: ${esc(top.topic_name)}</span>
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
              ${fb.explanation ? `<div style="margin-top:8px; font-size:0.88rem; line-height:1.4; color:var(--fg); opacity:0.9;"><strong>💡 Правило / Пояснение:</strong> ${esc(fb.explanation)}</div>` : ''}
            </div>
            <button type="button" class="btn block primary" style="margin-top:10px;" data-action="next-extra-task">
              ${idx + 1 < total ? 'Следующее задание →' : 'Завершить тему'}
            </button>`
          : `<button type="button" class="btn block primary" data-action="submit-extra-task">Проверить ответ</button>`
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
      const solved = top.solved_count || 0;
      const pct = top.progress_percent !== undefined
        ? top.progress_percent
        : (tasks > 0 ? Math.min(100, Math.round((solved / tasks) * 100)) : 0);

      let progressBorder = 'rgba(255, 255, 255, 0.12)';
      let progressTextColor = 'var(--muted)';
      let progressFill = 'rgba(255, 255, 255, 0.08)';

      if (pct > 0 && pct < 40) {
        progressBorder = 'rgba(245, 158, 11, 0.45)';
        progressTextColor = '#fbbf24';
        progressFill = 'linear-gradient(90deg, #f59e0b, #d97706)';
      } else if (pct >= 40 && pct < 80) {
        progressBorder = 'rgba(99, 102, 241, 0.45)';
        progressTextColor = '#a5b4fc';
        progressFill = 'linear-gradient(90deg, #6366f1, #3b82f6)';
      } else if (pct >= 80) {
        progressBorder = 'rgba(16, 185, 129, 0.5)';
        progressTextColor = '#6ee7b7';
        progressFill = 'linear-gradient(90deg, #10b981, #059669)';
      }

      return `
        <div class="curriculum-topic-card" style="background:var(--bg-secondary); border-radius:14px; padding:12px; margin-bottom:10px; border:1px solid var(--card-border)">
          <div style="display:flex; align-items:center; justify-content:space-between; gap:8px">
            <strong style="font-size:0.95rem; line-height:1.3">📌 ${esc(top.name)}</strong>
            ${tasks > 0 ? `
              <div class="topic-progress-badge" title="Решено ${solved} из ${tasks} заданий" style="
                border: 1px solid ${progressBorder};
              ">
                <div class="topic-progress-fill" style="
                  position: absolute;
                  left: 0;
                  top: 0;
                  bottom: 0;
                  width: ${pct}%;
                  background: ${progressFill};
                  opacity: 0.38;
                  transition: width 0.3s ease;
                "></div>
                <span style="position: relative; z-index: 1; font-size: 0.74rem; font-weight: 700; color: ${progressTextColor}">
                  ${pct === 100 ? '✅ ' : ''}${pct}% · ${solved}/${tasks} зад.
                </span>
              </div>
            ` : `
              <span class="chip" style="font-size:0.75rem; opacity:0.6; flex-shrink:0">скоро</span>
            `}
          </div>
          ${tasks > 0 ? `
            <div style="margin-top:8px; height:4px; border-radius:2px; background:rgba(255,255,255,0.06); overflow:hidden">
              <div style="height:100%; width:${pct}%; background:${progressFill}; transition:width 0.3s ease"></div>
            </div>
          ` : ''}
          ${top.has_summary && top.summary_key_points ? `
            <div style="font-size:0.82rem; color:var(--muted); margin-top:6px">
              💡 <strong>Правило:</strong> ${esc(top.summary_key_points.slice(0, 110))}${top.summary_key_points.length > 110 ? '…' : ''}
            </div>
          ` : ''}
          <div style="margin-top:10px; display:flex; flex-direction:column; gap:6px;">
            ${tasks > 0 ? `
              <button type="button" class="btn block secondary small"
                data-action="start-topic-practice"
                data-topic="${top.id}"
                data-grade="${cur.grade}">
                ⚡ Тренировать тему учебника (${tasks} зад.)
              </button>
            ` : `
              <button type="button" class="btn block secondary small" disabled style="opacity:0.6">Материалы пополняются</button>
            `}
            ${top.extra_task_count > 0 ? `
              <button type="button" class="btn block small" style="background:rgba(200, 255, 61, 0.12); color:#c8ff3d; border:1px solid rgba(200, 255, 61, 0.35); font-weight:600;"
                data-action="open-extra-topic"
                data-topic-id="${top.id}">
                🧩 Доп. задания по теме (${top.extra_task_count} с картинками)
              </button>
            ` : ''}
          </div>
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
    contentHtml = `
      <section class="card" style="margin-bottom:12px">
        <button type="button" class="btn block primary" data-action="start-grade-mix-practice" data-grade="${cur.grade}">
          🎯 Тренировать ${cur.grade} класс (${cur.school_tasks_count || cur.total_tasks} заданий · микс тем учебника)
        </button>
        ${(cur.total_extra_tasks || 0) > 0 ? `
          <button type="button" class="btn block secondary" style="margin-top:8px; border-color:rgba(200, 255, 61, 0.4); color:var(--accent); font-weight:600;" data-action="go-extra-tasks">
            🧩 Банк доп. заданий (${cur.total_extra_tasks} с картинками)
          </button>
        ` : ''}
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
      <p class="muted">${cur.total_topics} тем · ${cur.total_tasks} заданий в базе</p>
    </section>

    ${tabSwitcherHtml}
    ${contentHtml}
  `;
}

function renderCourses() {
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
      <h1>Курсы и экзамены</h1>
      <p>Выбирай класс школьной программы или направления подготовки к экзаменам. Сейчас у тебя: ${
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
        ? `
           ${myGrade === 9 ? (izloCardHtml + ctCardHtml) : (ctCardHtml + izloCardHtml)}

           <section class="card">
             <h2>🏫 Школьная программа по классам</h2>
             <p class="muted" style="margin-bottom:12px">Выбери класс для изучения тем учебника и прохождения заданий:</p>
             <div class="grade-grid">
               ${sortedGrades
                 .map((g) => {
                   const active = myGrade === g.grade;
                   const empty = !g.available;
                   return `
                     <button type="button"
                       class="grade-tile${active ? ' active my-grade' : ''}${empty ? ' empty' : ''}"
                       data-action="courses-pick-grade"
                       data-grade="${g.grade}"
                       data-subject="${subject.id}"
                       ${empty ? 'data-empty="1"' : ''}>
                       <span class="grade-tile-title">${esc(g.title)}</span>
                       <span class="grade-tile-badge">${active ? '⭐ Твой класс' : esc(g.badge || '')}</span>
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
      </section>
      <section class="card" style="margin-top:12px">
        <h2>🧩 Дополнительные задания</h2>
        <p class="muted">Хочешь продолжить практику? Проходи красочные карточки по темам школьной программы!</p>
        <button class="btn block" style="background:#c8ff3d; color:#121212; font-weight:700" data-action="go-extra-tasks">
          🧩 Решать доп. задания
        </button>
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
         ${task.is_primary || task.image_url ? `<p class="izlo-badge">Картинка · ${esc(String(state.me?.grade || ''))} класс</p>` : ''}
         ${taskImage}
         ${readingBlock}
         <h2 class="task-question">${esc(task.question)}</h2>
       </div>`;

  const topicMeta = (task.section_name || task.topic_name)
    ? `<div style="background:var(--bg-secondary); padding:8px 12px; border-radius:10px; margin-bottom:10px; font-size:0.83rem; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px;">
         <span>🎒 <strong>${task.grade_level ? task.grade_level + ' кл.' : ''}</strong> ${task.section_name ? '· ' + esc(task.section_name) : ''} · 📌 <strong>${esc(task.topic_name || '')}</strong></span>
         <div style="display:flex; gap:6px; align-items:center;">
           ${task.topic_id ? `<button type="button" class="btn secondary small" style="padding:2px 8px; font-size:0.75rem; border-color:rgba(200,255,61,0.4); color:var(--accent);" data-action="open-extra-topic" data-topic-id="${task.topic_id}">🧩 Доп. задания</button>` : ''}
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
                ? (state.me?.is_pro
                    ? `<button class="btn block secondary" data-action="explain" style="margin-top:8px">🤖 Разбор с ИИ</button>`
                    : `<button class="btn block secondary pro-locked-btn" data-action="open-tariffs" style="margin-top:8px; opacity:0.65;">🤖 Разбор с ИИ 🔒 (В тарифе Pro)</button>`)
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
      <h1>Статистика & Прогресс</h1>
      <p>Твой личный дашборд успеваемости</p>
    </section>
    <div class="stats-row">
      <button type="button" class="stat clickable" data-action="open-streak">
        <strong>🔥 ${streak} дн.</strong>
        <span>ударный режим</span>
      </button>
      <button type="button" class="stat clickable" data-action="open-accuracy">
        <strong>${accuracy}%</strong>
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
  return renderProfileAndFamily();
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
  return renderProfileAndFamily();
}

function renderProfileAndFamily() {
  const pack = state.family;
  const isParent = Boolean(pack?.is_parent || (state.me && state.me.is_parent));

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

  const regFormHtml = state.reg
    ? renderRegForm(state.reg, {
        title: '⚙️ Настройки профиля',
        subtitle: 'Класс обучения, цель, имя, город и школа.',
        submitLabel: state.reg.saving ? 'Сохраняем…' : 'Сохранить изменения',
      })
    : '<section class="card empty">Загружаем настройки…</section>';

  return `
    <section class="hero">
      <h1>⚙️ Профиль и семья</h1>
      <p>Родительский контроль, класс обучения и личные настройки</p>
    </section>
    ${parentCard}
    ${notifCard}
    ${regFormHtml}
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

  return `
    <section class="hero">
      <h1>🏆 Рейтинг</h1>
      <p>Таблица лидеров по заработанному опыту (XP)</p>
    </section>

    <!-- Фильтр периода: Неделя / Месяц / Всё время -->
    <div class="filters" style="margin-bottom:12px;display:flex;gap:6px">
      <button type="button" class="chip${period === 'week' ? ' active' : ''}" data-action="rating-period" data-period="week">⚡ Неделя</button>
      <button type="button" class="chip${period === 'month' ? ' active' : ''}" data-action="rating-period" data-period="month">📅 Месяц</button>
      <button type="button" class="chip${period === 'all' ? ' active' : ''}" data-action="rating-period" data-period="all">🏆 Всё время</button>
    </div>

    ${renderLeaguePrizes(league)}

    <section class="card">
      <div class="filters" style="display:flex;gap:6px;flex-wrap:wrap">
        <button type="button" class="chip${scope === 'grade' ? ' active' : ''}" data-action="rating-scope" data-scope="grade">🎒 Мой класс${myGrade ? ` (${myGrade} кл)` : ''}</button>
        <button type="button" class="chip${scope === 'country' ? ' active' : ''}" data-action="rating-scope" data-scope="country">🌍 Вся страна</button>
        <button type="button" class="chip${scope === 'city' ? ' active' : ''}" data-action="rating-scope" data-scope="city" ${filters.has_city ? '' : 'disabled'} title="${filters.has_city ? esc(filters.city_name || '') : 'Город не указан в профиле'}">🏙️ Город</button>
        <button type="button" class="chip${scope === 'school' ? ' active' : ''}" data-action="rating-scope" data-scope="school" ${filters.has_school ? '' : 'disabled'} title="${filters.has_school ? esc(filters.school_name || '') : 'Школа не указана в профиле'}">🏫 Школа</button>
      </div>

      <p class="filter-note" style="margin:12px 0 10px; font-size:0.86rem; color:var(--muted)">${filterNote}</p>

      ${
        entries.length
          ? `<ul class="list">${entries
              .map(
                (e, i) => {
                  const rank = i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `${i + 1}.`;
                  const scoreVal = period === 'all' ? (e.xp ?? 0) : (e.period_xp ?? e.xp ?? 0);
                  const streakHtml = e.streak_days > 1 ? `<span style="font-size:0.75rem; color:#f59e0b; margin-left:5px" title="Серия дней подряд">🔥 ${e.streak_days}</span>` : '';
                  return `
                    <li class="${e.is_me ? 'me' : ''}" style="display:flex; align-items:center; justify-content:space-between; padding:10px 12px">
                      <div style="display:flex; align-items:center; gap:8px; overflow:hidden">
                        <span style="font-weight:700; min-width:24px; text-align:center">${rank}</span>
                        <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-weight:${e.is_me ? '700' : '500'}">
                          ${esc(e.display_name)}${e.is_me ? ' <strong style="color:var(--accent); font-weight:700">(ты)</strong>' : ''}${streakHtml}
                        </span>
                      </div>
                      <span style="font-weight:700; color:var(--accent); flex-shrink:0; margin-left:8px">
                        ⚡ ${scoreVal} XP
                      </span>
                    </li>
                  `;
                }
              )
              .join('')}</ul>`
          : `<div class="empty" style="padding:20px 12px; border-radius:10px">
               <p class="muted">${esc(state.rating?.empty_reason || 'Пока в этом рейтинге нет активных учеников. Реши пару заданий и займи 1-е место!')}</p>
             </div>`
      }
    </section>
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

function render() {
  const root = view();
  if (!root) return;

  const theme = THEMES[getTheme()];
  document.getElementById('theme-toggle-label').textContent = theme.nextLabel;
  const myGrade = Number(state.me?.grade) || 0;
  if (myGrade > 0 && myGrade <= 9) {
    document.getElementById('brand-sub').textContent = `${myGrade} класс · Школьная программа`;
  } else if (myGrade >= 10) {
    document.getElementById('brand-sub').textContent = 'ЦТ · ЦЭ · Подготовка';
  } else {
    document.getElementById('brand-sub').textContent = theme.sub;
  }

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
  else if (state.route === 'extra-tasks') root.innerHTML = renderExtraTasks();
  else if (state.route === 'practice') root.innerHTML = renderPractice();
  else if (state.route === 'stats') root.innerHTML = renderStats();
  else if (state.route === 'rating') root.innerHTML = renderRating();
  else if (state.route === 'family' || state.route === 'profile') {
    root.innerHTML = renderProfileAndFamily();
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

  syncTabbar();
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
      const optId = String(t.dataset.opt || '');
      if (!task || !optId) return;
      if (task.answer_format === 'multiple_choice') {
        if (state.selected.has(optId)) state.selected.delete(optId);
        else state.selected.add(optId);
      } else {
        state.selected = new Set([optId]);
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
    if (action === 'open-streak' || action === 'go-rating') {
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
    if (action === 'go-extra-tasks') {
      state.activeExtraTopic = null;
      state.extraTopicsSearch = '';
      state.extraTasksGrade = Number(state.me?.grade) || 1;
      setRoute('extra-tasks');
      return;
    }
    if (action === 'change-extra-grade') {
      state.extraTasksGrade = Number(t.dataset.grade);
      state.activeExtraTopic = null;
      state.extraTopicsSearch = '';
      await loadForRoute();
      return;
    }
    if (action === 'open-extra-topic') {
      const topicId = Number(t.dataset.topicId || t.dataset.topic);
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
      state.extraTaskSelected = t.dataset.opt;
      render();
      return;
    }
    if (action === 'submit-extra-task') {
      await submitExtraTaskAnswer();
      return;
    }
    if (action === 'next-extra-task') {
      if (state.extraTaskIndex + 1 < (state.activeExtraTopic?.tasks?.length || 0)) {
        nextExtraTask();
      } else {
        await finishExtraTopic();
      }
      return;
    }
    if (action === 'finish-extra-topic') {
      await finishExtraTopic();
      return;
    }
    if (action === 'go-practice') setRoute('practice');
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
      state.loading = true;
      state.inCoursesCatalog = false;
      state.selectedExamYear = null;
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
    if (action === 'start-topic-practice') {
      const topicId = Number(t.dataset.topic);
      const id = tgId();
      if (!id) return;
      state.loading = true;
      render();
      try {
        state.daily = await api.startTopicPractice(id, topicId);
        if (state.daily?.current_task?.options) {
          state.daily.current_task.options = shuffleArray(state.daily.current_task.options);
        }
        state.selected = new Set();
        state.answerText = '';
        state.feedback = null;
        state.selectedGradeCurriculum = null;
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
      state.loading = true;
      render();
      try {
        state.daily = await api.startTopicPractice(id, null, 'school', grade);
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

    if (action === 'start-mode-practice') {
      const mode = t.dataset.mode;
      const grade = Number(t.dataset.grade);
      const year = t.dataset.year ? Number(t.dataset.year) : (state.selectedExamYear || null);
      const id = tgId();
      if (!id) return;
      state.loading = true;
      render();
      try {
        state.daily = await api.startTopicPractice(id, null, mode, grade, year);
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
      render();
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
  });

  const viewEl = view();
  viewEl?.addEventListener('input', (e) => {
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

  viewEl?.addEventListener('keydown', async (e) => {
    if (e.target && e.target.id === 'extra-task-text' && e.key === 'Enter') {
      e.preventDefault();
      await submitExtraTaskAnswer();
    }
  });
}

async function main() {
  try {
    bootTelegram();
    const theme = initTheme();
    startAtmosphere(theme);
    bindUi();

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

    await loadMe();
    await loadForRoute();
  } catch (err) {
    console.error('App init error:', err);
    state.error = err.message || 'Ошибка запуска приложения';
    render();
  } finally {
    const splash = document.getElementById('app-splash');
    if (splash) {
      splash.classList.add('hidden');
      setTimeout(() => splash.remove(), 400);
    }
  }
}

main();
