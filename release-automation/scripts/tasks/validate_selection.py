def run_in_dai(releaseVariables, configurationApi):

    log_section("Validation de la Selection")

    components   = json_load_var(releaseVariables, "componentsJson",   [])
    environments = json_load_var(releaseVariables, "environmentsJson", [])

    comp_name = get_var(releaseVariables, "componentName", "").strip()
    env_csv   = get_var(releaseVariables, "targetEnvironmentsCsv", "").strip()
    image_tag = get_var(releaseVariables, "imageTag", "").strip()

    errors   = []
    warnings = []

    # Valider image tag
    if not image_tag:
        errors.append("imageTag est vide")
    elif image_tag == "latest":
        warnings.append("Tag 'latest' non recommande en prod")

    # Valider composant
    component = None
    comp_names = [c.get("name") for c in components]
    for c in components:
        if c.get("name") == comp_name:
            component = c
            break
    if not component:
        errors.append(
            "Composant '%s' invalide. Disponibles: %s" % (
                comp_name, comp_names
            )
        )

    # Valider environnements
    target_envs       = [x.strip() for x in env_csv.split(",") if x.strip()]
    valid_env_names   = [e.get("name") for e in environments]
    selected_env_cfgs = []

    if not target_envs:
        errors.append("Aucun environnement selectionne")

    for env in target_envs:
        if env not in valid_env_names:
            errors.append(
                "Env '%s' invalide. Disponibles: %s" % (
                    env, valid_env_names
                )
            )
        else:
            for e in environments:
                if e.get("name") == env:
                    selected_env_cfgs.append(e)
                    break

    # Bloquer latest sur prod
    prod_envs     = ["prod", "production", "dr"]
    selected_prod = [e for e in target_envs if e in prod_envs]
    if selected_prod and image_tag == "latest":
        errors.append(
            "Interdit de deployer 'latest' sur: %s" % selected_prod
        )

    # Valider que argocdServerVariable existe pour chaque env
    for ec in selected_env_cfgs:
        var_name = ec.get("argocdServerVariable")
        if not var_name:
            errors.append(
                "argocdServerVariable manquant pour env '%s' "
                "dans environments.yaml" % ec.get("name")
            )
        else:
            val = releaseVariables.get(var_name)
            if val is None:
                errors.append(
                    "Variable de folder '%s' introuvable "
                    "(requise pour env '%s')" % (
                        var_name, ec.get("name")
                    )
                )

    for w in warnings:
        log_warn(w)

    if errors:
        for e in errors:
            log_error(e)
        raise Exception(
            "Validation echouee:\n%s" % "\n".join(errors)
        )

    # Trier par ordre de deploiement
    selected_env_cfgs.sort(
        key=lambda x: x.get("deploymentOrder", 99)
    )

    # Approval requise ?
    needs_approval = any(
        e.get("approvalRequired") for e in selected_env_cfgs
    )
    approval_envs = [
        e.get("name") for e in selected_env_cfgs
        if e.get("approvalRequired")
    ]

    log_ok("Validation reussie")
    log_info("  Composant : %s" % comp_name)
    log_info("  Envs      : %s" % target_envs)
    log_info("  Tag       : %s" % image_tag)
    log_info("  Approval  : %s" % needs_approval)

    return {
        "componentConfigJson":    component,
        "targetEnvironmentsJson": target_envs,
        "selectedEnvConfigsJson": selected_env_cfgs,
        "needsApproval":          "true" if needs_approval else "false",
        "approvalEnvsJson":       approval_envs
    }