import sys
import requests
from requests.auth import HTTPBasicAuth
from collections import defaultdict

# --- CONFIGURATION ---
# 1. Replace with your Jira instance URL
JIRA_URL = ""

# 2. Replace with your email address
JIRA_USERNAME = ""

# 3. Replace with your Jira API Token.
#    Generate one here: https://id.atlassian.com/manage-profile/security/api-tokens
JIRA_API_TOKEN = ""
# ---------------------

def make_jira_request(url_path, auth, params=None):
    """
    Helper function to make a GET request to the Jira API.
    Handles URL construction, auth, headers, and error raising.
    """
    # Ensure no double slashes if JIRA_URL ends with / and url_path starts with /
    url = f"{JIRA_URL.rstrip('/')}/{url_path.lstrip('/')}"
    
    headers = {
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, auth=auth, params=params)
        # Raise an exception for 4xx or 5xx status codes
        response.raise_for_status() 
        return response.json()
    
    except requests.exceptions.HTTPError as http_err:
        # Provide more context for HTTP errors
        print(f"\nHTTP Error: {http_err.response.status_code} for URL: {url}")
        try:
            # Try to print JSON error message from Jira
            error_data = http_err.response.json()
            if 'errorMessages' in error_data:
                print(f"Details: {', '.join(error_data['errorMessages'])}")
            else:
                print(f"Details: {http_err.response.text}")
        except requests.exceptions.JSONDecodeError:
            print(f"Details: {http_err.response.text}")
        
        # Re-raise the exception to be caught by the calling function
        raise http_err
    
    except requests.exceptions.RequestException as req_err:
        # Handle other requests errors (connection, timeout, etc.)
        print(f"\nRequest Error: {req_err}")
        raise req_err

def main():
    """
    Main function to connect to Jira, check issue type usage,
    and report on unused issue types.
    """
    
    if JIRA_API_TOKEN == "YOUR_API_TOKEN_HERE" or not JIRA_API_TOKEN:
        print("Error: Please update the JIRA_API_TOKEN variable in the script.")
        sys.exit(1)

    print(f"Connecting to {JIRA_URL} as {JIRA_USERNAME}...")
    
    auth = HTTPBasicAuth(JIRA_USERNAME, JIRA_API_TOKEN)
    
    try:
        # Test connection by fetching the current user
        current_user = make_jira_request("rest/api/3/myself", auth)
        print(f"Successfully connected as: {current_user.get('displayName', 'Unknown User')}")
        
    except requests.exceptions.RequestException as e:
        print(f"\nConnection Error: Failed to connect to Jira.")
        print("Please check your JIRA_URL, JIRA_USERNAME, and JIRA_API_TOKEN.")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred during connection: {e}")
        sys.exit(1)

    # This map will hold: { "Issue Type Name": [ProjectKey1, ProjectKey2, ...] }
    issue_type_to_projects_map = defaultdict(list)
    all_issue_type_names = set()

    # --- Step 1: Get all issue types in the instance ---
    # This gives us the master list of all possible issue types.
    try:
        print("\nFetching all available issue types in the instance...")
        all_instance_issue_types = make_jira_request("rest/api/3/issuetype", auth)
        all_issue_type_names = {it['name'] for it in all_instance_issue_types}
        print(f"Found {len(all_issue_type_names)} total issue types.")
    
    except requests.exceptions.RequestException as e:
        print(f"Error: Could not fetch the instance's issue types.")
        sys.exit(1)

    # --- Step 2: Get all projects and their associated issue types ---
    try:
        print("\nFetching all projects (handles pagination)...")
        
        all_projects = []
        start_at = 0
        max_results = 50
        is_last = False

        # Handle pagination for project search
        while not is_last:
            params = {'startAt': start_at, 'maxResults': max_results}
            response = make_jira_request("rest/api/3/project/search", auth, params=params)
            
            all_projects.extend(response.get('values', []))
            is_last = response.get('isLast', True) # Default to True if 'isLast' is missing
            start_at += len(response.get('values', [])) # Increment by items received
            
            if not is_last:
                print(f"  Fetched {len(all_projects)} projects so far...")

        print(f"Found {len(all_projects)} total projects. Checking issue types for each...")
        
        for project in all_projects:
            project_key = project.get('key')
            project_name = project.get('name', 'Unknown Name')
            if not project_key:
                print("  - WARNING: Found a project with no key. Skipping.")
                continue

            try:
                # We fetch the full project details to get its issueTypes attribute
                print(f"  - Processing: {project_key} ({project_name})")
                full_project = make_jira_request(f"rest/api/3/project/{project_key}", auth)
                
                if 'issueTypes' not in full_project:
                    print(f"  - WARNING: Could not read issue types for project {project_key}. Skipping.")
                    continue
                
                # Add this project to the map for each issue type it uses
                for issue_type in full_project.get('issueTypes', []):
                    if 'name' in issue_type:
                        issue_type_to_projects_map[issue_type['name']].append(project_key)
                    
            except requests.exceptions.HTTPError as proj_e:
                if proj_e.response.status_code in [403, 401]:
                    print(f"  - ERROR: No permission to view project {project_key}. Skipping.")
                else:
                    # Error already printed by helper, just note the skip
                    print(f"  - ERROR: Skipping project {project_key} due to HTTP error.")
            except Exception as e:
                 print(f"  - ERROR: An unexpected error occurred with project {project_key}: {e}. Skipping.")

    except requests.exceptions.RequestException as e:
        print(f"Error: Could not fetch the project list.")
        sys.exit(1)

    # --- Step 3: Report on unused issue types ---
    print("\n--- Analysis Complete ---")
    
    unused_types = []
    
    # Check our master list against the projects we found
    for issue_type_name in all_issue_type_names:
        # If the issue type name is not in our map, it means no projects
        # (that we could access) are using it.
        if issue_type_name not in issue_type_to_projects_map:
            unused_types.append(issue_type_name)

    if not unused_types:
        print("\n=== Report ===")
        print("All issue types are used by at least one project (that you have access to).")
    else:
        print("\n=== Report: Unused Issue Types ===")
        print("The following issue types were not found in any project schemas (that you have access to):")
        for type_name in sorted(unused_types):
            print(f"- {type_name}")

    # --- Print the full mapping ---
    print("\n\n=== Full Report: Issue Type to Project Mapping ===")
    for issue_type_name in sorted(all_issue_type_names):
        projects = issue_type_to_projects_map.get(issue_type_name, [])
        if projects:
            print(f"\n{issue_type_name} (Used by {len(projects)} project(s)):")
            print(f"  > {', '.join(sorted(projects))}")
        else:
            print(f"\n{issue_type_name} (Used by 0 projects)")


if __name__ == "__main__":
    main()