"""Texts of the TUI: French and English catalogues stay in step."""

import re

import pytest

from kta16 import i18n


def fields(text):
    return sorted(re.findall(r"\{(\w*)\}", text))


def test_both_languages_have_the_same_keys():
    assert set(i18n.MESSAGES["fr"]) == set(i18n.MESSAGES["en"])


def test_both_languages_use_the_same_placeholders():
    for key, fr in i18n.MESSAGES["fr"].items():
        assert fields(fr) == fields(i18n.MESSAGES["en"][key]), key


def test_no_empty_text():
    for lang, catalogue in i18n.MESSAGES.items():
        for key, text in catalogue.items():
            assert text.strip(), (lang, key)


@pytest.mark.parametrize(
    "env,expected",
    [
        ({"LANG": "fr_FR.UTF-8"}, "fr"),
        ({"LC_ALL": "fr_CA.UTF-8", "LANG": "en_US.UTF-8"}, "fr"),
        ({"LC_MESSAGES": "en_GB.UTF-8", "LANG": "fr_FR.UTF-8"}, "en"),
        ({"LANG": "de_DE.UTF-8"}, "en"),
        ({"LANG": "C"}, "en"),
        ({}, "en"),
    ],
)
def test_language_follows_the_environment(env, expected):
    assert i18n.detect(env) == expected


def test_set_language_and_translate():
    i18n.set_language("en")
    assert i18n.t("b_quit") == "Quit"
    assert i18n.t("pending_channel", n=2) == "Channel 2"
    i18n.set_language("fr")
    assert i18n.t("b_quit") == "Quitter"
    assert i18n.t("pending_channel", n=2) == "Canal 2"


def test_unknown_language_and_key_are_refused():
    with pytest.raises(ValueError):
        i18n.set_language("de")
    with pytest.raises(KeyError):
        i18n.t("no such key")


def test_default_is_english_for_other_locales():
    assert i18n.detect({"LANG": "de_DE.UTF-8"}) == "en"
    assert i18n.detect({"LANG": "fr_BE.UTF-8"}) == "fr"


def test_english_texts_hold_no_french_letters():
    accented = set("éèêàçùôîïœÉÈÀ")
    for key, (_, en) in i18n._TEXTS.items():
        assert not accented & set(en), f"{key}: {en}"


def test_aero_description_follows_the_language():
    try:
        i18n.set_language("fr")
        assert i18n.aero_desc("AVORD Approche") == "AVORD Approche"
        i18n.set_language("en")
        assert i18n.aero_desc("AVORD Approche") == "AVORD Approach"
        assert i18n.aero_desc("DE GAULLE Gonio") == "DE GAULLE Direction finding"
        assert i18n.aero_desc("LE TOUQUET") == "LE TOUQUET"  # names are untouched
    finally:
        i18n.set_language("fr")
