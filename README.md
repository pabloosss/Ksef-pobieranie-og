# KSeF Pobieranie OG

Repozytorium programu do pobierania faktur z Aplikacji Podatnika KSeF 2.0.

## Wersja testowa do dużych pobrań

Uruchamiaj `ksef_large_download_fix.py` albo zbuduj EXE przez `build_fix_exe.bat`.

Najważniejsze poprawki:
- maksymalnie 10 FV w jednej operacji pobrania — zgodnie z limitem KSeF 2.0,
- każda strona jest dzielona na paczki po maks. 10 FV,
- wybierany jest format PDF; przy kilku fakturach KSeF sam zwraca ZIP,
- retry nieudanej paczki,
- fallback 10 -> 5 -> 1 FV zamiast przerwania całej operacji,
- dłuższe oczekiwanie na wygenerowanie pliku,
- krótka przerwa między paczkami i po dłuższej serii,
- poprawione rozpoznawanie numeru KSeF z literami w końcówce,
- `run_log.txt`, raport weryfikacji i folder `debug` ze screenshotem/HTML po nieudanej paczce.

## Stara wersja

`ksef_app_selenium_edge_fix.py` zostaje na razie bez zmian jako punkt odniesienia. Przed poprawką utworzono także branch:
`backup/pre-large-download-fix-20260826`.

Po potwierdzeniu, że nowa wersja przechodzi duże zestawy (np. 300+ FV), można podmienić nią główny plik programu.
