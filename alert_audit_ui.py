from flask import Flask, request, render_template_string, make_response, redirect, url_for, jsonify
import alert_analyzer_lib as analyzer
import uuid
import threading
from datetime import datetime, timedelta

app = Flask(__name__)

# Simple in-memory cache to store job status and results temporarily
results_cache = {}

# --- HTML Templates ---

# Template for the main input form
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Relic Alert Analyzer</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background-color: #f0f2f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { max-width: 600px; width: 100%; margin: 20px; padding: 30px; background-color: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        h1 { color: #1d2129; text-align: center; margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-weight: 600; margin-bottom: 5px; color: #4b4f56; }
        input[type="text"], input[type="password"], input[type="date"] { width: 100%; padding: 10px; border: 1px solid #dddfe2; border-radius: 6px; box-sizing: border-box; }
        .btn { display: block; width: 100%; padding: 12px; background-color: #1877f2; color: #fff; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; text-align: center; text-decoration: none; }
        .btn:hover { background-color: #166fe5; }
        .notice { background-color: #fffbe2; border: 1px solid #ffe8a5; padding: 15px; border-radius: 6px; margin-top: 20px; color: #7d6608; }
    </style>
</head>
<body>
    <div class="container">
        <h1>New Relic Alert Analyzer</h1>
        <form action="/run" method="post">
            <div class="form-group">
                <label for="api_key">New Relic User API Key:</label>
                <input type="password" id="api_key" name="api_key" required>
            </div>
            <div class="form-group">
                <label for="account_id">New Relic Account ID:</label>
                <input type="text" id="account_id" name="account_id" required>
            </div>
            <div class="form-group">
                <label for="start_date">Start Date:</label>
                <input type="date" id="start_date" name="start_date">
            </div>
            <div class="form-group">
                <label for="end_date">End Date:</label>
                <input type="date" id="end_date" name="end_date">
            </div>
            <button type="submit" class="btn">Generate Reports</button>
        </form>
        <div class="notice">
            <strong>Note:</strong> If no date range is provided, the analysis will default to the last 30 days. If you provide one date, you must provide the other.
        </div>
    </div>
</body>
</html>
"""

# Template for the progress page
PROGRESS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Processing...</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background-color: #f0f2f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { max-width: 600px; margin: 40px auto; padding: 40px; background-color: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; }
        h1 { color: #1d2129; }
        #status { color: #4b4f56; font-size: 18px; margin-top: 10px; font-weight: 500; }
        .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #1877f2; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="container">
        <h1>Processing Your Request</h1>
        <div class="spinner"></div>
        <p id="status">Initializing...</p>
    </div>
    <script>
        const jobId = "{{ job_id }}";
        const statusElement = document.getElementById('status');
        
        function checkStatus() {
            fetch(`/status/${jobId}`)
                .then(response => response.json())
                .then(data => {
                    statusElement.textContent = data.status || '...';
                    if (data.status === 'complete') {
                        window.location.href = `/results/${jobId}`;
                    } else if (data.status.startsWith('Error:')) {
                        statusElement.style.color = 'red';
                    } else {
                        setTimeout(checkStatus, 1500); // Poll every 1.5 seconds
                    }
                })
                .catch(err => {
                    statusElement.textContent = 'Error checking status.';
                    statusElement.style.color = 'red';
                });
        }
        
        // Start checking after a brief delay
        setTimeout(checkStatus, 500);
    </script>
</body>
</html>
"""

# Template for the final results and download page
RESULTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analysis Results</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background-color: #f0f2f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; }
        .container { max-width: 600px; margin: 40px auto; padding: 30px; background-color: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; }
        h1 { color: #1d2129; }
        .summary { background-color: #f0f2f5; border-radius: 6px; padding: 15px; margin: 20px 0; }
        .summary p { color: #4b4f56; font-size: 16px; margin: 5px 0; }
        .summary strong { color: #1d2129; }
        .btn { display: inline-block; width: 45%; padding: 12px; background-color: #42b72a; color: #fff; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; text-align: center; text-decoration: none; }
        .btn:hover { background-color: #36a420; }
        .download-links { display: flex; gap: 15px; margin-top: 20px; justify-content: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>✅ Reports Generated</h1>
        <div class="summary">
            <p><strong>Policies Found:</strong> {{ counts.policies }} ({{ counts.policies_changed }} Changed)</p>
            <p><strong>Conditions Found:</strong> {{ counts.conditions }} ({{ counts.conditions_changed }} Changed)</p>
            <p><strong>Audit Events Found:</strong> {{ counts.audit_events }}</p>
        </div>
        <p>Your analysis is complete. Download your CSV files below.</p>
        <div class="download-links">
            <a href="{{ url_for('download_file', job_id=job_id, file_type='alerts') }}" class="btn">Download Alerts CSV</a>
            <a href="{{ url_for('download_file', job_id=job_id, file_type='audit') }}" class="btn">Download Audit CSV</a>
        </div>
    </div>
</body>
</html>
"""

def _run_analysis_background(job_id, api_key, account_id, start_date, end_date):
    """This function runs in a background thread to avoid blocking the UI."""
    try:
        results_cache[job_id]['status'] = 'Fetching alert policies...'
        policies = analyzer.fetch_all_data(api_key, account_id, analyzer.POLICIES_QUERY, "alerts.policiesSearch", "policies")
        if policies is None:
            raise Exception("Failed to fetch policies. Check API Key/Account ID.")
        results_cache[job_id]['counts']['policies'] = len(policies)

        results_cache[job_id]['status'] = f'Found {len(policies)} policies. Fetching conditions...'
        conditions = analyzer.fetch_all_data(api_key, account_id, analyzer.CONDITIONS_QUERY, "alerts.nrqlConditionsSearch", "nrqlConditions")
        if conditions is None:
            raise Exception("Failed to fetch conditions.")
        results_cache[job_id]['counts']['conditions'] = len(conditions)

        results_cache[job_id]['status'] = f'Found {len(conditions)} conditions. Fetching audit events...'
        audit_events = analyzer.fetch_audit_events(api_key, account_id, start_date, end_date)
        if audit_events is None:
            raise Exception("Failed to fetch audit events.")
        results_cache[job_id]['counts']['audit_events'] = len(audit_events)
        
        results_cache[job_id]['status'] = 'Processing data and generating CSV files...'
        filtered_conditions = analyzer.filter_conditions_by_date(conditions, start_date, end_date)
        
        # --- NEW: Calculate changed counts ---
        results_cache[job_id]['counts']['conditions_changed'] = len(filtered_conditions)
        changed_policy_ids = {int(cond['policyId']) for cond in filtered_conditions}
        results_cache[job_id]['counts']['policies_changed'] = len(changed_policy_ids)
        # --- End of new logic ---

        alerts_csv = analyzer.generate_alerts_csv_data(policies, filtered_conditions, account_id)
        audit_csv = analyzer.generate_audit_csv_data(audit_events)

        results_cache[job_id]['alerts'] = alerts_csv or "No alert data found for the selected range."
        results_cache[job_id]['audit'] = audit_csv or "No audit event data found for the selected range."
        results_cache[job_id]['status'] = 'complete'

    except Exception as e:
        results_cache[job_id]['status'] = f"Error: {e}"


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/run', methods=['POST'])
def run_analysis():
    api_key = request.form['api_key']
    account_id_str = request.form['account_id']
    start_date = request.form['start_date']
    end_date = request.form['end_date']

    if (start_date and not end_date) or (not start_date and end_date):
        return "Error: Both start and end dates must be provided together.", 400
    
    try:
        account_id = int(account_id_str)
    except ValueError:
        return "Error: Account ID must be a number.", 400

    if not start_date and not end_date:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)
        start_date = start_dt.strftime('%Y-%m-%d')
        end_date = end_dt.strftime('%Y-%m-%d')

    job_id = str(uuid.uuid4())
    results_cache[job_id] = {'status': 'Initializing...', 'counts': {}}

    thread = threading.Thread(target=_run_analysis_background, args=(job_id, api_key, account_id, start_date, end_date))
    thread.start()

    return redirect(url_for('show_progress', job_id=job_id))

@app.route('/progress/<job_id>')
def show_progress(job_id):
    return render_template_string(PROGRESS_TEMPLATE, job_id=job_id)

@app.route('/status/<job_id>')
def get_status(job_id):
    status_info = results_cache.get(job_id, {'status': 'Job not found.'})
    return jsonify(status=status_info.get('status'))

@app.route('/results/<job_id>')
def show_results(job_id):
    if job_id not in results_cache or results_cache[job_id]['status'] != 'complete':
        return redirect(url_for('show_progress', job_id=job_id))
    
    counts = results_cache[job_id].get('counts', {})
    return render_template_string(RESULTS_TEMPLATE, job_id=job_id, counts=counts)

@app.route('/download/<file_type>/<job_id>')
def download_file(file_type, job_id):
    if job_id not in results_cache:
        return "File not found or expired.", 404

    result_data = results_cache[job_id].get(file_type)
    if not result_data:
        return f"No {file_type} data available.", 404

    filename = f"new_relic_{file_type}.csv"
    response = make_response(result_data)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/csv"
    
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5001)
