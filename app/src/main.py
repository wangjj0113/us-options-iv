import os
import json
import yfinance as yf
import gspread
from datetime import datetime
from google.oauth2.service_account import Credentials

def get_option_iv(ticker_symbol):
    """Fetches the at-the-money (ATM) implied volatility for a given stock ticker."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        opt = ticker.option_chain(ticker.options[0])
        
        current_price = ticker.history(period="1d")['Close'][0]
        
        # Find the strike price closest to the current price (ATM)
        atm_strike = min(opt.calls['strike'], key=lambda x: abs(x - current_price))
        
        # Get the IV for that ATM strike
        iv = opt.calls[opt.calls['strike'] == atm_strike]['impliedVolatility'].iloc[0]
        
        return round(iv * 100, 2) # Return as a percentage
    except Exception as e:
        print(f"Could not retrieve IV for {ticker_symbol}: {e}")
        return "N/A"

def update_google_sheet(service_account_json, sheet_id, data):
    """Updates the Google Sheet with the provided data."""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(service_account_json, scopes=scopes )
        client = gspread.authorize(creds)
        
        sheet = client.open_by_key(sheet_id).sheet1
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Check if today's date is already in the first column
        dates_in_sheet = sheet.col_values(1)
        if today in dates_in_sheet:
            row_index = dates_in_sheet.index(today) + 1
            # Update the existing row
            sheet.update(f'A{row_index}', [[today] + data])
            print(f"Updated data for {today}.")
        else:
            # Append a new row
            sheet.append_row([today] + data)
            print(f"Appended new data for {today}.")

    except Exception as e:
        print(f"Failed to update Google Sheet: {e}")

def main():
    """Main function to run the script."""
    # Load config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    tickers = config['tickers']
    sheet_id = os.getenv('SHEET_ID', config.get('sheet_id'))

    # Get Google credentials from GitHub Secrets
    google_creds_json_str = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
    if not google_creds_json_str:
        print("Error: GOOGLE_SERVICE_ACCOUNT_JSON secret not found.")
        return
    
    service_account_json = json.loads(google_creds_json_str)

    # Fetch IV for all tickers
    iv_data = [get_option_iv(ticker) for ticker in tickers]
    
    # Update sheet header if it's empty or needs updating
    try:
        client = gspread.service_account_from_dict(service_account_json)
        sheet = client.open_by_key(sheet_id).sheet1
        header = sheet.row_values(1)
        expected_header = ["Date"] + tickers
        if header != expected_header:
             sheet.update('A1', [expected_header])
             print("Sheet header updated.")
    except Exception as e:
        print(f"Could not update header: {e}")


    # Update Google Sheet
    update_google_sheet(service_account_json, sheet_id, iv_data)

if __name__ == "__main__":
    main()
