/** Telegram WebApp bootstrap + initData для HMAC на бэке. */

export function getWebApp() {
  return window.Telegram?.WebApp ?? null;
}

export function bootTelegram() {
  const tg = getWebApp();
  if (!tg) return null;
  try {
    tg.ready();
    tg.expand();
    if (typeof tg.disableVerticalSwipes === 'function') {
      tg.disableVerticalSwipes();
    }
  } catch (_) {
    /* ignore */
  }
  return tg;
}

export function getInitData() {
  const tg = getWebApp();
  if (tg?.initData) return tg.initData;
  // локальная отладка вне Telegram
  const params = new URLSearchParams(window.location.search);
  return params.get('initData') || '';
}

const DEV_KEY = 'tutor_dev_tg_id';

export function getDevTgId() {
  const params = new URLSearchParams(window.location.search);
  const fromQuery = params.get('dev_tg_id');
  if (fromQuery) {
    sessionStorage.setItem(DEV_KEY, fromQuery);
    return fromQuery;
  }
  return sessionStorage.getItem(DEV_KEY) || '';
}

export function setDevTgId(id) {
  sessionStorage.setItem(DEV_KEY, String(id));
  const url = new URL(window.location.href);
  url.searchParams.set('dev_tg_id', String(id));
  window.history.replaceState({}, '', url.toString());
}

export function getUnsafeUser() {
  const tg = getWebApp();
  if (tg?.initDataUnsafe?.user) return tg.initDataUnsafe.user;
  const id = getDevTgId();
  if (id) return { id: Number(id), first_name: 'Dev' };
  return null;
}

export function isDevBypass() {
  // Вне Telegram всегда пробуем dev-режим (если бэкенд BYPASS выключен — получим 401)
  const tg = getWebApp();
  if (tg?.initData) return false;
  return Boolean(getDevTgId()) || true;
}
