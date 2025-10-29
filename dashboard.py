import os
import sys
import json
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# -------------------- 🧾 Setup --------------------
base_dir = Path("results")
base_dir.mkdir(exist_ok=True)

# Default diff files
diff_files = {
    "Headers": base_dir / "diff_headers.txt",
    "Body": base_dir / "diff_body.txt"
}

dashboard_html = base_dir / "diff_dashboard.html"
chart_file_headers = base_dir / "change_counts_headers.png"
chart_file_body = base_dir / "change_counts_body.png"

# -------------------- 🧠 Helper Functions --------------------
def parse_diff(input_file):
    """Parse DeepDiff JSON or Unified Text Diff into structured changes."""
    if not os.path.exists(input_file):
        print(f"⚠️ File not found: {input_file}")
        return pd.DataFrame()

    is_json = False
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            is_json = True
    except Exception:
        with open(input_file, "r", encoding="utf-8") as f:
            diff_lines = f.readlines()

    changes = []

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
    return pd.DataFrame(changes)


def generate_chart(df, title, output_path):
    """Generate a summary bar chart of changes."""
    if df.empty:
        return None
    counts = df["Type"].value_counts()
    fig = go.Figure(data=[go.Bar(
        x=counts.index,
        y=counts.values,
        marker_color=["#28a745" if "Add" in t else "#dc3545" for t in counts.index]
    )])
    fig.update_layout(title=title, xaxis_title="Type", yaxis_title="Count", template="plotly_white")
    fig.write_image(str(output_path))
    return output_path.name


# -------------------- ⚙️ Process Each Diff --------------------
sections_html = ""
for section_name, diff_path in diff_files.items():
    print(f"📂 Processing {section_name} diff: {diff_path}")

    df = parse_diff(diff_path)
    if df.empty:
        sections_html += f"<h2>{section_name} – No Differences Found ✅</h2>"
        continue

    # Generate chart
    chart_file = base_dir / f"change_counts_{section_name.lower()}.png"
    chart_name = generate_chart(df, f"{section_name} Change Summary", chart_file)

    # Build section HTML
    section_html = f"""
    <div id="tab-{section_name.lower()}" class="tabcontent">
      <h2>📄 {section_name} Differences</h2>
      <div style="text-align:center;">
        <img src="{chart_name}" alt="{section_name} Change Chart" width="400"/>
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
        section_html += f"<tr class='{cls}'><td>{row['Type']}</td><td>{row['Section']}</td><td><pre>{row['Line']}</pre></td></tr>\n"

    section_html += "</table></div>\n"
    sections_html += section_html

# -------------------- 🌐 Combine into One HTML --------------------
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
.tabs {{
  text-align: center;
  margin-bottom: 20px;
}}
.tab {{
  display: inline-block;
  margin: 0 10px;
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border-radius: 6px;
  cursor: pointer;
  font-weight: bold;
}}
.tab:hover {{
  background: #0056b3;
}}
.tabcontent {{
  display: none;
}}
.active {{
  display: block;
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
<div class="tabs">
  <div class="tab" onclick="openTab('headers')">Headers</div>
  <div class="tab" onclick="openTab('body')">Body</div>
</div>
{sections_html}
<script>
function openTab(name) {{
  document.querySelectorAll('.tabcontent').forEach(el => el.style.display = 'none');
  document.querySelectorAll('.tab').forEach(el => el.style.background = '#007bff');
  document.getElementById('tab-' + name).style.display = 'block';
  event.target.style.background = '#0056b3';
}}
document.addEventListener('DOMContentLoaded', () => {{
  openTab('headers');
}});
</script>
</body>
</html>
"""

with open(dashboard_html, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✅ Dashboard created: {dashboard_html}")
