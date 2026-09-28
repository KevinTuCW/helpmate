// Rendering only: this module knows about DOM nodes and nothing about fetch.
// index.js drives it by calling these methods as transport events arrive.

const STAGE_TEXT = {
  route: '正在理解问题…',
  retrieve: '正在检索知识库…',
  retrieved: '已找到相关文档，正在整理…',
  act: '正在查询订单…',
  delegate: '正在处理售后方案…',
  generate: '正在组织回答…',
};

export function renderOffer(mount, payload, { onAccept, onDecline, onExpired }) {
  const sourceText = `${payload.offer.label || ''} ${payload.escape_hatch || ''}`;
  const english = !/[\u3400-\u9fff]/.test(sourceText) && /[A-Za-z]/.test(sourceText);
  const copy = english ? {
    fallback: 'Available option', accept: 'Accept', decline: 'I still want to return it',
    processing: 'Processing…', accepted: 'Accepted', declined: 'Return requested',
    expiredButton: 'Expired', expired: 'This offer expired. I’m requesting a new option now…',
    failed: 'This option could not be processed. Please ask the agent for a new option.', currency: '$',
  } : {
    fallback: '为你准备的方案', accept: '接受', decline: '还是要退',
    processing: '处理中…', accepted: '已受理', declined: '已申请退货',
    expiredButton: '已失效', expired: '方案已失效，正在为你重新获取可用方案…',
    failed: '方案未能执行，请让客服重新提供方案。', currency: '¥',
  };
  const card = document.createElement('div');
  card.className = 'offer-card';

  const label = document.createElement('div');
  label.className = 'offer-label';
  label.textContent = payload.offer.label || copy.fallback;

  const value = document.createElement('div');
  value.className = 'offer-value';
  value.textContent = `${copy.currency}${Number(payload.offer.value).toFixed(2)}`;

  const row = document.createElement('div');
  row.className = 'offer-actions';
  const accept = document.createElement('button');
  accept.className = 'offer-accept';
  accept.textContent = copy.accept;
  const decline = document.createElement('button');
  decline.className = 'offer-decline';
  decline.textContent = copy.decline;

  const idem = crypto.randomUUID();

  const status = document.createElement('div');
  status.className = 'offer-status';
  status.setAttribute('role', 'status');
  status.setAttribute('aria-live', 'polite');

  const lockCard = (selected) => {
    card.classList.add('offer-final');
    accept.disabled = true;
    decline.disabled = true;
    accept.setAttribute('aria-pressed', selected === 'accept' ? 'true' : 'false');
    decline.setAttribute('aria-pressed', selected === 'decline' ? 'true' : 'false');
  };

  // Only the latest offer may be acted on. A newly rendered offer supersedes
  // every older card in the conversation.
  mount.querySelectorAll('.offer-card:not(.offer-final)').forEach((oldCard) => {
    oldCard.classList.add('offer-final', 'offer-superseded');
    oldCard.querySelectorAll('button').forEach((button) => { button.disabled = true; });
  });

  accept.addEventListener('click', async () => {
    lockCard('accept');
    accept.textContent = copy.processing;
    try {
      const r = await onAccept({
        offer_token: payload.offer.offer_token,
        idempotency_key: idem,
      });
      if (r.data.status === 'executed' || r.data.status === 'already_executed') {
        card.classList.add('offer-done');
        accept.textContent = copy.accepted;
        status.textContent = copy.accepted;
        return;
      }
      const expired = r.data?.guardrail?.code === 'TOKEN_EXPIRED'
        || r.data?.next_action === 'reissue_offer';
      card.classList.add(expired ? 'offer-expired' : 'offer-failed');
      accept.textContent = expired ? copy.expiredButton : copy.accept;
      status.textContent = expired ? copy.expired : (r.data?.detail || copy.failed);
      if (expired) onExpired?.();
    } catch {
      card.classList.add('offer-failed');
      accept.textContent = copy.accept;
      status.textContent = copy.failed;
    }
  });
  decline.addEventListener('click', () => {
    lockCard('decline');
    decline.textContent = copy.declined;
    status.textContent = copy.declined;
    onDecline(copy.decline);
  });

  row.append(accept, decline);

  const escape = document.createElement('div');
  escape.className = 'offer-escape';
  escape.textContent = payload.escape_hatch || '';

  card.append(label, value, row, status, escape);
  mount.append(card);
  return card;
}

export function createUI(panel, { onSend }) {
  const bd = panel.querySelector('.bd');
  const ta = panel.querySelector('textarea');
  const send = panel.querySelector('.send');

  let current = null;   // the assistant bubble being streamed into

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };
  const scroll = () => { bd.scrollTop = bd.scrollHeight; };

  // --- typeahead panel, anchored above the input -----------------------------
  const ac = el('div', 'ac');
  ac.hidden = true;
  panel.querySelector('.ft').appendChild(ac);
  let acItems = [];
  let acIndex = -1;

  const closeAc = () => {
    ac.hidden = true;
    ac.innerHTML = '';
    acItems = [];
    acIndex = -1;
  };
  const highlight = (i) => {
    acIndex = i;
    acItems.forEach((n, k) => n.classList.toggle('on', k === i));
  };

  function resetComposer() {
    ta.value = '';
    ta.style.height = 'auto';
    // Assigning `value` fires no input event, so the button state is set here.
    send.disabled = true;
  }

  function submit() {
    closeAc();
    const q = ta.value.trim();
    if (!q || send.disabled) return;
    resetComposer();
    onSend(q);
  }

  // Sending a suggestion clears the composer too. Without this the half-typed
  // fragment that produced the suggestion stays behind, and the user has to
  // delete it before asking anything else.
  function pick(q, onPick) {
    closeAc();
    resetComposer();
    onPick(q);
  }

  ta.addEventListener('input', () => {
    send.disabled = !ta.value.trim() || current !== null;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 96)}px`;
  });

  ta.addEventListener('keydown', (e) => {
    if (!ac.hidden && acItems.length) {
      if (e.key === 'ArrowDown') {
        e.preventDefault(); highlight((acIndex + 1) % acItems.length); return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        highlight((acIndex - 1 + acItems.length) % acItems.length); return;
      }
      if (e.key === 'Escape') { e.preventDefault(); closeAc(); return; }
      if (e.key === 'Enter' && acIndex >= 0) {
        e.preventDefault(); acItems[acIndex].click(); return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  });

  send.addEventListener('click', submit);

  return {
    greet(text) {
      bd.appendChild(el('div', 'msg a', text));
      scroll();
    },

    // Opening suggestions: an empty input box is the single biggest reason a
    // support widget goes unused.
    showHot(questions, onPick) {
      if (!questions.length) return null;
      const wrap = el('div');
      wrap.appendChild(el('div', 'lab', '大家都在问'));
      const box = el('div', 'hot');
      for (const q of questions) {
        const b = el('button', null, q);
        b.addEventListener('click', () => pick(q, onPick));
        box.appendChild(b);
      }
      wrap.appendChild(box);
      bd.appendChild(wrap);
      scroll();
      return wrap;
    },

    pushUser(text) {
      bd.appendChild(el('div', 'msg u', text));
      scroll();
    },

    // Opens an assistant bubble with a live stage line above it.
    startAssistant() {
      const stage = el('div', 'stage', STAGE_TEXT.route);
      const msg = el('div', 'msg a');
      const body = el('span');
      const cursor = el('span', 'cursor');
      msg.append(body, cursor);
      bd.append(stage, msg);
      current = { stage, msg, body, cursor, text: '' };
      send.disabled = true;
      scroll();
    },

    setStage(name) {
      if (current) current.stage.textContent = STAGE_TEXT[name] || '处理中…';
      scroll();
    },

    appendToken(text) {
      if (!current) return;
      current.text += text;
      current.body.textContent = current.text;
      scroll();
    },

    // The output guardrail's final verdict arrives after the text is on screen,
    // so a block is a replacement, not a prevention.
    replaceAssistant(text) {
      if (!current) return;
      current.text = text;
      current.body.textContent = text;
    },

    // `hits` is citation metadata only (title / section / url) — the backend
    // deliberately does not ship chunk text to an embedded widget.
    finishAssistant(hits = []) {
      if (!current) return '';
      current.stage.remove();
      current.cursor.remove();
      const { msg, body, text } = current;
      current = null;
      send.disabled = !ta.value.trim();

      if (hits.length) {
        const box = el('details', 'cites');
        const list = el('ol');
        for (const h of hits) {
          const li = document.createElement('li');
          li.dataset.n = String(h.n);
          if (h.url) {
            const a = el('a', null, h.title || h.url);
            a.href = h.url;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            li.appendChild(a);
          } else {
            li.textContent = h.title || `文档 ${h.n}`;
          }
          if (h.section) li.append(` · ${h.section}`);
          list.appendChild(li);
        }
        box.append(el('summary', null, `已参考 ${hits.length} 篇文档`), list);
        msg.appendChild(box);

        // Turn the [1] markers the model wrote into clickable jumps.
        body.textContent = '';
        for (const part of text.split(/(\[\d+\])/g)) {
          const m = /^\[(\d+)\]$/.exec(part);
          if (!m) { body.append(part); continue; }
          const sup = el('span', 'sup', part);
          sup.addEventListener('click', () => {
            box.open = true;
            for (const li of list.children) li.classList.toggle('on', li.dataset.n === m[1]);
          });
          body.appendChild(sup);
        }
      }
      scroll();
      return text;
    },

    showFollowups(questions, onPick) {
      if (!questions.length) return;
      bd.appendChild(el('div', 'lab', '您可能还想问'));
      const box = el('div', 'chips');
      for (const q of questions) {
        const b = el('button', null, q);
        b.addEventListener('click', () => pick(q, onPick));
        box.appendChild(b);
      }
      bd.appendChild(box);
      scroll();
    },

    showRetry(message, onRetry) {
      const line = el('div', 'stage', message);
      const btn = el('button', 'retry', '重试');
      btn.addEventListener('click', () => { line.remove(); onRetry(); });
      line.appendChild(btn);
      bd.appendChild(line);
      scroll();
    },

    showOffer(payload, handlers) {
      const card = renderOffer(bd, payload, handlers);
      scroll();
      return card;
    },

    showTypeahead(questions, prefix, onPick) {
      closeAc();
      if (!questions.length) return;
      for (const q of questions) {
        const row = document.createElement('div');
        // Highlight the typed fragment so it reads as a match, not a random list.
        const at = q.indexOf(prefix);
        if (at === -1) {
          row.textContent = q;
        } else {
          row.append(q.slice(0, at), el('b', null, prefix), q.slice(at + prefix.length));
        }
        row.addEventListener('click', () => pick(q, onPick));
        ac.appendChild(row);
        acItems.push(row);
      }
      ac.hidden = false;
    },

    hideTypeahead: closeAc,
    onInput(fn) { ta.addEventListener('input', () => fn(ta.value.trim())); },
    clear() { bd.innerHTML = ''; closeAc(); },
    focus() { ta.focus({ preventScroll: true }); },
  };
}
