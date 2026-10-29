# Лицензии компонентов

| Компонент | Источник | Лицензия |
|---|---|---|
| 3D-модель девушки (`avatar.glb`) | `mpfb.glb` из [met4citizen/TalkingHead](https://github.com/met4citizen/TalkingHead), собрана в Blender + MPFB из ассетов MakeHuman | CC0 1.0: можно использовать где угодно, в том числе коммерчески. В проекте модель сжата (текстуры WebP, геометрия meshopt), карта нормалей убрана |
| Движения (`motions.bin`) | CMU Graphics Lab Motion Capture Database, BVH-конверсия Bruce Hahne (cgspeed), копия [una-dinosauria/cmu-mocap](https://github.com/una-dinosauria/cmu-mocap) | «This data is free for use in research and commercial projects worldwide». Перенесены на скелет модели, частота 30 кадров/с |
| three.js (внутри `lisa3d.js`) | [three.js](https://threejs.org), версия 0.186.1 | MIT |
| Декодер meshopt (внутри `lisa3d.js`) | three.js examples / meshoptimizer | MIT |
| Платье, чулки, кожа, глаза второй девушки (`avatar2/*.webp`) | Перерисованы `tools/make-dress.py`, `tools/make-suit.py` из текстур MakeHuman внутри `avatar.glb`; лицо перенесено с `avatar2/portrait.webp` | CC0 1.0 (основа) |
| Юбка, туфли, танец второй девушки (`avatar2/skirt.bin`, `shoes.bin`, `motions.bin`) | Сгенерированы `tools/skirt.py`, `tools/shoes.py`, `tools/make-dance.py` | Собственные (танец — процедурный; остальные движения из CMU) |
| Волосы (`avatar2/hair.bin`) | Сгенерированы `tools/hair.py` по форме головы модели | Собственные |
| MediaPipe Face Landmarker | Только при сборке (`make-suit.py`, `make-dress.py`, `make-face-data.py`), в файлы не входит | Apache 2.0 |

Благодарность, которую просит CMU: «The data used in this project was obtained from mocap.cs.cmu.edu. The database was created with funding from NSF EIA-0196217.»
