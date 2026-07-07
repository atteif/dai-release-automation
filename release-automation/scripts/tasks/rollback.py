def run_in_dai(releaseVariables, configurationApi):

    log_section("ROLLBACK")

    perform = get_var(releaseVariables, "performRollback", "false")
    if perform != "true":
        log_info("Rollback non demande - skip")
        return {"rollbackStatus": "skipped"}

    component   = json_load_var(releaseVariables, "componentConfigJson")
    env_configs = json_load_var(releaseVariables, "selectedEnvConfigsJson")
    rollback_tag = get_var(releaseVariables, "rollbackTag", "")

    comp_name = component.get("name")
    results   = []

    for ec in env_configs:
        env_name = ec.get("name")
        app_name = "%s-%s" % (comp_name, env_name)

        log_info("Rollback %s ..." % app_name)

        try:
            argocd_url, argocd_token = get_argocd_credentials(
                releaseVariables, configurationApi, ec
            )

            if rollback_tag:
                # Rollback par tag: modifier le parametre helm
                app = argocd_request(
                    argocd_url, argocd_token,
                    "GET", "/applications/%s" % app_name
                )
                spec   = app.get("spec", {})
                source = spec.get("source", {})
                helm   = source.get("helm", {})
                params = helm.get("parameters", [])

                updated = False
                for p in params:
                    if p.get("name") == "image.tag":
                        p["value"] = rollback_tag
                        updated = True
                        break
                if not updated:
                    params.append({
                        "name": "image.tag", "value": rollback_tag
                    })

                helm["parameters"] = params
                source["helm"]     = helm
                spec["source"]     = source
                app["spec"]        = spec

                argocd_request(
                    argocd_url, argocd_token,
                    "PUT", "/applications/%s" % app_name, body=app
                )
                argocd_sync(argocd_url, argocd_token, app_name)

                log_ok("Rollback -> tag %s pour %s" % (
                    rollback_tag, app_name
                ))
            else:
                # Rollback vers la revision precedente
                history = argocd_get_history(
                    argocd_url, argocd_token, app_name
                )
                if len(history) < 2:
                    raise Exception("Pas assez d historique")
                prev_id = history[-2].get("id")
                argocd_request(
                    argocd_url, argocd_token,
                    "POST", "/applications/%s/rollback" % app_name,
                    body={"id": prev_id}
                )
                log_ok("Rollback -> revision %s pour %s" % (
                    prev_id, app_name
                ))

            results.append({
                "env": env_name, "app": app_name,
                "status": "rolled_back"
            })

        except Exception as e:
            log_error("Erreur rollback %s: %s" % (app_name, str(e)))
            results.append({
                "env": env_name, "app": app_name,
                "status": "error", "error": str(e)
            })

    return {
        "rollbackResultsJson": results,
        "rollbackStatus":      "completed"
    }