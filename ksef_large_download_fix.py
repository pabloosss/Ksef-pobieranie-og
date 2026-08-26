import os
import re
import time
import zipfile
from datetime import datetime
from tkinter import messagebox

from selenium.webdriver.common.by import By

import ksef_app_selenium_edge_fix as base

MAX_BATCH = 10
DOWNLOAD_TIMEOUT = 120
DOWNLOAD_RETRIES = 3
RETRY_DELAYS = (3, 7, 15)
BATCH_PAUSE = 1.5
KSEF_RE = re.compile(r"\b\d{10}-\d{8}-[A-Z0-9]+-[A-Z0-9]+\b", re.I)
TEMP_EXTS = (".crdownload", ".tmp", ".part")


def better_invoice_key(text):
    text = base.clean_text(text)
    match = KSEF_RE.search(text)
    if match:
        return match.group(0).lower()
    match = re.search(r"([A-Z0-9][A-Z0-9/._-]{3,}/\d{4})", text, re.I)
    if match:
        return match.group(1).lower()
    return text.lower()


base.invoice_key = better_invoice_key


class ReliableKsefDownloader(base.SimpleKsefDownloader):
    def __init__(self, root):
        self.session_log_path = None
        super().__init__(root)
        self.log("[FIX] Tryb niezawodny: max 10 FV/paczkę, PDF -> ZIP, retry 10→5→1.")

    def log(self, text):
        super().log(text)
        if self.session_log_path:
            try:
                with open(self.session_log_path, "a", encoding="utf-8") as handle:
                    handle.write(datetime.now().strftime("%H:%M:%S") + " " + text + "\n")
            except Exception:
                pass

    def sleep(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            try:
                self.root.update_idletasks()
            except Exception:
                pass
            time.sleep(min(0.2, max(0.01, end - time.time())))

    def page_signature(self):
        rows = self.row_items()
        if not rows:
            return "EMPTY"
        ids = [item["id"] for item in rows]
        return f"{len(ids)}|" + "|".join(ids[:3] + ids[-3:])

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
        for attempt in range(1, 4):
            if not self.click_any(candidates, 2, 0.4):
                return False
            end = time.time() + 15
            while time.time() < end:
                after = self.page_signature()
                if after != before and after != "EMPTY":
                    return True
                self.sleep(0.35)
            self.log(f"[UWAGA] Następna strona nie zmieniła tabeli ({attempt}/3).")
        return False

    def clear_selection(self):
        changed = 0
        for item in self.row_items():
            try:
                if self.is_selected(item["check"]):
                    if self.click_element(item["check"], 0.08):
                        changed += 1
            except Exception:
                pass
        if changed:
            self.sleep(0.2)

    def select_ids(self, ids):
        wanted = list(ids)
        wanted_set = set(wanted)
        self.clear_selection()
        selected = []
        for item in self.row_items():
            if item["id"] not in wanted_set:
                continue
            try:
                if not self.is_selected(item["check"]):
                    self.click_element(item["check"], 0.08)
                if self.is_selected(item["check"]):
                    selected.append(item["id"])
            except Exception:
                pass
        actual = {item["id"] for item in self.row_items() if self.is_selected(item["check"])}
        return [item_id for item_id in wanted if item_id in actual]

    def wait_new_download(self, folder, before):
        start = time.time()
        sizes = {}
        stable = {}
        while time.time() - start < DOWNLOAD_TIMEOUT:
            try:
                names = set(os.listdir(folder))
            except Exception:
                names = set()
            temps = [name for name in names if name.lower().endswith(TEMP_EXTS)]
            candidates = []
            for name in names - before:
                if name.lower().endswith(TEMP_EXTS):
                    continue
                path = os.path.join(folder, name)
                if os.path.isfile(path):
                    candidates.append(path)
            if candidates:
                path = max(candidates, key=os.path.getmtime)
                try:
                    size = os.path.getsize(path)
                except Exception:
                    size = 0
                if size > 0:
                    stable[path] = stable.get(path, 0) + 1 if sizes.get(path) == size and not temps else 0
                    sizes[path] = size
                    if stable[path] >= 2:
                        return path
            elapsed = int(time.time() - start)
            if elapsed in (20, 45, 75):
                self.log(f"[INFO] KSeF nadal generuje plik... {elapsed}s")
            self.sleep(0.6)
        return None

    def download_pdf(self, session):
        self.set_download_dir(session)
        before = set(os.listdir(session))
        self.close_popups()
        open_btn = [
            (By.XPATH, "//button[contains(normalize-space(.),'Pobierz')]"),
            (By.XPATH, "//*[@role='button' and contains(normalize-space(.),'Pobierz')]"),
            (By.XPATH, "//button[contains(normalize-space(.),'Eksportuj')]"),
        ]
        if not self.click_any(open_btn, 4, 0.5):
            return None
        pdf_btn = [
            (By.XPATH, "//*[(@role='menuitem' or self::button or self::a or self::li) and normalize-space(.)='PDF']"),
            (By.XPATH, "//*[(@role='menuitem' or self::button or self::a or self::li) and contains(normalize-space(.),'PDF')]"),
            (By.XPATH, "//*[normalize-space(.)='PDF']"),
        ]
        if not self.click_any(pdf_btn, 4, 0.4):
            self.close_popups()
            return None
        path = self.wait_new_download(session, before)
        self.close_popups()
        return path

    def unpack(self, path, session):
        if not path or not os.path.exists(path):
            return 0
        if zipfile.is_zipfile(path):
            try:
                with zipfile.ZipFile(path) as archive:
                    members = [n for n in archive.namelist() if n.lower().endswith(".pdf")]
                    archive.extractall(session)
                os.remove(path)
                return len(members)
            except Exception as exc:
                self.log(f"[BŁĄD] ZIP: {exc}")
                return 0
        return 1 if path.lower().endswith(".pdf") else 0

    def debug_snapshot(self, session, label):
        folder = os.path.join(session, "debug")
        os.makedirs(folder, exist_ok=True)
        stamp = datetime.now().strftime("%H%M%S")
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", label)
        try:
            self.driver.save_screenshot(os.path.join(folder, f"{stamp}_{safe}.png"))
        except Exception:
            pass
        try:
            with open(os.path.join(folder, f"{stamp}_{safe}.html"), "w", encoding="utf-8") as handle:
                handle.write(self.driver.page_source)
        except Exception:
            pass

    def one_batch(self, items, session, batch_no):
        ids = [item["id"] for item in items]
        for attempt in range(1, DOWNLOAD_RETRIES + 1):
            self.set_step(f"Partia {batch_no}: {len(items)} FV, próba {attempt}/{DOWNLOAD_RETRIES}")
            selected = self.select_ids(ids)
            if len(selected) != len(ids):
                self.log(f"[UWAGA] Partia {batch_no}: zaznaczono {len(selected)}/{len(ids)}.")
                self.clear_selection()
            else:
                self.log(f"[INFO] Partia {batch_no}: pobieram {len(items)} FV jako PDF.")
                path = self.download_pdf(session)
                if path:
                    pdfs = self.unpack(path, session)
                    self.log(f"[OK] Partia {batch_no}: paczka zapisana, PDF po rozpakowaniu: {pdfs}.")
                    self.clear_selection()
                    self.sleep(BATCH_PAUSE)
                    return True
                self.log(f"[UWAGA] Partia {batch_no}: brak pliku po {DOWNLOAD_TIMEOUT}s.")
                self.debug_snapshot(session, f"batch_{batch_no}_attempt_{attempt}")
                self.clear_selection()
            if attempt < DOWNLOAD_RETRIES:
                delay = RETRY_DELAYS[attempt - 1]
                self.log(f"[INFO] Retry za {delay}s.")
                self.sleep(delay)
        return False

    def batch_with_fallback(self, items, session, batch_no, failed):
        if self.one_batch(items, session, batch_no):
            return len(items), batch_no + 1
        if len(items) > 1:
            mid = len(items) // 2
            self.log(f"[UWAGA] Dzielę nieudaną paczkę {len(items)} FV na {mid}+{len(items)-mid}.")
            ok1, next_no = self.batch_with_fallback(items[:mid], session, batch_no + 1, failed)
            ok2, next_no = self.batch_with_fallback(items[mid:], session, next_no, failed)
            return ok1 + ok2, next_no
        failed.append(items[0])
        self.log(f"[BŁĄD] Nie pobrano pojedynczej FV: {items[0]['id']}")
        return 0, batch_no + 1

    def scan_manifest(self):
        self.go_first_page()
        self.sleep(0.5)
        manifest = []
        seen_pages = set()
        seen_ids = set()
        page = 0
        while page < base.MAX_PAGES:
            rows = self.row_items()
            sig = self.page_signature()
            if not rows or sig == "EMPTY" or sig in seen_pages:
                break
            seen_pages.add(sig)
            page += 1
            for item in rows:
                if item["id"] in seen_ids:
                    continue
                seen_ids.add(item["id"])
                manifest.append({"id": item["id"], "text": item["text"], "page": page})
            self.log(f"[INFO] Skan: strona {page}, razem {len(manifest)} FV.")
            if not self.go_next_page():
                break
        self.go_first_page()
        self.sleep(0.5)
        return manifest

    def count_unique_pdfs(self, session):
        keys = set()
        unmatched = set()
        for root, _, files in os.walk(session):
            if os.path.basename(root).lower() == "debug":
                continue
            for name in files:
                if not name.lower().endswith(".pdf"):
                    continue
                match = KSEF_RE.search(name)
                if match:
                    keys.add(match.group(0).lower())
                else:
                    unmatched.add(os.path.join(root, name))
        return len(keys) + len(unmatched)

    def save_fix_reports(self, session, manifest, failed):
        count = self.count_unique_pdfs(session)
        with open(os.path.join(session, "info.txt"), "w", encoding="utf-8") as handle:
            handle.write(f"Data: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            handle.write(f"Znalezione FV: {len(manifest)}\n")
            handle.write(f"Unikalne PDF w folderze: {count}\n")
            handle.write(f"Nieudane po retry: {len(failed)}\n")
        failed_ids = {item["id"] for item in failed}
        with open(os.path.join(session, "raport_weryfikacji.txt"), "w", encoding="utf-8") as handle:
            for item in manifest:
                status = "BRAK/SPRAWDŹ" if item["id"] in failed_ids else "POBRANO/PACZKA_OK"
                handle.write(f"{status} | strona {item['page']} | {item['id']} | {item['text']}\n")
        if failed:
            with open(os.path.join(session, "NIEPOBRANE_DO_SPRAWDZENIA.txt"), "w", encoding="utf-8") as handle:
                for item in failed:
                    handle.write(f"strona {item['page']} | {item['id']} | {item['text']}\n")
        return count

    def download_all(self):
        try:
            if not self.driver:
                messagebox.showwarning("Uwaga", "Najpierw kliknij Start.")
                return

            self.start_pulse("Skanowanie listy FV")
            manifest = self.scan_manifest()
            if not manifest:
                self.stop_pulse("Brak FV")
                messagebox.showwarning("Brak FV", "Nie znalazłem faktur na aktualnej liście.")
                return

            self.found_var.set(str(len(manifest)))
            session = os.path.join(self.download_dir, datetime.now().strftime("%Y-%m-%d__%H-%M-%S__WSZYSTKIE_FV"))
            os.makedirs(session, exist_ok=True)
            self.session_log_path = os.path.join(session, "run_log.txt")
            self.log(f"[INFO] Folder sesji: {session}")
            self.log(f"[INFO] Start: {len(manifest)} FV, paczki max {MAX_BATCH}.")

            targets = {item["id"]: item for item in manifest}
            done = set()
            failed = []
            seen_pages = set()
            batch_no = 1
            page = 0
            self.go_first_page()
            self.sleep(0.5)

            while len(done) + len(failed) < len(manifest) and page < base.MAX_PAGES:
                rows = self.row_items()
                sig = self.page_signature()
                if not rows or sig == "EMPTY" or sig in seen_pages:
                    break
                seen_pages.add(sig)
                page += 1
                page_items = [targets[r["id"]] for r in rows if r["id"] in targets and r["id"] not in done and all(f["id"] != r["id"] for f in failed)]
                self.log(f"[INFO] Strona {page}: {len(page_items)} FV do pobrania.")

                for start in range(0, len(page_items), MAX_BATCH):
                    batch = page_items[start:start + MAX_BATCH]
                    _, batch_no = self.batch_with_fallback(batch, session, batch_no, failed)
                    failed_ids = {f["id"] for f in failed}
                    for item in batch:
                        if item["id"] not in failed_ids:
                            done.add(item["id"])
                    self.done_var.set(str(len(done)))
                    self.progress_set(len(done) + len(failed), len(manifest), "Pobieranie FV")
                    if batch_no % 10 == 0:
                        self.log("[INFO] Przerwa 4s po serii paczek.")
                        self.sleep(4)

                if len(done) + len(failed) >= len(manifest):
                    break
                if not self.go_next_page():
                    break

            actual = self.save_fix_reports(session, manifest, failed)
            self.done_var.set(str(actual))
            self.session_log_path = None
            if actual < len(manifest) or failed:
                self.stop_pulse("Zakończono z brakami")
                self.result_var.set(f"PDF: {actual}/{len(manifest)} | nieudane: {len(failed)}")
                messagebox.showwarning("Niepełne pobranie", f"PDF: {actual}/{len(manifest)}\nNieudane po retry: {len(failed)}\n\nFolder: {session}\n\nPodeślij run_log.txt i folder debug, jeśli problem się powtórzy.")
            else:
                self.stop_pulse("Gotowe")
                self.result_var.set(f"Pobrane: {actual}/{len(manifest)}")
                messagebox.showinfo("Sukces", f"Pobrano {actual} FV.\n\nFolder: {session}")
        except Exception as exc:
            self.session_log_path = None
            self.stop_pulse("Błąd")
            path = os.path.join(self.base_dir, "crash_log.txt")
            with open(path, "a", encoding="utf-8") as handle:
                import traceback
                handle.write(str(exc) + "\n" + traceback.format_exc() + "\n")
            self.log("[BŁĄD] " + str(exc))
            messagebox.showerror("Błąd", f"{exc}\n\nLog: {path}")


def main():
    import tkinter as tk
    root = tk.Tk()
    ReliableKsefDownloader(root)
    root.mainloop()


if __name__ == "__main__":
    main()
