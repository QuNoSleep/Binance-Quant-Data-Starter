# Binance Quant Data Starter

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)
![Data](https://img.shields.io/badge/Data-Binance%20Futures-yellow?style=flat-square&logo=binance)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-v0.1%20MVP-orange?style=flat-square)

> **"Don't stay up late manually downloading CSVs."** — Qu Zong

## 📖 简介 (Introduction)

这是一个专为 **Crypto量化研究 (Quant Research)** 设计的轻量级数据获取框架。

---

## 核心特性 (Key Features)

- **智能清洗 (Smart Parsing)**: 
  - 内置 `Header Sniffer`，自动识别币安早期（2020年前）缺失表头的 CSV 数据，无需人工修补。
- **费率对齐 (Funding Rate Alignment)**: 
  - 自动拉取 8小时/4小时 维度的资金费率，并将其**前向填充 (Forward Fill)** 对齐至分钟级 K 线，方便计算持仓成本。
- **高效存储 (Parquet)**: 
  - 清洗后的数据直接保存为 `.parquet` 格式，读取速度比 CSV 快 10-50 倍，大幅加速回测初始化。
- **断点续传 (Resumable)**: 
  - (v0.2 开发中) 多线程并发下载 (Multi-threading)，支持现货和期权数据以及其他频率的数据等。

---

## 🛠️ 快速开始 (Quick Start)

### 1. 环境准备
```bash
git clone https://github.com/QuNoSleep/Binance-Quant-Data-Starter.git
cd Binance-Quant-Data-Starter
pip install -r requirements.txt
```

### 2. 配置参数
打开 `main.py` 修改头部配置：

```python
# Configs
SYMBOL_LIST = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
START_DATE = "2023-01-01"
END_DATE = "2024-01-01"
DATA_DIR = "./data"
```

### 3. 运行下载
```bash
python history_bar_loader.py
```
运行结束后，清洗好的数据将保存在 `./data` 目录下。

---

## 📊 数据结构 (Data Structure)

清洗后的 Parquet 文件包含 **24个字段**，涵盖了价格、成交量、资金费率及标记价格，完全满足基础因子挖掘的需求。

| 类别 (Category) | 字段名 (Columns) | 说明 (Description) |
|:---|:---|:---|
| **时间与标的** | `open_time` | K线开始时间 (datetime) |
| | `code` | 交易对 (e.g., BTCUSDT) |
| **基础行情 (OHLC)** | `open`, `high`, `low`, `close` | 市场最新成交价 (Market Price) |
| **成交量分析** | `volume` | 成交量 (币) |
| | `quote_volume` | 成交额 (USDT) |
| | `count` | 成交笔数 (Number of Trades) |
| **订单流 (Alpha)** | `taker_buy_volume` | 主动买入量 (用于计算多空比/资金流向) |
| | `taker_buy_quote_volume` | 主动买入额 |
| **衍生品核心** | `last_funding_rate` | **资金费率** (已对齐至每根 K 线) |
| | `funding_interval_hours` | 费率收取间隔 (通常为 8h) |
| **风控与结算** | `open_mark`, `high_mark`... | **标记价格** (Mark Price, 用于回测爆仓逻辑) |

### 💡 数据亮点
*   **Mark Price (标记价格)**: 包含 `_mark` 后缀的四列数据。在回测时，建议使用标记价格来判断止损/爆仓，避免被市场插针误杀。
*   **Taker Volume**: 包含了主动买入量，可以用来计算 **Net Taker Volume** 等强效因子。
*   **Funding Rate**: 费率已自动填充，可直接用于计算持仓成本：`Cost = Position * Price * FundingRate`。

---

## 🗺️ 开发路线图 (Roadmap)

- [x] **v0.1 MVP**: 基础 K 线下载 + 资金费率清洗 + Parquet 存储
- [ ] **v0.2 Performance**: 多线程并发下载 (Multi-threading)
- [ ] **v0.3 Options**: 币安期权数据 (Options) 获取接口
- [ ] **v0.4 Frequent**: 下载更高频率的数据 (High Frequent)

---

## 👨‍💻 作者 (Author)

**Qu Zong (曲总)**
*   🎓 SJTU & HKU FinTech
*   📈 Quant Researcher (CTA / Crypto)
*   📕 小红书: [曲总不想熬夜] ID：63806448023

*If this tool helped you save some sleep, please give it a Star! ⭐*
