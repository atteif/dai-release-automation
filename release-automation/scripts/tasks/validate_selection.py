# =============================================================
# validate_selection.py
# Valide les choix de l'utilisateur
# =============================================================

def run_in_dai(releaseVariables, configurationApi):

    log_section("Validation de la Selection")

    components = json_load_var(releaseVariables, "componentsJson", [])
    environments = json_load_var(releaseVariables, "environmentsJson", [])

    component_name = get_var(releaseVariables, "componentName", "").strip()
    env_csv = get_var(releaseVariables, "targetEnvironmentsCsv", "").strip()
    image_tag = get_var(releaseVariables, "imageTag", "").strip()

    errors = []
    warnings = []

    # --- Valider le tag ---
    if not image_tag:
        errors.append("imageTag est vide")
    elif image_tag == "latest":
        warnings.append("Tag 'latest' non recommande en production")

    # --- Valider le composant ---
    component = None
    component_names = [c.get("name") for c in components]
    for c in components:
        if c.get("name") == component_name:
            component = c
            break

    if not component:
        errors.append(
            "Composant '%s' invalide. Disponibles: %s" % (
                component_name, component_names
            )
        )

    # --- Valider les environnements ---
    target_envs = [x.strip() for x in env_csv.split(",") if x.strip()]
    if not target_envs:
        errors.append("Aucun environnement selectionne")

    valid_env_names = [e.get("name") for e in environments]
    selected_env_configs = []

    for env in target_envs:
        if env not in valid_env_names:
            errors.append(
                "Environnement '%s' invalide. Disponibles: %s" % (
                    env, valid_env_names
                )
            )
        else:
            for e in environments:
                if e.get("name") == env:
                    selected_env_configs.append(e)
                    break

    # --- Bloquer latest sur prod ---
    prod_envs = ["prod", "production", "dr"]
    selected_prod = [e for e in target_envs if e in prod_envs]
    if selected_prod and image_tag == "latest":
        errors.append(
            "Interdit de deployer 'latest' sur: %s" % selected_prod
        )

    # --- Afficher warnings ---
    for w in warnings:
        log_warn(w)

    # --- Stopper si erreurs ---
    if errors:
        for err in errors:
            log_error(err)
        raise Exception(
            "Validation echouee:\n%s" % "\n".join(errors)
        )

    # --- Trier envs par ordre de deploiement ---
    def get_order(env_cfg):
        return env_cfg.get("deploymentOrder", 99)

    selected_env_configs.sort(key=get_order)

    # --- Calculer si approval requise ---
    needs_approval = any(
        e.get("approvalRequired", False) for e in selected_env_configs
    )
    approval_envs = [
        e.get("name") for e in selected_env_configs
        if e.get("approvalRequired", False)
    ]

    log_ok("Validation reussie:")
    log_info("  Composant   : %s" % component_name)
    log_info("  Envs        : %s" % target_envs)
    log_info("  Image Tag   : %s" % image_tag)
    log_info("  Approval    : %s" % needs_approval)

    return {
        "componentConfigJson": component,
        "targetEnvironmentsJson": target_envs,
        "selectedEnvConfigsJson": selected_env_configs,
        "needsApproval": "true" if needs_approval else "false",
        "approvalEnvsJson": approval_envs,
        "validationWarnings": "\n".join(warnings) if warnings else ""
    }