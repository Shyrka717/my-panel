# Лицензии компонентов

| Компонент | Источник | Лицензия |
|---|---|---|
| 3D-модель девушки (`avatar.glb`) | `mpfb.glb` из [met4citizen/TalkingHead](https://github.com/met4citizen/TalkingHead), собрана в Blender + MPFB из ассетов MakeHuman | CC0 1.0: можно использовать где угодно, в том числе коммерчески. В проекте модель сжата (текстуры WebP, геометрия meshopt), карта нормалей убрана |
| Движения (`motions.bin`) | CMU Graphics Lab Motion Capture Database, BVH-конверсия Bruce Hahne (cgspeed), копия [una-dinosauria/cmu-mocap](https://github.com/una-dinosauria/cmu-mocap) | «This data is free for use in research and commercial projects worldwide». Перенесены на скелет модели, частота 30 кадров/с |
| three.js (внутри `lisa3d.js`) | [three.js](https://threejs.org), версия 0.186.1 | MIT |
| Декодер meshopt (внутри `lisa3d.js`) | three.js examples / meshoptimizer | MIT |

Благодарность, которую просит CMU: «The data used in this project was obtained from mocap.cs.cmu.edu. The database was created with funding from NSF EIA-0196217.»
