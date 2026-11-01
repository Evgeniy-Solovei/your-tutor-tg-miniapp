/** Фоны: градиенты и стили атмосферы для тем: vibe, ultra, calm. */

const CALM = [
  {
    gradient:
      'radial-gradient(1000px 500px at 50% -5%, rgba(16, 185, 129, 0.14), transparent 55%), radial-gradient(800px 400px at 100% 40%, rgba(56, 189, 248, 0.08), transparent 50%), linear-gradient(165deg, #090f1a 0%, #0f172a 45%, #080d17 100%)',
  },
];

const VIBE = [
  {
    gradient:
      'radial-gradient(ellipse at 20% 0%, rgba(255,77,141,0.32), transparent 45%), radial-gradient(ellipse at 90% 20%, rgba(200,255,61,0.26), transparent 40%), linear-gradient(160deg, #0a0a10 0%, #151224 55%, #0b0c14 100%)',
  },
];

const ULTRA = [
  {
    gradient:
      'radial-gradient(1200px 700px at 15% 10%, rgba(139,92,246,0.35), transparent 50%), radial-gradient(1000px 600px at 85% 20%, rgba(6,182,212,0.25), transparent 45%), radial-gradient(800px 500px at 50% 90%, rgba(244,63,94,0.18), transparent 45%), linear-gradient(180deg, #06070b 0%, #0c0e17 50%, #08090e 100%)',
  },
];

let timer = null;
let index = 0;

function slidesFor(theme) {
  if (theme === 'ultra') return ULTRA;
  if (theme === 'calm') return CALM;
  return VIBE;
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
