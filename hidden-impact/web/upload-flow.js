const result = document.getElementById('view-presentation');
const next = document.getElementById('upload-next');
const links = [...document.querySelectorAll('.step-nav a')].slice(1);
const targets = ['video', 'story', 'data'];
function syncResult() {
  const ready = !result.hidden && !!result.getAttribute('href');
  const url = ready ? new URL(result.href, location.href) : null;
  [next, ...links].forEach((link, index) => {
    link.setAttribute('aria-disabled', String(!ready));
    if (ready) {
      url.hash = index === 0 ? 'video' : targets[index - 1];
      link.href = url.href;
    } else link.removeAttribute('href');
  });
}
new MutationObserver(syncResult).observe(result, {attributes: true, attributeFilter: ['href', 'hidden']});
[next, ...links].forEach(link => link.addEventListener('click', event => {
  if (link.getAttribute('aria-disabled') === 'true') event.preventDefault();
}));
syncResult();
