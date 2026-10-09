import pandas as pd
import streamlit as st

from components import report_view
from services import api_client
from views.home import language_picker


def _rerun(language: dict, measurements: list[dict] | None = None) -> None:
    try:
        with st.spinner("Writing the explanation and running safety checks"):
            res = api_client.simplify(st.session_state.report_id, language["code"], measurements)
        st.session_state.update(result=res, rtl=language["rtl"])
        st.rerun()
    except api_client.ApiError as e:
        st.error(str(e))


def render() -> None:
    res, ex = st.session_state.result, st.session_state.extraction
    top = st.columns([3, 1])
    top[0].markdown("# Your report explained")
    if top[1].button("Start over"):
        for k in ("result", "extraction", "report_id", "rtl"):
            st.session_state.pop(k, None)
        st.rerun()

    report_view.render(res, ex.get("text"), st.session_state.get("rtl", False))

    st.subheader("Change language or correct values")
    c1, c2 = st.columns([2, 1])
    with c1:
        lang = language_picker(key="language_results", default=res["language"])
    with c2:
        st.write("")
        st.write("")
        if st.button("Explain in this language"):
            _rerun(lang)

    if res["measurements"]:
        with st.expander("A value looks wrong? Correct it and explain again"):
            st.caption("Scanned documents can be misread. Edit the text below, then explain again. "
                       "Low, normal and high are always recalculated from the range you enter.")
            df = pd.DataFrame([{"id": m["id"], "test_name": m["test_name"], "value_text": m["value_text"], "unit": m["unit"],
                                "reference_range_text": m["reference_range_text"]} for m in res["measurements"]])
            edited = st.data_editor(df, disabled=["id"], hide_index=True, width="stretch", key="editor")
            if st.button("Explain again with these values"):
                by_id = {m["id"]: m for m in res["measurements"]}
                payload = []
                for _, row in edited.iterrows():
                    m = dict(by_id[row["id"]])
                    m.update(test_name=row["test_name"], value_text=row["value_text"], unit=row["unit"],
                             reference_range_text=row["reference_range_text"])
                    payload.append(m)
                _rerun(lang, payload)
