import os
import io
import uuid
import traceback
import threading
from datetime import datetime
from flask import Flask, request, abort, send_from_directory
from dotenv import load_dotenv

from linebot.v3.messaging import MessagingApi, Configuration, ApiClient
from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging.models import (
    TextMessage, ImageMessage, PushMessageRequest, ReplyMessageRequest,
    QuickReply, QuickReplyItem, DatetimePickerAction
)
from linebot.v3.webhooks.models import (
    MessageEvent, TextMessageContent, PostbackEvent
)

import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# === 初始化 ===
load_dotenv()
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
BASE_URL = os.getenv('BASE_URL')

app = Flask(__name__)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

IMAGE_DIR = r'C:\Users\eric2\Desktop\程式交易實作\期末2\picture'
os.makedirs(IMAGE_DIR, exist_ok=True)

user_state = {}

@app.route("/picture/<filename>")
def serve_picture(filename):
    return send_from_directory(IMAGE_DIR, filename)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    print("=== 收到 LINE Webhook ===")
    print("Signature:", signature)
    print("Body:", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("❌ 簽名驗證失敗！")
        abort(400)
    except Exception as e:
        print("❌ 其他錯誤：", e)
        traceback.print_exc()
        abort(500)
        
    return "OK"


@handler.add(MessageEvent)
def handle_message(event):
    user_id = event.source.user_id
    if isinstance(event.message, TextMessageContent):
        text = event.message.text.strip()
        if text.lower() in ['回測', '開始', 'macd']:
            user_state[user_id] = {}
            ask_start_date(user_id, event.reply_token)
        elif text.lower() in ['說明', 'help', '使用說明']:
            send_instruction(event.reply_token)
        elif user_id in user_state and 'end_date' not in user_state[user_id]:
            user_state[user_id]['end_date'] = text
            ask_invest_amount(user_id, event.reply_token)
        elif user_id in user_state and 'amount' not in user_state[user_id]:
            try:
                user_state[user_id]['amount'] = float(text)
                start = user_state[user_id]['start_date']
                end = user_state[user_id]['end_date']
                amount = user_state[user_id]['amount']
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="✅ 資料輸入完成，開始回測...")]
                ))
                threading.Thread(target=process_backtest_in_background, args=(user_id, start, end, amount, BASE_URL)).start()
                del user_state[user_id]
            except:
                line_bot_api.reply_message(ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text="⚠️ 金額格式錯誤，請重新輸入純數字金額。")]
                ))
        else:
            send_instruction(event.reply_token)

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.params
    if 'date' in data:
        if user_id not in user_state or 'start_date' not in user_state[user_id]:
            user_state[user_id] = {'start_date': data['date']}
            ask_end_date(user_id, event.reply_token)
        else:
            user_state[user_id]['end_date'] = data['date']
            ask_invest_amount(user_id, event.reply_token)

def ask_start_date(user_id, reply_token):
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=reply_token,
        messages=[
            TextMessage(
                text="請選擇回測【開始日期】：",
                quick_reply=QuickReply(items=[
                    QuickReplyItem(
                        action=DatetimePickerAction(
                            label="選擇日期", data="select_start", mode="date"
                        )
                    )
                ])
            )
        ]
    ))

def ask_end_date(user_id, reply_token):
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=reply_token,
        messages=[
            TextMessage(
                text="請選擇回測【結束日期】：",
                quick_reply=QuickReply(items=[
                    QuickReplyItem(
                        action=DatetimePickerAction(
                            label="選擇日期", data="select_end", mode="date"
                        )
                    )
                ])
            )
        ]
    ))

def ask_invest_amount(user_id, reply_token):
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=reply_token,
        messages=[TextMessage(text="請輸入投入的本金（例如：100000）：")]
    ))

def send_instruction(reply_token):
    line_bot_api.reply_message(ReplyMessageRequest(
        reply_token=reply_token,
        messages=[TextMessage(
            text=("您好，我是 MACD 回測機器人 📊\n\n"
                  "請輸入以下指令開始使用：\n"
                  "🔹 輸入 `回測` 或 `開始` 或 `macd` 來啟動互動式回測流程\n"
                  "🔹 接著會請您依序輸入：開始日期、結束日期與本金金額\n\n"
                  "⚠️ 若您輸入錯誤或中斷流程，請重新輸入 `回測` 即可重新開始。")
        )]
    ))

def run_backtest_strategy(start, end, initial_cash):
    try:
        stock_ticker = "0050.TW"
        df = yf.Ticker(stock_ticker).history(start=start, end=end)
        if df.empty:
            return {'error': f'無法取得 {stock_ticker} 資料，請檢查日期。'}

        df['EMA_fast'] = df['Close'].ewm(span=12).mean()
        df['EMA_slow'] = df['Close'].ewm(span=26).mean()
        df['DIF'] = df['EMA_fast'] - df['EMA_slow']
        df['MACD'] = df['DIF'].ewm(span=9).mean()
        df['Histogram'] = df['DIF'] - df['MACD']

        position = 0
        cash = initial_cash
        shares = 0
        buy_price = 0
        fee_rate, tax_rate = 0.001425, 0.003
        stop_loss_pct, take_profit_pct = 0.05, 0.10
        trade_log = []

        equity_curve = []
        peak = initial_cash

        for i in range(1, len(df)):
            today, yesterday = df.iloc[i], df.iloc[i - 1]

            if position == 0 and yesterday['DIF'] < yesterday['MACD'] and today['DIF'] > today['MACD']:
                buy_price = today['Close']
                shares_to_buy = int(cash // (buy_price * (1 + fee_rate)))
                if shares_to_buy > 0:
                    cost = shares_to_buy * buy_price
                    cash -= cost * (1 + fee_rate)
                    shares = shares_to_buy
                    position = shares
                    trade_log.append({'日期': df.index[i].strftime('%Y-%m-%d'), '動作': '買進 (黃金交叉)', '價格': f"{buy_price:.2f}"})

            elif position > 0:
                sell, reason = False, ''
                current_price = today['Close']
                change_pct = (current_price - buy_price) / buy_price
                if yesterday['DIF'] > yesterday['MACD'] and today['DIF'] < today['MACD']:
                    sell, reason = True, '死亡交叉'
                elif change_pct <= -stop_loss_pct:
                    sell, reason = True, f'停損 (-{stop_loss_pct*100:.1f}%)'
                elif change_pct >= take_profit_pct:
                    sell, reason = True, f'停利 (+{take_profit_pct*100:.1f}%)'

                if sell:
                    revenue = shares * current_price
                    cash += revenue * (1 - fee_rate - tax_rate)
                    trade_log.append({'日期': df.index[i].strftime('%Y-%m-%d'), '動作': f'賣出 ({reason})', '價格': f"{current_price:.2f}"})
                    position = 0
                    shares = 0

            # 每日資產紀錄
            equity = cash + shares * today['Close']
            equity_curve.append(equity)
            peak = max(peak, equity)

        if position > 0:
            final_price = df.iloc[-1]['Close']
            cash += shares * final_price * (1 - fee_rate - tax_rate)

        final_value = cash
        total_return = (final_value - initial_cash) / initial_cash * 100

        # 新增統計指標
        trade_pairs = [trade_log[i:i + 2] for i in range(0, len(trade_log) - 1, 2)
                       if trade_log[i]['動作'].startswith('買進') and trade_log[i + 1]['動作'].startswith('賣出')]
        win_trades = [pair for pair in trade_pairs if float(pair[1]['價格']) > float(pair[0]['價格'])]
        total_trades = len(trade_pairs)
        win_rate = len(win_trades) / total_trades * 100 if total_trades else 0

        days = (pd.to_datetime(end) - pd.to_datetime(start)).days
        annualized_return = ((final_value / initial_cash) ** (365 / days) - 1) * 100 if days > 0 else 0

        drawdowns = [(peak_val - val) / peak_val for peak_val, val in zip(pd.Series(equity_curve).cummax(), equity_curve)]
        max_drawdown = max(drawdowns) * 100 if drawdowns else 0

        gains = [float(p[1]['價格']) - float(p[0]['價格']) for p in trade_pairs if float(p[1]['價格']) > float(p[0]['價格'])]
        losses = [float(p[0]['價格']) - float(p[1]['價格']) for p in trade_pairs if float(p[1]['價格']) < float(p[0]['價格'])]
        avg_gain = sum(gains) / len(gains) if gains else 0.01
        avg_loss = sum(losses) / len(losses) if losses else 0.01
        risk_reward = avg_gain / avg_loss if avg_loss != 0 else 0

        # 繪圖
        buf = io.BytesIO()
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        ax1.plot(df.index, df['Close'], label='收盤價', color='darkcyan')
        ax1.set_title(f'{stock_ticker} MACD 策略回測 ({start} ~ {end})', fontsize=16)
        ax1.grid(True, linestyle='--', alpha=0.6)
        ax2.plot(df.index, df['DIF'], label='DIF', color='blue')
        ax2.plot(df.index, df['MACD'], label='MACD', color='red')
        bar_colors = ['green' if x > 0 else 'red' for x in df['Histogram']]
        ax2.bar(df.index, df['Histogram'], label='柱狀圖', color=bar_colors, alpha=0.5)
        for ax in [ax1, ax2]: ax.legend()
        plt.tight_layout()
        plt.savefig(buf, format='png')
        plt.close()

        return {
            'trades': trade_log,
            'total_return_float': total_return,
            'final_value': final_value,
            'macd_chart_bytes': buf.getvalue(),
            'win_rate': win_rate,
            'annualized_return': annualized_return,
            'trade_count': total_trades,
            'max_drawdown': max_drawdown,
            'risk_reward': risk_reward,
            'error': None
        }

    except Exception as e:
        traceback.print_exc()
        return {'error': str(e)}


def process_backtest_in_background(user_id, start_date, end_date, initial_cash, base_url):
    try:
        data = run_backtest_strategy(start_date, end_date, initial_cash)
        if data['error']:
            line_bot_api.push_message(PushMessageRequest(
                to=user_id,
                messages=[TextMessage(text=f"❌ 錯誤：{data['error']}")]
            ))
            return

        result_text = (
            f"📈 回測結果報告 (0050.TW)\n"
            f"--------------------------\n"
            f"時間範圍：{start_date} ~ {end_date}\n"
            f"初始本金：${initial_cash:,.0f}\n"
            f"最終價值：${data['final_value']:,.2f}\n"
            f"總報酬率：{data['total_return_float']:.2f}% {'💹' if data['total_return_float'] > 0 else '🔻'}\n"
            f"📊 年化報酬率：{data['annualized_return']:.2f}%\n"
            f"🎯 勝率：{data['win_rate']:.2f}%\n"
            f"🔁 交易次數：{data['trade_count']} 次\n"
            f"📉 最大回撤：{data['max_drawdown']:.2f}%\n"
            f"📈 風險報酬比：{data['risk_reward']:.2f}\n"
            f"--------------------------\n"
        )
        last_5 = data['trades'][-5:]
        if last_5:
            result_text += "最後 5 筆交易紀錄：\n" + "\n".join(
                [f"- {t['日期']} {t['動作']} @{t['價格']}" for t in last_5])
        else:
            result_text += "期間內無交易紀錄。\n"

        filename = f"{uuid.uuid4()}.png"
        filepath = os.path.join(IMAGE_DIR, filename)
        with open(filepath, 'wb') as f:
            f.write(data['macd_chart_bytes'])
        image_url = f"{base_url.rstrip('/')}/picture/{filename}"

        line_bot_api.push_message(PushMessageRequest(
            to=user_id,
            messages=[
                TextMessage(text=result_text),
                ImageMessage(original_content_url=image_url, preview_image_url=image_url)
            ]
        ))
    except Exception as e:
        traceback.print_exc()
        line_bot_api.push_message(PushMessageRequest(
            to=user_id,
            messages=[TextMessage(text=f"❌ 發生錯誤：{e}")]
        ))

if __name__ == '__main__':
    app.run(debug=True, port=5001)
