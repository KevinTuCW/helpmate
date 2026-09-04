// helpmate support widget — entry point.
//
// Embedding contract: one line on the host page.
//   <script type="module" src="/widget/index.js" data-api="/" data-api-key="..."></script>
//
// Everything renders inside a shadow root so the host page's global CSS (box-sizing
// resets, root font sizes, z-index wars) cannot reach in and break the panel.
import { createApi, resetSession } from './api.js';
import { createUI } from './ui.js';

// `document.currentScript` is null inside a module, so the embedding tag has to
// be found by matching its resolved src against this module's own URL. Getting
// this wrong fails silently: data-api-key would simply be dropped.
function embedTag() {
  for (const s of document.querySelectorAll('script[src]')) {
    if (s.src === import.meta.url) return s;
  }
  return null;
}

const cfg = embedTag()?.dataset ?? {};
const BASE = new URL(cfg.api || '/', location.href);
const HERE = new URL('.', import.meta.url);

const MOBILE = () => window.matchMedia('(max-width: 767px)').matches;
const DISMISSED = 'helpmate.dismissed';
// Names the assistant but keeps the answerable domain explicit — the knowledge
// base is DJI's, and a greeting that hides that invites questions it cannot answer.
const GREETING = '您好 👋 我是 Helpmate 客服助手，可以问我大疆产品、售后和订单相关的问题。';

const ICON = '<svg viewBox="0 0 24 24"><path d="M12 3C6.9 3 3 6.6 3 11c0 2.3 1.1 4.3 2.9 5.7L5 21l4.4-2.2c.8.2 1.7.3 2.6.3 5.1 0 9-3.6 9-8s-3.9-8-9-8z"/></svg>';

function mount() {
  const host = document.createElement('div');
  host.id = 'helpmate-widget';
  document.body.appendChild(host);
  const root = host.attachShadow({ mode: 'open' });

  const css = document.createElement('link');
  css.rel = 'stylesheet';
  css.href = new URL('style.css', HERE).href;
  root.appendChild(css);

  const fab = document.createElement('button');
  fab.className = 'fab';
  fab.setAttribute('aria-label', '打开在线客服');
  fab.innerHTML = ICON;

  const panel = document.createElement('section');
  panel.className = 'panel';
  panel.hidden = true;
  panel.innerHTML = `
    <div class="hd">
      <button class="back" aria-label="返回">‹</button>
      <b>Helpmate智能客服</b>
      <button class="reset" title="结束会话">⋯</button>
      <button class="close" aria-label="关闭">✕</button>
    </div>
    <div class="bd"></div>
    <div class="ft">
      <textarea rows="1" placeholder="输入你的问题…"></textarea>
      <button class="send" disabled>↑</button>
    </div>`;

  root.append(fab, panel);
  return { fab, panel };
}

const shell = mount();
const api = createApi({ base: BASE, apiKey: cfg.apiKey });

function open() {
  shell.panel.hidden = false;
  shell.fab.hidden = true;
  if (MOBILE()) document.documentElement.style.overflow = 'hidden';
  view.focus();
}

function close() {
  shell.panel.hidden = true;
  shell.fab.hidden = false;
  document.documentElement.style.overflow = '';
  sessionStorage.setItem(DISMISSED, '1');
}

let hotBox = null;
let lastQuestion = null;
let acTimer = null;
let acAbort = null;

function cancelTypeahead() {
  clearTimeout(acTimer);
  acAbort?.abort();
  acAbort = null;
}

async function ask(question) {
  // Clearing the composer fires no input event, so the debounce timer from the
  // last keystroke is still armed — without this it fires after the pick and
  // reopens the suggestion list over a conversation that has already moved on.
  cancelTypeahead();
  lastQuestion = question;
  hotBox?.remove();
  hotBox = null;
  view.pushUser(question);
  view.startAssistant();
  try {
    await api.chat(question, {
      stage: (d) => view.setStage(d.stage),
      token: (d) => view.appendToken(d.text),
      replace: (d) => view.replaceAssistant(d.text),
      done: (d) => {
        const answer = view.finishAssistant(d.hits || []);
        // Fired only after the answer is on screen, so it never adds to the wait.
        api.followups({
          question,
          answer,
          hit_titles: (d.hits || []).map((h) => h.title).filter(Boolean),
        })
          .then(({ questions }) => view.showFollowups(questions, ask))
          .catch(() => {});
      },
      error: () => {
        view.finishAssistant();
        view.showRetry('回答中断', () => ask(lastQuestion));
      },
    });
  } catch {
    view.finishAssistant();
    view.showRetry('连接中断', () => ask(lastQuestion));
  }
}

const view = createUI(shell.panel, { onSend: ask });
view.greet(GREETING);

// Suggestions are an enhancement: a failure here must leave the widget usable,
// so every one of these calls swallows its error and renders nothing.
api.hot()
  .then(({ questions }) => { hotBox = view.showHot(questions, ask); })
  .catch(() => {});

// Typeahead: debounced, and every in-flight request is aborted when the next
// keystroke arrives — otherwise a slow early response lands after a fast later
// one and overwrites the list with stale matches.
view.onInput((value) => {
  cancelTypeahead();
  if (value.length < 2) { view.hideTypeahead(); return; }
  acTimer = setTimeout(() => {
    acAbort = new AbortController();
    api.match(value, acAbort.signal)
      .then(({ questions }) => view.showTypeahead(questions, value, ask))
      .catch(() => {});
  }, 200);
});

shell.fab.addEventListener('click', open);
shell.panel.querySelector('.close').addEventListener('click', close);
shell.panel.querySelector('.back').addEventListener('click', close);
shell.panel.querySelector('.reset').addEventListener('click', () => {
  resetSession();
  view.clear();
  view.greet('会话已结束，有新问题随时问我。');
  hotBox = null;
});

// Auto-open once per browsing session, desktop only: on a phone the panel is
// full screen, so popping it unasked hijacks the page.
if (!MOBILE() && !sessionStorage.getItem(DISMISSED)) {
  setTimeout(() => { if (shell.panel.hidden) open(); }, 8000);
}
