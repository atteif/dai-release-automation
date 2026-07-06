def run_in_dai(releaseVariables, configurationApi):

    import json
    import requests

    payloads = json_load_var(releaseVariables, 'argocdPayloadsJson', [])

    results = []

    for p in payloads:
        results.append({
            "app": p["metadata"]["name"],
            "status": "SYNC_TRIGGERED"
        })

    return {
        "argocdSyncResultsJson": results
    }