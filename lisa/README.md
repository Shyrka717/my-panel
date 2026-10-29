# LISA: лицо голосового ассистента

Живое лицо по одному портрету: моргание, брови, взгляд, поворот головы, губы под речь, зубы и язык.
Работает в любом браузере с WebGL, в WebView (Android, iOS), Electron и PWA. Зависимостей нет.

## Готовые файлы для приложения

`dist/lisa-hologram.html`: чистая голограмма на весь экран, без надписей, только анимация. Всё внутри одного файла (скрипты, разметка лица, портрет), открывается напрямую из приложения, без сервера и интернета.
`dist/lisa-demo.html`: то же с кнопками для проверки (фраза, состояния, настроения, озвучка файлом, микрофон).

Пересобрать после правок: `python3 lisa/tools/build-single.py`.

### Встраивание

**Android (WebView)**: положите `lisa-hologram.html` в `app/src/main/assets/`.
```kotlin
webView.settings.javaScriptEnabled = true
webView.settings.mediaPlaybackRequiresUserGesture = false
webView.loadUrl("file:///android_asset/lisa-hologram.html")
// управление
webView.evaluateJavascript("lisa.setState('thinking')", null)
webView.evaluateJavascript("lisa.say('Привет!')", null)
```

**iOS (WKWebView)**: добавьте файл в бандл, `webView.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())`, команды через `evaluateJavaScript("lisa.feed(0.6)")`.

**Веб-приложение (iframe)**:
```html
<iframe id="lisa" src="lisa-hologram.html" style="width:100%;height:100%;border:0" allow="autoplay"></iframe>
<script>
const lisa = document.getElementById('lisa').contentWindow;
lisa.postMessage({ lisa: 'state', value: 'listening' }, '*');
lisa.postMessage({ lisa: 'say', text: 'Привет!', mood: 'happy' }, '*');
addEventListener('message', e => { if (e.data && e.data.lisa) console.log(e.data.event); });   // ready, speakstart, speakend, state
</script>
```
Команды: `say {text, mood, rate, silent}`, `audio {src, text, mood}`, `feed {level, round, stretch}`, `stop`, `state {value}`, `mood {value}`, `level {value}`, `react`.

**Голос из самого приложения** (нативный синтез речи, свой сервер): пока звучит ответ, передавайте его громкость 20-60 раз в секунду, губы пойдут за звуком; через 0.4 с без данных лицо замолкает само.
```js
lisa.feed(rms)            // 0..1
```
Если нужны субтитры, откройте страницу с `?subs=1` и вызовите `lisa.say(text, {silent: true})` вместе с `feed()`.

Параметры адреса: `?fit=cover` на весь экран с обрезкой краёв, `?tag=1` метка состояния, `?subs=1` субтитры, `?fx=0` без эффектов, `?edge=0` без растворения краёв, `?bg=000000` цвет фона, `?origin=https://...` принимать команды только с этого адреса.

## Запуск исходников

Исходники (`index.html`, `embed.html`) открывайте через http: из `file://` браузер не даёт читать отдельную картинку в WebGL (у собранных файлов из `dist/` этого ограничения нет).

```
cd my-panel && python3 -m http.server 8000
# http://localhost:8000/lisa/
```

Файлы: `lisa-face.js` (движок), `face-data.js` (разметка лица), `portrait.webp` (портрет), `index.html` (демо), `embed.html` (голограмма для встраивания).

## Подключение

```html
<canvas id="face"></canvas>
<script src="face-data.js"></script>
<script src="lisa-face.js"></script>
<script>
LisaFace.create(document.getElementById('face'), { image: 'portrait.webp' }).then(lisa => {
  lisa.setState('listening');            // слушает
  lisa.setState('thinking');             // думает
  lisa.setState('idle');
  lisa.speakAudio(audioBlobOrUrl, { text: 'Ответ ассистента', mood: 'happy' });   // губы по звуку
});
</script>
```

Размер холста задаёт CSS, пропорции портрета 586×780.

## API

| Вызов | Что делает |
|---|---|
| `say(text, {mood, rate, lang, silent})` | Озвучка системным голосом, губы по тексту. Без голоса говорит беззвучно, субтитры идут |
| `speakAudio(src, {text, mood, lead})` | `src`: URL, Blob/File, `<audio>` или `MediaStream`. Губы по громкости и спектру, звук с задержкой `lead` (по умолчанию 0.06 с), чтобы губы опережали его |
| `stop()` | Остановить речь |
| `setState('idle' \| 'listening' \| 'thinking')` | Состояние ассистента |
| `setMood('neutral' \| 'happy' \| 'surprised' \| 'thinking' \| 'sad')` | Выражение лица |
| `feed(0..1, {round, stretch})` | Громкость речи из приложения (нативный синтез речи): губы по ней, без звука в странице |
| `level(0..1)` | Уровень микрофона: лицо реагирует, пока пользователь говорит |
| `react()` | Короткая реакция (брови, улыбка, моргание) |
| `pose({...})` | Ручные параметры лица: `jaw, round, stretch, smile, browA, browB, furrow, gx, gy, yaw, pitch, roll, blink`; `pose(null)` вернёт управление |
| `on(name, fn)` | События: `speakstart`, `speakend`, `text` (`{text, done}` для субтитров), `state`, `mood` |
| `destroy()` | Освободить ресурсы |

Типичный цикл ассистента: микрофон → `setState('listening')` + `level()` → распознавание → `setState('thinking')` → ответ → `speakAudio(ответ, {text})` → `setState('idle')`.

## Другой портрет

Лицо должно быть анфас, глаза открыты, рот закрыт. Разметка делается один раз:

```
pip install mediapipe numpy pillow
curl -o face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
python3 lisa/tools/make-face-data.py lisa/portrait.webp face_landmarker.task lisa/face-data.js
```

Чем выше разрешение портрета, тем чётче лицо на больших экранах: движок от разрешения не зависит.

## Ограничения

- Это деформация неподвижного фото: повороты головы до нескольких градусов, без полного 3D.
- Звук `speakAudio` двигает губы по громкости и спектру; точные виземы (по фонемам) можно подать через `pose()`.
- `say()` озвучивает системным голосом; русский голос нужен в системе, иначе лицо говорит беззвучно.
- Микрофон и звук запускаются только по действию пользователя (политика браузеров).
- При `prefers-reduced-motion` отключаются покачивание головы и дрейф взгляда, остаются моргание и губы.
