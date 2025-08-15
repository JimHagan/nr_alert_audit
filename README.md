# New Relic Alert Audit

This Python utility helps organizations audit changes to their New Relic alert configurations. By querying both the New Relic Alerts API and the Audit Log API, it provides a clear picture of which alert conditions have been modified within a specific timeframe and which users may have changed them. This is invaluable for auditing, change management, and troubleshooting unexpected alert behavior.

The script generates two detailed CSV files, providing both a high-level summary of changed conditions and a low-level dump of all alert-related audit events.

---

## 1. Prerequisites

Before you begin, ensure you have the following:

* **Python 3.6+** installed on your system.
* A **New Relic User API Key**. This is required for authentication.
* Your **New Relic Account ID**.

You must set your credentials as environment variables for the script to work:
* `NEW_RELIC_API_KEY`
* `NEW_RELIC_ACCOUNT_ID`

---

## 2. Setup and Installation

It is highly recommended to run this script within a Python virtual environment to manage its dependencies.



### Step 1: Create and Activate the Virtual Environment

1.  **Create the environment:**
    ```bash
    python3 -m venv venv
    ```

3.  **Activate the environment:**
    * **On macOS / Linux:**
        ```bash
        source venv/bin/activate
        ```
    * **On Windows (Command Prompt):**
        ```cmd
        venv\Scripts\activate
        ```

### Step 2: Install Dependencies
Install dependencies from the provided requirements.txt file:
```bash
pip install -r requirements.txt
```

---

## 3. How to Run the Program

Invoke the script from your terminal using the `python3` command. You can optionally provide a date range to filter the results.

### Command Structure
```bash
NEW_RELIC_API_KEY="YOUR_KEY" NEW_RELIC_ACCOUNT_ID="YOUR_ID" python3 get_nr_alerts.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

### Date Parameters
* The date format for both `--start` and `--end` **must be `YYYY-MM-DD`**.
* If you provide one date parameter (`--start` or `--end`), you **must** provide the other.
* **Default Behavior**: If no date range is provided, the script will automatically default to the **last 30 days**. A notice will be printed to the console to confirm this.

### Examples
* **Run with a specific date range:**
    ```bash
    NEW_RELIC_API_KEY="..." NEW_RELIC_ACCOUNT_ID="..." python3 get_nr_alerts.py --start 2025-07-01 --end 2025-07-31
    ```
* **Run using the default 30-day range:**
    ```bash
    NEW_RELIC_API_KEY="..." NEW_RELIC_ACCOUNT_ID="..." python3 get_nr_alerts.py
    ```

---

## 4. Output Files

The script generates two CSV files in the same directory.

### a. `new_relic_alerts.csv`
This file lists all alert conditions that were last updated within the specified (or default) date range. It provides a clean, high-level summary of what changed.

| Field                   | Description                                                              |
| ----------------------- | ------------------------------------------------------------------------ |
| `condition_name`        | The name of the alert condition.                                         |
| `condition_id`          | The unique ID for the condition.                                         |
| `policy_name`           | The name of the alert policy the condition belongs to.                   |
| `policy_id`             | The unique ID for the policy.                                            |
| `condition_last_update` | The timestamp when the condition was last modified.                      |
| `policy_last_update`    | The most recent update timestamp among all conditions within that policy.|
| `condition_url`         | A direct URL to the condition in the New Relic UI.                       |
| `policy_url`            | A direct URL to the policy in the New Relic UI.                          |

### b. `nr_audit_event.csv`
This file is a detailed dump of all `NrAuditEvent` records where the `actionIdentifier` starts with `alerts`. It provides the raw data needed to investigate who made changes and what those changes were.

| Field              | Description                                                              |
| ------------------ | ------------------------------------------------------------------------ |
| `timestamp`        | The timestamp of the audit event.                                        |
| `actionIdentifier` | The specific action that was logged (e.g., `alerts_nrql_condition.update`).|
| `actorEmail`       | The email of the user who performed the action.                          |
| `actorId`          | The ID of the user or API key that performed the action.                 |
| `targetId`         | The ID of the resource that was changed (e.g., a condition ID).          |
| `targetType`       | The type of resource that was changed.                                   |
| `targetName`       | The name of the resource that was changed.                               |
| `description`      | A JSON string describing the event.                                      |
| `changes`          | A JSON string detailing the specific fields that were modified.          |

---

## 5. Audit Log Query

To retrieve the data for `nr_audit_event.csv`, the script constructs and executes the following NRQL query via the API. The `SINCE` and `UNTIL` clauses are populated based on the command-line arguments or the 30-day default.

```nrql
FROM NrAuditEvent SELECT * WHERE actionIdentifier LIKE 'alerts%' SINCE 'YYYY-MM-DD 00:00:00' UNTIL 'YYYY-MM-DD 23:59:59'
```

---

## 6. Additional Resources

For more detailed information, please refer to the official New Relic documentation:

1.  **NrAuditEvent**: [Introduction to the audit log](https://docs.newrelic.com/docs/accounts/accounts/account-maintenance/query-account-audit-logs-nrauditevent/)
2.  **NerdGraph (GraphQL) API**: [Introduction to New Relic NerdGraph](https://docs.newrelic.com/docs/apis/nerdgraph/get-started/introduction-new-relic-nerdgraph/)
