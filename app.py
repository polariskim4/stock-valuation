import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(page_title="US Stock Valuation Dashboard", layout="wide")

st.title("📊 미국 주식 밸류에이션 분석 대시보드")
st.markdown("티커를 입력하면 현재 지표를 **역사적 평균(3년)** 및 **경쟁사**와 비교합니다.")

# 사이드바 설정
with st.sidebar:
    st.header("설정")
    ticker_symbol = st.text_input("분석할 티커 (예: AAPL)", value="AAPL").upper()
    compare_tickers_input = st.text_input("비교할 경쟁사 (쉼표 구분)", value="MSFT, GOOGL, AMZN").upper()
    compare_tickers = [t.strip() for t in compare_tickers_input.split(',') if t.strip()]

@st.cache_data(ttl=3600)
def get_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        # 역사적 데이터 추출 (최근 3년 연간 재무제표)
        return {
            "info": info,
            "financials": stock.financials,
            "history": stock.history(period="3y")
        }
    except Exception:
        return None

# 데이터 가져오기
data_bundle = get_data(ticker_symbol)

if data_bundle and 'info' in data_bundle:
    info = data_bundle['info']
    
    # 1. 상단 요약 정보 (시가총액 Billion 단위)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("종목명", info.get('longName', 'N/A'))
    with col2:
        st.metric("현재가", f"${info.get('currentPrice', 0):.2f}")
    with col3:
        st.metric("섹터", info.get('sector', 'N/A'))
    with col4:
        m_cap_billion = info.get('marketCap', 0) / 1e9
        st.metric("시가총액", f"${m_cap_billion:.2f}B")

    # 2. 밸류에이션 지표 추출 함수 (순서 고정)
    def extract_metrics(target_info):
        return {
            "PER (Trailing)": target_info.get('trailingPE'),
            "Forward PER": target_info.get('forwardPE'),
            "PEG Ratio": target_info.get('pegRatio'),
            "P/S Ratio": target_info.get('priceToSalesTrailing12Months'),
            "P/B Ratio": target_info.get('priceToBook'),
            "EV/EBITDA": target_info.get('enterpriseToEbitda')
        }

    # 3. 역사적 평균 계산 (최근 3년 데이터 기준)
    def get_historical_avg_metrics(bundle):
        try:
            # 주가와 발행주식수를 이용한 대략적 과거 배수 계산
            hist = bundle['history']
            avg_price = hist['Close'].mean()
            shares = info.get('sharesOutstanding', 1)
            
            # 재무제표 데이터
            fin = bundle['financials'].T
            if fin.empty: return {}
            
            avg_net_income = fin['Net Income'].mean() if 'Net Income' in fin.columns else None
            avg_rev = fin['Total Revenue'].mean() if 'Total Revenue' in fin.columns else None
            
            return {
                "PER (Trailing)": avg_price / (avg_net_income / shares) if avg_net_income else None,
                "Forward PER": None, # 미래 예측치는 과거 평균이 없음
                "PEG Ratio": None,
                "P/S Ratio": (avg_price * shares) / avg_rev if avg_rev else None,
                "P/B Ratio": info.get('priceToBook'), # P/B는 현재 데이터 활용 권장
                "EV/EBITDA": None
            }
        except:
            return {}

    # 비교 데이터 프레임 생성
    rows = []
    # (1) 대상 종목 현재가
    current_metrics = extract_metrics(info)
    rows.append({"Ticker": f"{ticker_symbol} (Current)", **current_metrics})
    
    # (2) 역사적 평균
    hist_metrics = get_historical_avg_metrics(data_bundle)
    if hist_metrics:
        rows.append({"Ticker": f"{ticker_symbol} (3Y Avg)", **hist_metrics})
    
    # (3) 경쟁사 데이터
    for t in compare_tickers:
        c_data = get_data(t)
        if c_data:
            rows.append({"Ticker": t, **extract_metrics(c_data['info'])})
    
    df_compare = pd.DataFrame(rows).set_index("Ticker")

    # 4. 시각화 섹션
    st.subheader("📋 주요 밸류에이션 지표 비교")
    metrics_list = ["PER (Trailing)", "Forward PER", "PEG Ratio", "P/S Ratio", "P/B Ratio", "EV/EBITDA"]
    tabs = st.tabs(metrics_list)

    for i, metric in enumerate(metrics_list):
        with tabs[i]:
            clean_df = df_compare[df_compare[metric].notnull()]
            if not clean_df.empty:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=clean_df.index,
                    y=clean_df[metric],
                    marker_color=['#1f77b4' if ticker_symbol in x else '#d3d3d3' for x in clean_df.index],
                    text=clean_df[metric].apply(lambda x: f"{x:.1f}"),
                    textposition='auto'
                ))
                # 평균선
                avg_val = clean_df[metric].mean()
                fig.add_shape(type="line", line=dict(color="Red", dash="dash"),
                              x0=-0.5, x1=len(clean_df)-0.5, y0=avg_val, y1=avg_val)
                
                fig.update_layout(title=f"{metric} (현재 vs 역사적 평균 vs 경쟁사)", yaxis_title="배수", height=400)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"{metric} 데이터를 불러올 수 없습니다.")

    # 5. 데이터 테이블 섹션 (소수점 한자리, 오른쪽 정렬)
    st.subheader("📊 상세 데이터 비교")
    styled_df = df_compare.style.format(precision=1, na_rep="-") \
                .set_properties(**{'text-align': 'right'}) \
                .highlight_min(axis=0, color='#ccffcc') # 수치가 낮을수록(저평가) 녹색
    
    st.dataframe(styled_df, use_container_width=True)

    st.caption("참고: 역사적 평균(3Y Avg)은 최근 3년 재무제표의 평균값으로 계산된 추정치입니다.")
else:
    st.error("데이터를 가져오는 중 오류가 발생했습니다. 티커를 다시 확인해 주세요.")
