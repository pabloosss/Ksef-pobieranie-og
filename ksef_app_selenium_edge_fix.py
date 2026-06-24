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
MAX_PAGES = 300
DOWNLOAD_TIMEOUTS = {10: 90, 5: 60, 1: 35}
NO_SIGNAL_TIMEOUTS = {10: 18, 5: 14, 1: 10}


def app_dir():
    path = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
    try:
        os.makedirs(path, exist_ok=True)
        test = os.path.join(path, ".write_test.tmp")
        with open(test, "w", encoding="utf-8") as handle:
            handle.write("ok")
        os.remove(test)
        return path
    except Exception:
        path = os.path.join(str(Path.home()), "Documents", "Ksef-Pobieranie")
        os.makedirs(path, exist_ok=True)
        return path


def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()


def invoice_key(text):
    text = clean_text(text)
    for pattern in (r"(\d{10,}-\d{8}-[A-Z0-9]+-\d+)", r"([A-Z0-9/\-]{6,}/\d{4})"):
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(1).lower()
    return text.lower()


class KsefDownloader:
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

    def set_step(self, text):
        self.step_var.set("Status: " + text)
        self.root.update_idletasks()

    def start_pulse(self, text):
        self.animating = True
        self.set_step(text)

    def stop_pulse(self, text):
        self.animating = False
        self.progress["value"] = 0
        self.set_step(text)

    def progress_set(self, current, total, text):
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
        options.add_experimental_option("prefs", {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
        })
        driver = webdriver.Edge(options=options)
        driver.implicitly_wait(1)
        driver.set_page_load_timeout(90)
        return driver

    def start_browser(self):
        try:
            if self.driver:
                messagebox.showinfo("Info", "Przeglądarka jest już otwarta.")
                return
            self.start_pulse("Uruchamianie Edge")
            self.driver = self.create_driver()
            self.driver.get(KSEF_URL)
            try:
                self.driver.maximize_window()
            except Exception:
                pass
            self.stop_pulse("Czekam na logowanie")
            self.log("[OK] KSeF otwarty. Zaloguj się i ustaw filtry.")
        except WebDriverException as exc:
            self.stop_pulse("Błąd Edge")
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
        found = []
        for selector in ("tbody tr", "table tbody tr", "[role='row']"):
            try:
                found = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if found:
                    break
            except Exception:
                pass
        result = []
        for row in found:
            try:
                text = clean_text(row.text)
                checks = row.find_elements(By.CSS_SELECTOR, "input[type='checkbox'], [role='checkbox']")
                if text and checks:
                    result.append({"text": text, "id": invoice_key(text), "check": checks[0], "row": row})
            except Exception:
                pass
        return result

    def find_row(self, row_id):
        for item in self.rows():
            if item["id"] == row_id:
                return item
        return None

    def signature(self):
        rows = self.rows()
        return "EMPTY" if not rows else "|".join(item["id"] for item in rows)

    def click_any(self, candidates, timeout=3, delay=0.6):
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

    def go_next_page(self):
        before = self.signature()
        candidates = [
            (By.CSS_SELECTOR, "button[aria-label*='Następna']"),
            (By.CSS_SELECTOR, "button[title*='Następna']"),
            (By.CSS_SELECTOR, "[role='button'][aria-label*='Następna']"),
            (By.XPATH, "//*[self::button or @role='button'][contains(., 'Następna') or contains(., 'Next')]")
        ]
        if not self.click_any(candidates, 2, 0.8):
            return False
        for _ in range(10):
            time.sleep(0.35)
            after = self.signature()
            if after != before and after != "EMPTY":
                self.log("[OK] Następna strona")
                return True
        return False

    def go_first_page(self):
        candidates = [
            (By.CSS_SELECTOR, "button[aria-label*='Poprzednia']"),
            (By.CSS_SELECTOR, "button[title*='Poprzednia']"),
            (By.CSS_SELECTOR, "[role='button'][aria-label*='Poprzednia']"),
            (By.XPATH, "//*[self::button or @role='button'][contains(., 'Poprzednia') or contains(., 'Previous')]")
        ]
        for _ in range(50):
            before = self.signature()
            if not self.click_any(candidates, 1, 0.3):
                break
            time.sleep(0.2)
            if self.signature() == before:
                break

    def is_selected(self, checkbox):
        try:
            return checkbox.is_selected() or checkbox.get_attribute("aria-checked") == "true" or checkbox.get_attribute("checked") is not None
        except Exception:
            return False

    def clear_checks(self):
        for item in self.rows():
            try:
                if self.is_selected(item["check"]):
                    item["check"].click()
                    time.sleep(0.04)
            except Exception:
                pass

    def select_rows(self, rows):
        self.clear_checks()
        time.sleep(0.1)
        selected_ids = []
        for item in rows:
            fresh = self.find_row(item["id"])
            if not fresh:
                continue
            checkbox = fresh["check"]
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", checkbox)
            except Exception:
                pass
            ok = False
            for method in (lambda: checkbox.click(), lambda: ActionChains(self.driver).move_to_element(checkbox).click().perform(), lambda: self.driver.execute_script("arguments[0].click();", checkbox)):
                try:
                    method()
                    time.sleep(0.12)
                    if self.is_selected(checkbox):
                        ok = True
                        break
                except Exception:
                    pass
            if ok:
                selected_ids.append(item["id"])
                self.log(f"[INFO] Zaznaczono: {item['text'][:120]}")
        fresh_map = {item["id"]: item for item in self.rows()}
        return [fresh_map[row_id] for row_id in selected_ids if row_id in fresh_map and self.is_selected(fresh_map[row_id]["check"])]

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
        saw_signal = False
        while time.time() - start < timeout:
            for folder, old in before.items():
                try:
                    names = set(os.listdir(folder))
                except Exception:
                    continue
                if any(name.endswith((".crdownload", ".tmp", ".part")) for name in names):
                    saw_signal = True
                candidates = []
                for name in names:
                    if name.endswith((".crdownload", ".tmp", ".part")):
                        continue
                    path = os.path.join(folder, name)
                    if os.path.isfile(path) and (name not in old or os.path.getmtime(path) >= start - 1):
                        candidates.append(path)
                if candidates:
                    saw_signal = True
                if not candidates:
                    continue
                path = max(candidates, key=os.path.getmtime)
                try:
                    size = os.path.getsize(path)
                except Exception:
                    continue
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
            if not saw_signal and time.time() - start >= signal_timeout:
                return None
            time.sleep(1)
        return None

    def try_download_menu_format(self, session, format_candidates, label, timeout, signal_timeout):
        before = self.snapshot([session, self.download_dir])
        open_btn = [(By.XPATH, "//*[self::button or @role='button' or self::a][contains(., 'Pobierz') or contains(., 'Eksportuj')]")]
        if not self.click_any(open_btn, 3, 0.5):
            self.close_popups()
            return None
        direct = self.wait_file(session, before, 4, 2)
        if direct:
            self.log("[INFO] Pobieranie ruszyło bez wyboru formatu.")
            return direct
        if not self.click_any(format_candidates, 2, 0.5):
            self.close_popups()
            return None
        self.log(f"[INFO] Wybrano {label}")
        found = self.wait_file(session, before, timeout, signal_timeout)
        if found is None:
            self.close_popups()
        return found

    def download_from_list(self, session, count):
        self.set_download_dir(session)
        timeout = DOWNLOAD_TIMEOUTS.get(count, 45)
        signal_timeout = NO_SIGNAL_TIMEOUTS.get(count, 10)
        zip_btn = [(By.XPATH, "//*[self::button or @role='button' or self::a or self::span][contains(translate(., 'zip', 'ZIP'), 'ZIP')]")]
        pdf_btn = [(By.XPATH, "//*[self::button or @role='button' or self::a or self::span][contains(translate(., 'pdf', 'PDF'), 'PDF')]")]
        found = self.try_download_menu_format(session, zip_btn, "ZIP", timeout, signal_timeout)
        if found:
            return found
        if count == 1:
            self.log("[INFO] ZIP z listy nie ruszył. Próbuję PDF z listy.")
            found = self.try_download_menu_format(session, pdf_btn, "PDF", 30, 10)
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

    def open_preview_for_row(self, row_id):
        item = self.find_row(row_id)
        if not item:
            return False
        row = item["row"]
        before = self.signature()
        candidates = [
            ".//*[self::button or self::a or @role='button'][contains(., 'podgl') or contains(., 'Podgl') or contains(@aria-label, 'podgl') or contains(@title, 'podgl')]",
            ".//*[self::button or self::a or @role='button'][contains(., 'Przejdź') or contains(., 'Przejdz')]"
        ]
        for xpath in candidates:
            try:
                for el in row.find_elements(By.XPATH, xpath):
                    if not el.is_displayed():
                        continue
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    try:
                        el.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", el)
                    time.sleep(2)
                    return True
            except Exception:
                pass
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", row)
            ActionChains(self.driver).double_click(row).perform()
            time.sleep(2)
            return self.signature() != before
        except Exception:
            return False

    def return_to_list(self):
        try:
            self.driver.back()
            time.sleep(2)
        except Exception:
            pass
        self.close_popups()

    def download_from_preview(self, session):
        self.set_download_dir(session)
        pdf_btn = [(By.XPATH, "//*[self::button or @role='button' or self::a or self::span][contains(translate(., 'pdf', 'PDF'), 'PDF')]")]
        xml_btn = [(By.XPATH, "//*[self::button or @role='button' or self::a or self::span][contains(translate(., 'xml', 'XML'), 'XML')]")]
        zip_btn = [(By.XPATH, "//*[self::button or @role='button' or self::a or self::span][contains(translate(., 'zip', 'ZIP'), 'ZIP')]")]
        for label, candidates in (("PDF z podglądu", pdf_btn), ("XML z podglądu", xml_btn), ("ZIP z podglądu", zip_btn)):
            found = self.try_download_menu_format(session, candidates, label, 30, 8)
            if found:
                return found
        return None

    def try_list_batch(self, rows, session, batch_no, size):
        selected = self.select_rows(rows[:size])
        if len(selected) != min(size, len(rows)):
            self.clear_checks()
            return None
        self.set_step(f"Pobieranie partii {batch_no}")
        self.log(f"[INFO] Pobieram partię {batch_no}. Rozmiar: {len(selected)} FV")
        path = self.download_from_list(session, len(selected))
        if not path:
            self.log("[UWAGA] Pobieranie z listy nie ruszyło.")
            self.clear_checks()
            return None
        self.log(f"[OK] Zapisano: {os.path.basename(path)}")
        if self.extract_zip(path, session):
            self.log("[OK] ZIP wypakowany.")
        self.clear_checks()
        return selected

    def try_single_all_methods(self, row, session):
        selected = self.try_list_batch([row], session, 0, 1)
        if selected:
            return selected
        self.log("[INFO] Próbuję pobrać pojedynczą FV z podglądu faktury.")
        self.clear_checks()
        if self.open_preview_for_row(row["id"]):
            path = self.download_from_preview(session)
            self.return_to_list()
            if path:
                self.log(f"[OK] Zapisano z podglądu: {os.path.basename(path)}")
                if self.extract_zip(path, session):
                    self.log("[OK] ZIP wypakowany.")
                return [row]
        else:
            self.log("[UWAGA] Nie udało się wejść w podgląd tej FV.")
        return None

    def process_current_page(self, page_rows, processed, failed, session, batch_no):
        remaining_ids = [item["id"] for item in page_rows if item["id"] not in processed and item["id"] not in failed]
        while remaining_ids:
            fresh_rows = [item for item in self.rows() if item["id"] in remaining_ids]
            if not fresh_rows:
                break
            success = None
            for size in (10, 5):
                if len(fresh_rows) < 2:
                    break
                chunk = fresh_rows[:min(size, len(fresh_rows))]
                success = self.try_list_batch(chunk, session, batch_no, len(chunk))
                if success:
                    break
            if success:
                for item in success:
                    processed.add(item["id"])
                    if item["id"] in remaining_ids:
                        remaining_ids.remove(item["id"])
                batch_no += 1
                self.done_var.set(str(len(processed)))
                self.progress_set(len(processed), max(1, int(self.found_var.get() or "1")), "Pobieranie faktur")
                time.sleep(0.4)
                continue
            single = fresh_rows[0]
            result = self.try_single_all_methods(single, session)
            if result:
                for item in result:
                    processed.add(item["id"])
                    if item["id"] in remaining_ids:
                        remaining_ids.remove(item["id"])
                self.done_var.set(str(len(processed)))
                self.progress_set(len(processed), max(1, int(self.found_var.get() or "1")), "Pobieranie faktur")
            else:
                failed.add(single["id"])
                if single["id"] in remaining_ids:
                    remaining_ids.remove(single["id"])
                self.log(f"[BŁĄD] Nie udało się pobrać FV żadną metodą: {single['text'][:180]}")
        return batch_no

    def download_all_pages(self, session):
        manifest = []
        manifest_ids = set()
        processed = set()
        failed = set()
        seen_pages = set()
        batch_no = 1
        page_no = 0
        self.go_first_page()
        time.sleep(0.5)
        while page_no < MAX_PAGES:
            page_rows = self.rows()
            sig = self.signature()
            if not page_rows or sig == "EMPTY" or sig in seen_pages:
                break
            seen_pages.add(sig)
            page_no += 1
            for item in page_rows:
                if item["id"] not in manifest_ids:
                    manifest_ids.add(item["id"])
                    manifest.append({"row_id": item["id"], "text": item["text"]})
            self.found_var.set(str(len(manifest)))
            self.log(f"[INFO] Strona {page_no}: {len(page_rows)} FV. Razem wykryto: {len(manifest)}")
            batch_no = self.process_current_page(page_rows, processed, failed, session, batch_no)
            if not self.go_next_page():
                break
        missing = [item for item in manifest if item["row_id"] not in processed]
        return manifest, processed, missing

    def save_reports(self, session, manifest, processed, missing):
        info_path = os.path.join(session, "info.txt")
        with open(info_path, "w", encoding="utf-8") as handle:
            handle.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            handle.write(f"Znalezione FV: {len(manifest)}\n")
            handle.write(f"Pobrane FV: {len(processed)}\n")
            handle.write(f"Brakujące: {len(missing)}\n")
        audit_path = os.path.join(session, "raport_weryfikacji.txt")
        with open(audit_path, "w", encoding="utf-8") as handle:
            handle.write("STATUS | ID / NUMER | OPIS Z WIERSZA KSEF\n")
            handle.write("=" * 90 + "\n")
            for item in manifest:
                status = "POBRANE" if item["row_id"] in processed else "BRAK"
                handle.write(f"{status} | {item['row_id']} | {item['text']}\n")
        missing_path = None
        note_path = None
        if missing:
            missing_path = os.path.join(session, "brakujace_fv.txt")
            note_path = os.path.join(session, "NIEPOBRANE_DO_SPRAWDZENIA.txt")
            with open(missing_path, "w", encoding="utf-8") as handle:
                for item in missing:
                    handle.write(f"{item['row_id']} | {item['text']}\n")
            with open(note_path, "w", encoding="utf-8") as handle:
                handle.write("FV, których program nie mógł pobrać automatycznie\n")
                handle.write("=" * 70 + "\n")
                handle.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                handle.write(f"Liczba brakujących FV: {len(missing)}\n\n")
                handle.write("Program próbował: paczka z listy, pojedyncza FV z listy, PDF z listy, podgląd faktury, PDF/XML/ZIP z podglądu.\n\n")
                handle.write("Lista braków:\n")
                for idx, item in enumerate(missing, 1):
                    handle.write(f"{idx}. {item['row_id']} | {item['text']}\n")
        return audit_path, missing_path, note_path

    def download_all(self):
        try:
            if not self.driver:
                messagebox.showwarning("Uwaga", "Najpierw kliknij Start.")
                return
            self.start_pulse("Pobieranie FV")
            session = os.path.join(self.download_dir, datetime.now().strftime("%Y-%m-%d__%H-%M-%S__WSZYSTKIE_FV"))
            os.makedirs(session, exist_ok=True)
            self.log(f"[INFO] Folder sesji: {session}")
            manifest, processed, missing = self.download_all_pages(session)
            audit, miss, note = self.save_reports(session, manifest, processed, missing)
            self.log(f"[INFO] Raport: {audit}")
            if note:
                self.log(f"[INFO] Notatka braków: {note}")
            if missing:
                self.stop_pulse("Zakończono z brakami")
                self.result_var.set(f"Pobrane: {len(processed)} z {len(manifest)} FV | Brakuje: {len(missing)}")
                messagebox.showwarning("Niepełne pobranie", f"Pobrano {len(processed)} z {len(manifest)} FV.\nBraki: {len(missing)}\n\nNotatka: {note}\nLista: {miss}")
            else:
                self.stop_pulse("Gotowe")
                self.result_var.set(f"Pobrane: {len(processed)} z {len(manifest)} FV")
                messagebox.showinfo("Sukces", f"Pobieranie zakończone.\nZnalezione FV: {len(manifest)}\nPobrane FV: {len(processed)}\nFolder: {session}")
        except Exception as exc:
            self.stop_pulse("Błąd")
            path = os.path.join(self.base_dir, "crash_log.txt")
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(str(exc) + "\n" + traceback.format_exc() + "\n")
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
    KsefDownloader(root)
    root.mainloop()
