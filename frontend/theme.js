const THEME_KEY = 'tutor_theme';

export const THEMES = {
  calm: {
    id: 'calm',
    label: 'Спокойная',
    nextLabel: 'Вайб',
    sub: 'ЦТ · ЦЭ',
  },
  vibe: {
    id: 'vibe',
    label: 'Вайб',
    nextLabel: 'Спокойная',
    sub: 'поехали решать',
  },
};

function normalize(theme) {
  if (theme === 'vibe' || theme === 'night' || theme === 'arcade') return 'vibe';
  return 'calm';
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
  return setTheme(getTheme() === 'calm' ? 'vibe' : 'calm');
}

export function initTheme() {
  return setTheme(getTheme());
}
