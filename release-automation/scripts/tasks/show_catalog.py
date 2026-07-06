# =============================================================
# show_catalog.py
# Charge et affiche le catalogue des composants et environnements
# =============================================================

def run_in_dai(releaseVariables, configurationApi):

    log_section("Chargement du Catalogue")

    # --- Parser les YAML ---
    components_data = yaml_load(releaseVariables["componentsYaml"])
    envs_data = yaml_load(releaseVariables["environmentsYaml"])

    components = components_data.get("components", [])
    environments = envs_data.get("environments", [])

    if not components:
        raise Exception("Aucun composant trouve dans components.yaml")
    if not environments:
        raise Exception("Aucun environnement trouve dans environments.yaml")

    # --- Afficher les composants ---
    log_info("Composants disponibles:")
    components_text = ""
    for c in components:
        line = "  - %-20s | %s" % (
            c.get("name", ""),
            c.get("description", "")
        )
        log_info(line)
        components_text += "%-20s | %s\n" % (
            c.get("name", ""),
            c.get("description", "")
        )

    # --- Afficher les environnements ---
    log_info("")
    log_info("Environnements disponibles:")
    envs_text = ""
    for e in environments:
        approval = "Approval requis" if e.get(
            "approvalRequired", False
        ) else "Auto"
        auto_sync = "AutoSync" if e.get("autoSync", False) else "Manuel"
        line = "  - %-10s | %-10s | %-20s | %s" % (
            e.get("name", ""),
            e.get("displayName", ""),
            auto_sync,
            approval
        )
        log_info(line)
        envs_text += "%-10s | %-10s | %-20s | %s\n" % (
            e.get("name", ""),
            e.get("displayName", ""),
            auto_sync,
            approval
        )

    log_ok("Catalogue charge avec succes")

    return {
        "availableComponentsText": components_text,
        "availableEnvironmentsText": envs_text,
        "componentsJson": components,
        "environmentsJson": environments
    }