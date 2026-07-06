# =============================================================
# wait_sync.py
# Attend que les applications ArgoCD soient Synced + Healthy
# =============================================================

def run_in_dai(releaseVariables, configurationApi):

    log_section("Attente Synchronisation ArgoCD")

    deploy_results = json_load_var(
        releaseVariables, "argocdDeployResultsJson", []
    )
    env_configs = json_load_var(
        releaseVariables, "selectedEnvConfigsJson", []
    )
    dry_run = get_var(releaseVariables, "dryRun", "false") == "true"

    if dry_run:
        log_info("DRY RUN - Skip wait_sync")
        return {
            "waitResultsJson": [],
            "allHealthy": "true"
        }

    # Construire map env -> argocd_server
    env_to_server = {}
    for ec in env_configs:
        env_to_server[ec.get("name")] = ec.get("argocdServer")

    wait_results = []
    all_healthy = True
    timeout = 300
    interval = 15

    for r in deploy_results:
        if r.get("action") == "dry_run":
            continue
        if r.get("action") == "error":
            wait_results.append({
                "env": r.get("env"),
                "app": r.get("app_name"),
                "success": False,
                "error": r.get("error", "Deploy failed")
            })
            all_healthy = False
            continue

        app_name = r.get("app_name")
        env_name = r.get("env")
        argocd_server = r.get("argocd_server")

        if r.get("auto_sync"):
            log_info(
                "AutoSync active pour %s - attente health..." % app_name
            )
        else:
            log_info("Attente sync pour %s..." % app_name)

        try:
            argocd = ArgoCDClient.from_dai(
                configurationApi, argocd_server
            )
            success, status = argocd.wait_healthy(
                app_name, timeout=timeout, interval=interval
            )

            wait_results.append({
                "env": env_name,
                "app": app_name,
                "success": success,
                "sync": status.get("sync", "Unknown"),
                "health": status.get("health", "Unknown"),
                "error": status.get("error", "")
                    if not success else ""
            })

            if success:
                log_ok("%s est Synced + Healthy" % app_name)
            else:
                log_error(
                    "%s DEGRADE: %s" % (
                        app_name, status.get("health_message", "")
                    )
                )
                all_healthy = False

        except Exception as e:
            log_error("Erreur wait pour %s: %s" % (app_name, str(e)))
            wait_results.append({
                "env": env_name,
                "app": app_name,
                "success": False,
                "error": str(e)
            })
            all_healthy = False

    return {
        "waitResultsJson": wait_results,
        "allHealthy": "true" if all_healthy else "false"
    }