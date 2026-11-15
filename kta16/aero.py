"""French aeronautical frequencies, read from the SIA eAIP (public HTML pages).

Source: SIA (Service de l'Information Aeronautique), eAIP France, published
under the Licence Ouverte: keep the SIA name and the AIRAC date (both are
stored in aero.json). `python -m kta16.aero` rebuilds aero.json from the
current AIRAC cycle.
"""

import datetime as dt
import html as htmllib
import json
import logging
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from io import BytesIO
from pathlib import Path

DATA = Path(__file__).with_name("aero.json")
NAME_RE = re.compile(r"[0-9A-Z +_-]{0,7}")  # same rule as channels.NAME_RE
AIRAC_REF = dt.date(2026, 10, 29)  # a known AIRAC date; cycles are 28 days
MONTHS = [
    "JAN",
    "FEB",
    "MAR",
    "APR",
    "MAY",
    "JUN",
    "JUL",
    "AUG",
    "SEP",
    "OCT",
    "NOV",
    "DEC",
]
BASE = "https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_{day:02d}_{mon}_{year}/FRANCE/AIRAC-{iso}/html/eAIP"
VAC_URL = "https://www.sia.aviation-civile.gouv.fr/media/dvd/eAIP_{day:02d}_{mon}_{year}/Atlas-VAC/PDF_AIPparSSection/VAC/AD/AD-2.{icao}.pdf"
VAC_LINE_RE = re.compile(r"(ATIS|APP|TWR|GND|AFIS|A/A|FIS|SOL|Absence ATS)\b")
VAC_SERVICE_RE = re.compile(
    r"\b(ATIS(?:/ ?V)?|APP|TWR|GND|AFIS|A/A|FIS)\b[^0-9\n]*?(\d{3}\.\d{1,3})"
)
MAX_EMPTY_VAC = 10  # 3 today; more means the SIA changed its PDF layout or fonts
AIRBAND = (118.0, 137.0)  # MHz, filters out VOR and radial numbers read in a VAC
FREQ_RE = re.compile(r"(\d{3}\.\d{1,3}) MHz")
SECTION_RE = re.compile(r'id="[A-Z]{4}-AD-2\.\d+"')


def airac_date(today):
    """Start date of the AIRAC cycle in force on `today`."""
    return AIRAC_REF + dt.timedelta(days=(today - AIRAC_REF).days // 28 * 28)


def _rows(page):
    """Table rows of an HTML fragment as lists of plain-text cells."""
    for row in re.findall(r"<tr.*?</tr>", page, re.DOTALL):
        cells = re.findall(r"<t[dh].*?</t[dh]>", row, re.DOTALL)
        yield [
            re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
            for c in cells
        ]


def _section(page, number):
    """Text of AD 2.<number> of an aerodrome page, up to the next AD 2.x."""
    start = page.find(f'AD-2.{number}"')
    if start < 0:
        return ""
    nxt = SECTION_RE.search(page, start + 1)
    return page[start : nxt.start() if nxt else len(page)]


def _suffix(service, callsign):
    """Short service label for a channel name (GND, TWR, ATIS...)."""
    c = callsign.upper()
    if service == "TWR":
        for pattern, label in (
            (r"\b(SOL|GROUND)\b", "GND"),
            (r"\b(PREVOL|DELIVERY)\b", "DEL"),
            (r"\b(TRAFIC|APRON|RAMP)\b", "APN"),
        ):
            if re.search(pattern, c):
                return label
        return "TWR"
    if service == "FIS":
        return "INFO"
    return re.sub(r"[^0-9A-Z +_-]", "", service.upper())  # A/A -> AA


def decode_glyphs(text):
    """The SIA VAC fonts name each glyph /MT<decimal code>: turn them back into text."""
    return re.sub(r"/MT(\d+)", lambda m: chr(int(m[1])), text)


def parse_index(page):
    """{ICAO code: aerodrome name} from AD 1.3."""
    return {
        c[0]: c[1]
        for c in _rows(page)
        if len(c) > 2 and re.fullmatch(r"[A-Z]{4}", c[0]) and c[1]
    }


def parse_vac(text, icao, title):
    """Radio services of a VAC header (first page text): ATIS, APP, TWR, GND, AFIS, A/A."""
    out = []
    for line in text.splitlines():
        if not VAC_LINE_RE.match(line.strip()):
            continue
        for m in VAC_SERVICE_RE.finditer(line):
            service = "ATIS" if m[1].startswith("ATIS") else m[1]
            if AIRBAND[0] <= float(m[2]) <= AIRBAND[1]:
                label = (
                    "INFO"
                    if service == "FIS"
                    else re.sub(r"[^0-9A-Z +_-]", "", service)
                )
                out.append(
                    _entry(icao, f"{icao[2:]} {label}", m[2], f"{title} {service}")
                )
    return _dedup(out)


def check_coverage(without, total):
    """Refuse a build when too many VAC gave no frequency (parser out of date)."""
    if total == 0 or len(without) > MAX_EMPTY_VAC:
        raise ValueError(
            f"{len(without)} of {total} VAC without frequency: {' '.join(without)}"
        )


def vac_text(pdf):
    """Text of the first page of a VAC PDF (bytes), glyph names decoded."""
    from pypdf import PdfReader  # only `make aero` needs it

    logging.getLogger("pypdf").setLevel(logging.ERROR)  # one fontTools notice per font
    return decode_glyphs(PdfReader(BytesIO(pdf)).pages[0].extract_text())


def _entry(key, name, mhz, desc):
    return {"key": key, "name": name[:7].strip(), "mhz": float(mhz), "desc": desc}


def _dedup(entries):
    seen, out = set(), []
    for e in entries:
        if (e["key"], e["name"], e["mhz"]) not in seen:
            seen.add((e["key"], e["name"], e["mhz"]))
            out.append(e)
    return out


def parse_aerodrome(page, icao):
    """Radio services (AD 2.18) and VOR (AD 2.19) of one aerodrome page."""
    out = []
    for cells in _rows(_section(page, 18)):
        m = len(cells) > 2 and FREQ_RE.search(cells[2])
        if m and cells[0]:
            desc = cells[1].split(" (")[0]
            out.append(
                _entry(icao, f"{icao[2:]} {_suffix(cells[0], cells[1])}", m[1], desc)
            )
    for cells in _rows(_section(page, 19)):
        m = len(cells) > 2 and FREQ_RE.search(cells[2])
        if m and cells[0].startswith("VOR") and cells[1]:
            out.append(_entry(icao, f"VOR {cells[1]}", m[1], f"{cells[0]} {cells[1]}"))
    return _dedup(out)


def parse_fis(page):
    """Flight information services of the FIR (GEN 3.4), e.g. Paris Information."""
    out = []
    for cells in _rows(page):
        m = len(cells) > 2 and FREQ_RE.search(cells[2])
        if m and cells[0] == "FIS":
            key = cells[1].split()[0].upper()
            out.append(_entry(key, f"{key[:3]}INFO", m[1], cells[1].split(" (")[0]))
    return _dedup(out)


def parse_enr_vor(page):
    """En-route VOR and VOR-DME (ENR 4.1): name, type, ident, frequency."""
    out = []
    for cells in _rows(page):
        m = len(cells) > 3 and FREQ_RE.search(cells[3])
        if m and cells[1].startswith("VOR") and cells[2]:
            out.append(
                _entry(
                    cells[0].upper(), f"VOR {cells[2]}", m[1], f"{cells[0]} {cells[1]}"
                )
            )
    return _dedup(out)


def merge(have, new):
    """`have` plus the entries of `new` whose (name, frequency) is not in it yet."""
    seen = {(e["name"], e["mhz"]) for e in have}
    return have + [e for e in new if (e["name"], e["mhz"]) not in seen]


BEACON_BAND = (
    108.0,
    117.975,
)  # MHz: VOR, ILS localizer (the radio never transmits there)
_ATIS_RE = re.compile(r"\bATIS\b")
_BEACON_RE = re.compile(r"^(VOR|ILS|LOC|DME)\b")


def is_atis(hit):
    """ATIS service. Only the service label counts, never the aerodrome name."""
    return bool(_ATIS_RE.search(hit["name"]))


def is_beacon(hit):
    """VOR, ILS or any frequency of the beacon band (AVORD APP is not a beacon)."""
    return bool(_BEACON_RE.match(hit["name"])) or (
        BEACON_BAND[0] <= hit["mhz"] <= BEACON_BAND[1]
    )


def search(entries, text):
    """Entries whose ICAO code, name or description contains `text` (at most 50)."""
    t = text.strip().upper()
    if not t:
        return []
    hits = (e for e in entries if t in f"{e['key']}|{e['name']}|{e['desc'].upper()}")
    return [e for _, e in zip(range(50), hits)]


@cache
def load():
    """Entries of aero.json (empty list when `python -m kta16.aero` was never run)."""
    try:
        return json.loads(DATA.read_text(encoding="utf-8"))["entries"]
    except (OSError, ValueError, KeyError):
        return []


def _get_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kta16-aero"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _get(url):
    return _get_bytes(url).decode("utf-8")


def _vac_entries(day, icao, title):
    """Entries of one VAC, [] when the PDF is missing or unreadable."""
    url = VAC_URL.format(
        day=day.day, mon=MONTHS[day.month - 1], year=day.year, icao=icao
    )
    try:
        return parse_vac(vac_text(_get_bytes(url)), icao, title)
    except Exception:  # noqa: BLE001  # one bad PDF must not stop the whole build
        return []


def build(today=None, out=DATA):
    """Download the eAIP of the current AIRAC cycle and write `out`."""
    day = airac_date(today or dt.date.today())
    base = BASE.format(
        day=day.day, mon=MONTHS[day.month - 1], year=day.year, iso=day.isoformat()
    )
    menu = _get(f"{base}/FR-menu-fr-FR.html")
    icaos = sorted(set(re.findall(r"FR-AD-2\.([A-Z]{4})-fr-FR\.html", menu)))
    with ThreadPoolExecutor(8) as pool:
        pages = list(pool.map(lambda i: _get(f"{base}/FR-AD-2.{i}-fr-FR.html"), icaos))
    entries = parse_fis(_get(f"{base}/FR-GEN-3.4-fr-FR.html"))
    for icao, page in zip(icaos, pages):
        entries += parse_aerodrome(page, icao)
    entries = merge(entries, parse_enr_vor(_get(f"{base}/FR-ENR-4.1-fr-FR.html")))
    # The VAC header lists services the AD 2 page may lack (LFPT: APP run by Le Bourget),
    # and is the only source for VFR aerodromes
    index = parse_index(_get(f"{base}/FR-AD-1.3-fr-FR.html"))
    codes = sorted(index)
    with ThreadPoolExecutor(8) as pool:
        vacs = list(pool.map(lambda i: _vac_entries(day, i, index[i]), codes))
    for found in vacs:
        entries += found
    entries = _dedup(entries)
    missing = [i for i in codes if i not in icaos]  # VFR: no AD 2 page
    without = [i for i, found in zip(codes, vacs) if i in missing and not found]
    print(
        f"VAC: {len(missing)} VFR aerodromes, {len(without)} without frequency: {' '.join(without)}"
    )
    check_coverage(without, len(missing))
    doc = {
        "source": "SIA, eAIP France, Licence Ouverte",
        "airac": day.isoformat(),
        "entries": entries,
    }
    out.write_text(
        json.dumps(doc, ensure_ascii=True, indent=0) + "\n", encoding="ascii"
    )
    return len(icaos), len(entries)


if __name__ == "__main__":
    aerodromes, entries = build()
    print(f"aerodromes: {aerodromes}, entries: {entries}")
