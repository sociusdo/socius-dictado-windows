# Socius Dictado (Windows)

Dictado por voz con tu propia API de OpenAI, estilo WhisperFlow. Un **círculo
flotante** púrpura, siempre encima de todo: haces clic, hablas, y el texto se
**pega solo donde está tu cursor**. Gemelo de la versión para Mac.

> Freebie del curso de Socius. 🎤

### ⬇️ [Descargar SociusDictado.exe](https://github.com/sociusdo/socius-dictado-windows/releases/latest/download/SociusDictado.exe)
Última versión: [v1.0](https://github.com/sociusdo/socius-dictado-windows/releases/tag/v1.0) · Windows 10/11 · no necesitas instalar Python.

## 🚀 La forma más fácil: deja que Claude te guíe
Si usas **Claude Code**: descarga/clona esta carpeta, abre Claude Code dentro de ella y dile
**"ayúdame a instalar Socius Dictado"**. Claude lee las instrucciones del repo (`CLAUDE.md`)
y te lleva **paso a paso**: crear tu API key de OpenAI, instalar/compilar, permisos y probar.

## Para usarlo (ejecutable ya compilado)
1. Descarga **[SociusDictado.exe](https://github.com/sociusdo/socius-dictado-windows/releases/latest/download/SociusDictado.exe)**
   (o desde la página de [Releases](https://github.com/sociusdo/socius-dictado-windows/releases)).
2. Ábrelo (Windows puede mostrar "Windows protegió tu PC" por ser un .exe sin
   firma de editor → **Más información → Ejecutar de todas formas**).
3. La primera vez, pega tu **API key de OpenAI** (`sk-...`) en **Ajustes** (se
   guarda cifrada en el Administrador de credenciales de Windows, nunca en texto).
4. Haz clic en el círculo (o **Ctrl+Shift+Espacio**) para dictar; el texto se
   pega donde esté tu cursor.

## Atajos
- **Ctrl+Shift+Espacio** — empezar / parar dictado
- **Ctrl+Shift+D** — mostrar / ocultar el círculo
- Clic en el círculo — grabar/parar · Clic derecho — menú (Abrir, Cancelar, Ajustes, Salir)

## Funciones
Círculo flotante arrastrable (no se sale de pantalla), transcripción con OpenAI
(rápido/preciso), idioma auto/es/en, **modos IA** antes de pegar (limpiar, bullets,
correo, traducir), **diccionario personal**, historial con **títulos generados por
IA**, buscar, exportar, borrar varias, contador de uso, arrancar al iniciar sesión,
icono en la bandeja.

## Correr desde el código (para desarrollar)
Requiere Python 3.11+.
```bat
run.bat
```
Para compilar el `.exe`:
```bat
build_exe.bat
```
El ejecutable queda en `dist\SociusDictado.exe`.

## Privacidad
La API key vive solo en el Administrador de credenciales de Windows. El audio se
envía a OpenAI para transcribir; solo el **texto** se guarda localmente en el
historial (`%APPDATA%\SociusDictado\history.json`).
