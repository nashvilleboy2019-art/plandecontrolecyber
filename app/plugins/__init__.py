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
    "attestations_smsi": {
        "slug":         "attestations_smsi",
        "name":         "Attestations sur l'honneur – SMSI",
        "short":        "DSO-ATT-01",
        "description":  "Vérifie la présence et la validité des attestations pour les rôles de confiance SMSI (source : BaseLIR).",
        "icon":         _SHIELD_ICON,
        "family":       "Attestations",
        "family_tag":   "ATT",
        "form_template":   "plugins/attestations_smsi/form.html",
        "result_template": "plugins/attestations_smsi/resultats.html",
        "module":          "app.plugins.attestations_smsi",
    },
    "sensibilisations_smsi": {
        "slug":         "sensibilisations_smsi",
        "name":         "Sensibilisations sécurité – SMSI",
        "short":        "DSO-ATT-02",
        "description":  "Vérifie la présence et la validité annuelle des sensibilisations à la sécurité des SI pour les prestataires (source : BaseLIR).",
        "icon":         _SHIELD_ICON,
        "family":       "Attestations",
        "family_tag":   "ATT",
        "form_template":   "plugins/sensibilisations_smsi/form.html",
        "result_template": "plugins/sensibilisations_smsi/resultats.html",
        "module":          "app.plugins.sensibilisations_smsi",
    },
    "acces_basesecrets": {
        "slug":         "acces_basesecrets",
        "name":         "Accès Base des Secrets",
        "short":        "DSO-LOG-24",
        "description":  "Vérifie que les logs de connexion BaseSECRETS ne contiennent que des utilisateurs enregistrés (liste locale autorisée).",
        "icon":         "M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z",
        "family":       "Revue Acces",
        "family_tag":   "LOG",
        "form_template":   "plugins/acces_basesecrets/form.html",
        "result_template": "plugins/acces_basesecrets/resultats.html",
        "module":          "app.plugins.acces_basesecrets",
    },
    "revue_droits_bastion_eidas": {
        "slug":         "revue_droits_bastion_eidas",
        "name":         "Revue Droits Opérateurs – BASTION eIDAS",
        "short":        "DSO-LOG-19",
        "description":  "Croise l'export CSV de la console BASTION eIDAS avec BaseLIR pour vérifier la conformité des accès selon la matrice des autorisations.",
        "icon":         _SHIELD_ICON,
        "family":       "Revue Acces",
        "family_tag":   "LOG",
        "form_template":   "plugins/revue_droits_bastion_eidas/form.html",
        "result_template": "plugins/revue_droits_bastion_eidas/resultats.html",
        "module":          "app.plugins.revue_droits_bastion_eidas",
    },
    "revue_droits_sacre": {
        "slug":         "revue_droits_sacre",
        "name":         "Revue Droits Opérateurs – SACRE",
        "short":        "DSO-LOG-03-02",
        "description":  "Contrôle automatisé SACRE. Vérifie les fonctions sensibles vs la LIR.",
        "icon":         _SHIELD_ICON,
        "family":       "Revue Acces",
        "family_tag":   "LOG",
        "form_template":   "plugins/revue_droits_sacre/form.html",
        "result_template": "plugins/revue_droits_operateurs/resultats.html",
        "module":          "app.plugins.revue_droits_sacre",
    },
    "revue_droits_pki": {
        "slug":         "revue_droits_pki",
        "name":         "Revue Droits Opérateurs – PKI",
        "short":        "DSO-LOG-03-03",
        "description":  "Contrôle automatisé PKI. Vérifie les groupes PKI vs la LIR.",
        "icon":         _SHIELD_ICON,
        "family":       "Revue Acces",
        "family_tag":   "LOG",
        "form_template":   "plugins/revue_droits_pki/form.html",
        "result_template": "plugins/revue_droits_operateurs/resultats.html",
        "module":          "app.plugins.revue_droits_pki",
    },
    "revue_droits_kstamp": {
        "slug":         "revue_droits_kstamp",
        "name":         "Revue Droits Opérateurs – KSTAMP",
        "short":        "DSO-LOG-03-01",
        "description":  "Contrôle automatisé KSTAMP (MRS1 / MRS2 / CLY). Vérifie les profils vs la LIR.",
        "icon":         _SHIELD_ICON,
        "family":       "Revue Acces",
        "family_tag":   "LOG",
        "form_template":   "plugins/revue_droits_kstamp/form.html",
        "result_template": "plugins/revue_droits_operateurs/resultats.html",
        "module":          "app.plugins.revue_droits_kstamp",
    },
    "revue_droits_bastion_sin": {
        "slug":         "revue_droits_bastion_sin",
        "name":         "Revue Droits Opérateurs – BASTION SIN",
        "short":        "DSO-LOG-20",
        "description":  "Croise l'export CSV de la console BASTION SI Notaire avec BaseLIR pour vérifier la conformité des accès selon la matrice des autorisations.",
        "icon":         _SHIELD_ICON,
        "family":       "Revue Acces",
        "family_tag":   "LOG",
        "form_template":   "plugins/revue_droits_bastion_sin/form.html",
        "result_template": "plugins/revue_droits_bastion_sin/resultats.html",
        "module":          "app.plugins.revue_droits_bastion_sin",
    },
}


def get_plugin(slug: str) -> dict | None:
    return PLUGIN_REGISTRY.get(slug)


def all_plugins() -> list[dict]:
    return list(PLUGIN_REGISTRY.values())
