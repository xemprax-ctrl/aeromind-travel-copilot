from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from aeromind.graph.workflow import AeroMindWorkflow
from aeromind.tools.flights import SEARCH_AIRPORT_CODES


st.set_page_config(page_title="AeroMind Travel Copilot", page_icon="✈", layout="wide")

st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Noto+Kufi+Arabic:wght@400;500;600;700&display=swap');
        :root { --ink:#18232d; --muted:#6d7982; --teal:#0d6b68; --coral:#ef765e; --cream:#f6f3ed; --line:#e6e1d8; }
        html, body, [class*="css"] { font-family: 'DM Sans', 'Noto Kufi Arabic', sans-serif; }
        .stApp { background:var(--cream); color:var(--ink); }
        .block-container { max-width:1220px; padding:2.5rem 3rem 4rem; }
        [data-testid="stSidebar"] { background:#17343b; }
        [data-testid="stSidebar"] * { color:#f6f3ed !important; }
        [data-testid="stSidebar"] .stAlert { background:rgba(255,255,255,.09); border:1px solid rgba(255,255,255,.16); }
        .hero { display:flex; justify-content:space-between; align-items:flex-end; padding:2rem 0 2.2rem; border-bottom:1px solid var(--line); margin-bottom:2rem; }
        .hero-kicker { color:var(--coral); font-weight:700; letter-spacing:.12em; text-transform:uppercase; font-size:.78rem; }
        .hero h1 { font-size:clamp(2rem,4vw,4rem); line-height:1; margin:.45rem 0 .7rem; letter-spacing:-.04em; }
        .hero p { color:var(--muted); margin:0; max-width:560px; font-size:1rem; }
        .hero-mark { color:var(--teal); font-size:4rem; line-height:1; }
        .section-label { color:var(--teal); font-size:.78rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase; margin:1.6rem 0 .5rem; }
        .stButton > button[kind="primary"] { background:var(--coral); border:0; border-radius:8px; min-height:48px; font-weight:700; box-shadow:0 6px 16px rgba(239,118,94,.22); }
        .stButton > button[kind="primary"]:hover { background:#d95f4c; }
        div[data-testid="stMetric"] { background:white; border:1px solid var(--line); border-radius:10px; padding:1rem; }
        div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:10px; overflow:hidden; background:white; }
        .result-note { background:#e2f1e9; border-left:5px solid var(--teal); border-radius:8px; padding:1rem 1.2rem; margin:.7rem 0 1.4rem; }
        .simulation-note { color:var(--muted); font-size:.82rem; margin-top:.4rem; }
        </style>
        """,
        unsafe_allow_html=True,
)

st.markdown(
        """
        <header class="hero" dir="rtl">
            <div>
                <div class="hero-kicker">Agentic travel planning</div>
                <h1>AeroMind Travel Copilot</h1>
                <p>خطط رحلتك بذكاء، قارن المباشر والتوقف، واضبط الميزانية والأمتعة في مسار واحد واضح.</p>
            </div>
            <div class="hero-mark">✈</div>
        </header>
        """,
        unsafe_allow_html=True,
)

if "history" not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header("معلومات المشروع")
    st.info("قاعدة محاكاة ثابتة: 15 وجهة، أكثر من 300 رحلة باتجاهين، و8 شركات طيران.")
    st.caption("OpenRouter وTavily اختياريان ولا يوفران سعرًا حياً للرحلات.")
    st.divider()
    st.markdown("**فريق المشروع**")
    st.markdown("[Abdullah Mohammed Alabdullah](https://github.com/xemprax-ctrl)")
    st.markdown("[Abdullah Salem bin Ghafrah](https://github.com/aspsa1111-dot)")

st.markdown('<div class="section-label">01 / الرحلة</div>', unsafe_allow_html=True)
st.header("صمّم رحلتك")

AIRPORT_LABELS = {
    "LHR": "لندن - Heathrow",
    "DXB": "دبي - Dubai",
    "CAI": "القاهرة - Cairo",
    "DOH": "الدوحة - Doha",
    "IST": "إسطنبول - Istanbul",
    "CDG": "باريس - Paris",
    "AMM": "عمان - Amman",
    "KWI": "الكويت - Kuwait",
    "JED": "جدة - Jeddah",
    "MED": "المدينة المنورة - Medina",
    "BEY": "بيروت - Beirut",
    "TUN": "تونس - Tunis",
    "JFK": "نيويورك - New York",
    "SIN": "سنغافورة - Singapore",
    "BKK": "بانكوك - Bangkok",
    "RUH": "الرياض - Riyadh",
    "DMM": "الدمام - Dammam",
}

search_airports = list(SEARCH_AIRPORT_CODES)
controls = st.columns([2, 2, 2, 1.5, 1.5])
origin_code = controls[0].selectbox("المغادرة", search_airports, format_func=lambda code: AIRPORT_LABELS.get(code, code), index=0)
destination_code = controls[1].selectbox(
    "الوجهة",
    SEARCH_AIRPORT_CODES,
    format_func=lambda code: AIRPORT_LABELS.get(code, code),
    index=SEARCH_AIRPORT_CODES.index("DXB"),
)
budget = controls[2].number_input("الميزانية بالريال", min_value=300, max_value=30000, value=3000, step=100)
extra_bags = controls[3].number_input("عدد الحقائب", min_value=0, max_value=5, value=0, step=1)
trip_mode = controls[4].selectbox("نوع الرحلة", ["مباشرة", "مباشرة أو توقف", "أفضل توقف قريب"])

query = (
    f"رحلة من {origin_code} إلى {destination_code} بميزانية {int(budget)} ريال "
    f"مع {int(extra_bags)} حقيبة إضافية"
)
if trip_mode == "مباشرة":
    query += " مباشرة"
elif trip_mode == "أفضل توقف قريب":
    query += " مع توقف قريب عند مطار مناسب"

st.markdown('<div class="simulation-note">الأسعار والرحلات محاكاة قابلة للاختبار، وليست عروض حجز حية.</div>', unsafe_allow_html=True)
plan_clicked = st.button("ابحث عن أفضل الخيارات", type="primary")

if plan_clicked:
    if origin_code == destination_code:
        st.error("اختر مطارًا مختلفًا للوجهة عن مطار المغادرة.")
    elif not query.strip():
        st.warning("اكتب طلب الرحلة أولاً.")
    else:
        with st.spinner("يتم تحليل الطلب وتشغيل الوكلاء..."):
            workflow = AeroMindWorkflow()
            result = workflow.run(
                query,
                origin=origin_code,
                destination=destination_code,
                budget=float(budget),
                extra_bags=int(extra_bags),
                direct_only=(trip_mode == "مباشرة"),
                allow_stopovers=(trip_mode != "مباشرة"),
                require_stopover=(trip_mode == "أفضل توقف قريب"),
            )

        st.markdown('<div class="section-label">02 / القرار</div>', unsafe_allow_html=True)
        st.header("خلاصة الرحلة")
        status = result["terminal_reason"]
        status_labels = {
            "APPROVED": "تم اعتماد الخطة",
            "SECURITY_BLOCKED": "تم حظر الطلب أمنياً",
            "INVALID_INPUT": "الطلب غير صالح أو الوجهة غير مدعومة",
            "NO_RESULTS": "لا توجد رحلات مطابقة",
            "REVISION_LIMIT": "بلغت المراجعة حد التصحيح",
            "TOOL_FAILURE": "تعذر تشغيل أداة الرحلات",
        }

        if status == "APPROVED":
            st.success(status_labels[status])
        elif status in {"SECURITY_BLOCKED", "INVALID_INPUT", "NO_RESULTS", "REVISION_LIMIT", "TOOL_FAILURE"}:
            st.warning(status_labels[status])
        else:
            st.info(status_labels.get(status, status))

        st.markdown(f'<div class="result-note"><strong>{result["final_response"]}</strong></div>', unsafe_allow_html=True)

        candidates = result.get("candidate_flights", [])
        if candidates:
            direct_count = sum(int(item.get("stops", 0) == 0) for item in candidates)
            stop_count = sum(int(item.get("stops", 0) > 0) for item in candidates)
        else:
            direct_count, stop_count = 0, 0

        summary_cols = st.columns(3)
        summary_cols[0].metric("مرشحات مباشرة", direct_count)
        summary_cols[1].metric("مرشحات بتوقف", stop_count)
        stop_options = [item for item in candidates if item.get("stops", 0) > 0]
        stop_airport = stop_options[0].get("stopover_airport") if stop_options else "لا ينطبق"
        summary_cols[2].metric("أقرب مطار توقف", stop_airport)

        st.markdown('<div class="section-label">03 / المطابقة</div>', unsafe_allow_html=True)
        st.header("القيود التي تم اعتمادها")
        metric_cols = st.columns(5)
        metric_cols[0].metric("الانطلاق", result.get("origin") or "—")
        metric_cols[1].metric("الوجهة", result.get("destination") or "—")
        metric_cols[2].metric("الميزانية", f"{result.get('max_budget') or 0:g} SAR")
        metric_cols[3].metric("رحلة مباشرة", "نعم" if result.get("direct_only") else "لا")
        metric_cols[4].metric("الأمتعة الإضافية", result.get("extra_bags") or 0)

        st.markdown('<div class="section-label">04 / الخيارات</div>', unsafe_allow_html=True)
        st.header("قارن الرحلات")
        candidates = result.get("candidate_flights", [])
        if candidates:
            table = pd.DataFrame(candidates)
            visible_columns = [
                "flight_id", "airline", "origin", "destination",
                "base_price_sar", "tax_sar", "baggage_fee_sar",
                "total_price_sar", "stops", "stopover_airport", "duration",
            ]
            table = table[[column for column in visible_columns if column in table.columns]]
            table = table.rename(columns={
                "flight_id": "الرحلة",
                "airline": "شركة الطيران",
                "origin": "من",
                "destination": "إلى",
                "base_price_sar": "السعر الأساسي",
                "tax_sar": "الضريبة",
                "baggage_fee_sar": "الأمتعة",
                "total_price_sar": "الإجمالي SAR",
                "stops": "التوقفات",
                "stopover_airport": "مطار التوقف",
                "duration": "المدة",
            })
            table["نوع الرحلة"] = table["التوقفات"].apply(
                lambda stops: "مباشرة" if stops == 0 else "بتوقف"
            )
            preferred_columns = [
                "نوع الرحلة", "الرحلة", "شركة الطيران", "من", "إلى",
                "الإجمالي SAR", "التوقفات", "مطار التوقف", "المدة",
            ]
            table = table[[column for column in preferred_columns if column in table.columns]]
            st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.caption("لا توجد مرشحات متاحة لهذه القيود.")

        with st.expander("سجل تنفيذ الوكلاء"):
            st.json(workflow.logger.logs)

        st.session_state.history.append({"query": query, "result": result})

if st.session_state.history:
    st.divider()
    st.subheader("الطلبات السابقة")
    for item in reversed(st.session_state.history[-5:]):
        cols = st.columns([4, 1])
        cols[0].markdown(item["query"])
        cols[1].caption(item["result"]["terminal_reason"])
