# APP.py

import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from flask import Flask, render_template, request
from datetime import datetime
import traceback

# 設定 Matplotlib 使用支援中文的字體
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Heiti TC', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False # 解決負號顯示問題

app = Flask(__name__)

# --- ↓↓↓ 新增的程式碼：忽略 favicon.ico 的請求 ↓↓↓ ---
@app.route('/favicon.ico')
def favicon():
    # 返回一個 204 No Content 回應，告訴瀏覽器這裡沒有圖示
    return '', 204
# --- ↑↑↑ 新增的程式碼結束 ↑↑↑ ---


def generate_chart_base64(buf):
    """將 Matplotlib 圖片緩衝區轉換為 Base64 字串"""
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    return f"data:image/png;base64,{b64}"

def calculate_macd(df, fast=12, slow=26, signal=9):
    """計算 MACD 指標"""
    df['EMA_fast'] = df['Close'].ewm(span=fast, adjust=False).mean()
    df['EMA_slow'] = df['Close'].ewm(span=slow, adjust=False).mean()
    df['DIF'] = df['EMA_fast'] - df['EMA_slow']
    df['MACD'] = df['DIF'].ewm(span=signal, adjust=False).mean()
    df['Histogram'] = df['DIF'] - df['MACD']
    return df

def run_backtest_strategy(start, end, initial_cash):
    """執行回測策略的核心邏輯"""
    try:
        stock_ticker = "2330.TW"
        df = yf.Ticker(stock_ticker).history(start=start, end=end)
        
        if df.empty:
            return {'error': f'無法在指定日期範圍內取得 {stock_ticker} 的資料，請嘗試調整日期。'}

        df = calculate_macd(df)

        position = 0
        buy_price = 0
        cash = initial_cash
        shares = 0
        trade_log = []
        fee_rate = 0.001425
        tax_rate = 0.003
        stop_loss_pct = 0.05
        take_profit_pct = 0.10

        # --- 交易邏輯 ---
        for i in range(1, len(df)):
            today = df.iloc[i]
            yesterday = df.iloc[i - 1]

            if position == 0 and (yesterday['DIF'] < yesterday['MACD']) and (today['DIF'] > today['MACD']):
                buy_price = today['Close']
                shares_to_buy = int(cash // (buy_price * (1 + fee_rate)))
                if shares_to_buy > 0:
                    cost = shares_to_buy * buy_price
                    fee = cost * fee_rate
                    total_cost = cost + fee
                    cash -= total_cost
                    position = shares_to_buy
                    shares = shares_to_buy
                    trade_log.append({
                        '日期': df.index[i].strftime('%Y-%m-%d'),
                        '動作': '買進 (黃金交叉)',
                        '價格': f"{buy_price:.2f}",
                        '股數': shares,
                        '資金餘額': f"{cash:,.2f}"
                    })

            elif position > 0:
                sell, reason = False, ''
                current_price = today['Close']
                change_pct = (current_price - buy_price) / buy_price

                if (yesterday['DIF'] > yesterday['MACD']) and (today['DIF'] < today['MACD']):
                    sell, reason = True, '死亡交叉'
                elif change_pct <= -stop_loss_pct:
                    sell, reason = True, f'停損 (-{stop_loss_pct*100}%)'
                elif change_pct >= take_profit_pct:
                    sell, reason = True, f'停利 (+{take_profit_pct*100}%)'

                if sell:
                    revenue = shares * current_price
                    fee = revenue * fee_rate
                    tax = revenue * tax_rate
                    net_income = revenue - fee - tax
                    cost_basis = shares * buy_price * (1 + fee_rate)
                    profit = net_income - cost_basis
                    roi = (profit / cost_basis) * 100 if cost_basis > 0 else 0
                    cash += net_income
                    trade_log.append({
                        '日期': df.index[i].strftime('%Y-%m-%d'),
                        '動作': f'賣出 ({reason})',
                        '價格': f"{current_price:.2f}",
                        '股數': shares,
                        '資金餘額': f"{cash:,.2f}",
                        '報酬率': f"{roi:.2f}%"
                    })
                    position = 0
                    shares = 0
                    buy_price = 0

        if position > 0:
            final_price = df.iloc[-1]['Close']
            revenue = shares * final_price
            fee, tax = revenue * fee_rate, revenue * tax_rate
            net_income = revenue - fee - tax
            cost_basis = shares * buy_price * (1 + fee_rate)
            profit = net_income - cost_basis
            roi = (profit / cost_basis) * 100 if cost_basis > 0 else 0
            cash += net_income
            trade_log.append({
                '日期': df.index[-1].strftime('%Y-%m-%d'),
                '動作': '期末強制平倉',
                '價格': f"{final_price:.2f}",
                '股數': shares,
                '資金餘額': f"{cash:,.2f}",
                '報酬率': f"{roi:.2f}%"
            })

        total_return_float = (cash - initial_cash) / initial_cash * 100

        # --- 圖表生成 ---
        buf_macd = io.BytesIO()
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        ax1.plot(df.index, df['Close'], label='收盤價', color='darkcyan')
        ax1.set_title(f'{stock_ticker} MACD 策略回測 ({start} ~ {end})', fontsize=16)
        ax1.set_ylabel('股價 (TWD)')
        ax1.grid(True, linestyle='--', alpha=0.6)
        ax1.legend()
        ax2.plot(df.index, df['DIF'], label='DIF (快線)', color='blue', linewidth=1.5)
        ax2.plot(df.index, df['MACD'], label='MACD (慢線)', color='red', linewidth=1.5)
        bar_colors = ['#28a745' if x > 0 else '#dc3545' for x in df['Histogram']]
        ax2.bar(df.index, df['Histogram'], label='柱狀圖 (DIF-MACD)', color=bar_colors, alpha=0.5)
        ax2.axhline(0, color='black', linewidth=0.8, linestyle='--')
        ax2.set_xlabel('日期')
        ax2.set_ylabel('MACD 值')
        ax2.legend()
        ax2.grid(True, linestyle='--', alpha=0.6)
        plt.tight_layout()
        plt.savefig(buf_macd, format='png', dpi=100)
        plt.close(fig)

        return {
            'trades': trade_log,
            'total_return_float': total_return_float,
            'macd_chart_b64': generate_chart_base64(buf_macd),
            'error': None
        }
    except Exception as e:
        traceback.print_exc()
        return {'error': f"發生未預期的錯誤: {e}"}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/strategy')
def strategy():
    start = request.args.get('start')
    end = request.args.get('end')
    cash_str = request.args.get('cash')
    today_str = datetime.today().strftime('%Y-%m-%d')
    
    if not all([start, end, cash_str]):
        return render_template('strategy_template.html',
                               error="所有欄位 (投入金額、開始日期、結束日期) 皆為必填。",
                               today=today_str,
                               signal="⚠️ 參數錯誤")
    try:
        initial_cash = float(cash_str)
        if initial_cash <= 0:
            raise ValueError("投入金額必須大於 0。")
    except ValueError as e:
        return render_template('strategy_template.html', error=str(e), today=today_str, signal="⚠️ 參數錯誤")
    
    data = run_backtest_strategy(start, end, initial_cash)

    if data['error']:
        return render_template('strategy_template.html', error=data['error'], today=today_str, signal="⚠️ 執行錯誤")

    signal = "⚪️ 無交易紀錄或期末平倉"
    if data['trades']:
        last_trade = data['trades'][-1]
        if '買進' in last_trade['動作']:
            signal = f"🟢 持有中 (於 {last_trade['日期']} 買進)"
        else:
            signal = f"🔴 空手 (於 {last_trade['日期']} 賣出)"

    total_return_float = data.get('total_return_float', 0)

    return render_template('strategy_template.html',
                           trades=data['trades'],
                           total_return=f"{total_return_float:.2f}",
                           total_return_float=total_return_float,
                           signal=signal,
                           today=today_str,
                           macd_chart_b64=data['macd_chart_b64'],
                           error=None)

if __name__ == '__main__':
    app.run(debug=True, port=5001)