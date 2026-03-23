"""
================================================================================
  E-COMMERCE PERFORMANCE DASHBOARD  |  Streamlit App
  Compatible with: Python 3.9+  |  Streamlit 1.28+
================================================================================
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import re
import os

# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="E-Commerce Performance Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global styling (UX/UI Upgrades & Responsive CSS Grid) ──────────────────────
st.markdown("""
<style>
    /* Main Layout */
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    
    /* CSS Grid สำหรับ KPI Cards (รองรับมือถือ/iPad อัตโนมัติ) */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 16px;
        margin-bottom: 24px;
    }
    
    /* CSS Grid สำหรับ Platform Cards */
    .plat-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 16px;
    }

    /* KPI Cards - Glassmorphism & Depth */
    .kpi-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 16px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2), 0 4px 6px -2px rgba(0, 0, 0, 0.1);
        border-color: #475569;
    }
    .kpi-label {
        font-size: 13px; color: #94a3b8; font-weight: 600; 
        text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;
    }
    .kpi-value { font-size: 32px; font-weight: 800; color: #f8fafc; letter-spacing: -0.02em; }
    .kpi-delta { font-size: 14px; margin-top: 8px; font-weight: 600; }
    
    /* Semantic Colors */
    .delta-good  { color: #10b981; } /* Emerald Green */
    .delta-warn  { color: #f59e0b; } /* Amber */
    .delta-bad   { color: #ef4444; } /* Rose Red */
    .delta-neutral { color: #94a3b8; } /* Slate */
    
    /* Section Headers */
    .section-header {
        font-size: 22px; font-weight: 700; color: #f8fafc;
        margin: 40px 0 20px 0; border-left: 5px solid #6366f1;
        padding-left: 16px; letter-spacing: -0.01em;
    }
    
    /* Platform Progress Container */
    .plat-container {
        background-color: #1e293b;
        padding: 16px 20px; border-radius: 12px; border: 1px solid #334155;
        box-shadow: 0 1px 3px 0 rgba(0,0,0,0.1);
        transition: border-color 0.2s ease;
    }
    .plat-container:hover { border-color: #64748b; }
    .plat-title {
        font-size: 16px; font-weight: 700; color: #f8fafc;
        margin-bottom: 14px; display: flex; justify-content: space-between;
    }
    .progress-track {
        background-color: #334155; border-radius: 9999px;
        height: 10px; width: 100%; margin-bottom: 6px; position: relative; overflow: hidden;
    }
    .progress-fill-rev { background-color: #10b981; height: 100%; border-radius: 9999px; }
    .progress-fill-ad { background-color: #FFC1BA; height: 100%; border-radius: 9999px; }
    .progress-label {
        font-size: 13px; color: #cbd5e1; display: flex; font-weight: 500;
        justify-content: space-between; margin-top: -2px; margin-bottom: 12px;
    }

    /* Media Query for smaller screens */
    @media (max-width: 768px) {
        .kpi-value { font-size: 26px; }
        .kpi-card { padding: 16px; }
        .section-header { font-size: 18px; margin: 30px 0 15px 0; }
    }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def fmt_thb(value: float) -> str:
    if pd.isna(value): return "฿0"
    if abs(value) >= 1_000_000:
        return f"฿{value/1_000_000:.2f}M"
    elif abs(value) >= 1_000:
        return f"฿{value:,.0f}"
    else:
        return f"฿{value:.0f}"

def load_and_clean(file):
    try:
        filename = file.name.lower() if hasattr(file, 'name') else "default_data.csv"
        if filename.endswith(".csv"):
            try:
                file.seek(0)
                df_raw = pd.read_csv(file)
            except Exception:
                file.seek(0)
                df_raw = pd.read_csv(file, sep=None, engine='python')
        else:
            df_raw = pd.read_excel(file)

        metric_col = None
        max_metric_hits = 0
        keywords = ['revenue', 'cost', 'spend', 'fee', 'orders', 'margin']
        
        for col in df_raw.columns:
            if df_raw[col].dtype == object:
                pattern = '|'.join(keywords)
                hits = df_raw[col].astype(str).str.lower().str.contains(pattern, na=False).sum()
                if hits > max_metric_hits:
                    max_metric_hits = hits
                    metric_col = col

        if not metric_col: return None

        date_cols = []
        for col in df_raw.columns:
            if re.match(r'\d{1,4}[-/]\d{1,2}[-/]\d{2,4}', str(col)):
                date_cols.append(col)
                
        if not date_cols: return None

        parsed_data = []
        current_platform = "Unknown"
        
        for index, row in df_raw.iterrows():
            metric_raw = str(row[metric_col]).strip()
            metric_lower = metric_raw.lower()
            
            if not metric_raw or metric_raw == 'nan' or metric_lower.startswith('total') or metric_lower.startswith('overall'):
                continue
            
            metric_type = None
            if "revenue" in metric_lower and "contribution" not in metric_lower:
                current_platform = re.sub(r'(?i)\s*revenue\s*', '', metric_raw).strip()
                metric_type = "revenue"
            elif "product cost" in metric_lower:
                metric_type = "product_cost"
            elif "platform fee" in metric_lower:
                metric_type = "platform_fee"
            elif "ad spend" in metric_lower:
                metric_type = "ad_spend"
            elif "orders" in metric_lower and "contribution" not in metric_lower:
                metric_type = "orders"
            else:
                continue 
            
            for col in date_cols:
                val = row[col]
                val_str = str(val).strip()
                if pd.isna(val) or val_str in ['-', '', 'NaN', 'nan', '#REF!']:
                    clean_val = 0.0
                else:
                    val_str = val_str.replace(',', '').replace('฿', '').replace(' ', '')
                    if val_str.startswith('(') and val_str.endswith(')'):
                        val_str = '-' + val_str[1:-1]
                    try:
                        clean_val = float(val_str)
                    except ValueError:
                        clean_val = 0.0
                        
                parsed_data.append({
                    "date": col, "platform": current_platform,
                    "metric": metric_type, "value": clean_val
                })
                
        if not parsed_data: return None
            
        df_long = pd.DataFrame(parsed_data)
        df_piv = df_long.pivot_table(index=["date", "platform"], columns="metric", values="value", aggfunc="sum").reset_index()
        
        for c in ["revenue", "product_cost", "platform_fee", "ad_spend", "orders"]:
            if c not in df_piv.columns: df_piv[c] = 0.0
                
        df_piv = df_piv.fillna(0)
        df_piv["date"] = pd.to_datetime(df_piv["date"], errors="coerce", dayfirst=True)
        df_piv = df_piv.dropna(subset=["date"])
        
        df_piv["cogs"] = df_piv["product_cost"] + df_piv["platform_fee"]
        df_piv = df_piv[(df_piv["revenue"] > 0) | (df_piv["ad_spend"] > 0)]
        df_piv["gross_profit"] = df_piv["revenue"] - df_piv["cogs"]
        df_piv["cm"] = df_piv["revenue"] - df_piv["cogs"] - df_piv["ad_spend"]
        df_piv["roas"] = df_piv.apply(lambda r: r["revenue"] / r["ad_spend"] if r["ad_spend"] > 0 else 0, axis=1)

        return df_piv
    
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        return None

def render_progress_bar(label: str, current: float, target: float, pacing_pct: float, color: str = "#10b981"):
    pct = min(current / target, 1.0) * 100 if target > 0 else 0
    raw_pct = (current / target) * 100 if target > 0 else 0
    time_pct = pacing_pct * 100
    
    label_text = f"{label}   |   {fmt_thb(current)} / {fmt_thb(target)}   (ทำได้ {raw_pct:.1f}%)"

    fig = go.Figure(go.Bar(
        x=[pct], y=[""], orientation="h", marker_color=color,
        text=[f" {raw_pct:.1f}% "], textposition="auto", textfont=dict(color="#ffffff", size=14, weight="bold"),
        cliponaxis=False,
        hovertemplate=f"ทำได้จริง: {fmt_thb(current)} ({raw_pct:.1f}%)<br>เป้าตามเวลา: {time_pct:.0f}%<extra></extra>",
    ))
    
    fig.add_shape(type="line", x0=100, x1=100, y0=-0.5, y1=0.5, line=dict(color="rgba(255,255,255,0.2)", width=2, dash="solid"))
    fig.add_shape(type="line", x0=time_pct, x1=time_pct, y0=-0.6, y1=0.6, line=dict(color="#ef4444", width=3, dash="dot"))
    
    fig.add_annotation(
        x=time_pct, y=0.5, text=f"📍 เวลาผ่านไป {time_pct:.0f}%", 
        showarrow=False, yshift=24, font=dict(color="#fca5a5", size=12, weight="bold")
    )

    fig.update_layout(
        title=dict(text=label_text, font=dict(size=15, color="#f8fafc", weight="bold"), x=0.01),
        xaxis=dict(range=[0, max(max(raw_pct, time_pct) * 1.15, 110)], showticklabels=False, showgrid=False),
        yaxis=dict(showticklabels=False, showgrid=False),
        height=100, margin=dict(l=10, r=50, t=45, b=10),
        paper_bgcolor="#1e293b", plot_bgcolor="#1e293b", bargap=0.4,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

def generate_channel_progress_html(platform_name, rev, total_rev, ad, total_ad, roas, cm):
    rev_pct = (rev / total_rev * 100) if total_rev > 0 else 0
    ad_pct = (ad / total_ad * 100) if total_ad > 0 else 0
    roas_color = "#10b981" if roas >= 4 else ("#f59e0b" if roas >= 2 else "#ef4444")
    
    # ลบการย่อหน้า (Indent) ด้านหน้า HTML ออก เพื่อไม่ให้ Streamlit มองว่าเป็น Code block
    html = f"""<div class="plat-container">
<div class="plat-title">
<span style="color: #f8fafc;">{platform_name}</span>
<span style="color: {roas_color}; font-size: 14px;">ROAS: {roas:.1f}x | CM: {fmt_thb(cm)}</span>
</div>
<div class="progress-track">
<div class="progress-fill-rev" style="width: {min(rev_pct, 100)}%;"></div>
</div>
<div class="progress-label" style="color: #cbd5e1;">
<span>Sales Share</span>
<span style="color: #ffffff !important; font-weight: 700;">{fmt_thb(rev)} ({rev_pct:.1f}%)</span>
</div>
<div class="progress-track">
<div class="progress-fill-ad" style="width: {min(ad_pct, 100)}%;"></div>
</div>
<div class="progress-label" style="color: #cbd5e1; margin-bottom: 0;">
<span>Ads Share</span>
<span style="color: #ffffff !important; font-weight: 700;">{fmt_thb(ad)} ({ad_pct:.1f}%)</span>
</div>
</div>"""
    return html

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/combo-chart.png", width=60)
    st.title("Executive Hub")
    st.caption("E-Commerce Performance Tracker")
    st.divider()

    uploaded_file = st.file_uploader("📂 Upload Data (Excel/CSV)", type=["xlsx", "xls", "csv"])

    st.divider()
    st.markdown("**⚙️ Targets & Budget**")
    sales_input = st.text_input("Sales Target (THB)", value="10,000,000")
    ad_input = st.text_input("Ad Spend Budget (THB)", value="1,000,000")
    
    try:
        sales_target = float(sales_input.replace(",", "").strip())
        ad_budget = float(ad_input.replace(",", "").strip())
    except ValueError:
        st.error("⚠️ กรุณากรอกตัวเลขเป้าหมายให้ถูกต้อง")
        sales_target = 10000000.0
        ad_budget = 1000000.0

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("## 📊 Executive Performance Dashboard")
st.caption("Real-time data insights tracker")

DEFAULT_FILE = "default_data.csv" 

if uploaded_file is not None:
    df = load_and_clean(uploaded_file)
    st.sidebar.success("✅ แสดงผลข้อมูลจากไฟล์ของคุณ")
elif os.path.exists(DEFAULT_FILE):
    with open(DEFAULT_FILE, "rb") as f:
        df = load_and_clean(f)
    st.sidebar.info(f"ℹ️ กำลังแสดงผลข้อมูลตัวอย่าง ({DEFAULT_FILE})")
else:
    st.info("👈 **Upload your Excel/CSV file** in the sidebar to get started.")
    st.stop()

if df is None or df.empty:
    st.error("⚠️ ไม่สามารถอ่านข้อมูลได้ โปรดตรวจสอบโครงสร้างของไฟล์")
    st.stop()

# เก็บ Data ต้นฉบับไว้เพื่อเปรียบ% MOM
df_full = df.copy()

# กำหนดตัวแปรเก็บยอดเดือนก่อน
prev_revenue = 0.0
prev_ad_spend = 0.0
prev_cm = 0.0

if "date" in df.columns and df["date"].notna().any():
    with st.sidebar:
        st.divider()
        st.markdown("**📅 Date Range Filter**")
        
        min_d = df_full["date"].min().date()
        max_d = df_full["date"].max().date()
        
        # ตั้งค่า Default ให้เลือกเฉพาะ "เดือนล่าสุด"
        default_start = pd.Timestamp(max_d).replace(day=1).date()
        
        date_range = st.date_input("Select range", value=(default_start, max_d), min_value=min_d, max_value=max_d)
        
        if len(date_range) == 2:
            df = df_full[(df_full["date"].dt.date >= date_range[0]) & (df_full["date"].dt.date <= date_range[1])]
            
            prev_start = (pd.to_datetime(date_range[0]) - pd.DateOffset(months=1)).date()
            prev_end = (pd.to_datetime(date_range[1]) - pd.DateOffset(months=1)).date()
            
            df_prev = df_full[(df_full["date"].dt.date >= prev_start) & (df_full["date"].dt.date <= prev_end)]
            prev_revenue = df_prev["revenue"].sum()
            prev_ad_spend = df_prev["ad_spend"].sum()
            prev_cm = df_prev["cm"].sum()

# คำนวณยอดปัจจุบัน
total_revenue   = df["revenue"].sum()
total_ad_spend  = df["ad_spend"].sum()
total_orders    = int(df["orders"].sum())
total_cm        = df["cm"].sum()
overall_roas    = total_revenue / total_ad_spend if total_ad_spend > 0 else 0
cm_pct          = (total_cm / total_revenue * 100) if total_revenue > 0 else 0

if "date" in df.columns and df["date"].notna().any():
    max_date = df["date"].max()
    days_elapsed = max_date.day 
    days_in_month = max_date.days_in_month
else:
    days_elapsed = 10
    days_in_month = 31

pacing_pct = days_elapsed / days_in_month

# -----------------------------------------------------------------------------
# คำนวณ % การเติบโต MoM และ Pacing (ย้ายมารวมไว้ที่ KPI Cards)
# -----------------------------------------------------------------------------
mom_rev_pct = ((total_revenue - prev_revenue) / abs(prev_revenue)) * 100 if prev_revenue != 0 else 0.0
mom_ad_pct  = ((total_ad_spend - prev_ad_spend) / abs(prev_ad_spend)) * 100 if prev_ad_spend != 0 else 0.0
mom_cm_pct  = ((total_cm - prev_cm) / abs(prev_cm)) * 100 if prev_cm != 0 else 0.0

# คำนวณ Revenue Pacing
expected_rev = sales_target * pacing_pct
rev_pace_diff_pct = ((total_revenue - expected_rev) / expected_rev) * 100 if expected_rev > 0 else 0

# คำนวณ Ad Spend Pacing
expected_ad = ad_budget * pacing_pct
ad_pace_diff_pct = ((total_ad_spend - expected_ad) / expected_ad) * 100 if expected_ad > 0 else 0

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: KPIs AND GLOBAL TARGETS (Responsive CSS Grid)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">📌 Key Performance Indicators</div>', unsafe_allow_html=True)

# --- เตรียม HTML สำหรับ KPI: Revenue ---
rev_mom_html = f'<div class="kpi-delta {"delta-good" if mom_rev_pct >= 0 else "delta-bad"}">% MOM: {"+" if mom_rev_pct > 0 else ""}{mom_rev_pct:.1f}%</div>' if prev_revenue > 0 else ''
rev_pace_class = "delta-good" if rev_pace_diff_pct >= 0 else "delta-bad"
rev_pace_icon = "🟢" if rev_pace_diff_pct >= 0 else "🔴"
rev_pace_label = "นำหน้าเป้าเวลา" if rev_pace_diff_pct >= 0 else "ตามหลังเป้าเวลา"
rev_pace_html = f'<div class="kpi-delta {rev_pace_class}" style="margin-top: 4px; font-size: 13px;">{rev_pace_icon} {rev_pace_label} {abs(rev_pace_diff_pct):.1f}%</div>'

# --- เตรียม HTML สำหรับ KPI: Ad Spend ---
ad_mom_html = f'<div class="kpi-delta {"delta-warn" if mom_ad_pct > 0 else "delta-good"}">% MOM: {"+" if mom_ad_pct > 0 else ""}{mom_ad_pct:.1f}%</div>' if prev_ad_spend > 0 else ''
ad_pace_class = "delta-warn" if ad_pace_diff_pct > 0 else "delta-good"
ad_pace_icon = "🟠" if ad_pace_diff_pct > 0 else "🟢"
ad_pace_label = "ใช้เงินเกินเป้าเวลา" if ad_pace_diff_pct > 0 else "ใช้ต่ำกว่าเป้าเวลา"
ad_pace_html = f'<div class="kpi-delta {ad_pace_class}" style="margin-top: 4px; font-size: 13px;">{ad_pace_icon} {ad_pace_label} {abs(ad_pace_diff_pct):.1f}%</div>'

# --- เตรียม HTML สำหรับ KPI: ROAS ---
roas_class = "delta-good" if overall_roas >= 5 else ("delta-warn" if overall_roas >= 3 else "delta-bad")
roas_html = f'<div class="kpi-delta {roas_class}">Target: ≥ 5.0x</div>'

# --- เตรียม HTML สำหรับ KPI: Contribution Margin ---
cm_mom_html = f'<div class="kpi-delta {"delta-good" if mom_cm_pct >= 0 else "delta-bad"}">% MOM: {"+" if mom_cm_pct > 0 else ""}{mom_cm_pct:.1f}%</div>' if prev_cm != 0 else ''
cm_rate_class = "delta-good" if cm_pct >= 15 else ("delta-warn" if cm_pct >= 5 else "delta-bad")
cm_rate_html = f'<div class="kpi-delta {cm_rate_class}" style="margin-top: 4px; font-size: 13px;">อัตรากำไร (CM Rate): {cm_pct:.1f}%</div>'

# --- สร้าง Grid ของ KPI Cards ---
kpi_grid_html = f"""
<div class="kpi-grid">
    <div class="kpi-card">
        <div class="kpi-label">Total Revenue</div>
        <div class="kpi-value">{fmt_thb(total_revenue)}</div>
        {rev_mom_html}
        {rev_pace_html}
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Total Ad Spend</div>
        <div class="kpi-value">{fmt_thb(total_ad_spend)}</div>
        {ad_mom_html}
        {ad_pace_html}
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Overall ROAS</div>
        <div class="kpi-value">{overall_roas:.2f}x</div>
        {roas_html}
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Contribution Margin</div>
        <div class="kpi-value">{fmt_thb(total_cm)}</div>
        {cm_mom_html}
        {cm_rate_html}
    </div>
</div>
"""
st.markdown(kpi_grid_html, unsafe_allow_html=True)

# ── Copy Summary Button ──────────────────────────────────────────────────────
date_range_label = ""
if "date" in df.columns and df["date"].notna().any():
    d_min = df["date"].min().strftime("%d %b %Y")
    d_max = df["date"].max().strftime("%d %b %Y")
    date_range_label = f"{d_min} - {d_max}"

rev_target_pct = (total_revenue / sales_target * 100) if sales_target > 0 else 0
ad_budget_pct = (total_ad_spend / ad_budget * 100) if ad_budget > 0 else 0

mom_rev_str = f"{'+' if mom_rev_pct > 0 else ''}{mom_rev_pct:.1f}%" if prev_revenue > 0 else "N/A"
mom_ad_str = f"{'+' if mom_ad_pct > 0 else ''}{mom_ad_pct:.1f}%" if prev_ad_spend > 0 else "N/A"

summary_text = (
    f"📊 Performance Summary ({date_range_label})\n"
    f"Revenue: {fmt_thb(total_revenue)} ({rev_target_pct:.1f}% of target) | MOM: {mom_rev_str}\n"
    f"Ad Spend: {fmt_thb(total_ad_spend)} ({ad_budget_pct:.1f}% of budget) | ROAS: {overall_roas:.2f}x | MOM: {mom_ad_str}\n"
    f"Contribution Margin: {fmt_thb(total_cm)} (CM Rate: {cm_pct:.1f}%)"
)

st.code(summary_text, language=None)

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: MONTHLY TARGETS PACING (Visual Bars Only)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f'<div class="section-header">🎯 Monthly Targets Progress (วันที่ {days_elapsed}/{days_in_month})</div>', unsafe_allow_html=True)

render_progress_bar("💰 Sales vs. Target", total_revenue, sales_target, pacing_pct, "#10b981")
st.markdown("<br>", unsafe_allow_html=True)
render_progress_bar("📢 Ads vs. Budget", total_ad_spend, ad_budget, pacing_pct, "#FFC1BA")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 3: PLATFORM PROGRESS BARS (Responsive CSS Grid)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">🏆 Channel Performance (Share of Total)</div>', unsafe_allow_html=True)
st.markdown("**📊 Sales & Ads Progress per Channel** (เรียงตามยอดขาย)")

if "platform" in df.columns:
    plat_df = df.groupby("platform").agg(revenue=("revenue", "sum"), ad_spend=("ad_spend", "sum"), cm=("cm", "sum"), orders=("orders", "sum")).reset_index()
    plat_df["roas"] = plat_df["revenue"] / plat_df["ad_spend"].replace(0, float("nan"))
    plat_df["cm_pct"] = (plat_df["cm"] / plat_df["revenue"] * 100).round(1)
    
    plat_df = plat_df.sort_values("revenue", ascending=False)
    
    # ใช้ CSS Grid ในการจัดเรียงแทน st.columns เพื่อความ Responsive
    plat_cards_html = '<div class="plat-grid">'
    for _, row in plat_df.iterrows():
        plat_cards_html += generate_channel_progress_html(
            row['platform'], row['revenue'], total_revenue,
            row['ad_spend'], total_ad_spend, row['roas'], row['cm']
        )
    plat_cards_html += '</div>'
    
    st.markdown(plat_cards_html, unsafe_allow_html=True)
else:
    st.warning("Platform data unavailable.")

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 4: DAILY TREND
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">📈 Daily Trend: Revenue vs. Ad Spend</div>', unsafe_allow_html=True)

if "date" in df.columns and df["date"].notna().any():
    daily = df.groupby("date").agg(revenue=("revenue", "sum"), ad_spend=("ad_spend", "sum"), orders=("orders", "sum")).reset_index().sort_values("date")
    daily["roas"] = daily["revenue"] / daily["ad_spend"].replace(0, float("nan"))
    daily["date_str"] = daily["date"].dt.strftime("%b %d")

    fig_line = make_subplots(specs=[[{"secondary_y": True}]])
    fig_line.add_trace(go.Scatter(x=daily["date_str"], y=daily["revenue"], name="Revenue", mode="lines+markers", line=dict(color="#10b981", width=3)), secondary_y=False)
    fig_line.add_trace(go.Scatter(x=daily["date_str"], y=daily["ad_spend"], name="Ad Spend", mode="lines+markers", line=dict(color="#FFC1BA", width=3, dash="dot")), secondary_y=False)
    fig_line.add_trace(go.Scatter(x=daily["date_str"], y=daily["roas"], name="ROAS", mode="lines", line=dict(color="#a855f7", width=2, dash="dash")), secondary_y=True)

    fig_line.update_layout(
        height=380, paper_bgcolor="#1e293b", plot_bgcolor="#1e293b", font=dict(color="#cbd5e1"),
        legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)"), margin=dict(l=0, r=0, t=10, b=0), hovermode="x unified",
        xaxis=dict(showgrid=False, linecolor="#334155"), yaxis=dict(showgrid=True, gridcolor="#334155", tickprefix="฿")
    )
    fig_line.update_yaxes(title_text="ROAS (x)", secondary_y=True, showgrid=False, ticksuffix="x", tickfont=dict(color="#a855f7"))
    st.plotly_chart(fig_line, use_container_width=True, config={"displayModeBar": False})

# ══════════════════════════════════════════════════════════════════════════════
#  SECTION 5: DATA TABLE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-header">📋 Raw Platform Data</div>', unsafe_allow_html=True)

if "platform" in df.columns:
    display_df = plat_df.copy()
    display_df["Revenue"]    = display_df["revenue"].apply(fmt_thb)
    display_df["Ad Spend"]   = display_df["ad_spend"].apply(fmt_thb)
    display_df["ROAS"]       = display_df["roas"].apply(lambda r: f"{r:.2f}x" if pd.notna(r) else "—")
    display_df["Margin (฿)"] = display_df["cm"].apply(fmt_thb)
    display_df["CM %"]       = display_df["cm_pct"].apply(lambda p: f"{p:.1f}%")
    
    st.dataframe(
        display_df[["platform", "Revenue", "Ad Spend", "ROAS", "Margin (฿)", "CM %"]].rename(columns={"platform": "Platform"}),
        use_container_width=True, hide_index=True,
    )

st.divider()
st.caption("📊 Executive Performance Dashboard  |  Built with Streamlit")