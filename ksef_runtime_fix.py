import time

from selenium.webdriver.common.by import By

import ksef_app_selenium_edge_fix as base


def _signature(app):
    try:
        if hasattr(app, "page_signature"):
            return app.page_signature()
    except Exception:
        pass
    try:
        return app.signature()
    except Exception:
        return "EMPTY"


def _sleep(app, seconds):
    try:
        app.sleep(seconds)
    except Exception:
        time.sleep(seconds)


def _enabled_element(app, candidates):
    for by, value in candidates:
        try:
            elements = app.driver.find_elements(by, value)
        except Exception:
            elements = []
        for element in elements:
            try:
                if not element.is_displayed():
                    continue
                if element.get_attribute("disabled") is not None:
                    continue
                if element.get_attribute("aria-disabled") == "true":
                    continue
                return element
            except Exception:
                pass
    return None


def _wait_page_change(app, before, timeout=7):
    end = time.time() + timeout
    while time.time() < end:
        after = _signature(app)
        if after != before and after != "EMPTY":
            return True
        _sleep(app, 0.10)
    return False


def go_first_page_fixed(self):
    """Wraca faktycznie na stronę 1, bez starego limitu 50 cofnięć."""
    if not getattr(self, "driver", None):
        return False

    first_candidates = [
        (By.CSS_SELECTOR, "button[aria-label*='Pierwsza']"),
        (By.CSS_SELECTOR, "button[title*='Pierwsza']"),
        (By.CSS_SELECTOR, "[role='button'][aria-label*='Pierwsza']"),
        (By.CSS_SELECTOR, "button[aria-label*='First']"),
        (By.CSS_SELECTOR, "button[title*='First']"),
        (By.XPATH, "//button[contains(@aria-label,'Pierwsza') or contains(@title,'Pierwsza') or contains(@aria-label,'First') or contains(@title,'First')]"),
    ]
    previous_candidates = [
        (By.CSS_SELECTOR, "button[aria-label*='Poprzednia']"),
        (By.CSS_SELECTOR, "button[title*='Poprzednia']"),
        (By.CSS_SELECTOR, "[role='button'][aria-label*='Poprzednia']"),
        (By.CSS_SELECTOR, "button[aria-label*='Previous']"),
        (By.CSS_SELECTOR, "button[title*='Previous']"),
        (By.XPATH, "//button[contains(@aria-label,'Poprzednia') or contains(@title,'Poprzednia') or contains(@aria-label,'Previous') or contains(@title,'Previous')]"),
    ]

    # Jeżeli KSeF pokazuje przycisk „pierwsza strona”, użyj jednego kliknięcia.
    first = _enabled_element(self, first_candidates)
    if first is not None:
        before = _signature(self)
        if self.click_element(first, 0.03) and _wait_page_change(self, before):
            _sleep(self, 0.15)
            if _enabled_element(self, previous_candidates) is None:
                try:
                    self.log("[INFO] Wrócono do strony 1.")
                except Exception:
                    pass
                return True

    # Fallback: cofaj tyle razy, ile naprawdę potrzeba. Bez limitu 50 stron.
    moved = 0
    max_steps = int(getattr(base, "MAX_PAGES", 300)) + 10
    for _ in range(max_steps):
        previous = _enabled_element(self, previous_candidates)
        if previous is None:
            try:
                self.log(f"[INFO] Wrócono do strony 1 (cofnięto {moved} stron).")
            except Exception:
                pass
            return True

        before = _signature(self)
        if not self.click_element(previous, 0.03):
            raise RuntimeError("Nie udało się kliknąć poprzedniej strony podczas powrotu do początku listy.")

        if not _wait_page_change(self, before):
            # Po kliknięciu na pierwszej stronie przycisk może od razu stać się nieaktywny.
            if _enabled_element(self, previous_candidates) is None:
                return True
            raise RuntimeError(
                "KSeF nie zmienił strony podczas powrotu do początku listy. "
                "Przerwałem, żeby nie rozpocząć pobierania od złej strony."
            )
        moved += 1

    raise RuntimeError(
        f"Nie udało się wrócić do strony 1 po {max_steps} próbach. "
        "Pobieranie nie zostało rozpoczęte."
    )


base.SimpleKsefDownloader.go_first_page = go_first_page_fixed
