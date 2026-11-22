/**
 * Стартовая страница-презентация образовательной платформы «Твой Репетитор».
 * Презентация для новых посетителей: почему платформа эффективна,
 * что она даёт школьнику и родителям, интерактивная демонстрация и форма входа.
 */

import { REQUISITES } from './legal.js';

function esc(s) {
  return String(s ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

export function renderLandingPresentation(state, authBlockHtml) {
  return `
    <div class="landing-page">
      <!-- Навигационная шапка лендинга -->
      <header class="landing-header">
        <div class="landing-header-inner">
          <div class="brand" data-action="landing-scroll-top" style="cursor:pointer; display:flex; align-items:center; gap:10px">
            <span class="brand-mark" style="font-size:24px">⚡</span>
            <div>
              <div style="font-weight:800; font-size:1.1rem; line-height:1.2; letter-spacing:-0.02em">Твой Репетитор</div>
              <div style="font-size:0.75rem; color:var(--muted)">🇧🇾 Беларусь · ЦТ / ЦЭ / 1–11 кл.</div>
            </div>
          </div>

          <nav class="landing-nav-links">
            <a class="landing-nav-link" data-action="landing-nav" data-target="benefits">Что даст ребёнку</a>
            <a class="landing-nav-link" data-action="landing-nav" data-target="exam-sim">Тренажёр ЦТ / ЦЭ</a>
            <a class="landing-nav-link" data-action="landing-nav" data-target="for-parents">Родителям</a>
            <a class="landing-nav-link" data-action="landing-nav" data-target="how-it-works">Как работает</a>
            <a class="landing-nav-link" data-action="landing-nav" data-target="tariffs-section">Тарифы</a>
          </nav>

          <div class="landing-header-actions">
            <button type="button" class="btn secondary sm" data-action="landing-go-auth" data-tab="login" style="border-radius:10px; font-weight:600">
              Войти
            </button>
            <button type="button" class="btn primary sm" data-action="landing-go-auth" data-tab="register" style="border-radius:10px; font-weight:700">
              Начать бесплатно
            </button>
          </div>
        </div>
      </header>

      <!-- Главный экран (Hero Section) -->
      <section class="landing-hero landing-container">
        <div class="landing-pill">
          <span>🇧🇾</span>
          <span>Образовательная онлайн-платформа №1 в Беларуси</span>
        </div>

        <h1 class="landing-hero-title">
          Умная подготовка к ЦТ, ЦЭ и урокам для вашего ребёнка
        </h1>

        <p class="landing-hero-sub">
          13 000+ заданий по программе Министерства образования РБ, официальная шкала пересчёта РИКЗ, пошаговый разбор ошибок с персональным ИИ-репетитором и регулярный контроль успеваемости в Telegram.
        </p>

        <div class="landing-hero-cta">
          <button type="button" class="btn primary lg" data-action="landing-go-auth" data-tab="register" style="padding:15px 32px; font-size:1.08rem; font-weight:800; border-radius:14px; box-shadow:0 8px 24px rgba(200,255,61,0.25)">
            🚀 Начать учиться бесплатно
          </button>
          <button type="button" class="btn lg" data-action="telegram-fast-login" style="background:#229ED9; color:#fff; padding:15px 28px; font-size:1.05rem; font-weight:700; border-radius:14px; border:none; display:flex; align-items:center; gap:10px; box-shadow:0 8px 24px rgba(34,158,217,0.3)">
            <span style="font-size:20px; line-height:1">✈️</span>
            <span>Войти через Telegram в 1 клик</span>
          </button>
        </div>

        <!-- Доказательные метрики платформы -->
        <div class="landing-metrics-grid">
          <div class="landing-metric-card">
            <div class="landing-metric-val">13 300+</div>
            <div class="landing-metric-label">актуальных заданий РБ: Часть А (тесты) и Часть Б (открытые)</div>
          </div>
          <div class="landing-metric-card">
            <div class="landing-metric-val">100 баллов</div>
            <div class="landing-metric-label">официальная шкала РИКЗ с точным расчётом первичного балла</div>
          </div>
          <div class="landing-metric-card">
            <div class="landing-metric-val">24 / 7</div>
            <div class="landing-metric-label">персональный ИИ-разбор каждого правила простыми словами</div>
          </div>
          <div class="landing-metric-card">
            <div class="landing-metric-val">10–15 мин</div>
            <div class="landing-metric-label">в день для стабильного прогресса и высоких школьных отметок</div>
          </div>
        </div>
      </section>

      <!-- Интерактивная демонстрация (Visual Showcase) -->
      <section class="landing-container" style="margin-bottom:70px">
        <div class="card" style="padding:32px; border-radius:24px; border:1px solid rgba(200,255,61,0.3); background:radial-gradient(circle at 10% 20%, rgba(200,255,61,0.06), transparent 50%), var(--card)">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:10px">
            <div style="display:flex; align-items:center; gap:10px">
              <span class="badge" style="background:rgba(200,255,61,0.15); color:var(--accent); font-weight:700">11 класс · ЦТ / ЦЭ</span>
              <span style="font-size:0.85rem; color:var(--muted)">Русский язык · Орфография</span>
            </div>
            <div style="display:flex; align-items:center; gap:14px; font-size:0.88rem; font-weight:700">
              <span style="color:#f59e0b">🔥 4 дня серии</span>
              <span style="color:#10b981">⚡ +15 XP</span>
            </div>
          </div>

          <div style="font-size:1.15rem; font-weight:700; margin-bottom:16px; line-height:1.4">
            Укажите номера слов, в которых на месте пропуска пишется буква <u>И</u>:
          </div>

          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:10px; margin-bottom:20px">
            <div style="padding:12px 16px; border-radius:12px; background:rgba(255,255,255,0.04); border:1px solid var(--card-border); font-size:0.95rem">
              1) прик..саться
            </div>
            <div style="padding:12px 16px; border-radius:12px; background:rgba(16,185,129,0.15); border:1px solid #10b981; color:#34d399; font-weight:700; font-size:0.95rem; display:flex; justify-content:space-between">
              <span>2) ц..стерна (И)</span> <span>✓</span>
            </div>
            <div style="padding:12px 16px; border-radius:12px; background:rgba(16,185,129,0.15); border:1px solid #10b981; color:#34d399; font-weight:700; font-size:0.95rem; display:flex; justify-content:space-between">
              <span>3) заст..лать (И)</span> <span>✓</span>
            </div>
            <div style="padding:12px 16px; border-radius:12px; background:rgba(255,255,255,0.04); border:1px solid var(--card-border); font-size:0.95rem">
              4) пр..ветливый
            </div>
          </div>

          <!-- Блок ИИ-разбора -->
          <div style="background:rgba(56,189,248,0.08); border-left:4px solid #38bdf8; border-radius:12px; padding:16px 20px">
            <div style="display:flex; align-items:center; gap:8px; font-weight:700; color:#38bdf8; font-size:0.95rem; margin-bottom:6px">
              <span>🤖 Умный ИИ-разбор:</span>
            </div>
            <p style="margin:0; font-size:0.9rem; line-height:1.55; color:var(--ink)">
              <strong>Правило:</strong> В слове <em>«застилать»</em> пишется <strong>И</strong>, так как за корнем следует суффикс <em>-А-</em> (правило корней с чередованием <em>-стел- / -стил-</em>). В слове <em>«цистерна»</em> пишется <strong>И</strong>, так как это корень нерусского происхождения (исключения: цыган, цыпочки, цыплёнок, цыкнуть, цыц).
            </p>
          </div>
        </div>
      </section>

      <!-- Секция: Что платформа даст вашему ребёнку -->
      <section id="benefits" class="landing-section">
        <div class="landing-container">
          <div class="landing-section-header">
            <span class="landing-section-tag">Преимущества для ученика</span>
            <h2 class="landing-section-title">Что получит ваш ребёнок?</h2>
            <p class="landing-section-desc">
              Система построена так, чтобы ребёнок понимал логику предмета, а не бездумно заучивал тесты.
            </p>
          </div>

          <div class="landing-benefits-grid">
            <div class="landing-benefit-card">
              <div>
                <span class="landing-benefit-icon">🎯</span>
                <h3 class="landing-benefit-title">Максимальный балл на ЦТ и ЦЭ</h3>
                <p class="landing-benefit-text">
                  Настоящие бланки ответов РИКЗ, Часть А и Часть Б, таймер 180 минут и официальный алгоритм пересчёта первичных баллов в 100-балльный результат.
                </p>
              </div>
              <ul class="landing-benefit-list">
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Тестирование без страха перед бланками</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Реальные тренировочные варианты прошлых лет</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Наглядный график роста тестового балла</span></li>
              </ul>
            </div>

            <div class="landing-benefit-card">
              <div>
                <span class="landing-benefit-icon">📚</span>
                <h3 class="landing-benefit-title">Высокие оценки в школе 1–11 кл.</h3>
                <p class="landing-benefit-text">
                  Полная школьная программа Беларуси: от базового правописания до синтаксиса и пунктуации. Помогает закрыть пробелы и стабильно получать девятки и десятки.
                </p>
              </div>
              <ul class="landing-benefit-list">
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Строго по государственным учебникам РБ</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Подготовка к контрольным и экзамену за 9 класс</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Каталог изложений с аудиоозвучкой</span></li>
              </ul>
            </div>

            <div class="landing-benefit-card">
              <div>
                <span class="landing-benefit-icon">🤖</span>
                <h3 class="landing-benefit-title">Персональный ИИ-репетитор 24/7</h3>
                <p class="landing-benefit-text">
                  Никаких готовых ответов — ИИ раскладывает правило по полочкам, объясняет логику ошибки и моментально подбирает упражнения для закрепления.
                </p>
              </div>
              <ul class="landing-benefit-list">
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Мгновенный ответ без очередей</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Выявление слабых тем в автоматическом режиме</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Экономия сотен рублей на почасовых репетиторах</span></li>
              </ul>
            </div>

            <div class="landing-benefit-card">
              <div>
                <span class="landing-benefit-icon">🏆</span>
                <h3 class="landing-benefit-title">Привычка учиться с интересом</h3>
                <p class="landing-benefit-text">
                  Геймификация и Ударный режим: ежедневные серии, уровни, достижения и Зал Славы мотивируют заниматься каждый день по 10–15 минут без ссор.
                </p>
              </div>
              <ul class="landing-benefit-list">
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Серия «Огонька» дисциплинирует каждый день</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Здоровый соревновательный дух в рейтинге школ</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Понятный путь к поступлению на бюджет</span></li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <!-- Секция: Для родителей -->
      <section id="for-parents" class="landing-section">
        <div class="landing-container">
          <div class="landing-parents-row">
            <div>
              <span class="landing-section-tag">Кабинет семьи</span>
              <h2 class="landing-section-title">Спокойствие и гордость для родителей</h2>
              <p class="landing-section-desc" style="text-align:left; margin:0 0 24px">
                Вам больше не нужно стоять над душой у ребёнка, проверять черновики или ругаться из-за домашки. Вы всегда точно знаете его готовность к экзаменам.
              </p>

              <div style="display:flex; flex-direction:column; gap:18px; margin-bottom:28px">
                <div style="display:flex; gap:14px; align-items:flex-start">
                  <div style="font-size:24px; line-height:1">📲</div>
                  <div>
                    <h4 style="margin:0 0 4px; font-size:1.05rem">Еженедельные отчёты в Telegram</h4>
                    <p class="muted" style="margin:0; font-size:0.9rem; line-height:1.5">
                      Бот автоматически присылает маме и папе понятную сводку: время за учебой, число решённых заданий, средний балл и слабые места.
                    </p>
                  </div>
                </div>

                <div style="display:flex; gap:14px; align-items:flex-start">
                  <div style="font-size:24px; line-height:1">💰</div>
                  <div>
                    <h4 style="margin:0 0 4px; font-size:1.05rem">В 10 раз выгоднее частных уроков</h4>
                    <p class="muted" style="margin:0; font-size:0.9rem; line-height:1.5">
                      Один час репетитора в Беларуси стоит от 30 BYN. Месяц безлимитного обучения с ИИ на нашей платформе — всего 19.90 BYN.
                    </p>
                  </div>
                </div>

                <div style="display:flex; gap:14px; align-items:flex-start">
                  <div style="font-size:24px; line-height:1">🛡️</div>
                  <div>
                    <h4 style="margin:0 0 4px; font-size:1.05rem">Только проверенные материалы</h4>
                    <p class="muted" style="margin:0; font-size:0.9rem; line-height:1.5">
                      Никакой посторонней рекламы, опасных ссылок или сомнительного контента. Только концентрированная учёба.
                    </p>
                  </div>
                </div>
              </div>

              <button type="button" class="btn primary" data-action="landing-go-auth" data-tab="register" style="padding:13px 26px; border-radius:12px; font-weight:700">
                👨‍👩‍👧 Подключить ребёнка к платформе
              </button>
            </div>

            <!-- Имитация сообщения бота родителям -->
            <div class="landing-tg-report-mockup">
              <div style="display:flex; align-items:center; gap:10px; margin-bottom:14px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:10px">
                <span style="font-size:22px">🤖</span>
                <div>
                  <div style="font-weight:700; font-size:0.95rem">Бот «Твой Репетитор»</div>
                  <div style="font-size:0.75rem; color:#94a3b8">Уведомление родителям</div>
                </div>
              </div>

              <div style="font-weight:700; font-size:1.05rem; margin-bottom:10px; color:#38bdf8">
                📊 Отчёт об успехах за неделю
              </div>

              <div style="line-height:1.6; font-size:0.9rem">
                <div>👤 Ученик: <strong>Максим</strong> (11 класс)</div>
                <div>⏱️ Время занятий: <strong>2 ч 45 мин</strong></div>
                <div>⚡ Решено заданий: <strong>74 задачи</strong></div>
                <div>🎯 Точность ответов: <strong style="color:#10b981">88% (+6% к прошлой неделе)</strong></div>
                <div>📈 Прогноз ЦТ/ЦЭ: <strong style="color:#c8ff3d">84 балла из 100</strong></div>
                <div>🔥 Ударный режим: <strong>7 дней подряд</strong></div>
                <div style="margin-top:10px; padding:10px; background:rgba(255,255,255,0.06); border-radius:10px">
                  💡 <em>Рекомендация ИИ:</em> Повторить правило «Правописание суффиксов причастий» перед контрольной.
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Секция: Тренажёр ЦТ/ЦЭ -->
      <section id="exam-sim" class="landing-section">
        <div class="landing-container">
          <div class="landing-section-header">
            <span class="landing-section-tag">Экзаменационный центр</span>
            <h2 class="landing-section-title">Симулятор ЦТ и ЦЭ по методике РИКЗ</h2>
            <p class="landing-section-desc">
              Точная тренировка реального бланка тестирования, исключающая стресс и ошибки по невнимательности на экзамене.
            </p>
          </div>

          <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:20px; max-width:1040px; margin:0 auto">
            <div class="card" style="padding:26px; border-radius:18px">
              <div style="font-size:32px; margin-bottom:12px">🔘</div>
              <h3 style="font-size:1.2rem; font-weight:700; margin:0 0 8px">Часть А: Закрытые тесты</h3>
              <p class="muted" style="font-size:0.92rem; line-height:1.55; margin:0">
                Задания с выбором одного или нескольких правильных вариантов. Мгновенная проверка и фиксация первичного балла.
              </p>
            </div>

            <div class="card" style="padding:26px; border-radius:18px">
              <div style="font-size:32px; margin-bottom:12px">✍️</div>
              <h3 style="font-size:1.2rem; font-weight:700; margin:0 0 8px">Часть Б: Краткий ответ</h3>
              <p class="muted" style="font-size:0.92rem; line-height:1.55; margin:0">
                Открытый ввод слов, форм слов или основ. Система проверяет правильность написания строго по правилам РИКЗ.
              </p>
            </div>

            <div class="card" style="padding:26px; border-radius:18px">
              <div style="font-size:32px; margin-bottom:12px">⏱️</div>
              <h3 style="font-size:1.2rem; font-weight:700; margin:0 0 8px">Таймер и 100-балльная шкала</h3>
              <p class="muted" style="font-size:0.92rem; line-height:1.55; margin:0">
                Полный симулятор 180 минут с официальным протоколом пересчёта, детализацией ошибок и разбором каждого вопроса.
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- Секция: Как это работает -->
      <section id="how-it-works" class="landing-section">
        <div class="landing-container">
          <div class="landing-section-header">
            <span class="landing-section-tag">Простой старт</span>
            <h2 class="landing-section-title">Как начать учиться за 3 шага</h2>
            <p class="landing-section-desc">
              Никаких долгих анкет и установок — платформа работает прямо в браузере на ПК, планшете или телефоне.
            </p>
          </div>

          <div class="landing-steps-grid">
            <div class="landing-step-card">
              <div class="landing-step-num">1</div>
              <h3 style="font-size:1.2rem; font-weight:700; margin:0 0 8px">Быстрый вход</h3>
              <p class="muted" style="font-size:0.92rem; line-height:1.55; margin:0">
                Создайте логин и пароль за 30 секунд или нажмите «Войти через Telegram» в 1 клик.
              </p>
            </div>

            <div class="landing-step-card">
              <div class="landing-step-num">2</div>
              <h3 style="font-size:1.2rem; font-weight:700; margin:0 0 8px">Выбор класса и цели</h3>
              <p class="muted" style="font-size:0.92rem; line-height:1.55; margin:0">
                Укажите класс (1–11) и цель: подготовка к ЦТ/ЦЭ, экзамен в 9 классе или школьная программа.
              </p>
            </div>

            <div class="landing-step-card">
              <div class="landing-step-num">3</div>
              <h3 style="font-size:1.2rem; font-weight:700; margin:0 0 8px">15 минут в день</h3>
              <p class="muted" style="font-size:0.92rem; line-height:1.55; margin:0">
                Решайте подборки заданий, получайте умный разбор ошибок от ИИ и радуйтесь росту баллов!
              </p>
            </div>
          </div>
        </div>
      </section>

      <!-- Секция: Тарифы -->
      <section id="tariffs-section" class="landing-section">
        <div class="landing-container">
          <div class="landing-section-header">
            <span class="landing-section-tag">Честные условия</span>
            <h2 class="landing-section-title">Тарифные планы</h2>
            <p class="landing-section-desc">
              Начните с бесплатного тарифа. Подключайте расширенные возможности, когда будете готовы.
            </p>
          </div>

          <div class="landing-tariffs-grid">
            <!-- Базовый -->
            <div class="landing-benefit-card" style="border-radius:22px">
              <div>
                <span class="badge" style="background:rgba(255,255,255,0.08); color:var(--muted); margin-bottom:12px">Ознакомительный</span>
                <h3 style="font-size:1.5rem; font-weight:800; margin:0 0 8px">Базовый</h3>
                <div style="font-size:2rem; font-weight:800; color:var(--ink); margin-bottom:16px">0 BYN</div>
                <p class="muted" style="font-size:0.9rem; line-height:1.5; margin-bottom:20px">
                  Идеально, чтобы попробовать платформу и закрепить основные темы уроков.
                </p>
              </div>
              <ul class="landing-benefit-list" style="margin-bottom:24px">
                <li class="landing-benefit-item"><span class="check">✓</span> <span>До 15 заданий в день</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Все темы программы 1–11 кл.</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Ударный режим и рейтинг</span></li>
              </ul>
              <button type="button" class="btn secondary block" data-action="landing-go-auth" data-tab="register" style="padding:12px; border-radius:12px; font-weight:700">
                Попробовать бесплатно
              </button>
            </div>

            <!-- Pro Месяц (Хит) -->
            <div class="landing-benefit-card" style="border-radius:22px; border:2px solid var(--accent); background:linear-gradient(180deg, rgba(200,255,61,0.06), transparent 60%), var(--card); position:relative">
              <div style="position:absolute; top:-12px; right:20px; background:var(--accent); color:#000; font-size:0.75rem; font-weight:800; padding:4px 12px; border-radius:999px">
                ПОПУЛЯРНЫЙ
              </div>
              <div>
                <span class="badge" style="background:rgba(200,255,61,0.2); color:var(--accent); margin-bottom:12px">Полный Pro-доступ</span>
                <h3 style="font-size:1.5rem; font-weight:800; margin:0 0 8px">Pro · 1 месяц</h3>
                <div style="font-size:2rem; font-weight:800; color:var(--accent); margin-bottom:4px">19.90 BYN</div>
                <div style="font-size:0.82rem; color:var(--muted); margin-bottom:16px">или 590 ₽ / 30 дней</div>
                <p class="muted" style="font-size:0.9rem; line-height:1.5; margin-bottom:20px">
                  Неограниченная подготовка к ЦТ/ЦЭ и персональный ИИ-репетитор.
                </p>
              </div>
              <ul class="landing-benefit-list" style="margin-bottom:24px">
                <li class="landing-benefit-item"><span class="check">✓</span> <span><strong>Безлимитный</strong> тренажёр</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Полные симуляторы ЦТ (РИКЗ)</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Пошаговый разбор ошибок с ИИ</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Отчёты родителям в Telegram</span></li>
              </ul>
              <button type="button" class="btn primary block" data-action="landing-go-auth" data-tab="register" style="padding:12px; border-radius:12px; font-weight:800">
                ⚡ Начать подготовку
              </button>
            </div>

            <!-- Pro Год -->
            <div class="landing-benefit-card" style="border-radius:22px">
              <div>
                <span class="badge" style="background:rgba(56,189,248,0.2); color:#38bdf8; margin-bottom:12px">Выгода 60%</span>
                <h3 style="font-size:1.5rem; font-weight:800; margin:0 0 8px">Pro · Учебный год</h3>
                <div style="font-size:2rem; font-weight:800; color:var(--ink); margin-bottom:4px">149.90 BYN</div>
                <div style="font-size:0.82rem; color:var(--muted); margin-bottom:16px">всего ~12.50 BYN в месяц</div>
                <p class="muted" style="font-size:0.9rem; line-height:1.5; margin-bottom:20px">
                  Полное сопровождение на весь учебный год до самого поступления.
                </p>
              </div>
              <ul class="landing-benefit-list" style="margin-bottom:24px">
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Все преимущества Pro на 365 дней</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Приоритетная линия ИИ-ответов</span></li>
                <li class="landing-benefit-item"><span class="check">✓</span> <span>Экономия более 85 BYN</span></li>
              </ul>
              <button type="button" class="btn secondary block" data-action="landing-go-auth" data-tab="register" style="padding:12px; border-radius:12px; font-weight:700">
                Оформить на год
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Интерактивная секция авторизации / регистрации -->
      <section id="auth-section" class="landing-section" style="background:rgba(255,255,255,0.015)">
        <div class="landing-container">
          <div class="landing-section-header">
            <span class="landing-section-tag">Личный кабинет</span>
            <h2 class="landing-section-title">Присоединяйтесь к платформе</h2>
            <p class="landing-section-desc">
              Создайте бесплатный аккаунт или войдите через Telegram за 1 секунду.
            </p>
          </div>

          <!-- Встроенная карточка входа/регистрации -->
          <div id="auth-card-anchor" style="max-width:440px; margin:0 auto">
            ${authBlockHtml}
          </div>
        </div>
      </section>

      <!-- Подвал (Footer) -->
      <footer class="landing-footer landing-container">
        <div class="landing-footer-grid">
          <div>
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px">
              <span style="font-size:22px">⚡</span>
              <strong style="font-size:1.1rem">Твой Репетитор</strong>
            </div>
            <p class="muted" style="font-size:0.88rem; line-height:1.6; margin:0 0 16px">
              Интерактивная образовательная онлайн-платформа подготовки к ЦТ, ЦЭ и школьной аттестации в Республике Беларусь.
            </p>
            <div style="font-size:0.82rem; color:var(--muted); line-height:1.5">
              ${REQUISITES.shortName}<br />
              ИНН: ${REQUISITES.inn}<br />
              Email: <a href="mailto:${REQUISITES.email}" style="color:var(--accent)">${REQUISITES.email}</a><br />
              Тел.: ${REQUISITES.phone}
            </div>
          </div>

          <div>
            <div class="landing-footer-title">Навигация</div>
            <ul class="landing-footer-links">
              <li><a class="landing-footer-link" data-action="landing-nav" data-target="benefits">Преимущества</a></li>
              <li><a class="landing-footer-link" data-action="landing-nav" data-target="exam-sim">Тренажёр ЦТ/ЦЭ</a></li>
              <li><a class="landing-footer-link" data-action="landing-nav" data-target="for-parents">Для родителей</a></li>
              <li><a class="landing-footer-link" data-action="landing-nav" data-target="tariffs-section">Тарифы</a></li>
              <li><a class="landing-footer-link" data-action="landing-go-auth" data-tab="login">Вход в аккаунт</a></li>
            </ul>
          </div>

          <div>
            <div class="landing-footer-title">Документы</div>
            <ul class="landing-footer-links">
              <li><a class="landing-footer-link" data-action="open-legal" data-legal="terms">Публичная оферта</a></li>
              <li><a class="landing-footer-link" data-action="open-legal" data-legal="privacy">Политика конфиденциальности</a></li>
              <li><a class="landing-footer-link" data-action="open-legal" data-legal="refund">Оплата и безопасность</a></li>
              <li><a class="landing-footer-link" href="https://t.me/tutor_by_bot" target="_blank">Telegram-бот @tutor_by_bot</a></li>
            </ul>
          </div>
        </div>

        <div style="border-top:1px solid var(--card-border); padding-top:20px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; font-size:0.82rem; color:var(--muted)">
          <div>© 2026 Образовательная платформа «Твой Репетитор». Все права защищены.</div>
          <div>Разработано для школьников и абитуриентов Беларуси 🇧🇾</div>
        </div>
      </footer>
    </div>
  `;
}
