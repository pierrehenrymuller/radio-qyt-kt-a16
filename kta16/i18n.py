"""Texts of the TUI in French and English.

The language is chosen once, at start: `--lang fr|en`, else the environment
(LC_ALL, LC_MESSAGES, LANG): French when the first variable set starts with
"fr", English otherwise. Labels of the vendor software that are kept as in
the CPS (field names such as "DTMF Speed On", "Group Code") are not
translated.
"""

import os

LANGUAGES = ("fr", "en")

# key: (French, English)
_TEXTS = {
    "app_title": ("QYT KT-A16", "QYT KT-A16"),
    # shortcuts shown in the footer
    "b_read": ("Lire radio", "Read radio"),
    "b_write": ("Écrire radio", "Write radio"),
    "b_write_changes": ("Écrire modifs", "Write changes"),
    "b_default": ("Défaut", "Default"),
    "b_clear": ("Effacer", "Clear"),
    "b_open": ("Ouvrir", "Open"),
    "b_save": ("Enregistrer", "Save"),
    "b_release": ("Libérer la radio", "Release radio"),
    "b_theme": ("Thème", "Theme"),
    "b_quit": ("Quitter", "Quit"),
    # sidebar groups and tabs
    "nav_memories": ("Mémoires", "Memories"),
    "nav_settings": ("Réglages", "Settings"),
    "nav_signal": ("Signalisation", "Signalling"),
    "nav_advanced": ("Avancé", "Advanced"),
    "tab_channels": ("Canaux", "Channels"),
    "tab_options": ("Options", "Options"),
    "tab_dtmf": ("DTMF", "DTMF"),
    "tab_2tone": ("2-tone", "2-tone"),
    "tab_5tone": ("5-tone", "5-tone"),
    "tab_fm": ("FM", "FM"),
    "tab_calibration": ("Calibration", "Calibration"),
    "tab_password": ("Mot de passe", "Password"),
    "tab_memory": ("Mémoire", "Memory"),
    # status bar and panel
    "status_port": ("{port}", "{port}"),
    "status_ready": ("Prête", "Ready"),
    "status_session": ("Session ouverte", "Session open"),
    "status_busy": ("Session en cours", "Session running"),
    "status_emulator": ("radio simulée", "simulated radio"),
    "status_last_read": (
        "dernière lecture : {what}, {time}",
        "last read: {what}, {time}",
    ),
    "line_title": ("Ligne {name}", "Line {name}"),
    "line_title_freq": ("Ligne {name} ({freq} MHz)", "Line {name} ({freq} MHz)"),
    "not_read": ("non lue", "not read"),
    "status_no_port": ("aucun port", "no port"),
    "status_never_read": ("jamais lue", "never read"),
    "channels_count": ("{n} / {total} programmés", "{n} / {total} programmed"),
    "pending_title": ("À écrire", "To write"),
    "pending_none": ("Rien à écrire.", "Nothing to write."),
    "pending_hint": ("a : écrire en une session", "a: write in one session"),
    "pending_count": ("{n} zone(s) modifiée(s)", "{n} changed zone(s)"),
    "b_write_changes_n": ("Tout écrire ({n})", "Write all ({n})"),
    "pending_channel": ("Canal {n}", "Channel {n}"),
    "pending_never_read": (
        "{zone} : jamais lue, toute la zone sera écrite",
        "{zone}: never read, the whole zone will be written",
    ),
    "pending_unread": (
        "Jamais lues, à écrire en entier : {zones}",
        "Never read, written in full: {zones}",
    ),
    "pending_bytes": ("{zone} : {n} octet(s)", "{zone}: {n} byte(s)"),
    "pending_line": (
        "{item}, {field} : {old} -> {new}",
        "{item}, {field}: {old} -> {new}",
    ),
    # zones
    "zone_channels": ("Canaux", "Channels"),
    "zone_options": ("Options", "Options"),
    "zone_dtmf": ("DTMF", "DTMF"),
    "zone_twotone": ("2-tone", "2-tone"),
    "zone_fivetone": ("5-tone", "5-tone"),
    "zone_fm": ("FM", "FM"),
    "zone_calibration": ("Calibration", "Calibration"),
    "zone_password": ("Mot de passe", "Password"),
    "zone_all": ("toute la radio", "the whole radio"),
    # channel table columns (also used as field names in the changes panel)
    "col_n": ("N", "N"),
    "col_name": ("Nom", "Name"),
    "col_rx": ("RX MHz", "RX MHz"),
    "col_tx": ("TX MHz", "TX MHz"),
    "col_rxtone": ("Ton RX", "RX tone"),
    "col_txtone": ("Ton TX", "TX tone"),
    "col_power": ("Puiss.", "Power"),
    "col_mod": ("Mod.", "Mod."),
    "col_ptt": ("PTT-ID", "PTT-ID"),
    "col_bcl": ("BCL", "BCL"),
    "col_scan": ("Scan", "Scan"),
    "col_sig": ("Sig", "Sig"),
    "col_optsig": ("OptSig", "OptSig"),
    "col_mute": ("Mute", "Mute"),
    "col_scr": ("SCR", "SCR"),
    "col_changed": ("modifié", "changed"),
    "mod_wide": ("Large", "Wide"),
    "mod_narrow": ("Étroite", "Narrow"),
    "bytes_word": ("octets", "bytes"),
    "empty": ("(vide)", "(empty)"),
    # channel dialog
    "ch_title": (
        "Canal {n} (numéro affiché par la radio)",
        "Channel {n} (number shown by the radio)",
    ),
    "ch_aero": (
        "Recherche aéro (LFPX, PX, Paris, VOR...)",
        "Aero search (LFPX, PX, Paris, VOR...)",
    ),
    "ch_aero_pick": (
        "Fréquences (Espace pour cocher, plusieurs possibles)",
        "Frequencies (Space to tick, several allowed)",
    ),
    "ch_name": (
        "Nom (7 car. : 0-9 A-Z espace - + _)",
        "Name (7 chars: 0-9 A-Z space - + _)",
    ),
    "ch_rx": ("RX MHz (vide = canal supprimé)", "RX MHz (empty = channel deleted)"),
    "ch_tx": ("TX MHz", "TX MHz"),
    "ch_rxtone": ("Tonalité RX (CTCSS/DCS)", "RX tone (CTCSS/DCS)"),
    "moving": (
        "déplacement : flèches haut et bas, Espace ou Entrée pour déposer, Échap pour annuler",
        "moving: up and down arrows, Space or Enter to drop, Esc to cancel",
    ),
    "session_lost": (
        "session perdue ({exc}) : la prochaine lecture ou écriture refait un handshake",
        "session lost ({exc}): the next read or write starts a new handshake",
    ),
    "released": ("radio libérée : elle redémarre", "radio released: it restarts"),
    "release_busy": ("opération en cours, réessayer", "operation running, try again"),
    "ch_aero_count": (
        "{n} canaux seront créés : {a} à {b} (les suivants reculent si besoin)",
        "{n} channels will be created: {a} to {b} (the next ones move on if needed)",
    ),
    "insert_failed": ("rien n'est modifié : {exc}", "nothing changed: {exc}"),
    # calibration tables ("Adjust" screen)
    "cal_power_high": ("Puissance haute {band}", "High power {band}"),
    "cal_power_low": ("Puissance basse {band}", "Low power {band}"),
    "cal_sql_level": ("Squelch niveaux 0-9 {band}", "Squelch levels 0-9 {band}"),
    "cal_sql_freq": ("Squelch par fréquence {band}", "Squelch per frequency {band}"),
    "cal_am_sql_level": ("AM SQL niveaux 1-16", "AM SQL levels 1-16"),
    "cal_am_sql_freq": ("AM SQL par fréquence", "AM SQL per frequency"),
    "cal_rf_out_wide": (
        "Sortie RF large bande colonne {column}",
        "RF output wide band column {column}",
    ),
    "cal_rf_out_narrow": (
        "Sortie RF bande étroite colonne {column}",
        "RF output narrow band column {column}",
    ),
    "cal_pa": ("PA 108-138 MHz (pas de 2 MHz)", "PA 108-138 MHz (2 MHz steps)"),
    "cal_audio_wide": (
        "Audio large bande (MIC, voix, TONE, …)",
        "Audio wide band (MIC, voice, TONE, ...)",
    ),
    "cal_audio_narrow": (
        "Audio bande étroite (MIC, voix, TONE, …)",
        "Audio narrow band (MIC, voice, TONE, ...)",
    ),
    "cal_vox": ("Seuils VOX, niveaux 0-10", "VOX thresholds, levels 0-10"),
    "cal_limit_mode": (
        "Limites de fréquence : 0 TX and RX, 1 Only RX",
        "Frequency limits: 0 TX and RX, 1 Only RX",
    ),
    # pending changes
    "chg_empty": ("(vide)", "(empty)"),
    "chg_tx_off": ("TX désactivé", "TX disabled"),
    "chg_channel": ("canal", "channel"),
    "ch_tx_on": ("Émission (TX)", "Transmit (TX)"),
    "ch_txtone": ("Tonalité TX (CTCSS/DCS)", "TX tone (CTCSS/DCS)"),
    "ch_power": ("Puissance", "Power"),
    "ch_mod": ("Modulation", "Modulation"),
    "ch_bcl": ("Verrou d'occupation", "Busy lock"),
    "ch_scan": ("Balayage", "Scan"),
    "ch_scr": ("Brouilleur", "Scrambler"),
    "ch_sig": (
        "Code de signalisation (vide ou 1-15)",
        "Signalling code (empty or 1-15)",
    ),
    "ch_ptt": ("PTT-ID", "PTT-ID"),
    "ch_bandwarn": (
        "Hors des bandes de la radio : vérifier",
        "Outside the radio bands: check it",
    ),
    "ch_bandok": ("bande {low} à {high} MHz", "band {low} to {high} MHz"),
    "ch_hz_mhz": ("MHz", "MHz"),
    # buttons and dialogs
    "btn_ok": ("OK", "OK"),
    "btn_cancel": ("Annuler", "Cancel"),
    "btn_apply": ("Appliquer", "Apply"),
    "btn_confirm": ("Confirmer", "Confirm"),
    "btn_write": ("Écrire", "Write"),
    "btn_apply_image": ("Appliquer à l'image", "Apply to image"),
    "btn_cal_tables": (
        "Tables standard du CPS (0x2000..0x23EF)",
        "CPS standard tables (0x2000..0x23EF)",
    ),
    "confirm_type": ("tapez {word}", "type {word}"),
    "confirm_wrong": ("mot de confirmation incorrect", "wrong confirmation word"),
    "yes_no": (
        "Oui ou non, ou un mot à taper pour les opérations dangereuses.",
        "Yes or no, or a word to type for dangerous operations.",
    ),
    "path_open": (
        "Ouvrir (.img brut, .dat ou .adj du CPS)",
        "Open (.img raw, CPS .dat or .adj)",
    ),
    "path_save": (
        "Enregistrer (.img brut, .dat ou .adj du CPS)",
        "Save (.img raw, CPS .dat or .adj)",
    ),
    # messages
    "invalid_input": ("saisie invalide : {exc}", "invalid input: {exc}"),
    "not_a_frequency": ("pas une fréquence : {text}", "not a frequency: {text}"),
    "open_failed": ("ouverture impossible : {exc}", "cannot open: {exc}"),
    "save_failed": ("enregistrement impossible : {exc}", "cannot save: {exc}"),
    "opened": ("fichier {path} ouvert", "file {path} opened"),
    "saved": ("image enregistrée dans {path}", "image saved to {path}"),
    "no_port": (
        "aucun port : choisir un adaptateur ou lancer avec --port /dev/ttyUSB0",
        "no port: pick an adapter or start with --port /dev/ttyUSB0",
    ),
    "port_title": (
        "Adaptateur USB-série de la radio (Entrée = choisir, Échap = sans port)",
        "Radio USB-serial adapter (Enter = pick, Esc = no port)",
    ),
    "port_recommended": ("recommandé", "recommended"),
    "restart_wait": (
        (
            "La radio redémarre à la fin d'une session. Passez son écran "
            "d'avertissement (Exit 3 fois) jusqu'à l'écran normal, puis OK."
        ),
        (
            "The radio restarts when a session ends. Go past its warning screen "
            "(Exit 3 times) to the normal screen, then OK."
        ),
    ),
    "restart_cancelled": (
        "annulé : rien n'a été envoyé",
        "cancelled: nothing was sent",
    ),
    "radio_hint": (
        "Si la radio a redémarré, passer son écran d'avertissement (3 x Exit) puis relancer",
        "If the radio restarted, go past its warning screen (3 x Exit), then retry",
    ),
    "read_failed": ("lecture échouée : {exc}. {hint}", "read failed: {exc}. {hint}"),
    "write_failed": ("écriture échouée : {exc}. {hint}", "write failed: {exc}. {hint}"),
    "reading": ("lecture {zone}…", "reading {zone}…"),
    "read_done": ("lecture {zone} terminée", "{zone} read"),
    "write_done": (
        "écriture {zone} terminée : la radio redémarre (écran d'avertissement : Exit 3 fois)",
        "{zone} written: the radio restarts (warning screen: Exit 3 times)",
    ),
    "radio_ident": ("radio : {a} {b} bandes {bands}", "radio: {a} {b} bands {bands}"),
    "write_confirm": (
        "Écrire la zone « {zone} » dans la radio ? Une copie de l'image est faite avant.",
        "Write the zone « {zone} » to the radio? A copy of the image is made first.",
    ),
    "write_changes_confirm": (
        "Écrire en une seule session (un redémarrage) : {names} ? Une copie de l'image est faite avant.",
        "Write in one session (one restart): {names}? A copy of the image is made first.",
    ),
    "write_nothing": (
        "aucune zone modifiée depuis la dernière lecture ou écriture",
        "no zone changed since the last read or write",
    ),
    "backup_writing": (
        "copie {path} ; écriture {names}…",
        "copy {path}; writing {names}…",
    ),
    "cal_word_title": ("Écriture de la calibration", "Calibration write"),
    "default_none": (
        "pas de valeurs « Default » du CPS mesurées pour {zone}",
        "no CPS « Default » values measured for {zone}",
    ),
    "default_done": (
        "valeurs « Default » du CPS mises dans l'image ({zone})",
        "CPS « Default » values put in the image ({zone})",
    ),
    "default_confirm": (
        "Remplacer la zone {zone} de l'image par les valeurs « Default » du CPS ?",
        "Replace the zone {zone} of the image with the CPS « Default » values?",
    ),
    "clear_only": (
        "« Effacer » n'existe que pour les canaux et la FM",
        "« Clear » only exists for channels and FM",
    ),
    "clear_done": (
        "zone {zone} effacée dans l'image",
        "zone {zone} cleared in the image",
    ),
    "clear_confirm": ("Effacer la zone {zone} ?", "Clear the zone {zone}?"),
    "quit_confirm": (
        "Modifications ni écrites dans la radio ni enregistrées : quitter quand même ?",
        "Changes neither written to the radio nor saved: quit anyway?",
    ),
    "dtmf_applied": ("DTMF appliqué à l'image", "DTMF applied to the image"),
    "pw_applied": (
        "mots de passe appliqués à l'image (écrire l'onglet pour envoyer)",
        "passwords applied to the image (write the tab to send them)",
    ),
    "tables_copied": (
        "tables 5-tone standard copiées dans l'image",
        "standard 5-tone tables copied into the image",
    ),
    "cal_refused": (
        "calibration ou mots de passe : passer par leurs onglets",
        "calibration or passwords: use their tabs",
    ),
    "poke_out": ("adresse hors image", "address outside the image"),
    "theme_changed": ("thème : {name}", "theme: {name}"),
    # command line
    "vfo_freq": ("fréquence (MHz, 999.99999)", "frequency (MHz, 999.99999)"),
    "vfo_offset": ("offset (MHz, 999.999)", "offset (MHz, 999.999)"),
    "vfo_rx": ("tonalité RX (OFF, 88.5, D023N)", "RX tone (OFF, 88.5, D023N)"),
    "vfo_tx": ("tonalité TX (OFF, 88.5, D023N)", "TX tone (OFF, 88.5, D023N)"),
    "rights": ("Droits", "Rights"),
    "help_2tone": (
        "enc n F1 F2 | enc n - | tones n A B C D (- = vide) | dur ms1 ms2 gap | reset ms (100..8000) | dec n P R A P R A P R A P R A (R = 0..3)",
        "enc n F1 F2 | enc n - | tones n A B C D (- = empty) | dur ms1 ms2 gap | reset ms (100..8000) | dec n P R A P R A P R A P R A (R = 0..3)",
    ),
    "help_5tone": (
        "tone s i Hz (s 0-14, i 0-15) | std s période groupe répétition | enc n T1 T2 T3 STANDARD (- = trame vide) | delays d1 d2 d3 ext (ms) | dec STANDARD appel affichage reset_ms (ex. dec CCIR1 1 23 6000)",
        "tone s i Hz (s 0-14, i 0-15) | std s period group repeat | enc n T1 T2 T3 STANDARD (- = empty frame) | delays d1 d2 d3 ext (ms) | dec STANDARD call display reset_ms (e.g. dec CCIR1 1 23 6000)",
    ),
    "help_fm": (
        "Modification : « n MHz nom », ex. 3 98.3 FJQX ; « n - » efface",
        "Edit: « n MHz name », e.g. 3 98.3 FJQX ; « n - » clears",
    ),
    "help_cal": (
        "Modification : « clé index valeur », ex. power_high_1 0 12. Écriture radio : mot CALIBRATION exigé.",
        "Edit: « key index value », e.g. power_high_1 0 12. Writing to the radio requires the word CALIBRATION.",
    ),
    "pw1_label": (
        "Mot de passe 1 (6 chiffres, vide = aucun)",
        "Password 1 (6 digits, empty = none)",
    ),
    "pw2_label": (
        "Mot de passe 2 (6 chiffres, vide = aucun)",
        "Password 2 (6 digits, empty = none)",
    ),
    "poke_placeholder": (
        "adresse=octets hex, ex. 2a00=01 02 0a",
        "address=hex bytes, e.g. 2a00=01 02 0a",
    ),
    "btn_dtmf_apply": ("Appliquer à l'image", "Apply to image"),
    "col_key": ("clé", "key"),
    "col_address": ("adresse", "address"),
    "col_row": ("ligne", "row"),
    "col_content": ("contenu", "content"),
    "limits": ("Limites", "Limits"),
    "tt_decode": (
        "décodage (paire réponse alerte) x4",
        "decoding (pair, response, alert) x4",
    ),
    "tt_tones": ("tons A B C D", "tones A B C D"),
    "decoding": ("décodage", "decoding"),
    "durations": ("durées", "durations"),
    "reset_octet": ("{ms} ms (octet {raw})", "{ms} ms (byte {raw})"),
    "fivetone_decode": (
        "{std} appel {call} affichage {disp} reset {reset} ms",
        "{std} call {call} display {disp} reset {reset} ms",
    ),
    "delays_ms": ("délais ms", "delays (ms)"),
    "dtmf_one_char": (
        "{key} : un seul caractère DTMF attendu",
        "{key}: one DTMF character expected",
    ),
    "dtmf_ms": ("{label} : nombre de ms attendu", "{label}: number of ms expected"),
    "unknown_command": ("commande inconnue", "unknown command"),
    "cli_desc": ("Programmation QYT KT-A16", "Programming of the QYT KT-A16"),
    "cli_port": ("port série, ex. /dev/ttyUSB0", "serial port, e.g. /dev/ttyUSB0"),
    "cli_emulator": (
        "radio simulée (démonstration, aucun port ouvert)",
        "simulated radio (demo, no port opened)",
    ),
    "cli_image": ("image à ouvrir au démarrage", "image to open at start"),
    "cli_lang": ("langue de l'interface : fr ou en", "interface language: fr or en"),
}

MESSAGES = {
    "fr": {key: fr for key, (fr, _) in _TEXTS.items()},
    "en": {key: en for key, (_, en) in _TEXTS.items()},
}

_language = "fr"


def detect(env=None):
    """French if the first locale variable set starts with "fr", else English."""
    env = os.environ if env is None else env
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = env.get(name, "")
        if value:
            return "fr" if value.lower().startswith("fr") else "en"
    return "en"


def set_language(lang):
    global _language
    if lang not in LANGUAGES:
        raise ValueError(f"language must be one of {LANGUAGES}")
    _language = lang


def language():
    return _language


# Service words of the SIA descriptions of kta16/aero.json (aerodrome names stay as they are)
_AERO_WORDS = {
    "Approche": "Approach", "Gonio": "Direction finding", "Tour": "Tower",
    "Sol": "Ground", "Prevol": "Pre-flight", "Trafic": "Traffic",
    "Controle": "Control", "Precision": "Precision",
}  # fmt: skip


def aero_desc(text):
    """Description of an aeronautical line in the current language."""
    if _language == "fr":
        return text
    return " ".join(_AERO_WORDS.get(word, word) for word in text.split(" "))


def t(key, **values):
    """Text for `key` in the current language, with {name} fields filled."""
    return MESSAGES[_language][key].format(**values)
