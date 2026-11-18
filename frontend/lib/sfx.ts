// Tiny synthesized sound effects (no audio files). Only ever played right after a user gesture
// or for a job the user started; muted with the theme switcher's speaker toggle.
let ctx: AudioContext | null = null;

function ac(): AudioContext | null {
  if (typeof window === "undefined") return null;
  try {
    if (!ctx) ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
    return ctx;
  } catch {
    return null;
  }
}

/** Unlock audio on a user gesture so later sounds (job done) can play. */
export function primeAudio() {
  ac();
}

/** Clapperboard: a sharp wooden clack. */
export function clap() {
  const c = ac();
  if (!c) return;
  const t = c.currentTime;
  const len = Math.floor(c.sampleRate * 0.12);
  const buf = c.createBuffer(1, len, c.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.exp(-i / (c.sampleRate * 0.012));
  const src = c.createBufferSource();
  src.buffer = buf;
  const bp = c.createBiquadFilter();
  bp.type = "bandpass";
  bp.frequency.value = 2200;
  bp.Q.value = 0.9;
  const g = c.createGain();
  g.gain.setValueAtTime(0.9, t);
  src.connect(bp).connect(g).connect(c.destination);
  src.start(t);
  const o = c.createOscillator();
  const og = c.createGain();
  o.frequency.setValueAtTime(180, t);
  o.frequency.exponentialRampToValueAtTime(60, t + 0.08);
  og.gain.setValueAtTime(0.5, t);
  og.gain.exponentialRampToValueAtTime(0.001, t + 0.1);
  o.connect(og).connect(c.destination);
  o.start(t);
  o.stop(t + 0.12);
}

/** Service bell: bright metallic ding. */
export function bell() {
  const c = ac();
  if (!c) return;
  const t = c.currentTime;
  const partials = [
    [1760, 0.25, 1.6],
    [2637, 0.12, 1.1],
    [3520, 0.06, 0.8],
    [4435, 0.04, 0.5],
  ];
  for (const [f, v, dur] of partials) {
    const o = c.createOscillator();
    const g = c.createGain();
    o.type = "sine";
    o.frequency.value = f;
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(v, t + 0.005);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g).connect(c.destination);
    o.start(t);
    o.stop(t + dur + 0.05);
  }
}

/** Gas burner whoosh for "Fire!". */
export function whoosh() {
  const c = ac();
  if (!c) return;
  const t = c.currentTime;
  const len = Math.floor(c.sampleRate * 0.6);
  const buf = c.createBuffer(1, len, c.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
  const src = c.createBufferSource();
  src.buffer = buf;
  const lp = c.createBiquadFilter();
  lp.type = "lowpass";
  lp.frequency.setValueAtTime(300, t);
  lp.frequency.exponentialRampToValueAtTime(2400, t + 0.18);
  lp.frequency.exponentialRampToValueAtTime(500, t + 0.6);
  const g = c.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(0.5, t + 0.08);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.6);
  src.connect(lp).connect(g).connect(c.destination);
  src.start(t);
}

/** Short fanfare sting for a premiere. */
export function fanfare() {
  const c = ac();
  if (!c) return;
  const t = c.currentTime;
  [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => {
    const o = c.createOscillator();
    const g = c.createGain();
    o.type = "triangle";
    o.frequency.value = f;
    const s = t + i * 0.09;
    g.gain.setValueAtTime(0.0001, s);
    g.gain.exponentialRampToValueAtTime(0.18, s + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, s + 0.7);
    o.connect(g).connect(c.destination);
    o.start(s);
    o.stop(s + 0.75);
  });
}
