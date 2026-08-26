# KSeF Pobieranie OG

Program do pobierania większej liczby faktur z Aplikacji Podatnika KSeF 2.0.

## Uruchomienie

Uruchom:

`ksef_large_download_fix.py`

albo zbuduj wersję EXE przez:

`build_fix_exe.bat`

## Najważniejsze funkcje

- pobieranie faktur partiami zgodnie z limitem KSeF,
- maksymalnie 10 FV w jednej operacji,
- automatyczny podział większych zestawów na paczki,
- retry nieudanych pobrań,
- fallback 10 -> 5 -> 1 FV zamiast zatrzymania całego procesu,
- obsługa PDF i ZIP,
- dłuższe oczekiwanie na wygenerowanie pliku,
- przerwy między paczkami przy dużych pobraniach,
- rozpoznawanie numerów KSeF z literami w końcówce,
- log działania i dane diagnostyczne przy błędach.

## Pliki

- `ksef_large_download_fix.py` — główny program,
- `build_fix_exe.bat` — budowanie wersji EXE,
- `requirements.txt` — wymagane pakiety Pythona.

Starsza wersja programu jest zachowana w historii Git oraz na branchu `backup/pre-large-download-fix-20260826`.
