def run_in_dai(releaseVariables, configurationApi):

    log_section("Attente Synchronisation ArgoCD")

    results  = json_load_var(releaseVariables, "argocdDeployResultsJson", [])
    env_cfgs = json_load_var(releaseVariables, "selectedEnvConfigsJson",  [])
    dry_run  = get_var(releaseVariables, "dryRun", "false") == "true"

    if dry_run:
        log_info("DRY RUN - skip")
        return {"waitResultsJson": [], "allHealthy": "true"}

    # Map env_name -> env_config
    env_map = {}
    for ec in env_cfgs:
        env_map[ec.get("name")] = ec

    wait_results = []
    all_healthy  = True

    for r in results:
        if r.get("action") in ("dry_run", "error"):
            wait_results.append({
                "env": r.get("env"), "app": r.get("app_name"),
                "success": r.get("action") != "error",
                "error": r.get("error", "")
            })
            if r.get("action") == "error":
                all_healthy = False
            continue

        app_name = r.get("app_name")
        env_name = r.get("env")
        ec       = env_map.get(env_name, {})

        log_info("Attente: %s ..." % app_name)

        try:
            argocd_url, argocd_token = get_argocd_credentials(
                releaseVariables, configurationApi, ec
            )

            success, status = argocd_wait_healthy(
                argocd_url, argocd_token, app_name,
                timeout=300, interval=15
            )

            wait_results.append({
                "env":     env_name,
                "app":     app_name,
                "success": success,
                "sync":    status.get("sync",   "Unknown"),
                "health":  status.get("health", "Unknown"),
                "error":   status.get("error",  "") if not success else ""
            })

            if success:
                log_ok("%s Synced + Healthy" % app_name)
            else:
                log_error("%s FAILED: %s" % (
                    app_name, status.get("msg", status.get("error", ""))
                ))
                all_healthy = False

        except Exception as e:
            log_error("Erreur wait %s: %s" % (app_name, str(e)))
            wait_results.append({
                "env": env_name, "app": app_name,
                "success": False, "error": str(e)
            })
            all_healthy = False

    return {
        "waitResultsJson": wait_results,
        "allHealthy":      "true" if all_healthy else "false"
    }