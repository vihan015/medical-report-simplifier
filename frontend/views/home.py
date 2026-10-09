import streamlit as st

from components import safety_notice, uploader
from services import api_client


@st.cache_data(ttl=300, show_spinner=False)
def _languages() -> list[dict]:
    return api_client.languages()


def language_picker(key: str = "language", default: str = "hi") -> dict:
    try:
        langs = _languages()
    except api_client.ApiError as e:
        st.error(str(e))
        st.stop()
    codes = [l["code"] for l in langs]
    by_code = {l["code"]: l for l in langs}
    choice = st.selectbox("Explain in", codes, index=codes.index(default), key=key,
                          format_func=lambda c: f"{by_code[c]['native']}  -  {by_code[c]['name']}")
    if by_code[choice]["tier"] == 2:
        st.markdown('<div class="notice-secondary">Explanations in this language are less tested. Please have them checked '
                    "by a fluent speaker or your doctor before relying on them.</div>", unsafe_allow_html=True)
    return by_code[choice]


def render() -> None:
    st.markdown("# Medical report simplifier")
    st.markdown('<div class="lede">Upload a lab report or prescription and read what it says in plain words, '
                "in your own language.</div>", unsafe_allow_html=True)
    safety_notice.render()

    file = uploader.render()
    lang = language_picker()
    if st.button("Simplify", type="primary", disabled=file is None):
        try:
            with st.status("Processing your report", expanded=True) as status:
                st.write("Uploading and checking the file")
                up = api_client.upload(file.name, file.getvalue(), file.type)
                st.write("Reading the document (OCR is used for scanned pages)")
                ex = api_client.extract(up["report_id"])
                for w in ex["warnings"]:
                    st.write(w)
                st.write("Finding reference material, writing the explanation and running safety checks")
                res = api_client.simplify(up["report_id"], lang["code"])
                status.update(label="Done", state="complete")
            st.session_state.update(report_id=up["report_id"], extraction=ex, result=res, rtl=lang["rtl"])
            st.rerun()
        except api_client.ApiError as e:
            st.error(str(e))
