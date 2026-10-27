# LISA 3D: голограмма в полный рост

Девушка-голограмма со скелетом и лицевой мимикой. Движения записаны с живых людей (захват движения), поэтому они естественные и гибкие.

- **По умолчанию танцует.** Через 25 с тишины снова начинает танцевать.
- **Ей написали:** перестаёт танцевать, поворачивается к зрителю и слушает. Если в сообщении команда, выполняет её.
- **Говорит:** жестикулирует руками, как будто объясняет. Губы двигаются под речь, она моргает и смотрит на собеседника.
- **10 стилей танцев, 20 записей:** сальса, чарльстон, линди-хоп, индийский, современный, русский, лунная походка, твист, макарена, танец утят.
- **Действия:** сесть, лечь, встать, идти, бежать, прыгнуть, покружиться, развернуться, помахать, поклон, потянуться, смех, радость, пожать плечами, «дай пять», «ку-ку», зарядка.

## Готовые файлы

- `dist/lisa3d-hologram.html`: чистая голограмма на весь экран, без текста и кнопок. Один файл примерно на 10 МБ, работает без сервера и интернета.
- `dist/lisa3d-demo.html`: то же с панелью для проверки: написать ей, сказать вслух, кнопки танцев и действий.

## Встраивание

**Android (WebView)**: положите `lisa3d-hologram.html` в `app/src/main/assets/`.
```kotlin
webView.settings.javaScriptEnabled = true
webView.settings.mediaPlaybackRequiresUserGesture = false
webView.loadUrl("file:///android_asset/lisa3d-hologram.html")
webView.evaluateJavascript("lisa.message('станцуй сальсу')", null)   // сообщение пользователя: команда или просто текст
webView.evaluateJavascript("lisa.feed(0.7)", null)                  // громкость голоса ассистента 0..1, 20-60 раз в секунду
```

**iOS (WKWebView)**: добавьте файл в бандл, `loadFileURL(...)`, команды через `evaluateJavaScript("lisa.message('сядь')")`.

**Веб (iframe)**:
```html
<iframe id="lisa" src="lisa3d-hologram.html" style="width:100%;height:100%;border:0" allow="autoplay"></iframe>
<script>
const lisa = document.getElementById('lisa').contentWindow;
lisa.postMessage({ lisa: 'message', text: 'станцуй макарену' }, '*');
lisa.postMessage({ lisa: 'feed', level: 0.6 }, '*');
addEventListener('message', e => { if (e.data && e.data.lisa) console.log(e.data.event, e.data.value); });   // ready, command, state, action, speakstart, speakend
</script>
```
Команды через `postMessage`: `message {text}`, `do {action, style}`, `say {text, mood, silent}`, `audio {src, text}`, `feed {level, round, stretch}`, `stop`, `attention`, `state {value}`, `mood {value}`.

Параметры адреса: `?dance=0` не танцевать при запуске, `?after=40` через сколько секунд тишины снова танцевать.

## API (`window.lisa`)

| Вызов | Что делает |
|---|---|
| `message(text)` | Сообщение пользователя: останавливает танец; если это команда, выполняет и возвращает `{action, style}`, иначе `null` |
| `attention()` | Пользователь начал печатать: перестаёт танцевать и слушает |
| `do(action, {style})` | Действие напрямую: `dance, stop, sit, lie, stand, walk, run, jump, spin, turn, wave, bow, stretch, laugh, happy, shrug, highfive, peekaboo, jacks` |
| `dance(style?)` | Танец: `salsa, charleston, lindy, indian, modern, russian, moonwalk, twist, macarena, chicken` или любой |
| `say(text, {mood, rate, silent})` | Говорит системным голосом (или беззвучно): жесты и губы |
| `speakAudio(src, {text})` | Говорит звуком вашего синтеза речи (URL, Blob, `<audio>`, MediaStream): губы по звуку |
| `feed(level)` | Голос играет само приложение: передавайте громкость 0..1, губы и жесты идут за ним, через 0.4 с без данных замолкает |
| `stop()` | Остановить речь |
| `setState('idle' \| 'listening' \| 'thinking')`, `setMood('happy' \| 'sad' \| 'surprised' \| 'thinking' \| 'neutral')` | Состояние и настроение |
| `on(event, fn)` | `state`, `action`, `speakstart`, `speakend`, `text` |
| `command(text)` | Только разобрать команду, ничего не делая |

Команды понимаются в свободной форме: «станцуй», «потанцуй сальсу», «сядь», «ляг», «встань», «иди», «беги», «прыгни», «покружись», «повернись», «помаши», «поклонись», «потянись», «посмейся», «порадуйся», «пожми плечами», «дай пять», «ку-ку», «зарядка», «стоп/хватит».

## Пересборка

```
cd lisa3d/tools
./fetch-data.sh                          # модель и записи движений
pip install numpy scipy && python3 export_motions.py      # перенос движений -> ../motions.bin
npm i three@0.186.1 esbuild @gltf-transform/core @gltf-transform/extensions @gltf-transform/functions meshoptimizer sharp
node optimize-avatar.mjs data/mpfb.glb ../avatar.glb
node build.mjs ../src/lisa3d.js ../lisa3d.js
python3 build-single.py                  # -> ../dist
```

Реалистичный вид (`style: 'real'`), свой костюм, лицо с фото и волосы: `avatar2/README.md`.

Лицензии компонентов: `LICENSES.md`.
