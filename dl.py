import hashlib
import os
from urllib.request import urlopen

import lxml.html

BASE_URL = "https://aplikace.mv.gov.cz/seznam-politickych-stran/Vypis_Rejstrik.aspx?id="
CACHE_DIR = "cache"
IDS_FN = "ids.txt"


def download_if_not_cached(url):
    """Download the URL content only if not cached locally."""
    file_path = os.path.join(CACHE_DIR, hashlib.sha256(url.encode("utf-8")).hexdigest())

    if os.path.exists(file_path):
        print(f"Using cached file: {file_path}")
        with open(file_path, "rb") as f:
            return f.read()
    else:
        print(f"Downloading: {url}")
        with urlopen(url) as response:
            content = response.read()
            with open(file_path, "wb") as f:
                f.write(content)
            return content


def tc(root, selector):
    els = root.cssselect(selector)
    if not els:
        return None

    return els[0].text_content()


if __name__ == "__main__":
    os.makedirs(CACHE_DIR, exist_ok=True)

    ids = []
    if os.path.exists(IDS_FN):
        ids = [int(ln) for ln in open(IDS_FN)]

    ids = [225, 359]  # TODO: drop

    # TODO: expand IDs if needed

    # TODO: dl
    for pid in ids:
        url = BASE_URL + str(pid)
        data = download_if_not_cached(url)
        # TODO: yank out into a func
        ht = lxml.html.fromstring(data)
        dt = {
            "nazev": tc(ht, "span#ctl00_Application_lblNazevStrany"),
            "sidlo": tc(ht, "span#ctl00_Application_lblAdresaSidla"),
            # TODO: ISO konverze
            "den_registrace": tc(ht, "span#ctl00_Application_lblDenRegistrace"),
            "cislo_registrace": tc(ht, "span#ctl00_Application_lblCisloRegistrace"),
            "identifikacni_cislo": tc(ht, "span#ctl00_Application_lblIdentCislo"),
        }
        print(dt)

    with open(IDS_FN, "wt") as fw:
        for pid in ids:
            fw.write(str(pid) + "\n")
