import streamlit as st
from datetime import datetime
import streamlit.components.v1 as components
import base64
import pandas as pd
import time
import requests

API_BASE_URL = "http://127.0.0.1:5000"

st.set_page_config(page_title="Dynamic Merton Backtest", page_icon="", layout="wide")
st.title("Dynamic Merton Backtest")

if "phase"      not in st.session_state: st.session_state.phase      = "input"
if "results"    not in st.session_state: st.session_state.results    = None
if "poll_count" not in st.session_state: st.session_state.poll_count = 0
if "start_date" not in st.session_state: st.session_state.start_date = datetime(2015,1,1).date()
if "end_date"   not in st.session_state: st.session_state.end_date   = datetime(2025,1,1).date()

if st.session_state.phase == "input":
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.start_date = st.date_input("Start Date", st.session_state.start_date)
    with col2:
        st.session_state.end_date = st.date_input("End Date", st.session_state.end_date)

    if st.button("Run Dynamic Merton Backtest", type="primary"):
        st.session_state.phase      = "streaming"
        st.session_state.poll_count = 0
        st.rerun()

elif st.session_state.phase == "streaming":

    # Hide all buttons and inputs during streaming so nothing bleeds through
    st.markdown("""
        <style>
        div.stButton, div.stDownloadButton, div.stFormSubmitButton { display: none !important; }
        div[data-testid="stDateInput"] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

    start_str = st.session_state.start_date.strftime('%Y-%m-%d')
    end_str   = st.session_state.end_date.strftime('%Y-%m-%d')

    components.html(f"""
        <!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <style>
            *{{box-sizing:border-box;margin:0;padding:0}}
            body{{font-family:sans-serif;background:#0e1117;color:#eee;
                  display:flex;flex-direction:column;align-items:center;
                  padding:20px;gap:14px}}
            #status{{font-size:15px;color:#aad4f5;font-weight:500}}
            #bar-wrap{{width:90%;max-width:860px;height:18px;background:#2a2a3a;
                       border-radius:9px;overflow:hidden}}
            #bar{{height:100%;width:0%;background:linear-gradient(90deg,#00c6ff,#0072ff);
                  border-radius:9px;transition:width .15s ease}}
            #img-wrap{{width:90%;max-width:860px;aspect-ratio:14/8;background:#121212;
                       border-radius:10px;display:flex;align-items:center;
                       justify-content:center;overflow:hidden}}
            #frame{{max-width:100%;max-height:100%;object-fit:contain;display:none}}
            #ph{{color:#444;font-size:13px}}
        </style></head><body>
        <div id="status">Connecting...</div>
        <div id="bar-wrap"><div id="bar"></div></div>
        <div id="img-wrap">
            <span id="ph">Waiting for first frame...</span>
            <img id="frame" alt="stream"/>
        </div>
        <script>
            const BACKTEST_KEY = 'backtest_started_{start_str}_{end_str}';
            const status = document.getElementById('status');
            const bar    = document.getElementById('bar');
            const frame  = document.getElementById('frame');
            const ph     = document.getElementById('ph');

            const socket = io("{API_BASE_URL}", {{transports:["websocket"],reconnectionAttempts:10}});

            socket.on('connect', () => {{
                if (!sessionStorage.getItem(BACKTEST_KEY)) {{
                    sessionStorage.setItem(BACKTEST_KEY, '1');
                    status.textContent = 'Connected - starting backtest...';
                    socket.emit('start_backtest_stream', {{start_date:"{start_str}",end_date:"{end_str}"}});
                }} else {{
                    status.textContent = 'Reconnected - backtest running...';
                }}
            }});

            socket.on('connect_error', e => {{ status.textContent = 'Connection error: '+e.message; }});

            socket.on('backtest_frame', d => {{
                if(frame.style.display!=='block'){{frame.style.display='block';ph.style.display='none';}}
                frame.src='data:image/png;base64,'+d.frame;
                bar.style.width=d.progress+'%';
                status.textContent='Rendering... '+Math.round(d.progress)+'%';
            }});

            socket.on('backtest_results', ()=>{{
                bar.style.width='100%';
                status.textContent='Done! Results loading...';
                sessionStorage.removeItem(BACKTEST_KEY);
            }});

            socket.on('stream_error', d=>{{
                status.textContent='Error: '+d.error;
                sessionStorage.removeItem(BACKTEST_KEY);
            }});
        </script></body></html>
    """, height=560)

    pc = st.session_state.poll_count

    if pc >= 600:
        st.error("Timed out waiting for results. Please try again.")
        st.stop()

    ready = False
    try:
        r = requests.get(f"{API_BASE_URL}/get_results/latest", timeout=3)
        if r.status_code == 200 and r.json().get("ready"):
            st.session_state.results    = r.json()["results"]
            st.session_state.phase      = "results"
            st.session_state.poll_count = 0
            ready = True
    except Exception:
        pass

    if ready:
        st.rerun()
    else:
        st.session_state.poll_count += 1
        time.sleep(2)
        st.rerun()

elif st.session_state.phase == "results":
    results = st.session_state.results

    if st.button("Run New Backtest"):
        try:
            requests.post(f"{API_BASE_URL}/clear_results", timeout=2)
        except Exception:
            pass
        st.session_state.phase      = "input"
        st.session_state.results    = None
        st.session_state.poll_count = 0
        st.rerun()

    if "error" in results:
        st.error(f"Backtest error: {results['error']}")
    else:
        st.success("Backtest complete!")

        final_b64 = results.get("final_frame_b64", "")
        if final_b64:
            st.subheader("Backtest Final State")
            st.image(base64.b64decode(final_b64), use_container_width=True)

        dash_html = results.get("dashboard_html")
        if dash_html:
            st.subheader("Interactive Backtest Dashboard")
            components.html(dash_html, height=750, scrolling=True)

        st.subheader("Performance Summary")
        c1, c2, c3 = st.columns(3)
        c1.metric("Final Portfolio Value",   f"${results.get('final_portfolio_value', 0):,.2f}")
        c2.metric("CAGR",                    f"{results.get('cagr_percent', 0):,.2f}%")
        c3.metric("Annualised Sharpe Ratio", f"{results.get('annualized_sharpe_ratio', 0):.2f}")

        c1, c2, c3, c4 = st.columns(4)
        ta = results.get('trade_analysis', {})
        c1.metric("Max Drawdown",   f"{results.get('max_drawdown_percent', 0):,.2f}%")
        c2.metric("Total Trades",   ta.get('total_trades',   0))
        c3.metric("Winning Trades", ta.get('winning_trades', 0))
        c4.metric("Losing Trades",  ta.get('losing_trades',  0))

        st.write("**Annual Returns**")
        if 'annual_returns_df' in results:
            try:
                raw = results['annual_returns_df']
                if isinstance(raw, dict):
                    df = pd.DataFrame(raw['data'], index=raw.get('index'), columns=raw.get('columns'))
                elif isinstance(raw, str):
                    df = pd.read_json(raw, orient='split')
                else:
                    df = pd.DataFrame(raw)
                st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.error(f"Could not parse annual returns: {e}")