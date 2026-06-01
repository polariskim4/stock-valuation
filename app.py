import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(page_title="US Stock Valuation Dashboard", layout="wide")

st.title("📊 미국 주식 밸류에이션 분석 대시보드")
st.markdown("티커를 입력하면 현재 밸류에이션 지표를 경쟁사 및 역사적 수치와 비교합니다.")

# 사이드바: 티커 입력 및 경쟁사 설정
with st.sidebar:
    ticker_symbol = st.text_input("분석할 티커 입력 (예: AAPL)", value="AAPL").upper()
    compare_tickers = st.text_input("비교할 경쟁사 티커 (쉼표 구분)", value="MSFT, GOOGL, AMZN").upper().split(',')
    compare_tickers = [t.strip() for t in compare_tickers]

@st.cache_data
def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return info
    except:
        return None

# 데이터 가져오기
target_info = get_stock_data(ticker_symbol)

if target_info:
    # 대시보드 상단 요약
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("종목명", target_info.get('longName'))
    col2.metric("현재가", f"${target_info.get('currentPrice')}")
    col3.metric("섹터", target_info.get('sector'))
    col4.metric("시가총액", f"${target_info.get('marketCap', 0):,}")

    # 밸류에이션 지표 추출 함수
    def extract_metrics(info):
        return {
            "PER (Trailing)": info.get('trailingPE'),
            "Forward PER": info.get('forwardPE'),
            "PEG Ratio": info.get('pegRatio'),
            "P/S Ratio": info.get('priceToSalesTrailing12Months'),
            "EV/EBITDA": info.get('enterpriseToEbitda'),
            "P/B Ratio": info.get('priceToBook')
        }

    target_metrics = extract_metrics(target_info)
    
    # 경쟁사 데이터 수집
    comparison_data = []
    comparison_data.append({"Ticker": ticker_symbol, **target_metrics})
    
    for t in compare_tickers:
        c_info = get_stock_data(t)
        if c_info:
            comparison_data.append({"Ticker": t, **extract_metrics(c_info)})
    
    df_compare = pd.DataFrame(comparison_data).set_index("Ticker")

    # 시각화 부분
    st.subheader("📋 밸류에이션 지표 비교")
    
    metrics_to_show = ["PER (Trailing)", "Forward PER", "PEG Ratio", "P/S Ratio", "EV/EBITDA", "P/B Ratio"]
    
    # 탭을 이용한 지표별 차트 구성
    tabs = st.tabs(metrics_to_show)
    
    for i, metric in enumerate(metrics_to_show):
        with tabs[i]:
            fig = go.Figure()
            # 경쟁사들 바 차트
            fig.add_trace(go.Bar(
                x=df_compare.index,
                y=df_compare[metric],
                marker_color=['#1f77b4' if x == ticker_symbol else '#d3d3d3' for x in df_compare.index],
                text=df_compare[metric].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "N/A"),
                textposition='auto'
            ))
            
            # 평균선 추가
            avg_val = df_compare[metric].mean()
            fig.add_shape(type="line", line=dict(color="Red", dash="dash"),
                          x0=-0.5, x1=len(df_compare)-0.5, y0=avg_val, y1=avg_val)
            
            fig.update_layout(title=f"{metric} 비교 (빨간선: 그룹 평균)", 
                              yaxis_title="배수",
                              showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    # 상세 데이터 테이블
    st.subheader("데이터 상세 보기")
    st.dataframe(df_compare.style.highlight_max(axis=0, color='#ffcccc').highlight_min(axis=0, color='#ccffcc'))

    st.info("""
    **💡 지표 가이드:**
    - **PER**: 이익 대비 주가 수준. 낮을수록 저평가이나 성장성이 낮을 수 있음.
    - **PEG**: PER을 성장률로 나눈 값. 보통 1 미만이면 매우 매력적.
    - **P/S**: 매출 대비 주가. 이익이 나지 않는 성장주 분석에 유용.
    - **EV/EBITDA**: 영업현금창출능력 대비 기업가치. 감가상각비 영향을 배제함.
    """)
else:
    st.error("티커를 찾을 수 없습니다. 정확한 심볼을 입력해주세요.")
streamlit
yfinance
pandas
plotly
