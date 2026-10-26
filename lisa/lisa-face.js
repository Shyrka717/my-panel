/* LisaFace: живое лицо по портрету.
   Сетка лица (478 точек) деформируется в WebGL: веки, брови, губы, челюсть, взгляд, поворот головы.
   Полость рта (зубы, язык, тени) строится по внутреннему контуру губ.
   Речь: по тексту (виземы) или по звуку (громкость и спектр). */
(function (root) {
'use strict';

const clamp = (x, a, b) => x < a ? a : x > b ? b : x;
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const TAU = Math.PI * 2;

/* ---------- шейдеры ---------- */
const VS = `attribute vec2 aPos;attribute vec2 aUv;uniform vec2 uRes;varying vec2 vUv;
void main(){vUv=aUv;vec2 n=aPos/uRes;gl_Position=vec4(n.x*2.-1.,1.-n.y*2.,0.,1.);}`;

const FS_TEX = `precision mediump float;uniform sampler2D uTex;uniform float uAlpha;varying vec2 vUv;
void main(){gl_FragColor=vec4(texture2D(uTex,vUv).rgb,uAlpha);}`;

// vUv.x: -1..1 поперёк рта, vUv.y: 0 у верхней губы .. 1 у нижней; размеры в пикселях портрета
const FS_MOUTH = `precision mediump float;uniform float uOpenH,uAlpha,uRound;varying vec2 vUv;
void main(){
  float u=vUv.x,v=vUv.y,au=abs(u);
  float H=max(uOpenH,.5),py=v*H,pb=(1.-v)*H;
  vec3 col=mix(vec3(.16,.07,.24),vec3(.03,.014,.09),.55*smoothstep(0.,.9,v)+.45*(1.-au));
  // язык
  float tTop=H*(.56-.16*(1.-au*au));
  float tg=smoothstep(tTop-1.2,tTop+1.2,py)*(1.-smoothstep(.45,.9,au))*smoothstep(5.,10.,H);
  vec3 tc=mix(vec3(.42,.18,.42),vec3(.56,.30,.54),(1.-au)*.6);
  col=mix(col,tc*(.45+.55*smoothstep(H,H*.35,py)),tg*.9);
  // верхние зубы: светятся тем же холодным светом, что и кожа, в тени у дёсен и по краям
  float open=1.-.85*uRound;
  float tu=5.4*(1.-.2*au*au);
  float tf=(1.-smoothstep(tu-1.1,tu+1.3,py))*open;
  float gx=abs(fract(u/.286+.5)-.5)*.286;
  float groove=1.-smoothstep(0.,.03,gx);
  vec3 tb=vec3(.60,.68,.88)*(1.-.75*smoothstep(.5,.95,au))*(.55+.45*smoothstep(0.,4.2,py))*(1.-.5*smoothstep(tu-2.,tu+.6,py));
  tb*=1.-.13*groove;
  tb=mix(vec3(.40,.20,.46),tb,smoothstep(.1,1.6,py));
  col=mix(col,tb,tf*.92);
  // нижние зубы: глубже в тени
  float bu=3.0*(1.-.15*au*au);
  float bf=(1.-smoothstep(bu-1.,bu+1.2,pb))*smoothstep(7.,12.,H)*open;
  col=mix(col,tb*.55,bf*.8);
  // тень от губ и боковых коридоров рта
  col*=.5+.5*smoothstep(0.,3.,min(py,pb));
  col*=1.-.6*smoothstep(.6,1.,au);
  gl_FragColor=vec4(col,uAlpha);
}`;

/* ---------- геометрия и веса ---------- */
function buildRig(F) {
  const W = F.w, H = F.h, N = F.pts.length / 3;
  const X = [], Y = [], Z = [];
  for (let i = 0; i < N; i++) { X.push(F.pts[i * 3]); Y.push(F.pts[i * 3 + 1]); Z.push(F.pts[i * 3 + 2]); }
  const avg = (l, a) => l.reduce((s, i) => s + a[i], 0) / l.length;
  const add = (x, y, z) => { X.push(x); Y.push(y); Z.push(z); return X.length - 1; };

  // кольцо вокруг овала лица: неподвижные точки, к которым «тянется» кожа
  const ocx = avg(F.oval, X), ocy = avg(F.oval, Y);
  const ring = F.oval.map(i => add(clamp(ocx + (X[i] - ocx) * 1.22, 2, W - 2), clamp(ocy + (Y[i] - ocy) * 1.22, 2, H - 2), 0));
  const mouthC = add(avg(F.lipIn.loop, X), avg(F.lipIn.loop, Y), avg(F.lipIn.loop, Z));
  const byX = l => l.slice().sort((p, q) => X[p] - X[q]);
  const eyes = [F.eyeA, F.eyeB].map(e => {
    const c = e.iris ? e.iris[0] : add(avg(e.loop, X), avg(e.loop, Y), avg(e.loop, Z));
    const x0 = Math.min(X[e.a], X[e.b]), x1 = Math.max(X[e.a], X[e.b]);
    return { e, c, top: byX([e.a, ...e.up, e.b]), bot: byX([e.a, ...e.lo, e.b]), x0, x1, ex: (x0 + x1) / 2, ew: x1 - x0 };
  });
  const M = X.length;
  const isRing = new Uint8Array(M); ring.forEach(i => isRing[i] = 1);

  const poly = (arr, x) => {
    if (x <= X[arr[0]]) return Y[arr[0]];
    for (let k = 1; k < arr.length; k++) if (x <= X[arr[k]]) {
      const p = arr[k - 1], q = arr[k], t = (x - X[p]) / ((X[q] - X[p]) || 1);
      return Y[p] + (Y[q] - Y[p]) * t;
    }
    return Y[arr[arr.length - 1]];
  };

  // треугольники: сетка лица, заливка глаз веером от центра радужки, полоса к кольцу
  const tris = [];
  eyes.forEach(k => { const L = k.e.loop; for (let i = 0; i < L.length; i++) tris.push(k.c, L[i], L[(i + 1) % L.length]); });   // глаза рисуются первыми, кожа век ложится сверху
  F.tris.forEach(i => tris.push(i));
  for (let i = 0; i < ring.length; i++) {
    const j = (i + 1) % ring.length, o0 = F.oval[i], o1 = F.oval[j];
    tris.push(o0, o1, ring[j], o0, ring[j], ring[i]);
  }
  const mouthTris = [];
  const LI = F.lipIn.loop;
  for (let i = 0; i < LI.length; i++) mouthTris.push(mouthC, LI[i], LI[(i + 1) % LI.length]);

  // рот
  const lo = F.lipOut, li = F.lipIn;
  const mcx = (X[lo.a] + X[lo.b]) / 2, mw = (X[lo.b] - X[lo.a]) / 2, ym = avg(li.loop, Y), chinY = Y[F.chin];
  const setUp = new Set([...li.up, ...lo.up]), setLo = new Set([...li.lo, ...lo.lo]), setCor = new Set([li.a, li.b, lo.a, lo.b]);
  const f32 = () => new Float32Array(M);
  const wJ = f32(), wUp = f32(), wSq = f32(), wCa = f32(), wCb = f32(), wChkA = f32(), wChkB = f32();
  const g2 = (x, y, cx, cy, r) => Math.exp(-.5 * (((x - cx) * (x - cx) + (y - cy) * (y - cy)) / (r * r)));
  for (let i = 0; i < M; i++) {
    if (isRing[i]) continue;
    const x = X[i], y = Y[i], dx = (x - mcx) / mw;
    let w;
    if (setCor.has(i)) w = .28;
    else if (setLo.has(i)) w = clamp(1 - Math.pow(Math.abs(dx), 2.4), 0, 1);
    else if (setUp.has(i)) w = 0;
    else {
      const below = smooth(ym - 1.5, ym + 2.5, y), hf = 1 - smooth(.4, 1.25, Math.abs(dx)), t = clamp((y - ym) / (chinY - ym), 0, 1);
      w = below * hf * (1 - .12 * t);
    }
    wJ[i] = w;
    if (setUp.has(i)) wUp[i] = clamp(1 - Math.pow(Math.abs(dx), 2.4), 0, 1);
    else if (!setLo.has(i) && y < ym && y > ym - mw * .9) wUp[i] = Math.exp(-(ym - y) / (.45 * mw)) * (1 - smooth(.3, 1.1, Math.abs(dx)));
    wSq[i] = Math.exp(-.5 * (Math.pow((x - mcx) / (1.3 * mw), 2) + Math.pow((y - ym) / (1.2 * mw), 2)));
    wCa[i] = g2(x, y, X[lo.a], Y[lo.a], .5 * mw);
    wCb[i] = g2(x, y, X[lo.b], Y[lo.b], .5 * mw);
    wChkA[i] = g2(x, y, X[lo.a] - .15 * mw, Y[lo.a] - mw, .85 * mw);
    wChkB[i] = g2(x, y, X[lo.b] + .15 * mw, Y[lo.b] - mw, .85 * mw);
  }

  // глаза
  const eyeId = new Int8Array(M).fill(-1), eyeUpW = f32(), eyeLoW = f32(), eyeIrisW = f32(), eyeCl = f32(), gazeW = f32();
  eyes.forEach((k, id) => {
    const upSet = new Set(k.e.up), loSet = new Set(k.e.lo);
    let eh = 0;
    k.e.up.forEach(i => { eh = Math.max(eh, poly(k.bot, X[i]) - Y[i]); });
    eh = Math.max(eh, 4);
    k.eh = eh;
    for (let i = 0; i < M; i++) {
      if (isRing[i] || i === k.e.a || i === k.e.b) continue;
      const x = X[i], y = Y[i], lf = 1 - smooth(.5, .8, Math.abs(x - k.ex) / k.ew);
      if (lf <= 0) continue;
      const xc = clamp(x, k.x0, k.x1), yt = poly(k.top, xc), yb = poly(k.bot, xc), cl = Math.max(0, yb - yt);
      if (i === k.c) { eyeId[i] = id; eyeIrisW[i] = 1; eyeCl[i] = cl; gazeW[i] = 1; continue; }
      if (upSet.has(i)) { eyeId[i] = id; eyeUpW[i] = 1; eyeCl[i] = cl; continue; }
      if (loSet.has(i)) { eyeId[i] = id; eyeLoW[i] = 1; eyeCl[i] = cl; continue; }
      if (y < yt) { const w = Math.exp(-(yt - y) / (.9 * eh)) * lf; if (w > .02) { eyeId[i] = id; eyeUpW[i] = w; eyeCl[i] = cl; } }
      else if (y > yb) { const w = Math.exp(-(y - yb) / (.8 * eh)) * lf * .8; if (w > .02) { eyeId[i] = id; eyeLoW[i] = w; eyeCl[i] = cl; } }
    }
  });

  // брови
  const wBA = f32(), wBB = f32(), wFA = f32(), wFB = f32();
  [F.browA, F.browB].forEach((l, k) => {
    const x0 = Math.min(...l.map(i => X[i])), x1 = Math.max(...l.map(i => X[i])), bw = x1 - x0, eye = eyes[k];
    const browY = x => { let s = 0, sw = 0; l.forEach(i => { const w = Math.exp(-.5 * Math.pow((X[i] - x) / (.12 * bw), 2)); s += w * Y[i]; sw += w; }); return s / sw; };
    const xi = k === 0 ? x1 : x0, yi = browY(xi), wB = k === 0 ? wBA : wBB, wF = k === 0 ? wFA : wFB;
    for (let i = 0; i < M; i++) {
      if (isRing[i]) continue;
      const x = X[i], y = Y[i], d = Math.max(0, x0 - x, x - x1), lat = 1 - smooth(0, .35 * bw, d);
      if (lat <= 0) continue;
      const xc = clamp(x, x0, x1), yb = browY(xc), yl = poly(eye.top, clamp(xc, eye.x0, eye.x1));
      let w = 0;
      if (y <= yb) w = Math.exp(-(yb - y) / (.55 * bw)) * lat;
      else if (y < yl) w = (1 - .8 * smooth(yb, yl, y)) * lat;
      wB[i] = w;
      wF[i] = Math.exp(-.5 * (Math.pow((x - xi) / (.35 * bw), 2) + Math.pow((y - yi) / 10, 2)));
    }
  });

  // вес 3D-поворота головы
  const w3 = f32();
  for (let i = 0; i < M; i++) w3[i] = isRing[i] ? 0 : 1;
  F.oval.forEach(i => { w3[i] = .85; });

  // полость рта
  const halfIn = (X[li.b] - X[li.a]) / 2, upS = new Set(li.up), loS = new Set(li.lo);
  const cavLoop = LI.concat([mouthC]);
  const cavUV = new Float32Array(cavLoop.length * 2);
  cavLoop.forEach((i, k) => {
    cavUV[k * 2] = i === mouthC ? 0 : clamp((X[i] - mcx) / halfIn, -1, 1);
    cavUV[k * 2 + 1] = i === mouthC ? .5 : upS.has(i) ? 0 : loS.has(i) ? 1 : .5;
  });
  const cavIdx = [];
  for (let i = 0; i < LI.length; i++) cavIdx.push(LI.length, i, (i + 1) % LI.length);
  const mid = a => a[Math.floor(a.length / 2)];

  const uv = new Float32Array(M * 2);
  for (let i = 0; i < M; i++) { uv[i * 2] = X[i] / W; uv[i * 2 + 1] = Y[i] / H; }

  return {
    W, H, N, M, X: Float32Array.from(X), Y: Float32Array.from(Y), Z: Float32Array.from(Z), uv,
    idx: new Uint16Array(tris), mouthIdx: new Uint16Array(mouthTris), cavLoop, cavUV, cavIdx: new Uint16Array(cavIdx),
    mouthC, midUp: mid(li.up), midLo: mid(li.lo), restOpen: 0,
    mcx, mw, ym, jawAmp: .5 * mw, nose: [X[F.nose], Y[F.nose]], breath: [chinY + 35, chinY + 190],
    wJ, wUp, wSq, wCa, wCb, wChkA, wChkB, eyeId, eyeUpW, eyeLoW, eyeIrisW, eyeCl, gazeW, wBA, wBB, wFA, wFB, w3, isRing,
    loopIdx: LI, faceTriCount: tris.length
  };
}

/* ---------- виземы текста ---------- */
// [раскрытие, округление, растяжение]
const VOW = {
  а: [.95, 0, .1], я: [.85, 0, .2], о: [.72, .6, 0], ё: [.68, .5, 0], у: [.55, 1, 0], ю: [.55, .8, 0],
  э: [.66, 0, .35], е: [.62, 0, .4], и: [.3, 0, .85], ы: [.36, 0, .4],
  a: [.92, 0, .1], e: [.62, 0, .4], i: [.3, 0, .8], o: [.72, .6, 0], u: [.55, 1, 0], y: [.34, 0, .5]
};
const LAB = 'бпмвфbpmvf', PUNCT = /[.,!?…:;]/;

const MOODS = {
  neutral: {},
  happy: { smile: .8, browA: .25, browB: .25 },
  surprised: { browA: 1, browB: 1, jaw: .28, round: .45 },
  thinking: { smile: -.05, browA: .5, browB: -.1, furrow: .4, gx: -.6, gy: -.7, roll: .03, yaw: -.04 },
  sad: { smile: -.55, browA: .35, browB: .35, furrow: .55, pitch: .03 }
};
const STATES = {
  idle: {},
  listening: { browA: .22, browB: .22, roll: .045, pitch: -.01 },
  thinking: { smile: -.05, browA: .5, browB: -.1, furrow: .4, gx: -.6, gy: -.7, roll: .03, yaw: -.04 }
};

/* ---------- создание ---------- */
function create(canvas, opts) {
  opts = opts || {};
  const F = opts.data || root.LISA_FACE;
  if (!F) return Promise.reject(new Error('LisaFace: нет данных лица (face-data.js)'));
  const loadImage = src => typeof src !== 'string' ? Promise.resolve(src) : new Promise((res, rej) => {
    const im = new Image(); im.crossOrigin = 'anonymous'; im.onload = () => res(im); im.onerror = () => rej(new Error('LisaFace: не загрузилось изображение ' + src)); im.src = src;
  });
  return loadImage(opts.image).then(img => start(canvas, opts, F, img));
}

function start(canvas, opts, F, img) {
  const gl = canvas.getContext('webgl', { alpha: false, antialias: true });
  if (!gl) throw new Error('LisaFace: WebGL недоступен');
  const rig = buildRig(F), { W, H, M } = rig;
  const calm = opts.reducedMotion != null ? !!opts.reducedMotion : (root.matchMedia && matchMedia('(prefers-reduced-motion:reduce)').matches);

  const sh = (t, src) => { const o = gl.createShader(t); gl.shaderSource(o, src); gl.compileShader(o); if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; };
  const prog = fs => {
    const p = gl.createProgram();
    gl.attachShader(p, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fs));
    gl.bindAttribLocation(p, 0, 'aPos'); gl.bindAttribLocation(p, 1, 'aUv'); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    return { p, res: gl.getUniformLocation(p, 'uRes'), alpha: gl.getUniformLocation(p, 'uAlpha'), open: gl.getUniformLocation(p, 'uOpenH'), round: gl.getUniformLocation(p, 'uRound') };
  };
  const pT = prog(FS_TEX), pM = prog(FS_MOUTH);
  gl.enableVertexAttribArray(0); gl.enableVertexAttribArray(1);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

  const tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, img);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

  const buf = (data, usage, target) => { const b = gl.createBuffer(); gl.bindBuffer(target || gl.ARRAY_BUFFER, b); gl.bufferData(target || gl.ARRAY_BUFFER, data, usage || gl.STATIC_DRAW); return b; };
  // фоновая сетка (дыхание корпуса)
  const GX = 12, GY = 16, gridRest = new Float32Array((GX + 1) * (GY + 1) * 2), gridUv = new Float32Array(gridRest.length), gridPos = new Float32Array(gridRest.length), gi = [];
  for (let y = 0; y <= GY; y++) for (let x = 0; x <= GX; x++) {
    const k = (y * (GX + 1) + x) * 2; gridRest[k] = x / GX * W; gridRest[k + 1] = y / GY * H; gridUv[k] = x / GX; gridUv[k + 1] = y / GY;
  }
  for (let y = 0; y < GY; y++) for (let x = 0; x < GX; x++) { const a = y * (GX + 1) + x, b = a + 1, c = a + GX + 1, d = c + 1; gi.push(a, b, c, b, d, c); }
  const bGridPos = buf(gridPos, gl.DYNAMIC_DRAW), bGridUv = buf(gridUv), iGrid = buf(new Uint16Array(gi), gl.STATIC_DRAW, gl.ELEMENT_ARRAY_BUFFER);
  const P = new Float32Array(M * 2), bPos = buf(P, gl.DYNAMIC_DRAW), bUv = buf(rig.uv), iMesh = buf(rig.idx, gl.STATIC_DRAW, gl.ELEMENT_ARRAY_BUFFER), iMouth = buf(rig.mouthIdx, gl.STATIC_DRAW, gl.ELEMENT_ARRAY_BUFFER);
  const cavPos = new Float32Array(rig.cavLoop.length * 2), bCavPos = buf(cavPos, gl.DYNAMIC_DRAW), bCavUv = buf(rig.cavUV), iCav = buf(rig.cavIdx, gl.STATIC_DRAW, gl.ELEMENT_ARRAY_BUFFER);

  /* ----- состояние лица ----- */
  const S = { blinkA: 0, blinkB: 0, jaw: 0, round: 0, stretch: 0, smile: 0, browA: 0, browB: 0, furrow: 0, gx: 0, gy: 0, yaw: 0, pitch: 0, roll: 0, bob: 0, breath: 0 };
  const T = { jaw: 0, round: 0, stretch: 0, smile: 0, browA: 0, browB: 0, furrow: 0, gx: 0, gy: 0, yaw: 0, pitch: 0, roll: 0 };
  let mood = 'neutral', state = 'idle', ov = null, talk = null, bump = 0, react = 0, env = 0, micLevel = 0;
  let nextBlink = performance.now() + 1500, blinkT0 = -1e9, blinkDur = .15, gazeAt = 0, gz = { x: 0, y: 0 }, noiseSeed = Math.random() * 100;
  const handlers = {};
  const emit = (n, a) => { (handlers[n] || []).forEach(f => { try { f(a); } catch (e) { /* обработчик не должен ломать анимацию */ } }); if (opts['on' + n]) try { opts['on' + n](a); } catch (e) { /* то же */ } };

  function setMood(n) { if (MOODS[n]) { mood = n; emit('mood', n); } }
  function setState(n) { if (STATES[n]) { state = n; emit('state', n); } }

  /* ----- речь ----- */
  let ac = null, audioEl = null, mediaSrc = null;
  function stop() {
    if (root.speechSynthesis) root.speechSynthesis.cancel();
    if (audioEl) { audioEl.pause(); audioEl = null; }
    if (talk) { release(talk); talk = null; emit('speakend'); }
  }
  function release(t) { if (t && t.url) { URL.revokeObjectURL(t.url); t.url = null; } }
  function finish() { if (talk) { release(talk); talk = null; emit('speakend'); } }
  function text(t, spoken) { emit('text', { text: t, done: spoken }); }

  function say(str, o) {
    o = o || {}; str = String(str || '').trim().slice(0, 600); if (!str) return;
    stop(); if (o.mood) setMood(o.mood);
    const rate = clamp(o.rate || 1, .6, 1.6), ss = root.speechSynthesis;
    const mine = talk = { mode: 'text', text: str, pos: 0, cps: 15 * rate, tts: false, shown: -1, lv: [0, 0, 0], lastSpace: -1, t0: performance.now(), silent: !(ss && root.SpeechSynthesisUtterance) || !!o.silent };
    emit('speakstart', { text: str }); text(str, 0);
    if (!mine.silent) {
      const u = new SpeechSynthesisUtterance(str); u.lang = o.lang || 'ru-RU'; u.rate = rate;
      const v = ss.getVoices().find(x => x.lang && x.lang.toLowerCase().indexOf((o.lang || 'ru').slice(0, 2).toLowerCase()) === 0); if (v) u.voice = v;
      u.onstart = () => { if (talk === mine) { mine.tts = true; mine.silent = false; mine.pos = 0; } };
      u.onboundary = e => { if (talk === mine && typeof e.charIndex === 'number') mine.pos = e.charIndex; };
      u.onend = () => { if (talk === mine) finish(); };
      u.onerror = () => { if (talk === mine) { mine.silent = true; mine.tts = false; } };
      ss.speak(u);
    }
  }

  // источник: URL, Blob, HTMLAudioElement или MediaStream; звук идёт с задержкой 60 мс, чтобы губы опережали его
  function speakAudio(src, o) {
    o = o || {}; stop(); if (o.mood) setMood(o.mood);
    const AC = root.AudioContext || root.webkitAudioContext; if (!AC) return Promise.resolve(false);
    ac = ac || new AC(); if (ac.resume) ac.resume();
    let el = null, node, url = null;
    try {
      if (root.MediaStream && src instanceof MediaStream) node = ac.createMediaStreamSource(src);
      else {
        el = src instanceof HTMLMediaElement ? src : new Audio();
        if (!(src instanceof HTMLMediaElement)) { el.crossOrigin = 'anonymous'; el.src = typeof src === 'string' ? src : (url = URL.createObjectURL(src)); }
        node = ac.createMediaElementSource(el);
      }
    } catch (e) { if (url) URL.revokeObjectURL(url); return Promise.resolve(false); }
    const an = ac.createAnalyser(); an.fftSize = 1024; an.smoothingTimeConstant = .15;
    const dl = ac.createDelay(.5); dl.delayTime.value = o.lead != null ? o.lead : .06;
    node.connect(an); node.connect(dl); dl.connect(ac.destination);
    const mine = talk = { mode: 'audio', an, td: new Uint8Array(an.fftSize), fd: new Uint8Array(an.frequencyBinCount), text: o.text || '', node, dl, url };
    emit('speakstart', { text: mine.text }); if (mine.text) text(mine.text, 0);
    if (!el) return Promise.resolve(true);
    audioEl = el;
    el.onended = el.onerror = () => { if (talk === mine) finish(); };
    return el.play().then(() => true, () => { if (talk === mine) finish(); return false; });
  }

  // уровень микрофона (0..1) для «слушающего» лица
  function level(v) { micLevel = clamp(v, 0, 1); }

  /* ----- обновление ----- */
  const k = (dt, r) => 1 - Math.exp(-r * dt);
  let tNow = 0;
  function visemes(dt, now) {
    let jaw = 0, round = 0, stretch = 0;
    if (!talk) return [0, 0, 0];
    if (talk.mode === 'text') {
      if (!talk.silent && !talk.tts && now - talk.t0 > 1500) talk.silent = true;   // голос не стартовал: говорим беззвучно
      const tx = talk.text, i = Math.floor(talk.pos);
      if (i < tx.length) {
        const ch = tx[i], lo = ch.toLowerCase(), p = PUNCT.test(ch);
        if (VOW[lo]) { talk.lv = VOW[lo]; [jaw, round, stretch] = VOW[lo]; }
        else if (LAB.indexOf(lo) >= 0) { jaw = 0; }
        else if (ch === ' ' || p) { jaw = p ? 0 : talk.lv[0] * .25; }
        else { jaw = Math.max(.18, talk.lv[0] * .45); round = talk.lv[1] * .5; stretch = talk.lv[2] * .5; }
        talk.pos += dt * talk.cps * (p ? .22 : 1);
        if (ch === ' ' && talk.lastSpace !== i) { talk.lastSpace = i; if (Math.random() < .4) bump = Math.max(bump, .35 + Math.random() * .3); }
        if (ch === '!' || ch === '?') bump = Math.max(bump, ch === '!' ? .8 : .55);
        if (i !== talk.shown) { talk.shown = i; text(tx, i); }
      } else { talk.pos += dt * talk.cps; if (talk.silent && talk.pos >= tx.length + 3) finish(); }
    } else {
      const a = talk.an; a.getByteTimeDomainData(talk.td); a.getByteFrequencyData(talk.fd);
      let r = 0; for (let i = 0; i < talk.td.length; i++) { const x = (talk.td[i] - 128) / 128; r += x * x; }
      const rms = Math.sqrt(r / talk.td.length), hz = ac.sampleRate / a.fftSize;
      const band = (f0, f1) => { let s = 0, n = 0; for (let b = Math.max(1, Math.round(f0 / hz)); b <= Math.round(f1 / hz); b++) { s += talk.fd[b]; n++; } return n ? s / n : 0; };
      const lowE = band(200, 700), midE = band(700, 1800), hiE = band(1800, 4200), tot = lowE + midE + hiE + 1e-3;
      jaw = Math.pow(clamp((rms - .012) / .13, 0, 1), .7) * (.75 + .25 * clamp(lowE / tot * 2, 0, 1));
      round = clamp((lowE - midE) / tot * 2.2, 0, 1) * jaw;
      stretch = clamp((hiE / tot - .22) * 3, 0, 1) * jaw;
      if (jaw > .55 && !talk.hit) { talk.hit = true; bump = Math.max(bump, .5); } else if (jaw < .25) talk.hit = false;
    }
    return [jaw, round, stretch];
  }

  function update(dt, now) {
    const t = now / 1000, speaking = !!talk;
    const [vj, vr, vs] = visemes(dt, now);
    bump = Math.max(0, bump - dt * 2.5); react = Math.max(0, react - dt * 1.2);
    env += (vj - env) * k(dt, 6);

    // моргание: закрытие быстрее открытия, иногда двойное; во время речи чаще
    if (now >= nextBlink && !(ov && 'blink' in ov)) {
      blinkT0 = now; blinkDur = .13 + Math.random() * .06;
      nextBlink = now + (Math.random() < .16 ? 280 : (speaking ? 1800 : 2300) + Math.random() * 3600 * (state === 'thinking' ? .6 : 1));
    }
    const bt = (now - blinkT0) / 1000, bc = blinkDur * .38;
    const blink = bt >= 0 && bt < blinkDur ? (bt < bc ? Math.pow(bt / bc, 1.6) : 1 - Math.pow((bt - bc) / (blinkDur - bc), .8)) : 0;
    const blinkB = (() => { const b2 = bt - .008; return b2 >= 0 && b2 < blinkDur ? (b2 < bc ? Math.pow(b2 / bc, 1.6) : 1 - Math.pow((b2 - bc) / (blinkDur - bc), .8)) : 0; })();

    // взгляд: резкие саккады к новой точке, чаще на собеседника
    if (!calm && now >= gazeAt) {
      gazeAt = now + 900 + Math.random() * 2600;
      const away = state === 'thinking' ? .85 : speaking ? .25 : .45;
      gz.x = Math.random() < 1 - away ? 0 : (Math.random() - .5) * 1.3; gz.y = Math.random() < 1 - away ? 0 : (Math.random() - .5) * .7;
      if (Math.random() < .35) nextBlink = Math.min(nextBlink, now + 60);   // моргание после движения глаз
    }

    const m = MOODS[mood], st = STATES[state], g = n => (m[n] || 0) + (st[n] || 0);
    // лёгкий «шум» мимики
    const nz = (f, a) => a * (Math.sin(t * f + noiseSeed) * .6 + Math.sin(t * f * 2.3 + noiseSeed * 1.7) * .4);
    const idle = calm ? 0 : 1;
    T.jaw = Math.max(vj, g('jaw')); T.round = Math.max(vr, g('round')); T.stretch = vs;
    T.smile = g('smile') + react * .7 + idle * nz(.23, .04);
    T.browA = g('browA') + bump * .6 + react * .5 + idle * nz(.19, .05) + micLevel * .25;
    T.browB = g('browB') + bump * .6 + react * .5 + idle * nz(.17, .05) + micLevel * .25;
    T.furrow = g('furrow');
    const gk = speaking ? .3 : 1;
    T.gx = clamp(g('gx') + gz.x * gk, -1, 1); T.gy = clamp(g('gy') + gz.y * gk, -1, 1);
    // голова: покачивание, кивки на акцентах, наклон при слушании
    T.yaw = g('yaw') + idle * (.016 * Math.sin(t * .31 + 1) + .007 * Math.sin(t * .83)) + (speaking ? idle * env * .02 * Math.sin(t * 1.7) : 0);
    T.pitch = g('pitch') + idle * (.012 * Math.sin(t * .41) + .005 * Math.sin(t * 1.9)) - env * .03 * idle - bump * .03 * idle + micLevel * .02;
    T.roll = g('roll') + idle * .008 * Math.sin(t * .27 + 2);

    S.jaw += (T.jaw - S.jaw) * k(dt, T.jaw > S.jaw ? 30 : 18);
    S.round += (T.round - S.round) * k(dt, 20); S.stretch += (T.stretch - S.stretch) * k(dt, 20);
    S.smile += (T.smile - S.smile) * k(dt, 7);
    S.browA += (T.browA - S.browA) * k(dt, 12); S.browB += (T.browB - S.browB) * k(dt, 12); S.furrow += (T.furrow - S.furrow) * k(dt, 8);
    S.gx += (T.gx - S.gx) * k(dt, 38); S.gy += (T.gy - S.gy) * k(dt, 38);
    S.yaw += (T.yaw - S.yaw) * k(dt, 4); S.pitch += (T.pitch - S.pitch) * k(dt, 5); S.roll += (T.roll - S.roll) * k(dt, 4);
    const squint = clamp(S.smile, 0, 1) * .2, lidDown = clamp(S.gy, 0, 1) * .22;
    S.blinkA = clamp(Math.max(blink, squint + lidDown), 0, 1); S.blinkB = clamp(Math.max(blinkB, squint + lidDown), 0, 1);
    S.bob = idle * Math.sin(t * 1.1) * .5; S.breath = idle * Math.sin(t * 1.1);
    if (ov) for (const n in ov) { if (n === 'blink') S.blinkA = S.blinkB = ov[n]; else S[n] = ov[n]; }
  }

  /* ----- деформация сетки ----- */
  function deform() {
    const r = rig, s = S, jd = s.jaw * r.jawAmp * (1 - .3 * s.round), mw = r.mw, mcx = r.mcx;
    const sqK = .30 * s.round - .13 * s.stretch - .10 * Math.max(s.smile, 0);
    const smA = s.smile * .20 * mw, smX = s.smile * .10 * mw, chk = Math.max(s.smile, 0) * .07 * mw;
    const cy = Math.cos(s.roll), sy = Math.sin(s.roll);
    for (let i = 0; i < M; i++) {
      const x0 = r.X[i], y0 = r.Y[i];
      let dx = 0, dy = 0;
      dy += jd * r.wJ[i] - s.jaw * 1.9 * r.wUp[i];
      dx -= (x0 - mcx) * sqK * r.wSq[i];
      dy -= smA * (r.wCa[i] + r.wCb[i]) + chk * (r.wChkA[i] + r.wChkB[i]);
      dx += smX * (r.wCb[i] - r.wCa[i]);
      const id = r.eyeId[i];
      if (id >= 0) {
        const b = id ? s.blinkB : s.blinkA;
        dy += b * r.eyeCl[i] * (r.eyeUpW[i] * 1.12 + r.eyeIrisW[i] * .6 - .15 * r.eyeLoW[i]);
        if (r.gazeW[i]) { dx += s.gx * 2.2; dy += s.gy * 1.6; }
      }
      dy -= 6 * (s.browA * r.wBA[i] + s.browB * r.wBB[i]);
      dx += 2.5 * s.furrow * (r.wFA[i] - r.wFB[i]); dy += 3 * s.furrow * (r.wFA[i] + r.wFB[i]);
      const w3 = r.w3[i];
      if (w3) {
        const z = r.Z[i];
        dx += w3 * (s.yaw * z * 2.2 - s.roll * (y0 - r.nose[1]));
        dy += w3 * (-s.pitch * z * 2.2 + s.roll * (x0 - r.nose[0]) + s.bob);
      }
      P[i * 2] = x0 + dx; P[i * 2 + 1] = y0 + dy;
    }
    // центр рта: среднее по внутреннему контуру
    let cx = 0, cyy = 0; for (const i of r.loopIdx) { cx += P[i * 2]; cyy += P[i * 2 + 1]; }
    P[r.mouthC * 2] = cx / r.loopIdx.length; P[r.mouthC * 2 + 1] = cyy / r.loopIdx.length;
    r.cavLoop.forEach((i, n) => { cavPos[n * 2] = P[i * 2]; cavPos[n * 2 + 1] = P[i * 2 + 1]; });
    for (let n = 0; n < gridPos.length; n += 2) {
      gridPos[n] = gridRest[n]; gridPos[n + 1] = gridRest[n + 1] - s.breath * 1.3 * smooth(r.breath[0], r.breath[1], gridRest[n + 1]);
    }
  }

  /* ----- отрисовка ----- */
  function bind(pos, uv) { gl.bindBuffer(gl.ARRAY_BUFFER, pos); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0); gl.bindBuffer(gl.ARRAY_BUFFER, uv); gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 0, 0); }
  function draw() {
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.bindBuffer(gl.ARRAY_BUFFER, bPos); gl.bufferSubData(gl.ARRAY_BUFFER, 0, P);
    gl.bindBuffer(gl.ARRAY_BUFFER, bGridPos); gl.bufferSubData(gl.ARRAY_BUFFER, 0, gridPos);
    gl.bindBuffer(gl.ARRAY_BUFFER, bCavPos); gl.bufferSubData(gl.ARRAY_BUFFER, 0, cavPos);
    const open = P[rig.midLo * 2 + 1] - P[rig.midUp * 2 + 1];
    if (!rig.restOpen) rig.restOpen = Math.max(open, 0.01);
    const cavA = smooth(.5, 2.2, open - rig.restOpen);

    gl.useProgram(pT.p); gl.uniform2f(pT.res, W, H); gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.disable(gl.BLEND); gl.uniform1f(pT.alpha, 1);
    bind(bGridPos, bGridUv); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, iGrid); gl.drawElements(gl.TRIANGLES, GX * GY * 6, gl.UNSIGNED_SHORT, 0);

    if (cavA > .01) {
      gl.useProgram(pM.p); gl.uniform2f(pM.res, W, H); gl.uniform1f(pM.open, Math.max(open, 0)); gl.uniform1f(pM.round, clamp(S.round, 0, 1)); gl.uniform1f(pM.alpha, cavA); gl.enable(gl.BLEND);
      bind(bCavPos, bCavUv); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, iCav); gl.drawElements(gl.TRIANGLES, rig.cavIdx.length, gl.UNSIGNED_SHORT, 0);
      gl.useProgram(pT.p);
    }
    gl.disable(gl.BLEND); gl.uniform1f(pT.alpha, 1);
    bind(bPos, bUv); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, iMesh); gl.drawElements(gl.TRIANGLES, rig.idx.length, gl.UNSIGNED_SHORT, 0);
    if (cavA < .99) {
      gl.enable(gl.BLEND); gl.uniform1f(pT.alpha, 1 - cavA);
      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, iMouth); gl.drawElements(gl.TRIANGLES, rig.mouthIdx.length, gl.UNSIGNED_SHORT, 0);
    }
  }

  /* ----- цикл ----- */
  let raf = 0, last = performance.now(), visible = true, alive = true;
  function resize() {
    const r = canvas.getBoundingClientRect(), d = Math.min(root.devicePixelRatio || 1, opts.maxDpr || 2);
    if (!r.width) return;
    const w = Math.round(r.width * d), h = Math.round(r.height * d);
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
  }
  const ro = root.ResizeObserver ? new ResizeObserver(resize) : null; if (ro) ro.observe(canvas); resize();
  const io = root.IntersectionObserver ? new IntersectionObserver(e => { visible = e[0].isIntersecting; }) : null; if (io) io.observe(canvas);
  function tick(now) {
    if (!alive) return;
    const dt = Math.min(.05, (now - last) / 1000); last = now;
    if (visible && !document.hidden && canvas.width) { update(dt, now); deform(); draw(); }
    raf = requestAnimationFrame(tick);
  }
  raf = requestAnimationFrame(tick);
  const onVis = () => { if (document.hidden) stop(); };
  document.addEventListener('visibilitychange', onVis);
  canvas.addEventListener('webglcontextlost', e => { e.preventDefault(); alive = false; emit('contextlost'); });

  return {
    canvas, say, speakAudio, stop, level,
    setMood, setState, react: () => { react = 1; nextBlink = 0; },
    pose: o => { ov = o || null; },
    get speaking() { return !!talk; }, get mood() { return mood; }, get state() { return state; },
    on: (n, f) => { (handlers[n] = handlers[n] || []).push(f); },
    destroy: () => { alive = false; cancelAnimationFrame(raf); stop(); if (ro) ro.disconnect(); if (io) io.disconnect(); document.removeEventListener('visibilitychange', onVis); },
    _rig: rig
  };
}

root.LisaFace = { create, MOODS: Object.keys(MOODS), STATES: Object.keys(STATES) };
})(typeof window !== 'undefined' ? window : globalThis);
