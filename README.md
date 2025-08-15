# New Relic Alert Change Analyzer

This Python utility helps organizations analyze changes to their New Relic alert configurations. It can be run as a command-line tool or as a local web application.

By querying both the New Relic Alerts API and the Audit Log API, it provides a clear picture of which alert conditions have been modified within a specific timeframe and which users may have changed them. This is invaluable for auditing, change management, and troubleshooting unexpected alert behavior.

The script generates two detailed CSV files, providing both a high-level summary of changed conditions and a low-level dump of all alert-related audit events.

---

## 1. Prerequisites

Before you begin, ensure you have the following:

* **Python 3.6+** installed on your system.
* A **New Relic User API Key**. This is required for authentication.
* Your **New Relic Account ID**.

---

## 2. Setup and Installation

It is highly recommended to run this script within a Python virtual environment to manage its dependencies.



### Step 1: Create and Activate the Virtual Environment

1.  **Create the environment:**
    ```bash
    python3 -m venv venv
    ```

2.  **Activate the environment:**
    * **On macOS / Linux:**
        ```bash
        source venv/bin/activate
        ```
    * **On Windows (Command Prompt):**
        ```cmd
        venv\Scripts\activate
        ```

### Step 2: Install Dependencies
With your virtual environment active, install the required packages from the provided requirements.txt file:
```bash
pip install -r requirements.txt
```

---

## 3. How to Run the Program

You can run this tool in two ways: as a command-line script or as a web UI.

### A. Running the Web UI

The web UI provides a user-friendly form to enter your credentials and date range.

1.  **Start the web server:**
    ```bash
    python3 alert_audit_ui.py
    ```
2.  **Open your browser:** Navigate to `http://127.0.0.1:5000`.
3.  **Fill out the form** with your API Key, Account ID, and desired date range.
4.  **Click "Generate Reports"**. You will be taken to a new page where you can download your two CSV files.

### B. Running in Command-Line Mode

For automation or terminal-based workflows, use the `get_nr_alerts.py` script.

1.  **Set Environment Variables:**
    * **On macOS / Linux:**
        ```bash
        export NEW_RELIC_API_KEY="YOUR_KEY"
        export NEW_RELIC_ACCOUNT_ID="YOUR_ID"
        ```
    * **On Windows (Command Prompt):**
        ```cmd
        set NEW_RELIC_API_KEY="YOUR_KEY"
        set NEW_RELIC_ACCOUNT_ID="YOUR_ID"
        ```

2.  **Run the script:**
    ```bash
    python3 get_nr_alerts.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]
    ```

#### Date Parameters (CLI)
* The date format for both `--start` and `--end` **must be `YYYY-MM-DD`**.
* If you provide one date parameter, you **must** provide the other.
* **Default Behavior**: If no date range is provided, the script will automatically default to the **last 30 days**.

---

## 4. Output Files

The script generates two CSV files.

### a. `new_relic_alerts.csv`
This file lists all alert conditions that were last updated within the specified (or default) date range.

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
This file is a detailed dump of all `NrAuditEvent` records where the `actionIdentifier` starts with `alerts`.

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

## 5. Additional Resources

For more detailed information, please refer to the official New Relic documentation:

1.  **NrAuditEvent**: [Introduction to the audit log](https://docs.newrelic.com/docs/telemetry-data-platform/data-ingest-apis/manage-data/introduction-audit-log/)
2.  **NerdGraph (GraphQL) API**: [Introduction to New Relic NerdGraph](https://docs.newrelic.com/docs/apis/nerdgraph/get-started/introduction-new-relic-nerdgraph/)
