import { getDevTgId, getInitData, getUnsafeUser, isDevBypass } from './telegram.js';

const API_BASE = '/api/tutor';

function authHeaders() {
  const headers = { 'Content-Type': 'application/json' };
  // Официальный способ ngrok free не показывать warning на API-запросах
  headers['ngrok-skip-browser-warning'] = 'true';
  const initData = getInitData();
  if (initData) {
    headers['Telegram-Init-Data'] = initData;
    headers.Authorization = `tma ${initData}`;
  } else if (isDevBypass()) {
    const id = getDevTgId() || getUnsafeUser()?.id;
    if (id) headers['Telegram-Dev-User'] = String(id);
  }
  return headers;
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.detail || data.error || `HTTP ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  me: () => request('/me/'),
  register: (payload) =>
    request('/me/register/', { method: 'POST', body: JSON.stringify(payload) }),
  updateProfile: (payload) =>
    request('/me/profile/', { method: 'PATCH', body: JSON.stringify(payload) }),
  config: () => request('/config/'),
  setWebAppUrl: (web_app_url) =>
    request('/config/web-app-url/', {
      method: 'POST',
      body: JSON.stringify({ web_app_url }),
    }),
  cities: (q = '') => request(`/cities/?q=${encodeURIComponent(q)}`),
  schools: (cityId, q = '') =>
    request(`/cities/${cityId}/schools/?q=${encodeURIComponent(q)}`),
  subjects: () => request('/knowledge/subjects/'),
  tracks: (subjectId) => request(`/knowledge/subjects/${subjectId}/tracks/`),
  catalog: () => request('/knowledge/catalog/'),
  devUsers: () => request('/dev/users/'),
  stats: (tgId) => request(`/stats/${tgId}/`),
  scores: (tgId, page = 1) => request(`/scores/${tgId}/?page=${page}`),
  streak: (tgId) => request(`/streak/${tgId}/`),
  tariffs: () => request('/tariffs/'),
  daily: (tgId) => request(`/daily-session/${tgId}/`),
  izlozheniya: (tgId, q = '') =>
    request(`/izlozheniya/${tgId}/?q=${encodeURIComponent(q)}`),
  startIzlozhenie: (tgId, payload = {}) =>
    request(`/izlozheniya/${tgId}/start/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  leaderboard: (scope = 'country', extra = {}) => {
    const params = new URLSearchParams({ scope });
    if (extra.period) params.set('period', String(extra.period));
    if (extra.city_id) params.set('city_id', String(extra.city_id));
    if (extra.school_id) params.set('school_id', String(extra.school_id));
    return request(`/leaderboard/?${params}`);
  },
  submit: (tgId, sessionTaskId, answerText) =>
    request(`/submit-answer/${tgId}/`, {
      method: 'POST',
      body: JSON.stringify({
        session_task_id: sessionTaskId,
        answer_text: answerText,
      }),
    }),
  explain: (tgId, sessionTaskId) =>
    request(`/learning/ai-explain/${tgId}/`, {
      method: 'POST',
      body: JSON.stringify({ session_task_id: sessionTaskId }),
    }),
  family: () => request('/family/'),
  familyInvite: (tgId) =>
    request(`/family/invite/${tgId}/`, { method: 'POST', body: '{}' }),
  familyLink: (code) =>
    request('/family/link/', {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),
  familyReport: (payload) =>
    request('/family/report/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  familyUnlink: (studentId) =>
    request('/family/unlink/', {
      method: 'POST',
      body: JSON.stringify({ student_id: studentId }),
    }),
  dashboard: (tgId) => request(`/dashboard/${tgId}/`),
  createCheckout: (planCode) =>
    request('/payments/bepaid/checkout/', {
      method: 'POST',
      body: JSON.stringify({ plan_code: planCode }),
    }),
  startExam: (tgId, payload = {}) =>
    request(`/exam/${tgId}/start/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  submitExam: (tgId, payload = {}) =>
    request(`/exam/${tgId}/submit/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  pingSession: (durationSeconds = 30) =>
    request('/ping-session/', {
      method: 'POST',
      body: JSON.stringify({ duration_seconds: durationSeconds }),
    }),
};
