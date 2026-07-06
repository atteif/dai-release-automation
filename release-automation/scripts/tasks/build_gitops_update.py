# =============================================================
# build_gitops_update.py
# Cree/met a jour les values files dans le repo GitOps
# via GitLab API
# =============================================================

def run_in_dai(releaseVariables, configurationApi):

    import json

    log_section("Mise a jour GitOps (GitLab)")

    component = json_load_var(releaseVariables, "componentConfigJson")
    target_envs = json_load_var(releaseVariables, "targetEnvironmentsJson")
    image_tag = get_var(releaseVariables, "imageTag")
    release_id = get_var(releaseVariables, "releaseId", "unknown")
    release_owner = get_var(releaseVariables, "releaseOwner", "dai-release")

    chart_path = component.get("chartPath")
    gitops_project = component.get("gitopsRepoProject")
    gitops_branch_base = component.get("gitopsRepoBranch", "main")
    component_name = component.get("name")

    # --- Creer la branche de release ---
    release_branch = "release/%s-%s-%s" % (
        component_name, image_tag, release_id
    )

    gl = GitLabClient.from_dai(configurationApi, "GitLab Server")

    log_info("Creation branche: %s" % release_branch)
    gl.create_branch(gitops_project, release_branch, gitops_branch_base)
    log_ok("Branche creee: %s" % release_branch)

    updated_files = []

    # --- Mettre a jour values-{env}.yaml ---
    for env_name in target_envs:
        file_path = "%s/values-%s.yaml" % (chart_path, env_name)
        log_info("Lecture de: %s" % file_path)

        # Lire le fichier actuel
        try:
            current_content = gl.get_file(
                gitops_project, file_path, ref=gitops_branch_base
            )
            try:
                values = yaml_load(current_content)
            except Exception:
                values = {}
        except Exception as e:
            log_warn("Fichier introuvable, creation: %s" % file_path)
            values = {}

        if not isinstance(values, dict):
            values = {}

        # Mettre a jour le tag
        if "image" not in values:
            values["image"] = {}
        old_tag = values["image"].get("tag", "N/A")
        values["image"]["tag"] = image_tag

        # Mettre a jour les metadonnees
        values["_deployMeta"] = {
            "releaseId": release_id,
            "deployedBy": release_owner,
            "previousTag": old_tag
        }

        new_content = yaml_dump(values)

        # Ecrire le fichier mis a jour
        gl.update_file(
            project=gitops_project,
            file_path=file_path,
            content=new_content,
            branch=release_branch,
            commit_message="chore(%s): update image.tag to %s [%s]" % (
                component_name, image_tag, release_id
            )
        )

        log_ok("Mis a jour: %s (tag: %s -> %s)" % (
            file_path, old_tag, image_tag
        ))
        updated_files.append({
            "file": file_path,
            "env": env_name,
            "old_tag": old_tag,
            "new_tag": image_tag
        })

    # --- Creer la Merge Request ---
    log_info("Creation Merge Request...")
    envs_str = ", ".join(target_envs)
    mr_title = "deploy: %s v%s -> [%s]" % (
        component_name, image_tag, envs_str
    )
    mr_description = """## Deploiement Automatique GitOps

| Composant | %s |
| Version   | %s |
| Envs      | %s |
| Release   | %s |

Genere par Digital.ai Release.
""" % (component_name, image_tag, envs_str, release_id)

    mr_resp = gl.create_mr(
        project=gitops_project,
        source_branch=release_branch,
        target_branch=gitops_branch_base,
        title=mr_title,
        description=mr_description,
        labels=["auto-deploy", "gitops", component_name]
    )

    mr_iid = mr_resp.get("iid")
    mr_url = mr_resp.get("web_url", "")

    log_ok("MR creee: !%s" % mr_iid)
    log_info("URL: %s" % mr_url)

    # --- Merger la MR ---
    log_info("Merge de la MR !%s ..." % mr_iid)
    gl.merge_mr(gitops_project, mr_iid)
    log_ok("MR mergee dans %s" % gitops_branch_base)

    # --- Creer un tag Git ---
    tag_name = "deploy/%s/%s-%s" % (
        component_name, image_tag, release_id
    )
    gl.create_tag(
        project=gitops_project,
        tag_name=tag_name,
        ref=gitops_branch_base,
        message="Deploy %s v%s to [%s] - Release %s" % (
            component_name, image_tag, envs_str, release_id
        )
    )
    log_ok("Tag Git cree: %s" % tag_name)

    return {
        "releaseBranch": release_branch,
        "mergeRequestIid": str(mr_iid),
        "mergeRequestUrl": mr_url,
        "gitopsUpdatedFilesJson": updated_files,
        "gitopsTag": tag_name
    }