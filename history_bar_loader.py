import pandas as pd
import numpy as np
from datetime import datetime
import requests
import io
import zipfile
import os
from tqdm import tqdm
from joblib import Parallel, delayed

# ================= 配置参数 =================
SYMBOL_LIST = ['BTCUSDT', 'ETHUSDT']
INTERVAL = '1m'
START_DATE = "2020-01-01" 
END_DATE = datetime.now()
N_JOBS = 16
BACKEND = "threading"

# K线标准列定义
KLINE_COLS_DEF = [
    'open_time', 'open', 'high', 'low', 'close',
    'volume', 'close_time', 'quote_volume', 
    'count', 'taker_buy_volume', 
    'taker_buy_quote_volume', 'ignore'
    ]

# 需要转换为数值类型的列
NUMERIC_COLS = [
    'open', 'high', 'low', 'close', 'volume',
    'quote_volume', 'count','taker_buy_volume',
    'taker_buy_quote_volume'
    ]

# ================= 核心工具函数 =================
def read_csv_auto(file_handle, fallback_columns=None):
    """
    智能读取：自动判断 CSV 是否有表头
    """
    try:
        first_line = file_handle.readline().decode('utf-8').strip()  # 币安早期的数据没有header，后期的有header，因此需要先读取第一行看一下
        if not first_line: return None # 空文件返回None
        
        first_token = first_line.split(',')[0]  # 判断第一列是否为数字(Binance数据第一列通常是时间戳)
        has_header = False
        try:  # 这里判断的逻辑是看第一列数据能不能转换成float，如果有header的话，header为str，会报错
            float(first_token) # 转换成功 -> 是数字 -> 无表头
            has_header = False
        except ValueError:     # 转换失败 -> 是单词 -> 有表头
            has_header = True
            
        file_handle.seek(0)   # 重置指针，readline会把光标移动到第二行

        if has_header:
            return pd.read_csv(file_handle, header=0)
        else:
            return pd.read_csv(file_handle, header=None, names=fallback_columns)
    except Exception as e:
        print(f"读取CSV失败: {e}")
        return None

def fetch_and_clean_kline(symbol, date, url):
    """下载并清洗 K线 / MarkPrice"""
    try:
        resp = requests.get(url)
        if resp.status_code != 200: return None

        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            csv_name = z.namelist()[0]
            with z.open(csv_name) as f:
                df = read_csv_auto(f, fallback_columns=KLINE_COLS_DEF)   # 智能读取，如果klines没有header会自动用KLINE_COLS_DEF
                
                # 基础数据清洗：数据类型的转换
                df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
                cols_to_convert = [c for c in NUMERIC_COLS if c in df.columns]
                df[cols_to_convert] = df[cols_to_convert].apply(pd.to_numeric, errors='coerce')
                
                # 内存优化：只返回需要的列
                keep_cols = ['open_time'] + cols_to_convert
                return df[keep_cols]
    except Exception as e:
        print(f"\n[K线异常] {symbol} {date}: {e}")
        return None

def fetch_monthly_funding(symbol, month_str):
    """下载并清洗资金费率"""
    url = f"https://data.binance.vision/data/futures/um/monthly/fundingRate/{symbol}/{symbol}-fundingRate-{month_str}.zip"
    try:
        resp = requests.get(url)
        if resp.status_code != 200: return None
        
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            with z.open(z.namelist()[0]) as f:
                df = read_csv_auto(f) # 费率文件通常自带表头
        
        # --- 列名兼容性处理 ---
        # 时间列处理：这里kline数据的header里，时间列为open_time，而资金费率数据的header里，时间列为calc_time，要分开处理
        if 'calc_time' in df.columns:
            df['open_time'] = pd.to_datetime(df['calc_time'], unit='ms')
        elif 'open_time' in df.columns: # 防止某些文件已经是 open_time
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            
        # 费率列处理：币安后期数据的费率列名为last_funding_rate, 前期的列名为fundingRate，因此这里统一改成last_funding_rate
        if 'last_funding_rate' not in df.columns:
            if 'fundingRate' in df.columns:
                df.rename(columns={'fundingRate': 'last_funding_rate'}, inplace=True)
        
        # 周期列处理：早期币安费率数据没有funding_interval_hours, 因此这里如果没有则设为默认值8
        if 'funding_interval_hours' not in df.columns:
            df['funding_interval_hours'] = 8 

        # 返回清洗后的三列
        return df[['open_time', 'last_funding_rate', 'funding_interval_hours']]
    except Exception as e:
        print(f" [费率异常: {e}]", end="")
        return None
    
def download_daily_pair(symbol, interval, date_str):
    """
    下载指定日期的kline和mark_price，返回(k_df, m_df)
    """
    kline_url = f"https://data.binance.vision/data/futures/um/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{date_str}.zip"
    mark_url  = f"https://data.binance.vision/data/futures/um/daily/markPriceKlines/{symbol}/{interval}/{symbol}-{interval}-{date_str}.zip"

    k_df = fetch_and_clean_kline(symbol, date_str, kline_url)
    m_df = fetch_and_clean_kline(symbol, date_str, mark_url)
    return k_df, m_df

def download_monthly_funding(symbol, month_str):
    """下载指定月份的funding，返回df或None"""
    return fetch_monthly_funding(symbol, month_str)

# ================= 主程序 =================
dates = pd.date_range(start=START_DATE, end=END_DATE, freq='D')
str_dates = dates.strftime('%Y-%m-%d').tolist()
month_list = sorted(pd.to_datetime(str_dates).to_period("M").astype(str).unique().to_list())

os.makedirs("data_parquet", exist_ok=True)  # parquet存放路径

for symbol in SYMBOL_LIST:
    print(f"\n开始处理: {symbol} | 总天数: {len(str_dates)} ｜ 总月份: {len(month_list)}")

    fund_results = Parallel(n_jobs=N_JOBS, backend=BACKEND)(
        delayed(download_monthly_funding)(symbol, m)
        for m in tqdm(month_list, desc=f"{symbol} funding(月)", leave=False)
    )
    all_fund_dfs = [df for df in fund_results if df is not None]

    daily_results = Parallel(n_jobs=N_JOBS, backend=BACKEND)(
        delayed(download_daily_pair)(symbol, INTERVAL, d)
        for d in tqdm(str_dates, desc=f"{symbol} daily(日)", leave=False)
    )

    all_kline_dfs = []
    all_mark_dfs = []
    for k_df, m_df in daily_results:
        if k_df is not None:
            all_kline_dfs.append(k_df)
        if m_df is not None:
            all_mark_dfs.append(m_df)
        
    print(f"\n正在合并 {symbol} 数据...")
    
    if not all_kline_dfs:
        print(f"{symbol} 无数据，跳过。")
        continue
    
    # 合并K线数据
    full_kline_df = pd.concat(all_kline_dfs).sort_values('open_time').reset_index(drop=True)
    
    # 合并MarkPrice
    if all_mark_dfs:
        full_mark_df = pd.concat(all_mark_dfs).sort_values('open_time').reset_index(drop=True)
        # MarkPrice只保留OHLC，防止列名冲突
        full_mark_df = full_mark_df[['open_time', 'open', 'high', 'low', 'close']]
        
        final_df = pd.merge(full_kline_df, full_mark_df, on='open_time', how='left', suffixes=('', '_mark'))
    else:
        final_df = full_kline_df

    # 合并资金费率
    if all_fund_dfs:
        full_fund_df = pd.concat(all_fund_dfs).sort_values('open_time').reset_index(drop=True)
        
        # 左连接：把费率挂到对应的open_time上
        final_df = pd.merge(final_df, full_fund_df, on='open_time', how='left')
        
        cols_to_fill = ['last_funding_rate', 'funding_interval_hours']
        final_df[cols_to_fill] = final_df[cols_to_fill].ffill()   # 币安会在每8小时的整点更新费率，然后在这一刻会按照持仓*费率来调整保证金
        
        # 填补开头缺失(如果K线开始时间早于第一个费率结算点)
        final_df[cols_to_fill] = final_df[cols_to_fill].fillna(0)
    else:
        print(f"⚠️ 未获取到 {symbol} 资金费率")
        final_df['last_funding_rate'] = 0
        final_df['funding_interval_hours'] = 8

    final_df['code'] = symbol

    print(f"✅ 完成 {symbol}！Shape: {final_df.shape}")
    # display(final_df.head())
    
    # 保存
    final_df.to_parquet(f"data_parquet/{symbol}_{INTERVAL}.parquet")