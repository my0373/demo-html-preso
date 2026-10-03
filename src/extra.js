/* ---- deck additions: jump search, slide ids, goto links ---- */
// Slides can be reached by number (#12) or by id (#model). data-goto="id" on any element jumps there.
const topicOf = [];
groups.forEach(g => g.idx.forEach(i => topicOf[i] = g.name));

const ovq = document.getElementById('ovq');
const ovInfo = document.getElementById('ovinfo');
[...ovg.children].forEach((b, i) => b.insertAdjacentHTML('beforeend', `<small>${topicOf[i]}</small>`));

function openOv(){
  ov.classList.add('on');
  [...ovg.children].forEach((b, i) => b.classList.toggle('cur', i === cur));
  ovq.value = ''; filterOv();
  ovq.focus();
}
function closeOv(){ ov.classList.remove('on'); ovq.blur(); }
function filterOv(){
  const q = ovq.value.trim().toLowerCase();
  let first = null, n = 0;
  [...ovg.children].forEach((b, i) => {
    const hay = (slides[i].dataset.title + ' ' + topicOf[i] + ' ' + (i + 1)).toLowerCase();
    const ok = !q || hay.includes(q) || String(i + 1) === q;
    b.classList.toggle('off', !ok); b.classList.remove('hit');
    if (ok) { n++; if (!first) first = b; }
  });
  if (q && first) first.classList.add('hit');
  ovInfo.textContent = q ? `${n} match${n === 1 ? '' : 'es'}. Enter to jump` : 'Type a title, a topic or a slide number';
}
ovq.addEventListener('input', filterOv);
ovq.addEventListener('keydown', e => {
  if (e.key === 'Enter') { const h = ovg.querySelector('button.hit') || ovg.querySelector('button:not(.off)'); if (h) h.click(); }
  if (e.key === 'Escape') closeOv();
  e.stopPropagation();
});
document.getElementById('jumpbtn').onclick = e => { e.stopPropagation(); ov.classList.contains('on') ? closeOv() : openOv(); };
addEventListener('keydown', e => {
  if (e.target === ovq) return;
  if (e.key === 'g' || e.key === 'G' || e.key === '/') { e.preventDefault(); e.stopImmediatePropagation(); openOv(); }
  if (e.key === 'o' || e.key === 'O') { e.stopImmediatePropagation(); ov.classList.contains('on') ? closeOv() : openOv(); }
}, true);

document.addEventListener('click', e => {
  const t = e.target.closest('[data-goto]');
  if (!t || e.target.closest('a')) return;
  const i = slides.findIndex(s => s.id === t.dataset.goto);
  if (i >= 0) { e.stopPropagation(); go(i); }
}, true);
addEventListener('hashchange', () => {
  const h = location.hash.slice(1), i = isNaN(+h) ? slides.findIndex(s => s.id === h) : +h - 1;
  if (i >= 0 && i !== cur) go(i);
});

/* ---- motion ---- */
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

// Code blocks: one span per line, so lines can settle in one after another
document.querySelectorAll('.code pre').forEach(pre => {
  pre.innerHTML = pre.innerHTML.split('\n').map((l, i) => `<span class="ln" style="--i:${i}">${l}</span>`).join('');
});

// Diagram edges: a bead of light travels each connector, out of step with its neighbours
const SVGNS = 'http://www.w3.org/2000/svg';
const drawEdges = edges;
edges = function(el){
  drawEdges(el);
  if (reduceMotion) return;
  el.querySelectorAll('.dia svg.e').forEach(svg => {
    svg.querySelectorAll('path').forEach((p, i) => {
      const c = document.createElementNS(SVGNS, 'circle');
      c.setAttribute('r', '4.5'); c.setAttribute('class', 'pk ' + (p.getAttribute('class') || ''));
      const a = document.createElementNS(SVGNS, 'animateMotion');
      a.setAttribute('dur', (2.8 + (i % 3) * 0.6) + 's'); a.setAttribute('repeatCount', 'indefinite');
      a.setAttribute('begin', (-i * 0.9) + 's'); a.setAttribute('path', p.getAttribute('d'));
      c.appendChild(a); svg.appendChild(c);
    });
  });
};

// Video loops: all preload (about 2.7 MB in total), only the slide in view plays
const loops = [...document.querySelectorAll('video.loop')];
loops.forEach(v => { v.muted = true; v.loop = true; v.playsInline = true; });
function syncVideo(){
  loops.forEach(v => {
    const i = slides.indexOf(v.closest('.slide'));
    if (reduceMotion) return;
    if (i === cur) { const pr = v.play(); if (pr && pr.catch) pr.catch(() => {}); }
    else if (!v.paused) v.pause();
  });
}
const paintSlide = paint;
paint = function(){ paintSlide(); syncVideo(); };
