import os
import json
import gspread
import yfinance as yf
from datetime import datetime
import pandas as pd
import numpy as np

# --- 功能函式 ---

def get_credentials():
    """從 GitHub Secrets 讀取 Google 服務帳戶金鑰"""
    creds_json_str = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
    if not creds_json_str:
        raise ValueError("Secret 'GOOGLE_SERVICE_ACCOUNT_JSON' not found!")
    return json.loads(creds_json_str)

def get_sheet_id():
    """從 GitHub Secrets 讀取 Google Sheet ID"""
    sheet_id = os.getenv('SHEET_ID')
    if not sheet_id:
        raise ValueError("Secret 'SHEET_ID' not found!")
    return sheet_id

def get_config():
    """讀取 config.json 檔案"""
    with open('config.json', 'r') as f:
        return json.load(f)

def calculate_historical_iv(ticker_symbol):
    """
    計算指定股票過去一年的歷史波動率 (HV) 作為 IV 的代理。
    yfinance 不直接提供 IV，我們用 HV 來估算 IV Rank 和 Percentile。
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        # 獲取過去一年的股價數據
        hist = ticker.history(period="1y")
        if hist.empty:
            print(f"Warning: No history found for {ticker_symbol}, cannot calculate IVR/IVP.")
            return None
        
        # 計算每日對數回報率
        log_returns = np.log(hist['Close'] / hist['Close'].shift(1))
        # 計算 30 天滾動的年化波動率
        rolling_hv = log_returns.rolling(window=30).std() * np.sqrt(252)
        return rolling_hv.dropna()
    except Exception as e:
        print(f"Error calculating historical IV for {ticker_symbol}: {e}")
        return None

def get_iv_data(tickers):
    """獲取股票的當前隱含波動率 (IV)、IV Rank (IVR) 和 IV Percentile (IVP)"""
    data = {}
    for symbol in tickers:
        print(f"Fetching data for {symbol}...")
        try:
            ticker = yf.Ticker(symbol)
            
            # 1. 獲取當前 IV (通過最近的選擇權鏈)
            opt = ticker.option_chain(ticker.options[0])
            # 簡單加權平均 IV
            iv = (opt.calls['impliedVolatility'] * opt.calls['volume']).sum() / opt.calls['volume'].sum() if opt.calls['volume'].sum() > 0 else opt.calls['impliedVolatility'].mean()
            current_iv = iv * 100  # 轉換為百分比
            
            # 2. 計算 IVR 和 IVP
            historical_iv = calculate_historical_iv(symbol)
            ivr = None
            ivp = None

            if historical_iv is not None and not historical_iv.empty:
                # 取得過去一年的最高和最低 IV
                iv_high = historical_iv.max() * 100
                iv_low = historical_iv.min() * 100
                
                # 計算 IV Rank
                if iv_high > iv_low:
                    ivr = ((current_iv - iv_low) / (iv_high - iv_low)) * 100
                
                # 計算 IV Percentile
                ivp = (historical_iv * 100 < current_iv).mean() * 100

            data[symbol] = {
                'IV': f"{current_iv:.2f}",
                'IVR': f"{ivr:.2f}" if ivr is not None else "N/A",
                'IVP': f"{ivp:.2f}" if ivp is not None else "N/A"
            }
            print(f"Success for {symbol}: IV={data[symbol]['IV']}, IVR={data[symbol]['IVR']}, IVP={data[symbol]['IVP']}")

        except Exception as e:
            print(f"Could not fetch IV data for {symbol}: {e}")
            data[symbol] = {'IV': 'N/A', 'IVR': 'N/A', 'IVP': 'N/A'}
            
    return data

def update_google_sheet(credentials, sheet_id, data):
    """將數據更新到 Google Sheet"""
    try:
        gc = gspread.service_account_from_dict(credentials)
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.sheet1
        print("Successfully connected to Google Sheet.")

        # 建立新的標題行
        headers = ['Date']
        for symbol in data.keys():
            headers.append(f"{symbol}_IV")
            headers.append(f"{symbol}_IVR")
            headers.append(f"{symbol}_IVP")

        # 建立新的數據行
        row_to_insert = [datetime.now().strftime('%Y-%m-%d')]
        for symbol in data.keys():
            row_to_insert.append(data[symbol]['IV'])
            row_to_insert.append(data[symbol]['IVR'])
            row_to_insert.append(data[symbol]['IVP'])

        # 檢查第一行是否為我們期望的標題
        # 如果不是，則插入標題行
        if worksheet.row_values(1) != headers:
            # 清空工作表以確保結構正確 (可選，更安全的做法是新增工作表)
            # 這裡我們選擇更新第一行
            print("Header mismatch or not found. Updating header row...")
            worksheet.update('A1', [headers])
            # 找到下一個空行來插入數據
            next_row = len(worksheet.get_all_values()) + 1
            worksheet.insert_row(row_to_insert, next_row)
        else:
            # 如果標題正確，直接在最後追加新行
            print("Header is correct. Appending new data...")
            worksheet.append_row(row_to_insert)

        print("Google Sheet updated successfully!")
    except Exception as e:
        print(f"Failed to update Google Sheet: {e}")
        raise

# --- 主執行流程 ---

def main():
    """主函式"""
    print("Starting IV update process...")
    config = get_config()
    credentials = get_credentials()
    sheet_id = get_sheet_id()
    
    iv_data = get_iv_data(config['tickers'])
    
    if iv_data:
        update_google_sheet(credentials, sheet_id, iv_data)
    else:
        print("No IV data fetched. Skipping sheet update.")
        
    print("IV update process finished.")

if __name__ == "__main__":
    main()

