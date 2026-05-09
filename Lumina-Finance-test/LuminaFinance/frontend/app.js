// LuminaFinance — auth-gated fetch, hydration, then animation.

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ── CSRF helper ─────────────────────────────────────────────
function csrfToken() {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : '';
}

async function postJSON(url, body) {
  return fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'Accept':       'application/json',
      'X-CSRFToken':  csrfToken(),
    },
    body: JSON.stringify(body ?? {}),
  });
}
const ALLOC_COLORS = {
  Cash:   ['#f5f5f7', '#9d9da3'],
  Stocks: ['#50fa7b', '#2bd9ff'],
  Crypto: ['#ff5555', '#ffb86c'],
  Gold:   ['#ffd86c', '#ffb86c'],
  Bonds:  ['#a78bfa', '#60a5fa'],
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const get = (obj, path) => path.split('.').reduce((o, k) => (o == null ? o : o[k]), obj);

// ── 1. fetch + hydrate ──────────────────────────────────────
async function loadDashboard() {
  const res = await fetch('/api/dashboard/', {
    credentials: 'same-origin',
    headers: { 'Accept': 'application/json' },
  });
  if (res.status === 401) return { __unauthenticated: true };
  if (!res.ok) {
    console.error('Dashboard fetch failed:', res.status);
    return null;
  }
  return res.json();
}

function hydrate(data) {
  // text bindings
  $$('[data-bind]').forEach(el => {
    const key = el.dataset.bind;
    const v = bindResolve(data, key);
    if (v != null) el.textContent = v;
  });

  // counter targets
  $$('[data-bind-target]').forEach(el => {
    const v = get(data, el.dataset.bindTarget);
    if (v != null) el.dataset.target = String(v);
  });

  // trend pct
  $$('[data-bind-trend]').forEach(el => {
    const v = get(data, el.dataset.bindTrend);
    if (v != null) el.textContent = (v >= 0 ? '+' : '') + v.toFixed(1) + '%';
  });

  // allocation rows
  const allocHost = $('[data-bind-allocations]');
  if (allocHost && data.allocation) {
    allocHost.innerHTML = data.allocation.map(row => {
      const [from, to] = ALLOC_COLORS[row.label] ?? ['#50fa7b', '#2bd9ff'];
      return `
        <div class="alloc-row" title="$${row.value.toLocaleString('en-US', { minimumFractionDigits: 2 })} (${row.label})">
          <span class="alloc-label">${row.label}</span>
          <div class="alloc-bar" data-reveal-bar style="--pct: ${row.pct.toFixed(1)}%; --bar-from: ${from}; --bar-to: ${to}"></div>
          <span class="alloc-pct">${row.pct.toFixed(0)}%</span>
        </div>`;
    }).join('');
  }

  // forecast strip
  const stripHost = $('[data-bind-forecast]');
  if (stripHost && data.forecast) {
    stripHost.innerHTML = data.forecast.map((cell, idx) => `
      <div class="forecast-cell" style="cursor: pointer;" data-month="${cell.month}" data-delta="${cell.delta}" title="Balance: $${cell.value.toLocaleString('en-US', { minimumFractionDigits: 2 })}&#10;Monthly Change: ${cell.delta < 0 ? '-' : '+'}$${Math.abs(cell.delta).toLocaleString('en-US', { minimumFractionDigits: 2 })}">
        <div class="month">${cell.month}</div>
        <div class="value" data-counter data-target="${cell.value}" data-prefix="$">$0</div>
        <div class="delta ${cell.delta < 0 ? 'delta--down' : ''}">${cell.delta >= 0 ? '+' : ''}${Math.round(cell.delta)}</div>
      </div>`).join('');
  }

  // transactions
  const txnHost = $('[data-bind-transactions]');
  const txnTitle = document.querySelector('#transactions h2');
  
  if (txnHost && data.recent_transactions) {
    const fmtDate = iso => new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    window.__allTxns = data.recent_transactions;

    const renderTxns = (txns) => {
      if (txns.length === 0) {
        txnHost.innerHTML = `<li class="txn-row"><div class="txn-body"><span class="txn-desc" style="color: var(--ink-mute);">No transactions found.</span></div></li>`;
        return;
      }
      txnHost.innerHTML = txns.map(t => {
        const isIn = t.kind === 'INCOME';
        const sign = isIn ? '+' : '−';
        return `
          <li class="txn-row">
            <span class="txn-date">${t.isProjected ? 'Projected' : fmtDate(t.date)}</span>
            <div class="txn-body">
              <span class="txn-desc">${t.description}</span>
              <span class="txn-cat" data-cat="${t.category}" style="cursor: pointer;">${t.category}</span>
            </div>
            <span class="txn-amount ${isIn ? 'txn-amount--in' : 'txn-amount--out'}">${sign}$${t.amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
            ${!t.isProjected ? `<button class="txn-delete" data-id="${t.id}" title="Delete Transaction">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>` : ''}
          </li>`;
      }).join('');
    };

    // Initial render
    renderTxns(window.__allTxns);
    if (txnTitle) txnTitle.textContent = "Recent Activity";

    // Search logic
    const searchInput = $('#txn-search');
    if (searchInput) {
      const newSearch = searchInput.cloneNode(true);
      searchInput.parentNode.replaceChild(newSearch, searchInput);
      newSearch.addEventListener('input', (e) => {
        const q = e.target.value.toLowerCase();
        const filtered = window.__allTxns.filter(t => 
          t.description.toLowerCase().includes(q) || 
          t.category.toLowerCase().includes(q)
        );
        renderTxns(filtered);
      });
    }

    // Badge filtering & Deletion logic
    txnHost.addEventListener('click', async (e) => {
      const badge = e.target.closest('.txn-cat');
      if (badge && !window.__allTxns[0]?.isProjected) {
        const cat = badge.dataset.cat;
        if (searchInput) searchInput.value = cat;
        if (resetButton) resetButton.style.display = 'block';
        renderTxns(window.__allTxns.filter(t => t.category === cat));
      }
      
      const delBtn = e.target.closest('.txn-delete');
      if (delBtn) {
        const id = delBtn.dataset.id;
        try {
          const res = await fetch(`/api/delete-transaction/${id}/`, {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: { 'X-CSRFToken': csrfToken() }
          });
          if (res.ok) boot(); // Re-fetch
        } catch(err) { console.error(err); }
      }
    });

    const resetButton = $('#txn-reset');
    if (resetButton) {
      resetButton.addEventListener('click', () => {
        if (txnTitle) txnTitle.textContent = "Recent Activity";
        window.__allTxns = data.recent_transactions;
        if (searchInput) searchInput.value = '';
        const countLabel = document.querySelector('[data-bind="recent-count"]');
        if (countLabel) countLabel.textContent = `${window.__allTxns.length} in last 30 days`;
        renderTxns(window.__allTxns);
        $$('.forecast-cell').forEach(c => c.style.background = '');
        resetButton.style.display = 'none';
      });
    }

    // Interactive Forecast Clicks
    setTimeout(() => {
      $$('.forecast-cell').forEach(cell => {
        cell.addEventListener('click', () => {
          // Visual selection
          $$('.forecast-cell').forEach(c => c.style.background = '');
          cell.style.background = 'rgba(255, 255, 255, 0.1)';
          
          if (resetButton) resetButton.style.display = 'block';
          
          const monthName = cell.dataset.month;
          if (txnTitle) txnTitle.textContent = `Projected Activity: ${monthName}`;
          
          const currentSearch = $('#txn-search');
          if (currentSearch) currentSearch.value = '';
          
          // Generate projected transactions for this future month based on recent habits
          const incomeTxns = data.recent_transactions.filter(t => t.kind === 'INCOME');
          const avgIncome = incomeTxns.length ? incomeTxns.reduce((sum, t) => sum + t.amount, 0) / incomeTxns.length : 8000;
          
          const delta = parseFloat(cell.dataset.delta);
          const totalExpenses = avgIncome - delta; // delta is net change (usually negative)
          
          // Add random jitter so each click/month feels different (+/- 5%)
          const jitter = () => 1 + (Math.random() * 0.1 - 0.05);
          
          const projected = [];
          projected.push({ isProjected: true, kind: 'INCOME', category: 'Salary', description: 'Payroll Deposit', amount: avgIncome * jitter() });
          projected.push({ isProjected: true, kind: 'EXPENSE', category: 'Rent', description: 'Monthly Rent', amount: totalExpenses * 0.55 * jitter() });
          
          const remainingExpenses = totalExpenses * 0.45;
          const numSmall = Math.floor(Math.random() * 15) + 20; // 20 to 34 small expenses
          
          const expTypes = [
            { cat: 'Groceries', desc: ['Whole Foods', 'Trader Joe\'s', 'Kroger', 'Safeway', 'Aldi'] },
            { cat: 'Dining', desc: ['Local Restaurant', 'Coffee Shop', 'Uber Eats', 'Doordash', 'Starbucks'] },
            { cat: 'Transport', desc: ['Uber', 'Lyft', 'Gas Station', 'Subway Pass'] },
            { cat: 'Subscriptions', desc: ['Netflix', 'Spotify', 'Amazon Prime', 'Gym Membership'] },
            { cat: 'Other', desc: ['Amazon', 'Target', 'Pharmacy', 'Miscellaneous'] }
          ];
          
          let generatedSmallWeight = 0;
          for (let i = 0; i < numSmall; i++) {
            const type = expTypes[Math.floor(Math.random() * expTypes.length)];
            const desc = type.desc[Math.floor(Math.random() * type.desc.length)];
            const weight = (Math.random() * 0.8 + 0.2);
            projected.push({
              isProjected: true,
              kind: 'EXPENSE',
              category: type.cat,
              description: desc,
              amount: 0,
              weight: weight
            });
            generatedSmallWeight += weight;
          }
          
          const scale = remainingExpenses / generatedSmallWeight;
          projected.forEach(p => {
             if (p.weight) {
                 p.amount = p.weight * scale * jitter();
                 delete p.weight;
             }
          });
          
          window.__allTxns = projected;
          const countLabel = document.querySelector('[data-bind="recent-count"]');
          if (countLabel) countLabel.textContent = `${projected.length} projected activity`;
          
          renderTxns(projected);
        });
      });
    }, 200);
  }

  // profile initial
  const initialEl = document.querySelector('[data-bind="profile.initial"]');
  if (initialEl && data.user?.name) initialEl.textContent = data.user.name.charAt(0).toUpperCase();

  // runway label tier
  const runwayLabel = $('[data-bind-runway-label]');
  if (runwayLabel && data.runway_months != null) {
    const months = data.runway_months;
    if (months >= 12)      runwayLabel.textContent = 'Healthy';
    else if (months >= 6)  runwayLabel.textContent = 'Stable';
    else if (months >= 3)  { runwayLabel.textContent = 'Tight'; runwayLabel.className = 'trend trend--down'; }
    else                   { runwayLabel.textContent = 'Critical'; runwayLabel.className = 'trend trend--down'; }
  }

  // Draw SVG Trend Line
  const chart = $('#forecast-chart');
  if (chart && data.forecast && data.forecast.length > 0) {
    const values = data.forecast.map(c => c.value);
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal || 1; // Prevent div/0
    
    const pts = data.forecast.map((c, i) => {
      const x = (i / (data.forecast.length - 1)) * 1000;
      const normalized = (c.value - minVal) / range;
      const y = 100 - (normalized * 80); // scale between 20 and 100
      return `${x},${y}`;
    });
    chart.innerHTML = `
      <path d="M ${pts.join(' L ')}" fill="none" stroke="var(--emerald)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" style="filter: drop-shadow(0 8px 12px var(--emerald-soft));" />
      <path d="M 0,120 L ${pts.join(' L ')} L 1000,120 Z" fill="url(#chartGrad)" opacity="0.3" />
      <defs>
        <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--emerald)" stop-opacity="0.8"/>
          <stop offset="100%" stop-color="var(--emerald)" stop-opacity="0"/>
        </linearGradient>
      </defs>
    `;
  }
  
  // Theme Toggle
  const themeBtn = $('#theme-toggle');
  if (themeBtn && !window.__themeHooked) {
    window.__themeHooked = true;
    themeBtn.addEventListener('click', (e) => {
      e.preventDefault();
      document.body.classList.toggle('theme-light');
      const isLight = document.body.classList.contains('theme-light');
      const tip = themeBtn.querySelector('.tip');
      if (tip) tip.textContent = isLight ? 'Dark Mode' : 'Light Mode';
    });
  }

  // Modal logic
  const fab = $('#fab-add-txn');
  const modal = $('#txn-modal');
  const modalContent = $('#txn-modal-content');
  const closeBtn = $('#txn-modal-close');
  const form = $('#add-txn-form');

  if (fab && modal && closeBtn && form && !window.__modalHooked) {
    window.__modalHooked = true;
    const showModal = () => {
      modal.style.display = 'flex';
      setTimeout(() => {
        modalContent.style.opacity = '1';
        modalContent.style.transform = 'scale(1)';
      }, 10);
    };
    const hideModal = () => {
      modalContent.style.opacity = '0';
      modalContent.style.transform = 'scale(0.95)';
      setTimeout(() => modal.style.display = 'none', 300);
    };
    
    fab.addEventListener('click', showModal);
    closeBtn.addEventListener('click', hideModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) hideModal();
    });
    
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.style.opacity = '0.5';
      submitBtn.textContent = 'Adding...';
      
      const formData = new FormData(form);
      try {
        const res = await postJSON('/api/add-transaction/', Object.fromEntries(formData));
        if (res.ok) {
          hideModal();
          form.reset();
          boot(); // Re-fetch dashboard data
        }
      } catch (err) {
        console.error(err);
      } finally {
        submitBtn.style.opacity = '1';
        submitBtn.textContent = 'Add Transaction';
      }
    });
  }
}

function bindResolve(data, key) {
  switch (key) {
    case 'period':
      return new Date().toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
    case 'updated':
      return 'Updated just now';
    case 'burn.method-label':
      return `${data.burn?.kept ?? 0} kept · ${data.burn?.dropped ?? 0} outliers dropped`;
    case 'burn.dropped-label':
      return `${data.burn?.dropped ?? 0} one-shots filtered`;
    case 'alloc-count':
      return `${data.allocation?.length ?? 0} asset classes`;
    case 'top_mover.subtitle':
      return data.top_mover ? `${data.top_mover.ticker} · ${data.top_mover.quantity} units` : '—';
    case 'top_mover.trend':
      return data.top_mover ? `${data.top_mover.pct_change >= 0 ? '+' : ''}${data.top_mover.pct_change.toFixed(1)}% (7d)` : '—';
    case 'forecast.method':
      return `${data.burn?.method ?? 'MA3'} · IQR filter`;
    case 'recent-count':
      return `${data.recent_transactions?.length ?? 0} in last 30 days`;
    case 'profile.initial':
      return null;  // handled imperatively after innerHTML set
    default:
      return get(data, key);
  }
}

// ── 2. observers (run after hydration so they see real targets) ───
function attachObservers() {
  const revealObs = new IntersectionObserver((entries, o) => {
    entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('is-revealed'); o.unobserve(e.target); } });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.1 });
  $$('[data-reveal]').forEach(el => revealObs.observe(el));

  const counterObs = new IntersectionObserver((entries, o) => {
    entries.forEach(e => { if (e.isIntersecting) { tweenCounter(e.target); o.unobserve(e.target); } });
  }, { threshold: 0.4 });
  $$('[data-counter]').forEach(el => counterObs.observe(el));

  const bars = $$('[data-reveal-bar]');
  const barObs = new IntersectionObserver((entries, o) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      setTimeout(() => e.target.classList.add('is-visible'), bars.indexOf(e.target) * 90);
      o.unobserve(e.target);
    });
  }, { threshold: 0.5 });
  bars.forEach(el => barObs.observe(el));
}

function tweenCounter(el) {
  const target = parseFloat(el.dataset.target ?? '0');
  const prefix = el.dataset.prefix ?? '';
  const suffix = el.dataset.suffix ?? '';
  const decimals = (el.dataset.target ?? '').split('.')[1]?.length ?? 0;
  const fmt = v => prefix + v.toLocaleString('en-US', {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  }) + suffix;

  if (reduceMotion || isNaN(target)) { el.textContent = fmt(target || 0); return; }

  const duration = 1400;
  const start = performance.now();
  const tick = (now) => {
    const t = Math.min((now - start) / duration, 1);
    el.textContent = fmt(target * (1 - Math.pow(1 - t, 3)));
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// ── 3. dock — smooth-scroll nav + scroll-spy ───────────────
function setActiveDock(targetId) {
  $$('.dock-item').forEach(i => {
    i.classList.toggle('is-active', i.getAttribute('href') === '#' + targetId);
  });
}

$$('.dock-item').forEach(item => {
  item.addEventListener('click', e => {
    const href = item.getAttribute('href');
    if (!href || !href.startsWith('#')) return;
    const target = document.getElementById(href.slice(1));
    if (!target) return;
    e.preventDefault();
    target.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'start' });
    setActiveDock(href.slice(1));
    history.replaceState(null, '', href);
  });
});

function attachDockHiding() {
  const dockNav = document.querySelector('.dock');
  if (!dockNav) return;
  
  let lastScrollY = window.scrollY;
  let dockTimeout;
  
  // Hide initially if not scrolling
  dockTimeout = setTimeout(() => {
    dockNav.classList.add('dock--hidden');
  }, 2000);

  window.addEventListener('scroll', () => {
    const currentScrollY = window.scrollY;
    
    if (currentScrollY > lastScrollY) {
      // Scrolling down -> show
      dockNav.classList.remove('dock--hidden');
    } else if (currentScrollY < lastScrollY) {
      // Scrolling up -> hide
      dockNav.classList.add('dock--hidden');
    }
    
    lastScrollY = currentScrollY;

    clearTimeout(dockTimeout);
    dockTimeout = setTimeout(() => {
      dockNav.classList.add('dock--hidden');
    }, 1500);
  }, { passive: true });
}

function attachScrollSpy() {
  const sections = ['dashboard', 'portfolio', 'forecast', 'transactions', 'settings']
    .map(id => document.getElementById(id))
    .filter(Boolean);

  // Top half of viewport rules; whichever section's top is most recently above
  // the 35% line wins.
  const spy = new IntersectionObserver((entries) => {
    const visible = entries
      .filter(e => e.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
    if (visible[0]) setActiveDock(visible[0].target.id);
  }, { rootMargin: '-35% 0px -55% 0px', threshold: [0, 0.5, 1] });

  sections.forEach(s => spy.observe(s));
}

// ── auth flow ───────────────────────────────────────────────
const overlay = $('[data-auth-overlay]');
const authForm = $('[data-auth-form]');
const authError = $('[data-auth-error]');

function showOverlay() {
  if (!overlay) return;
  overlay.hidden = false;
  document.body.style.overflow = 'hidden';
  setTimeout(() => authForm?.querySelector('input[name="email"]')?.focus(), 50);
}
function hideOverlay() {
  if (!overlay) return;
  overlay.hidden = true;
  document.body.style.overflow = '';
}

let isRegisterMode = false;
const toggleBtn = $('#auth-toggle-btn');
if (toggleBtn) {
  toggleBtn.addEventListener('click', (e) => {
    e.preventDefault();
    isRegisterMode = !isRegisterMode;
    
    $('#auth-title-text').textContent = isRegisterMode ? 'Create account' : 'Welcome back';
    $('#auth-sub-text').textContent = isRegisterMode ? 'Join LuminaFinance today.' : 'Sign in to LuminaFinance.';
    $('#auth-name-field').style.display = isRegisterMode ? 'block' : 'none';
    $('#name').required = isRegisterMode;
    
    authForm.querySelector('.auth-submit-label').textContent = isRegisterMode ? 'Register' : 'Sign in';
    $('#auth-toggle-text').textContent = isRegisterMode ? 'Already have an account?' : "Don't have an account?";
    toggleBtn.textContent = isRegisterMode ? 'Sign in here' : 'Register here';
    
    authError.hidden = true;
  });
}

authForm?.addEventListener('submit', async (e) => {
  e.preventDefault();
  authError.hidden = true;
  const submitBtn = authForm.querySelector('.auth-submit');
  const label = authForm.querySelector('.auth-submit-label');
  submitBtn.disabled = true;
  label.textContent = isRegisterMode ? 'Registering…' : 'Signing in…';

  const fd = new FormData(authForm);
  const endpoint = isRegisterMode ? '/api/register/' : '/api/login/';
  const payload = {
    email:    fd.get('email'),
    password: fd.get('password'),
  };
  if (isRegisterMode) payload.name = fd.get('name');
  
  const res = await postJSON(endpoint, payload);

  if (res.ok) {
    hideOverlay();
    await boot();   // re-fetch dashboard with the now-authenticated session
  } else {
    const body = await res.json().catch(() => ({}));
    if (isRegisterMode) {
      authError.textContent = body.error === 'email_taken' 
        ? 'Email is already in use.' 
        : 'Registration failed. Try again.';
    } else {
      authError.textContent = body.error === 'invalid_credentials'
        ? 'Wrong email or password.'
        : 'Sign in failed. Try again.';
    }
    authError.hidden = false;
  }
  submitBtn.disabled = false;
  label.textContent = isRegisterMode ? 'Register' : 'Sign in';
});

document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-action="logout"]');
  if (!btn) return;
  btn.disabled = true;
  await postJSON('/api/logout/');
  // Reset the dashboard scroll/state and prompt for credentials again.
  showOverlay();
  btn.disabled = false;
});

// ── boot ────────────────────────────────────────────────────
async function boot() {
  const data = await loadDashboard();
  if (!data) {
    // Network or 5xx — don't show the login overlay for those, just bail.
    return;
  }
  if (data.__unauthenticated) {
    showOverlay();
    return;
  }
  hydrate(data);
  attachObservers();
  attachDockHiding();
  attachScrollSpy();
}

boot();
