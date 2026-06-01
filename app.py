import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(page_title="US Stock Valuation Dashboard", layout="wide")

st.title("📊 미국 주식 밸류에이션 분석 대시보드")

# 사이드바 설정
with st.sidebar:
    st.header("🔍 종목 설정")
    ticker_symbol = st.text_input("분석할 티커 (예: AAPL)", value="AAPL").upper()
    
    # 데이터 먼저 로드하여 섹터 정보 확인
    @st.cache_data(ttl=3600)
    def get_basic_info(ticker):
        try:
            s = yf.Ticker(ticker)
            return s.info
        except:
            return None

    basic_info = get_basic_info(ticker_symbol)
    
    suggested_peers = ""
    if basic_info:
        sector = basic_info.get('sector', 'N/A')
        industry = basic_info.get('industry', 'N/A')
        st.info(f"**섹터:** {sector}\n\n**산업:** {industry}")
        
        # 간단한 섹터별 주요 종목 추천 (자동화의 한계 보완)
        peer_map = {
            "Technology": "MSFT, GOOGL, AMZN, META",
            "Communication Services": "NFLX, DIS, TMUS",
            "Consumer Cyclical": "TSLA, ORCL, HD",
            "Financial Services": "JPM, BAC, V, MA",
            "Healthcare": "JNJ, UNH, PFE"
        }
        suggested_peers = peer_map.get(sector, "MSFT, GOOGL")

    compare_tickers_input = st.text_input("비교할 경쟁사 (쉼표 구분)", value=suggested_peers).upper()
    compare_tickers = [t.strip() for t in compare_tickers_input.split(',') if t.strip()]

@st.cache_data(ttl=3600)
def get_full_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        # 역사적 데이터 (손익계산서, 대차대조표, 현금흐름표)
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        history = stock.history(period="3y")
        return {"info": info, "fin": financials, "bs": balance_sheet, "hist": history}
    except:
        return None

def calculate_historical_metrics(data_bundle):
    """역사적 평균 계산 (EV/EBITDA 포함)"""
    try:
        info = data_bundle['info']
        fin = data_bundle['fin'].T
        bs = data_bundle['bs'].T
        hist = data_bundle['hist']
        
        avg_price = hist['Close'].mean()
        shares = info.get('sharesOutstanding', 1)
        mkt_cap = avg_price * shares
        
        # 3년 평균 데이터 추출
        avg_net_income = fin['Net Income'].mean() if 'Net Income' in fin.columns else None
        avg_rev = fin['Total Revenue'].mean() if 'Total Revenue' in fin.columns else None
        avg_ebitda = fin['EBITDA'].mean() if 'EBITDA' in fin.columns else None
        
        # EV 계산을 위한 부채/현금 (최근 데이터 기준)
        total_debt = info.get('totalDebt', 0)
        total_cash = info.get('totalCash', 0)
        ev = mkt_cap + total_debt - total_cash

        return {
            "PER (Trailing)": avg_price / (avg_net_income / shares) if avg_net_income else None,
            "Forward P/E": None, # 미래 예측치는 과거 데이터로 산출 불가
            "PEG": None,         # 과거 성장률 기반 PEG는 왜곡이 심해 제외
            "P/S": mkt_cap / avg_rev if avg_rev else None,
            "P/B": info.get('priceToBook'),
            "EV/EBITDA": ev / avg_ebitda if avg_ebitda and avg_ebitda > 0 else None
        }
    except:
        return {}

# 메인 분석 실행
target_data = get_full_data(ticker_symbol)

if target_data:
    info = target_data['info']
    
    # 1. 상단 요약
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("종목명", info.get('longName', 'N/A'))
    with col2: st.metric("현재가", f"${info.get('currentPrice', 0):.1f}")
    with col3: st.metric("섹터", info.get('sector', 'N/A'))
    with col4: 
        m_cap_billion = info.get('marketCap', 0) / 1e9
        st.metric("시가총액", f".1fB")

    # 2. 데이터 정리
    def extract_current(t_info):
        return {
            "PER (Trailing)": t_info.get('trailingPE'),
            "Forward P/E": t_info.get('forwardPE'),
            "PEG": t_info.get('pegRatio'),
            "P/S": t_info.get('priceToSalesTrailing12Months'),
            "P/B": t_info.get('priceToBook'),
            "EV/EBITDA": t_info.get('enterpriseToEbitda')
        }

    rows = []
    # 대상 현재 데이터
    rows.append({"Ticker": f"{ticker_symbol} (Current)", **extract_current(info)})
    # 역사적 평균
    hist_avg = calculate_historical_metrics(target_data)
    if hist_avg:
        rows.append({"Ticker": f"{ticker_symbol} (3Y Avg)", **hist_avg})
    # 경쟁사 데이터
    for t in compare_tickers:
        c_bundle = get_full_data(t)
        if c_bundle:
            rows.append({"Ticker": t, **extract_current(c_bundle['info'])})

    df = pd.DataFrame(rows).set_index("Ticker")

    # 3. 시각화
    st.subheader("📋 밸류에이션 비교 차트")
    metrics = ["PER (Trailing)", "Forward P/E", "PEG", "P/S", "P/B", "EV/EBITDA"]
    tabs = st.tabs(metrics)

    for i, m in enumerate(metrics):
        with tabs[i]:
            plot_df = df[df[m].notnull()]
            if not plot_df.empty:
                fig = go.Figure(go.Bar(
                    x=plot_df.index, y=plot_df[m],
                    marker_color=['#1f77b4' if ticker_symbol in x else '#d3d3d3' for x in plot_df.index],
                    text=plot_df[m].apply(lambda x: f"{x:.1f}"), textposition='auto'
                ))
                fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
                st.plotly_chart(fig, use_container_width=True)

    # 4. 상세 데이터 테이블 (커스텀 스타일링)
    st.subheader("📊 상세 데이터 비교")

    def highlight_target(row):
        # 현재 종목 행에 배경색과 볼드체 적용
        if f"{ticker_symbol} (Current)" in row.name:
            return ['background-color: #e6f3ff; font-weight: bold'] * len(row)
        return [''] * len(row)

    styled_df = df.style.format(precision=1, na_rep="-") \
                .apply(highlight_target, axis=1) \
                .set_properties(**{'text-align': 'right'})

    st.dataframe(styled_df, use_container_width=True)

else:
    st.error("티커 정보를 불러올 수 없습니다.")
