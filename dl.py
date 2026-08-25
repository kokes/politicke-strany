import hashlib
import json
import logging
import os
import re
import unicodedata
from glob import glob
from urllib.request import Request, urlopen

OPEN_DATA_URL = "https://mv.gov.cz/app/opendata/boards/SPS"
CACHE_DIR = "cache"
DATA_DIR = "strany"
IDS_FN = "ids.txt"


def download_if_not_cached(url):
    """Download the URL content only if not cached locally."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    file_path = os.path.join(
        CACHE_DIR, hashlib.sha256(url.encode("utf-8")).hexdigest()[:7]
    )

    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return f.read()
    else:
        logging.info("Downloading: %s", url)
        req = Request(url, headers={"User-Agent": "politicke-strany-scraper/1.0"})
        with urlopen(req, timeout=60) as response:
            content = response.read()
            with open(file_path, "wb") as f:
                f.write(content)
            return content


def fetch_registry():
    return json.loads(download_if_not_cached(OPEN_DATA_URL).decode("utf-8"))


def party_id(raw):
    return int(raw["iri"].rsplit("/", 1)[-1])


def format_identifikacni_cislo(value):
    if not value or not value.isdigit():
        return value
    return value.zfill(8)


def convert_party(raw):
    dt = {
        "nazev": raw["název"],
        "zkratka": raw.get("zkratka") or "",
        "sidlo": raw.get("adresa_sídla") or "",
        "den_registrace": raw.get("den_registrace") or "",
        "cislo_registrace": raw.get("číslo_registrace") or "",
        "identifikacni_cislo": format_identifikacni_cislo(
            raw.get("identifikační_číslo") or ""
        ),
        "statutarni_organ": raw.get("statutární_orgán") or "",
        "osoby": [],
    }

    for osoba_raw in raw.get("osoby") or []:
        role = (osoba_raw.get("funkce") or "").rstrip(":")
        osoba = {
            "role": role,
            "jmeno": osoba_raw.get("jméno") or "",
        }
        if osoba_raw.get("datum_narození"):
            osoba["datum_narozeni"] = osoba_raw["datum_narození"]
        adresa_parts = [
            part
            for part in (osoba_raw.get("adresa_ulice"), osoba_raw.get("adresa_město"))
            if part
        ]
        if adresa_parts:
            osoba["adresa"] = ", ".join(adresa_parts)
        elif not osoba["jmeno"]:
            osoba["adresa"] = ""
        dt["osoby"].append(osoba)

    dt["osoby"].sort(key=lambda x: json.dumps(x))
    return dt


def slug_from_zkratka(zkratka):
    szkr = (
        unicodedata.normalize("NFKD", zkratka.lower())
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return re.sub(r"[^a-zA-Z0-9]+", "-", szkr).strip("-")


def target_path(dt):
    fnid = hashlib.sha256(dt["cislo_registrace"].encode("utf-8")).hexdigest()[:7]
    tdir = os.path.join(DATA_DIR, dt["den_registrace"][:4])
    tfn = os.path.join(tdir, f"{fnid}-{slug_from_zkratka(dt['zkratka'])}.json")
    return fnid, tdir, tfn


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    registry = fetch_registry()
    strany = registry["strany"]
    ids = sorted(party_id(raw) for raw in strany)
    logging.info("Found %d parties in registry", len(ids))

    changed, added = [], []

    for raw in strany:
        dt = convert_party(raw)
        if not dt["nazev"]:
            logging.info("Preskakujem %d, nema nazev", party_id(raw))
            continue

        fnid, tdir, tfn = target_path(dt)
        os.makedirs(tdir, exist_ok=True)

        serialised = json.dumps(dt, ensure_ascii=False, indent=2)
        write = False

        fncand = glob(os.path.join(tdir, fnid + "*"))
        assert len(fncand) in (0, 1), fncand

        if len(fncand) == 0:
            logging.info("Nova strana: %s", dt["nazev"])
            added.append(dt["nazev"])
            write = True
        else:
            existing = open(fncand[0], "rt").read()
            if existing != serialised:
                logging.info("Zmenena strana: %s", dt["nazev"])
                changed.append(dt["nazev"])
                write = True

        for ex in fncand:
            if ex != tfn:
                os.remove(ex)

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
