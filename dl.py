import hashlib
import json
import logging
import os
import re
from urllib.request import urlopen

import lxml.html

BASE_URL = "https://aplikace.mv.gov.cz/seznam-politickych-stran/Vypis_Rejstrik.aspx?id="
CACHE_DIR = "cache"
DATA_DIR = "strany"
IDS_FN = "ids.txt"

DT_RE = re.compile(r"[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4}")


def download_if_not_cached(url):
    """Download the URL content only if not cached locally."""
    file_path = os.path.join(
        CACHE_DIR, hashlib.sha256(url.encode("utf-8")).hexdigest()[:7]
    )

    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return f.read()
    else:
        logging.info("Downloading: %s", url)
        with urlopen(url) as response:
            content = response.read()
            with open(file_path, "wb") as f:
                f.write(content)
            return content


def tc(root, selector):
    els = root.cssselect(selector)
    if not els:
        return None

    return els[0].text_content().strip()


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
    logging.getLogger().setLevel(logging.INFO)
    os.makedirs(CACHE_DIR, exist_ok=True)

    ids = []
    if os.path.exists(IDS_FN):
        ids = [int(ln) for ln in open(IDS_FN)]

    mid = max(ids) if len(ids) > 0 else 0
    # inkrementalni zkouseni jen po kouskach, ale inicialni load
    # udelame velkej
    # rng = 10 if mid > 0 else 200
    rng = 10
    # zkusime par novych IDs
    for j in range(1, rng):
        ids.append(mid + j)

    changed, added = [], []

    os.makedirs(DATA_DIR, exist_ok=True)
    # list, abychom to duplikovali (budem mazat)
    for pid in list(ids):
        url = BASE_URL + str(pid)
        data = download_if_not_cached(url)
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
        if dt["nazev"] == "":
            logging.info("Preskakujem %d, nema nazev", pid)
            ids.remove(pid)
            continue
        dt["den_registrace"] = iso_dt(dt["den_registrace"])

        # osoby jsou trochu tricky
        osoby = [j for j in tbl.findall(".//h3") if j.text_content() == "Osoby"]
        if len(osoby) == 1:
            tros = first_typed_parent(osoby[0], "tr")
            for el in tros.itersiblings():
                if el.tag != "tr":
                    break
                tds = el.findall("td")
                assert len(tds) == 2, tds
                role = tds[0].text_content().strip().rstrip(":")
                detaily = [j.strip() for j in tds[1].itertext()]
                osoba = {
                    "role": role,
                    "jmeno": detaily[0],
                }
                idx = 1
                if DT_RE.match(detaily[1]) is not None:
                    osoba["datum_narozeni"] = iso_dt(detaily[1])
                    idx += 1

                adresa = detaily[idx : idx + detaily[idx:].index("")]
                osoba["adresa"] = ", ".join(adresa)

                # TODO: Plati od/plati do? v tom co zbylo
                dt["osoby"].append(osoba)

        # puvodne jsem pro nazev souboru pouzival identifikacni cislo,
        # ale zdaleka ne vsechny strany ho maj
        fnid = hashlib.sha256(dt["cislo_registrace"].encode("utf-8")).hexdigest()[:7]
        tdir = os.path.join(DATA_DIR, dt["den_registrace"][:4])
        os.makedirs(tdir, exist_ok=True)
        tfn = os.path.join(tdir, fnid + ".json")

        serialised = json.dumps(dt, ensure_ascii=False, indent=2)
        write = False
        if not os.path.exists(tfn):
            logging.info("Nova strana: %s", dt["nazev"])
            added.append(dt["nazev"])
            write = True
        else:
            existing = open(tfn, "rt").read()
            if existing != serialised:
                logging.info("Zmenena strana: %s", dt["nazev"])
                changed.append(dt["nazev"])
                write = True

        if write:
            with open(tfn, "wt") as fw:
                fw.write(serialised)

    if len(changed) + len(added) > 0:
        print(f"Změněno: {len(changed)}, přidáno: {len(added)}")
        print()
        for el in sorted(changed):
            print(f"Změna ve straně: {el}")
        for el in sorted(added):
            print(f"Nová strana: {el}")

    with open(IDS_FN, "wt") as fw:
        for pid in ids:
            fw.write(str(pid) + "\n")
