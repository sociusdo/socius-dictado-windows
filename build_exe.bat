@echo off
REM Empaqueta un .exe único (Windows) con PyInstaller.
REM Resultado: dist\SociusDictado.exe  (eso es lo que se le manda al usuario final)
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

pyinstaller --noconfirm --onefile --windowed --name "SociusDictado" ^
  --collect-all sounddevice ^
  --collect-submodules keyring ^
  --hidden-import keyring.backends.Windows ^
  --hidden-import win32timezone ^
  src\main.py

echo.
echo Listo. El ejecutable esta en: dist\SociusDictado.exe
