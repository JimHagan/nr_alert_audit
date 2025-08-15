from flask import Flask, request, render_template_string, make_response, redirect, url_for
import alert_analyzer_lib as analyzer
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)

# Simple in-memory cache to store results temporarily
results_cache = {}

# HTML template for the user interface form
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Relic Alert Analyzer</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background-color: #f0f2f5; }
        .container { max-width: 600px; margin: 40px auto; padding: 30px; background-color: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        h1 { color: #1d2129; text-align: center; margin-bottom: 20px; }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-weight: 600; margin-bottom: 5px; color: #4b4f56; }
        input[type="text"], input[type="date"] { width: 100%; padding: 10px; border: 1px solid #dddfe2; border-radius: 6px; box-sizing: border-box; }
        .btn { display: block; width: 100%; padding: 12px; background-color: #1877f2; color: #fff; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; text-align: center; text-decoration: none; }
        .btn:hover { background-color: #166fe5; }
        .notice { background-color: #fffbe2; border: 1px solid #ffe8a5; padding: 15px; border-radius: 6px; margin-top: 20px; color: #7d6608; }
        .results { text-align: center; }
        .results h2 { color: #1d2129; }
        .results p { color: #4b4f56; }
        .download-links { display: flex; gap: 15px; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>New Relic Alert Analyzer</h1>
        <form action="/run" method="post">
            <div class="form-group">
                <label for="api_key">New Relic User API Key:</label>
                <input type="text" id="api_key" name="api_key" required>
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

RESULTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Analysis Results</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 0; background-color: #f0f2f5; }
        .container { max-width: 600px; margin: 40px auto; padding: 30px; background-color: #fff; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; }
        h1 { color: #1d2129; }
        p { color: #4b4f56; font-size: 18px; }
        .btn { display: inline-block; width: 45%; padding: 12px; background-color: #42b72a; color: #fff; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; cursor: pointer; text-align: center; text-decoration: none; }
        .btn:hover { background-color: #36a420; }
        .btn-secondary { background-color: #6c757d; }
        .btn-secondary:hover { background-color: #5a6268; }
        .download-links { display: flex; gap: 15px; margin-top: 20px; justify-content: center; }
    </style>
</head>
<body>
    <div class="container">
        <h1>✅ Reports Generated</h1>
        <p>Your analysis is complete. Download your CSV files below.</p>
        <div class="download-links">
            <a href="{{ url_for('download_file', job_id=job_id, file_type='alerts') }}" class="btn">Download Alerts CSV</a>
            <a href="{{ url_for('download_file', job_id=job_id, file_type='audit') }}" class="btn btn-secondary">Download Audit CSV</a>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/run', methods=['POST'])
def run_analysis():
    api_key = request.form['api_key']
    account_id = int(request.form['account_id'])
    start_date = request.form['start_date']
    end_date = request.form['end_date']

    if (start_date and not end_date) or (not start_date and end_date):
        return "Error: Both start and end dates must be provided together.", 400

    if not start_date and not end_date:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)
        start_date = start_dt.strftime('%Y-%m-%d')
        end_date = end_dt.strftime('%Y-%m-%d')

    # --- Run Analysis ---
    policies = analyzer.fetch_all_data(api_key, account_id, analyzer.POLICIES_QUERY, "alerts.policiesSearch", "policies")
    conditions = analyzer.fetch_all_data(api_key, account_id, analyzer.CONDITIONS_QUERY, "alerts.nrqlConditionsSearch", "nrqlConditions")
    audit_events = analyzer.fetch_audit_events(api_key, account_id, start_date, end_date)

    if policies is None or conditions is None:
        return "Error: Failed to fetch alert policies or conditions. Check API key and Account ID.", 500

    filtered_conditions = analyzer.filter_conditions_by_date(conditions, start_date, end_date)
    
    alerts_csv = analyzer.generate_alerts_csv_data(policies, filtered_conditions, account_id)
    audit_csv = analyzer.generate_audit_csv_data(audit_events)

    job_id = str(uuid.uuid4())
    results_cache[job_id] = {
        'alerts': alerts_csv or "No alert data found for the selected range.",
        'audit': audit_csv or "No audit event data found for the selected range."
    }

    return redirect(url_for('show_results', job_id=job_id))

@app.route('/results/<job_id>')
def show_results(job_id):
    if job_id not in results_cache:
        return "Results not found or expired.", 404
    return render_template_string(RESULTS_TEMPLATE, job_id=job_id)

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
    
    # Clean up the cache after download if desired, but might be better to let it expire
    # del results_cache[job_id] 
    
    return response

if __name__ == '__main__':
    app.run(debug=True)
