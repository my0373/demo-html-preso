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
