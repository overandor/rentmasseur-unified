document.getElementById('saveBtn').addEventListener('click', () => {
  const url = document.getElementById('serverUrl').value.trim();
  chrome.storage.local.set({ bookingServerUrl: url }, () => {
    const status = document.getElementById('status');
    status.textContent = 'Saved!';
    status.className = 'status ok';
    setTimeout(() => { status.textContent = ''; status.className = 'status'; }, 1500);
  });
});

document.getElementById('openBookings').addEventListener('click', () => {
  chrome.storage.local.get('bookingServerUrl', (data) => {
    const url = data.bookingServerUrl || 'http://localhost:3000';
    chrome.tabs.create({ url });
  });
});

// Load saved URL on open
chrome.storage.local.get('bookingServerUrl', (data) => {
  if (data.bookingServerUrl) {
    document.getElementById('serverUrl').value = data.bookingServerUrl;
  }
});

// ─── Cartman TTS Summary ───────────────────────────────────────────

function extractKeyPoints(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  const points = [];

  for (const line of lines) {
    // Skip headers, code fences, citations, empty lines
    if (/^#{1,6}\s/.test(line)) continue;
    if (/^```/.test(line)) continue;
    if (/^@\//.test(line)) continue;
    if (/^[-*]\s\*\*/.test(line)) {
      // Bullet point with bold title — grab the bold part
      const m = line.match(/\*\*(.+?)\*\*/);
      if (m) points.push(m[1]);
    } else if (/^[-*]\s/.test(line)) {
      // Plain bullet — grab first sentence
      const clean = line.replace(/^[-*]\s/, '');
      const firstSentence = clean.split(/[.!?]/)[0];
      if (firstSentence.length > 5) points.push(firstSentence.trim());
    } else if (/\*\*(.+?)\*\*/.test(line)) {
      // Bold text inline — grab it
      const m = line.match(/\*\*(.+?)\*\*/);
      if (m) points.push(m[1]);
    } else if (line.length > 20 && line.length < 200 && !/^http/.test(line)) {
      // Short standalone sentence
      const firstSentence = line.split(/[.!?]/)[0];
      if (firstSentence.length > 10) points.push(firstSentence.trim());
    }
    if (points.length >= 5) break;
  }

  // Fallback: first 3 sentences of the whole text
  if (points.length === 0) {
    const sentences = text.split(/[.!?]\s/).filter(s => s.trim().length > 10);
    return sentences.slice(0, 3).map(s => s.trim());
  }

  return points.slice(0, 5);
}

function cartmanize(points) {
  if (points.length === 0) return "Ay! There's nothing to say, dude.";

  const intros = [
    "Alright, listen up. Here's what you actually need to know.",
    "Okay, okay, let me break it down for you.",
    "Dude, seriously, here's the important stuff.",
    "Ey! Pay attention, here's what matters.",
  ];

  const closers = [
    "And that's the bottom line, respect my authoritah.",
    "So yeah, that's what's going on. Whatever.",
    "That's it. Now leave me alone, I'm watching Terrence and Phillip.",
    "So there you go. Don't say I never did anything for you.",
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

function speakAsCartman(text) {
  if (!('speechSynthesis' in window)) {
    showTtsStatus('Speech not supported in this browser', 'err');
    return;
  }

  window.speechSynthesis.cancel();

  const points = extractKeyPoints(text);
  const script = cartmanize(points);

  const utter = new SpeechSynthesisUtterance(script);

  // Cartman voice: low pitch, slightly slow, force a male voice if available
  utter.pitch = 0.4;
  utter.rate = 0.95;
  utter.volume = 1.0;

  // Try to pick a male English voice
  const voices = window.speechSynthesis.getVoices();
  const maleVoice = voices.find(v =>
    /en[-_]US/i.test(v.lang) && /male|david|alex|daniel|fred/i.test(v.name)
  ) || voices.find(v => /en[-_]US/i.test(v.lang)) || voices.find(v => /^en/i.test(v.lang));

  if (maleVoice) utter.voice = maleVoice;

  utter.onstart = () => showTtsStatus('Speaking...', 'ok');
  utter.onend = () => showTtsStatus('', '');
  utter.onerror = (e) => showTtsStatus('Speech error: ' + e.error, 'err');

  window.speechSynthesis.speak(utter);
}

function showTtsStatus(msg, cls) {
  const el = document.getElementById('ttsStatus');
  el.textContent = msg;
  el.className = 'status' + (cls ? ' ' + cls : '');
}

// Load voices asynchronously (Chrome loads them lazily)
if ('speechSynthesis' in window) {
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices();
  };
}

document.getElementById('speakBtn').addEventListener('click', () => {
  const text = document.getElementById('ttsInput').value.trim();
  if (!text) {
    // Try clipboard
    navigator.clipboard.readText().then(clip => {
      if (clip && clip.trim()) {
        document.getElementById('ttsInput').value = clip.trim();
        speakAsCartman(clip.trim());
      } else {
        showTtsStatus('Paste some text first', 'err');
      }
    }).catch(() => {
      showTtsStatus('Paste some text first', 'err');
    });
  } else {
    speakAsCartman(text);
  }
});

document.getElementById('stopSpeakBtn').addEventListener('click', () => {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
    showTtsStatus('Stopped', '');
  }
});
