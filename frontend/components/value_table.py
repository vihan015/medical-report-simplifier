import html

import streamlit as st

LABEL = {"low": "Low", "normal": "Normal", "high": "High", "unknown": "Unknown"}


def badge(status: str, label: str | None = None) -> str:
    return f'<span class="badge badge-{status}">{html.escape(label or LABEL[status])}</span>'


def render(measurements: list[dict]) -> None:
    if not measurements:
        st.markdown('<div class="notice-secondary">No lab values were recognised.</div>', unsafe_allow_html=True)
        return
    rows = "".join(
        f"<tr><td>{html.escape(m['test_name'])}</td><td>{html.escape(m['value_text'])}</td><td>{html.escape(m['unit'])}</td>"
        f"<td>{html.escape(m['reference_range_text'] or 'not printed')}</td><td>{badge(m['status'])}</td>"
        f"<td>{int(round(m['confidence'] * 100))}%</td></tr>" for m in measurements)
    st.markdown(
        '<div class="table-wrap"><table class="facts"><thead><tr><th>Test</th><th>Value</th><th>Unit</th>'
        '<th>Range in report</th><th>Status</th><th>Read confidence</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>", unsafe_allow_html=True)
