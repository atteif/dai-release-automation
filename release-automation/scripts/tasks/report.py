def run_in_dai(releaseVariables, configurationApi):

    log_section("Rapport de Deploiement")

    component   = json_load_var(releaseVariables, "componentConfigJson", {})
    target_envs = json_load_var(releaseVariables, "targetEnvironmentsJson", [])
    deploy_res  = json_load_var(releaseVariables, "argocdDeployResultsJson", [])
    wait_res    = json_load_var(releaseVariables, "waitResultsJson",  [])
    image_tag   = get_var(releaseVariables, "imageTag",      "N/A")
    release_id  = get_var(releaseVariables, "releaseId",     "N/A")
    owner       = get_var(releaseVariables, "releaseOwner",  "N/A")
    mr_url      = get_var(releaseVariables, "mergeRequestUrl", "N/A")
    all_healthy = get_var(releaseVariables, "allHealthy", "false")

    comp_name = component.get("name", "N/A")

    deploy_map = {}
    for r in deploy_res:
        deploy_map[r.get("env", "")] = r

    wait_map = {}
    for r in wait_res:
        wait_map[r.get("env", "")] = r

    lines = []
    lines.append("=" * 65)
    lines.append("  RAPPORT DE DEPLOIEMENT")
    lines.append("=" * 65)
    lines.append("")
    lines.append("  Composant   : %s (%s)" % (
        component.get("displayName", comp_name), comp_name
    ))
    lines.append("  Version     : %s" % image_tag)
    lines.append("  Deploye par : %s" % owner)
    lines.append("  Release ID  : %s" % release_id)
    lines.append("  MR GitLab   : %s" % mr_url)
    lines.append("")
    lines.append("-" * 65)
    lines.append("%-12s %-4s %-12s %-12s %-12s" % (
        "Env", "", "Action", "Sync", "Health"
    ))
    lines.append("-" * 65)

    overall_ok = True
    for env in target_envs:
        d = deploy_map.get(env, {})
        w = wait_map.get(env, {})

        action  = d.get("action", "unknown")
        sync    = w.get("sync",   "N/A")
        health  = w.get("health", "N/A")
        success = w.get("success", False)
        error   = w.get("error",  d.get("error", ""))

        if action == "dry_run":
            icon = "?"
        elif action == "error" or not success:
            icon = "X"
            overall_ok = False
        else:
            icon = "v"

        lines.append("[%s] %-12s %-12s %-12s %-12s" % (
            icon, env, action, sync, health
        ))
        if error:
            lines.append("    -> %s" % error)

    lines.append("-" * 65)
    lines.append("")

    if overall_ok:
        lines.append("  RESULTAT : DEPLOIEMENT REUSSI")
    else:
        lines.append("  RESULTAT : DEPLOIEMENT EN ECHEC")

    lines.append("")
    lines.append("=" * 65)

    report = "\n".join(lines)
    print(report)

    return {
        "deploymentReport": report,
        "overallSuccess":   "true" if overall_ok else "false"
    }