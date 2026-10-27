/* Lisa3D: голограмма в полный рост.
   Модель со скелетом и лицевыми формами, движения из записей захвата движения (CMU),
   танцы, жесты при разговоре, действия по командам, губы под речь. */
import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

const clamp = (x, a, b) => x < a ? a : x > b ? b : x;
const pick = a => a[Math.floor(Math.random() * a.length)];

/* ---------- команды ---------- */
const DANCE_STYLES = [
  [/сальс/, 'salsa'], [/чарльстон/, 'charleston'], [/линди/, 'lindy'], [/индий/, 'indian'],
  [/современ|модерн|балет|пируэт/, 'modern'], [/русск|присядк|вприсядк/, 'russian'], [/лунн|джексон/, 'moonwalk'],
  [/твист/, 'twist'], [/макарен/, 'macarena'], [/утят|утк|цыпл/, 'chicken']
];
const COMMANDS = [
  [/(стоп|хватит|останов|замри|перестань|прекрати)/, 'stop'],
  [/(станцуй|танцуй|потанцуй|танец|танцевать|зажги)/, 'dance'],
  [/(сядь|присядь|садись|посиди|сесть)/, 'sit'],
  [/(ляг|ложись|приляг|полежи|лечь)/, 'lie'],
  [/(встань|вставай|поднимись|встать)/, 'stand'],
  [/(покружись|крутись|кружись|вращайся|покрутись)/, 'spin'],
  [/(повернись|развернись|разворот|обернись)/, 'turn'],
  [/(прыгни|прыгай|подпрыгни|прыжок|попрыгай)/, 'jump'],
  [/(беги|побеги|бегай|побегай|пробеж)/, 'run'],
  [/(иди|пройдись|шагай|ходи|походи|прогуляйся)/, 'walk'],
  [/(помаши|поздоровайся|привет)/, 'wave'],
  [/(поклонись|реверанс|поклон)/, 'bow'],
  [/(потянись|зевни|разомнись)/, 'stretch'],
  [/(посмейся|смейся|засмейся|рассмеши)/, 'laugh'],
  [/(порадуйся|радуйся|ура|празднуй)/, 'happy'],
  [/(пожми плечами)/, 'shrug'],
  [/(дай пять)/, 'highfive'],
  [/(ку-ку|куку|прятки)/, 'peekaboo'],
  [/(зарядк|прыжки на месте)/, 'jacks'],
];
const ONESHOT = { jump: ['jump1', 'jump2', 'jump3'], spin: ['spin'], turn: ['turn'], wave: ['wave1', 'wave2'], bow: ['bow'], stretch: ['stretch'],
  laugh: ['laugh'], happy: ['happy'], shrug: ['shrug'], highfive: ['highfive'], peekaboo: ['peekaboo'], jacks: ['jacks'] };

function parseCommand(text) {
  const t = String(text || '').toLowerCase().replace(/ё/g, 'е');
  for (const [re, action] of COMMANDS) if (re.test(t)) {
    let style = null;
    if (action === 'dance') for (const [r, s] of DANCE_STYLES) if (r.test(t)) { style = s; break; }
    return { action, style };
  }
  for (const [r, s] of DANCE_STYLES) if (r.test(t)) return { action: 'dance', style: s };
  return null;
}

/* ---------- голографический материал ---------- */
function holoMaterial(src, U, kind) {
  const m = new THREE.MeshBasicMaterial({ map: src.map || null, transparent: true, depthWrite: kind === 0, side: kind ? THREE.DoubleSide : THREE.FrontSide, alphaTest: src.alphaTest || 0 });
  if (src.alphaMap) m.alphaMap = src.alphaMap;
  m.onBeforeCompile = sh => {
    Object.assign(sh.uniforms, U);
    sh.uniforms.uKind = { value: kind };
    sh.vertexShader = 'varying vec3 vN;varying vec3 vV;varying float vWy;\n' + sh.vertexShader.replace('#include <fog_vertex>',
      `#include <fog_vertex>
      #ifdef USE_SKINNING
        vN = normalize(transformedNormal);
      #else
        vN = normalize(normalMatrix * normal);
      #endif
      vV = -mvPosition.xyz; vWy = (modelMatrix * vec4(transformed, 1.0)).y;`);
    sh.fragmentShader = 'uniform float uTime,uFlick,uOpacity,uKind;uniform vec3 uTint,uRim,uDeep,uHair;varying vec3 vN;varying vec3 vV;varying float vWy;\n' +
      sh.fragmentShader.replace('#include <dithering_fragment>', `#include <dithering_fragment>
      vec3 n = normalize(vN), v = normalize(vV);
      float fr = pow(1.0 - abs(dot(n, v)), 2.2);
      float lum = dot(diffuseColor.rgb, vec3(.299, .587, .114));
      float l2 = smoothstep(0.0, .8, lum);
      vec3 base = uKind > .5 ? mix(uDeep, uHair, .3 + .95 * l2) : mix(uDeep, uTint, .32 + .68 * l2);
      float scan = .84 + .16 * sin(gl_FragCoord.y * 1.25 - uTime * 5.0);
      float band = 1.0 - smoothstep(0.0, .035, abs(fract(vWy * .9 - uTime * .28) - .5));
      vec3 col = base * (uKind > .5 ? .42 + 1.35 * l2 : .66 + .6 * l2) * scan + uRim * fr * (uKind > .5 ? .9 : 1.5) + uTint * band * .18;
      float a = clamp(uOpacity * (.74 + .26 * l2) + fr * .45, 0.0, 1.0) * uFlick;
      if (uKind > .5) a *= diffuseColor.a;
      gl_FragColor = vec4(col, a);`);
  };
  m.customProgramCacheKey = () => 'holo' + kind;
  return m;
}

/* ---------- реалистичный вид (не голограмма) ---------- */
function realMaterial(src, name, opts, U, tex) {
  if (/suit/i.test(name)) {
    const m = new THREE.MeshStandardMaterial({
      color: new THREE.Color(opts.suit || (tex.suit ? '#ffffff' : '#a9afb8')), map: tex.suit || null, metalness: .55, roughness: .36, envMapIntensity: 1.1,
      emissive: new THREE.Color(tex.glow ? '#ffffff' : '#000000'), emissiveMap: tex.glow || null, emissiveIntensity: opts.glow ?? 2.2
    });
    // голубое свечение по краям костюма, как у подсвеченной ткани
    m.onBeforeCompile = sh => {
      sh.uniforms.uAccent = { value: U.uTint.value };
      sh.fragmentShader = 'uniform vec3 uAccent;\n' + sh.fragmentShader.replace('#include <emissivemap_fragment>',
        '#include <emissivemap_fragment>\n totalEmissiveRadiance += uAccent * pow(1.0 - clamp(abs(dot(normalize(normal), normalize(vViewPosition))), 0.0, 1.0), 3.0) * .25;');
    };
    m.customProgramCacheKey = () => 'suit';
    return m;
  }
  if (/ponytail/i.test(name)) return new THREE.MeshStandardMaterial({ map: src.map, color: new THREE.Color(opts.hairTint || '#ffffff').multiplyScalar(opts.hairGain ?? 1), roughness: .48, metalness: 0, alphaTest: .3, side: THREE.DoubleSide });
  if (/eyebrow|eyelash/i.test(name)) return new THREE.MeshStandardMaterial({ color: new THREE.Color(opts.brows || '#2a1c14'), roughness: .85, side: THREE.DoubleSide });
  if (/^Human$/i.test(name)) return new THREE.MeshStandardMaterial({ map: tex.skin || src.map, roughness: .55, metalness: 0 });
  if (/high-poly/i.test(name) && tex.eyes) src.map = tex.eyes;   // свой цвет радужки
  if (src.isMeshStandardMaterial) { src.side = THREE.FrontSide; return src; }
  return src;
}

/* ---------- волосы из пряди-карточек (hair.bin, см. tools/hair.py) ---------- */
function hairTexture() {
  // 4 варианта пряди по горизонтали: тонкие волоски разной яркости, кончики и края прозрачные
  const W = 512, H = 512, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const g = cv.getContext('2d'); let seed = 7;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let c = 0; c < 4; c++) {
    for (let i = 0; i < 46; i++) {
      const x0 = c * 128 + 8 + rnd() * 112, sway = (rnd() - .5) * 10, len = .78 + rnd() * .22, v = 150 + rnd() * 105;
      const gr = g.createLinearGradient(0, 0, 0, H * len);
      gr.addColorStop(0, `rgba(${v},${v},${v},1)`); gr.addColorStop(.8, `rgba(${v},${v},${v},${.85 + rnd() * .15})`); gr.addColorStop(1, `rgba(${v},${v},${v},0)`);
      g.strokeStyle = gr; g.lineWidth = 1 + rnd() * 2.2;
      g.beginPath(); g.moveTo(x0, 0); g.bezierCurveTo(x0 + sway, H * .33, x0 - sway, H * .66, x0 + sway * .5, H * len); g.stroke();
    }
  }
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; t.flipY = false;   // v = 0 у корня
  return t;
}

function buildHair(buf, opts) {
  const dv = new DataView(buf);
  if (dv.getUint32(0) !== 0x48414952) throw new Error('hair: неверный формат');
  const n = dv.getUint16(6, true), k = dv.getUint16(8, true);
  const o = [dv.getFloat32(12, true), dv.getFloat32(16, true), dv.getFloat32(20, true)], q = dv.getFloat32(24, true);
  const P = new Int16Array(buf, 28, n * k * 3), Wb = new Uint8Array(buf, 28 + n * k * 6, n * k * 2), SP = new Uint8Array(buf, 28 + n * k * 8, n * 2);
  const nv = n * k * 2, pos = new Float32Array(nv * 3), nor = new Float32Array(nv * 3), uv = new Float32Array(nv * 2), col = new Float32Array(nv * 3);
  const si = new Uint16Array(nv * 4), sw = new Float32Array(nv * 4), idx = new Uint32Array(n * (k - 1) * 6), hv = new Float32Array(nv * 4);
  const C = new THREE.Vector3(0, 1.665, .05), p = new THREE.Vector3(), a = new THREE.Vector3(), b = new THREE.Vector3(), T = new THREE.Vector3(), R = new THREE.Vector3(), B = new THREE.Vector3();
  const pt = (s, j, v) => v.set(o[0] + P[(s * k + j) * 3] * q, o[1] + P[(s * k + j) * 3 + 1] * q, o[2] + P[(s * k + j) * 3 + 2] * q);
  let ii = 0;
  for (let s = 0; s < n; s++) {
    const width = SP[s * 2] / 10000, tone = SP[s * 2 + 1] / 255 * 1.2, colU = (s % 4) * .25, phase = (s * 2.399) % 6.283;
    for (let j = 0; j < k; j++) {
      const t = j / (k - 1);
      pt(s, j, p); pt(s, Math.min(k - 1, j + 1), a); pt(s, Math.max(0, j - 1), b);
      T.subVectors(a, b).normalize();
      R.subVectors(p, C); R.y *= .3; R.normalize();
      B.crossVectors(T, R).normalize();
      const w = width * (1 - .55 * t * t) * (.6 + .4 * Math.min(1, t * 8)) / 2;
      const ao = .55 + .45 * Math.min(1, t * 4);                    // у корней темнее: глубина причёски
      for (let e = 0; e < 2; e++) {
        const v = (s * k + j) * 2 + e, sg = e ? 1 : -1;
        pos[v * 3] = p.x + B.x * w * sg; pos[v * 3 + 1] = p.y + B.y * w * sg; pos[v * 3 + 2] = p.z + B.z * w * sg;
        nor[v * 3] = R.x; nor[v * 3 + 1] = R.y + .3; nor[v * 3 + 2] = R.z;
        uv[v * 2] = colU + e * .25; uv[v * 2 + 1] = t;
        col[v * 3] = col[v * 3 + 1] = col[v * 3 + 2] = tone * ao;
        const wh = Wb[(s * k + j) * 2] / 255, wn = Wb[(s * k + j) * 2 + 1] / 255;
        si[v * 4] = 0; si[v * 4 + 1] = 1; si[v * 4 + 2] = 2;
        sw[v * 4] = wh; sw[v * 4 + 1] = wn; sw[v * 4 + 2] = Math.max(0, 1 - wh - wn);
        // для физики: сектор вокруг головы, доля соседнего, насколько прядь висит (0 у кожи, 1 на кончиках), фаза
        const sec = (Math.atan2(p.x, p.z - C.z) / (2 * Math.PI) + .5) * HAIR_SECTORS;
        hv[v * 4] = Math.floor(sec) % HAIR_SECTORS; hv[v * 4 + 1] = sec - Math.floor(sec);
        hv[v * 4 + 2] = clamp((1.66 - p.y) / .2, 0, 1); hv[v * 4 + 3] = phase;
      }
      if (j < k - 1) { const v = (s * k + j) * 2; idx.set([v, v + 1, v + 2, v + 1, v + 3, v + 2], ii); ii += 6; }
    }
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('normal', new THREE.BufferAttribute(nor, 3)); geo.normalizeNormals();
  geo.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  geo.setAttribute('skinIndex', new THREE.BufferAttribute(si, 4));
  geo.setAttribute('skinWeight', new THREE.BufferAttribute(sw, 4));
  geo.setAttribute('aHair', new THREE.BufferAttribute(hv, 4));
  geo.setIndex(new THREE.BufferAttribute(idx, 1));
  const mat = new THREE.MeshStandardMaterial({
    map: hairTexture(), color: new THREE.Color(opts.hairColor || '#5d3d29'), vertexColors: true, roughness: .5, metalness: 0,
    alphaTest: .5, alphaToCoverage: true, side: THREE.DoubleSide
  });
  // смещение прядей от пружин (uSway) и лёгкое шевеление после скиннинга
  const uSway = { value: Array.from({ length: HAIR_SECTORS }, () => new THREE.Vector3()) }, uHairT = { value: 0 };
  mat.onBeforeCompile = sh => {
    sh.uniforms.uSway = uSway; sh.uniforms.uHairT = uHairT;
    sh.vertexShader = `uniform vec3 uSway[${HAIR_SECTORS}];\nuniform float uHairT;\nattribute vec4 aHair;\n` + sh.vertexShader.replace('#include <skinning_vertex>', `#include <skinning_vertex>
      int hs = int(aHair.x + .5), hn = hs == ${HAIR_SECTORS - 1} ? 0 : hs + 1;
      float hh = aHair.z;
      transformed += mix(uSway[hs], uSway[hn], aHair.y) * hh * hh
        + vec3(sin(uHairT * 1.7 + aHair.w), .4 * sin(uHairT * 1.1 + aHair.w * 2.3), cos(uHairT * 1.3 + aHair.w * 1.3)) * .0025 * hh;`);
  };
  mat.customProgramCacheKey = () => 'hair';
  const mesh = new THREE.SkinnedMesh(geo, mat);
  mesh.name = 'hair'; mesh.frustumCulled = false; mesh.castShadow = true; mesh.renderOrder = 3;
  mesh.userData.sim = { uSway, uHairT, C };
  return mesh;
}

/* физика волос: пружина на каждый сектор вокруг головы. Цель — точка, прикреплённая к голове,
   но при наклоне частично «висящая» вниз (гравитация); пружина отстаёт от движений и покачивается */
const HAIR_SECTORS = 6;
function hairPhysics(hair, head) {
  const { uSway, uHairT, C } = hair.userData.sim;
  head.updateMatrixWorld(true);
  const inv = head.matrixWorld.clone().invert();
  const pivotL = C.clone().applyMatrix4(inv);                        // центр головы в системе кости
  const q0 = head.getWorldQuaternion(new THREE.Quaternion());
  const anchors = [], rest = [], P = [], V = [], K = [];
  for (let i = 0; i < HAIR_SECTORS; i++) {
    const az = (i / HAIR_SECTORS - .5) * 2 * Math.PI;
    const w = new THREE.Vector3(C.x + Math.sin(az) * .1, C.y - .13, C.z + Math.cos(az) * .1);
    anchors.push(w.clone().applyMatrix4(inv)); rest.push(w.clone().sub(C));
    P.push(w.clone()); V.push(new THREE.Vector3()); K.push(55 + 25 * ((i * .618) % 1));
  }
  const pivot = new THREE.Vector3(), rigid = new THREE.Vector3(), target = new THREE.Vector3(), a = new THREE.Vector3();
  const qr = new THREE.Quaternion(), tw = new THREE.Quaternion(), sw = new THREE.Quaternion(), qg = new THREE.Quaternion(), qi = new THREE.Quaternion();
  let t = 0, init = false;
  return dt => {
    t += dt; uHairT.value = t;
    pivot.copy(pivotL).applyMatrix4(head.matrixWorld);
    // поворот головы от покоя: наклон (swing) наполовину гасим гравитацией, поворот вокруг вертикали оставляем
    qr.copy(head.getWorldQuaternion(qi)).multiply(q0.clone().invert());
    tw.set(0, qr.y, 0, qr.w).normalize(); sw.copy(qr).multiply(tw.clone().invert());
    qg.slerpQuaternions(sw, qi.identity(), .35).multiply(tw);
    const steps = Math.max(1, Math.ceil(dt / .012)), h = dt / steps;
    for (let i = 0; i < HAIR_SECTORS; i++) {
      rigid.copy(anchors[i]).applyMatrix4(head.matrixWorld);
      target.copy(rest[i]).applyQuaternion(qg).add(pivot);
      if (!init || dt > .2) { P[i].copy(target); V[i].set(0, 0, 0); }
      for (let s = 0; s < steps; s++) {
        a.subVectors(target, P[i]).multiplyScalar(K[i]).addScaledVector(V[i], -6);
        V[i].addScaledVector(a, h); P[i].addScaledVector(V[i], h);
      }
      const o = uSway.value[i].subVectors(P[i], rigid);
      o.y = clamp(o.y, -.02, .03);                                       // вниз мало: кончики лежат на плечах
      o.clampLength(0, .045);
    }
    init = true;
  };
}

function makeFloor(U, opts) {
  const g = new THREE.Group();
  // пол растворяется к краям в цвет фона: без линии горизонта
  const cv = document.createElement('canvas'); cv.width = cv.height = 128;
  const cx = cv.getContext('2d'), gr = cx.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, '#fff'); gr.addColorStop(.3, '#fff'); gr.addColorStop(1, '#000');
  cx.fillStyle = gr; cx.fillRect(0, 0, 128, 128);
  const floor = new THREE.Mesh(new THREE.CircleGeometry(6, 64), new THREE.MeshStandardMaterial({
    color: new THREE.Color(opts.floor || '#1c2229'), roughness: .9, metalness: .05, transparent: true, alphaMap: new THREE.CanvasTexture(cv)
  }));
  floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; g.add(floor);
  const ring = new THREE.Mesh(new THREE.CircleGeometry(.9, 96), new THREE.ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: 'varying vec3 vP;void main(){vP=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
    fragmentShader: 'uniform float uTime;uniform vec3 uTint;varying vec3 vP;void main(){float r=length(vP.xy)/.9;float a=smoothstep(.03,.0,abs(r-.97))*.9+smoothstep(.02,.0,abs(r-.8))*.35*(.6+.4*sin(uTime*1.3));gl_FragColor=vec4(uTint,a);}'
  }));
  ring.rotation.x = -Math.PI / 2; ring.position.y = .003; g.add(ring);
  return { group: g, waves: [] };
}

/* ---------- сцена платформы ---------- */
function makeStage(U) {
  const g = new THREE.Group();
  const add = (geo, frag, o) => {
    const mat = new THREE.ShaderMaterial({
      uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      vertexShader: 'varying vec2 vUv;varying vec3 vP;void main(){vUv=uv;vP=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
      fragmentShader: 'uniform float uTime;uniform vec3 uTint,uRim;varying vec2 vUv;varying vec3 vP;' + frag
    });
    const mesh = new THREE.Mesh(geo, mat); Object.assign(mesh, o || {}); g.add(mesh); return mesh;
  };
  // диск платформы
  const disc = add(new THREE.CircleGeometry(0.9, 96), `void main(){float r=length(vP.xy)/.9;
    float rings=smoothstep(.04,.0,abs(r-.98))+smoothstep(.025,.0,abs(r-.82))*.8+smoothstep(.02,.0,abs(r-.6))*.6+smoothstep(.03,.0,abs(r-.36))*.5;
    float ang=atan(vP.y,vP.x);float ticks=step(.6,fract(ang*12./6.2832+uTime*.05))*smoothstep(.04,.0,abs(r-.9));
    float core=exp(-r*r*7.)*.9;
    vec3 c=uTint*(rings*1.1+ticks*.6)+uRim*core;gl_FragColor=vec4(c,(rings+core+ticks)*.85);}`);
  disc.rotation.x = -Math.PI / 2; disc.position.y = 0.004;
  // расходящиеся кольца
  const waves = [];
  for (let i = 0; i < 3; i++) {
    const w = add(new THREE.RingGeometry(0.97, 1.0, 96), `uniform float uW${i};void main(){gl_FragColor=vec4(uRim,(1.-uW${i})*.9);}`);
    w.rotation.x = -Math.PI / 2; w.position.y = 0.006; w.userData.phase = i / 3; waves.push(w);
    U['uW' + i] = { value: 0 };
  }
  // луч света вверх
  const cone = add(new THREE.CylinderGeometry(0.62, 0.86, 2.3, 64, 1, true), `void main(){float h=clamp(vP.y/2.3+.5,0.,1.);
    float streak=.55+.45*sin(atan(vP.z,vP.x)*24.+uTime*1.5);
    gl_FragColor=vec4(uTint,(1.-h)*(1.-h)*.16*streak);}`);
  cone.position.y = 1.15;
  // частицы
  const N = 220, pos = new Float32Array(N * 3), seed = new Float32Array(N);
  for (let i = 0; i < N; i++) { const a = Math.random() * 6.283, r = Math.sqrt(Math.random()) * 0.8; pos[i * 3] = Math.cos(a) * r; pos[i * 3 + 1] = Math.random() * 2.4; pos[i * 3 + 2] = Math.sin(a) * r; seed[i] = Math.random(); }
  const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(pos, 3)); pg.setAttribute('seed', new THREE.BufferAttribute(seed, 1));
  const pts = new THREE.Points(pg, new THREE.ShaderMaterial({
    uniforms: U, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `uniform float uTime;attribute float seed;varying float vA;void main(){vec3 p=position;p.y=mod(p.y+uTime*(.12+seed*.25),2.4);
      p.x+=sin(uTime*.7+seed*20.)*.03;vA=(1.-p.y/2.4)*(.4+.6*seed);vec4 mv=modelViewMatrix*vec4(p,1.);gl_PointSize=(2.+seed*3.)*(3.5/-mv.z);gl_Position=projectionMatrix*mv;}`,
    fragmentShader: `uniform vec3 uRim;varying float vA;void main(){float d=length(gl_PointCoord-.5);gl_FragColor=vec4(uRim,smoothstep(.5,.0,d)*vA);}`
  }));
  g.add(pts);
  return { group: g, waves };
}

/* ---------- виземы текста ---------- */
const VOW = { а: [.95, 0, .1], я: [.85, 0, .2], о: [.72, .6, 0], ё: [.68, .5, 0], у: [.5, 1, 0], ю: [.5, .8, 0], э: [.66, 0, .35], е: [.62, 0, .4], и: [.3, 0, .85], ы: [.36, 0, .4],
  a: [.92, 0, .1], e: [.62, 0, .4], i: [.3, 0, .8], o: [.72, .6, 0], u: [.5, 1, 0], y: [.34, 0, .5] };
const LAB = 'бпмbpm', LABD = 'вфvf', PUNCT = /[.,!?…:;]/;

/* ---------- создание ---------- */
export async function create(container, opts = {}) {
  const calm = opts.reducedMotion != null ? !!opts.reducedMotion : !!(window.matchMedia && matchMedia('(prefers-reduced-motion:reduce)').matches);
  const bg = new THREE.Color(opts.background || '#050a1a');
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, opts.maxDpr || 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(bg, 1);
  const real = opts.style === 'real';
  if (real) {
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = opts.exposure ?? 1.05;
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFShadowMap;
  }
  const canvas = renderer.domElement;
  canvas.style.cssText = 'display:block;width:100%;height:100%';
  canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', opts.label || 'Голограмма ассистента');
  container.appendChild(canvas);

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(bg, 6, 14);
  if (real) {
    const pm = new THREE.PMREMGenerator(renderer);
    scene.environment = pm.fromScene(new RoomEnvironment(), .04).texture; scene.environmentIntensity = .55;
    scene.add(new THREE.HemisphereLight(0xd9e8ff, 0x1c2026, .55));
    const key = new THREE.DirectionalLight(0xfff1e6, 2.2); key.position.set(1.6, 3.2, 2.6); key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024); key.shadow.bias = -.0005; key.shadow.normalBias = .02;
    Object.assign(key.shadow.camera, { left: -1.6, right: 1.6, top: 2.2, bottom: -.4, near: .5, far: 9 });
    scene.add(key);
    const rim = new THREE.DirectionalLight(new THREE.Color(opts.accent || '#45dcff'), 1.1); rim.position.set(-2.2, 2.4, -2.5); scene.add(rim);
    const fill = new THREE.DirectionalLight(0xbcd4ff, .5); fill.position.set(-2, 1.5, 2); scene.add(fill);
  }
  const camera = new THREE.PerspectiveCamera(28, 1, 0.05, 40);
  const U = {
    uTime: { value: 0 }, uFlick: { value: 1 }, uOpacity: { value: opts.opacity ?? .86 },
    uTint: { value: new THREE.Color(opts.tint || opts.accent || '#5aa8ff') }, uHair: { value: new THREE.Color(opts.hair || '#8f7bff') }, uRim: { value: new THREE.Color(opts.rim || '#9fe0ff') }, uDeep: { value: new THREE.Color(opts.deep || '#0b1b4a') }
  };

  // данные
  const loader = new GLTFLoader(); loader.setMeshoptDecoder(MeshoptDecoder);
  // свои текстуры костюма, свечения, кожи и глаз (как у glTF: без переворота, sRGB)
  const texture = src => src ? new THREE.TextureLoader().loadAsync(src).then(t => {
    t.flipY = false; t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy()); return t;
  }) : null;
  const [gltf, meta, bin, suitMap, suitGlow, skinMap, eyeMap, hairBuf] = await Promise.all([
    opts.avatarData instanceof ArrayBuffer ? loader.parseAsync(opts.avatarData, '') : loader.loadAsync(opts.avatar || 'avatar.glb'),
    typeof opts.motionsMeta === 'object' ? opts.motionsMeta : fetch(opts.motionsMeta || 'motions.json').then(r => r.json()),
    opts.motionsData instanceof ArrayBuffer ? opts.motionsData : fetch(opts.motions || 'motions.bin').then(r => r.arrayBuffer()),
    real && texture(opts.suitMap), real && texture(opts.suitGlow), real && texture(opts.skinMap), real && texture(opts.eyeMap),
    opts.hairData instanceof ArrayBuffer ? opts.hairData : opts.hairFile ? fetch(opts.hairFile).then(r => r.arrayBuffer()) : null
  ]);
  const avatar = gltf.scene;
  scene.add(avatar);
  const morphMeshes = [];
  avatar.traverse(o => {
    if (o.isMesh || o.isSkinnedMesh) {
      const hair = /eyebrow|eyelash|ponytail/i.test(o.name);
      if (real) { o.material = realMaterial(o.material, o.name, opts, U, { suit: suitMap, glow: suitGlow, skin: skinMap, eyes: eyeMap }); o.castShadow = true; }
      else o.material = holoMaterial(o.material, U, hair ? 1 : 0);
      if (real && opts.hideBrows && /eyebrow/i.test(o.name)) o.visible = false;   // брови уже нарисованы на коже лица
      o.frustumCulled = false;
      o.renderOrder = hair ? 3 : /teeth|tongue|high-poly/i.test(o.name) ? 2 : /suit/i.test(o.name) ? 1 : 0;   // тело пишет глубину первым: зубы и глаза видны только через открытый рот и веки
      if (o.morphTargetDictionary) morphMeshes.push(o);
    }
  });
  const stage = real ? makeFloor(U, opts) : makeStage(U); scene.add(stage.group);

  const bones = {};
  avatar.traverse(o => { if (o.isBone) bones[o.name] = o; });
  const restQ = {}; for (const n in bones) restQ[n] = bones[n].quaternion.clone();

  // свои волосы вместо хвоста: привязка к голове, шее и груди в позе покоя
  let hairSim = null;
  if (hairBuf) {
    const hair = buildHair(hairBuf, opts);
    if (!real) hair.material = holoMaterial(hair.material, U, 1);
    avatar.add(hair); avatar.updateMatrixWorld(true);
    hair.bind(new THREE.Skeleton([bones.Head, bones.Neck, bones.Spine2]));
    avatar.traverse(o => { if (o.isMesh && /ponytail/i.test(o.name)) o.visible = false; });
    if (real) hairSim = hairPhysics(hair, bones.Head);
  }

  // пальцы: расслабленный изгиб (в записях их движения нет)
  avatar.updateMatrixWorld(true);
  for (const side of ['Left', 'Right']) {
    const h = bones[side + 'Hand']; if (!h) continue;
    const P = n => bones[side + n] ? bones[side + n].getWorldPosition(new THREE.Vector3()) : null;
    const hp = h.getWorldPosition(new THREE.Vector3());
    const across = P('HandIndex1').sub(P('HandPinky1'));
    const along = P('HandMiddle1').sub(hp);
    let palm = new THREE.Vector3().crossVectors(along, across).normalize();
    if (palm.dot(P('HandThumb2').sub(hp)) < 0) palm.negate();
    for (const f of ['Index', 'Middle', 'Ring', 'Pinky', 'Thumb']) for (let k = 1; k <= 3; k++) {
      const b = bones[side + 'Hand' + f + k], c = bones[side + 'Hand' + f + (k + 1)] || null;
      if (!b) continue;
      const bp = b.getWorldPosition(new THREE.Vector3());
      const tip = c ? c.getWorldPosition(new THREE.Vector3()) : bp.clone().add(along.clone().normalize().multiplyScalar(0.02));
      const dir = tip.sub(bp).normalize();
      const axisW = new THREE.Vector3().crossVectors(dir, palm).normalize();
      const ang = (f === 'Thumb' ? 0.18 : [0.32, 0.42, 0.28][k - 1] + (f === 'Pinky' ? .12 : f === 'Ring' ? .06 : 0));
      const qW = new THREE.Quaternion().setFromAxisAngle(axisW, ang);
      const pw = b.parent.getWorldQuaternion(new THREE.Quaternion());
      const bw = b.getWorldQuaternion(new THREE.Quaternion());
      const nw = qW.multiply(bw);
      b.quaternion.copy(pw.invert().multiply(nw));
      b.updateMatrixWorld(true);
    }
  }

  /* ----- клипы ----- */
  const data = new Int16Array(bin);
  const clips = {}, groups = {}, titles = {};
  for (const c of meta.clips) {
    const n = c.frames, st = meta.stride, base = c.offset / 2, times = new Float32Array(n);
    for (let i = 0; i < n; i++) times[i] = i / meta.fps;
    const pos = new Float32Array(n * 3), tracks = [];
    for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) pos[i * 3 + k] = data[base + i * st + k] * meta.posScale;
    tracks.push(new THREE.VectorKeyframeTrack('Hips.position', times, pos));
    meta.bones.forEach((b, j) => {
      if (!bones[b]) return;
      const q = new Float32Array(n * 4);
      for (let i = 0; i < n; i++) for (let k = 0; k < 4; k++) q[i * 4 + k] = data[base + i * st + 3 + j * 4 + k] * meta.quatScale;
      tracks.push(new THREE.QuaternionKeyframeTrack(b + '.quaternion', times, q));
    });
    clips[c.name] = [new THREE.AnimationClip(c.name, n / meta.fps, tracks), null];
    clips[c.name][1] = clips[c.name][0].clone();
    (groups[c.group] = groups[c.group] || []).push(c.name);
    if (c.title) titles[c.name] = c.title;
  }
  const danceClips = groups.dance || [];
  const styleOf = n => n.replace(/\d+$/, '');
  const mixer = new THREE.AnimationMixer(avatar);
  let cur = null, curName = '', flip = 0, oneshotDone = null;

  function play(name, fade = 0.6, onDone) {
    const pair = clips[name]; if (!pair) return;
    flip ^= 1;
    const a = mixer.clipAction(pair[flip]);
    a.reset(); a.setLoop(THREE.LoopOnce, 1); a.clampWhenFinished = true; a.enabled = true; a.setEffectiveWeight(1); a.setEffectiveTimeScale(1);
    if (cur && cur !== a) { a.crossFadeFrom(cur, fade, true); } else a.fadeIn(fade);
    a.userData = { queued: false };
    a.play(); cur = a; curName = name; oneshotDone = onDone || null;
  }

  /* ----- поведение ----- */
  // base: dance | idle | listen | think | talk | walk | run | sit | lie
  let base = 'idle', style = null, lastDance = '', pending = null, posture = 'stand', lastInteract = performance.now();
  const autoDance = opts.autoDance !== false && !calm;
  const danceAfter = (opts.danceAfter ?? 25) * 1000;
  const handlers = {};
  const emit = (n, a) => (handlers[n] || []).forEach(f => { try { f(a); } catch (e) { /* обработчик хоста не ломает анимацию */ } });

  function nextFor(b) {
    if (b === 'dance') {
      const pool = style ? danceClips.filter(n => styleOf(n) === style) : danceClips;
      let n = pick(pool); if (pool.length > 1) while (n === lastDance) n = pick(pool);
      lastDance = n; return n;
    }
    if (b === 'talk') return pick(groups.talk);
    if (b === 'walk') return pick(groups.walk);
    if (b === 'run') return pick(groups.run);
    if (b === 'sit') return 'sit_hold';
    if (b === 'lie') return 'lie_hold';
    return pick(groups.idle);
  }
  let busy = false, pendingCmd = null;
  function runPending() { if (pendingCmd) { const [a, o] = pendingCmd; pendingCmd = null; doAction(a, o); } }
  function enterPosture(p) {
    leavePosture(() => {
      posture = p; base = p; busy = true;
      play(p + '_down', .5, () => { busy = false; play(p + '_hold', .4); runPending(); });
    });
    emit('action', p);
  }
  function setBase(b, opt = {}) {
    if (b === 'sit' && posture !== 'sit') { enterPosture('sit'); return; }
    if (b === 'lie' && posture !== 'lie') { enterPosture('lie'); return; }
    if (b !== 'sit' && b !== 'lie' && posture !== 'stand') { leavePosture(() => setBase(b, opt)); return; }
    const changed = base !== b || opt.force;
    base = b;
    if (b === 'dance') { style = opt.style || null; emit('action', 'dance'); }
    if (changed || !cur) play(nextFor(b), opt.fade ?? .7);
    emit('state', b);
  }
  function leavePosture(then) {
    if (posture === 'sit' || posture === 'lie') {
      const clip = posture + '_up'; posture = 'stand'; busy = true;
      play(clip, .4, () => { busy = false; then(); runPending(); });
    } else then();
  }
  function oneshot(kind) {
    const list = ONESHOT[kind]; if (!list) return;
    const ret = base === 'dance' || base === 'walk' || base === 'run' ? base : 'idle';
    leavePosture(() => { play(pick(list), .45, () => { base = ret === 'idle' ? (talk ? 'talk' : 'listen') : ret; play(nextFor(base), .6); }); });
    emit('action', kind);
  }
  function doAction(action, opt = {}) {
    lastInteract = performance.now();
    if (busy) { pendingCmd = [action, opt]; return; }   // идёт переход (садится, встаёт): выполним после
    switch (action) {
      case 'dance': setBase('dance', { style: opt.style, force: true }); break;
      case 'stop': setBase('listen', { force: base === 'dance' }); break;
      case 'stand': if (posture !== 'stand') leavePosture(() => setBase('listen', { force: true })); else setBase('listen'); break;
      case 'walk': case 'run': case 'sit': case 'lie': setBase(action, { force: true }); break;
      default: oneshot(action);
    }
  }
  function attention() {
    lastInteract = performance.now();
    if (base === 'dance' || base === 'walk' || base === 'run') setBase('listen');
  }
  function message(text) {
    const c = parseCommand(text);
    if (!c || c.action !== 'dance') attention();   // любое сообщение сначала останавливает танец
    if (c) doAction(c.action, c);
    return c;
  }

  /* ----- лицо: морфы ----- */
  const has = new Set(); morphMeshes.forEach(m => Object.keys(m.morphTargetDictionary).forEach(k => has.add(k)));
  const MORPH = {};
  function setMorph(name, v) { MORPH[name] = v; }
  function applyMorphs() {
    for (const m of morphMeshes) {
      const d = m.morphTargetDictionary, inf = m.morphTargetInfluences;
      for (const k in MORPH) { const i = d[k]; if (i !== undefined) inf[i] = MORPH[k]; }
    }
  }
  const S = { jaw: 0, round: 0, stretch: 0, press: 0, smile: 0, brow: 0, sad: 0, blink: 0 };
  let nextBlink = performance.now() + 1500, blinkT0 = -1e9, blinkDur = .15;

  /* ----- речь ----- */
  let talk = null, ac = null, audioEl = null, mood = 'neutral';
  const MOODS = { neutral: {}, happy: { smile: .7, brow: .2 }, surprised: { brow: 1, jaw: .2 }, thinking: { brow: .3 }, sad: { sad: .7 } };
  function release(t) { if (t && t.url) { URL.revokeObjectURL(t.url); t.url = null; } }
  function speechStart(t) { emit('speakstart', { text: t || '' }); if (posture === 'stand' && base !== 'walk' && base !== 'run') setBase('talk'); }
  function finish() { if (talk) { release(talk); talk = null; emit('speakend'); if (base === 'talk') setBase('listen'); } }
  function stop() {
    if (window.speechSynthesis) speechSynthesis.cancel();
    if (audioEl) { audioEl.pause(); audioEl = null; }
    if (talk) { release(talk); talk = null; emit('speakend'); if (base === 'talk') setBase('listen'); }
  }
  function say(str, o = {}) {
    str = String(str || '').trim().slice(0, 600); if (!str) return;
    stop(); lastInteract = performance.now(); if (o.mood) mood = o.mood;
    const rate = clamp(o.rate || 1, .6, 1.6), ss = window.speechSynthesis;
    const mine = talk = { mode: 'text', text: str, pos: 0, cps: 15 * rate, tts: false, shown: -1, lv: [0, 0, 0], t0: performance.now(), silent: !(ss && window.SpeechSynthesisUtterance) || !!o.silent };
    speechStart(str); emit('text', { text: str, done: 0 });
    if (!mine.silent) {
      const u = new SpeechSynthesisUtterance(str); u.lang = o.lang || 'ru-RU'; u.rate = rate;
      const v = ss.getVoices().find(x => x.lang && x.lang.toLowerCase().indexOf((o.lang || 'ru').slice(0, 2)) === 0); if (v) u.voice = v;
      u.onstart = () => { if (talk === mine) { mine.tts = true; mine.silent = false; mine.pos = 0; } };
      u.onboundary = e => { if (talk === mine && typeof e.charIndex === 'number') mine.pos = e.charIndex; };
      u.onend = () => { if (talk === mine) finish(); };
      u.onerror = () => { if (talk === mine) { mine.silent = true; mine.tts = false; } };
      ss.speak(u);
    }
  }
  function speakAudio(src, o = {}) {
    stop(); lastInteract = performance.now(); if (o.mood) mood = o.mood;
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return Promise.resolve(false);
    ac = ac || new AC(); if (ac.resume) ac.resume();
    let el = null, node, url = null;
    try {
      if (window.MediaStream && src instanceof MediaStream) node = ac.createMediaStreamSource(src);
      else {
        el = src instanceof HTMLMediaElement ? src : new Audio();
        if (!(src instanceof HTMLMediaElement)) { el.crossOrigin = 'anonymous'; el.src = typeof src === 'string' ? src : (url = URL.createObjectURL(src)); }
        node = ac.createMediaElementSource(el);
      }
    } catch (e) { if (url) URL.revokeObjectURL(url); return Promise.resolve(false); }
    const an = ac.createAnalyser(); an.fftSize = 1024; an.smoothingTimeConstant = .15;
    const dl = ac.createDelay(.5); dl.delayTime.value = o.lead != null ? o.lead : .06;
    node.connect(an); node.connect(dl); dl.connect(ac.destination);
    const mine = talk = { mode: 'audio', an, td: new Uint8Array(an.fftSize), fd: new Uint8Array(an.frequencyBinCount), url };
    speechStart(o.text); if (o.text) emit('text', { text: String(o.text), done: 0 });
    if (!el) return Promise.resolve(true);
    audioEl = el; el.onended = el.onerror = () => { if (talk === mine) finish(); };
    return el.play().then(() => true, () => { if (talk === mine) finish(); return false; });
  }
  function feed(v, o) {
    const e = { lv: clamp(+v || 0, 0, 1), at: performance.now(), r: clamp(o && o.round || 0, 0, 1), s: clamp(o && o.stretch || 0, 0, 1) };
    if (talk && talk.mode === 'text' && talk.silent) { talk.ext = e; return; }
    if (!talk || talk.mode !== 'ext') { stop(); talk = { mode: 'ext' }; speechStart(''); }
    Object.assign(talk, e);
  }
  function visemes(dt, now) {
    let jaw = 0, round = 0, stretch = 0, press = 0;
    if (!talk) return [0, 0, 0, 0];
    if (talk.mode === 'text') {
      if (!talk.silent && !talk.tts && now - talk.t0 > 1500) talk.silent = true;
      const tx = talk.text, i = Math.floor(talk.pos);
      if (i < tx.length) {
        const ch = tx[i], lo = ch.toLowerCase(), p = PUNCT.test(ch);
        if (VOW[lo]) { talk.lv = VOW[lo]; [jaw, round, stretch] = VOW[lo]; }
        else if (LAB.includes(lo)) press = 1;
        else if (LABD.includes(lo)) { jaw = .08; press = .4; }
        else if (ch === ' ' || p) jaw = p ? 0 : talk.lv[0] * .25;
        else { jaw = Math.max(.18, talk.lv[0] * .45); round = talk.lv[1] * .5; stretch = talk.lv[2] * .5; }
        talk.pos += dt * talk.cps * (p ? .22 : 1);
        if (i !== talk.shown) { talk.shown = i; emit('text', { text: tx, done: i }); }
      } else talk.pos += dt * talk.cps;
      const ex = talk.ext && now - talk.ext.at < 400 ? talk.ext : null;
      if (ex) { jaw = ex.lv; round = ex.r * jaw; stretch = ex.s * jaw; press = 0; }
      else if (i >= tx.length && talk.silent && talk.pos >= tx.length + 3) finish();
    } else if (talk.mode === 'ext') {
      if (now - talk.at > 400) finish(); else { jaw = talk.lv; round = talk.r * jaw; stretch = talk.s * jaw; }
    } else {
      const a = talk.an; a.getByteTimeDomainData(talk.td); a.getByteFrequencyData(talk.fd);
      let r = 0; for (let i = 0; i < talk.td.length; i++) { const x = (talk.td[i] - 128) / 128; r += x * x; }
      const rms = Math.sqrt(r / talk.td.length), hz = ac.sampleRate / a.fftSize;
      const band = (f0, f1) => { let s = 0, n = 0; for (let b = Math.max(1, Math.round(f0 / hz)); b <= Math.round(f1 / hz); b++) { s += talk.fd[b]; n++; } return n ? s / n : 0; };
      const lowE = band(200, 700), midE = band(700, 1800), hiE = band(1800, 4200), tot = lowE + midE + hiE + 1e-3;
      jaw = Math.pow(clamp((rms - .012) / .13, 0, 1), .7) * (.75 + .25 * clamp(lowE / tot * 2, 0, 1));
      round = clamp((lowE - midE) / tot * 2.2, 0, 1) * jaw;
      stretch = clamp((hiE / tot - .22) * 3, 0, 1) * jaw;
    }
    return [jaw, round, stretch, press];
  }

  /* ----- голова к зрителю ----- */
  const head = bones.Head, neck = bones.Neck;
  let lookW = 0;
  const _v = new THREE.Vector3(), _q = new THREE.Quaternion(), _q2 = new THREE.Quaternion(), _q3 = new THREE.Quaternion();
  const headFwdLocal = (() => { avatar.updateMatrixWorld(true); const hq = head.getWorldQuaternion(new THREE.Quaternion()); return new THREE.Vector3(0, 0, 1).applyQuaternion(hq.invert()); })();
  function lookAtCamera(w) {
    if (w < .01 || !head) return;
    head.updateWorldMatrix(true, false);
    const hp = head.getWorldPosition(new THREE.Vector3());
    const want = camera.position.clone().sub(hp).normalize();
    const hq = head.getWorldQuaternion(_q);
    const fwd = headFwdLocal.clone().applyQuaternion(hq).normalize();
    const d = new THREE.Quaternion().setFromUnitVectors(fwd, want);
    const ang = 2 * Math.acos(clamp(d.w, -1, 1));
    const lim = .9; if (ang > lim) d.slerp(new THREE.Quaternion(), 1 - lim / ang);
    _q2.identity().slerp(d, w);
    // делим поворот между шеей и головой
    for (const [b, k] of [[neck, .4], [head, .6]]) {
      if (!b) continue;
      const pq = b.parent.getWorldQuaternion(_q3);
      const bw = b.getWorldQuaternion(new THREE.Quaternion());
      const part = new THREE.Quaternion().identity().slerp(_q2, k);
      b.quaternion.copy(pq.invert().multiply(part.multiply(bw)));
      b.updateMatrixWorld(true);
    }
  }

  /* ----- корпус к зрителю (когда слушает и говорит) ----- */
  const hips = bones.Hips, hipsFwdLocal = new THREE.Vector3(0, 0, 1).applyQuaternion(hips.quaternion.clone().invert());
  let faceW = 0, faceYaw = 0;
  function faceViewer(dt, want) {
    faceW += (want - faceW) * (1 - Math.exp(-2 * dt));
    if (faceW < .01) { faceYaw = 0; return; }
    const f = hipsFwdLocal.clone().applyQuaternion(hips.quaternion);
    const err = Math.atan2(f.x, f.z);                     // отклонение от направления на зрителя (+Z)
    faceYaw += (-err - faceYaw) * (1 - Math.exp(-3 * dt));
    hips.quaternion.premultiply(_q.setFromAxisAngle(_v.set(0, 1, 0), faceYaw * faceW));
    hips.updateMatrixWorld(true);
  }

  /* ----- хвостик: пружина ----- */
  const tail = ['PonytailRoot', 'Ponytail1', 'Ponytail2', 'Ponytail3'].map(n => bones[n]).filter(Boolean);
  const tailVel = new THREE.Vector3(), tailOff = new THREE.Vector3(), prevHead = new THREE.Vector3(), prevHeadV = new THREE.Vector3();
  let tailInit = false;
  function updateTail(dt) {
    if (!tail.length || !head || dt <= 0) return;
    const hp = head.getWorldPosition(new THREE.Vector3());
    if (!tailInit) { prevHead.copy(hp); tailInit = true; return; }
    for (const b of tail) b.quaternion.copy(restQ[b.name]);
    tail[0].updateMatrixWorld(true);
    const v = hp.clone().sub(prevHead).divideScalar(dt); prevHead.copy(hp);
    const acc = v.clone().sub(prevHeadV).divideScalar(dt); prevHeadV.copy(v);
    // пружина отстаёт от движения головы
    tailVel.addScaledVector(acc, -.0016).addScaledVector(tailOff, -60 * dt).multiplyScalar(Math.exp(-6 * dt));
    tailOff.addScaledVector(tailVel, dt * 60 * dt + dt);
    tailOff.clampLength(0, .35);
    for (let i = 1; i < tail.length; i++) {
      const b = tail[i], k = .5 + i * .25;
      const bp = b.getWorldPosition(new THREE.Vector3());
      const child = tail[i + 1] ? tail[i + 1].getWorldPosition(new THREE.Vector3()) : null;
      if (!child) continue;
      const dir = child.clone().sub(bp).normalize();
      const nd = dir.clone().addScaledVector(tailOff, k).normalize();
      const d = new THREE.Quaternion().setFromUnitVectors(dir, nd);
      const pq = b.parent.getWorldQuaternion(new THREE.Quaternion());
      const bw = b.getWorldQuaternion(new THREE.Quaternion());
      b.quaternion.copy(pq.invert().multiply(d.multiply(bw)));
      b.updateMatrixWorld(true);
    }
  }

  /* ----- камера ----- */
  function resize() {
    const w = container.clientWidth || 1, h = container.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    const halfV = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const needV = (opts.frameHeight || 2.35) / 2 / halfV, needH = (opts.frameWidth || 1.9) / 2 / (halfV * camera.aspect);
    const dist = Math.max(needV, needH);
    const va = THREE.MathUtils.degToRad(opts.viewAngle || 0);   // взгляд сбоку: поворот камеры вокруг фигуры
    camera.position.set(Math.sin(va) * dist, (opts.cameraY ?? 1.02), Math.cos(va) * dist);
    camera.lookAt(0, opts.lookY ?? 1.0, 0);
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize); ro.observe(container); resize();

  /* ----- цикл ----- */
  let lastT = performance.now();
  const maxDt = opts.maxDt || .05;
  let alive = true, visible = true, glitchT = 0;
  const io = window.IntersectionObserver ? new IntersectionObserver(e => { visible = e[0].isIntersecting; }) : null; if (io) io.observe(canvas);
  mixer.addEventListener('finished', e => {
    if (e.action !== cur) return;
    if (oneshotDone) { const f = oneshotDone; oneshotDone = null; f(); return; }
    if ((base === 'sit' && curName === 'sit_hold') || (base === 'lie' && curName === 'lie_hold')) return;   // держим позу
    play(nextFor(base), .6);
  });

  function frame() {
    if (!alive) return;
    requestAnimationFrame(frame);
    const nowT = performance.now(), dt = Math.min((nowT - lastT) / 1000, maxDt); lastT = nowT;
    if (!visible || document.hidden) return;
    const now = performance.now(), t = now / 1000;
    U.uTime.value = t;
    // мерцание и редкий глитч
    if (!calm && !real && Math.random() < dt * .08) glitchT = .18;
    glitchT = Math.max(0, glitchT - dt);
    U.uFlick.value = calm ? 1 : (glitchT > 0 ? .55 + .45 * Math.random() : .96 + .04 * Math.sin(t * 9.1) * Math.sin(t * 3.7));
    // переход к следующему клипу заранее, чтобы стык был плавным
    const holding = (base === 'sit' && curName === 'sit_hold') || (base === 'lie' && curName === 'lie_hold');
    if (cur && !oneshotDone && !holding && cur.userData && !cur.userData.queued) { const left = cur.getClip().duration - cur.time; if (left < .6) { cur.userData.queued = true; play(nextFor(base), .6); } }
    // сама начинает танцевать, если долго не трогали
    if (autoDance && !talk && (base === 'idle' || base === 'listen') && posture === 'stand' && now - lastInteract > danceAfter) setBase('dance');
    mixer.update(dt);
    avatar.updateMatrixWorld(true);
    const wantLook = (base === 'idle' || base === 'listen' || base === 'talk' || base === 'think') && posture === 'stand' ? 1 : posture !== 'stand' ? .4 : 0;
    lookW += (wantLook - lookW) * (1 - Math.exp(-3 * dt));
    faceViewer(dt, wantLook > .5 ? .75 : 0);
    lookAtCamera(lookW);
    updateTail(dt);
    if (hairSim) hairSim(calm ? 0 : dt);
    // лицо
    const [vj, vr, vs, vp] = visemes(dt, now);
    const m = MOODS[mood] || {};
    const k = r => 1 - Math.exp(-r * dt);
    S.jaw += (Math.max(vj, m.jaw || 0) - S.jaw) * k(vj > S.jaw ? 30 : 18);
    S.round += (vr - S.round) * k(20); S.stretch += (vs - S.stretch) * k(20); S.press += (vp - S.press) * k(25);
    S.smile += ((m.smile || 0) + (base === 'dance' ? .25 : 0) - S.smile) * k(4);
    S.brow += ((m.brow || 0) - S.brow) * k(6); S.sad += ((m.sad || 0) - S.sad) * k(4);
    if (now >= nextBlink) { blinkT0 = now; blinkDur = .13 + Math.random() * .06; nextBlink = now + (Math.random() < .16 ? 280 : 2200 + Math.random() * 3600); }
    const bt = (now - blinkT0) / 1000, bc = blinkDur * .38;
    const blink = bt >= 0 && bt < blinkDur ? (bt < bc ? Math.pow(bt / bc, 1.6) : 1 - Math.pow((bt - bc) / (blinkDur - bc), .8)) : 0;
    const j = S.jaw, r = S.round, s = S.stretch;
    setMorph('viseme_aa', clamp(j * (1 - r) * (1 - s * .5), 0, 1));
    setMorph('viseme_O', clamp(j * r, 0, 1));
    setMorph('viseme_U', clamp(r * (1 - j) * .9, 0, 1));
    setMorph('viseme_E', clamp(j * s * .9, 0, 1));
    setMorph('viseme_I', clamp(s * (1 - j) * .7, 0, 1));
    setMorph('viseme_PP', clamp(S.press, 0, 1));
    setMorph('jawOpen', clamp(j * .25, 0, 1));
    setMorph('eyeBlinkLeft', clamp(blink + S.smile * .12, 0, 1)); setMorph('eyeBlinkRight', clamp(blink + S.smile * .12, 0, 1));
    setMorph('mouthSmileLeft', clamp(S.smile, 0, 1)); setMorph('mouthSmileRight', clamp(S.smile, 0, 1));
    setMorph('browInnerUp', clamp(S.brow * .8 + S.sad * .6, 0, 1));
    setMorph('browOuterUpLeft', clamp(S.brow * .6, 0, 1)); setMorph('browOuterUpRight', clamp(S.brow * .6, 0, 1));
    setMorph('mouthFrownLeft', clamp(S.sad * .7, 0, 1)); setMorph('mouthFrownRight', clamp(S.sad * .7, 0, 1));
    applyMorphs();
    // платформа
    stage.waves.forEach((w, i) => { const p = calm ? .5 : (t * .32 + w.userData.phase) % 1; w.scale.setScalar(.35 + p * .9); U['uW' + i].value = p; });
    renderer.render(scene, camera);
  }

  // старт: танец по умолчанию или ожидание
  setBase(autoDance && opts.startDancing !== false ? 'dance' : 'listen', { force: true, fade: 0 });
  frame();
  const onVis = () => { if (document.hidden) stop(); };
  document.addEventListener('visibilitychange', onVis);
  canvas.addEventListener('webglcontextlost', e => { e.preventDefault(); emit('contextlost'); });

  return {
    canvas, say, speakAudio, feed, stop, message, attention,
    command: parseCommand,
    do: doAction,
    dance: s => doAction('dance', { style: s || null }),
    setState: s => { lastInteract = performance.now(); setBase(s === 'thinking' ? 'think' : s === 'listening' ? 'listen' : s, { force: false }); },
    setMood: m => { if (MOODS[m]) mood = m; },
    on: (n, f) => { (handlers[n] = handlers[n] || []).push(f); },
    get state() { return base; }, get posture() { return posture; }, get speaking() { return !!talk; }, get clip() { return curName; },
    styles: [...new Set(danceClips.map(styleOf))].map(s => ({ id: s, title: titles[danceClips.find(n => styleOf(n) === s)] || s })),
    actions: ['dance', 'stop', 'sit', 'lie', 'stand', 'walk', 'run', ...Object.keys(ONESHOT)],
    _debug: () => ({ morphs: [...has], meshes: morphMeshes.map(m => m.name), bones: Object.keys(bones).length }),
    destroy() { alive = false; stop(); ro.disconnect(); if (io) io.disconnect(); document.removeEventListener('visibilitychange', onVis); renderer.dispose(); canvas.remove(); }
  };
}

export { parseCommand };
