# =============================================================
# lib.py - Librairie commune pour tous les scripts DAI Release
# Compatible Jython 2.7
# =============================================================

import json
import sys
import time

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


# =============================================================
# YAML
# =============================================================

def yaml_load(text):
    """Parse YAML compatible Jython via SnakeYAML Java."""
    if not text or not text.strip():
        raise Exception("yaml_load: contenu vide")
    if JYTHON_MODE:
        result = Yaml().load(StringReader(text))
        return _java_to_python(result)
    else:
        import yaml
        return yaml.safe_load(text)


def yaml_dump(data):
    """Serialise en YAML."""
    try:
        import yaml
        return yaml.dump(
            data,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False
        )
    except ImportError:
        return json.dumps(data, indent=2)


def _java_to_python(obj):
    """Convertit les objets Java (Map/List) en types Python natifs."""
    if obj is None:
        return None
    try:
        from java.util import Map, List
        if isinstance(obj, Map):
            result = {}
            for key in obj.keySet():
                result[str(key)] = _java_to_python(obj.get(key))
            return result
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

def set_result(releaseVariables, data):
    """
    Ecrit les resultats dans les variables de release.
    Serialise automatiquement dict/list en JSON string.
    """
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            releaseVariables[key] = json.dumps(value)
        elif value is None:
            releaseVariables[key] = ""
        else:
            releaseVariables[key] = value


def json_load_var(releaseVariables, key, default_value=None):
    """
    Charge et deserialise une variable JSON depuis releaseVariables.
    """
    raw = releaseVariables.get(key)
    if not raw:
        if default_value is not None:
            return default_value
        raise Exception("Variable manquante ou vide: %s" % key)
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception as e:
        raise Exception(
            "Impossible de parser JSON pour '%s': %s" % (key, str(e))
        )


def get_var(releaseVariables, key, default=None):
    """Recupere une variable avec valeur par defaut."""
    value = releaseVariables.get(key)
    if value is None or value == "":
        return default
    return value


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


def log_table_row(col1, col2, col3="", width1=20, width2=15, width3=20):
    row = str(col1).ljust(width1) + str(col2).ljust(width2)
    if col3:
        row += str(col3).ljust(width3)
    print(row)
    sys.stdout.flush()


# =============================================================
# HTTP CLIENT
# =============================================================

class HttpClient(object):
    """Client HTTP simple compatible Jython."""

    def __init__(self, base_url, headers=None, ssl_verify=False):
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.ssl_verify = ssl_verify

    def _get_ssl_ctx(self):
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def _request(self, method, path, body=None, params=None):
        url = "%s%s" % (self.base_url, path)
        if params:
            url += "?" + urlencode(params)

        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")

        req = Request(url, data=data)
        req.get_method = lambda: method
        req.add_header("Content-Type", "application/json")
        for k, v in self.headers.items():
            req.add_header(k, v)

        try:
            ctx = self._get_ssl_ctx()
            resp = urlopen(req, context=ctx, timeout=30)
            body = resp.read()
            if body:
                return json.loads(body.decode("utf-8"))
            return {}
        except HTTPError as e:
            err = e.read().decode("utf-8")
            raise Exception(
                "HTTP %s %s -> %d: %s" % (method, url, e.code, err)
            )
        except URLError as e:
            raise Exception("URL error %s: %s" % (url, str(e)))

    def get(self, path, params=None):
        return self._request("GET", path, params=params)

    def post(self, path, body=None):
        return self._request("POST", path, body=body)

    def put(self, path, body=None):
        return self._request("PUT", path, body=body)

    def delete(self, path, params=None):
        return self._request("DELETE", path, params=params)


# =============================================================
# GITLAB CLIENT
# =============================================================

class GitLabClient(object):
    """Client GitLab API v4 compatible Jython."""

    def __init__(self, base_url, token, ssl_verify=False):
        self.http = HttpClient(
            base_url="%s/api/v4" % base_url.rstrip("/"),
            headers={"PRIVATE-TOKEN": token},
            ssl_verify=ssl_verify
        )

    @classmethod
    def from_dai(cls, configurationApi, server_title="GitLab Server"):
        """Cree un client depuis la config DAI Release."""
        servers = configurationApi.searchByTypeAndTitle(
            "gitlab.Server", server_title
        )
        if not servers:
            raise Exception(
                "Serveur GitLab '%s' non configure dans DAI" % server_title
            )
        s = servers[0]
        return cls(
            base_url=s.getProperty("url"),
            token=s.getProperty("token")
        )

    def _encode(self, path):
        return quote(path, safe="")

    def get_file(self, project, file_path, ref="main"):
        """Recupere le contenu d'un fichier (decode base64)."""
        import base64
        encoded_project = self._encode(project)
        encoded_file = self._encode(file_path)
        resp = self.http.get(
            "/projects/%s/repository/files/%s" % (
                encoded_project, encoded_file
            ),
            params={"ref": ref}
        )
        content = resp.get("content", "")
        encoding = resp.get("encoding", "base64")
        if encoding == "base64":
            return base64.b64decode(content).decode("utf-8")
        return content

    def create_branch(self, project, branch, ref="main"):
        """Cree une branche."""
        encoded_project = self._encode(project)
        try:
            return self.http.post(
                "/projects/%s/repository/branches" % encoded_project,
                body={"branch": branch, "ref": ref}
            )
        except Exception as e:
            if "already exists" in str(e).lower() or "409" in str(e):
                log_warn("Branche existe deja: %s" % branch)
                return {}
            raise

    def update_file(self, project, file_path, content, branch,
                    commit_message):
        """Cree ou met a jour un fichier."""
        encoded_project = self._encode(project)
        encoded_file = self._encode(file_path)
        endpoint = "/projects/%s/repository/files/%s" % (
            encoded_project, encoded_file
        )
        body = {
            "branch": branch,
            "content": content,
            "commit_message": commit_message,
            "encoding": "text"
        }
        try:
            # Try update first
            return self.http.put(endpoint, body=body)
        except Exception as e:
            if "404" in str(e):
                # File doesn't exist, create it
                return self.http.post(endpoint, body=body)
            raise

    def create_mr(self, project, source_branch, target_branch,
                  title, description="", labels=None):
        """Cree une Merge Request."""
        encoded_project = self._encode(project)
        body = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
            "remove_source_branch": True,
            "squash": True
        }
        if labels:
            body["labels"] = ",".join(labels)
        return self.http.post(
            "/projects/%s/merge_requests" % encoded_project,
            body=body
        )

    def merge_mr(self, project, mr_iid):
        """Merge une MR."""
        encoded_project = self._encode(project)
        return self.http.put(
            "/projects/%s/merge_requests/%s/merge" % (
                encoded_project, mr_iid
            ),
            body={"squash": True}
        )

    def create_tag(self, project, tag_name, ref, message=""):
        """Cree un tag Git."""
        encoded_project = self._encode(project)
        try:
            return self.http.post(
                "/projects/%s/repository/tags" % encoded_project,
                body={
                    "tag_name": tag_name,
                    "ref": ref,
                    "message": message
                }
            )
        except Exception as e:
            if "already exists" in str(e).lower() or "409" in str(e):
                log_warn("Tag existe deja: %s" % tag_name)
                return {}
            raise


# =============================================================
# ARGOCD CLIENT
# =============================================================

class ArgoCDClient(object):
    """Client ArgoCD API v1 compatible Jython."""

    def __init__(self, base_url, token, ssl_verify=False):
        self.http = HttpClient(
            base_url="%s/api/v1" % base_url.rstrip("/"),
            headers={"Authorization": "Bearer %s" % token},
            ssl_verify=ssl_verify
        )

    @classmethod
    def from_dai(cls, configurationApi, server_title):
        """Cree un client ArgoCD depuis la config DAI Release."""
        servers = configurationApi.searchByTypeAndTitle(
            "argocd.Server", server_title
        )
        if not servers:
            raise Exception(
                "Serveur ArgoCD '%s' non configure dans DAI" % server_title
            )
        s = servers[0]
        return cls(
            base_url=s.getProperty("url"),
            token=s.getProperty("token")
        )

    def app_exists(self, app_name):
        """Verifie si une application existe."""
        try:
            self.http.get("/applications/%s" % app_name)
            return True
        except Exception as e:
            if "404" in str(e):
                return False
            raise

    def create_or_update_app(self, app_spec):
        """Cree ou met a jour une application ArgoCD."""
        app_name = app_spec["metadata"]["name"]
        if self.app_exists(app_name):
            log_info("Application existante, mise a jour: %s" % app_name)
            existing = self.http.get("/applications/%s" % app_name)
            rv = existing.get("metadata", {}).get("resourceVersion")
            if rv:
                app_spec["metadata"]["resourceVersion"] = rv
            return self.http.put(
                "/applications/%s" % app_name,
                body=app_spec
            )
        else:
            log_info("Creation application: %s" % app_name)
            return self.http.post("/applications", body=app_spec)

    def sync_app(self, app_name, prune=False, revision=None):
        """Lance un sync ArgoCD."""
        body = {
            "prune": prune,
            "dryRun": False,
            "strategy": {"apply": {"force": False}},
            "syncOptions": {"items": ["CreateNamespace=true"]}
        }
        if revision:
            body["revision"] = revision
        return self.http.post(
            "/applications/%s/sync" % app_name,
            body=body
        )

    def get_app_status(self, app_name):
        """Recupere le statut d'une application."""
        app = self.http.get("/applications/%s" % app_name)
        status = app.get("status", {})
        return {
            "sync": status.get("sync", {}).get("status", "Unknown"),
            "health": status.get("health", {}).get("status", "Unknown"),
            "health_message": status.get("health", {}).get("message", ""),
            "operation": status.get(
                "operationState", {}
            ).get("phase", "Unknown")
        }

    def wait_healthy(self, app_name, timeout=300, interval=15):
        """Attend qu'une application soit Synced+Healthy."""
        elapsed = 0
        while elapsed < timeout:
            status = self.get_app_status(app_name)
            sync = status["sync"]
            health = status["health"]
            log_info(
                "[%ds/%ds] %s -> Sync: %s | Health: %s" % (
                    elapsed, timeout, app_name, sync, health
                )
            )
            if sync == "Synced" and health == "Healthy":
                return True, status
            if health == "Degraded":
                return False, status
            time.sleep(interval)
            elapsed += interval
        return False, {"error": "Timeout after %ds" % timeout}

    def rollback_app(self, app_name, revision_id):
        """Rollback vers une revision precedente."""
        return self.http.post(
            "/applications/%s/rollback" % app_name,
            body={"id": revision_id}
        )

    def get_app_history(self, app_name):
        """Recupere l'historique de deployments."""
        app = self.http.get("/applications/%s" % app_name)
        return app.get("status", {}).get("history", [])