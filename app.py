import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 1. 설정 및 지표 정의 (NameError 방지 및 관리 용이성)
st.set_page_config(page_title="US Stock Valuation Dashboard", layout="wide")

METRIC_DESCRIPTIONS = {
    "PER (Trailing)": "주가수익비율 (과거 12개월). 실제 이익 대비 주가가 몇 배인지 나타냅니다.",
    "Forward P/E": "선행 주가수익비율 (향후 12개월 예상). 미래 수익성 대비 주가 수준입니다.",
    "PEG": "주가수익성장비율 (PER / 이익성장률). 1 미만이면 성장성 대비 저평가로 봅니다.",
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

# 2. 데이터 수집 함수 (Ticker 객체 대신 데이터 뭉치 반환으로 캐시 에러 방지)
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

# 3. 사이드바 설정 (섹터 인식 및 경쟁사 추천)
with st.sidebar:
    st.header("🔍 종목 설정")
    target_ticker = st.text_input("분석할 티커", value="XOM").upper()
    
    temp_stock = yf.Ticker(target_ticker)
    try:
        sector = temp_stock.info.get('sector', 'Technology')
        st.write(f"**현재 섹터:** {sector}")
        default_peers = PEER_SUGGESTIONS.get(sector, "MSFT, GOOGL")
    except:
        default_peers = "MSFT, GOOGL"

    compare_input = st.text_input("비교할 경쟁사", value=default_peers).upper()
    compare_list = [t.strip() for t in compare_input.split(',') if t.strip()]

# 4. 데이터 계산 로직
target_bundle = get_stock_bundle(target_ticker)

if target_bundle:
    info = target_bundle['info']
    
    # 상단 요약 바 (소수점 한자리 및 시가총액 단위)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("종목명", info.get('longName', 'N/A'))
    c2.metric("현재가", f"${info.get('currentPrice', 0):.1f}")
    c3.metric("섹터", info.get('sector', 'N/A'))
    m_cap = info.get('marketCap', 0)
    c4.metric("시가총액", f"${m_cap / 1e9:.1f}B" if m_cap else "N/A")

    # 지표 추출용 헬퍼 함수
    def extract_metrics(data_info):
        return {
            "PER (Trailing)": data_info.get('trailingPE'),
            "Forward P/E": data_info.get('forwardPE'),
            "PEG": data_info.get('pegRatio'),
            "P/S": data_info.get('priceToSalesTrailing12Months'),
            "P/B": data_info.get('priceToBook'),
            "EV/EBITDA": data_info.get('enterpriseToEbitda')
        }

    # 역사적 평균 계산 함수 (핵심 복구 기능)
    def calculate_historical_avg(bundle):
        try:
            hist = bundle['hist']
            fin = bundle['fin'].T
            avg_price = hist['Close'].mean()
            shares = bundle['info'].get('sharesOutstanding', 1)
            
            avg_net_income = fin['Net Income'].mean() if 'Net Income' in fin.columns else None
            avg_rev = fin['Total Revenue'].mean() if 'Total Revenue' in fin.columns else None
            avg_ebitda = fin['EBITDA'].mean() if 'EBITDA' in fin.columns else None
            
            total_debt = bundle['info'].get('totalDebt', 0)
            total_cash = bundle['info'].get('totalCash', 0)
            
            return {
                "PER (Trailing)": avg_price / (avg_net_income / shares) if avg_net_income else None,
                "Forward P/E": None, # 선행 지표는 과거 데이터로 산출 불가
                "PEG": None,
                "P/S": (avg_price * shares) / avg_rev if avg_rev else None,
                "P/B": bundle['info'].get('priceToBook'), # P/B는 현재 장부가 기준
                "EV/EBITDA": (avg_price * shares + total_debt - total_cash) / avg_ebitda if avg_ebitda and avg_ebitda > 0 else None
            }
        except: return {}

    # 비교 데이터 프레임 구성
    rows = []
    # (1) 현재 종목
    rows.append({"Ticker": f"{target_ticker} (Current)", **extract_metrics(info)})
    
    # (2) 역사적 평균 추가
    h_avg = calculate_historical_avg(target_bundle)
    if h_avg:
        rows.append({"Ticker": f"{target_ticker} (3Y Avg)", **h_avg})
    
    # (3) 경쟁사 추가
    for t in compare_list:
        peer_b = get_stock_bundle(t)
        if peer_b:
            rows.append({"Ticker": t, **extract_metrics(peer_b['info'])})

    df = pd.DataFrame(rows).set_index("Ticker")

    # 5. 시각화 (차트)
    st.subheader("📋 밸류에이션 지표별 비교")
    tabs = st.tabs(list(METRIC_DESCRIPTIONS.keys()))
    for i, m_name in enumerate(METRIC_DESCRIPTIONS.keys()):
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

    # 6. 상세 표 스타일링 (현재 종목 하이라이트)
    st.subheader("📊 상세 데이터 비교")
    
    def highlight_current(row):
        if f"{target_ticker} (Current)" in row.name:
            return ['background-color: #f0f7ff; font-weight: bold'] * len(row)
        return [''] * len(row)

    st.dataframe(
        df.style.format(precision=1, na_rep="-")
        .apply(highlight_current, axis=1)
        .set_properties(**{'text-align': 'right'}),
        use_container_width=True
    )

    # 7. 지표 도움말
    st.markdown("---")
    with st.expander("💡 지표별 상세 설명 확인하기"):
        for metric, desc in METRIC_DESCRIPTIONS.items():
            st.markdown(f"**{metric}**: {desc}")

else:
    st.error("종목 정보를 불러올 수 없습니다. 티커를 확인해 주세요.")
