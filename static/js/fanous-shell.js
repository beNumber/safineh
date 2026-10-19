document.addEventListener('DOMContentLoaded', () => {
  const quizIndicator = document.getElementById('quiz-live-indicator');
  const quizWindowsNode = document.getElementById('quiz-live-windows');
  if (quizIndicator && quizWindowsNode) {
    const quizWindows = JSON.parse(quizWindowsNode.textContent || '[]');
    const updateQuizIndicator = () => {
      const now = Date.now();
      quizIndicator.hidden = !quizWindows.some(window => Date.parse(window.opens) <= now && now < Date.parse(window.closes));
    };
    updateQuizIndicator();
    setInterval(updateQuizIndicator, 15000);
  }
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
      const response = await fetch(button.dataset.readUrl, {
        method: 'POST',
        headers: {'X-CSRFToken': csrfToken(), 'Content-Type': 'application/x-www-form-urlencoded'},
        body: new URLSearchParams({token: button.dataset.readToken || ''}),
        credentials: 'same-origin'
      });
      if (!response.ok) throw new Error('Notification read failed');
      badge.style.transition = 'opacity .25s, transform .25s';
      badge.style.opacity = '0';
      badge.style.transform = 'scale(.55)';
      setTimeout(() => badge.remove(), 260);
    } catch (_) { marked = false; }
  };
  button?.addEventListener('click', event => {
    event.stopPropagation();
    panel?.classList.toggle('hidden');
    document.getElementById('profile-menu')?.classList.add('hidden');
    button.setAttribute('aria-expanded', String(!panel?.classList.contains('hidden')));
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
