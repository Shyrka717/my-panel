import * as esbuild from 'esbuild';
import path from 'node:path';
const [src, out] = process.argv.slice(2);   // node build.mjs ../src/lisa3d.js ../lisa3d.js
await esbuild.build({ entryPoints: [src], bundle: true, format: 'iife', globalName: 'Lisa3D', minify: true, target: 'es2019',
  legalComments: 'none', outfile: out, nodePaths: [path.resolve('node_modules')], logLevel: 'warning' });
console.log('built', out);
