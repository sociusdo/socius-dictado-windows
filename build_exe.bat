@echo off
REM Empaqueta un .exe único (Windows) con PyInstaller.
REM Resultado: dist\SociusDictado.exe  (eso es lo que se le manda al usuario final)
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

python -m PyInstaller --noconfirm --onefile --windowed --name "SociusDictado" ^
  --icon "src\assets\icon.ico" ^
  --add-data "src\assets\icon.png;assets" ^
  --add-data "src\assets\icon.ico;assets" ^
  --collect-all sounddevice ^
  --collect-submodules keyring ^
  --hidden-import keyring.backends.Windows ^
  --hidden-import win32timezone ^
  src\main.py

echo.
echo Listo. El ejecutable esta en: dist\SociusDictado.exe
