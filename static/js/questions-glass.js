document.addEventListener('DOMContentLoaded', () => {
  const shell = document.querySelector('.qb-shell');
  if (!shell) return;
  const script = document.getElementById('questions-glass-script');
  const bankUrl = script?.dataset.bankUrl || '/questions/wizard/mode/';

  const normalizedPath = window.location.pathname.replace(/\/+$/, '/') || '/';
  const normalizedBankUrl = bankUrl.replace(/\/+$/, '/') || '/';
  const bankRoots = ['/questions/', normalizedBankUrl];
  if (!bankRoots.includes(normalizedPath) && !shell.querySelector('.qb-back-to-bank')) {
    const back = document.createElement('a');
    back.className = 'qb-back-to-bank';
    back.href = bankUrl;
    back.innerHTML = '<i class="fa-solid fa-arrow-right"></i><span>بازگشت به بانک سؤال</span>';
    shell.prepend(back);
  }

  const revealTargets = shell.querySelectorAll('.qb-hero, .qb-card, .qb-performance-card, .qb-topic-panel');
  if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add('qb-visible');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.08 });
    revealTargets.forEach((item, index) => {
      item.classList.add('qb-reveal');
      item.style.transitionDelay = `${Math.min(index * 45, 220)}ms`;
      observer.observe(item);
    });
  }

  shell.querySelectorAll('button, .qb-session-type, .qb-check-card').forEach((target) => {
    target.addEventListener('pointerdown', (event) => {
      const rect = target.getBoundingClientRect();
      const diameter = Math.max(rect.width, rect.height) * 1.5;
      const ripple = document.createElement('span');
      ripple.className = 'qb-ripple';
      ripple.style.width = ripple.style.height = `${diameter}px`;
      ripple.style.left = `${event.clientX - rect.left}px`;
      ripple.style.top = `${event.clientY - rect.top}px`;
      if (getComputedStyle(target).position === 'static') target.style.position = 'relative';
      target.style.overflow = 'hidden';
      target.appendChild(ripple);
      ripple.addEventListener('animationend', () => ripple.remove());
    });
  });
});
