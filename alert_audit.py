import os
import requests
import json
import csv
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

# The New Relic GraphQL API endpoint
NR_GRAPHQL_URL = "https://api.newrelic.com/graphql"

# Query for policies
POLICIES_QUERY = """
query($accountId: Int!, $cursor: String) {
  actor {
    account(id: $accountId) {
      alerts {
        policiesSearch(cursor: $cursor) {
          policies { id name }
          nextCursor
        }}}}}
"""

# Query for conditions
CONDITIONS_QUERY = """
query($accountId: Int!, $cursor: String) {
  actor {
    account(id: $accountId) {
      alerts {
        nrqlConditionsSearch(cursor: $cursor) {
          nrqlConditions { policyId id name updatedAt }
          nextCursor
        }}}}}
"""

# Query to run a generic NRQL query (used for Audit Events)
NRQL_QUERY = """
query($accountId: Int!, $nrqlQuery: Nrql!) {
    actor {
        account(id: $accountId) {
            nrql(query: $nrqlQuery, timeout: 120) {
                results
            }
        }
    }
}
"""

def fetch_all_data(api_key, account_id, query, data_path, entity_key):
    """Generic function to fetch all paginated data from the New Relic GraphQL API."""
    headers = {"Content-Type": "application/json", "API-Key": api_key}
    all_entities = []
    cursor = None
    has_next_page = True

    while has_next_page:
        variables = {"accountId": account_id, "cursor": cursor}
        payload = {"query": query, "variables": variables}
        try:
            response = requests.post(NR_GRAPHQL_URL, headers=headers, data=json.dumps(payload), timeout=15)
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                print(f"GraphQL Error: {data['errors']}")
                return None
            path_parts = data_path.split('.')
            result_data = data["data"]["actor"]["account"]
            for part in path_parts:
                result_data = result_data.get(part, {})
            entities_page = result_data.get(entity_key, [])
            all_entities.extend(entities_page)
            cursor = result_data.get("nextCursor")
            if not cursor:
                has_next_page = False
        except requests.exceptions.RequestException as e:
            print(f"Error making API request: {e}")
            return None
    return all_entities

def fetch_audit_events(api_key, account_id, start_date_str, end_date_str):
    """Fetches alert-related audit events using an NRQL query."""
    # REVISED: SINCE and UNTIL clauses are now always provided by main()
    nrql_query = f"FROM NrAuditEvent SELECT * WHERE actionIdentifier LIKE 'alerts%' SINCE '{start_date_str} 00:00:00' UNTIL '{end_date_str} 23:59:59'"
    
    headers = {"Content-Type": "application/json", "API-Key": api_key}
    variables = {"accountId": account_id, "nrqlQuery": nrql_query}
    payload = {"query": NRQL_QUERY, "variables": variables}

    try:
        response = requests.post(NR_GRAPHQL_URL, headers=headers, data=json.dumps(payload), timeout=30)
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            print(f"GraphQL Error on Audit Query: {data['errors']}")
            return None
        return data.get("data", {}).get("actor", {}).get("account", {}).get("nrql", {}).get("results", [])
    except requests.exceptions.RequestException as e:
        print(f"Error making API request for audit events: {e}")
        return None

def write_audit_csv(events, filename="nr_audit_event.csv"):
    """Writes the audit event data to a CSV file."""
    if not events:
        print("\nNo audit events found to write to CSV.")
        return

    fieldnames = [
        'timestamp', 'actionIdentifier', 'actorEmail', 'actorId',
        'targetId', 'targetType', 'targetName', 'description', 'changes'
    ]

    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            for event in events:
                if 'timestamp' in event:
                    event['timestamp'] = datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                for field in ['description', 'changes']:
                    if field in event and isinstance(event[field], (dict, list)):
                        event[field] = json.dumps(event[field])
                writer.writerow(event)
        print(f"✅ Successfully wrote {len(events)} rows to {filename}")
    except IOError as e:
        print(f"Error writing to audit file {filename}: {e}")

def filter_conditions_by_date(conditions, start_date_str, end_date_str):
    """Filters a list of conditions based on their 'updatedAt' timestamp."""
    if not start_date_str and not end_date_str:
        return conditions
    start_ms, end_ms = None, None
    date_format = '%Y-%m-%d'
    try:
        if start_date_str:
            start_dt = datetime.strptime(start_date_str, date_format)
            start_ms = start_dt.timestamp() * 1000
            print(f"Filtering conditions updated on or after {start_date_str}...")
        if end_date_str:
            end_dt = datetime.strptime(end_date_str, date_format).replace(hour=23, minute=59, second=59)
            end_ms = end_dt.timestamp() * 1000
            print(f"Filtering conditions updated on or before {end_date_str}...")
    except ValueError as e:
        print(f"Error: Invalid date format. Please use YYYY-MM-DD. Details: {e}")
        return []
    filtered_conditions = []
    for cond in conditions:
        updated_at = cond.get('updatedAt')
        if not updated_at: continue
        passes_filter = True
        if start_ms and updated_at < start_ms: passes_filter = False
        if end_ms and updated_at > end_ms: passes_filter = False
        if passes_filter: filtered_conditions.append(cond)
    return filtered_conditions

def write_csv_output(policies, conditions, account_id, filename="new_relic_alerts.csv"):
    """Processes the fetched data and writes it to a CSV file."""
    if not conditions:
        print("\nNo conditions found to write to CSV after filtering.")
        return
    policy_map = {int(p['id']): p['name'] for p in policies}
    policy_last_updates = defaultdict(int)
    for c in conditions:
        policy_id = int(c['policyId'])
        update_time = c.get('updatedAt', 0)
        policy_last_updates[policy_id] = max(policy_last_updates[policy_id], update_time)
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'condition_name', 'condition_id', 'policy_name', 'policy_id',
                'condition_last_update', 'policy_last_update', 'condition_url', 'policy_url'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for condition in sorted(conditions, key=lambda c: c.get('name', '').lower()):
                policy_id = int(condition['policyId'])
                condition_id = int(condition['id'])
                cond_updated_at = condition.get('updatedAt')
                cond_update_str = datetime.fromtimestamp(cond_updated_at / 1000).strftime('%Y-%m-%d %H:%M:%S') if cond_updated_at else 'N/A'
                policy_updated_at = policy_last_updates.get(policy_id)
                policy_update_str = datetime.fromtimestamp(policy_updated_at / 1000).strftime('%Y-%m-%d %H:%M:%S') if policy_updated_at else 'N/A'
                writer.writerow({
                    'condition_name': condition.get('name', 'N/A'),
                    'condition_id': condition_id,
                    'policy_name': policy_map.get(policy_id, 'Policy Not Found'),
                    'policy_id': policy_id,
                    'condition_last_update': cond_update_str,
                    'policy_last_update': policy_update_str,
                    'condition_url': f"https://one.newrelic.com/alerts-ai/policy/{policy_id}/condition/{condition_id}?account={account_id}",
                    'policy_url': f"https://one.newrelic.com/alerts-ai/policy/{policy_id}?account={account_id}"
                })
        print(f"\n✅ Successfully wrote {len(conditions)} rows to {filename}")
    except IOError as e:
        print(f"Error writing to file {filename}: {e}")

def main():
    """Main function to run the program."""
    parser = argparse.ArgumentParser(description="Fetch New Relic alert policies, conditions, and audit events.")
    parser.add_argument('--start', dest='update_range_start', required=False, help="The start of the date range (YYYY-MM-DD).")
    parser.add_argument('--end', dest='update_range_end', required=False, help="The end of the date range (YYYY-MM-DD).")
    args = parser.parse_args()

    # --- REVISED: Date handling logic ---
    start_date_str = args.update_range_start
    end_date_str = args.update_range_end

    # Rule 2: Enforce that both start and end dates must be provided together.
    if (start_date_str and not end_date_str) or (not start_date_str and end_date_str):
        print("\n❌ Error: Both --start and --end arguments must be provided together.")
        parser.print_help()
        return

    # Rule 1: Default to the last 30 days if no date range is provided.
    if not start_date_str and not end_date_str:
        print("No date range specified. Defaulting to the last 30 days.")
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)
        start_date_str = start_dt.strftime('%Y-%m-%d')
        end_date_str = end_dt.strftime('%Y-%m-%d')
    # --- End of revised logic ---

    api_key = os.getenv("NEW_RELIC_API_KEY")
    account_id_str = os.getenv("NEW_RELIC_ACCOUNT_ID")
    if not api_key or not account_id_str:
        print("Error: Please set environment variables 'NEW_RELIC_API_KEY' and 'NEW_RELIC_ACCOUNT_ID'")
        return
    try:
        account_id = int(account_id_str)
    except ValueError:
        print("Error: 'NEW_RELIC_ACCOUNT_ID' must be an integer.")
        return

    # --- Section 1: Fetch Policies and Conditions ---
    print("\nFetching policies...")
    policies_list = fetch_all_data(api_key, account_id, POLICIES_QUERY, "alerts.policiesSearch", "policies")
    if policies_list is None: return
    
    print("Fetching NRQL conditions...")
    conditions_list = fetch_all_data(api_key, account_id, CONDITIONS_QUERY, "alerts.nrqlConditionsSearch", "nrqlConditions")
    if conditions_list is None: return
    
    print(f"Successfully fetched {len(policies_list)} policies and {len(conditions_list)} conditions.")
    filtered_conditions = filter_conditions_by_date(conditions_list, start_date_str, end_date_str)
    write_csv_output(policies_list, filtered_conditions, account_id)

    # --- Section 2: Fetch Audit Events ---
    print("\nFetching alert-related audit events...")
    audit_events = fetch_audit_events(api_key, account_id, start_date_str, end_date_str)
    if audit_events is not None:
        write_audit_csv(audit_events)

if __name__ == "__main__":
    main()