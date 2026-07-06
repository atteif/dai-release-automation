# =============================================================
# build_argocd_payload.py
# Construit et applique les Applications ArgoCD dynamiquement
# =============================================================

def run_in_dai(releaseVariables, configurationApi):

    import json

    log_section("Deploiement ArgoCD")

    component = json_load_var(releaseVariables, "componentConfigJson")
    env_configs = json_load_var(
        releaseVariables, "selectedEnvConfigsJson"
    )
    image_tag = get_var(releaseVariables, "imageTag")
    release_id = get_var(releaseVariables, "releaseId", "unknown")
    release_owner = get_var(releaseVariables, "releaseOwner", "dai-release")
    dry_run = get_var(releaseVariables, "dryRun", "false") == "true"

    component_name = component.get("name")
    chart_path = component.get("chartPath")
    git_repo = component.get("gitopsRepoUrl")
    git_branch = component.get("gitopsRepoBranch", "main")

    results = []

    for env_cfg in env_configs:
        env_name = env_cfg.get("name")
        app_name = "%s-%s" % (component_name, env_name)
        namespace = "%s-%s" % (
            env_cfg.get("namespace_prefix", env_name), component_name
        )
        argocd_server = env_cfg.get("argocdServer")
        argocd_project = env_cfg.get("argocdProject", "default")
        k8s_cluster = env_cfg.get("k8sCluster", "https://kubernetes.default.svc")
        auto_sync = env_cfg.get("autoSync", False)
        self_heal = env_cfg.get("selfHeal", False)
        prune = env_cfg.get("prune", False)

        log_info("")
        log_info("Application: %s" % app_name)
        log_info("  Namespace  : %s" % namespace)
        log_info("  Cluster    : %s" % k8s_cluster)
        log_info("  ArgoCD     : %s" % argocd_server)
        log_info("  AutoSync   : %s" % auto_sync)

        # --- Construire le spec ArgoCD ---
        sync_policy = {
            "syncOptions": [
                "CreateNamespace=true",
                "PruneLast=true",
                "ApplyOutOfSyncOnly=true"
            ]
        }
        if auto_sync:
            sync_policy["automated"] = {
                "selfHeal": self_heal,
                "prune": prune,
                "allowEmpty": False
            }
            sync_policy["retry"] = {
                "limit": 3,
                "backoff": {
                    "duration": "30s",
                    "factor": 2,
                    "maxDuration": "5m"
                }
            }

        app_spec = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": app_name,
                "namespace": "argocd",
                "labels": {
                    "app.kubernetes.io/managed-by": "digitalai-release",
                    "app.kubernetes.io/component": component_name,
                    "app.kubernetes.io/environment": env_name,
                    "app.kubernetes.io/version": image_tag,
                    "dai-release/release-id": release_id
                },
                "annotations": {
                    "dai-release/deployed-by": release_owner,
                    "dai-release/component": component_name,
                    "notifications.argoproj.io/subscribe.on-sync-succeeded.slack":
                        env_cfg.get("notificationChannel", ""),
                    "notifications.argoproj.io/subscribe.on-sync-failed.slack":
                        env_cfg.get("notificationChannel", ""),
                    "notifications.argoproj.io/subscribe.on-health-degraded.slack":
                        env_cfg.get("notificationChannel", "")
                },
                "finalizers": [
                    "resources-finalizer.argocd.argoproj.io"
                ]
            },
            "spec": {
                "project": argocd_project,
                "source": {
                    "repoURL": git_repo,
                    "targetRevision": git_branch,
                    "path": chart_path,
                    "helm": {
                        "valueFiles": [
                            "values.yaml",
                            "values-%s.yaml" % env_name
                        ],
                        "parameters": [
                            {
                                "name": "image.tag",
                                "value": image_tag
                            }
                        ]
                    }
                },
                "destination": {
                    "server": k8s_cluster,
                    "namespace": namespace
                },
                "syncPolicy": sync_policy
            }
        }

        if dry_run:
            log_info("DRY RUN - App spec:")
            log_info(json.dumps(app_spec, indent=2))
            results.append({
                "env": env_name,
                "app_name": app_name,
                "action": "dry_run",
                "status": "skipped"
            })
            continue

        # --- Appliquer dans ArgoCD ---
        try:
            argocd = ArgoCDClient.from_dai(
                configurationApi, argocd_server
            )
            argocd.create_or_update_app(app_spec)

            # --- Sync si pas autoSync ---
            if not auto_sync:
                log_info("Sync manuel: %s" % app_name)
                argocd.sync_app(app_name, prune=prune)

            log_ok("Deploye: %s" % app_name)
            results.append({
                "env": env_name,
                "app_name": app_name,
                "argocd_server": argocd_server,
                "action": "deployed",
                "auto_sync": auto_sync,
                "status": "pending"
            })

        except Exception as e:
            log_error("Erreur sur %s: %s" % (app_name, str(e)))
            results.append({
                "env": env_name,
                "app_name": app_name,
                "argocd_server": argocd_server,
                "action": "error",
                "status": "error",
                "error": str(e)
            })

    has_errors = any(r.get("action") == "error" for r in results)
    if has_errors:
        raise Exception(
            "Erreurs lors du deploiement ArgoCD. Voir les logs."
        )

    return {
        "argocdDeployResultsJson": results
    }