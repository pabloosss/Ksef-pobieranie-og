import os
import re
import sys
import time
import zipfile
import traceback
import tkinter as tk
from pathlib import Path
from datetime import datetime
from tkinter import ttk, messagebox

from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

APP_TITLE = "Program do pobierania FV KSeF - Emerlog"
KSEF_URL = "https://ap.ksef.mf.gov.pl/web/invoice-list"
MAX_SCAN_PAGES = 300
MAX_RETRY_PASSES = 2
BATCH_SIZES = (10, 5, 1)
DOWNLOAD_TIMEOUTS = {10: 90, 5: 60, 1: 30}
NO_DOWNLOAD_SIGNAL_TIMEOUTS = {10: 18, 5: 14, 1: 10}


def app_dir():
    path = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    try:
        os.makedirs(path, exist_ok=True)
        test = os.path.join(path, ".write_test.tmp")
        with open(test, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test)
        return path
    except Exception:
        path = os.path.join(str(Path.home()), "Documents", "Ksef-Pobieranie")
        os.makedirs(path, exist_ok=True)
        return path


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()


def row_key(text):
    text = norm(text)
    for pattern in (r"(\d{10,}-\d{8}-[A-Z0-9]+-\d+)", r"([A-Z0-9/\-]{6,}/\d{4})"):
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).lower()
    return text.lower()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1200x840")
        self.root.configure(bg="white")
        self.driver = None
        self.logo_img = None
        self.base_dir = app_dir()
        self.download_dir = os.path.join(self.base_dir, "pobrane_fv")
        os.makedirs(self.download_dir, exist_ok=True)
        self.found_var = tk.StringVar(value="0")
        self.done_var = tk.StringVar(value="0")
        self.step_var = tk.StringVar(value="Status: gotowe")
        self.result_var = tk.StringVar(value="")
        self.animating = False
        self.progress_value = 0
        self.progress_dir = 1
        self.build_ui()
        self.root.after(40, self.animate)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Red.TButton", font=("Segoe UI", 11, "bold"), padding=12)
        style.configure("Black.TButton", font=("Segoe UI", 10, "bold"), padding=11)

        main = tk.Frame(self.root, bg="white", padx=18, pady=18)
        main.pack(fill="both", expand=True)
        header = tk.Frame(main, bg="black", padx=24, pady=20)
        header.pack(fill="x", pady=(0, 14))
        self.load_logo(header)
        tk.Label(header, text=APP_TITLE, font=("Segoe UI", 24, "bold"), bg="black", fg="white").pack(anchor="w", pady=(12, 0))

        stats = tk.Frame(main, bg="white")
        stats.pack(fill="x", pady=(0, 12))
        self.stat(stats, "Znalezione FV", self.found_var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.stat(stats, "Pobrane FV", self.done_var).pack(side="left", fill="x", expand=True, padx=(8, 0))

        body = tk.Frame(main, bg="white")
        body.pack(fill="both", expand=True)
        left = tk.Frame(body, bg="white", bd=1, relief="solid", padx=18, pady=18, width=430)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)
        right = tk.Frame(body, bg="white", bd=1, relief="solid", padx=18, pady=18)
        right.pack(side="left", fill="both", expand=True)

        ttk.Button(left, text="Start / Otwórz KSeF", style="Red.TButton", command=self.start_browser).pack(fill="x", pady=(0, 10))
        ttk.Button(left, text="Otwórz folder", style="Black.TButton", command=self.open_folder).pack(fill="x", pady=(0, 16))
        ttk.Button(left, text="Pobierz FV", style="Red.TButton", command=self.download_all).pack(fill="x")
        tk.Label(left, text="Postęp", bg="white", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(24, 8))
        self.progress = ttk.Progressbar(left, maximum=100)
        self.progress.pack(fill="x")
        tk.Label(left, textvariable=self.step_var, bg="#fafafa", wraplength=360, justify="left").pack(fill="x", pady=(12, 0))
        tk.Label(left, textvariable=self.result_var, bg="white", fg="#d10f14", wraplength=370, justify="left").pack(anchor="w", pady=(12, 0))

        tk.Label(right, text="Log operacji", bg="white", font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(0, 12))
        self.box = tk.Text(right, bg="black", fg="white", font=("Consolas", 10), padx=14, pady=14, wrap="word")
        self.box.pack(fill="both", expand=True)
        self.log(f"[INFO] Folder programu: {self.base_dir}")
        self.log(f"[INFO] Folder pobierania: {self.download_dir}")

    def load_logo(self, parent):
        folders = [os.path.join(self.base_dir, "grafiki"), os.path.join(self.base_dir, "grafika"), self.base_dir]
        names = ["logo.png", "emerloglogo.png", "emerlog_logo.png", "Logo.png", "LOGO.png"]
        candidates = []
        for folder in folders:
            for name in names:
                candidates.append(os.path.join(folder, name))
            try:
                for name in os.listdir(folder):
                    if name.lower().endswith((".png", ".gif")):
                        candidates.append(os.path.join(folder, name))
            except Exception:
                pass
        for path in candidates:
            if not os.path.exists(path):
                continue
            try:
                self.logo_img = tk.PhotoImage(file=path)
                if self.logo_img.width() > 560:
                    factor = max(1, self.logo_img.width() // 560)
                    self.logo_img = self.logo_img.subsample(factor, factor)
                tk.Label(parent, image=self.logo_img, bg="black").pack(anchor="w")
                return
            except Exception:
                pass
        tk.Label(parent, text="EMERLOG", font=("Segoe UI", 28, "bold italic"), bg="black", fg="white").pack(anchor="w")

    def stat(self, parent, title, var):
        frame = tk.Frame(parent, bg="white", bd=1, relief="solid", padx=14, pady=12)
        tk.Label(frame, text=title, bg="white", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        tk.Label(frame, textvariable=var, bg="white", fg="#d10f14", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        return frame

    def log(self, text):
        self.box.insert("end", text + "\n")
        self.box.see("end")
        self.root.update_idletasks()

    def step(self, text):
        self.step_var.set("Status: " + text)
        self.root.update_idletasks()

    def pulse(self, text):
        self.animating = True
        self.step(text)

    def stop(self, text):
        self.animating = False
        self.progress["value"] = 0
        self.step(text)

    def update_progress(self, current, total, text):
        total = max(1, total)
        self.animating = False
        self.progress.configure(maximum=total)
        self.progress["value"] = min(current, total)
        self.step_var.set(f"Status: {text} ({current}/{total}, {int(current / total * 100)}%)")
        self.root.update_idletasks()

    def animate(self):
        if self.animating:
            self.progress_value += 4 * self.progress_dir
            if self.progress_value >= 100:
                self.progress_value, self.progress_dir = 100, -1
            if self.progress_value <= 0:
                self.progress_value, self.progress_dir = 0, 1
            self.progress["value"] = self.progress_value
        self.root.after(40, self.animate)

    def create_driver(self):
        options = EdgeOptions()
        options.use_chromium = True
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_experimental_option("prefs", {"download.default_directory": self.download_dir, "download.prompt_for_download": False, "download.directory_upgrade": True, "plugins.always_open_pdf_externally": True})
        driver = webdriver.Edge(options=options)
        driver.implicitly_wait(1)
        driver.set_page_load_timeout(90)
        return driver

    def start_browser(self):
        try:
            if self.driver:
                messagebox.showinfo("Info", "Przeglądarka jest już otwarta.")
                return
            self.pulse("Uruchamianie Edge")
            self.driver = self.create_driver()
            self.driver.get(KSEF_URL)
            try:
                self.driver.maximize_window()
            except Exception:
                pass
            self.stop("Czekam na logowanie")
            self.log("[OK] KSeF otwarty. Zaloguj się i ustaw filtry.")
        except WebDriverException as exc:
            self.stop("Błąd Edge")
            self.log("[BŁĄD] " + str(exc))
            messagebox.showerror("Błąd Edge", str(exc))

    def open_folder(self):
        os.makedirs(self.download_dir, exist_ok=True)
        try:
            os.startfile(self.download_dir)
        except Exception:
            messagebox.showinfo("Folder", self.download_dir)

    def close_popups(self):
        try:
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.2)
        except Exception:
            pass

    def rows(self):
        rows = []
        for selector in ("tbody tr", "table tbody tr", "[role='row']"):
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if rows:
                    break
            except Exception:
                pass
        result = []
        for row in rows:
            try:
                text = norm(row.text)
                checks = row.find_elements(By.CSS_SELECTOR, "input[type='checkbox'], [role='checkbox']")
                if text and checks:
                    result.append({"text": text, "id": row_key(text), "check": checks[0]})
            except Exception:
                pass
        return result

    def signature(self):
        rows = self.rows()
        if not rows:
            return "EMPTY"
        return "|".join(x["id"] for x in rows)

    def click_any(self, candidates, timeout=3, delay=0.8):
        for by, value in candidates:
            try:
                elements = WebDriverWait(self.driver, timeout).until(EC.presence_of_all_elements_located((by, value)))
                for el in elements:
                    try:
                        if not el.is_displayed():
                            continue
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        try:
                            el.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(delay)
                        return True
                    except Exception:
                        pass
            except Exception:
                pass
        return False

    def next_page(self):
        before = self.signature()
        candidates = [(By.CSS_SELECTOR, "button[aria-label*='Następna']"), (By.CSS_SELECTOR, "button[title*='Następna']"), (By.CSS_SELECTOR, "[role='button'][aria-label*='Następna']"), (By.XPATH, "//*[self::button or @role='button'][contains(., 'Następna') or contains(., 'Next')]")]
        if not self.click_any(candidates, 2, 0.8):
            return False
        for _ in range(10):
            time.sleep(0.35)
            after = self.signature()
            if after != before and after != "EMPTY":
                self.log("[OK] Następna strona")
                return True
        return False

    def first_page(self):
        candidates = [(By.CSS_SELECTOR, "button[aria-label*='Poprzednia']"), (By.CSS_SELECTOR, "button[title*='Poprzednia']"), (By.CSS_SELECTOR, "[role='button'][aria-label*='Poprzednia']"), (By.XPATH, "//*[self::button or @role='button'][contains(., 'Poprzednia') or contains(., 'Previous')]")]
        for _ in range(50):
            before = self.signature()
            if not self.click_any(candidates, 1, 0.3):
                break
            time.sleep(0.2)
            if self.signature() == before:
                break

    def scan_manifest(self):
        result, ids, seen = [], set(), set()
        self.first_page()
        time.sleep(0.5)
        page = 0
        while page < MAX_SCAN_PAGES:
            rows = self.rows()
            sig = self.signature()
            if not rows or sig == "EMPTY" or sig in seen:
                break
            seen.add(sig)
            page += 1
            for row in rows:
                if row["id"] not in ids:
                    ids.add(row["id"])
                    result.append({"row_id": row["id"], "text": row["text"]})
            self.found_var.set(str(len(ids)))
            self.update_progress(page, page + 1, "Skanowanie listy FV")
            self.log(f"[INFO] Skan strony {page}: {len(rows)} wierszy, unikalnych FV: {len(ids)}")
            if not self.next_page():
                break
        self.first_page()
        time.sleep(0.5)
        return result

    def selected(self, checkbox):
        try:
            return checkbox.is_selected() or checkbox.get_attribute("aria-checked") == "true" or checkbox.get_attribute("checked") is not None
        except Exception:
            return False

    def clear_checks(self):
        for row in self.rows():
            try:
                if self.selected(row["check"]):
                    row["check"].click()
                    time.sleep(0.04)
            except Exception:
                pass

    def select_rows(self, rows):
        self.clear_checks()
        time.sleep(0.1)
        selected = []
        for row in rows:
            check = row["check"]
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", check)
            except Exception:
                pass
            ok = False
            for method in (lambda: check.click(), lambda: ActionChains(self.driver).move_to_element(check).click().perform(), lambda: self.driver.execute_script("arguments[0].click();", check)):
                try:
                    method()
                    time.sleep(0.12)
                    if self.selected(check):
                        ok = True
                        break
                except Exception:
                    pass
            if ok:
                selected.append(row)
                self.log(f"[INFO] Zaznaczono: {row['text'][:120]}")
        fresh = {x["id"]: x for x in self.rows()}
        return [fresh[x["id"]] for x in selected if x["id"] in fresh and self.selected(fresh[x["id"]]["check"])]

    def set_download_dir(self, path):
        os.makedirs(path, exist_ok=True)
        for command in ("Page.setDownloadBehavior", "Browser.setDownloadBehavior"):
            try:
                self.driver.execute_cdp_cmd(command, {"behavior": "allow", "downloadPath": path})
            except Exception:
                pass

    def snapshot(self, folders):
        return {folder: set(os.listdir(folder)) if os.path.isdir(folder) else set() for folder in folders}

    def unique_path(self, folder, name):
        base, ext = os.path.splitext(name)
        path = os.path.join(folder, name)
        counter = 1
        while os.path.exists(path):
            path = os.path.join(folder, f"{base}_{counter}{ext}")
            counter += 1
        return path

    def wait_file(self, session, before, timeout, signal_timeout):
        start = time.time()
        sizes, stable = {}, {}
        saw_download_signal = False
        while time.time() - start < timeout:
            for folder, old in before.items():
                try:
                    names = set(os.listdir(folder))
                except Exception:
                    continue
                if any(name.endswith((".crdownload", ".tmp", ".part")) for name in names):
                    saw_download_signal = True
                candidates = []
                for name in names:
                    if name.endswith((".crdownload", ".tmp", ".part")):
                        continue
                    path = os.path.join(folder, name)
                    if os.path.isfile(path) and (name not in old or os.path.getmtime(path) >= start - 1):
                        candidates.append(path)
                if candidates:
                    saw_download_signal = True
                if not candidates:
                    continue
                path = max(candidates, key=os.path.getmtime)
                size = os.path.getsize(path)
                if size <= 0:
                    continue
                stable[path] = stable.get(path, 0) + 1 if sizes.get(path) == size else 0
                sizes[path] = size
                if stable[path] >= 2:
                    if os.path.abspath(os.path.dirname(path)) != os.path.abspath(session):
                        target = self.unique_path(session, os.path.basename(path))
                        try:
                            os.replace(path, target)
                            return target
                        except Exception:
                            return path
                    return path
            if not saw_download_signal and time.time() - start >= signal_timeout:
                return None
            time.sleep(1)
        return None

    def try_download_format(self, session, button_candidates, timeout, signal_timeout, label):
        before = self.snapshot([session, self.download_dir])
        open_btn = [(By.XPATH, "//*[self::button or @role='button' or self::a][contains(., 'Pobierz') or contains(., 'Eksportuj')]")]
        if not self.click_any(open_btn, 3, 0.5):
            self.close_popups()
            return None
        if not self.click_any(button_candidates, 2, 0.5):
            self.close_popups()
            return None
        self.log(f"[INFO] Wybrano {label}")
        found = self.wait_file(session, before, timeout, signal_timeout)
        if found is None:
            self.close_popups()
        return found

    def download_selected(self, session, batch_size):
        self.set_download_dir(session)
        timeout = DOWNLOAD_TIMEOUTS.get(batch_size, 45)
        signal_timeout = NO_DOWNLOAD_SIGNAL_TIMEOUTS.get(batch_size, 10)
        zip_btn = [(By.XPATH, "//*[self::button or @role='button' or self::a or self::span][contains(translate(., 'zip', 'ZIP'), 'ZIP')]")]
        pdf_btn = [(By.XPATH, "//*[self::button or @role='button' or self::a or self::span][contains(translate(., 'pdf', 'PDF'), 'PDF')]")]

        found = self.try_download_format(session, zip_btn, timeout, signal_timeout, "ZIP")
        if found:
            return found

        if batch_size == 1:
            self.log("[INFO] ZIP nie ruszył dla pojedynczej FV. Próbuję PDF.")
            found = self.try_download_format(session, pdf_btn, 30, 10, "PDF")
            if found:
                return found

        return None

    def extract_zip(self, path, session):
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r") as archive:
                archive.extractall(session)
            try:
                os.remove(path)
            except Exception:
                pass
            return True
        return False

    def try_batch(self, rows, session, batch_no, size):
        selected = self.select_rows(rows[:size])
        if len(selected) != min(size, len(rows)):
            self.clear_checks()
            return None
        self.step(f"Pobieranie partii {batch_no}")
        self.log(f"[INFO] Pobieram partię {batch_no}. Rozmiar: {len(selected)} FV")
        path = self.download_selected(session, len(selected))
        if not path:
            self.log("[UWAGA] Pobieranie nie ruszyło. Przechodzę dalej i zapiszę tę FV w notatce.")
            self.clear_checks()
            return None
        self.log(f"[OK] Zapisano: {os.path.basename(path)}")
        if self.extract_zip(path, session):
            self.log("[OK] ZIP wypakowany.")
        self.clear_checks()
        return selected

    def process(self, target_ids, target_map, session, processed=None):
        processed = set(processed or set())
        failed = set()
        batch_no = 1
        seen = set()
        self.first_page()
        time.sleep(0.5)
        while len(seen) < MAX_SCAN_PAGES:
            rows = self.rows()
            sig = self.signature()
            if not rows or sig == "EMPTY" or sig in seen:
                break
            seen.add(sig)
            while True:
                rows = self.rows()
                remaining = [x for x in rows if x["id"] in target_ids and x["id"] not in processed and x["id"] not in failed]
                if not remaining:
                    break
                ok_rows = None
                for size in BATCH_SIZES:
                    size = min(size, len(remaining))
                    if size <= 0:
                        continue
                    ok_rows = self.try_batch(remaining, session, batch_no, size)
                    if ok_rows:
                        break
                if ok_rows:
                    for row in ok_rows:
                        processed.add(row["id"])
                    self.done_var.set(str(len(processed)))
                    self.update_progress(len(processed), max(1, len(target_ids)), "Pobieranie faktur")
                    self.log(f"[OK] Łącznie pobrano: {len(processed)}/{len(target_ids)}")
                    batch_no += 1
                    time.sleep(0.4)
                else:
                    failed.add(remaining[0]["id"])
                    self.log(f"[BŁĄD] Ta FV nie wystartowała. Zostawiam do retry i notatki: {remaining[0]['text'][:160]}")
            if len(processed) >= len(target_ids):
                break
            if not self.next_page():
                break
        missing = [target_map[x] for x in target_ids if x not in processed]
        return processed, missing

    def save_reports(self, session, manifest, processed, retries, missing):
        info_path = os.path.join(session, "info.txt")
        with open(info_path, "w", encoding="utf-8") as f:
            f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Znalezione FV: {len(manifest)}\nPobrane FV: {len(processed)}\nPróby naprawcze: {retries}\nBrakujące: {len(missing)}\n")

        audit = os.path.join(session, "raport_weryfikacji.txt")
        with open(audit, "w", encoding="utf-8") as f:
            f.write("STATUS | ID / NUMER | OPIS Z WIERSZA KSEF\n")
            f.write("=" * 90 + "\n")
            for item in manifest:
                f.write(("POBRANE" if item["row_id"] in processed else "BRAK") + f" | {item['row_id']} | {item['text']}\n")

        miss = None
        note = None
        if missing:
            miss = os.path.join(session, "brakujace_fv.txt")
            note = os.path.join(session, "NIEPOBRANE_DO_SPRAWDZENIA.txt")
            with open(miss, "w", encoding="utf-8") as f:
                for item in missing:
                    f.write(f"{item['row_id']} | {item['text']}\n")
            with open(note, "w", encoding="utf-8") as f:
                f.write("FV, których program nie mógł pobrać automatycznie\n")
                f.write("=" * 70 + "\n")
                f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Liczba brakujących FV: {len(missing)}\n\n")
                f.write("Co zrobić ręcznie:\n")
                f.write("1. Wejdź w KSeF na tej samej liście/filtrach.\n")
                f.write("2. Wyszukaj po numerze/id z listy poniżej.\n")
                f.write("3. Spróbuj pobrać ręcznie z podglądu faktury.\n")
                f.write("4. Jeżeli ręcznie też nie idzie, to problem jest po stronie tej pozycji/KSeF.\n\n")
                f.write("Lista braków:\n")
                for index, item in enumerate(missing, start=1):
                    f.write(f"{index}. {item['row_id']} | {item['text']}\n")
        return audit, miss, note

    def download_all(self):
        try:
            if not self.driver:
                messagebox.showwarning("Uwaga", "Najpierw kliknij Start.")
                return
            self.pulse("Skanowanie listy FV")
            manifest = self.scan_manifest()
            if not manifest:
                self.stop("Brak FV")
                messagebox.showwarning("Brak FV", "Nie znaleziono FV.")
                return
            ids = [x["row_id"] for x in manifest]
            target = {x["row_id"]: x for x in manifest}
            self.found_var.set(str(len(ids)))
            session = os.path.join(self.download_dir, datetime.now().strftime("%Y-%m-%d__%H-%M-%S__WSZYSTKIE_FV"))
            os.makedirs(session, exist_ok=True)
            self.log(f"[INFO] Folder sesji: {session}")
            processed, missing = self.process(set(ids), target, session)
            retries = 0
            while missing and retries < MAX_RETRY_PASSES:
                retries += 1
                self.log(f"[INFO] Próba naprawcza {retries}/{MAX_RETRY_PASSES}, braków: {len(missing)}")
                processed, missing = self.process(set(x["row_id"] for x in missing), target, session, processed)
            audit, miss, note = self.save_reports(session, manifest, processed, retries, missing)
            self.log(f"[INFO] Raport: {audit}")
            if note:
                self.log(f"[INFO] Notatka braków: {note}")
            if missing:
                self.stop("Zakończono z brakami")
                self.result_var.set(f"Pobrane: {len(processed)} z {len(ids)} FV | Brakuje: {len(missing)}")
                messagebox.showwarning("Niepełne pobranie", f"Pobrano {len(processed)} z {len(ids)} FV.\nBraki: {len(missing)}\n\nNotatka: {note}\nLista: {miss}")
            else:
                self.stop("Gotowe")
                self.result_var.set(f"Pobrane: {len(processed)} z {len(ids)} FV")
                messagebox.showinfo("Sukces", f"Pobieranie zakończone.\nZnalezione FV: {len(ids)}\nPobrane FV: {len(processed)}\nFolder: {session}")
        except Exception as exc:
            self.stop("Błąd")
            path = os.path.join(self.base_dir, "crash_log.txt")
            with open(path, "a", encoding="utf-8") as f:
                f.write(str(exc) + "\n" + traceback.format_exc() + "\n")
            self.log("[BŁĄD] " + str(exc))
            messagebox.showerror("Błąd", f"{exc}\n\nLog: {path}")

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
