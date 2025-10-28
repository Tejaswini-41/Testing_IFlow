import os
import sys
import json
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# -------------------- 🧾 Setup --------------------
input_file = sys.argv[1] if len(sys.argv) > 1 else "results/diff.txt"
output_dir = Path("results")
output_dir.mkdir(exist_ok=True)

dashboard_html = output_dir / "diff_dashboard.html"
chart_file = output_dir / "change_counts.png"

if not os.path.exists(input_file):
    print(f"❌ Diff file not found: {input_file}")
    sys.exit(1)

# -------------------- 🧠 Try to Detect JSON vs Text --------------------
is_json = False
try:
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        is_json = True
except Exception:
    with open(input_file, "r", encoding="utf-8") as f:
        diff_lines = f.readlines()

changes = []

# -------------------- 📊 Parse DeepDiff JSON --------------------
if is_json:
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

# -------------------- 📄 Parse Unified Diff Text --------------------
else:
    section = ""
    for line in diff_lines:
        line = line.rstrip("\n")
        if line.startswith("@@"):
            section = line
        elif line.startswith("+") and not line.startswith("+++"):
            changes.append({"Type": "Addition", "Section": section, "Line": line[1:].strip()})
        elif line.startswith("-") and not line.startswith("---"):
            changes.append({"Type": "Deletion", "Section": section, "Line": line[1:].strip()})

# -------------------- ✅ Create DataFrame --------------------
df = pd.DataFrame(changes)
if df.empty:
    print("✅ No differences found.")
    sys.exit(0)

# -------------------- 📈 Summary Chart --------------------
counts = df["Type"].value_counts()
fig = go.Figure(data=[go.Bar(
    x=counts.index,
    y=counts.values,
    marker_color=["#28a745" if "Add" in t else "#dc3545" for t in counts.index]
)])
fig.update_layout(title="Change Summary", xaxis_title="Type", yaxis_title="Count", template="plotly_white")
fig.write_image(str(chart_file))

# -------------------- 🌐 Build HTML --------------------
html = f"""
<html>
<head>
<title>CPI Response Diff Dashboard</title>
<style>
body {{
  font-family: Arial, sans-serif;
  background: #fafafa;
  margin: 40px;
}}
h1 {{
  text-align: center;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  margin-top: 20px;
  font-size: 14px;
}}
th, td {{
  padding: 8px 10px;
  border: 1px solid #ccc;
}}
tr.addition td {{
  background-color: #e8f8e8;
  color: #0a7a0a;
}}
tr.deletion td {{
  background-color: #fde8e8;
  color: #b00000;
}}
tr.value td {{
  background-color: #fff7e6;
  color: #b36b00;
}}
pre {{
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}}
</style>
</head>
<body>
<h1>📊 CPI Response Diff Dashboard</h1>
<div style="text-align:center;">
<img src="{chart_file.name}" alt="Change Chart" width="400"/>
</div>
<table>
<tr><th>Type</th><th>Section</th><th>Details</th></tr>
"""

for _, row in df.iterrows():
    t = row["Type"].lower()
    if "add" in t:
        cls = "addition"
    elif "delete" in t or "remove" in t:
        cls = "deletion"
    else:
        cls = "value"
    html += f"<tr class='{cls}'><td>{row['Type']}</td><td>{row['Section']}</td><td><pre>{row['Line']}</pre></td></tr>\n"

html += """
</table>
</body>
</html>
"""

with open(dashboard_html, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ Dashboard created: {dashboard_html}")
