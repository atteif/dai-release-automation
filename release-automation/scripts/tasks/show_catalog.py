def run_in_dai(releaseVariables, configurationApi):

    log_section("Chargement du Catalogue")

    components_data = yaml_load(releaseVariables["componentsYaml"])
    envs_data       = yaml_load(releaseVariables["environmentsYaml"])

    components   = components_data.get("components",   [])
    environments = envs_data.get("environments", [])

    if not components:
        raise Exception("Aucun composant dans components.yaml")
    if not environments:
        raise Exception("Aucun environnement dans environments.yaml")

    comp_text = ""
    for c in components:
        line = "%-20s | %s" % (c.get("name",""), c.get("description",""))
        log_info("  %s" % line)
        comp_text += "%s\n" % line

    log_info("")

    env_text = ""
    for e in environments:
        approval  = "Approval" if e.get("approvalRequired") else "Auto"
        auto_sync = "AutoSync" if e.get("autoSync")         else "Manuel"
        line = "%-10s | %-12s | %-10s | %s" % (
            e.get("name",""), e.get("displayName",""),
            auto_sync, approval
        )
        log_info("  %s" % line)
        env_text += "%s\n" % line

    log_ok("Catalogue charge")

    return {
        "availableComponentsText":    comp_text,
        "availableEnvironmentsText":  env_text,
        "componentsJson":             components,
        "environmentsJson":           environments
    }