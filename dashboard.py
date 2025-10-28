import os
import sys
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
 
diff_file = sys.argv[1] if len(sys.argv) > 1 else "results/diff.txt"
output_dir = Path("results")
output_dir.mkdir(exist_ok=True)
 
dashboard_html = output_dir / "diff_dashboard.html"
 
if not os.path.exists(diff_file):
    print(f"❌ Diff file not found: {diff_file}")
    sys.exit(1)
 
with open(diff_file, "r", encoding="utf-8") as f:
    diff_lines = f.readlines()
 
changes = []
section = ""
for line in diff_lines:
    line = line.rstrip("\n")
    if line.startswith("@@"):
        section = line
    elif line.startswith("+") and not line.startswith("+++"):
        changes.append({"Type": "Addition", "Section": section, "Line": line[1:].strip()})
    elif line.startswith("-") and not line.startswith("---"):
        changes.append({"Type": "Deletion", "Section": section, "Line": line[1:].strip()})
 
df = pd.DataFrame(changes)
 
if df.empty:
    print("✅ No differences found.")
    sys.exit(0)
 
# Summary bar chart
counts = df["Type"].value_counts()
fig = go.Figure(data=[go.Bar(
    x=counts.index,
    y=counts.values,
    marker_color=["#28a745" if t == "Addition" else "#dc3545" for t in counts.index]
)])
fig.update_layout(title="Change Summary", xaxis_title="Type", yaxis_title="Count", template="plotly_white")
chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
 
# Build HTML
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
{chart_html}
</div>
<table>
<tr><th>Type</th><th>Section</th><th>Line</th></tr>
"""
 
for _, row in df.iterrows():
    row_class = "addition" if row["Type"] == "Addition" else "deletion"
    html += f"<tr class='{row_class}'><td>{row['Type']}</td><td>{row['Section']}</td><td><pre>{row['Line']}</pre></td></tr>\n"
 
html += """
</table>
</body>
</html>
"""
 
with open(dashboard_html, "w", encoding="utf-8") as f:
    f.write(html)
 
print(f"✅ Dashboard created: {dashboard_html}")
