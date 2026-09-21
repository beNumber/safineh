document.addEventListener('DOMContentLoaded', () => {
  const links = [...document.querySelectorAll('.sidebar-link[href]')];
  const current = window.location.pathname.replace(/\/+$/, '/') || '/';
  const candidates = links.map((link, index) => {
    const path = (link.dataset.navPrefix || new URL(link.href, window.location.origin).pathname).replace(/\/+$/, '/') || '/';
    const matches = path === '/dashboard/' ? current === path : path !== '/' && current.startsWith(path);
    return { link, path, index, matches };
  }).filter(item => item.matches).sort((a, b) => b.path.length - a.path.length || a.index - b.index);
  links.forEach(link => { link.classList.remove('active', 'sidebar-link-active'); link.removeAttribute('aria-current'); });
  if (candidates[0]) {
    candidates[0].link.classList.add('active');
    candidates[0].link.setAttribute('aria-current', 'page');
  }

  const button = document.getElementById('notification-toggle');
  const panel = document.getElementById('notification-panel');
  const badge = document.getElementById('notification-count');
  let marked = false;
  const csrfToken = () => document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || button?.dataset.csrf || '';
  const markRead = async () => {
    if (marked || !badge) return;
    marked = true;
    try {
      await fetch(button.dataset.readUrl, {
        method: 'POST',
        headers: {'X-CSRFToken': csrfToken()},
        credentials: 'same-origin'
      });
      badge.style.transition = 'opacity .25s, transform .25s';
      badge.style.opacity = '0';
      badge.style.transform = 'scale(.55)';
      setTimeout(() => badge.remove(), 260);
    } catch (_) { marked = false; }
  };
  button?.addEventListener('click', event => {
    event.stopPropagation();
    panel?.classList.toggle('hidden');
    button.classList.toggle('is-open', !panel?.classList.contains('hidden'));
    if (!panel?.classList.contains('hidden')) markRead();
  });
  document.addEventListener('click', event => {
    if (panel && button && !panel.contains(event.target) && !button.contains(event.target)) {
      panel.classList.add('hidden');
      button.classList.remove('is-open');
    }
  });
});
