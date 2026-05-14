"""
Registre des plugins d'automatisation de contrôle.
Chaque plugin est identifié par un slug unique et expose son interface via son module.
"""

_SHIELD_ICON = (
    "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01"
    "-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 "
    "9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
)

PLUGIN_REGISTRY: dict[str, dict] = {
    "revue_droits_sacre": {
        "slug":         "revue_droits_sacre",
        "name":         "Revue Droits Opérateurs – SACRE",
        "short":        "DSO-LOG-03-01",
        "description":  "Contrôle automatisé SACRE. Vérifie les fonctions sensibles vs la LIR.",
        "icon":         _SHIELD_ICON,
        "family":       "Revue des droits opérateurs",
        "family_tag":   "LOG",
        "form_template":   "plugins/revue_droits_sacre/form.html",
        "result_template": "plugins/revue_droits_operateurs/resultats.html",
        "module":          "app.plugins.revue_droits_sacre",
    },
    "revue_droits_pki": {
        "slug":         "revue_droits_pki",
        "name":         "Revue Droits Opérateurs – PKI",
        "short":        "DSO-LOG-03-02",
        "description":  "Contrôle automatisé PKI. Vérifie les groupes PKI vs la LIR.",
        "icon":         _SHIELD_ICON,
        "family":       "Revue des droits opérateurs",
        "family_tag":   "LOG",
        "form_template":   "plugins/revue_droits_pki/form.html",
        "result_template": "plugins/revue_droits_operateurs/resultats.html",
        "module":          "app.plugins.revue_droits_pki",
    },
    "revue_droits_kstamp": {
        "slug":         "revue_droits_kstamp",
        "name":         "Revue Droits Opérateurs – KSTAMP",
        "short":        "DSO-LOG-03-03",
        "description":  "Contrôle automatisé KSTAMP (MRS1 / MRS2 / CLY). Vérifie les profils vs la LIR.",
        "icon":         _SHIELD_ICON,
        "family":       "Revue des droits opérateurs",
        "family_tag":   "LOG",
        "form_template":   "plugins/revue_droits_kstamp/form.html",
        "result_template": "plugins/revue_droits_operateurs/resultats.html",
        "module":          "app.plugins.revue_droits_kstamp",
    },
}


def get_plugin(slug: str) -> dict | None:
    return PLUGIN_REGISTRY.get(slug)


def all_plugins() -> list[dict]:
    return list(PLUGIN_REGISTRY.values())
