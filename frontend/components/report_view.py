import html

import streamlit as st

from components import safety_notice, value_table


def _dir(rtl: bool) -> str:
    return ' dir="rtl"' if rtl else ""


def explanation_card(item: dict, rtl: bool) -> None:
    attention = item["status"] in ("low", "high") or item["low_confidence"]
    ref = f" &nbsp;|&nbsp; Range in report: {html.escape(item['reference_range_text'])}" if item.get("reference_range_text") else ""
    meta = f"{html.escape(item['value_text'])} {html.escape(item['unit'])}{ref}".strip() if item["kind"] == "measurement" else ""
    badge = value_table.badge(item["status"], item["status_label"] or None) if item["kind"] == "measurement" else ""
    warn = "".join(f"<div>{html.escape(line)}</div>" for line in item["warning"].splitlines() if line.strip())
    st.markdown(
        f'<div class="card{" attention" if attention else ""}"><h4>{html.escape(item["title"])} {badge}</h4>'
        f'<div class="meta">{meta}</div><div class="body"{_dir(rtl)}>{html.escape(item["explanation"])}</div>'
        f'{f"<div class=warning{_dir(rtl)}>{warn}</div>" if warn else ""}</div>', unsafe_allow_html=True)


def render(result: dict, extraction_text: str | None, rtl: bool) -> None:
    safety_notice.render(result["disclaimer"] if result["language"] != "en" else None)

    if result["fallback_used"]:
        st.markdown('<div class="notice-secondary"><b>Plain facts only.</b> A full explanation could not be verified as safe '
                    f"for this report, so only the extracted facts are shown. Reason: {html.escape(result['fallback_reason'])}</div>",
                    unsafe_allow_html=True)

    st.subheader("Report summary")
    n_m, n_p = len(result["measurements"]), len(result["prescription_items"])
    flagged = [m for m in result["measurements"] if m["status"] in ("low", "high")]
    st.write(f"Document type: {result['document_type'].replace('_', ' ')}. {n_m} lab value(s) and {n_p} prescription line(s) read. "
             f"{len(flagged)} value(s) outside the range printed in the report.")
    if result["overall_summary"]:
        st.markdown(f'<div class="body"{_dir(rtl)}>{html.escape(result["overall_summary"])}</div>', unsafe_allow_html=True)

    st.subheader("Extracted facts")
    st.caption("Read directly from your document. Check these against the paper report.")
    value_table.render(result["measurements"])

    if flagged:
        st.subheader("Values outside the report range")
        for it in result["items"]:
            if it["kind"] == "measurement" and it["status"] in ("low", "high"):
                explanation_card(it, rtl)

    st.subheader("Explanation")
    for it in result["items"]:
        if it["kind"] == "measurement" and it["status"] not in ("low", "high"):
            explanation_card(it, rtl)

    rx = [i for i in result["items"] if i["kind"] == "prescription"]
    if rx:
        st.subheader("Prescription, as written")
        for it in rx:
            explanation_card(it, rtl)

    if result["questions_for_doctor"]:
        st.subheader("Questions you can ask your doctor")
        st.markdown(f'<div class="body"{_dir(rtl)}>' + "".join(f"<div>- {html.escape(q)}</div>" for q in result["questions_for_doctor"]) + "</div>",
                    unsafe_allow_html=True)

    with st.expander("Reference material used"):
        if not result["references"]:
            st.write("No reference passages were used.")
        for c in result["references"]:
            st.markdown(f"**{c['section']}**  \n{c['text']}  \n<span class='muted'>Source: {html.escape(c['source'])}, version {html.escape(c['version'])}</span>",
                        unsafe_allow_html=True)
    if extraction_text:
        with st.expander("Extracted text"):
            st.text(extraction_text)
    with st.expander("Safety checks"):
        s = result["safety"]
        st.write(f"Result: {'passed' if s['passed'] else 'not passed'}. Independent review used: {'yes' if s['judge_used'] else 'no'}. "
                 f"Model: {result['model']}.")
        if s["metrics"]:
            st.json({k: round(v, 3) for k, v in s["metrics"].items()})
        for v in s["violations"]:
            st.write(f"- {v['check']} ({v['severity']}): {v['detail']}")

    st.markdown("---")
    safety_notice.render(result["disclaimer"] if result["language"] != "en" else None)
