# Ассистент 2: живое лицо и 3D в полный рост

Две версии по одной фотографии (`portrait.webp`).

## Готовые файлы (`dist/`)

| Файл | Что это |
|---|---|
| `avatar2-face.html` | Живое лицо по фото: моргает, двигает губами под речь, мимика. Без текста и кнопок |
| `avatar2-face-demo.html` | То же с панелью проверки |
| `avatar2-3d.html` | 3D в полный рост, реалистичный вид: её лицо с фото, каштановое каре с волнами, серый костюм с голубыми линиями. Танцует, слушает, говорит с жестами, выполняет команды |
| `avatar2-3d-demo.html` | То же с панелью: написать ей, сказать вслух, кнопки танцев и действий |

Каждый файл самодостаточный: работает без сервера и интернета (WebView, Electron, браузер).

## Живое лицо

Встраивание и команды как у LISA (`lisa/README.md`): `window.lisa.say(text)`, `speakAudio(src)`, `feed(level)`, `stop()`, `setMood(...)`, а также `postMessage({lisa:'say', text:'Привет'})`.
Параметры адреса: `?fit=cover` на весь экран, `?edge=0` без растворения краёв, `?bg=1b2129` цвет фона.

## 3D в полный рост

Те же команды и API, что у LISA 3D (`lisa3d/README.md`):
```kotlin
webView.loadUrl("file:///android_asset/avatar2-3d.html")
webView.evaluateJavascript("lisa.message('станцуй сальсу')", null)   // команда или просто сообщение
webView.evaluateJavascript("lisa.feed(0.7)", null)                  // громкость голоса 0..1
```
Параметры адреса: `?dance=0` не танцевать при запуске, `?after=40` через сколько секунд тишины снова танцевать, `?bg=1b2129` цвет фона.

Внешний вид задаётся при создании (`3d.html`):

| Опция | Значение |
|---|---|
| `style: 'real'` | Реалистичный свет, тени, пол вместо голограммы |
| `suitMap`, `suitGlow` | Текстура костюма и карта свечения линий |
| `skinMap` | Кожа с лицом с фото и обувью в тон костюма |
| `eyeMap` | Глаза (серо-зелёная радужка) |
| `hairFile` / `hairData` | Волосы (`hair.bin`); хвост модели скрывается |
| `hairColor` | Цвет волос, например `'#6e4632'` |
| `hideBrows` | Скрыть брови модели (брови нарисованы на коже с фото) |
| `accent`, `background`, `floor`, `exposure` | Цвет подсветки, фона, пола; яркость |
| `viewAngle` | Поворот камеры вокруг фигуры, градусы |

## Пересборка

```
cd lisa3d/tools
node uvmap.mjs ../avatar.glb suit data/suit-uv.f32 data/suit-orig.png
node uvmap.mjs ../avatar.glb '^base' data/body-uv.f32 data/body-orig.png
node uvmap.mjs ../avatar.glb high-poly data/eye-uv.f32 data/eye-orig.png
node uvmap.mjs ../avatar.glb '^base' data/bodyw-uv.f32 data/bodyw-orig.png 1024 world
node uvmap.mjs ../avatar.glb '^base' data/head-uv.f32 data/head-orig.png 2048 world
node uvmap.mjs ../avatar.glb suit data/suitw-uv.f32 data/suitw-orig.png 1024 world
node front-render.mjs ../avatar.glb data/front.png data/front-z.f32
pip install numpy scipy pillow mediapipe
curl -o data/face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
python3 make-suit.py data ../../avatar2 ../../avatar2/portrait.webp data/face_landmarker.task   # костюм, кожа с лицом, глаза
python3 hair.py data ../../avatar2/hair.bin                                                       # волосы
python3 build-single.py                                                                           # -> avatar2/dist
```
Живое лицо: `python3 lisa/tools/make-face-data.py avatar2/portrait.webp face_landmarker.task avatar2/face-data.js`, затем `python3 lisa/tools/build-single.py avatar2`.
