import os

BASE_URL = "https://aplikace.mv.gov.cz/seznam-politickych-stran/Vypis_Rejstrik.aspx?id="
CACHE_DIR = "cache"
IDS_FN = "ids.txt"

if __name__ == "__main__":
    os.makedirs(CACHE_DIR, exist_ok=True)

    ids = [225]  # TODO: drop
    if os.path.exists(IDS_FN):
        ids = [int(ln) for ln in open(IDS_FN)]

    # TODO: expand IDs if needed

    with open(IDS_FN, "wt") as fw:
        for pid in ids:
            fw.write(str(pid) + "\n")
