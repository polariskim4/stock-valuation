import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 지표 정의 및 설정 (코드 최상단에 위치하여 NameError 방지)
st.set_page_config(page_title="US Stock Valuation Dashboard", layout="wide")

# 지표 설명 사전 정의
METRIC_DESCRIPTIONS = {
    "PER (Trailing)": "주가수익비율 (과거 12개월). 실제 이익 대비 주가가 몇 배인지 나타내는 지표입니다.",
    "Forward P/E": "선행 주가수익비율 (향후 12개월 예상). 시장이 기대하는 미래 수익성 대비 주가 수준입니다.",
    "PEG": "주가수익성장비율 (PER / 이익성장률). 보통 1 미만이면 성장성 대비 저평가로 간주합니다.",
    "P/S": "주가매출비율. 매출액 대비 주가 수준으로, 성장주 분석에 유용합니다.",
    "P/B": "주가순자산비율. 기업의 자본(장부가치) 대비 주가 수준입니다.",
    "EV/EBITDA": "기업가치 대비 영업현금흐름. 실제 현금 창출 능력 대비 기업 가치를 평가합니다."
}

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

st.title("📊 미국 주식 밸류에이션 분석 대시보드")

# 2. 데이터 수집 함수
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

# 3. 사이드바 설정
with st.sidebar:
    st.header("🔍 종목 설정")
    target_ticker = st.text_input("분석할 티커", value="XOM").upper()
    
    # 섹터 정보 미리 가져오기
    temp_stock = yf.Ticker(target_ticker)
    try:
        sector = temp_stock.info.get('sector', 'Technology')
        st.write(f"**현재 섹터:** {sector}")
        default_peers = PEER_SUGGESTIONS.get(sector, "MSFT, GOOGL")
    except:
        default_peers = "MSFT, GOOGL"

    compare_input = st.text_input("비교할 경쟁사", value=default_peers).upper()
    compare_list = [t.strip() for t in compare_input.split(',') if t.strip()]

# 4. 데이터 계산 및 메인 화면
target_bundle = get_stock_bundle(target_ticker)

if target_bundle:
    info = target_bundle['info']
    
    # 상단 요약
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("종목명", info.get('longName', 'N/A'))
    c2.metric("현재가", f"${info.get('currentPrice', 0):.1f}")
    c3.metric("섹터", info.get('sector', 'N/A'))
    m_cap = info.get('marketCap', 0)
    c4.metric("시가총액", f"${m_cap / 1e9:.1f}B" if m_cap else "N/A")

    # 지표 데이터프레임 생성 로직
    def get_metrics(data):
        return {
            "PER (Trailing)": data.get('trailingPE'),
            "Forward P/E": data.get('forwardPE'),
            "PEG": data.get('pegRatio'),
            "P/S": data.get('priceToSalesTrailing12Months'),
            "P/B": data.get('priceToBook'),
            "EV/EBITDA": data.get('enterpriseToEbitda')
        }

    rows = [{"Ticker": f"{target_ticker} (Current)", **get_metrics(info)}]
    
    # 경쟁사 추가
    for t in compare_list:
        peer_b = get_stock_bundle(t)
        if peer_b: rows.append({"Ticker": t, **get_metrics(peer_b['info'])})

    df = pd.DataFrame(rows).set_index("Ticker")

    # 차트 출력
    st.subheader("📋 밸류에이션 지표별 비교")
    tabs = st.tabs(list(METRIC_DESCRIPTIONS.keys()))
    for i, m_name in enumerate(METRIC_DESCRIPTIONS.keys()):
        with tabs[i]:
            if m_name in df.columns:
                fig = go.Figure(go.Bar(x=df.index, y=df[m_name], text=df[m_name].apply(lambda x: f"{x:.1f}" if pd.notnull(x) else "")))
                st.plotly_chart(fig, use_container_width=True)

    # 상세 표
    st.subheader("📊 상세 데이터 비교")
    st.dataframe(df.style.format(precision=1, na_rep="-").set_properties(**{'text-align': 'right'}))

    # 5. 지표 도움말 (METRIC_DESCRIPTIONS를 여기서 사용)
    st.markdown("---")
    with st.expander("💡 지표별 상세 설명 확인하기"):
        for metric, desc in METRIC_DESCRIPTIONS.items():
            st.markdown(f"**{metric}**: {desc}")

else:
    st.error("데이터를 불러올 수 없습니다.")
