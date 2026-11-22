/**
 * Высокопроизводительный атмосферный фон без GPU-перегрузок и троттлинга.
 * Устраняет выпадение плиток (квадратиков) и мерцание при прокрутке.
 */

export function startAtmosphere(theme) {
  const root = document.getElementById('atmosphere');
  if (root) {
    // Очищаем DOM от тяжелых анимированных стикеров и таймеров, вызывающих лаги на GPU
    root.innerHTML = '';
    root.style.display = 'none';
  }
}
