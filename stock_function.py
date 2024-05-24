import requests
from bs4 import BeautifulSoup
import sqlite3
import boto3
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('agg')
import mplfinance as mpf
import os
from io import BytesIO
import twstock
from datetime import datetime, timedelta

def get_instructions():
    instructions = f"【股票代號查詢】\n直接輸入股票代號查詢股票資訊\n---------------\n【股票圖分析查詢】\n可查詢股票近一年的趨勢圖及k線圖\n-趨勢圖(tXXXX)\n-k線圖(kXXXX)\n---------------\n【我的股票】\n查詢股票清單中股市資料\n---------------\n【新增股票】\n新增股票到股票清單\n---------------\n【刪除股票】\n從股票清單中刪除股票"
    return instructions

def get_stock_info(stock_number):
    url = "https://tw.stock.yahoo.com/quote/"+stock_number+".TW"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            name_element = soup.find("h1", class_="C($c-link-text) Fw(b) Fz(24px) Mend(8px)")
            price_element = soup.find("div", class_="D(f) Ai(fe) Mb(4px)")
            trading_element = soup.find("div",class_= "D(f) Fld(c) Ai(c) Fw(b) Pend(8px) Bdendc($bd-primary-divider) Bdends(s) Bdendw(1px)")
            
            if price_element and name_element:
                company_name = name_element.text
                price = price_element.find_all("span")[0].text
                trading_volume = trading_element.find("span").text

                if "C($c-trend-down)" in price_element.find("span")['class']:
                  up_and_down = "-"+price_element.find_all("span")[1].text+"%"
                else:
                  up_and_down = "+"+price_element.find_all("span")[1].text+"%"

                res = "【公司】"+company_name+"\n"+"【股票代號】"+stock_number+"\n"+"【價格】"+price+"\n"+"【漲跌】"+up_and_down+"\n"+"【成交量】"+trading_volume
                return res
        else:
            print("Failed to fetch stock price. Status code:", response.status_code)
            return False
    except Exception as e:
        print("Error occurred while fetching stock price:", e)
        return None

def get_stock_name(stock_number):
    company_name = twstock.codes[stock_number].name
    return company_name

def get_user_stocks(user_id):
    # 從資料庫中取得使用者的股票資訊
    conn = sqlite3.connect('userdata.db')
    cursor = conn.cursor()
    cursor.execute("SELECT stock_code FROM stocks WHERE user_id = ?", (user_id,))
    user_stocks = cursor.fetchall()
    conn.close()
    res = ""
    index = 0
    while index < len(user_stocks):
        res+=get_stock_info(user_stocks[index][0])
        index+=1
        if(index!=len(user_stocks)):
            res+=f"\n---------------\n"
    if res:
        return res
    else:
        return "尚未有常用股票資訊"

def check_user_stocks(user_id,reply_text):
    conn = sqlite3.connect('userdata.db')
    cursor = conn.cursor()   
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE user_id = ? AND stock_code = ?", (user_id, reply_text))
    count = cursor.fetchone()[0]
    conn.close()
    return count>0

def add_user_stocks(user_id,add_stock_codes):
    # 從資料庫中取得使用者的股票資訊
    conn = sqlite3.connect('userdata.db')
    cursor = conn.cursor()
    for stock_code in add_stock_codes[user_id]:
        cursor.execute("SELECT COUNT(*) FROM stocks WHERE user_id = ? AND stock_code = ?", (user_id, stock_code))
        count = cursor.fetchone()[0]
        if count == 0:
            # 若股票代號不在資料庫中，則存入
            cursor.execute("INSERT INTO stocks (user_id, stock_code) VALUES (?, ?)", (user_id, stock_code))
        else:
            # 若已在，則不做動作
            print(f"股票代號 {stock_code} 已經存在資料庫")
    conn.commit()
    conn.close()
    add_stock_codes.pop(user_id)
    return "已存入常用股票"

def delete_user_stocks(user_id,delete_stock_codes):
    # 從資料庫中取得使用者的股票資訊
    conn = sqlite3.connect('userdata.db')
    cursor = conn.cursor()
    for stock_code in delete_stock_codes[user_id]:
        cursor.execute("DELETE FROM stocks WHERE user_id = ? AND stock_code = ?", (user_id, stock_code))
    conn.commit()
    conn.close()
    delete_stock_codes.pop(user_id)
    return "股票已被刪除"

def get_stock_trend_chart(stock_number):
    #傳進來的形式為tXXXX
    stock_number = stock_number[1:5]
    try:
        stock = twstock.Stock(stock_number)
        today = datetime.now()
        one_year_ago = today - timedelta(days=365)
        stock_data = stock.fetch_from(one_year_ago.year, one_year_ago.month)
        if stock_data is not None and len(stock_data) > 0:
            fig, ax = plt.subplots(figsize=(8, 6))
            
            # 抓取日期及股票資料
            dates = [data.date for data in stock_data]
            prices = [data.close for data in stock_data]
            
            # 繪製趨勢圖
            ax.plot(dates, prices)
            ax.set_title(f'Stock code {stock_number} one-year stock price trend chart')
            ax.set_xlabel('Date')
            ax.set_ylabel('Price')
            
            # 保存到Buffer，上傳雲端
            buf = BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)
            image_url = upload_to_s3(buf, f"t{stock_number}.png")
            return image_url

    except Exception as e:
        print(f"發生錯誤: {e}")
        return None


def get_stock_kline_chart(stock_number):
    #傳進來的形式為kXXXX
    stock_number = stock_number[1:5]
    try:
        stock = twstock.Stock(stock_number)
        today = datetime.now()
        one_year_ago = today - timedelta(days=365)
        stock_data = stock.fetch_from(one_year_ago.year, one_year_ago.month)
        if stock_data is not None and len(stock_data) > 0:
            fig, ax = plt.subplots(figsize=(6, 4))

            # 抓取日期及股票資料
            dates = [data.date for data in stock_data]
            open_prices = [data.open for data in stock_data]
            high_prices = [data.high for data in stock_data]
            low_prices = [data.low for data in stock_data]
            close_prices = [data.close for data in stock_data]

            # 繪製k線圖
            ax.plot(dates, close_prices, color='black', label='Close Price')
            ax.plot(dates, open_prices, color='blue', label='Open Price')
            ax.plot(dates, high_prices, color='red', label='High Price')
            ax.plot(dates, low_prices, color='green', label='Low Price')

            ax.set_title(f'Stock code {stock_number} one-year Candlestick chart')
            ax.set_xlabel('Date')
            ax.set_ylabel('Price')
            ax.legend()

            # 保存到Buffer，上傳雲端
            buf = BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)
            image_url = upload_to_s3(buf, f"k{stock_number}.png")
            return image_url
        else:
            return "Failed to fetch stock data."
    except Exception as e:
        return f"Error occurred: {e}"
    

def upload_to_s3(buffer, filename):
    # AWS 連接設定
    aws_access_key_id = 
    aws_secret_access_key = 
    bucket_name = 

    s3 = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key)

    try:
        content_type = 'image/png'
        extra_args = {'ContentType': content_type}
        s3.put_object(Bucket=bucket_name, Key=filename, Body=buffer.getvalue(),**extra_args)
        return "https://finance-track-image.s3.ap-northeast-3.amazonaws.com/"+filename
    except Exception as e:
        print(f"Error occurred while uploading to S3: {e}")
        return False
