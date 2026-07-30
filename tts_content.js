(function () {
  'use strict';

  if (window.__rmTtsInjected) return;
  window.__rmTtsInjected = true;

  const BTN_ID = 'rm-tts-fab';

  function injectButton() {
    if (document.getElementById(BTN_ID)) return;

    const btn = document.createElement('button');
    btn.id = BTN_ID;
    btn.innerHTML = '\u{1F4AC}';
    btn.title = 'Speak as Cartman';
    btn.style.cssText = [
      'position:fixed',
      'bottom:20px',
      'right:20px',
      'width:44px',
      'height:44px',
      'border-radius:50%',
      'background:#d94545',
      'border:2px solid #fff',
      'box-shadow:0 4px 12px rgba(0,0,0,0.3)',
      'cursor:pointer',
      'z-index:2147483647',
      'font-size:20px',
      'line-height:1',
      'padding:0',
      'display:flex',
      'align-items:center',
      'justify-content:center',
      'transition:transform 0.15s, background 0.15s',
    ].join(';');

    btn.addEventListener('mouseenter', () => {
      btn.style.transform = 'scale(1.1)';
      btn.style.background = '#e05555';
    });
    btn.addEventListener('mouseleave', () => {
      btn.style.transform = 'scale(1)';
      btn.style.background = '#d94545';
    });

    btn.addEventListener('click', () => {
      const text = getChatText();
      if (text && text.trim()) {
        speakAsCartman(text.trim());
      } else {
        showBubble('No text found to read');
      }
    });

    document.body.appendChild(btn);
  }

  function getChatText() {
    // 1. Selected text takes priority
    const sel = window.getSelection();
    if (sel && sel.toString().trim().length > 10) {
      return sel.toString().trim();
    }

    // 2. Try common chat container selectors
    const chatSelectors = [
      '[data-testid*="chat"]',
      '[data-testid*="message"]',
      '[class*="chat-message"]',
      '[class*="prose"]',
      '[class*="markdown"]',
      '[class*="response"]',
      '[class*="answer"]',
      '[class*="assistant"]',
      '[role="log"]',
      '[role="article"]',
      'main',
      'article',
    ];

    for (const sel of chatSelectors) {
      const els = document.querySelectorAll(sel);
      if (els.length > 0) {
        // Grab the last few elements (most recent responses)
        const recent = Array.from(els).slice(-3);
        const text = recent.map(e => e.innerText).join('\n').trim();
        if (text.length > 20) return text;
      }
    }

    // 3. Fallback: entire body text (trimmed to last 3000 chars for relevance)
    const bodyText = document.body.innerText.trim();
    if (bodyText.length > 20) {
      return bodyText.slice(-3000);
    }

    return null;
  }

  function extractKeyPoints(text) {
    const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
    const points = [];

    for (const line of lines) {
      if (/^#{1,6}\s/.test(line)) continue;
      if (/^```/.test(line)) continue;
      if (/^@\//.test(line)) continue;
      if (/^[-*]\s\*\*/.test(line)) {
        const m = line.match(/\*\*(.+?)\*\*/);
        if (m) points.push(m[1]);
      } else if (/^[-*]\s/.test(line)) {
        const clean = line.replace(/^[-*]\s/, '');
        const firstSentence = clean.split(/[.!?]/)[0];
        if (firstSentence.length > 5) points.push(firstSentence.trim());
      } else if (/\*\*(.+?)\*\*/.test(line)) {
        const m = line.match(/\*\*(.+?)\*\*/);
        if (m) points.push(m[1]);
      } else if (line.length > 20 && line.length < 200 && !/^http/.test(line)) {
        const firstSentence = line.split(/[.!?]/)[0];
        if (firstSentence.length > 10) points.push(firstSentence.trim());
      }
      if (points.length >= 5) break;
    }

    if (points.length === 0) {
      const sentences = text.split(/[.!?]\s/).filter(s => s.trim().length > 10);
      return sentences.slice(0, 3).map(s => s.trim());
    }

    return points.slice(0, 5);
  }

  const CARTMAN_API = 'http://127.0.0.1:5151';

  async function fetchCartmanSummary(text) {
    try {
      const res = await fetch(`${CARTMAN_API}/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error('API error');
      const data = await res.json();
      return data.response || null;
    } catch (e) {
      console.warn('[Cartman TTS] API unavailable, using fallback', e);
      return null;
    }
  }

  function cartmanizeFallback(points) {
    if (points.length === 0) return "Ay! There's nothing to say, dude.";

    const intros = [
      "Alright, listen up. Here's what you actually need to know.",
      "Okay, okay, let me break it down for you.",
      "Dude, seriously, here's the important stuff.",
      "Ey! Pay attention, here's what matters.",
    ];

    const closers = [
      "And that's the bottom line, respect my authoritah.",
      "Screw you guys, I'm goin' home.",
      "That's it. Now leave me alone, I'm watching Terrence and Phillip.",
      "Whatever.",
    ];

    const intro = intros[Math.floor(Math.random() * intros.length)];
    const closer = closers[Math.floor(Math.random() * closers.length)];

    const body = points.map((p, i) => {
      const prefixes = ["First off,", "Next,", "Also,", "And get this,", "Plus,"];
      const prefix = prefixes[i] || "And,";
      return `${prefix} ${p}.`;
    }).join(' ');

    return `${intro} ${body} ${closer}`;
  }

  async function speakAsCartman(text) {
    if (!('speechSynthesis' in window)) {
      showBubble('Speech not supported');
      return;
    }

    window.speechSynthesis.cancel();
    showBubble('God Cartman is thinking...');

    // Try God Cartman API first, fall back to local extraction
    let script = await fetchCartmanSummary(text);

    if (!script) {
      const points = extractKeyPoints(text);
      script = cartmanizeFallback(points);
    }

    const utter = new SpeechSynthesisUtterance(script);
    utter.pitch = 0.4;
    utter.rate = 0.95;
    utter.volume = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const maleVoice = voices.find(v =>
      /en[-_]US/i.test(v.lang) && /male|david|alex|daniel|fred/i.test(v.name)
    ) || voices.find(v => /en[-_]US/i.test(v.lang)) || voices.find(v => /^en/i.test(v.lang));

    if (maleVoice) utter.voice = maleVoice;

    utter.onstart = () => {
      btn.classList.add('speaking');
      showBubble('Speaking as God Cartman...');
    };
    utter.onend = () => {
      btn.classList.remove('speaking');
      hideBubble();
    };
    utter.onerror = () => {
      btn.classList.remove('speaking');
      hideBubble();
    };

    window.speechSynthesis.speak(utter);
  }

  let bubble = null;

  function showBubble(msg) {
    hideBubble();
    bubble = document.createElement('div');
    bubble.id = 'rm-tts-bubble';
    bubble.textContent = msg;
    bubble.style.cssText = [
      'position:fixed',
      'bottom:72px',
      'right:20px',
      'background:#1a1a1f',
      'color:#f0f0f5',
      'padding:8px 14px',
      'border-radius:8px',
      'font-size:12px',
      'font-family:-apple-system,BlinkMacSystemFont,sans-serif',
      'box-shadow:0 4px 12px rgba(0,0,0,0.3)',
      'z-index:2147483647',
      'white-space:nowrap',
    ].join(';');
    document.body.appendChild(bubble);
    setTimeout(hideBubble, 3000);
  }

  function hideBubble() {
    if (bubble) {
      bubble.remove();
      bubble = null;
    }
  }

  // Inject after DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectButton);
  } else {
    injectButton();
  }

  // Re-inject if removed by SPA navigation
  const observer = new MutationObserver(() => {
    if (!document.getElementById(BTN_ID)) {
      injectButton();
    }
  });
  observer.observe(document, { childList: true, subtree: true });
})();
