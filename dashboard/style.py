"""Dark, modern, mobile-friendly CSS for the Streamlit dashboard."""

CSS = """
<style>
/* ---- base dark polish ---- */
.stApp { background: #0b0f17; }
h1, h2, h3 { letter-spacing: -0.02em; }
[data-testid="stSidebar"] { background: #0e1420; }
div[data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }

/* ---- conviction badges ---- */
.badge {
  display: inline-block; padding: 3px 12px; border-radius: 999px;
  font-size: 0.78rem; font-weight: 700; letter-spacing: .04em;
}
.badge-high-long  { background:#0d3321; color:#4ade80; border:1px solid #16a34a; }
.badge-high-short { background:#3b0d13; color:#f87171; border:1px solid #dc2626; }
.badge-medium     { background:#332a0d; color:#facc15; border:1px solid #ca8a04; }
.badge-low        { background:#1a2233; color:#94a3b8; border:1px solid #334155; }
.badge-none       { background:#131a26; color:#64748b; border:1px solid #1e293b; }

/* ---- buttons (watchlist) ---- */
.stButton > button {
  background:#111827 !important; color:#e5e7eb !important;
  border:1px solid #1f2937 !important; border-radius:10px !important;
  font-weight:600 !important;
}
.stButton > button:hover { border-color:#3b82f6 !important; color:#93c5fd !important; }
header[data-testid="stHeader"] { background:#0b0f17 !important; }

/* ---- watchlist rows ---- */
.wl-row {
  display:flex; justify-content:space-between; align-items:center;
  padding:10px 14px; margin:6px 0; border-radius:12px;
  background:#111827; border:1px solid #1f2937;
}
.wl-row:hover { border-color:#3b82f6; }
.wl-sym { font-weight:700; font-size:1.0rem; color:#e5e7eb; }
.wl-px  { font-variant-numeric: tabular-nums; color:#cbd5e1; }

/* ---- guidance card ---- */
.guide-card {
  background:linear-gradient(160deg,#101827,#0d1420); border:1px solid #1f2937;
  border-radius:16px; padding:18px 20px; margin:8px 0;
}
.guide-headline { font-size:1.15rem; font-weight:800; color:#f1f5f9; margin-bottom:8px; }
.guide-action { color:#cbd5e1; line-height:1.55; }
.guide-caveat {
  background:#2a1a0d; border-left:3px solid #f59e0b; color:#fcd34d;
  padding:8px 12px; border-radius:8px; margin-top:8px; font-size:0.88rem;
}
.reason-line { color:#94a3b8; font-size:0.9rem; padding:2px 0; }

/* ---- market context chips ---- */
.ctx-chip {
  display:inline-block; padding:6px 14px; border-radius:10px; margin-right:8px;
  background:#111827; border:1px solid #1f2937; font-size:0.9rem; color:#e2e8f0;
}
.trend-up   { color:#4ade80; font-weight:700; }
.trend-down { color:#f87171; font-weight:700; }
.trend-flat { color:#94a3b8; font-weight:700; }

/* ---- disclaimer footer ---- */
.disclaimer {
  color:#64748b; font-size:0.78rem; border-top:1px solid #1e293b;
  padding-top:10px; margin-top:24px; line-height:1.5;
}

/* ---- mobile ---- */
@media (max-width: 640px) {
  .guide-card { padding:14px; }
  .wl-row { padding:8px 10px; }
  .block-container { padding-left:0.8rem !important; padding-right:0.8rem !important; }
}
</style>
"""

def badge(conviction: str, direction: int) -> str:
    if conviction == "HIGH":
        cls = "badge-high-long" if direction > 0 else "badge-high-short"
        arrow = "▲ LONG" if direction > 0 else "▼ SHORT"
        return f'<span class="badge {cls}">HIGH · {arrow}</span>'
    if conviction == "MEDIUM":
        arrow = "▲" if direction > 0 else "▼" if direction < 0 else ""
        return f'<span class="badge badge-medium">MEDIUM {arrow}</span>'
    if conviction == "LOW":
        return '<span class="badge badge-low">LOW</span>'
    return '<span class="badge badge-none">NO SETUP</span>'
