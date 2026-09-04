// Transport only: session identity, SSE parsing, the three suggestion calls.
// This module never touches the DOM, so it can be reasoned about (and swapped)
// without thinking about rendering at all.

const SESSION_KEY = 'helpmate.session';

// The id is persisted but the transcript is not: the backend remembers the turns
// (session_turns), so a refresh keeps coreference working — "那它续航呢" still
// resolves — without leaving a support conversation sitting in the user's
// localStorage.
export function sessionId() {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export function resetSession() {
  localStorage.removeItem(SESSION_KEY);
  return sessionId();
}

export function createApi({ base, apiKey }) {
  const url = (p) => new URL(p, base).toString();
  const headers = { 'Content-Type': 'application/json' };
  if (apiKey) headers['X-API-Key'] = apiKey;

  async function json(path, init) {
    const r = await fetch(url(path), { headers, ...init });
    if (!r.ok) throw new Error(`${path} → ${r.status}`);
    return r.json();
  }

  return {
    hot: () => json('suggest/hot'),
    match: (q, signal) => json(`suggest/match?q=${encodeURIComponent(q)}`, { signal }),
    followups: (body) => json('suggest/followups', {
      method: 'POST', body: JSON.stringify(body),
    }),

    // handlers: { stage, token, replace, done, error } — each gets the parsed data.
    async chat(question, handlers, signal) {
      const res = await fetch(url('chat/stream'), {
        method: 'POST', headers, signal,
        body: JSON.stringify({ question, session_id: sessionId() }),
      });
      if (!res.ok || !res.body) throw new Error(`chat → ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        // A network chunk can split an SSE frame anywhere, so a frame is only
        // dispatched once its terminating blank line has arrived.
        let cut;
        while ((cut = buf.indexOf('\n\n')) !== -1) {
          dispatch(buf.slice(0, cut), handlers);
          buf = buf.slice(cut + 2);
        }
      }
    },
  };
}

function dispatch(frame, handlers) {
  let event = 'message';
  let data = '';
  for (const line of frame.split('\n')) {
    if (line.startsWith('event: ')) event = line.slice(7);
    else if (line.startsWith('data: ')) data += line.slice(6);
  }
  if (!data) return;
  const fn = handlers[event];
  if (!fn) return;
  try {
    fn(JSON.parse(data));
  } catch {
    /* a malformed frame must not kill the rest of the stream */
  }
}
