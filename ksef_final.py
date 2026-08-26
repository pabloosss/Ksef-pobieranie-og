import base64
import os
import re
import time
import zipfile
import traceback
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from selenium.webdriver.common.by import By

import ksef_app_selenium_edge_fix as base

# Finalna wersja programu. Stary plik ksef_app_selenium_edge_fix.py zostaje jako rdzeń
# obsługi Edge/UI. Cała logika pobierania jest tutaj.
MAX_BATCH = 10
DOWNLOAD_TIMEOUT = 180
DOWNLOAD_RETRIES = 2
RETRY_DELAYS = (2, 5)
BATCH_PAUSE = 0.15
NO_DOWNLOAD_SIGNAL_TIMEOUT = 60
PAGE_CHANGE_TIMEOUT = 6
PAGE_RETRIES = 2
TABLE_WAIT_TIMEOUT = 12
TEMP_EXTS = (".crdownload", ".tmp", ".part")
KSEF_RE = re.compile(r"\b\d{10}-\d{8}-[A-Z0-9]+-[A-Z0-9]+\b", re.I)

EMERLOG_LOGO_B64 = (
    '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'
    'iUIxgP8Dav0WtYlEoCIAAAAASUVORK5CYII='
)


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


class KsefDownloader(base.SimpleKsefDownloader):
    def __init__(self, root):
        self.session_log_path = None
        self._running = False
        super().__init__(root)
        self.root.title("KSeF - pobieranie faktur | EMERLOG")
        self.log("[INFO] Program gotowy.")

    # ---------- wygląd / komunikaty ----------
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
            "[INFO] Tryb prosty: każda strona -> zaznacz wszystko -> pobierz ZIP -> następna strona.": "[INFO] Pobieranie w paczkach po maks. 10 faktur.",
            "Retry za": "Ponawiam za",
            "KSeF nadal generuje plik": "KSeF przygotowuje plik",
            "Nie pobrano pojedynczej FV": "Nie udało się pobrać faktury",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        super().log(text)
        if self.session_log_path:
            try:
                with open(self.session_log_path, "a", encoding="utf-8") as handle:
                    handle.write(datetime.now().strftime("%H:%M:%S") + " " + text + "\n")
            except Exception:
                pass

    def set_step(self, text):
        text = text.replace("Partia", "Paczka").replace("próba", "podejście")
        text = text.replace("Pobieranie FV", "Pobieranie faktur")
        text = text.replace("Skanowanie listy FV", "Skanowanie listy faktur")
        super().set_step(text)

    def sleep(self, seconds):
        # root.update() utrzymuje responsywne okno podczas pracy Selenium.
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

    # ---------- uruchamianie Edge ----------
    def create_driver(self):
        options = base.EdgeOptions()
        options.use_chromium = True
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-background-timer-throttling")
        options.add_experimental_option("prefs", {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
        })

        candidates = [
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        ]
        for path in candidates:
            if path and os.path.isfile(path):
                options.binary_location = path
                break

        driver = base.webdriver.Edge(options=options)
        driver.implicitly_wait(0.3)
        driver.set_page_load_timeout(90)
        return driver

    def _driver_alive(self):
        if not self.driver:
            return False
        try:
            _ = self.driver.current_url
            return True
        except Exception:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            return False

    def start_browser(self):
        if self._driver_alive():
            try:
                self.driver.switch_to.window(self.driver.current_window_handle)
                self.driver.maximize_window()
            except Exception:
                pass
            self.log("[INFO] KSeF jest już otwarty.")
            messagebox.showinfo("KSeF", "Przeglądarka jest już otwarta.")
            return

        self.start_pulse("Uruchamianie Edge")
        self.log("[INFO] Uruchamiam Edge...")
        last_error = None

        for attempt in range(1, 3):
            try:
                self.driver = self.create_driver()
                self.driver.get(base.KSEF_URL)
                try:
                    self.driver.maximize_window()
                except Exception:
                    pass

                self.stop_pulse("Czekam na logowanie")
                self.log("[OK] KSeF otwarty. Zaloguj się i ustaw filtry.")
                return
            except Exception as exc:
                last_error = exc
                self.log(f"[UWAGA] Edge nie wystartował (podejście {attempt}/2).")
                try:
                    if self.driver:
                        self.driver.quit()
                except Exception:
                    pass
                self.driver = None
                if attempt < 2:
                    self.sleep(1.0)

        self.stop_pulse("Nie udało się uruchomić Edge")
        error_text = str(last_error) if last_error else "Nieznany błąd uruchamiania Edge"
        self.log("[BŁĄD] " + error_text)
        try:
            path = os.path.join(self.base_dir, "edge_start_error.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(error_text + "\n")
        except Exception:
            path = None
        msg = "Nie udało się uruchomić Microsoft Edge.\n\n" + error_text
        if path:
            msg += "\n\nLog: " + path
        messagebox.showerror("Błąd Edge", msg)

    # ---------- szybkie klikanie / strony ----------
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

    def page_signature(self):
        rows = self.row_items()
        if not rows:
            return "EMPTY"
        ids = [item["id"] for item in rows]
        return f"{len(ids)}|" + "|".join(ids[:3] + ids[-3:])

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
        if len(rows) <= MAX_BATCH and set(row_ids) == wanted_set:
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
        while time.time() - start < DOWNLOAD_TIMEOUT:
            try:
                names = set(os.listdir(folder))
            except Exception:
                names = set()
            temps = [name for name in names if name.lower().endswith(TEMP_EXTS)]
            if temps:
                saw_signal = True
            candidates = []
            for name in names - before:
                if name.lower().endswith(TEMP_EXTS):
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

    def download_pdf(self, session):
        self.set_download_dir(session)
        before = set(os.listdir(session))
        self.close_popups()
        open_btn = [
            (By.XPATH, "//button[contains(normalize-space(.),'Pobierz')]"),
            (By.XPATH, "//*[@role='button' and contains(normalize-space(.),'Pobierz')]"),
            (By.XPATH, "//button[contains(normalize-space(.),'Eksportuj')]"),
        ]
        if not self.click_any(open_btn, 3, 0.08):
            return None
        pdf_btn = [
            (By.XPATH, "//*[(@role='menuitem' or self::button or self::a or self::li) and normalize-space(.)='PDF']"),
            (By.XPATH, "//*[(@role='menuitem' or self::button or self::a or self::li) and contains(normalize-space(.),'PDF')]"),
            (By.XPATH, "//*[normalize-space(.)='PDF']"),
        ]
        if not self.click_any(pdf_btn, 3, 0.08):
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

    def scan_manifest(self):
        self.go_first_page()
        self.sleep(0.3)
        manifest = []
        seen_pages = set()
        seen_ids = set()
        page = 0
        while page < base.MAX_PAGES:
            rows = self.row_items()
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
                    f"KSeF nie przeszedł ze strony {page} na następną. Przerwałem, żeby niczego nie pominąć."
                )
        self.go_first_page()
        self.sleep(0.3)
        return manifest

    def one_batch(self, items, session, batch_no):
        ids = [item["id"] for item in items]
        expected = len(items)
        for attempt in range(1, DOWNLOAD_RETRIES + 1):
            self.set_step(f"Paczka {batch_no}: {expected} faktur, podejście {attempt}/{DOWNLOAD_RETRIES}")
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
                        self.sleep(BATCH_PAUSE)
                        return True
                    self.log(f"[UWAGA] Paczka {batch_no}: pobrano {pdfs}/{expected} PDF. Ponawiam.")
                    self.debug_snapshot(session, f"batch_{batch_no}_count_{pdfs}_expected_{expected}")
                else:
                    self.log(f"[UWAGA] Paczka {batch_no}: nie dostałem pliku.")
                    self.debug_snapshot(session, f"batch_{batch_no}_attempt_{attempt}")
                self.clear_selection()
            if attempt < DOWNLOAD_RETRIES:
                delay = RETRY_DELAYS[attempt - 1]
                self.log(f"[INFO] Ponawiam za {delay} s.")
                self.sleep(delay)
        return False

    def batch_with_fallback(self, items, session, batch_no, failed):
        if self.one_batch(items, session, batch_no):
            return len(items), batch_no + 1
        if len(items) > 1:
            mid = len(items) // 2
            self.log(f"[UWAGA] Dzielę paczkę {len(items)} faktur na {mid}+{len(items)-mid}.")
            ok1, next_no = self.batch_with_fallback(items[:mid], session, batch_no + 1, failed)
            ok2, next_no = self.batch_with_fallback(items[mid:], session, next_no, failed)
            return ok1 + ok2, next_no
        failed.append(items[0])
        self.log(f"[BŁĄD] Nie udało się pobrać faktury: {items[0]['id']}")
        return 0, batch_no + 1

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

    def save_reports(self, session, manifest, failed):
        count = self.count_unique_pdfs(session)
        with open(os.path.join(session, "info.txt"), "w", encoding="utf-8") as handle:
            handle.write(f"Data: {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            handle.write(f"Znalezione FV: {len(manifest)}\n")
            handle.write(f"Unikalne PDF w folderze: {count}\n")
            handle.write(f"Nieudane po ponowieniach: {len(failed)}\n")
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
            while len(done) + len(failed_ids) < len(manifest) and page < base.MAX_PAGES:
                rows = self.row_items()
                sig = self.page_signature()
                if not rows or sig == "EMPTY":
                    raise RuntimeError("Lista faktur zniknęła podczas pobierania.")
                if sig in seen_pages:
                    if self.has_next_page():
                        raise RuntimeError("KSeF utknął na tej samej stronie. Przerwałem, żeby niczego nie pominąć.")
                    break
                seen_pages.add(sig)
                page += 1
                page_items = [
                    targets[r["id"]]
                    for r in rows
                    if r["id"] in targets
                    and r["id"] not in done
                    and r["id"] not in failed_ids
                ]
                self.log(f"[INFO] Strona {page}: {len(page_items)} faktur do pobrania.")
                for start in range(0, len(page_items), MAX_BATCH):
                    batch = page_items[start:start + MAX_BATCH]
                    _, batch_no = self.batch_with_fallback(batch, session, batch_no, failed)
                    failed_ids = {f["id"] for f in failed}
                    for item in batch:
                        if item["id"] not in failed_ids:
                            done.add(item["id"])
                    self.done_var.set(str(len(done)))
                    self.progress_set(len(done) + len(failed_ids), len(manifest), "Pobieranie faktur")
                    if batch_no % 10 == 0:
                        self.log("[INFO] Krótka przerwa techniczna.")
                        self.sleep(0.8)
                if len(done) + len(failed_ids) >= len(manifest):
                    break
                if not self.has_next_page():
                    break
                if not self.go_next_page():
                    raise RuntimeError(f"KSeF nie przeszedł ze strony {page} na następną.")
            actual = self.save_reports(session, manifest, failed)
            self.done_var.set(str(actual))
            if actual < len(manifest) or failed:
                self.stop_pulse("Zakończono z brakami")
                self.result_var.set(f"PDF: {actual}/{len(manifest)} | do sprawdzenia: {len(failed)}")
                messagebox.showwarning(
                    "Niepełne pobranie",
                    f"Pobrano {actual}/{len(manifest)} faktur.\nDo sprawdzenia: {len(failed)}\n\nFolder: {session}",
                )
            else:
                self.stop_pulse("Gotowe")
                self.result_var.set(f"Pobrane: {actual}/{len(manifest)}")
                messagebox.showinfo("Gotowe", f"Pobrano {actual} faktur.\n\nFolder: {session}")
        except Exception as exc:
            self.stop_pulse("Błąd")
            self.log("[BŁĄD] " + str(exc))
            path = os.path.join(self.base_dir, "crash_log.txt")
            try:
                with open(path, "a", encoding="utf-8") as handle:
                    handle.write(str(exc) + "\n" + traceback.format_exc() + "\n")
            except Exception:
                pass
            if session:
                self.debug_snapshot(session, "fatal_error")
            messagebox.showerror("Błąd", f"{exc}\n\nLog: {path}")
        finally:
            self.session_log_path = None
            self._running = False

    def close(self):
        if self._running:
            messagebox.showinfo("Pobieranie w toku", "Poczekaj na zakończenie pobierania przed zamknięciem programu.")
            return
        super().close()


def main():
    root = tk.Tk()
    KsefDownloader(root)
    root.mainloop()


if __name__ == "__main__":
    main()
