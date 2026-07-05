import streamlit as st
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'components'))
from paper_portfolio_widget import create_portfolio_section

st.set_page_config(
    page_title="Paper Trading Portfolio",
    page_icon="",
    layout="wide"
)

st.title("Paper Trading Portfolio")

create_portfolio_section()
