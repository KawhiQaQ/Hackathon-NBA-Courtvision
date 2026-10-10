const $ = id => document.getElementById(id);
const pages = {
  video: {number: '02', next: '#story', label: '故事', previous: 'workbench.html', back: '导入分析'},
  story: {number: '03', next: '#data', label: '数据', previous: '#video', back: '战术影像'},
  data: {number: '04', next: 'workbench.html', label: '新建', previous: '#story', back: '故事回放'},
  awards: {number: '04', next: 'workbench.html', label: '新建', previous: '#data', back: '数据解读'},
};
function route() {
  const requested = location.hash.slice(1);
  const view = Object.hasOwn(pages, requested) ? requested : 'video';
  const page = pages[view];
  document.body.dataset.view = view;
  document.querySelectorAll('[data-view-link]').forEach(link => {
    const active = link.dataset.viewLink === (view === 'awards' ? 'data' : view);
    if (active) link.setAttribute('aria-current', 'step');
    else link.removeAttribute('aria-current');
  });
  const hasAwards = !$('awards').hidden;
  $('awards-link').hidden = !hasAwards;
  $('next-page').href = view === 'data' && hasAwards ? '#awards' : page.next;
  const label = view === 'data' && hasAwards ? '汇总' : page.label;
  $('next-label').textContent = label;
  $('next-page').setAttribute('aria-label', '前往' + label);
  $('previous-page').href = page.previous;
  $('previous-page').textContent = '← ' + page.back;
  $('page-count').textContent = page.number + ' / 04';
  $('data-notes-open').hidden = view !== 'data';
  if (view !== 'video') $('replay').pause();
  requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
}
window.addEventListener('hashchange', route);
new MutationObserver(route).observe($('awards'), {attributes: true, attributeFilter: ['hidden']});
$('frames').addEventListener('click', event => {
  if (event.target.closest('[data-frame]')) location.hash = 'video';
});
$('leaderboard').addEventListener('click', event => {
  if (event.target.closest('[data-round]')) location.hash = 'video';
});
$('data-notes-open').onclick = () => {
  const content = $('data-notes-content');
  content.replaceChildren();
  for (const [heading, selector] of [
    ['回合贡献', '#score-formula, #score-method > p:last-child, #components .score-factor p'],
    ['指标与对照', '.data-grid .data-note'],
  ]) {
    const title = document.createElement('h3'); title.textContent = heading; content.append(title);
    document.querySelectorAll(selector).forEach(source => {
      if (!source.textContent.trim()) return;
      const p = document.createElement('p'); p.textContent = source.textContent; content.append(p);
    });
  }
  $('data-notes').showModal();
};
$('data-notes-close').onclick = () => $('data-notes').close();
route();
