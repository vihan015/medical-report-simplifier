import html

import streamlit as st

from components import safety_notice, value_table


def _dir(rtl: bool) -> str:
    return ' dir="rtl"' if rtl else ""


SECTIONS = ("what_it_is", "what_it_means", "should_i_worry", "when_to_see_doctor")


def explanation_card(item: dict, rtl: bool, labels: dict) -> None:
    attention = item["status"] in ("low", "high") or item["low_confidence"]
    ref = f" &nbsp;|&nbsp; Range in report: {html.escape(item['reference_range_text'])}" if item.get("reference_range_text") else ""
    meta = f"{html.escape(item['value_text'])} {html.escape(item['unit'])}{ref}".strip() if item["kind"] == "measurement" else ""
    badge = value_table.badge(item["status"], item["status_label"] or None) if item["kind"] == "measurement" else ""
    d = _dir(rtl)
    warn = "".join(f"<div>{html.escape(line)}</div>" for line in item["warning"].splitlines() if line.strip())
    parts = ""
    for key in SECTIONS:
        text = (item.get(key) or "").strip()
        if text:
            parts += (f'<div class="section"><div class="section-title"{d}>{html.escape(labels.get(key, key))}</div>'
                      f'<div class="body"{d}>{html.escape(text)}</div></div>')
    if not parts:  # prescription lines and plain-fact fallback
        parts = f'<div class="body"{d}>{html.escape(item["explanation"])}</div>'
    else:
        parts = f'<div class="muted"{d}>{html.escape(item["explanation"])}</div>' + parts
    warn_html = f'<div class="warning"{d}>{warn}</div>' if warn else ""
    st.markdown(f'<div class="card{" attention" if attention else ""}"><h4>{html.escape(item["title"])} {badge}</h4>'
                f'<div class="meta">{meta}</div>{warn_html}{parts}</div>', unsafe_allow_html=True)


def render(result: dict, extraction_text: str | None, rtl: bool) -> None:
    safety_notice.render(result["disclaimer"] if result["language"] != "en" else None)
    labels = result.get("section_labels") or {}
    if result.get("emergency_note"):
        st.markdown(f'<div class="notice"{_dir(rtl)}><b>!</b> {html.escape(result["emergency_note"])}</div>', unsafe_allow_html=True)

    if result["fallback_used"]:
        st.markdown(f'<div class="notice-secondary"><b>{result["template_items"]} item(s) show basic information only.</b> '
                    "A full explanation for these could not be verified as safe. They still show the status and when to see a doctor. "
                    f"{html.escape(result['fallback_reason'])}</div>", unsafe_allow_html=True)

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
                explanation_card(it, rtl, labels)

    st.subheader("Explanation")
    for it in result["items"]:
        if it["kind"] == "measurement" and it["status"] not in ("low", "high"):
            explanation_card(it, rtl, labels)

    rx = [i for i in result["items"] if i["kind"] == "prescription"]
    if rx:
        st.subheader("Prescription, as written")
        for it in rx:
            explanation_card(it, rtl, labels)

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
