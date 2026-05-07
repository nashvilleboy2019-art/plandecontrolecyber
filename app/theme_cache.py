_cache = {}

PALETTES = {
    "indigo":  {"primary": "indigo",  "hex": "#4f46e5", "dark": "#3730a3"},
    "blue":    {"primary": "blue",    "hex": "#2563eb", "dark": "#1d4ed8"},
    "teal":    {"primary": "teal",    "hex": "#0d9488", "dark": "#0f766e"},
    "emerald": {"primary": "emerald", "hex": "#059669", "dark": "#047857"},
    "sky":     {"primary": "sky",     "hex": "#0284c7", "dark": "#0369a1"},
    "purple":  {"primary": "purple",  "hex": "#7c3aed", "dark": "#6d28d9"},
    "rose":    {"primary": "rose",    "hex": "#e11d48", "dark": "#be123c"},
    "orange":  {"primary": "orange",  "hex": "#ea580c", "dark": "#c2410c"},
    "amber":   {"primary": "amber",   "hex": "#d97706", "dark": "#b45309"},
    "slate":   {"primary": "slate",   "hex": "#475569", "dark": "#334155"},
    "pink":    {"primary": "pink",    "hex": "#db2777", "dark": "#be185d"},
}

DEFAULT_PRIMARY = "indigo"
DEFAULT_SECONDARY = "slate"


def set_theme(primary: str, secondary: str):
    _cache["primary"] = primary
    _cache["secondary"] = secondary


def get_theme():
    p = _cache.get("primary", DEFAULT_PRIMARY)
    s = _cache.get("secondary", DEFAULT_SECONDARY)
    return {
        "primary": p,
        "secondary": s,
        "primary_hex": PALETTES.get(p, PALETTES[DEFAULT_PRIMARY])["hex"],
        "primary_dark": PALETTES.get(p, PALETTES[DEFAULT_PRIMARY])["dark"],
        "palettes": list(PALETTES.keys()),
    }
