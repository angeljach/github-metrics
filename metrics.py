import argparse
import os
import requests
import sys
import json
from datetime import datetime, timedelta, timezone
import pandas as pd
from dotenv import load_dotenv

# --- CONFIGURATION ---

# Load environment variables from .env
load_dotenv()
GITHUB_TOKEN = os.getenv("API_METRICS_KEY")
if not GITHUB_TOKEN:
    raise ValueError("API_METRICS_KEY not set in .env file.")

REPO_OWNER = "digitaltitransversal"
REPO_NAME = "spin-spec-apis"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

# --- DATE RANGE CALCULATION ---
def get_last_month_dates():
    today = datetime.now(timezone.utc)
    first_of_current_month = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end_of_last_month = first_of_current_month - timedelta(seconds=1)
    start_of_last_month = end_of_last_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start_of_last_month.isoformat(), end_of_last_month.isoformat()

# --- HELPER FUNCTIONS ---
def load_team_mapping(file_path=None):
    if file_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, 'teams.json')
    try:
        with open(file_path, 'r') as f:
            mapping = json.load(f)
            return {user['github_user']: user['team'] for user in mapping}
    except FileNotFoundError:
        print(f"Error: Team mapping file '{file_path}' not found.")
        return {}

def github_api_request(url, single_object=False):
    if single_object:
        try:
            response = requests.get(url, headers=HEADERS)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Request Error: {e}")
            return {}
    else:
        all_data = []
        page = 1
        while True:
            try:
                paginated_url = f"{url}&page={page}&per_page=100"
                response = requests.get(paginated_url, headers=HEADERS)
                response.raise_for_status()
                data = response.json()
                if not data:
                    break
                all_data.extend(data)
                if 'next' not in response.links:
                    break
                page += 1
            except requests.exceptions.RequestException as e:
                print(f"API Request Error on page {page}: {e}")
                break
        return all_data

def calculate_time_difference(start_str, end_str):
    if not start_str or not end_str:
        return 0
    start = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
    end = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
    return (end - start).total_seconds() / 3600.0

# --- MAIN LOGIC ---
def fetch_and_calculate_metrics(start_date, end_date):
    team_map = load_team_mapping()
    print(f"--- Generating report for period: {start_date} to {end_date} ---")
    pr_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls?state=all"
    prs = github_api_request(pr_url)
    # Convert start_date and end_date to datetime for filtering
    # Ensure start_dt and end_dt are offset-aware (UTC)
    def to_utc(dt_str):
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    start_dt = to_utc(start_date)
    end_dt = to_utc(end_date)
    filtered_prs = []
    for pr in prs:
        created_at = pr.get('created_at')
        if created_at:
            created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            if start_dt <= created_dt <= end_dt:
                filtered_prs.append(pr)
    prs = filtered_prs
    metrics_data = []
    unassigned_users = set()
    print(f"Fetched {len(prs)} Pull Requests in the period.")
    for pr in prs:
        author = pr['user']['login']
        team_name = team_map.get(author, 'Unassigned')
        if team_name == 'Unassigned':
            unassigned_users.add(author)
        pr_details_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/pulls/{pr['number']}"
        pr_details = github_api_request(pr_details_url, single_object=True)
        pr_metrics = {
            'team': team_name,
            'pr_id': pr['number'],
            'author': author,
            'state': pr['state'],
            'merged': pr['merged_at'] is not None,
            'time_to_merge_hours': 0,
            'lines_added': pr_details.get('additions', 0),
            'lines_deleted': pr_details.get('deletions', 0),
        }
        if pr_metrics['merged']:
            time_diff = calculate_time_difference(pr['created_at'], pr['merged_at'])
            pr_metrics['time_to_merge_hours'] = time_diff
        metrics_data.append(pr_metrics)
    if unassigned_users:
        print("\n--- Unassigned Users ---")
        for user in unassigned_users:
            print(user)
    else:
        print("\nNo unassigned users found.")
    if not metrics_data:
        print("No metrics data to process.")
        return
    df = pd.DataFrame(metrics_data)
    team_stats = df.groupby('team').agg(
        total_prs=('pr_id', 'count'),
        merged_prs=('merged', 'sum'),
        total_additions=('lines_added', 'sum'),
        total_deletions=('lines_deleted', 'sum'),
        avg_cycle_time_hours=('time_to_merge_hours', 'mean')
    ).reset_index()
    team_stats['merge_rate_%'] = (team_stats['merged_prs'] / team_stats['total_prs']) * 100
    team_stats['avg_cycle_time_days'] = (team_stats['avg_cycle_time_hours'] / 24).round(2)
    team_stats = team_stats.drop(columns=['avg_cycle_time_hours'])
    team_stats = team_stats.sort_values(by='merge_rate_%', ascending=False)
    # Format output filename with date range
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"{output_dir}/monthly_team_metrics_{start_date}_to_{end_date}.csv"
    # Custom CSV headers
    csv_headers = [
        "Team",
        "Total PRs",
        "Mrg PRs",
        "Total Add",
        "Total Del",
        "Mg R %",
        "Avg Cyc T (d)"
    ]
    team_stats.to_csv(output_filename, index=False, header=csv_headers)
    print("\n--- FINAL REPORT ---")
    print(team_stats.to_string())
    print(f"\nReport successfully saved to {output_filename}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate metrics for GitHub PRs using .env API key.")
    parser.add_argument("--start-date", required=True, help="Start date for metrics (YYYY-MM-DD)")
    parser.add_argument("--end-date", required=True, help="End date for metrics (YYYY-MM-DD)")
    args = parser.parse_args()
    fetch_and_calculate_metrics(args.start_date, args.end_date)
    
    #fetch_and_calculate_metrics("2025-06-01", "2025-06-30")
    #fetch_and_calculate_metrics("2025-07-01", "2025-07-30")
    #fetch_and_calculate_metrics("2025-08-01", "2025-08-31")
    #fetch_and_calculate_metrics("2025-09-01", "2025-09-30")
    #fetch_and_calculate_metrics("2025-10-01", "2025-10-31")