document.addEventListener('DOMContentLoaded', () => {
  const cfg = window.quizConfig;
  const form = document.getElementById('attempt-form');
  if (!cfg || !form) return;
  const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
  const slides = [...document.querySelectorAll('.quiz-question-slide')];
  const nav = [...document.querySelectorAll('.quiz-nav-item')];
  const pendingSaves = new Set();
  const revisions = new Map();
  let current = 0;
  let seconds = cfg.seconds;
  let submitted = false;
  let timerId;

  const go = index => {
    if (index < 0 || index >= slides.length) return;
    slides[current].classList.remove('active');
    nav[current].classList.remove('current');
    current = index;
    slides[current].classList.add('active');
    nav[current].classList.add('current');
    slides[current].scrollIntoView({behavior: 'smooth', block: 'center'});
  };
  nav.forEach((button, index) => button.addEventListener('click', () => go(index)));
  document.querySelectorAll('.next-btn').forEach(button => button.addEventListener('click', () => go(current + 1)));
  document.querySelectorAll('.prev-btn').forEach(button => button.addEventListener('click', () => go(current - 1)));

  const syncProgress = () => {
    const done = nav.filter(item => item.classList.contains('answered')).length;
    const percent = slides.length ? Math.round(done * 100 / slides.length) : 0;
    document.getElementById('progress-bar').style.width = `${percent}%`;
    document.getElementById('progress-label').textContent = `${percent.toLocaleString('fa-IR')}٪ پاسخ داده‌شده`;
  };
  const storageKey = slide => `quiz-${cfg.attemptId}-q-${slide.dataset.question}`;
  const setState = (slide, mode, html) => {
    const state = slide.querySelector('.quiz-save-state');
    state.className = `quiz-save-state ${mode} mt-4 h-5 text-xs`;
    state.innerHTML = html;
  };

  function save(slide, data, file = null, retry = false) {
    const revision = (revisions.get(slide) || 0) + 1;
    revisions.set(slide, revision);
    setState(slide, 'saving', '<span class="quiz-loader"></span> در حال ذخیره');
    if (!file) localStorage.setItem(storageKey(slide), JSON.stringify(data));
    let body;
    if (file) {
      body = new FormData();
      Object.entries(data).forEach(([key, value]) => body.append(key, value));
      body.append('image', file);
    } else {
      body = new URLSearchParams(data);
    }
    const promise = fetch(slide.dataset.save, {method: 'POST', headers: {'X-CSRFToken': csrf}, body})
      .then(async response => {
        if (response.status === 409) { submitNow(); return null; }
        const json = await response.json();
        if (!response.ok) throw new Error(json.error || 'ذخیره پاسخ ناموفق بود.');
        if (revisions.get(slide) !== revision) return json;
        localStorage.removeItem(storageKey(slide));
        setState(slide, 'saved', 'ذخیره شد ✓');
        const item = nav[Number(slide.dataset.index)];
        item.classList.toggle('answered', json.answered);
        item.classList.toggle('bookmarked', json.bookmarked);
        syncProgress();
        return json;
      })
      .catch(error => {
        if (revisions.get(slide) !== revision) return;
        setState(slide, navigator.onLine ? 'failed' : 'offline', `${navigator.onLine ? 'خطا در ذخیره' : 'ذخیره موقت آفلاین'}؛ تلاش مجدد خودکار`);
        if (file) slide.dataset.unsavedImage = 'true';
        if (!retry && navigator.onLine) window.setTimeout(() => save(slide, data, file, true), 1500);
        return error;
      })
      .finally(() => pendingSaves.delete(promise));
    pendingSaves.add(promise);
    return promise;
  }

  slides.forEach(slide => {
    slide.querySelectorAll('input[type=radio]').forEach(input => input.addEventListener('change', () => {
      slide.querySelectorAll('.quiz-choice').forEach(choice => choice.classList.remove('selected'));
      input.closest('.quiz-choice').classList.add('selected');
      save(slide, {choice: input.value, bookmarked: slide.querySelector('.quiz-bookmark').classList.contains('active')});
    }));
    let debounce;
    slide.querySelector('.descriptive-text')?.addEventListener('input', event => {
      clearTimeout(debounce);
      debounce = setTimeout(() => save(slide, {text: event.target.value, bookmarked: slide.querySelector('.quiz-bookmark').classList.contains('active')}), 650);
    });
    slide.querySelector('.answer-image')?.addEventListener('change', event => {
      if (event.target.files[0]) save(slide, {text: slide.querySelector('.descriptive-text').value, bookmarked: slide.querySelector('.quiz-bookmark').classList.contains('active')}, event.target.files[0]);
    });
    slide.querySelector('.quiz-bookmark').addEventListener('click', event => {
      const button = event.currentTarget;
      button.classList.toggle('active');
      button.querySelector('i').classList.toggle('fa-solid');
      button.querySelector('i').classList.toggle('fa-regular');
      const choice = slide.querySelector('input[type=radio]:checked');
      save(slide, {choice: choice?.value || '', text: slide.querySelector('.descriptive-text')?.value || '', bookmarked: button.classList.contains('active')});
    });
  });

  async function submitNow() {
    if (submitted) return;
    submitted = true;
    clearInterval(timerId);
    await Promise.race([
      Promise.allSettled([...pendingSaves]),
      new Promise(resolve => window.setTimeout(resolve, 1500)),
    ]);
    form.submit();
  }
  document.querySelectorAll('.finish-btn').forEach(button => button.addEventListener('click', () => {
    if (confirm('پاسخ‌برگ ارسال و آزمون پایان یابد؟')) submitNow();
  }));

  const timer = document.getElementById('timer');
  const box = document.getElementById('timer-box');
  function tick() {
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    timer.textContent = `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
    if (seconds <= 0) { submitNow(); return; }
    if (seconds < 60) box.classList.add('danger');
    seconds -= 1;
  }
  tick();
  timerId = setInterval(tick, 1000);

  window.addEventListener('online', () => {
    slides.forEach(slide => {
      const cached = localStorage.getItem(storageKey(slide));
      if (cached) save(slide, JSON.parse(cached), null, true);
    });
  });
  if (navigator.onLine) {
    slides.forEach(slide => {
      const cached = localStorage.getItem(storageKey(slide));
      if (cached) save(slide, JSON.parse(cached), null, true);
    });
  }
  document.addEventListener('visibilitychange', () => fetch(cfg.eventUrl, {
    method: 'POST', headers: {'X-CSRFToken': csrf, 'Content-Type': 'application/x-www-form-urlencoded'},
    body: new URLSearchParams({event: document.hidden ? 'tab_hidden' : 'tab_visible'}), keepalive: true,
  }).catch(() => {}));
  window.addEventListener('beforeunload', event => {
    if (!submitted) { event.preventDefault(); event.returnValue = ''; }
  });
  syncProgress();
});
