"""Streamlit entry point. Run from the project root:  streamlit run frontend/app.py"""
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Medical report simplifier", layout="centered", initial_sidebar_state="collapsed")
st.markdown(f"<style>{(Path(__file__).parent / 'styles' / 'theme.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

from views import home, results  # noqa: E402  (after page config)

(results if "result" in st.session_state else home).render()
