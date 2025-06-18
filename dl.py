import hashlib
import json
import os
from urllib.request import urlopen

import lxml.html

BASE_URL = "https://aplikace.mv.gov.cz/seznam-politickych-stran/Vypis_Rejstrik.aspx?id="
CACHE_DIR = "cache"
DATA_DIR = "strany"
IDS_FN = "ids.txt"


def download_if_not_cached(url):
    """Download the URL content only if not cached locally."""
    file_path = os.path.join(
        CACHE_DIR, hashlib.sha256(url.encode("utf-8")).hexdigest()[:7]
    )

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


def iso_dt(s):
    parts = s.split(".")
    assert len(parts) == 3, parts
    return f"{parts[2]}-{str(parts[1]).rjust(2, '0')}-{str(parts[0]).rjust(2, '0')}"


def first_typed_parent(el, tag):
    parent = el.getparent()
    while parent is not None:
        if parent.tag.lower() == tag:
            return parent
        parent = parent.getparent()
    return None


if __name__ == "__main__":
    os.makedirs(CACHE_DIR, exist_ok=True)

    ids = []
    if os.path.exists(IDS_FN):
        ids = [int(ln) for ln in open(IDS_FN)]

    ids = [225, 359]  # TODO: drop

    # TODO: expand IDs if needed

    os.makedirs(DATA_DIR, exist_ok=True)
    for pid in ids:
        url = BASE_URL + str(pid)
        data = download_if_not_cached(url)
        # TODO: yank out into a func
        ht = lxml.html.fromstring(data)
        tbl = ht.cssselect("table#vypisRejstrik")[0]
        dt = {
            "nazev": tc(tbl, "span#ctl00_Application_lblNazevStrany"),
            "zkratka": tc(tbl, "span#ctl00_Application_lblZkratkaStrany"),
            "sidlo": tc(tbl, "span#ctl00_Application_lblAdresaSidla"),
            "den_registrace": tc(tbl, "span#ctl00_Application_lblDenRegistrace"),
            "cislo_registrace": tc(tbl, "span#ctl00_Application_lblCisloRegistrace"),
            "identifikacni_cislo": tc(tbl, "span#ctl00_Application_lblIdentCislo"),
            "statutarni_organ": tc(tbl, "span#ctl00_Application_lblStatutarOrgan"),
            "osoby": [],
        }
        dt["den_registrace"] = iso_dt(dt["den_registrace"])

        # osoby jsou trochu tricky
        osoby = [j for j in tbl.findall(".//h3") if j.text_content() == "Osoby"][0]
        tros = first_typed_parent(osoby, "tr")
        for el in tros.itersiblings():
            if el.tag != "tr":
                break
            tds = el.findall("td")
            assert len(tds) == 2, tds
            role = tds[0].text_content().strip()
            detaily = [j.strip() for j in tds[1].itertext()]
            osoba = {
                "role": role,
                "jmeno": detaily[0],
                "datum_narozeni": iso_dt(detaily[1]),
                "adresa": f"{detaily[2]}, {detaily[3]}",
            }
            assert detaily[4] == "", detaily
            # TODO: Plati od/plati do? v detaily[5:]
            dt["osoby"].append(osoba)

        tfn = os.path.join(DATA_DIR, dt["identifikacni_cislo"] + ".json")
        with open(tfn, "wt") as fw:
            json.dump(dt, fw, ensure_ascii=False, indent=2)

    with open(IDS_FN, "wt") as fw:
        for pid in ids:
            fw.write(str(pid) + "\n")
