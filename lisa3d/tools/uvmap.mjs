// Карта развёртки: для каждого текселя текстуры сетки — точка и нормаль на теле в позе привязки.
// По ней make-suit.py рисует костюм и обувь в координатах тела, а не развёртки.
//   node uvmap.mjs ../avatar.glb suit data/suit-uv.f32 data/suit-orig.png [1024]
//   node uvmap.mjs ../avatar.glb '^base' data/body-uv.f32 data/body-orig.png [1024]
// С последним аргументом world координаты в метрах сцены (поза покоя), иначе в сжатых координатах сетки.
//   node uvmap.mjs ../avatar.glb '^base' data/head-uv.f32 data/head-orig.png 2048 world
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { MeshoptDecoder } from 'meshoptimizer';
import sharp from 'sharp';
import fs from 'node:fs';

const [src, meshName, outMap, outTex, size, space] = process.argv.slice(2);
const N = +size || 1024;
await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': MeshoptDecoder });
const doc = await io.read(src);
const mesh = doc.getRoot().listMeshes().find(m => new RegExp(meshName, 'i').test(m.getName()));
const prim = mesh.listPrimitives()[0];
// сетки сжаты (KHR_mesh_quantization): в позе покоя мир = кость * обратная матрица привязки * вершина
let M = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
if (space === 'world') {
  const skin = doc.getRoot().listNodes().find(n => n.getMesh() === mesh).getSkin();
  const a = skin.listJoints()[0].getWorldMatrix(), b = skin.getInverseBindMatrices().getElement(0, []);
  M = new Array(16).fill(0);
  for (let r = 0; r < 4; r++) for (let c = 0; c < 4; c++) for (let k = 0; k < 4; k++) M[c * 4 + r] += a[k * 4 + r] * b[c * 4 + k];
}
const toWorld = v => [0, 1, 2].map(r => M[r] * v[0] + M[4 + r] * v[1] + M[8 + r] * v[2] + M[12 + r]);
const P = prim.getAttribute('POSITION'), UV = prim.getAttribute('TEXCOORD_0'), NR = prim.getAttribute('NORMAL'), I = prim.getIndices();

// x y z nx ny nz покрытие; NaN там, где развёртки нет
const out = new Float32Array(N * N * 7).fill(NaN);
for (let k = 0; k < I.getCount(); k += 3) {
  const ids = [I.getScalar(k), I.getScalar(k + 1), I.getScalar(k + 2)];
  const uv = ids.map(i => UV.getElement(i, [])), pos = ids.map(i => toWorld(P.getElement(i, []))), nr = ids.map(i => NR.getElement(i, []));   // масштаб равномерный: нормали не меняются
  const X = uv.map(t => t[0] * N - .5), Y = uv.map(t => t[1] * N - .5);
  const d = (X[1] - X[0]) * (Y[2] - Y[0]) - (X[2] - X[0]) * (Y[1] - Y[0]);
  if (Math.abs(d) < 1e-9) continue;
  const x0 = Math.max(0, Math.floor(Math.min(...X))), x1 = Math.min(N - 1, Math.ceil(Math.max(...X)));
  const y0 = Math.max(0, Math.floor(Math.min(...Y))), y1 = Math.min(N - 1, Math.ceil(Math.max(...Y)));
  for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
    const l1 = ((x - X[0]) * (Y[2] - Y[0]) - (X[2] - X[0]) * (y - Y[0])) / d;
    const l2 = ((X[1] - X[0]) * (y - Y[0]) - (x - X[0]) * (Y[1] - Y[0])) / d;
    const l0 = 1 - l1 - l2;
    if (l0 < -.02 || l1 < -.02 || l2 < -.02) continue;   // небольшой запас, чтобы не было щелей между треугольниками
    const o = (y * N + x) * 7;
    for (let j = 0; j < 3; j++) {
      out[o + j] = l0 * pos[0][j] + l1 * pos[1][j] + l2 * pos[2][j];
      out[o + 3 + j] = l0 * nr[0][j] + l1 * nr[1][j] + l2 * nr[2][j];
    }
    out[o + 6] = 1;
  }
}
fs.writeFileSync(outMap, Buffer.from(out.buffer));
const tex = prim.getMaterial().getBaseColorTexture();
await sharp(Buffer.from(tex.getImage())).resize(N, N).png().toFile(outTex);
console.log('карта', N + 'x' + N, '->', outMap, '; исходная текстура ->', outTex);
