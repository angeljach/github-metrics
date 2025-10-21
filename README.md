# GitHub Pull Request Metrics Script

This Python script generates metrics for pull requests (PRs) in a GitHub repository. It calculates various statistics grouped by teams, such as the total number of PRs, merged PRs, lines added/deleted, and average cycle time. The script uses the GitHub API to fetch data and outputs the results as a CSV file.

---

## Features

- Fetches pull requests from a GitHub repository using the GitHub API.
- Filters PRs based on a specified date range (`start_date` and `end_date`).
- Maps GitHub users to teams using a `teams.json` file.
- Calculates the following metrics:
  - **Total PRs**: Number of PRs created by each team.
  - **Merged PRs**: Number of PRs merged by each team.
  - **Lines Added**: Total lines of code added in PRs.
  - **Lines Deleted**: Total lines of code deleted in PRs.
  - **Average Cycle Time**: Average time (in days) taken to merge PRs.
  - **Merge Rate**: Percentage of PRs merged out of total PRs.
- Identifies unassigned users (users not mapped to any team).
- Outputs the metrics as a CSV file.

---

## Prerequisites

1. **Python**: Ensure Python 3.x is installed on your system.
2. **Dependencies**: Install the required Python libraries:
   ```bash
   uv add requests pandas python-dotenv
   ```

---

## Run
```bash
uv run metrics.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD
```
   