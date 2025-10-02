import requests
import csv
from requests.auth import HTTPBasicAuth
from datetime import datetime

# --- CONFIG ---
JIRA_URL = ""
EMAIL = ""
API_TOKEN = ""

auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {"Accept": "application/json"}

# --- STEP 1: Global Permissions ---
def get_global_permissions():
    url = f"{JIRA_URL}/rest/api/3/permissionscheme"
    response = requests.get(url, headers=headers, auth=auth)
    response.raise_for_status()
    schemes = response.json().get("values", [])
    results = []

    print("\n🌍 Global Permissions:")
    for scheme in schemes:
        scheme_name = scheme["name"]
        scheme_id = scheme["id"]
        scheme_url = f"{JIRA_URL}/rest/api/3/permissionscheme/{scheme_id}"

        scheme_resp = requests.get(scheme_url, headers=headers, auth=auth)
        scheme_resp.raise_for_status()
        details = scheme_resp.json()

        print(f"\n🔹 {scheme_name}")
        for perm in details.get("permissions", []):
            key = perm["permission"]
            holders = perm.get("holders", [perm["holder"]]) if "holder" in perm else []
            for h in holders:
                desc = h.get("displayName") or h.get("parameter") or h.get("type")
                print(f"  • {key}: {desc}")
                results.append(["GLOBAL", scheme_name, key, desc])

    return results

# --- STEP 2: Get Projects ---
def get_projects():
    url = f"{JIRA_URL}/rest/api/3/project/search"
    response = requests.get(url, headers=headers, auth=auth)
    response.raise_for_status()
    return response.json()["values"]

# --- STEP 3: Get Project Roles ---
def get_project_roles(project_key):
    url = f"{JIRA_URL}/rest/api/3/project/{project_key}/role"
    response = requests.get(url, headers=headers, auth=auth)
    response.raise_for_status()
    return response.json()

# --- STEP 4: Expand Role Members ---
def get_role_details(role_url):
    response = requests.get(role_url, headers=headers, auth=auth)
    response.raise_for_status()
    return response.json()

# --- STEP 5: Project-Level Check ---
def project_permissions_check():
    projects = get_projects()
    results = []

    print("\n📂 Project Permissions:")
    for project in projects:
        project_key = project["key"]
        project_name = project["name"]

        print(f"\n🔎 {project_name} ({project_key})")
        roles = get_project_roles(project_key)

        for role_name, role_url in roles.items():
            role_details = get_role_details(role_url)
            actors = role_details.get("actors", [])

            members = [a.get("displayName") or a.get("name") or a.get("type") for a in actors]

            if members:
                print(f"  • {role_name}: {', '.join(members)}")
                for m in members:
                    results.append(["PROJECT", f"{project_name} ({project_key})", role_name, m])
            else:
                print(f"  • {role_name}: (empty)")
                results.append(["PROJECT", f"{project_name} ({project_key})", role_name, "(empty)"])

    return results

# --- STEP 6: Export to CSV ---
def export_to_csv(global_perms, project_perms):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"jira_permissions_audit_{timestamp}.csv"

    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Scope", "Project/Scheme", "Permission/Role", "User/Group"])

        for row in global_perms:
            writer.writerow(row)

        for row in project_perms:
            writer.writerow(row)

    print(f"\n✅ Export complete → {filename}")

# --- MAIN ---
if __name__ == "__main__":
    global_perms = get_global_permissions()
    project_perms = project_permissions_check()
    export_to_csv(global_perms, project_perms)