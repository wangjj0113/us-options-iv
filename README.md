# US Options IV Tracker

This is an automated project using Python and GitHub Actions to fetch the implied volatility (IV) of specified US stocks daily and log the results into a Google Sheet.

## Project Structure
- `.github/workflows/iv_update.yml`: The GitHub Actions workflow file that runs the script on a schedule.
- `app/src/main.py`: The main Python script to fetch IV and write to Google Sheet.
- `config.json`: Configuration file for stock tickers and Google Sheet ID.
- `requirements.txt`: Python dependencies.
- `.gitignore`: Specifies which files to ignore.
