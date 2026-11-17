"""French aeronautical frequencies parsed from the SIA eAIP pages."""

import json

import pytest

from kta16 import aero, channels

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


def hit(name, mhz, key="LFXX"):
    return {"key": key, "name": name, "mhz": mhz, "desc": "X"}


def names(entries):
    return [(e["name"], e["mhz"]) for e in entries]


def test_unique_name_is_unchanged():
    got = aero.number_duplicates([hit("PX TWR", 129.525), hit("PX GND", 121.9)])
    assert names(got) == [("PX TWR", 129.525), ("PX GND", 121.9)]


def test_duplicates_are_numbered_in_file_order_not_by_frequency():
    got = aero.number_duplicates(
        [hit("BD APP", 129.88), hit("PX GND", 121.9), hit("BD APP", 121.205),
         hit("BD APP", 126.73)]
    )  # fmt: skip
    assert names(got) == [
        ("BD APP1", 129.88), ("PX GND", 121.9), ("BD APP2", 121.205),
        ("BD APP3", 126.73),
    ]  # fmt: skip


def test_same_name_same_frequency_shares_its_number():
    got = aero.number_duplicates(
        [hit("BC APP", 121.5, "LFAA"), hit("BC APP", 243.0, "LFBB"),
         hit("BC APP", 121.5, "LFCC")]
    )  # fmt: skip
    assert [e["name"] for e in got] == ["BC APP1", "BC APP2", "BC APP1"]


def test_same_name_same_frequency_only_is_not_a_duplicate():
    got = aero.number_duplicates([hit("BC APP", 121.5, "A"), hit("BC APP", 121.5, "B")])
    assert [e["name"] for e in got] == ["BC APP", "BC APP"]


def test_number_takes_the_place_of_the_last_characters_at_7():
    got = aero.number_duplicates([hit("PX ATIS", 125.275), hit("PX ATIS", 125.3)])
    assert [e["name"] for e in got] == ["PX ATI1", "PX ATI2"]
    assert [e["base"] for e in got] == ["PX ATIS", "PX ATIS"]


def test_two_digit_numbers_stay_within_7_characters():
    got = aero.number_duplicates([hit("BC APP", 118 + i / 10) for i in range(11)])
    out = [e["name"] for e in got]
    assert out[8:] == ["BC APP9", "BC AP10", "BC AP11"]
    assert len(set(out)) == 11 and all(len(n) <= 7 for n in out)


def test_trailing_space_is_dropped_before_the_number():
    got = aero.number_duplicates([hit("AB C", 118.0), hit("AB C", 119.0)])
    assert [e["name"] for e in got] == ["AB C1", "AB C2"]
    got = aero.number_duplicates([hit("ABCDEF ", 118.0), hit("ABCDEF ", 119.0)])
    assert [e["name"] for e in got] == ["ABCDEF1", "ABCDEF2"]


def test_number_duplicates_keeps_input_and_handles_empty():
    entries = [hit("BD APP", 1.0), hit("BD APP", 2.0)]
    aero.number_duplicates(entries)
    assert [e["name"] for e in entries] == ["BD APP", "BD APP"]
    assert "base" not in entries[0]
    assert aero.number_duplicates([]) == []


def test_real_aero_json_has_one_frequency_per_name():
    entries = aero.load()
    if not entries:
        pytest.skip("aero.json missing")
    seen = {}
    for e in entries:
        assert aero.NAME_RE.fullmatch(e["name"]), e
        assert seen.setdefault(e["name"], e["mhz"]) == e["mhz"], e["name"]


@pytest.mark.parametrize(
    ("name", "base", "atis", "beacon"),
    [
        ("PX ATI1", "PX ATIS", True, False),
        ("PX TWR1", "PX TWR", False, False),
        ("VOR AB1", "VOR ABC", False, True),
    ],
)
def test_detection_reads_the_name_before_numbering(name, base, atis, beacon):
    h = {**hit(name, 125.275), "base": base}
    assert aero.is_atis(h) is atis
    assert aero.is_beacon(h) is beacon


def ch(name, rx, tx="same", **kw):
    tx_hz = rx if tx == "same" else tx
    return channels.Channel(
        rx, tx_hz, "OFF", "OFF", "LOW", False, "OFF", False, True, None, "OFF",
        "QT", False, name, **kw,
    )  # fmt: skip


NEW = [hit("PX TWR", 129.525), hit("PX GND", 121.9), hit("VOR BMC", 113.75)]


def test_refresh_moves_rx_and_tx_that_followed_it():
    old = ch("PX TWR", 120_000_000)
    got = aero.refresh({3: old}, NEW)
    assert got == [(3, old, ch("PX TWR", 129_525_000))]


def test_refresh_leaves_a_matching_frequency_alone():
    assert aero.refresh({1: ch("PX GND", 121_900_000)}, NEW) == []


def test_refresh_keeps_a_tx_that_differs_from_rx():
    got = aero.refresh({1: ch("PX TWR", 120_000_000, tx=121_000_000)}, NEW)
    assert got[0][2] == ch("PX TWR", 129_525_000, tx=121_000_000)


def test_refresh_keeps_a_disabled_tx():
    off = channels.TX_OFF_HZ
    got = aero.refresh({1: ch("PX TWR", 120_000_000, tx=off)}, NEW)
    assert got[0][2] == ch("PX TWR", 129_525_000, tx=off)


def test_refresh_keeps_an_empty_tx_in_the_beacon_band():
    got = aero.refresh({1: ch("VOR BMC", 113_000_000, tx=None)}, NEW)
    assert got[0][2] == ch("VOR BMC", 113_750_000, tx=None)


@pytest.mark.parametrize("name", ["", "UNKNOWN", "px twr", "X" * 500, "%'; DROP"])
def test_refresh_ignores_names_it_does_not_know(name):
    assert aero.refresh({1: ch(name, 120_000_000)}, NEW) == []


def test_refresh_skips_empty_slots_and_works_without_data():
    assert aero.refresh({1: None, 2: ch("PX TWR", 120_000_000)}, []) == []
    assert aero.refresh({}, NEW) == []
    assert [
        n for n, _, _ in aero.refresh({1: None, 2: ch("PX TWR", 1_000_000)}, NEW)
    ] == [2]


def test_refresh_returns_channels_in_number_order():
    got = aero.refresh({5: ch("PX GND", 1_000_000), 2: ch("PX TWR", 1_000_000)}, NEW)
    assert [n for n, _, _ in got] == [2, 5]


BASE_HITS = aero.number_duplicates(
    [hit("BD APP", 119.275), hit("BD APP", 126.73), hit("PX ATIS", 125.275),
     hit("PX ATIS", 125.3), hit("PX TWR", 129.525)]
)  # fmt: skip


def test_refresh_numbers_an_old_plain_name_from_its_frequency():
    old = ch("BD APP", 126_730_000)
    assert aero.refresh({4: old}, BASE_HITS) == [(4, old, ch("BD APP2", 126_730_000))]


def test_refresh_numbering_keeps_tx_and_cuts_like_the_list():
    old = ch("PX ATIS", 125_300_000, tx=channels.TX_OFF_HZ)
    got = aero.refresh({1: old}, BASE_HITS)
    assert got == [(1, old, ch("PX ATI2", 125_300_000, tx=channels.TX_OFF_HZ))]


def test_refresh_does_not_guess_a_plain_name_on_an_unknown_frequency():
    assert aero.refresh({1: ch("BD APP", 100_000_000)}, BASE_HITS) == []


def test_refresh_numbered_names_are_not_renamed_again():
    assert aero.refresh({1: ch("BD APP2", 126_730_000)}, BASE_HITS) == []
