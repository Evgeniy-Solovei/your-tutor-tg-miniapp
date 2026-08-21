/** Фоны: спокойный градиент / мемный стикер-слой для «вайба». */

const CALM = [
  { gradient: 'linear-gradient(165deg, #e8efe9 0%, #f3f6f4 42%, #e4ebe8 100%)' },
  { gradient: 'linear-gradient(145deg, #eef2f0 0%, #f6f8f7 55%, #e7eeea 100%)' },
];

const VIBE = [
  {
    // не картинки мемов с интернета — стикер-вайб через CSS в .atmosphere
    gradient:
      'radial-gradient(ellipse at 20% 0%, rgba(255,77,141,0.35), transparent 45%), radial-gradient(ellipse at 90% 20%, rgba(200,255,61,0.28), transparent 40%), linear-gradient(160deg, #0b0b12 0%, #171225 55%, #0e1520 100%)',
  },
];

let timer = null;
let index = 0;

function slidesFor(theme) {
  return theme === 'vibe' ? VIBE : CALM;
}

export function startAtmosphere(theme) {
  const root = document.getElementById('atmosphere');
  if (!root) return;

  const slides = slidesFor(theme);
  index = 0;

  const stickers =
    theme === 'vibe'
      ? `
      <div class="meme-layer" aria-hidden="true">
        <span class="sticker s1">ну такое</span>
        <span class="sticker s2">норм тема</span>
        <span class="sticker s3">💀</span>
        <span class="sticker s4">по кайфу</span>
        <span class="sticker s5">🔥</span>
        <span class="sticker s6">ваще</span>
        <span class="sticker s7">😭</span>
        <span class="sticker s8">топ</span>
      </div>`
      : '';

  root.innerHTML = `
    ${slides
      .map((s, i) => {
        const bg = `background-image:${s.gradient}`;
        return `<div class="slide${i === 0 ? ' active' : ''}" style="${bg}"></div>`;
      })
      .join('')}
    <div class="veil"></div>
    ${stickers}
  `;

  if (timer) clearInterval(timer);
  if (slides.length < 2) return;
  timer = setInterval(() => {
    const nodes = root.querySelectorAll('.slide');
    if (!nodes.length) return;
    nodes[index].classList.remove('active');
    index = (index + 1) % nodes.length;
    nodes[index].classList.add('active');
  }, 10000);
}
