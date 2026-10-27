// Ортографический вид головы спереди (поза покоя, только текстуры): для поиска точек лица на модели.
//   node front-render.mjs ../avatar.glb data/front.png data/front-z.f32
// Кадр: 2500 пикселей на метр, центр по x = 0, верх кадра y = 1.80 м; z-буфер в метрах (ближе к зрителю = больше).
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { MeshoptDecoder } from 'meshoptimizer';
import sharp from 'sharp';
import fs from 'node:fs';

export const FRAME = { S: 2500, W: 560, H: 900, YT: 1.8 };
const [src, outImg, outZ] = process.argv.slice(2);
const { S, W, H, YT } = FRAME;
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': MeshoptDecoder });
const doc = await io.read(src);
const img = new Uint8Array(W * H * 3).fill(40), zb = new Float32Array(W * H).fill(-9);

for (const node of doc.getRoot().listNodes()) {
  const mesh = node.getMesh();
  if (!mesh || !/^base$|high-poly/.test(mesh.getName())) continue;
  const skin = node.getSkin();
  const a = skin.listJoints()[0].getWorldMatrix(), b = skin.getInverseBindMatrices().getElement(0, []);
  const M = new Array(16).fill(0);
  for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) for (let k = 0; k < 4; k++) M[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k];
  const prim = mesh.listPrimitives()[0];
  const P = prim.getAttribute('POSITION'), UV = prim.getAttribute('TEXCOORD_0'), I = prim.getIndices();
  const tex = prim.getMaterial().getBaseColorTexture();
  const { data: T, info } = await sharp(Buffer.from(tex.getImage())).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const tw = info.width, th = info.height;
  const V = [];
  for (let i = 0; i < P.getCount(); i++) {
    const v = P.getElement(i, []);
    const w = [0, 1, 2].map(r => M[r] * v[0] + M[4 + r] * v[1] + M[8 + r] * v[2] + M[12 + r]);
    V.push([w[0] * S + W / 2, (YT - w[1]) * S, w[2]]);
  }
  for (let k = 0; k < I.getCount(); k += 3) {
    const ids = [I.getScalar(k), I.getScalar(k + 1), I.getScalar(k + 2)];
    const p = ids.map(i => V[i]), uv = ids.map(i => UV.getElement(i, []));
    const d = (p[1][0] - p[0][0]) * (p[2][1] - p[0][1]) - (p[2][0] - p[0][0]) * (p[1][1] - p[0][1]);
    if (Math.abs(d) < 1e-9) continue;
    const x0 = Math.max(0, Math.floor(Math.min(p[0][0], p[1][0], p[2][0]))), x1 = Math.min(W - 1, Math.ceil(Math.max(p[0][0], p[1][0], p[2][0])));
    const y0 = Math.max(0, Math.floor(Math.min(p[0][1], p[1][1], p[2][1]))), y1 = Math.min(H - 1, Math.ceil(Math.max(p[0][1], p[1][1], p[2][1])));
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
      const l1 = ((x - p[0][0]) * (p[2][1] - p[0][1]) - (p[2][0] - p[0][0]) * (y - p[0][1])) / d;
      const l2 = ((p[1][0] - p[0][0]) * (y - p[0][1]) - (x - p[0][0]) * (p[1][1] - p[0][1])) / d;
      const l0 = 1 - l1 - l2;
      if (l0 < 0 || l1 < 0 || l2 < 0) continue;
      const z = l0 * p[0][2] + l1 * p[1][2] + l2 * p[2][2], o = y * W + x;
      if (z <= zb[o]) continue;
      const u = l0 * uv[0][0] + l1 * uv[1][0] + l2 * uv[2][0], v = l0 * uv[0][1] + l1 * uv[1][1] + l2 * uv[2][1];
      const tx = Math.min(tw - 1, Math.max(0, Math.round(u * tw - .5))), ty = Math.min(th - 1, Math.max(0, Math.round(v * th - .5)));
      const t = (ty * tw + tx) * 4;
      if (T[t + 3] < 128) continue;   // прозрачная роговица глаза
      zb[o] = z;
      for (let c = 0; c < 3; c++) img[o * 3 + c] = T[t + c];
    }
  }
}
await sharp(Buffer.from(img), { raw: { width: W, height: H, channels: 3 } }).png().toFile(outImg);
fs.writeFileSync(outZ, Buffer.from(zb.buffer));
console.log('вид спереди ->', outImg, outZ);
