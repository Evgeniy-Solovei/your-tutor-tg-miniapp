const THEME_KEY = 'tutor_theme';

export const THEMES = {
  vibe: {
    id: 'vibe',
    label: '⚡ Вайб',
    nextTheme: 'ultra',
    nextLabel: '💎 Ультра',
    sub: 'поехали решать',
    toast: 'Тема: Молодежный Вайб ⚡',
  },
  ultra: {
    id: 'ultra',
    label: '💎 Ультра',
    nextTheme: 'calm',
    nextLabel: '🌿 Дзен',
    sub: 'Bento Glass & Cyber',
    toast: 'Тема: Ультра Модный Bento 💎',
  },
  calm: {
    id: 'calm',
    label: '🌿 Дзен',
    nextTheme: 'vibe',
    nextLabel: '⚡ Вайб',
    sub: 'чистый фокус',
    toast: 'Тема: Минимал Дзен 🌿',
  },
};

function normalize(theme) {
  if (theme === 'ultra') return 'ultra';
  if (theme === 'calm') return 'calm';
  return 'vibe';
}

export function getTheme() {
  return normalize(localStorage.getItem(THEME_KEY));
}

export function setTheme(theme) {
  const next = normalize(theme);
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem(THEME_KEY, next);
  return next;
}

export function toggleTheme() {
  const current = getTheme();
  const next = THEMES[current]?.nextTheme || 'vibe';
  return setTheme(next);
}

export function initTheme() {
  return setTheme(getTheme());
}
