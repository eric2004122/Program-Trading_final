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

plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'Heiti TC', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

app = Flask(__name__)

@app.route('/favicon.ico')
def favicon():
    return '', 204

def generate_chart_base64(buf):
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    return f"data:image/png;base64,{b64}"

def calculate_macd(df, fast=12, slow=26, signal=9):
    df['EMA_fast'] = df['Close'].ewm(span=fast, adjust=False).mean()
    df['EMA_slow'] = df['Close'].ewm(span=slow, adjust=False).mean()
    df['DIF'] = df['EMA_fast'] - df['EMA_slow']
    df['MACD'] = df['DIF'].ewm(span=signal, adjust=False).mean()
    df['Histogram'] = df['DIF'] - df['MACD']
    return df

def run_backtest_strategy(start, end, initial_cash):
    try:
        stock_ticker = "0050.TW"
        # 轉換日期字串為 datetime 物件以計算年份
        start_date = datetime.strptime(start, '%Y-%m-%d')
        end_date = datetime.strptime(end, '%Y-%m-%d')

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
        tax_rate = 0.001 # ETF 稅率為 0.1%

        # 新增指標的變數
        total_trades = 0
        winning_trades = 0
        peak_portfolio_value = initial_cash
        max_drawdown = 0.0
        
        stop_loss_pct = 0.05
        take_profit_pct = 0.10

        for i in range(1, len(df)):
            today = df.iloc[i]
            yesterday = df.iloc[i - 1]

            # 買進邏輯
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

            # 賣出邏輯
            elif position > 0:
                sell, reason = False, ''
                current_price = today['Close']
                change_pct = (current_price - buy_price) / buy_price

                if (yesterday['DIF'] > yesterday['MACD']) and (today['DIF'] < today['MACD']):
                    sell, reason = True, '死亡交叉'
                elif change_pct <= -stop_loss_pct:
                    sell, reason = True, f'停損 (-{stop_loss_pct*100:.0f}%)'
                elif change_pct >= take_profit_pct:
                    sell, reason = True, f'停利 (+{take_profit_pct*100:.0f}%)'

                if sell:
                    revenue = shares * current_price
                    fee = revenue * fee_rate
                    tax = revenue * tax_rate
                    net_income = revenue - fee - tax
                    
                    buy_cost = shares * buy_price
                    profit = net_income - (buy_cost * (1 + fee_rate))
                    roi = (profit / buy_cost) * 100 if buy_cost > 0 else 0
                    
                    cash += net_income
                    
                    # 更新交易統計
                    total_trades += 1
                    if profit > 0:
                        winning_trades += 1
                        
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

            # 計算每日的最大回撤
            current_portfolio_value = cash + (shares * today['Close'])
            peak_portfolio_value = max(peak_portfolio_value, current_portfolio_value)
            drawdown = (peak_portfolio_value - current_portfolio_value) / peak_portfolio_value
            max_drawdown = max(max_drawdown, drawdown)


        # 期末強制平倉
        if position > 0:
            final_price = df.iloc[-1]['Close']
            revenue = shares * final_price
            fee, tax = revenue * fee_rate, revenue * tax_rate
            net_income = revenue - fee - tax

            buy_cost = shares * buy_price
            profit = net_income - (buy_cost * (1 + fee_rate))
            roi = (profit / buy_cost) * 100 if buy_cost > 0 else 0

            cash += net_income

            # 期末平倉也算一次交易
            total_trades += 1
            if profit > 0:
                winning_trades += 1
            
            trade_log.append({
                '日期': df.index[-1].strftime('%Y-%m-%d'),
                '動作': '期末強制平倉',
                '價格': f"{final_price:.2f}",
                '股數': shares,
                '資金餘額': f"{cash:,.2f}",
                '報酬率': f"{roi:.2f}%"
            })

        # 計算最終指標
        total_return_float = (cash - initial_cash) / initial_cash * 100
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0

        # 計算年化報酬率 (CAGR)
        num_years = (end_date - start_date).days / 365.25
        if num_years > 0:
            cagr = ((cash / initial_cash) ** (1 / num_years) - 1) * 100
        else:
            cagr = total_return_float # 如果時間不足一年，年化報酬率等於總報酬率

        # 圖表生成 (不變)
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
            'error': None,
            # 回傳新指標
            'annualized_return': cagr,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'max_drawdown': max_drawdown * 100, # 轉換為百分比
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
    
    # 預設值，用於錯誤頁面
    default_context = {
        'error': None,
        'today': today_str,
        'end_date': end,
        'total_return': "0.00",
        'total_return_float': 0,
        'annualized_return': 0,
        'win_rate': 0,
        'total_trades': 0,
        'max_drawdown': 0,
        'signal': "⚠️ 參數錯誤"
    }

    if not all([start, end, cash_str]):
        default_context['error'] = "所有欄位 (投入金額、開始日期、結束日期) 皆為必填。"
        return render_template('strategy_template.html', **default_context)

    try:
        initial_cash = float(cash_str)
        if initial_cash <= 0:
            raise ValueError("投入金額必須大於 0。")
    except ValueError as e:
        default_context['error'] = str(e)
        return render_template('strategy_template.html', **default_context)

    data = run_backtest_strategy(start, end, initial_cash)

    if data['error']:
        default_context['error'] = data['error']
        default_context['signal'] = "⚠️ 執行錯誤"
        return render_template('strategy_template.html', **default_context)

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
                           annualized_return=f"{data.get('annualized_return', 0):.2f}",
                           win_rate=f"{data.get('win_rate', 0):.2f}",
                           total_trades=data.get('total_trades', 0),
                           max_drawdown=f"{data.get('max_drawdown', 0):.2f}",
                           signal=signal,
                           end_date=end,
                           today=today_str,
                           macd_chart_b64=data['macd_chart_b64'],
                           error=None)

if __name__ == '__main__':
    app.run(debug=True, port=5001)