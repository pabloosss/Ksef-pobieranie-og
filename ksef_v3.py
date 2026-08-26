import time
import tkinter as tk
from tkinter import messagebox

from selenium.webdriver.common.by import By

import ksef_fast_patch as fast
from emerlog_logo_b64 import EMERLOG_LOGO_B64

fix = fast.fix
fast.NO_DOWNLOAD_SIGNAL_TIMEOUT = 60
fast.PAGE_CHANGE_TIMEOUT = 6
fast.PAGE_RETRIES = 2
fix.DOWNLOAD_TIMEOUT = 180
fix.DOWNLOAD_RETRIES = 2
fix.RETRY_DELAYS = (2, 5)
fix.BATCH_PAUSE = 0.15
TABLE_WAIT_TIMEOUT = 12


class KsefV3(fast.FastKsefDownloader):
    def __init__(self, root):
        self._running = False
        super().__init__(root)
        self.root.title("KSeF - pobieranie faktur | EMERLOG")
        self.log("[INFO] Program gotowy.")

    def load_logo(self, parent):
        try:
            self.logo_img = tk.PhotoImage(data=EMERLOG_LOGO_B64)
            tk.Label(parent, image=self.logo_img, bg="black").pack(anchor="w")
        except Exception:
            super().load_logo(parent)

    def build_ui(self):
        super().build_ui()
        try:
            main = self.root.winfo_children()[0]
            header = main.winfo_children()[0]
            tk.Label(header, text="Paweł Ruchlicki", font=("Segoe UI", 10),
                     bg="black", fg="#d8d8d8").pack(anchor="w", pady=(8, 0))
        except Exception:
            pass
        self.step_var.set("Status: gotowe")
        self.result_var.set("")

    def log(self, text):
        repl = {
            "[FAST v2] Szybsza paginacja, zaznaczanie całej strony jednym kliknięciem i krótsze retry.": "[INFO] Szybkie pobieranie włączone.",
            "[FIX] Tryb niezawodny: max 10 FV/paczkę, PDF -> ZIP, retry 10→5→1.": "[INFO] Paczki po maks. 10 faktur.",
            "Retry za": "Ponawiam za",
            "Skan:": "Skanowanie:",
            "KSeF nadal generuje plik": "KSeF przygotowuje plik",
            "Dzielę nieudaną paczkę": "Dzielę paczkę",
            "Nie pobrano pojedynczej FV": "Nie udało się pobrać faktury",
        }
        for old, new in repl.items():
            text = text.replace(old, new)
        super().log(text)

    def set_step(self, text):
        text = text.replace("Partia", "Paczka").replace("próba", "podejście")
        text = text.replace("Pobieranie FV", "Pobieranie faktur")
        text = text.replace("Skanowanie listy FV", "Skanowanie listy faktur")
        super().set_step(text)

    def sleep(self, seconds):
        if 3.9 <= seconds <= 4.1:
            seconds = 0.8
        elif 0.3 <= seconds < 2:
            seconds = min(seconds, 0.25)
        end = time.time() + seconds
        while time.time() < end:
            try:
                self.root.update()
            except tk.TclError:
                return
            except Exception:
                pass
            time.sleep(min(0.05, max(0.01, end - time.time())))

    def download_all(self):
        if self._running:
            messagebox.showinfo("Pobieranie", "Pobieranie już trwa.")
            return
        self._running = True
        try:
            return super().download_all()
        finally:
            self._running = False

    def close(self):
        if self._running:
            messagebox.showinfo("Pobieranie w toku", "Poczekaj na zakończenie pobierania przed zamknięciem programu.")
            return
        super().close()

    def _next_candidates(self):
        return [
            (By.CSS_SELECTOR, "button[aria-label*='Następna']"),
            (By.CSS_SELECTOR, "button[title*='Następna']"),
            (By.CSS_SELECTOR, "[role='button'][aria-label*='Następna']"),
            (By.CSS_SELECTOR, "button[aria-label*='Next']"),
            (By.CSS_SELECTOR, "button[title*='Next']"),
            (By.XPATH, "//button[contains(normalize-space(.),'Następna') or contains(normalize-space(.),'Next')]"),
        ]

    def has_next_page(self):
        for by, value in self._next_candidates():
            try:
                elements = self.driver.find_elements(by, value)
            except Exception:
                continue
            for el in elements:
                try:
                    if el.is_displayed() and el.get_attribute("disabled") is None and el.get_attribute("aria-disabled") != "true":
                        return True
                except Exception:
                    pass
        return False

    def wait_rows(self, timeout=TABLE_WAIT_TIMEOUT):
        end = time.time() + timeout
        while time.time() < end:
            rows = self.row_items()
            if rows:
                return rows
            self.sleep(0.15)
        return []

    def scan_manifest(self):
        self.go_first_page()
        self.sleep(0.3)
        manifest, seen_pages, seen_ids = [], set(), set()
        page = 0

        while page < fix.base.MAX_PAGES:
            rows = self.wait_rows()
            sig = self.page_signature()
            if not rows or sig == "EMPTY":
                raise RuntimeError("Lista faktur nie załadowała się. Spróbuj ponownie.")
            if sig in seen_pages:
                if self.has_next_page():
                    raise RuntimeError("KSeF nie przełączył strony. Przerwałem, żeby nie pominąć faktur.")
                break

            seen_pages.add(sig)
            page += 1
            for item in rows:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    manifest.append({"id": item["id"], "text": item["text"], "page": page})

            self.log(f"[INFO] Skanowanie: strona {page}, razem {len(manifest)} faktur.")
            if not self.has_next_page():
                break
            if not self.go_next_page():
                raise RuntimeError(f"KSeF nie przeszedł ze strony {page} na następną. Przerwałem, żeby niczego nie pominąć.")

        self.go_first_page()
        self.sleep(0.3)
        return manifest

    def one_batch(self, items, session, batch_no):
        ids = [item["id"] for item in items]
        expected = len(items)

        for attempt in range(1, fix.DOWNLOAD_RETRIES + 1):
            self.set_step(f"Paczka {batch_no}: {expected} faktur, podejście {attempt}/{fix.DOWNLOAD_RETRIES}")
            selected = self.select_ids(ids)
            if len(selected) != expected:
                self.log(f"[UWAGA] Paczka {batch_no}: zaznaczono {len(selected)}/{expected}.")
                self.clear_selection()
            else:
                self.log(f"[INFO] Paczka {batch_no}: pobieram {expected} faktur.")
                path = self.download_pdf(session)
                if path:
                    pdfs = self.unpack(path, session)
                    if pdfs == expected:
                        self.log(f"[OK] Paczka {batch_no}: pobrano {pdfs}/{expected}.")
                        self.clear_selection()
                        self.sleep(fix.BATCH_PAUSE)
                        return True
                    self.log(f"[UWAGA] Paczka {batch_no}: pobrano {pdfs}/{expected} PDF. Ponawiam.")
                    self.debug_snapshot(session, f"batch_{batch_no}_count_{pdfs}_expected_{expected}")
                else:
                    self.log(f"[UWAGA] Paczka {batch_no}: nie dostałem pliku.")
                    self.debug_snapshot(session, f"batch_{batch_no}_attempt_{attempt}")
                self.clear_selection()

            if attempt < fix.DOWNLOAD_RETRIES:
                delay = fix.RETRY_DELAYS[attempt - 1]
                self.log(f"[INFO] Ponawiam za {delay} s.")
                self.sleep(delay)
        return False


def main():
    root = tk.Tk()
    KsefV3(root)
    root.mainloop()


if __name__ == "__main__":
    main()
