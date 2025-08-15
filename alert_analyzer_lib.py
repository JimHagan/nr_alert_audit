import requests
import json
import csv
import io
from datetime import datetime

# The New Relic GraphQL API endpoint
NR_GRAPHQL_URL = "https://api.newrelic.com/graphql"

# --- GraphQL Queries ---
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

# --- Data Fetching Functions ---

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

# --- Data Processing & CSV Generation ---

def filter_conditions_by_date(conditions, start_date_str, end_date_str):
    """Filters a list of conditions based on their 'updatedAt' timestamp."""
    start_ms, end_ms = None, None
    date_format = '%Y-%m-%d'
    try:
        start_dt = datetime.strptime(start_date_str, date_format)
        start_ms = start_dt.timestamp() * 1000
        end_dt = datetime.strptime(end_date_str, date_format).replace(hour=23, minute=59, second=59)
        end_ms = end_dt.timestamp() * 1000
    except ValueError as e:
        print(f"Error: Invalid date format. Please use YYYY-MM-DD. Details: {e}")
        return []
    
    filtered = [
        cond for cond in conditions if cond.get('updatedAt') and
        start_ms <= cond['updatedAt'] <= end_ms
    ]
    return filtered

def generate_alerts_csv_data(policies, conditions, account_id):
    """Processes alert data and returns it as a CSV string."""
    if not conditions:
        return None
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    header = [
        'condition_name', 'condition_id', 'policy_name', 'policy_id',
        'condition_last_update', 'policy_last_update', 'condition_url', 'policy_url'
    ]
    writer.writerow(header)

    policy_map = {int(p['id']): p['name'] for p in policies}
    
    for condition in sorted(conditions, key=lambda c: c.get('name', '').lower()):
        policy_id = int(condition['policyId'])
        condition_id = int(condition['id'])
        cond_updated_at = condition.get('updatedAt')
        cond_update_str = datetime.fromtimestamp(cond_updated_at / 1000).strftime('%Y-%m-%d %H:%M:%S') if cond_updated_at else 'N/A'
        
        writer.writerow([
            condition.get('name', 'N/A'),
            condition_id,
            policy_map.get(policy_id, 'Policy Not Found'),
            policy_id,
            cond_update_str,
            cond_update_str, # In this simplified model, policy update is the same as the condition
            f"https://one.newrelic.com/alerts-ai/policy/{policy_id}/condition/{condition_id}?account={account_id}",
            f"https://one.newrelic.com/alerts-ai/policy/{policy_id}?account={account_id}"
        ])
    return output.getvalue()

def generate_audit_csv_data(events):
    """Processes audit events and returns them as a CSV string."""
    if not events:
        return None
        
    output = io.StringIO()
    fieldnames = [
        'timestamp', 'actionIdentifier', 'actorEmail', 'actorId',
        'targetId', 'targetType', 'targetName', 'description', 'changes'
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()

    for event in events:
        if 'timestamp' in event:
            event['timestamp'] = datetime.fromtimestamp(event['timestamp'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
        for field in ['description', 'changes']:
            if field in event and isinstance(event[field], (dict, list)):
                event[field] = json.dumps(event[field])
        writer.writerow(event)
    return output.getvalue()
