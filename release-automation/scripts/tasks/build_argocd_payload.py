def run_in_dai(releaseVariables, configurationApi):

    log_section("Deploiement ArgoCD")

    component   = json_load_var(releaseVariables, "componentConfigJson")
    env_configs = json_load_var(releaseVariables, "selectedEnvConfigsJson")
    image_tag   = get_var(releaseVariables, "imageTag")
    release_id  = get_var(releaseVariables, "releaseId",    "unknown")
    owner       = get_var(releaseVariables, "releaseOwner", "dai-release")
    dry_run     = get_var(releaseVariables, "dryRun", "false") == "true"

    comp_name  = component.get("name")
    chart_path = component.get("chartPath")
    git_repo   = component.get("gitopsRepoUrl")
    git_branch = component.get("gitopsRepoBranch", "main")

    results = []

    for ec in env_configs:

        env_name       = ec.get("name")
        app_name       = "%s-%s" % (comp_name, env_name)
        namespace      = "%s-%s" % (ec.get("namespace_prefix", env_name), comp_name)
        argocd_project = ec.get("argocdProject", "default")
        k8s_cluster    = ec.get("k8sCluster", "https://kubernetes.default.svc")
        auto_sync      = ec.get("autoSync", False)
        self_heal      = ec.get("selfHeal", False)
        prune          = ec.get("prune", False)

        log_info("")
        log_info("Application : %s" % app_name)
        log_info("  Namespace : %s" % namespace)
        log_info("  Cluster   : %s" % k8s_cluster)
        log_info("  AutoSync  : %s" % auto_sync)

        # Construire sync policy
        sync_policy = {
            "syncOptions": [
                "CreateNamespace=true",
                "PruneLast=true",
                "ApplyOutOfSyncOnly=true"
            ]
        }
        if auto_sync:
            sync_policy["automated"] = {
                "selfHeal":   self_heal,
                "prune":      prune,
                "allowEmpty": False
            }
            sync_policy["retry"] = {
                "limit":   3,
                "backoff": {
                    "duration":    "30s",
                    "factor":      2,
                    "maxDuration": "5m"
                }
            }

        app_spec = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind":       "Application",
            "metadata": {
                "name":      app_name,
                "namespace": "argocd",
                "labels": {
                    "app.kubernetes.io/managed-by":  "digitalai-release",
                    "app.kubernetes.io/component":   comp_name,
                    "app.kubernetes.io/environment": env_name,
                    "app.kubernetes.io/version":     image_tag,
                    "dai-release/release-id":        release_id
                },
                "annotations": {
                    "dai-release/deployed-by": owner,
                    "notifications.argoproj.io/subscribe.on-sync-succeeded.slack":
                        ec.get("notificationChannel", ""),
                    "notifications.argoproj.io/subscribe.on-sync-failed.slack":
                        ec.get("notificationChannel", "")
                },
                "finalizers": [
                    "resources-finalizer.argocd.argoproj.io"
                ]
            },
            "spec": {
                "project": argocd_project,
                "source": {
                    "repoURL":        git_repo,
                    "targetRevision": git_branch,
                    "path":           chart_path,
                    "helm": {
                        "valueFiles": [
                            "values.yaml",
                            "values-%s.yaml" % env_name
                        ],
                        "parameters": [
                            {"name": "image.tag", "value": image_tag}
                        ]
                    }
                },
                "destination": {
                    "server":    k8s_cluster,
                    "namespace": namespace
                },
                "syncPolicy": sync_policy
            }
        }

        if dry_run:
            log_info("  DRY RUN - skip")
            results.append({
                "env": env_name, "app_name": app_name,
                "action": "dry_run", "status": "skipped"
            })
            continue

        # Recuperer les credentials ArgoCD depuis la variable de folder
        try:
            argocd_url, argocd_token = get_argocd_credentials(
                releaseVariables, configurationApi, ec
            )

            argocd_create_or_update(argocd_url, argocd_token, app_spec)

            if not auto_sync:
                log_info("  Sync manuel...")
                argocd_sync(argocd_url, argocd_token, app_name,
                            prune=prune)

            log_ok("  Deploye: %s" % app_name)
            results.append({
                "env": env_name, "app_name": app_name,
                "argocdServerVariable": ec.get("argocdServerVariable"),
                "action": "deployed", "auto_sync": auto_sync,
                "status": "pending"
            })

        except Exception as e:
            log_error("  Erreur %s: %s" % (app_name, str(e)))
            results.append({
                "env": env_name, "app_name": app_name,
                "action": "error", "status": "error",
                "error": str(e)
            })

    has_errors = any(r.get("action") == "error" for r in results)
    if has_errors:
        log_error("Des erreurs sont survenues.")

    return {
        "argocdDeployResultsJson": results
    }