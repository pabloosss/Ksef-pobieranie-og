import os
import re
import time
import traceback
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from selenium.webdriver.common.by import By

import ksef_large_download_fix as fix
from emerlog_logo_b64 import EMERLOG_LOGO_B64

# Ustawienia finalnej wersji
fix.DOWNLOAD_TIMEOUT = 180
fix.DOWNLOAD_RETRIES = 2
fix.RETRY_DELAYS = (2, 5)
fix.BATCH_PAUSE = 0.15

NO_DOWNLOAD_SIGNAL_TIMEOUT = 60
PAGE_CHANGE_TIMEOUT = 6
PAGE_RETRIES = 2
TABLE_WAIT_TIMEOUT = 12


class KsefFinal(fix.ReliableKsefDownloader):
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
            tk.Label(
                header,
                text="Paweł Ruchlicki",
                font=("Segoe UI", 10),
                bg="black",
                fg="#d8d8d8",
            ).pack(anchor="w", pady=(8, 0))
        except Exception:
            pass
        self.step_var.set("Status: gotowe")
        self.result_var.set("")

    def log(self, text):
        replacements = {
            "[FIX] Tryb niezawodny: max 10 FV/paczkę, PDF -> ZIP, retry 10→5→1.": "[INFO] Pobieranie w paczkach po maks. 10 faktur.",
            "Retry za": "Ponawiam za",
            "Skan:": "Skanowanie:",
            "KSeF nadal generuje plik": "KSeF przygotowuje plik",
            "Dzielę nieudaną paczkę": "Dzielę paczkę",
            "Nie pobrano pojedynczej FV": "Nie udało się pobrać faktury",
        }
        for old, new in replacements.items():
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

    def click_any(self, candidates, timeout=3, delay=0.4):
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

    def next_candidates(self):
        return [
            (By.CSS_SELECTOR, "button[aria-label*='Następna']"),
            (By.CSS_SELECTOR, "button[title*='Następna']"),
            (By.CSS_SELECTOR, "[role='button'][aria-label*='Następna']"),
            (By.CSS_SELECTOR, "button[aria-label*='Next']"),
            (By.CSS_SELECTOR, "button[title*='Next']"),
            (By.XPATH, "//button[contains(normalize-space(.),'Następna') or contains(normalize-space(.),'Next')]"),
        ]

    def has_next_page(self):
        for by, value in self.next_candidates():
            try:
                elements = self.driver.find_elements(by, value)
            except Exception:
                continue
            for el in elements:
                try:
                    if not el.is_displayed():
                        continue
                    if el.get_attribute("disabled") is not None:
                        continue
                    if el.get_attribute("aria-disabled") == "true":
                        continue
                    return True
                except Exception:
                    pass
        return False

    def go_next_page(self):
        before = self.page_signature()
        if not self.has_next_page():
            return False

        for attempt in range(1, PAGE_RETRIES + 1):
            if not self.click_any(self.next_candidates(), timeout=1.2, delay=0.03):
                continue

            end = time.time() + PAGE_CHANGE_TIMEOUT
            while time.time() < end:
                after = self.page_signature()
                if after != before and after != "EMPTY":
                    return True
                self.sleep(0.12)

            self.log(f"[UWAGA] Strona nie przełączyła się od razu ({attempt}/{PAGE_RETRIES}).")
        return False

    def wait_rows(self, timeout=TABLE_WAIT_TIMEOUT):
        end = time.time() + timeout
        while time.time() < end:
            rows = self.row_items()
            if rows:
                return rows
            self.sleep(0.15)
        return []

    def header_checkbox(self):
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

        if len(selected) == len(rows):
            header = self.header_checkbox()
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

        row_ids = [item["id"] for item in rows]
        if len(rows) <= fix.MAX_BATCH and set(row_ids) == wanted_set:
            header = self.header_checkbox()
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

    def ksef_busy(self):
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
                    stable[path] = stable.get(path, 0) + 1 if sizes.get(path) == size and not temps else 0
                    sizes[path] = size
                    if stable[path] >= 1:
                        return path

            elapsed = int(time.time() - start)
            for marker in (15, 30, 60, 90, 120, 150):
                if elapsed >= marker and marker not in logged:
                    logged.add(marker)
                    self.log(f"[INFO] KSeF przygotowuje plik... {marker} s")

            if not saw_signal and elapsed >= NO_DOWNLOAD_SIGNAL_TIMEOUT and not self.ksef_busy():
                self.log(f"[UWAGA] Pobieranie nie ruszyło przez {NO_DOWNLOAD_SIGNAL_TIMEOUT} s. Ponawiam.")
                return None

            self.sleep(0.25)
        return None

    def scan_manifest(self):
        self.go_first_page()
        self.sleep(0.3)
        manifest = []
        seen_pages = set()
        seen_ids = set()
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

            self.found_var.set(str(len(manifest)))
            self.log(f"[INFO] Skanowanie: strona {page}, razem {len(manifest)} faktur.")

            if not self.has_next_page():
                break
            if not self.go_next_page():
                raise RuntimeError(
                    f"KSeF nie przeszedł ze strony {page} na następną. "
                    "Przerwałem, żeby niczego nie pominąć."
                )

        self.go_first_page()
        self.sleep(0.3)
        return manifest

    def one_batch(self, items, session, batch_no):
        ids = [item["id"] for item in items]
        expected = len(items)

        for attempt in range(1, fix.DOWNLOAD_RETRIES + 1):
            self.set_step(
                f"Paczka {batch_no}: {expected} faktur, "
                f"podejście {attempt}/{fix.DOWNLOAD_RETRIES}"
            )
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

                    self.log(
                        f"[UWAGA] Paczka {batch_no}: pobrano {pdfs}/{expected} PDF. Ponawiam."
                    )
                    self.debug_snapshot(
                        session,
                        f"batch_{batch_no}_count_{pdfs}_expected_{expected}",
                    )
                else:
                    self.log(f"[UWAGA] Paczka {batch_no}: nie dostałem pliku.")
                    self.debug_snapshot(session, f"batch_{batch_no}_attempt_{attempt}")
                self.clear_selection()

            if attempt < fix.DOWNLOAD_RETRIES:
                delay = fix.RETRY_DELAYS[attempt - 1]
                self.log(f"[INFO] Ponawiam za {delay} s.")
                self.sleep(delay)
        return False

    def download_all(self):
        if self._running:
            messagebox.showinfo("Pobieranie", "Pobieranie już trwa.")
            return
        if not self.driver:
            messagebox.showwarning("Uwaga", "Najpierw kliknij Start / Otwórz KSeF.")
            return

        self._running = True
        session = None

        try:
            self.start_pulse("Skanowanie listy faktur")
            manifest = self.scan_manifest()
            if not manifest:
                self.stop_pulse("Brak faktur")
                messagebox.showwarning("Brak faktur", "Nie znalazłem faktur na aktualnej liście.")
                return

            self.found_var.set(str(len(manifest)))
            session = os.path.join(
                self.download_dir,
                datetime.now().strftime("%Y-%m-%d__%H-%M-%S__WSZYSTKIE_FV"),
            )
            os.makedirs(session, exist_ok=True)
            self.session_log_path = os.path.join(session, "run_log.txt")
            self.log(f"[INFO] Start pobierania: {len(manifest)} faktur.")

            targets = {item["id"]: item for item in manifest}
            done = set()
            failed = []
            failed_ids = set()
            seen_pages = set()
            batch_no = 1
            page = 0

            self.go_first_page()
            self.sleep(0.3)

            while len(done) + len(failed_ids) < len(manifest) and page < fix.base.MAX_PAGES:
                rows = self.wait_rows()
                sig = self.page_signature()

                if not rows or sig == "EMPTY":
                    raise RuntimeError("Tabela faktur zniknęła podczas pobierania.")
                if sig in seen_pages:
                    if self.has_next_page():
                        raise RuntimeError(
                            "KSeF nie przełączył strony podczas pobierania. "
                            "Przerwałem, żeby niczego nie pominąć."
                        )
                    break

                seen_pages.add(sig)
                page += 1
                page_items = [
                    targets[row["id"]]
                    for row in rows
                    if row["id"] in targets
                    and row["id"] not in done
                    and row["id"] not in failed_ids
                ]
                self.log(f"[INFO] Strona {page}: {len(page_items)} faktur do pobrania.")

                for start in range(0, len(page_items), fix.MAX_BATCH):
                    batch = page_items[start:start + fix.MAX_BATCH]
                    if not batch:
                        continue

                    _, batch_no = self.batch_with_fallback(
                        batch, session, batch_no, failed
                    )
                    failed_ids = {item["id"] for item in failed}

                    for item in batch:
                        if item["id"] not in failed_ids:
                            done.add(item["id"])

                    self.done_var.set(str(len(done)))
                    self.progress_set(
                        len(done) + len(failed_ids),
                        len(manifest),
                        "Pobieranie faktur",
                    )

                    if batch_no % 10 == 0:
                        self.log("[INFO] Krótka przerwa techniczna.")
                        self.sleep(0.8)

                if len(done) + len(failed_ids) >= len(manifest):
                    break

                if not self.has_next_page():
                    break
                if not self.go_next_page():
                    raise RuntimeError(
                        f"KSeF nie przeszedł ze strony {page} na następną "
                        "podczas pobierania."
                    )

            actual = self.save_fix_reports(session, manifest, failed)
            self.done_var.set(str(actual))
            self.session_log_path = None

            if actual < len(manifest) or failed:
                self.stop_pulse("Zakończono z brakami")
                self.result_var.set(
                    f"Pobrane PDF: {actual}/{len(manifest)} | "
                    f"do sprawdzenia: {len(failed)}"
                )
                messagebox.showwarning(
                    "Zakończono z brakami",
                    f"Pobrane PDF: {actual}/{len(manifest)}\n"
                    f"Do sprawdzenia: {len(failed)}\n\nFolder: {session}",
                )
            else:
                self.stop_pulse("Gotowe")
                self.result_var.set(f"Pobrane: {actual}/{len(manifest)}")
                messagebox.showinfo(
                    "Gotowe",
                    f"Pobrano {actual} faktur.\n\nFolder: {session}",
                )

        except Exception as exc:
            self.session_log_path = None
            self.stop_pulse("Błąd")
            path = os.path.join(self.base_dir, "crash_log.txt")

            try:
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
                    handle.write(str(exc) + "\n" + traceback.format_exc() + "\n")
            except Exception:
                pass

            if session:
                try:
                    self.debug_snapshot(session, "fatal_error")
                except Exception:
                    pass

            self.log("[BŁĄD] " + str(exc))
            messagebox.showerror("Błąd", f"{exc}\n\nLog: {path}")

        finally:
            self._running = False

    def close(self):
        if self._running:
            messagebox.showinfo(
                "Pobieranie w toku",
                "Poczekaj na zakończenie pobierania przed zamknięciem programu.",
            )
            return
        super().close()


def main():
    root = tk.Tk()
    KsefFinal(root)
    root.mainloop()


if __name__ == "__main__":
    main()
