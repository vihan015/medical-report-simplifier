import html

import streamlit as st

NOTICE_EN = ("This tool explains the values printed on your report in simple words. It does not diagnose any disease, "
             "does not give treatment or medicine advice, and is not a substitute for a doctor. Always discuss your report "
             "with a qualified doctor.")


def render(localized: str | None = None) -> None:
    body = f"<b>Important.</b> {html.escape(NOTICE_EN)}"
    if localized:
        body += f"<br><br>{html.escape(localized)}"
    st.markdown(f'<div class="notice">{body}</div>', unsafe_allow_html=True)
