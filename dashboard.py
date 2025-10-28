import os
import sys
import json
import plotly.graph_objects as go
from pathlib import Path
from collections import defaultdict

diff_file = sys.argv[1] if len(sys.argv) > 1 else "results/diff.txt"
output_dir = Path("results")
output_dir.mkdir(exist_ok=True)

dashboard_html = output_dir / "diff_dashboard.html"
dashboard_css = output_dir / "diff_dashboard.css"

if not os.path.exists(diff_file):
    print(f"Diff file not found: {diff_file}")
    sys.exit(1)

with open(diff_file, "r", encoding="utf-8") as f:
    diff_content = f.read()

# Check if it's JSON format (DeepDiff) or unified diff format
is_json_format = False
try:
    diff_data = json.loads(diff_content)
    is_json_format = True
except json.JSONDecodeError:
    pass

# Parse diff intelligently
field_changes = defaultdict(lambda: {"added": [], "removed": [], "section": ""})
current_section = ""

if is_json_format:
    # Handle DeepDiff JSON format
    for key, value in diff_data.items():
        if key == "dictionary_item_added":
            for field_path, val in value.items():
                # Extract field name from path like "root['a']['b']['c']"
                field_name = field_path.split("'")[-2] if "'" in field_path else field_path.split('"')[-2]
                field_changes[field_name]["added"].append(str(val))
                field_changes[field_name]["section"] = field_path
        elif key == "dictionary_item_removed":
            for field_path, val in value.items():
                field_name = field_path.split("'")[-2] if "'" in field_path else field_path.split('"')[-2]
                field_changes[field_name]["removed"].append(str(val))
                field_changes[field_name]["section"] = field_path
        elif key == "values_changed":
            for field_path, change_data in value.items():
                field_name = field_path.split("'")[-2] if "'" in field_path else field_path.split('"')[-2]
                if "old_value" in change_data:
                    field_changes[field_name]["removed"].append(str(change_data["old_value"]))
                if "new_value" in change_data:
                    field_changes[field_name]["added"].append(str(change_data["new_value"]))
                field_changes[field_name]["section"] = field_path
else:
    # Handle unified diff format
    diff_lines = diff_content.splitlines()
    for line in diff_lines:
        line = line.rstrip("\n")
        if line.startswith("@@"):
            current_section = line
        elif line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()
            if '":' in content:
                field_name = content.split('":')[0].strip('" ')
                field_value = content.split('":')[1].strip(' ",')
                field_changes[field_name]["added"].append(field_value)
                field_changes[field_name]["section"] = current_section
        elif line.startswith("-") and not line.startswith("---"):
            content = line[1:].strip()
            if '":' in content:
                field_name = content.split('":')[0].strip('" ')
                field_value = content.split('":')[1].strip(' ",')
                field_changes[field_name]["removed"].append(field_value)
                field_changes[field_name]["section"] = current_section

# Categorize changes
new_fields = []
modified_fields = []
removed_fields = []

for field, changes in field_changes.items():
    if changes["added"] and changes["removed"]:
        modified_fields.append({
            "Field": field,
            "Old Value": ", ".join(changes["removed"]),
            "New Value": ", ".join(changes["added"]),
            "Section": changes["section"]
        })
    elif changes["added"]:
        new_fields.append({
            "Field": field,
            "Value": ", ".join(changes["added"]),
            "Section": changes["section"]
        })
    elif changes["removed"]:
        removed_fields.append({
            "Field": field,
            "Value": ", ".join(changes["removed"]),
            "Section": changes["section"]
        })

# Create summary metrics
total_changes = len(new_fields) + len(modified_fields) + len(removed_fields)

if total_changes == 0:
    print("No differences found.")
    sys.exit(0)

# Summary donut chart
change_types = {
    "New Fields": len(new_fields),
    "Modified Fields": len(modified_fields),
    "Removed Fields": len(removed_fields)
}

fig = go.Figure(data=[go.Pie(
    labels=list(change_types.keys()),
    values=list(change_types.values()),
    marker=dict(colors=['#4CAF50', '#FF9800', '#F44336']),
    hole=0.6,
    textinfo='label+percent',
    textposition='outside'
)])
fig.update_layout(
    title="",
    template="plotly_white",
    height=300,
    showlegend=False,
    margin=dict(l=20, r=20, t=20, b=20)
)
chart_html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'displayModeBar': False})

# Read the second JSON payload (the one being compared)
json_file_2 = "results/payload_2.json"  # Adjust this path to your actual file
payload_2_content = ""

if os.path.exists(json_file_2):
    with open(json_file_2, "r", encoding="utf-8") as f:
        payload_2_raw = f.read()
        try:
            # Pretty print JSON
            payload_2_obj = json.loads(payload_2_raw)
            payload_2_content = json.dumps(payload_2_obj, indent=2)
        except:
            payload_2_content = payload_2_raw
else:
    payload_2_content = "# Payload file not found\n# Expected location: results/payload_2.json"

# Create CSS file
css_content = """* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: linear-gradient(180deg, #e9f0ff 0%, #eef3ff 40%, #f7f9ff 100%);
  padding: 24px;
  min-height: 100vh;
  color: #1a1a1a;
  display: flex;
  flex-direction: column;
}

.layout {
  display: grid;
  grid-template-columns: 260px 1fr;
  gap: 24px;
  flex: 1;
}

.sidebar {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 20px 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
  height: fit-content;
  position: sticky;
  top: 24px;
}

.brand {
  font-weight: 700;
  font-size: 1.1em;
  padding: 10px 16px 16px;
  color: #334155;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.nav-item {
  padding: 10px 14px;
  border-radius: 10px;
  color: #475569;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-item i {
  font-size: 1.1em;
  width: 20px;
  text-align: center;
}

.nav-item:hover {
  background: #f8f9fa;
}

.nav-item.active {
  background: #eef2ff;
  color: #3730a3;
  font-weight: 600;
}

.container {
  width: 100%;
  display: flex;
  flex-direction: column;
}

.header {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  padding: 24px 32px;
  border-radius: 16px;
  margin-bottom: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header h1 {
  font-size: 2em;
  color: #1a1a1a;
  font-weight: 700;
  margin-bottom: 4px;
}

.header-subtitle {
  color: #666;
  font-size: 0.95em;
}

.timestamp {
  text-align: right;
  color: #888;
  font-size: 0.9em;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}

.stat-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  padding: 24px;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  transition: transform 0.2s, box-shadow 0.2s;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
}

.stat-label {
  font-size: 0.85em;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
  margin-bottom: 12px;
}

.stat-value {
  font-size: 2.5em;
  font-weight: 700;
  line-height: 1;
}

.stat-card.total .stat-value { color: #4f46e5; }
.stat-card.new .stat-value { color: #4CAF50; }
.stat-card.modified .stat-value { color: #FF9800; }
.stat-card.removed .stat-value { color: #F44336; }

.content-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  margin-bottom: 24px;
}

.card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 2px solid #f0f0f0;
}

.card-title {
  font-size: 1.3em;
  font-weight: 700;
  color: #1a1a1a;
}

.badge {
  display: inline-block;
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 0.85em;
  font-weight: 600;
}

.badge-new { 
  background: #E8F5E9; 
  color: #2E7D32; 
}

.badge-modified { 
  background: #FFF3E0; 
  color: #E65100; 
}

.badge-removed { 
  background: #FFEBEE; 
  color: #C62828; 
}

.full-width {
  grid-column: 1 / -1;
}

.footer {
  margin-top: auto;
  padding: 20px;
  text-align: center;
  color: #888;
  font-size: 0.9em;
  border-top: 1px solid #e0e0e0;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
}
"""

# Add this to the CSS content (continuation)
css_content += """
table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 0.9em;
}

thead {
  background: #f8f9fa;
}

th {
  padding: 14px 16px;
  text-align: left;
  font-weight: 600;
  color: #555;
  text-transform: uppercase;
  font-size: 0.8em;
  letter-spacing: 0.5px;
  border-bottom: 2px solid #e0e0e0;
}

th:first-child {
  border-radius: 8px 0 0 0;
}

th:last-child {
  border-radius: 0 8px 0 0;
}

td {
  padding: 14px 16px;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: top;
}

tr:last-child td {
  border-bottom: none;
}

tr:hover {
  background: #f8f9fa;
}

.field-name {
  font-weight: 600;
  color: #333;
}

.value {
  font-family: 'Courier New', monospace;
  background: #f5f5f5;
  padding: 6px 10px;
  border-radius: 6px;
  display: inline-block;
  font-size: 0.9em;
  word-break: break-word;
}

.old-value {
  background: #FFEBEE;
  color: #C62828;
  text-decoration: line-through;
}

.new-value {
  background: #E8F5E9;
  color: #2E7D32;
}

.section-tag {
  font-size: 0.75em;
  color: #999;
  font-family: monospace;
}

.chart-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
}

.empty-state-icon { display: none; }

/* Section visibility for tabbed layout */
.section {
  display: none;
}

.section.active {
  display: block;
}

/* Responsive Design */
@media (max-width: 1024px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { order: 1; }
  .content-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .header h1 {
    font-size: 1.5em;
  }
  
  .dashboard-grid {
    grid-template-columns: 1fr 1fr;
  }
  
  .stat-value {
    font-size: 2em;
  }
  
  table {
    font-size: 0.85em;
  }
  
  th, td {
    padding: 10px 12px;
  }
}

@media (max-width: 480px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
  }
  
  .header-content {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .timestamp {
    text-align: left;
    margin-top: 8px;
  }
}


"""

# Write the complete CSS to file
with open(dashboard_css, "w", encoding="utf-8") as f:
    f.write(css_content)

# Generate HTML
from datetime import datetime

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Diff Analysis Dashboard</title>
    <link rel="stylesheet" href="diff_dashboard.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
 </head>
 <body>
    <div class="layout">
        <aside class="sidebar">
            <div class="brand">Diff Explorer</div>
            <nav class="nav">
                <a class="nav-item active" href="#">
                    <i class="fa-solid fa-table-columns"></i>
                    <span>Dashboard</span>
                </a>
                <a class="nav-item" href="#new">
                    <i class="fa-solid fa-plus"></i>
                    <span>New</span>
                </a>
                <a class="nav-item" href="#modified">
                    <i class="fa-solid fa-pen-to-square"></i>
                    <span>Modified</span>
                </a>
                <a class="nav-item" href="#removed">
                    <i class="fa-solid fa-eraser"></i>
                    <span>Removed</span>
                </a>
                <a class="nav-item" href="#payload">
                    <i class="fa-solid fa-file-code"></i>
                    <span>View Payload</span>
                </a>
            </nav>
        </aside>
        <main class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-content">
                <div>
                    <h1>Diff Analysis Dashboard</h1>
                    <p class="header-subtitle">Comprehensive comparison of configuration changes</p>
                </div>
                <div class="timestamp">
                    Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                </div>
            </div>
        </div>

        <!-- Statistics Cards (Dashboard Section) -->
        <section id="dashboard" class="section active">
        <div class="dashboard-grid">
            <div class="stat-card total">
                <div class="stat-label">Total Changes</div>
                <div class="stat-value">{total_changes}</div>
            </div>
            <div class="stat-card new">
                <div class="stat-label">New Fields</div>
                <div class="stat-value">{len(new_fields)}</div>
            </div>
            <div class="stat-card modified">
                <div class="stat-label">Modified Fields</div>
                <div class="stat-value">{len(modified_fields)}</div>
            </div>
            <div class="stat-card removed">
                <div class="stat-label">Removed Fields</div>
                <div class="stat-value">{len(removed_fields)}</div>
            </div>
        </div>

        <!-- Content Grid -->
        <div class="content-grid">
            <!-- Summary Chart -->
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">Change Distribution</h2>
                </div>
                <div class="chart-container">
                    {chart_html}
                </div>
            </div>

            <!-- Quick Stats -->
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">Quick Insights</h2>
                </div>
                <div style="padding: 20px 0;">
                    <div style="margin-bottom: 20px;">
                        <div style="font-size: 0.85em; color: #888; margin-bottom: 8px;">CHANGE RATE</div>
                        <div style="font-size: 1.5em; font-weight: 700; color: #FF9800;">
                            {round(len(modified_fields) / total_changes * 100) if total_changes > 0 else 0}% Modified
                        </div>
                    </div>
                    <div style="margin-bottom: 20px;">
                        <div style="font-size: 0.85em; color: #888; margin-bottom: 8px;">DATA QUALITY</div>
                        <div style="font-size: 1.5em; font-weight: 700; color: #4CAF50;">
                            {round((len(new_fields) + len(modified_fields)) / total_changes * 100) if total_changes > 0 else 0}% Additions
                        </div>
                    </div>
                    <div>
                        <div style="font-size: 0.85em; color: #888; margin-bottom: 8px;">REMOVED FIELDS</div>
                        <div style="font-size: 1.5em; font-weight: 700; color: #F44336;">
                            {len(removed_fields)}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        </section>

        <!-- New Fields -->
        <section id="new" class="section">
        <div class="card full-width">
            <div class="card-header">
                <h2 class="card-title">New Fields</h2>
                <span class="badge badge-new">{len(new_fields)} items</span>
            </div>
"""

if new_fields:
    html_content += """
            <table>
                <thead>
                    <tr>
                        <th style="width: 30%;">Field Path</th>
                        <th style="width: 15%;">Section</th>
                        <th style="width: 55%;">New Value</th>
                    </tr>
                </thead>
                <tbody>
"""
    for item in new_fields:
        field_path = item.get("Field", "")
        section = item.get("Section", "root") or "root"
        value = str(item.get("Value", "N/A"))
        display_value = (value[:100] + '...') if len(value) > 100 else value
        html_content += f"""
                    <tr>
                        <td class=\"field-name\">{field_path}</td>
                        <td><span class=\"section-tag\">{section}</span></td>
                        <td><span class=\"value new-value\">{display_value}</span></td>
                    </tr>
"""
    html_content += """
                </tbody>
            </table>
"""
else:
    html_content += """
            <div class="empty-state">
                <p>No new fields detected</p>
            </div>
"""

html_content += f"""
        </div>
        </section>

        <!-- Modified Fields -->
        <section id="modified" class="section">
        <div class="card full-width">
            <div class="card-header">
                <h2 class="card-title">Modified Fields</h2>
                <span class="badge badge-modified">{len(modified_fields)} items</span>
            </div>
"""

if modified_fields:
    html_content += """
            <table>
                <thead>
                    <tr>
                        <th style="width: 25%;">Field Path</th>
                        <th style="width: 12%;">Section</th>
                        <th style="width: 31%;">Old Value</th>
                        <th style="width: 31%;">New Value</th>
                    </tr>
                </thead>
                <tbody>
"""
    for item in modified_fields:
        field_path = item.get("Field", "")
        section = item.get("Section", "root") or "root"
        old_val = str(item.get("Old Value", "N/A"))
        new_val = str(item.get("New Value", "N/A"))
        old_display = (old_val[:80] + '...') if len(old_val) > 80 else old_val
        new_display = (new_val[:80] + '...') if len(new_val) > 80 else new_val
        html_content += f"""
                    <tr>
                        <td class=\"field-name\">{field_path}</td>
                        <td><span class=\"section-tag\">{section}</span></td>
                        <td><span class=\"value old-value\">{old_display}</span></td>
                        <td><span class=\"value new-value\">{new_display}</span></td>
                    </tr>
"""
    html_content += """
                </tbody>
            </table>
"""
else:
    html_content += """
            <div class="empty-state">
                <p>No modified fields detected</p>
            </div>
"""

html_content += f"""
        </div>
        </section>

        <!-- Removed Fields -->
        <section id="removed" class="section">
        <div class="card full-width">
            <div class="card-header">
                <h2 class="card-title">Removed Fields</h2>
                <span class="badge badge-removed">{len(removed_fields)} items</span>
            </div>
            
"""

if removed_fields:
    html_content += """
            <table>
                <thead>
                    <tr>
                        <th style="width: 30%;">Field Path</th>
                        <th style="width: 15%;">Section</th>
                        <th style="width: 55%;">Old Value</th>
                    </tr>
                </thead>
                <tbody>
"""
    for item in removed_fields:
        field_path = item.get("Field", "")
        section = item.get("Section", "root") or "root"
        value = str(item.get("Value", "N/A"))
        display_value = (value[:100] + '...') if len(value) > 100 else value
        html_content += f"""
                    <tr>
                        <td class=\"field-name\">{field_path}</td>
                        <td><span class=\"section-tag\">{section}</span></td>
                        <td><span class=\"value old-value\">{display_value}</span></td>
                    </tr>
"""
    html_content += """
                </tbody>
            </table>
"""
else:
    html_content += """
            <div class="empty-state">
                <p>No removed fields detected</p>
            </div>
"""

html_content += """
        </div>
        </section>

        <!-- View Payload Section -->
        <section id="payload" class="section">
            <div class="card full-width">
                <div class="card-header">
                    <h2 class="card-title">Second Payload (New Version)</h2>
                    <span class="badge badge-modified">JSON</span>
                </div>
                <div style="position: relative;">
                    <button id="copyBtn" style="position: absolute; top: 10px; right: 10px; padding: 8px 16px; background: #4f46e5; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 0.85em; font-weight: 600; transition: all 0.2s; z-index: 10;">
                        <i class="fa-solid fa-copy"></i> Copy
                    </button>
                    <pre style="background: #1e1e1e; color: #d4d4d4; padding: 24px; border-radius: 12px; overflow-x: auto; max-height: 600px; font-family: 'Courier New', monospace; font-size: 0.9em; line-height: 1.6; margin: 0;"><code id="payloadCode">{payload_2_content}</code></pre>
                </div>
            </div>
        </section>

        <!-- Footer -->
"""
html_content += f"""
        <footer class="footer">
            <p>Generated by Diff Analysis Tool | Data processed: {total_changes} changes across {len(change_types)} categories</p>
        </footer>
"""
html_content += """
        </main>
    </div>
    <script>
      (function() {{
        const navItems = document.querySelectorAll('.nav .nav-item');
        const sections = document.querySelectorAll('.section');
        
        // Function to show only the selected section
        function showSection(targetId) {{
          // Hide all sections
          sections.forEach(section => {{
            section.classList.remove('active');
          }});
          
          // Show only the target section
          const targetSection = document.getElementById(targetId);
          if (targetSection) {{
            targetSection.classList.add('active');
          }}
          
          // Update active nav item
          navItems.forEach(nav => {{
            nav.classList.remove('active');
            const href = nav.getAttribute('href');
            if ((targetId === 'dashboard' && href === '#') || 
                (href === '#' + targetId)) {{
              nav.classList.add('active');
            }}
          }});
        }}
        
        // Add click handlers to navigation items
        navItems.forEach(navItem => {{
          navItem.addEventListener('click', function(e) {{
            e.preventDefault();
            const href = this.getAttribute('href');
            
            // Determine which section to show
            let sectionId = 'dashboard';
            if (href && href !== '#') {{
              sectionId = href.substring(1); // Remove the '#'
            }}
            
            showSection(sectionId);
            
            // Update URL hash
            history.replaceState(null, '', href || '#dashboard');
          }});
        }});
        
        // Handle initial page load with hash
        const initialHash = window.location.hash;
        if (initialHash && initialHash.length > 1) {{
          const initialSection = initialHash.substring(1);
          showSection(initialSection);
        }} else {{
          // Show dashboard by default
          showSection('dashboard');
        }}

        // Copy button functionality for payload section
        const copyBtn = document.getElementById('copyBtn');
        if (copyBtn) {{
          copyBtn.addEventListener('click', function() {{
            const code = document.getElementById('payloadCode').textContent;
            navigator.clipboard.writeText(code).then(() => {{
              const btn = this;
              const originalText = btn.innerHTML;
              btn.innerHTML = '<i class="fa-solid fa-check"></i> Copied!';
              btn.style.background = '#10b981';
              setTimeout(() => {{
                btn.innerHTML = originalText;
                btn.style.background = '#4f46e5';
              }}, 2000);
            }}).catch(err => {{
              console.error('Failed to copy:', err);
              alert('Failed to copy to clipboard');
            }});
          }});
        }}
      }})();
    </script>
 </body>
</html>
"""

# Save HTML file into results directory
with open(dashboard_html, 'w', encoding='utf-8') as f:
    f.write(html_content)

print("Dashboard generated successfully.")
print("Files created:")
print(f"   - {dashboard_html}")
print(f"   - {dashboard_css}")
print("\nOpen 'results/diff_dashboard.html' in your browser to view the dashboard")

