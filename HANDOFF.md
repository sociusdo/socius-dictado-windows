# HANDOFF — Socius Dictado para Windows (para la sesión de Claude Code en Windows)

Eres una sesión de Claude Code corriendo en **Windows** (el Bootcamp de la Mac de Luis).
Tu trabajo: **terminar, probar y empaquetar** esta app a un `.exe` funcional, y dejarla
lista para que Luis la pruebe. El código ya está escrito (en `src/`), pero **se escribió
en una Mac y NO se pudo ejecutar ahí** — tú eres quien la corre por primera vez en Windows.
Prueba todo, arregla lo que falle en Windows, y no asumas que algo sirve sin verlo correr.

## Qué es la app
Gemelo Windows de la app de Mac "Socius Dictado": un **círculo flotante púrpura**, siempre
encima de todo, que graba la voz, la transcribe con la **API de OpenAI del usuario** y
**pega el texto donde está el cursor**. Es un freebie para estudiantes del curso de Socius.

Debe comportarse **igual que la de Mac**:
- Clic en el círculo (o **Ctrl+Shift+Espacio**) → graba (sin límite) → clic de nuevo → transcribe → pega en el cursor.
- Anillo girando al transcribir; verde al pegar; ámbar si solo copió.
- Al pasar el mouse: botón **"Abrir"** (en reposo) / **"Cancelar"** (grabando). Clic derecho = menú.
- **Ctrl+Shift+D** muestra/oculta el círculo. Arrastrable, nunca se sale de pantalla.
- Ventana con **Historial** (títulos por IA, buscar, exportar, **borrar varias con casillas**)
  y **Ajustes** (modelo, idioma, modo IA, diccionario, API key, color, sonido, arranque al inicio, uso).
- Icono en la bandeja (tray) con menú. API key guardada en el Administrador de credenciales (keyring).

## Stack
Python 3.11+ con **PyQt6** (UI), **sounddevice/numpy** (audio), **requests** (OpenAI),
**keyboard** (atajos globales + Ctrl+V), **pyperclip** (portapapeles), **keyring** (API key).
Empaquetado con **PyInstaller** a un `.exe` único.

## Estructura
```
src/
  main.py         entry: QApplication, tray, hotkeys, cableado
  orb.py          círculo flotante (frameless, translúcido, always-on-top, drag+clamp, botón hover, menú)
  controller.py   máquina de estados: grabar→transcribir→(modo IA)→pegar; señales Qt
  recorder.py     graba a WAV mono 16k (sounddevice)
  transcriber.py  POST /v1/audio/transcriptions + troceo paralelo + reintentos
  ai.py           modos IA + títulos IA (/v1/chat/completions, gpt-4o-mini)
  paster.py       portapapeles + Ctrl+V (keyboard)
  hotkeys.py      atajos globales (keyboard)
  store.py        historial JSON en %APPDATA%\SociusDictado
  config.py       ajustes JSON + API key en keyring
  window.py       ventana Historial + Ajustes
  theme.py, paths.py
requirements.txt, run.bat, build_exe.bat, README.md
```

## Pasos que debes seguir
1. **Verifica Python**: `python --version` (si falta, instálalo desde python.org, 3.11+,
   marcando "Add to PATH"). Si Luis no lo tiene, guíalo.
2. **Instala y corre para probar**:
   ```bat
   run.bat
   ```
   (hace `pip install -r requirements.txt` y lanza `src\main.py`.)
3. **Configura la API key**: la primera vez se abre Ajustes; pega la key de OpenAI del
   usuario (`sk-...`). NO la inventes ni la escribas en archivos/repo; es secreta y va al
   keyring. Si Luis no la tiene a mano, pídesela.
4. **Prueba CADA cosa y arregla lo que falle en Windows** (ver checklist abajo). No digas
   "listo" sin haberlo visto funcionar. Para depurar, lee `%APPDATA%\SociusDictado\debug.log`
   si agregas logging, y usa la consola (corre `python src\main.py` desde `cmd` para ver errores).
5. **Empaqueta el .exe**:
   ```bat
   build_exe.bat
   ```
   Resultado: `dist\SociusDictado.exe`. **Pruébalo haciendo doble clic** (no solo desde
   Python) — PyInstaller a veces omite imports; si truena, agrega `--hidden-import` o
   `--collect-all` del módulo que falte y recompila.
6. **Entrega**: deja `dist\SociusDictado.exe` listo; ese es el archivo final para Luis.
   Si vas a publicarlo en GitHub Releases, súbelo ahí (ver "GitHub" abajo).

## Checklist de pruebas (todo debe verse funcionando)
- [ ] El círculo aparece abajo a la derecha, encima de otras ventanas, sin botón en la barra de tareas.
- [ ] Clic en el círculo → se pone rojo (grabando) → clic → gira el anillo → pega el texto en el cursor (abre el Bloc de notas y prueba).
- [ ] **Ctrl+Shift+Espacio** inicia/para el dictado con el cursor en un textbox.
- [ ] **Ctrl+Shift+D** oculta/muestra el círculo.
- [ ] Pasar el mouse muestra "Abrir"; grabando muestra "Cancelar"; **Cancelar detiene de verdad**.
- [ ] Clic derecho en el círculo abre el menú (Abrir/Cancelar/Ajustes/Salir).
- [ ] Arrastrar el círculo: no se sale de la pantalla por ningún borde.
- [ ] Ventana → Historial: aparece el dictado con **título por IA**, fecha mm/dd/yy, duración, palabras.
- [ ] Historial: buscar filtra; **marcar casillas + "Borrar marcadas"** borra varias; Exportar genera .md.
- [ ] Ajustes: cambiar modelo/idioma/modo IA/diccionario/color/sonido persiste; guardar API key funciona; "Salir" cierra.
- [ ] Modo IA (ej. "Traducir a inglés") transforma el texto antes de pegar.
- [ ] Icono en la bandeja con su menú.
- [ ] El `.exe` compilado hace todo lo anterior.

## Gotchas / cosas específicas de Windows a vigilar
- **Micrófono**: Windows 11 tiene Configuración → Privacidad → Micrófono → "Permitir que las
  apps de escritorio accedan al micrófono". Suele estar activo; si `sounddevice` no graba,
  revísalo. No hace falta permiso de "accesibilidad" como en Mac.
- **Pegar**: en Windows NO se necesita permiso especial; `keyboard.send('ctrl+v')` basta. Si
  no cae en algún app, el texto igual queda en el portapapeles (Ctrl+V manual como respaldo).
- **`keyboard` (atajos globales)**: normalmente funciona sin admin para estas combinaciones.
  Si algún atajo no dispara, puede requerir ejecutar como administrador, o cambiar el combo.
  Un antivirus agresivo puede bloquear la simulación de teclado; avísale a Luis si pasa.
- **PyInstaller + keyring**: el backend de Windows a veces no se incluye solo; ya está el
  `--hidden-import keyring.backends.Windows`. Si la key no guarda en el .exe, agrega
  `--collect-all keyring`.
- **PyInstaller + sounddevice**: necesita la DLL de PortAudio; ya está `--collect-all sounddevice`.
- **SmartScreen**: el .exe no está firmado → "Windows protegió tu PC" → Más información →
  Ejecutar de todas formas. Documéntalo para el estudiante (ya está en el README).
- **Always-on-top sobre apps en pantalla completa**: `WindowStaysOnTopHint` cubre la mayoría;
  sobre juegos en exclusivo full-screen puede no verse (limitación de Windows, aceptable).
- **Los .bat**: si se corrompieron los saltos de línea (vinieron de Mac/zip), reescríbelos o
  corre los comandos a mano.

## Reglas
- La **API key es secreto de Luis**: solo al keyring/Ajustes, nunca al repo, a un archivo de
  texto, ni a tus mensajes. No la inventes; si hace falta, pídesela.
- **Verifica antes de afirmar**: corre y observa; usa la consola para ver trazas. No declares
  una función lista sin haberla visto.
- No cambies el diseño/colores de marca (púrpura #6D28D9 → negro). Mantén la paridad con Mac.

## GitHub (ya creado)
Repo público: **https://github.com/sociusdo/socius-dictado-windows** (cuenta `sociusdo`).
La versión Mac vive en https://github.com/sociusdo/socius-dictado-mac.
Puedes **clonar** el repo de Windows en vez de usar el zip:
```bat
gh repo clone sociusdo/socius-dictado-windows
```
Cuando el `.exe` funcione, súbelo como **Release** (`gh release create v1.0 dist\SociusDictado.exe
--title "v1.0" --notes "Primera versión"`) para que los estudiantes solo descarguen el ejecutable.
Commitea y haz push de cualquier arreglo Windows que hagas.

## Estado al entregar este handoff (qué YA se verificó en Mac)
- **Sintaxis** de todos los módulos: OK (`py_compile`).
- **Lógica central** probada: títulos (fallback + por IA), fecha mm/dd/yy, duración, config/defaults, store.
- **Camino real a OpenAI probado end-to-end** desde Mac: `ai.make_title` devolvió un título correcto
  y `ai.apply_mode('translate_en', …)` tradujo bien (auth + request + parseo verificados). El
  transcriptor (`/v1/audio/transcriptions`) usa el MISMO patrón de auth/reintentos.
- **NO probado (requiere Windows, es TU tarea)**: la GUI (PyQt6 orb/ventana/tray), captura de
  micrófono (sounddevice), pegado (Ctrl+V), atajos globales (keyboard), guardado en keyring, y
  el empaquetado a `.exe`. Empieza por `run.bat` y recorre el checklist.
