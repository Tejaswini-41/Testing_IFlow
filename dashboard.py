import os
import sys
import json
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# -------------------- 🧾 Setup --------------------
output_dir = Path("results")
output_dir.mkdir(exist_ok=True)

dashboard_html = output_dir / "diff_dashboard.html"

# Input files (headers + body)
diff_body_file = output_dir / "diff.txt"
diff_headers_file = output_dir / "diff_headers.txt"

# -------------------- 📥 Utility to Parse a Diff File --------------------
def parse_diff_file(file_path):
    if not file_path.exists():
        print(f"⚠ Skipping missing diff file: {file_path}")
        return pd.DataFrame(columns=["Type", "Section", "Line"])

    is_json = False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            is_json = True
    except Exception:
        with open(file_path, "r", encoding="utf-8") as f:
            diff_lines = f.readlines()

    changes = []

    if is_json:
        # DeepDiff JSON format
        for key, diff_list in data.items():
            for change in diff_list:
                if isinstance(change, str):
                    changes.append({
                        "Type": key.replace("_", " ").title(),
                        "Section": change,
                        "Line": ""
                    })
                elif isinstance(change, dict):
                    path = change.get("path", "")
                    old = change.get("old_value", "")
                    new = change.get("new_value", "")
                    changes.append({
                        "Type": key.replace("_", " ").title(),
                        "Section": path,
                        "Line": f"{old} → {new}"
                    })
    else:
        # Unified diff text format
        section = ""
        for line in diff_lines:
            line = line.rstrip("\n")
            if line.startswith("@@"):
                section = line
            elif line.startswith("+") and not line.startswith("+++"):
                changes.append({"Type": "Addition", "Section": section, "Line": line[1:].strip()})
            elif line.startswith("-") and not line.startswith("---"):
                changes.append({"Type": "Deletion", "Section": section, "Line": line[1:].strip()})

    return pd.DataFrame(changes)

# -------------------- 🧩 Parse Both Diffs --------------------
df_body = parse_diff_file(diff_body_file)
df_headers = parse_diff_file(diff_headers_file)

if df_body.empty and df_headers.empty:
    print("✅ No differences found in both headers and body.")
    sys.exit(0)

# -------------------- 📊 Chart Function --------------------
def create_chart(df, title, chart_name):
    counts = df["Type"].value_counts()
    fig = go.Figure(data=[go.Bar(
        x=counts.index,
        y=counts.values,
        marker_color=["#28a745" if "Add" in t else "#dc3545" for t in counts.index]
    )])
    fig.update_layout(title=title, xaxis_title="Type", yaxis_title="Count", template="plotly_white")
    chart_path = output_dir / chart_name
    fig.write_image(str(chart_path))
    return chart_path.name

# -------------------- 🌈 Generate Charts --------------------
header_chart = create_chart(df_headers, "Header Change Summary", "header_chart.png") if not df_headers.empty else None
body_chart = create_chart(df_body, "Body Change Summary", "body_chart.png") if not df_body.empty else None

# -------------------- 🌐 Build HTML --------------------
html = """
<html>
<head>
<title>CPI Response Diff Dashboard</title>
<style>
body {
  font-family: Arial, sans-serif;
  background: #fafafa;
  margin: 40px;
}
h1, h2 {
  text-align: center;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 20px;
  font-size: 14px;
}
th, td {
  padding: 8px 10px;
  border: 1px solid #ccc;
}
tr.addition td {
  background-color: #e8f8e8;
  color: #0a7a0a;
}
tr.deletion td {
  background-color: #fde8e8;
  color: #b00000;
}
tr.value td {
  background-color: #fff7e6;
  color: #b36b00;
}
pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}
.chart {
  text-align: center;
  margin-top: 20px;
}
</style>
</head>
<body>
<h1>📊 CPI Response Comparison Dashboard</h1>
"""

# -------------------- 🧱 Headers Section --------------------
if not df_headers.empty:
    html += "<h2>🧩 Header Differences</h2>"
    if header_chart:
        html += f"<div class='chart'><img src='{header_chart}' width='400'/></div>"
    html += "<table><tr><th>Type</th><th>Section</th><th>Details</th></tr>"
    for _, row in df_headers.iterrows():
        t = row["Type"].lower()
        cls = "addition" if "add" in t else "deletion" if "delete" in t else "value"
        html += f"<tr class='{cls}'><td>{row['Type']}</td><td>{row['Section']}</td><td><pre>{row['Line']}</pre></td></tr>\n"
    html += "</table>"

# -------------------- 🧱 Body Section --------------------
if not df_body.empty:
    html += "<h2>💾 Body Differences</h2>"
    if body_chart:
        html += f"<div class='chart'><img src='{body_chart}' width='400'/></div>"
    html += "<table><tr><th>Type</th><th>Section</th><th>Details</th></tr>"
    for _, row in df_body.iterrows():
        t = row["Type"].lower()
        cls = "addition" if "add" in t else "deletion" if "delete" in t else "value"
        html += f"<tr class='{cls}'><td>{row['Type']}</td><td>{row['Section']}</td><td><pre>{row['Line']}</pre></td></tr>\n"
    html += "</table>"

html += """
</body>
</html>
"""

# -------------------- 💾 Write Dashboard --------------------
with open(dashboard_html, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ Dashboard created: {dashboard_html}")