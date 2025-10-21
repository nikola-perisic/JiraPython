import requests
from datetime import datetime, timezone
import csv

# === CONFIGURATION ===
EMAIL = ""
API_TOKEN = ""
BASE_URL = ""

auth = (EMAIL, API_TOKEN)
headers = {"Accept": "application/json"}


# ---------------------------
# STEP 1: Get all spaces
# ---------------------------
def get_all_spaces():
    spaces = []
    url = f"{BASE_URL}/rest/api/space?limit=100&type=global"

    print("📚 Fetching all Confluence spaces...\n")

    while url:
        response = requests.get(url, headers=headers, auth=auth)
        response.raise_for_status()
        data = response.json()
        spaces.extend(data.get("results", []))
        next_link = data.get("_links", {}).get("next")
        url = f"{BASE_URL}{next_link}" if next_link else None

    print(f"✅ Found {len(spaces)} spaces.\n")
    return spaces


# ---------------------------
# STEP 2: Get last updated page safely
# ---------------------------
def get_last_updated_page(space_key):
    if not space_key:
        return None

    cql = f'space="{space_key}" and type=page order by lastmodified desc'
    url = f"{BASE_URL}/rest/api/content/search"
    params = {"cql": cql, "limit": 1, "expand": "version"}

    response = requests.get(url, headers=headers, auth=auth, params=params)
    if not response.ok:
        print(f"⚠️ Error {response.status_code} for space {space_key}: {response.text}")
        return None

    data = response.json()
    if not data.get("results"):
        return None

    page = data["results"][0]
    last_updated = page["version"]["when"]
    title = page.get("title", "No title")
    url = f"{BASE_URL}{page['_links'].get('webui', '')}"

    return {
        "title": title,
        "url": url,
        "last_updated": datetime.fromisoformat(last_updated.replace("Z", "+00:00")),
    }


# ---------------------------
# STEP 3: Main program
# ---------------------------
def main():
    spaces = get_all_spaces()
    results = []

    for space in spaces:
        name = space.get("name", "Unknown")
        key = space.get("key")
        print(f"🔍 Scanning space: {name} ({key}) ...")

        last_page = get_last_updated_page(key)
        results.append({
            "space": name,
            "key": key,
            "page_title": last_page["title"] if last_page else "No access or no pages",
            "page_url": last_page["url"] if last_page else "",
            "last_updated": last_page["last_updated"] if last_page else None
        })

    # Sort safely by last_updated
    safe_min = datetime.min.replace(tzinfo=timezone.utc)
    results.sort(key=lambda x: x["last_updated"] or safe_min, reverse=True)

    # Print results to console
    print("\n📋 === SPACE ACTIVITY REPORT ===")
    print(f"{'Space Name':<35} {'Key':<10} {'Last Updated':<25} {'Page Title'}")
    print("-" * 110)
    for r in results:
        last = (
            r["last_updated"].strftime("%Y-%m-%d %H:%M:%S %Z")
            if r["last_updated"]
            else "No access or no pages"
        )
        print(f"{r['space']:<35} {r['key']:<10} {last:<25} {r['page_title']}")

    # Export to CSV
    csv_file = "confluence_space_report.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Space Name", "Space Key", "Last Updated", "Page Title", "Page URL"])
        for r in results:
            writer.writerow([
                r["space"],
                r["key"],
                r["last_updated"].strftime("%Y-%m-%d %H:%M:%S") if r["last_updated"] else "",
                r["page_title"],
                r["page_url"]
            ])

    print(f"\n💾 Report saved to '{csv_file}'")


if __name__ == "__main__":
    main()
