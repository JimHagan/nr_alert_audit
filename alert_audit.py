import os
import argparse
from datetime import datetime, timedelta
import alert_analyzer_lib as analyzer

def main():
    """Main function to run the command-line program."""
    parser = argparse.ArgumentParser(description="Fetch New Relic alert policies, conditions, and audit events.")
    parser.add_argument('--start', dest='update_range_start', required=False, help="The start of the date range (YYYY-MM-DD).")
    parser.add_argument('--end', dest='update_range_end', required=False, help="The end of the date range (YYYY-MM-DD).")
    args = parser.parse_args()

    # --- Date handling logic ---
    start_date_str = args.update_range_start
    end_date_str = args.update_range_end

    if (start_date_str and not end_date_str) or (not start_date_str and end_date_str):
        print("\n❌ Error: Both --start and --end arguments must be provided together.")
        parser.print_help()
        return

    if not start_date_str and not end_date_str:
        print("\nNOTICE: No date range specified. The script will default to the last 30 days.")
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)
        start_date_str = start_dt.strftime('%Y-%m-%d')
        end_date_str = end_dt.strftime('%Y-%m-%d')

    # --- Get Credentials ---
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
    policies = analyzer.fetch_all_data(api_key, account_id, analyzer.POLICIES_QUERY, "alerts.policiesSearch", "policies")
    if policies is None: return
    
    print("Fetching NRQL conditions...")
    conditions = analyzer.fetch_all_data(api_key, account_id, analyzer.CONDITIONS_QUERY, "alerts.nrqlConditionsSearch", "nrqlConditions")
    if conditions is None: return
    
    print(f"Successfully fetched {len(policies)} policies and {len(conditions)} conditions.")
    filtered_conditions = analyzer.filter_conditions_by_date(conditions, start_date_str, end_date_str)
    alerts_csv_data = analyzer.generate_alerts_csv_data(policies, filtered_conditions, account_id)
    
    if alerts_csv_data:
        with open("new_relic_alerts.csv", "w") as f:
            f.write(alerts_csv_data)
        print(f"\n✅ Successfully wrote filtered alert conditions to new_relic_alerts.csv")
    else:
        print("\nNo conditions found to write to CSV after filtering.")

    # --- Section 2: Fetch Audit Events ---
    print("\nFetching alert-related audit events...")
    audit_events = analyzer.fetch_audit_events(api_key, account_id, start_date_str, end_date_str)
    if audit_events:
        audit_csv_data = analyzer.generate_audit_csv_data(audit_events)
        with open("nr_audit_event.csv", "w") as f:
            f.write(audit_csv_data)
        print(f"✅ Successfully wrote {len(audit_events)} audit events to nr_audit_event.csv")
    else:
        print("\nNo audit events found to write to CSV.")

if __name__ == "__main__":
    main()
