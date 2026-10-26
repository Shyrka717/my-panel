import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { dedup, prune, textureCompress, meshopt, inspect } from '@gltf-transform/functions';
import { MeshoptEncoder } from 'meshoptimizer';
import sharp from 'sharp';
await MeshoptEncoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.encoder': MeshoptEncoder });
const doc = await io.read(process.argv[2]);
const root = doc.getRoot();
// карта нормалей голограмме не нужна
for (const m of root.listMaterials()) { const t = m.getNormalTexture(); if (t) m.setNormalTexture(null); }
// отчёт: вершины и морфы по мешам
for (const mesh of root.listMeshes()) for (const p of mesh.listPrimitives()) {
  const n = p.getAttribute('POSITION').getCount(); console.log(mesh.getName(), 'verts', n, 'morphs', p.listTargets().length);
}
await doc.transform(dedup(), prune(),
  textureCompress({ encoder: sharp, targetFormat: 'webp', resize: [1024, 1024], quality: 82 }),
  meshopt({ encoder: MeshoptEncoder, level: 'medium' }));
await io.write(process.argv[3], doc);
for (const t of root.listTextures()) console.log('tex', t.getName(), t.getMimeType(), t.getImage().byteLength);
