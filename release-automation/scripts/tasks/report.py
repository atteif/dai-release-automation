# =============================================================
# report.py
# Genere le rapport final de deploiement
# =============================================================

def run_in_dai(releaseVariables, configurationApi):

    log_section("Rapport de Deploiement")

    component = json_load_var(
        releaseVariables, "componentConfigJson", {}
    )
    target_envs = json_load_var(
        releaseVariables, "targetEnvironmentsJson", []
    )
    deploy_results = json_load_var(
        releaseVariables, "argocdDeployResultsJson", []
    )
    wait_results = json_load_var(
        releaseVariables, "waitResultsJson", []
    )

    image_tag = get_var(releaseVariables, "imageTag", "N/A")
    release_id = get_var(releaseVariables, "releaseId", "N/A")
    release_owner = get_var(releaseVariables, "releaseOwner", "N/A")
    mr_url = get_var(releaseVariables, "mergeRequestUrl", "N/A")
    gitops_tag = get_var(releaseVariables, "gitopsTag", "N/A")
    all_healthy = get_var(releaseVariables, "allHealthy", "false")

    component_name = component.get("name", "N/A")

    # --- Construire maps de resultats ---
    deploy_map = {}
    for r in deploy_results:
        deploy_map[r.get("env", "")] = r

    wait_map = {}
    for r in wait_results:
        wait_map[r.get("env", "")] = r

    # --- Construire le rapport ---
    lines = []
    lines.append("=" * 65)
    lines.append("  RAPPORT DE DEPLOIEMENT")
    lines.append("=" * 65)
    lines.append("")
    lines.append("  Composant   : %s (%s)" % (
        component.get("displayName", component_name), component_name
    ))
    lines.append("  Version     : %s" % image_tag)
    lines.append("  Deploye par : %s" % release_owner)
    lines.append("  Release ID  : %s" % release_id)
    lines.append("  MR GitLab   : %s" % mr_url)
    lines.append("  Git Tag     : %s" % gitops_tag)
    lines.append("")
    lines.append("-" * 65)
    lines.append(
        "%-12s %-10s %-12s %-12s %-14s" % (
            "Env", "Action", "Sync", "Health", "Statut"
        )
    )
    lines.append("-" * 65)

    overall_ok = True
    for env in target_envs:
        d = deploy_map.get(env, {})
        w = wait_map.get(env, {})

        action = d.get("action", "unknown")
        sync = w.get("sync", "N/A")
        health = w.get("health", "N/A")
        success = w.get("success", False)
        error = w.get("error", d.get("error", ""))

        if action == "dry_run":
            status = "DRY_RUN"
            icon = "?"
        elif action == "error":
            status = "ERREUR"
            icon = "X"
            overall_ok = False
        elif success:
            status = "OK"
            icon = "v"
        else:
            status = "ECHOUE"
            icon = "X"
            overall_ok = False

        line = "[%s] %-12s %-10s %-12s %-12s %-14s" % (
            icon, env, action, sync, health, status
        )
        lines.append(line)

        if error:
            lines.append("    -> Erreur: %s" % error)

    lines.append("-" * 65)
    lines.append("")

    if overall_ok:
        lines.append("  RESULTAT: DEPLOIEMENT REUSSI !")
    else:
        lines.append("  RESULTAT: DEPLOIEMENT EN ECHEC - Action requise!")

    lines.append("")
    lines.append("  ArgoCD Links:")
    for env in target_envs:
        d = deploy_map.get(env, {})
        argocd_server = d.get("argocd_server", "")
        app_name = "%s-%s" % (component_name, env)
        lines.append("  %s -> ArgoCD: %s/applications/%s" % (
            env, argocd_server, app_name
        ))

    lines.append("")
    lines.append("=" * 65)

    report_text = "\n".join(lines)
    print(report_text)

    return {
        "deploymentReport": report_text,
        "overallSuccess": "true" if overall_ok else "false"
    }