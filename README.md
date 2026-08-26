# KSeF Pobieranie

Program do pobierania większej liczby faktur z Aplikacji Podatnika KSeF 2.0.

## Uruchomienie

Najprościej zbudować EXE:

`build_fix_exe.bat`

Gotowy plik pojawi się w:

`dist\Ksef-Pobieranie-FIX.exe`

Można też uruchomić bezpośrednio:

`python ksef_final.py`

## Najważniejsze funkcje

- pobieranie faktur w paczkach po maks. 10,
- automatyczne retry i fallback 10 -> 5 -> 1,
- sprawdzanie liczby PDF w każdej paczce,
- zabezpieczenie przed pominięciem strony przy problemie z paginacją,
- szybsze zaznaczanie i odznaczanie,
- responsywne okno podczas dłuższego oczekiwania,
- log działania i dane diagnostyczne przy błędach,
- logo EMERLOG i podpis autora.

## Pliki

- `ksef_final.py` — finalna logika programu,
- `ksef_large_download_fix.py` — warstwa pobierania i fallbacku używana przez finalną wersję,
- `ksef_app_selenium_edge_fix.py` — rdzeń obsługi Selenium / Edge i GUI,
- `emerlog_logo_b64.py` — logo,
- `build_fix_exe.bat` — budowanie EXE,
- `requirements.txt` — wymagane pakiety.

Autor: Paweł Ruchlicki
