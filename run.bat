@echo off
REM Instala dependencias (una vez) y corre la app para probar.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python src\main.py
