"""French aeronautical frequencies parsed from the SIA eAIP pages."""

import json

import pytest

from kta16 import aero

AD2 = """
<div id="LFPN-AD-2.18"><table>
<tr><th>Service</th><th>Indicatif</th><th>FREQ</th><th>HOR</th><th>Obs</th></tr>
<tr><td>FIS</td><td>CHEVREUSE Info (FR)</td><td>119.305 MHz</td><td>HO</td><td></td></tr>
<tr><td>TWR</td><td>TOUSSUS Sol (FR) TOUSSUS Ground (EN)</td><td>122.130 MHz</td><td>HO</td><td></td></tr>
<tr><td>TWR</td><td>TOUSSUS Tour (FR) TOUSSUS Tower (EN)</td><td>120.755 MHz</td><td>HO</td><td></td></tr>
<tr><td>A/A</td><td>TOUSSUS Radio</td><td>123.5 MHz</td><td>HO</td><td></td></tr>
<tr><td>ATIS</td><td>TOUSSUS (FR)</td><td>127.480 MHz</td><td>HO</td><td></td></tr>
<tr><td>D-ATIS</td><td>TOUSSUS (FR)</td><td>NIL</td><td>H24</td><td></td></tr>
<tr><td>TWR</td><td>TOUSSUS Tour (FR)</td><td>120.755 MHz</td><td>HO</td><td>duplicate</td></tr>
</table></div><div id="LFPN-AD-2.19"><table>
<tr><th>Type</th><th>ID</th><th>FREQ</th><th>HOR</th></tr>
<tr><td>VOR-DME</td><td>BMC</td><td>113.75 MHz CH 84Y</td><td>H24</td></tr>
<tr><td>LOC 23</td><td>BD</td><td>110.3 MHz</td><td>H24</td></tr>
</table></div><div id="LFPN-AD-2.20"><table>
<tr><td>TWR</td><td>NOT A RADIO TABLE</td><td>999.999 MHz</td></tr>
</table></div>
"""
GEN34 = """
<table>
<tr><td>ACS</td><td>PARIS Contrôle (FR) PARIS Control (EN)</td><td>118.725 MHz</td><td>H24</td></tr>
<tr><td>FIS</td><td>PARIS Information (FR) PARIS Information (EN)</td><td>124.325 MHz</td><td>H24</td></tr>
<tr><td>FIS</td><td>PARIS Information (FR)</td><td>NIL</td><td>H24</td></tr>
</table>
"""


def by_name(entries):
    return {(e["name"], e["mhz"]) for e in entries}


def test_aerodrome_services_and_vor():
    got = aero.parse_aerodrome(AD2, "LFPN")
    assert by_name(got) == {
        ("PN INFO", 119.305),
        ("PN GND", 122.13),
        ("PN TWR", 120.755),
        ("PN AA", 123.5),
        ("PN ATIS", 127.48),
        ("VOR BMC", 113.75),
    }
    assert all(e["key"] == "LFPN" for e in got)


def test_no_duplicate_and_section_boundaries():
    got = aero.parse_aerodrome(AD2, "LFPN")
    assert len(got) == len(by_name(got))  # same name+freq listed twice
    assert all(e["mhz"] != 999.999 for e in got)  # AD 2.20 is not read


def test_fis_only_from_gen_3_4():
    got = aero.parse_fis(GEN34)
    assert by_name(got) == {("PARINFO", 124.325)}
    assert got[0]["key"] == "PARIS"


@pytest.mark.parametrize("text", ["", "<html>", "<tr><td>TWR</td></tr>", "\x00" * 10])
def test_garbage_gives_nothing(text):
    assert aero.parse_aerodrome(text, "LFPN") == []
    assert aero.parse_fis(text) == []


def test_names_fit_the_radio():
    for e in aero.parse_aerodrome(AD2, "LFPN") + aero.parse_fis(GEN34):
        assert aero.NAME_RE.fullmatch(e["name"])


ENTRIES = [
    {"key": "LFPX", "name": "PX GND", "mhz": 121.6, "desc": "VILLEPREUX Sol"},
    {"key": "LFPX", "name": "PX TWR", "mhz": 118.0, "desc": "VILLEPREUX Tour"},
    {"key": "PARIS", "name": "PARINFO", "mhz": 124.3, "desc": "PARIS Information"},
]


def test_search_by_icao_short_code_and_text():
    assert len(aero.search(ENTRIES, "lfpx")) == 2
    assert len(aero.search(ENTRIES, "PX")) == 2
    assert len(aero.search(ENTRIES, "paris")) == 1
    assert aero.search(ENTRIES, "") == []
    assert aero.search(ENTRIES, "x" * 500) == []
    assert aero.search(ENTRIES, "%'; DROP") == []


def test_airac_date_is_a_28_day_step_from_the_reference():
    import datetime as dt

    ref = dt.date(2026, 10, 29)
    assert aero.airac_date(ref) == ref
    assert aero.airac_date(dt.date(2026, 11, 25)) == ref
    assert aero.airac_date(dt.date(2026, 11, 26)) == dt.date(2026, 11, 26)


ENR41 = """
<table>
<tr><th>Nom</th><th>Type</th><th>ID</th><th>FREQ</th></tr>
<tr><td>ABBEVILLE</td><td>DME</td><td>ABB</td><td>108.45 MHz Ch 21Y</td></tr>
<tr><td>AJACCIO-Coti Chiavari</td><td>VOR-DME</td><td>AJO</td><td>114.8 MHz Ch 95X</td></tr>
<tr><td>AJACCIO-Coti Chiavari</td><td>VOR-DME</td><td>AJO</td><td>114.8 MHz Ch 95X</td></tr>
<tr><td>SANS ID</td><td>VOR</td><td></td><td>112.1 MHz</td></tr>
</table>
"""


def test_en_route_vor_only_keeps_vor_with_id_once():
    got = aero.parse_enr_vor(ENR41)
    assert by_name(got) == {("VOR AJO", 114.8)}
    assert got[0]["key"] == "AJACCIO-COTI CHIAVARI"
    assert aero.parse_enr_vor("") == [] and aero.parse_enr_vor("\x00") == []


def test_merge_drops_vor_already_listed_for_an_aerodrome():
    have = [{"key": "LFKJ", "name": "VOR AJO", "mhz": 114.8, "desc": "VOR AJO"}]
    new = aero.parse_enr_vor(ENR41) + [
        {"key": "X", "name": "VOR ZZZ", "mhz": 110.0, "desc": "X"}
    ]
    assert [e["name"] for e in aero.merge(have, new)] == ["VOR AJO", "VOR ZZZ"]


VAC_LFPX = """PON 111.6187° 15 NM
(D) EVX 112.4
AD 2 LFPX APP 01
ATIS/ V : 125.275 (FR)        01 30 56 38 02
APP : NIL
TWR : 129.525
GND (SOL) : 121.900
Absence ATS : A/A (129.525) FR seulement / only.
"""
VAC_LFPT = """ATIS 124.130         01 30 30 52 08
APP : LE BOURGET Approche / Approach 118.805
TWR : 121.205 . Absence ATS : A/A (121.205) FR seulement / only
"""
VAC_LFNA = """(D) MTL 113.65
ATIS/V 129.330
APP  : NIL
TWR : NIL
AFIS : 119.105. Absence ATS : A/A (119.105)
"""
VAC_LFFU = "APP  : NIL\nTWR : NIL\nA/A : 123.500\nAMDT 01/26 CHG : RDL NEV 113.4 et/and BRG 375"


def test_vac_header_services():
    def names(text):
        return by_name(aero.parse_vac(text, "LFPX", "CHAVENAY VILLEPREUX"))

    assert names(VAC_LFPX) == {
        ("PX ATIS", 125.275),
        ("PX TWR", 129.525),
        ("PX GND", 121.9),
        ("PX AA", 129.525),
    }
    assert names(VAC_LFPT) == {
        ("PX ATIS", 124.13),
        ("PX APP", 118.805),
        ("PX TWR", 121.205),
        ("PX AA", 121.205),
    }
    assert names(VAC_LFNA) == {
        ("PX ATIS", 129.33),
        ("PX AFIS", 119.105),
        ("PX AA", 119.105),
    }
    assert names(VAC_LFFU) == {("PX AA", 123.5)}  # VOR radial 113.4 is not a radio line


def test_vac_description_has_the_aerodrome_name():
    got = aero.parse_vac(VAC_LFFU, "LFFU", "CHAUMONT")
    assert got[0]["desc"] == "CHAUMONT A/A" and got[0]["key"] == "LFFU"


@pytest.mark.parametrize(
    "text", ["", "\x00", "TWR : 999.999", "ATIS 12.5", "TWR : NIL"]
)
def test_vac_garbage_or_out_of_airband_gives_nothing(text):
    assert aero.parse_vac(text, "LFPX", "X") == []


def test_glyph_names_are_decoded():
    assert aero.decode_glyphs("/MT67/MT104/MT233/MT32/MT49") == "Ché 1"
    assert aero.decode_glyphs("TWR : 121.2") == "TWR : 121.2"


def test_index_gives_code_and_name():
    page = (
        "<table><tr><th>Code</th><th>Nom</th></tr>"
        "<tr><td>LFPX</td><td>CHAVENAY VILLEPREUX</td><td>1.6 °</td></tr>"
        "<tr><td>RWY</td><td>x</td></tr></table>"
    )
    assert aero.parse_index(page) == {"LFPX": "CHAVENAY VILLEPREUX"}
    assert aero.parse_index("") == {}


def test_coverage_guard_refuses_a_build_with_too_many_empty_vac():
    aero.check_coverage(["LFFW", "LFIF", "LFKK"], 290)  # today's state: accepted
    with pytest.raises(ValueError, match="11 of 290"):
        aero.check_coverage([f"LF{i:02d}" for i in range(11)], 290)
    with pytest.raises(ValueError):
        aero.check_coverage([], 0)  # no VAC read at all


def test_build_adds_vac_services_missing_from_the_ifr_page(tmp_path, monkeypatch):
    """LFPT has an AD 2 page without APP (run by Le Bourget): the VAC adds it."""
    pages = {
        "menu": "FR-AD-2.LFPT-fr-FR.html",
        "AD-2.LFPT": AD2,
        "GEN-3.4": GEN34,
        "ENR-4.1": ENR41,
        "AD-1.3": "<table><tr><td>LFPT</td><td>PONTOISE</td><td>x</td></tr>"
        "<tr><td>LFXX</td><td>AILLEURS</td><td>x</td></tr></table>",
    }
    monkeypatch.setattr(
        aero, "_get", lambda url: next(v for k, v in pages.items() if k in url)
    )
    monkeypatch.setattr(aero, "_get_bytes", lambda url: b"")
    monkeypatch.setattr(aero, "vac_text", lambda pdf: VAC_LFPT)
    out = tmp_path / "aero.json"
    aero.build(out=out)
    got = {
        (e["key"], e["name"], e["mhz"]) for e in json.loads(out.read_text())["entries"]
    }
    assert ("LFPT", "PT APP", 118.805) in got  # added from the VAC
    assert ("LFPT", "PT TWR", 120.755) in got  # kept from the AD 2 page
    assert ("LFXX", "XX APP", 118.805) in got  # aerodrome without AD 2 page
    assert (
        len([g for g in got if g[0] == "LFPT" and g[1] == "PT ATIS"]) == 2
    )  # 127.48, 124.13


def test_vac_fis_is_named_info_like_the_ad2_pages():
    got = aero.parse_vac("FIS : 124.050", "LFBL", "LIMOGES")
    assert by_name(got) == {("BL INFO", 124.05)}


@pytest.mark.parametrize(
    ("name", "mhz", "atis", "beacon"),
    [
        ("AT ATIS", 123.13, True, False),
        ("VOR BMC", 113.75, False, True),
        ("ILS 06", 109.1, False, True),
        ("LOC AB", 110.3, False, True),
        ("OA APP", 119.7, False, False),  # AVORD: VOR is in the aerodrome name only
        ("PX GND", 121.6, False, False),
        ("XX NAV", 117.975, False, True),  # beacon band, whatever the label
        ("XX AA", 118.0, False, False),
        ("", 0.0, False, False),
    ],
)
def test_atis_and_beacon_detection(name, mhz, atis, beacon):
    hit = {"key": "LFXX", "name": name, "mhz": mhz, "desc": "AVORD Approche"}
    assert aero.is_atis(hit) is atis
    assert aero.is_beacon(hit) is beacon
