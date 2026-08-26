@echo off
cd /d "%~dp0"

echo =====================================
echo KSeF - build FAST v2 EXE
echo =====================================

python --version >nul 2>nul
if errorlevel 1 (
    py --version >nul 2>nul
    if errorlevel 1 (
        echo [BLAD] Python nie jest zainstalowany albo nie ma go w PATH.
        pause
        exit /b 1
    ) else (
        set PY_CMD=py
    )
) else (
    set PY_CMD=python
)

%PY_CMD% -m pip install --upgrade pip
if errorlevel 1 goto :err
%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto :err

if exist build\Ksef-Pobieranie-FIX rmdir /s /q build\Ksef-Pobieranie-FIX

%PY_CMD% -m PyInstaller ^
  --noconfirm ^
  --onefile ^
  --windowed ^
  --name Ksef-Pobieranie-FIX ^
  ksef_fast_patch.py
if errorlevel 1 goto :err

echo.
echo [OK] Gotowe - FAST v2:
echo %cd%\dist\Ksef-Pobieranie-FIX.exe
start "" explorer "%cd%\dist"
pause
exit /b 0

:err
echo.
echo [BLAD] Build EXE nie powiodl sie.
pause
exit /b 1
