@echo off
cd /d "%~dp0"

echo =====================================
echo KSeF - build FINAL EXE
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
if exist dist\Ksef-Pobieranie-FIX.exe del /f /q dist\Ksef-Pobieranie-FIX.exe

%PY_CMD% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name Ksef-Pobieranie-FIX ^
  ksef_final.py
if errorlevel 1 goto :err

if not exist "%cd%\dist\Ksef-Pobieranie-FIX.exe" goto :err

echo.
echo [OK] Gotowe:
echo %cd%\dist\Ksef-Pobieranie-FIX.exe
start "" explorer "%cd%\dist"
start "" "%cd%\dist\Ksef-Pobieranie-FIX.exe"
pause
exit /b 0

:err
echo.
echo [BLAD] Build EXE nie powiodl sie.
echo Stary EXE zostal usuniety, wiec nie uruchomisz przypadkiem starej wersji.
pause
exit /b 1
