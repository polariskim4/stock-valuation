import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(page_title="US Stock Valuation AI Dashboard", layout="wide")

st.title("📊 미국 주식 밸류에이션 분석 대시보드")

# 1. 경쟁사 추천 로직 라이브러리 (섹터별 매핑 확장)
PEER_SUGGESTIONS = {
    "Technology": "MSFT, AAPL, NVDA, ASML",
    "Communication Services": "GOOGL, META, NFLX, DIS",
    "Consumer Cyclical": "TSLA, AMZN, HD, MCD",
    "Financial Services": "JPM, BAC, V, MA",
    "Healthcare": "JNJ, UNH, LLY, PFE",
    "Energy": "CVX, SHEL, BP, TTE",
    "Industrials": "CAT, GE, MMM, HON",
    "Consumer Defensive": "PG, KO, PEP, WMT",
    "Basic Materials": "LIN, RIO, BHP, FCX",
    "Utilities": "NEE, DUK, SO, EXC",
    "Real Estate": "PLD, AMT, EQIX, CCI"
}

@st.cache_data(ttl=3600)
def get_stock_bundle(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if not info or 'symbol' not in info:
            return None
        return {
            "info": info,
            "fin": stock.financials,
            "bs": stock.balance_sheet,
            "hist": stock.history(period="3y")
        }
    except Exception:
        return None

# 사이드바 설정
with st.sidebar:
    st.header("🔍 종목 설정")
    target_ticker = st.text_input("분석할 티커 (예: AAPL, XOM)", value="XOM").upper()
    
    # 기초 데이터 먼저 로드하여 섹터 확인
    temp_stock = yf.Ticker(target_ticker)
    try:
        sector = temp_stock.info.get('sector', 'Technology')
        industry = temp_stock.info.get('industry', 'N/A')
        st.write(f"**현재 섹터:** {sector}")
        st.write(f"**산업군:** {industry}")
        default_peers = PEER_SUGGESTIONS.get(sector, "MSFT, GOOGL")
    except:
        default_peers = "MSFT, GOOGL"

    compare_input = st.text_input("비교할 경쟁사 (쉼표 구분)", value=default_peers).upper()
    compare_list = [t.strip() for t in compare_input.split(',') if t.strip()]

# 데이터 로드
target_bundle = get_stock_bundle(target_ticker)

if target_bundle:
    info = target_bundle['info']
    
    # 1. 상단 요약 정보 (시가총액 포맷팅 수정)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("종목명", info.get('longName', 'N/A'))
    c2.metric("현재가", f"${info.get('currentPrice', 0):.1f}")
    c3.metric("섹터", info.get('sector', 'N/A'))
    
    m_cap = info.get('marketCap', 0)
    m_cap_formatted = f"${m_cap / 1e9:.1f}B" if m_cap else "N/A"
    c4.metric("시가총액", m_cap_formatted)

    # 2. 밸류에이션 지표 추출 함수
    def get_metrics_dict(data_info):
        return {
            "PER (Trailing)": data_info.get('trailingPE'),
            "Forward P/E": data_info.get('forwardPE'),
            "PEG": data_info.get('pegRatio'),
            "P/S": data_info.get('priceToSalesTrailing12Months'),
            "P/B": data_info.get('priceToBook'),
            "EV/EBITDA": data_info.get('enterpriseToEbitda')
        }

    # 3. 역사적 평균 계산
    def get_hist_avg(bundle):
        try:
            hist = bundle['hist']
            fin = bundle['fin'].T
            avg_price = hist['Close'].mean()
            shares = bundle['info'].get('sharesOutstanding', 1)
            
            avg_net_income = fin['Net Income'].mean() if 'Net Income' in fin.columns else None
            avg_rev = fin['Total Revenue'].mean() if 'Total Revenue' in fin.columns else None
            avg_ebitda = fin['EBITDA'].mean() if 'EBITDA' in fin.columns else None
            
            return {
                "PER (Trailing)": avg_price / (avg_net_income / shares) if avg_net_income else None,
                "Forward P/E": None,
                "PEG": None,
                "P/S": (avg_price * shares) / avg_rev if avg_rev else None,
                "P/B": bundle['info'].get('priceToBook'),
                "EV/EBITDA": (avg_price * shares + bundle['info'].get('totalDebt', 0) - bundle['info'].get('totalCash', 0)) / avg_ebitda if avg_ebitda and avg_ebitda > 0 else None
            }
        except: return {}

    # 데이터프레임 구성
    rows = []
    # (A) 현재 종목
    rows.append({"Ticker": f"{target_ticker} (Current)", **get_metrics_dict(info)})
    # (B) 역사적 평균
    h_avg = get_hist_avg(target_bundle)
    if h_avg:
        rows.append({"Ticker": f"{target_ticker} (3Y Avg)", **h_avg})
    # (C) 경쟁사
    for t in compare_list:
        peer_b = get_stock_bundle(t)
        if peer_b:
            rows.append({"Ticker": t, **get_metrics_dict(peer_b['info'])})

    df = pd.DataFrame(rows).set_index("Ticker")

    # 4. 시각화
    st.subheader("📋 밸류에이션 지표별 비교")
    metrics_names = ["PER (Trailing)", "Forward P/E", "PEG", "P/S", "P/B", "EV/EBITDA"]
    tabs = st.tabs(metrics_names)

    for i, m_name in enumerate(metrics_names):
        with tabs[i]:
            plot_df = df[df[m_name].notnull()]
            if not plot_df.empty:
                fig = go.Figure(go.Bar(
                    x=plot_df.index, y=plot_df[m_name],
                    marker_color=['#1f77b4' if target_ticker in x else '#d3d3d3' for x in plot_df.index],
                    text=plot_df[m_name].apply(lambda x: f"{x:.1f}"),
                    textposition='auto'
                ))
                fig.update_layout(height=400, margin=dict(t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)

    # 5. 상세 표 스타일링
    st.subheader("📊 상세 데이터 비교")
    
    def style_row(row):
        if f"{target_ticker} (Current)" in row.name:
            return ['background-color: #f0f7ff; font-weight: bold; color: #000000'] * len(row)
        return [''] * len(row)

    st.dataframe(
        df.style.format(precision=1, na_rep="-")
        .apply(style_row, axis=1)
        .set_properties(**{'text-align': 'right'}),
        use_container_width=True
    )
else:
    st.error("종목 정보를 불러올 수 없습니다. 티커를 확인해주세요.")
