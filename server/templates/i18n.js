// Lightweight en/zh localization for the static site.
// The preference lives under its own key (mtga-draft-tool-site.lang),
// separate from the desktop app's mtga.lang — localStorage is origin-scoped,
// and the Tauri webview (tauri://localhost) never shares storage with this
// GitHub Pages site, so one key cannot carry a choice across them anyway.
// Load this script BEFORE app.js / calendar.js on every page — they call
// I18N.t() while rendering dynamic content, and both re-render on the
// 'mtga:langchange' event fired when the visitor switches language.
(function () {
  'use strict';

  const STORAGE_KEY = 'mtga-draft-tool-site.lang';

  // Message dictionary. The deployed copy has the sentinel below replaced
  // with the JSON from i18n-messages.json by server/load.py::deploy_web_assets
  // (that file is the canonical source, loaded directly by
  // tests/server/test_web_i18n.py). The replacement double-escapes the JSON
  // into a JS string literal, so ONE JSON.parse here is correct: evaluating
  // the literal unescapes the first layer, JSON.parse handles the second.
  // The fallback keeps the raw template usable when served without the deploy
  // step — at worst translations degrade to the raw keys, the site never
  // crashes (t() guards missing buckets).
  let MESSAGES;
  try {
    MESSAGES = JSON.parse("__I18N_MESSAGES__");
  } catch {
    MESSAGES = {};
  }

  function currentLang() {
    try {
      const param = new URLSearchParams(window.location.search).get('lang');
      if (param === 'en' || param === 'zh') return param;
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'en' || stored === 'zh') return stored;
    } catch {
      // Storage disabled (private mode) — fall through to browser language.
    }
    const nav = (navigator.language || 'en').toLowerCase();
    return nav.startsWith('zh') ? 'zh' : 'en';
  }

  let lang = currentLang();

  /** Translate a message key; interpolates {name} placeholders via `vars`.
   *  Tolerates a missing or malformed dictionary (raw template served without
   *  the deploy-time injection, corrupted JSON, …) by falling back to the en
   *  bucket, then to the raw key — the site renders with visible keys instead
   *  of throwing. */
  function t(key, vars) {
    const bucket =
      (typeof MESSAGES === 'object' && MESSAGES && MESSAGES[lang]) ||
      (typeof MESSAGES === 'object' && MESSAGES && MESSAGES.en) ||
      {};
    let s = bucket[key] ?? key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        s = s.split(`{${k}}`).join(String(v));
      }
    }
    return s;
  }

  /** HTML-escape a data value before interpolating it into template HTML.
   *  Everything app.js / calendar.js renders from fetched data (report.json,
   *  manifest.json, the GitHub releases API) goes through this. */
  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /** Apply translations to every annotated static element (idempotent). */
  function applyStatic() {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-html]').forEach((el) => {
      // (the value is the developer-authored dictionary entry — the <strong>/
      // <code> markup is intentional and never user input)
      // nosemgrep
      el.innerHTML = t(el.dataset.i18nHtml);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    document.querySelectorAll('[data-i18n-title]').forEach((el) => {
      const msg = t(el.dataset.i18nTitle);
      el.title = msg;
      // Keep the accessible name localized too (e.g. the language switcher's
      // aria-label), not just the hover tooltip.
      if (el.hasAttribute('aria-label')) {
        el.setAttribute('aria-label', msg);
      }
    });
  }

  function setLang(next) {
    if (next !== 'en' && next !== 'zh') next = 'en';
    if (next === lang) {
      applyStatic();
      return;
    }
    lang = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Storage disabled — the switch still applies for this session.
    }
    applyStatic();
    // Dynamic renderers (warehouse tables, calendar grid, releases list)
    // re-render on this event.
    document.dispatchEvent(
      new CustomEvent('mtga:langchange', { detail: { lang: next } }),
    );
  }

  function init() {
    applyStatic();
    const switcher = document.getElementById('lang-switcher');
    if (switcher) {
      switcher.value = lang;
      switcher.addEventListener('change', () => setLang(switcher.value));
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.I18N = { t, getLang: () => lang, setLang, applyStatic, escapeHtml };
})();
