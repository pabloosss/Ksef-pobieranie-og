import os
import time
import tkinter as tk

from selenium.webdriver.common.by import By

import ksef_large_download_fix as fix

# Szybsze ustawienia, ale bez rezygnacji z retry/fallbacku.
fix.DOWNLOAD_TIMEOUT = 150
fix.DOWNLOAD_RETRIES = 2
fix.RETRY_DELAYS = (2, 5)
fix.BATCH_PAUSE = 0.15

NO_DOWNLOAD_SIGNAL_TIMEOUT = 40
PAGE_CHANGE_TIMEOUT = 7
PAGE_RETRIES = 2


class FastKsefDownloader(fix.ReliableKsefDownloader):
    def __init__(self, root):
        super().__init__(root)
        self.log("[FAST v2] Szybsza paginacja, zaznaczanie całej strony jednym kliknięciem i krótsze retry.")

    def sleep(self, seconds):
        # Stara wersja robiła 4 s przerwy co serię paczek. 0,8 s wystarczy.
        if 3.9 <= seconds <= 4.1:
            seconds = 0.8
        # Krótkie techniczne pauzy nie muszą trwać 0,5-1,5 s.
        elif 0.3 <= seconds < 2:
            seconds = min(seconds, 0.25)

        end = time.time() + seconds
        while time.time() < end:
            try:
                self.root.update_idletasks()
            except Exception:
                pass
            time.sleep(min(0.08, max(0.01, end - time.time())))

    def click_any(self, candidates, timeout=3, delay=0.4):
        # W starej wersji każdy selektor miał osobny WebDriverWait.
        # Przy 5-6 selektorach timeouty potrafiły sumować się do minut.
        end = time.time() + min(float(timeout), 2.5)
        while time.time() < end:
            for by, value in candidates:
                try:
                    elements = self.driver.find_elements(by, value)
                except Exception:
                    elements = []
                for el in elements:
                    try:
                        if not el.is_displayed():
                            continue
                        if el.get_attribute("disabled") is not None:
                            continue
                        if el.get_attribute("aria-disabled") == "true":
                            continue
                        if self.click_element(el, min(float(delay), 0.08)):
                            return True
                    except Exception:
                        pass
            self.sleep(0.08)
        return False

    def go_next_page(self):
        before = self.page_signature()
        candidates = [
            (By.CSS_SELECTOR, "button[aria-label*='Następna']"),
            (By.CSS_SELECTOR, "button[title*='Następna']"),
            (By.CSS_SELECTOR, "[role='button'][aria-label*='Następna']"),
            (By.CSS_SELECTOR, "button[aria-label*='Next']"),
            (By.CSS_SELECTOR, "button[title*='Next']"),
            (By.XPATH, "//button[contains(normalize-space(.),'Następna') or contains(normalize-space(.),'Next')]"),
        ]

        # Koniec listy: nie czekaj na timeouty, jeśli przycisk jest wyłączony.
        enabled = False
        for by, value in candidates:
            try:
                elements = self.driver.find_elements(by, value)
            except Exception:
                elements = []
            for el in elements:
                try:
                    if not el.is_displayed():
                        continue
                    if el.get_attribute("disabled") is not None:
                        continue
                    if el.get_attribute("aria-disabled") == "true":
                        continue
                    enabled = True
                    break
                except Exception:
                    pass
            if enabled:
                break
        if not enabled:
            return False

        for attempt in range(1, PAGE_RETRIES + 1):
            if not self.click_any(candidates, timeout=1.2, delay=0.03):
                return False

            end = time.time() + PAGE_CHANGE_TIMEOUT
            while time.time() < end:
                after = self.page_signature()
                if after != before and after != "EMPTY":
                    return True
                self.sleep(0.12)

            self.log(
                f"[UWAGA] Zmiana strony trwa ponad {PAGE_CHANGE_TIMEOUT}s "
                f"({attempt}/{PAGE_RETRIES}) - ponawiam kliknięcie."
            )

        return False

    def _header_checkbox(self):
        selectors = [
            "thead input[type='checkbox']",
            "table thead [role='checkbox']",
            "thead [role='checkbox']",
        ]
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                elements = []
            for el in elements:
                try:
                    if el.is_displayed() and el.get_attribute("disabled") is None:
                        return el
                except Exception:
                    pass
        return None

    def clear_selection(self):
        rows = self.row_items()
        selected = [item for item in rows if self.is_selected(item["check"])]
        if not selected:
            return 0

        # Najczęstszy przypadek: 10/10 zaznaczone. Jedno kliknięcie zamiast 10.
        if len(selected) == len(rows):
            header = self._header_checkbox()
            if header is not None and self.click_element(header, 0.03):
                self.sleep(0.06)
                if not any(self.is_selected(item["check"]) for item in self.row_items()):
                    return len(selected)

        changed = 0
        for item in selected:
            try:
                if self.click_element(item["check"], 0.02):
                    changed += 1
            except Exception:
                pass
        return changed

    def select_ids(self, ids):
        wanted = list(ids)
        wanted_set = set(wanted)
        rows = self.row_items()
        actual = {item["id"] for item in rows if self.is_selected(item["check"])}

        if actual == wanted_set:
            return wanted
        if actual:
            self.clear_selection()
            rows = self.row_items()

        # Jeżeli aktualna strona ma <=10 FV i pobieramy ją w całości,
        # zaznacz nagłówek jednym kliknięciem zamiast klikać każdy wiersz.
        row_ids = [item["id"] for item in rows]
        if len(rows) <= fix.MAX_BATCH and set(row_ids) == wanted_set:
            header = self._header_checkbox()
            if header is not None and self.click_element(header, 0.03):
                self.sleep(0.08)
                selected_now = {
                    item["id"] for item in self.row_items()
                    if self.is_selected(item["check"])
                }
                if selected_now == wanted_set:
                    return wanted
                self.clear_selection()
                rows = self.row_items()

        # Fallback dla części strony / paczek 5→1.
        for item in rows:
            if item["id"] not in wanted_set:
                continue
            try:
                if not self.is_selected(item["check"]):
                    self.click_element(item["check"], 0.02)
            except Exception:
                pass

        actual = {
            item["id"] for item in self.row_items()
            if self.is_selected(item["check"])
        }
        return [item_id for item_id in wanted if item_id in actual]

    def _ksef_busy(self):
        selectors = [
            "mat-spinner",
            "mat-progress-spinner",
            ".mat-mdc-progress-spinner",
            "[role='progressbar']",
            ".loading",
            ".spinner",
        ]
        for selector in selectors:
            try:
                if any(el.is_displayed() for el in self.driver.find_elements(By.CSS_SELECTOR, selector)):
                    return True
            except Exception:
                pass
        return False

    def wait_new_download(self, folder, before):
        start = time.time()
        sizes = {}
        stable = {}
        saw_signal = False
        logged = set()

        while time.time() - start < fix.DOWNLOAD_TIMEOUT:
            try:
                names = set(os.listdir(folder))
            except Exception:
                names = set()

            temps = [name for name in names if name.lower().endswith(fix.TEMP_EXTS)]
            if temps:
                saw_signal = True

            candidates = []
            for name in names - before:
                if name.lower().endswith(fix.TEMP_EXTS):
                    continue
                path = os.path.join(folder, name)
                if os.path.isfile(path):
                    candidates.append(path)

            if candidates:
                saw_signal = True
                path = max(candidates, key=os.path.getmtime)
                try:
                    size = os.path.getsize(path)
                except Exception:
                    size = 0

                if size > 0:
                    stable[path] = (
                        stable.get(path, 0) + 1
                        if sizes.get(path) == size and not temps
                        else 0
                    )
                    sizes[path] = size
                    # Dwa równe odczyty rozmiaru wystarczą.
                    if stable[path] >= 1:
                        return path

            elapsed = int(time.time() - start)
            for marker in (15, 30, 60, 90, 120):
                if elapsed >= marker and marker not in logged:
                    logged.add(marker)
                    self.log(f"[INFO] KSeF nadal generuje plik... {marker}s")

            # Jeżeli nic kompletnie nie ruszyło i nie ma spinnera,
            # nie czekaj 120-150 s - zrób retry wcześniej.
            if (
                not saw_signal
                and elapsed >= NO_DOWNLOAD_SIGNAL_TIMEOUT
                and not self._ksef_busy()
            ):
                self.log(
                    f"[UWAGA] Brak sygnału pobierania przez "
                    f"{NO_DOWNLOAD_SIGNAL_TIMEOUT}s - szybki retry."
                )
                return None

            self.sleep(0.25)

        return None


def main():
    root = tk.Tk()
    FastKsefDownloader(root)
    root.mainloop()


if __name__ == "__main__":
    main()
