# =============================================================
# lib.py
# Librairie commune pour tous les scripts DAI Release
# Compatible Jython 2.7
# Utilise les variables de folder de type Configuration
# =============================================================

import json
import sys
import time
import base64

try:
    from org.yaml.snakeyaml import Yaml
    from java.io import StringReader
    JYTHON_MODE = True
except ImportError:
    JYTHON_MODE = False

try:
    from urllib2 import Request, urlopen, HTTPError, URLError
    from urllib import urlencode, quote
except ImportError:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode, quote

import ssl

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


# =============================================================
# YAML
# =============================================================

def yaml_load(text):
    if not text or not text.strip():
        raise Exception("yaml_load: contenu vide")
    if JYTHON_MODE:
        result = Yaml().load(StringReader(text))
        return _java_to_python(result)
    else:
        import yaml
        return yaml.safe_load(text)


def yaml_dump(data):
    try:
        import yaml
        return yaml.dump(data, default_flow_style=False,
                         allow_unicode=True, sort_keys=False)
    except ImportError:
        return json.dumps(data, indent=2)


def _java_to_python(obj):
    if obj is None:
        return None
    try:
        from java.util import Map, List
        if isinstance(obj, Map):
            r = {}
            for key in obj.keySet():
                r[str(key)] = _java_to_python(obj.get(key))
            return r
        elif isinstance(obj, List):
            return [_java_to_python(item) for item in obj]
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {k: _java_to_python(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_java_to_python(i) for i in obj]
    return obj


# =============================================================
# VARIABLES
# =============================================================

def set_result(rv, data):
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            rv[key] = json.dumps(value)
        elif value is None:
            rv[key] = ""
        else:
            rv[key] = str(value)


def json_load_var(rv, key, default=None):
    raw = rv.get(key)
    if not raw:
        if default is not None:
            return default
        raise Exception("Variable manquante ou vide: %s" % key)
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception as e:
        raise Exception(
            "JSON invalide pour '%s': %s\nContenu: %s" % (
                key, str(e), raw[:200]
            )
        )


def get_var(rv, key, default=None):
    value = rv.get(key)
    if value is None or value == "":
        return default
    return value


# =============================================================
# CONFIGURATION VARIABLES (Folder variables de type Config)
# =============================================================

def resolve_config(rv, configurationApi, var_name, expected_type=None):
    """
    Resout une variable de folder de type Configuration.

    Cas 1 : la variable est un objet de configuration DAI
            -> on appelle getProperty() directement
    Cas 2 : la variable est un string (titre du serveur)
            -> on cherche avec configurationApi
    Cas 3 : la variable est un CI (Configuration Item)
            -> on accede a ses proprietes

    Retourne l objet de configuration DAI.
    """
    value = rv.get(var_name)

    if value is None:
        raise Exception(
            "Variable de configuration '%s' introuvable.\n"
            "Verifier les variables de folder dans DAI." % var_name
        )

    # Cas 1 : objet de config avec getProperty
    if hasattr(value, "getProperty"):
        return value

    # Cas 2 : objet CI avec properties
    if hasattr(value, "properties"):
        return value

    # Cas 3 : c est un string -> chercher par titre
    title = None
    try:
        title = str(value).strip()
    except:
        pass

    if title and expected_type:
        items = configurationApi.searchByTypeAndTitle(
            expected_type, title
        )
        if items and len(items) > 0:
            return items[0]

    raise Exception(
        "Impossible de resoudre '%s' (type=%s, valeur=%s).\n"
        "Verifier que la variable de folder est bien de type "
        "Configuration et pointe vers un serveur existant." % (
            var_name,
            type(value).__name__,
            str(value)[:100]
        )
    )


def get_config_property(config_obj, prop_name, default=None):
    """
    Lit une propriete d un objet de configuration DAI.
    Compatible avec differentes versions de DAI.
    """
    # Methode 1 : getProperty(name)
    if hasattr(config_obj, "getProperty"):
        try:
            val = config_obj.getProperty(prop_name)
            if val is not None:
                return str(val)
        except:
            pass

    # Methode 2 : accès direct attribut
    if hasattr(config_obj, prop_name):
        try:
            val = getattr(config_obj, prop_name)
            if val is not None:
                return str(val)
        except:
            pass

    # Methode 3 : properties map
    if hasattr(config_obj, "properties"):
        try:
            props = config_obj.properties
            if hasattr(props, "get"):
                val = props.get(prop_name)
                if val is not None:
                    return str(val)
        except:
            pass

    if default is not None:
        return default

    raise Exception(
        "Propriete '%s' introuvable sur l objet de configuration.\n"
        "Type: %s" % (prop_name, type(config_obj).__name__)
    )


# =============================================================
# GITLAB CLIENT (utilise les variables de configuration)
# =============================================================

def get_gitlab_credentials(rv, configurationApi):
    """
    Recupere URL et token GitLab depuis la variable de
    configuration de folder.
    """
    server = resolve_config(
        rv, configurationApi, "gitlabServer", "gitlab.Server"
    )
    url   = get_config_property(server, "url")
    token = get_config_property(server, "token")

    if not url:
        raise Exception("URL GitLab vide dans la configuration")
    if not token:
        raise Exception("Token GitLab vide dans la configuration")

    return url.rstrip("/"), token


def read_gitlab_file(gitlab_url, gitlab_token, project, file_path, ref):
    """
    Lit un fichier depuis GitLab via l API REST.
    """
    url = "%s/api/v4/projects/%s/repository/files/%s?ref=%s" % (
        gitlab_url,
        quote(project,   safe=""),
        quote(file_path, safe=""),
        quote(ref,       safe="")
    )
    req = Request(url)
    req.add_header("PRIVATE-TOKEN", gitlab_token)
    try:
        resp    = urlopen(req, context=SSL_CTX, timeout=30)
        data    = json.loads(resp.read().decode("utf-8"))
        content = data.get("content",  "")
        enc     = data.get("encoding", "base64")
        if enc == "base64":
            return base64.b64decode(content).decode("utf-8")
        return content
    except HTTPError as e:
        body = e.read().decode("utf-8")
        raise Exception(
            "GitLab HTTP %d [%s @ %s]: %s" % (
                e.code, file_path, project, body
            )
        )


def write_gitlab_file(gitlab_url, gitlab_token, project, file_path,
                      content, branch, commit_message):
    """
    Cree ou met a jour un fichier dans GitLab.
    """
    url = "%s/api/v4/projects/%s/repository/files/%s" % (
        gitlab_url,
        quote(project,   safe=""),
        quote(file_path, safe="")
    )
    body = json.dumps({
        "branch":         branch,
        "content":        content,
        "commit_message": commit_message,
        "encoding":       "text"
    }).encode("utf-8")

    # Essayer PUT (update) puis POST (create)
    for method in ["PUT", "POST"]:
        req = Request(url, data=body)
        req.get_method = lambda m=method: m
        req.add_header("PRIVATE-TOKEN", gitlab_token)
        req.add_header("Content-Type", "application/json")
        try:
            resp = urlopen(req, context=SSL_CTX, timeout=30)
            return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            if method == "PUT" and e.code in (400, 404):
                continue
            if method == "POST":
                err = e.read().decode("utf-8")
                raise Exception(
                    "Erreur ecriture %s: HTTP %d - %s" % (
                        file_path, e.code, err
                    )
                )
    raise Exception("Impossible d ecrire %s" % file_path)


# =============================================================
# ARGOCD CLIENT (utilise les variables de configuration)
# =============================================================

def get_argocd_credentials(rv, configurationApi, env_cfg):
    """
    Recupere URL et token ArgoCD depuis la variable de
    configuration de folder, en utilisant le mapping dans
    environments.yaml.
    """
    var_name = env_cfg.get("argocdServerVariable")
    if not var_name:
        raise Exception(
            "argocdServerVariable manquant pour env '%s'" % (
                env_cfg.get("name", "unknown")
            )
        )

    server = resolve_config(
        rv, configurationApi, var_name, "argocd.Server"
    )
    url   = get_config_property(server, "url")
    token = get_config_property(server, "token")

    if not url:
        raise Exception(
            "URL ArgoCD vide pour '%s'" % var_name
        )
    if not token:
        raise Exception(
            "Token ArgoCD vide pour '%s'" % var_name
        )

    return url.rstrip("/"), token


def argocd_request(argocd_url, argocd_token, method, path,
                   body=None, params=None):
    """
    Appel API ArgoCD.
    """
    url = "%s/api/v1%s" % (argocd_url, path)
    if params:
        url += "?" + urlencode(params)

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = Request(url, data=data)
    req.get_method = lambda: method
    req.add_header("Authorization", "Bearer %s" % argocd_token)
    req.add_header("Content-Type",  "application/json")

    try:
        resp = urlopen(req, context=SSL_CTX, timeout=30)
        raw  = resp.read()
        return json.loads(raw.decode("utf-8")) if raw else {}
    except HTTPError as e:
        err = e.read().decode("utf-8")
        raise Exception(
            "ArgoCD %s %s -> HTTP %d: %s" % (method, path, e.code, err)
        )


def argocd_app_exists(argocd_url, argocd_token, app_name):
    try:
        argocd_request(argocd_url, argocd_token,
                       "GET", "/applications/%s" % app_name)
        return True
    except Exception as e:
        if "404" in str(e):
            return False
        raise


def argocd_create_or_update(argocd_url, argocd_token, app_spec):
    app_name = app_spec["metadata"]["name"]
    if argocd_app_exists(argocd_url, argocd_token, app_name):
        existing = argocd_request(
            argocd_url, argocd_token,
            "GET", "/applications/%s" % app_name
        )
        rv = existing.get("metadata", {}).get("resourceVersion")
        if rv:
            app_spec["metadata"]["resourceVersion"] = rv
        return argocd_request(
            argocd_url, argocd_token,
            "PUT", "/applications/%s" % app_name, body=app_spec
        )
    else:
        return argocd_request(
            argocd_url, argocd_token,
            "POST", "/applications", body=app_spec
        )


def argocd_sync(argocd_url, argocd_token, app_name, prune=False):
    return argocd_request(
        argocd_url, argocd_token,
        "POST", "/applications/%s/sync" % app_name,
        body={
            "prune":       prune,
            "dryRun":      False,
            "strategy":    {"apply": {"force": False}},
            "syncOptions": {"items": ["CreateNamespace=true"]}
        }
    )


def argocd_get_status(argocd_url, argocd_token, app_name):
    app    = argocd_request(
        argocd_url, argocd_token,
        "GET", "/applications/%s" % app_name
    )
    status = app.get("status", {})
    return {
        "sync":   status.get("sync",   {}).get("status", "Unknown"),
        "health": status.get("health", {}).get("status", "Unknown"),
        "msg":    status.get("health", {}).get("message", ""),
        "op":     status.get("operationState", {}).get("phase", "Unknown")
    }


def argocd_wait_healthy(argocd_url, argocd_token, app_name,
                        timeout=300, interval=15):
    elapsed = 0
    while elapsed < timeout:
        st = argocd_get_status(argocd_url, argocd_token, app_name)
        log_info("[%ds/%ds] %s -> Sync=%s Health=%s" % (
            elapsed, timeout, app_name, st["sync"], st["health"]
        ))
        if st["sync"] == "Synced" and st["health"] == "Healthy":
            return True, st
        if st["health"] == "Degraded":
            return False, st
        if st["op"] == "Failed":
            return False, st
        time.sleep(interval)
        elapsed += interval
    return False, {"error": "Timeout after %ds" % timeout}


def argocd_get_history(argocd_url, argocd_token, app_name):
    app = argocd_request(
        argocd_url, argocd_token,
        "GET", "/applications/%s" % app_name
    )
    return app.get("status", {}).get("history", [])


# =============================================================
# LOGGING
# =============================================================

def log_section(title):
    print("")
    print("=" * 60)
    print("  %s" % title)
    print("=" * 60)
    sys.stdout.flush()

def log_info(msg):
    print("[INFO]  %s" % msg)
    sys.stdout.flush()

def log_ok(msg):
    print("[OK]    %s" % msg)
    sys.stdout.flush()

def log_warn(msg):
    print("[WARN]  %s" % msg)
    sys.stdout.flush()

def log_error(msg):
    print("[ERROR] %s" % msg)
    sys.stdout.flush()