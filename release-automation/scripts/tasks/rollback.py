# =============================================================
# rollback.py
# Rollback d'un deploiement ArgoCD
# =============================================================

def run_in_dai(releaseVariables, configurationApi):

    log_section("ROLLBACK")

    perform = get_var(
        releaseVariables, "performRollback", "false"
    ) == "true"

    if not perform:
        log_info("Rollback non demande - skip")
        return {"rollbackStatus": "skipped"}

    component = json_load_var(releaseVariables, "componentConfigJson")
    env_configs = json_load_var(
        releaseVariables, "selectedEnvConfigsJson"
    )
    rollback_tag = get_var(releaseVariables, "rollbackTag", "")

    component_name = component.get("name")
    rollback_results = []

    for env_cfg in env_configs:
        env_name = env_cfg.get("name")
        app_name = "%s-%s" % (component_name, env_name)
        argocd_server = env_cfg.get("argocdServer")

        log_info("Rollback %s (tag: %s)..." % (app_name, rollback_tag))

        try:
            argocd = ArgoCDClient.from_dai(
                configurationApi, argocd_server
            )

            if rollback_tag:
                # Rollback by tag: update helm parameter
                app = argocd.http.get(
                    "/applications/%s" % app_name
                )
                spec = app.get("spec", {})
                source = spec.get("source", {})
                helm = source.get("helm", {})
                params = helm.get("parameters", [])

                updated = False
                for param in params:
                    if param.get("name") == "image.tag":
                        param["value"] = rollback_tag
                        updated = True
                        break
                if not updated:
                    params.append({
                        "name": "image.tag",
                        "value": rollback_tag
                    })

                helm["parameters"] = params
                source["helm"] = helm
                spec["source"] = source
                app["spec"] = spec

                argocd.http.put(
                    "/applications/%s" % app_name, body=app
                )
                argocd.sync_app(app_name, prune=False)

            else:
                # Rollback to previous ArgoCD revision
                history = argocd.get_app_history(app_name)
                if len(history) < 2:
                    raise Exception(
                        "Pas assez d'historique pour rollback"
                    )
                prev_revision_id = history[-2].get("id")
                argocd.rollback_app(app_name, prev_revision_id)

            log_ok("Rollback initie: %s" % app_name)
            rollback_results.append({
                "env": env_name,
                "app": app_name,
                "status": "rolled_back",
                "rollback_tag": rollback_tag
            })

        except Exception as e:
            log_error(
                "Erreur rollback %s: %s" % (app_name, str(e))
            )
            rollback_results.append({
                "env": env_name,
                "app": app_name,
                "status": "error",
                "error": str(e)
            })

    return {
        "rollbackResultsJson": rollback_results,
        "rollbackStatus": "completed"
    }