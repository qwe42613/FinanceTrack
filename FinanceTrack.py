from linebot import LineBotApi, WebhookHandler
from linebot.models import TextMessage, TextSendMessage,ImageSendMessage
from linebot.exceptions import LineBotApiError
from linebot.models.events import MessageEvent
from flask import Flask, request, abort
from stock_function import get_stock_info, get_user_stocks, add_user_stocks, delete_user_stocks,check_user_stocks, get_stock_trend_chart, get_stock_name,get_stock_kline_chart, get_instructions
import sqlite3
import os


# Line Bot 的 Channel 資訊
CHANNEL_SECRET = 
CHANNEL_ACCESS_TOKEN = 

# 初始化 Line Bot API
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
# 儲存使用者股票代號
add_stock_codes = {}
delete_stock_codes = {}


app = Flask(__name__)

@app.route("/", methods=['POST'])
def webhook():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except LineBotApiError as e:
        print("Got exception from LINE Messaging API: %s\n" % e.message)
        abort(400)
    except Exception as e:
        print(e)
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    reply_text = event.message.text
    user_id = event.source.user_id
    image_url=None
    if reply_text=="使用說明":
        reply_info = get_instructions()
    # 新增常用股票
    elif reply_text=="新增股票":
        add_stock_codes[user_id] = []
        reply_info = "請輸入欲新增股票代號，完成後請輸入\"完成\"命令!"
    # 查詢常用股票
    elif reply_text=="我的股票":
        reply_info = get_user_stocks(user_id,)
    # 刪除常用股票
    elif reply_text=="刪除股票":
        delete_stock_codes[user_id] = []
        reply_info = "請輸入欲刪除股票代號，完成後請輸入\"完成\"命令!"
    # 使用者輸入股票代號，並存入常用股票
    elif user_id in add_stock_codes and reply_text.isdigit() and len(reply_text) == 4:
        if get_stock_info(reply_text):
            add_stock_codes[user_id].append(reply_text)
            reply_info = "已將股票代號存入常用股票"
        else:
            reply_info = "請輸入正確的股票代號"
    # 使用者輸入股票代號，並存入待刪除股票
    elif user_id in delete_stock_codes and reply_text.isdigit() and len(reply_text) == 4:
        if check_user_stocks(user_id,reply_text):
            delete_stock_codes[user_id].append(reply_text)
            reply_info = "已將股票代號存入待刪除股票"
        else:
            reply_info = "此股票代號並無在常用股票清單內"
    # 使用者完成新增股票代號，存入資料庫
    elif reply_text == "完成" and user_id in add_stock_codes:
        reply_info = add_user_stocks(user_id, add_stock_codes)
    # 使用者完成欲刪除股票代號，更新資料庫
    elif reply_text == "完成" and user_id in delete_stock_codes:
        reply_info = delete_user_stocks(user_id, delete_stock_codes)
    # 查詢股票資訊
    elif reply_text.isdigit() and len(reply_text)==4:
        reply_info = get_stock_info(reply_text)
    #取得股票趨勢圖
    elif len(reply_text)==5 and reply_text[1:5].isdigit() and reply_text[0]=="t":
        if get_stock_trend_chart(reply_text)!=None:
            image_url = get_stock_trend_chart(reply_text)
            company_name = get_stock_name(reply_text[1:5])
            reply_info = f"{company_name}_({reply_text[1:5]})近一年的股價趨勢圖"
        else:
            reply_info = "無法生成該股票資訊，請確認股票代號並重新操作"
    #取得股票K線圖
    elif len(reply_text)==5 and reply_text[1:5].isdigit() and reply_text[0]=="k":
        if get_stock_kline_chart(reply_text)!=None:
            image_url = get_stock_kline_chart(reply_text)
            company_name = get_stock_name(reply_text[1:5])
            reply_info = f"{company_name}_({reply_text[1:5]})近一年的K線圖"
        else:
            reply_info = "無法生成該股票資訊，請確認股票代號並重新操作"
    else:
        reply_info="請輸入有效指令或股票代號"

    reply(event.reply_token, reply_info,image_url)

def reply(reply_token, reply_text,image_url):
    try:
        if(image_url!=None):
            image_message = ImageSendMessage(original_content_url=image_url, preview_image_url=image_url)
            line_bot_api.reply_message(reply_token,[TextSendMessage(text=reply_text),image_message])
        else:
            line_bot_api.reply_message(reply_token,[TextSendMessage(text=reply_text)])
    except LineBotApiError as e:
        print("Got exception from LINE Messaging API: %s\n" % e.message)
        return

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)

