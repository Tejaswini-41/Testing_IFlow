import os
import sys
import json
import html
import re
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

# Load payload files
base_payload_file = "results/response_base.txt"
current_payload_file = "results/response_current.txt"

base_payload = ""
current_payload = ""

try:
    with open(base_payload_file, "r", encoding="utf-8") as f:
        base_payload_raw = f.read()
        try:
            # Try to pretty print JSON
            base_payload_obj = json.loads(base_payload_raw)
            base_payload = json.dumps(base_payload_obj, indent=2)
        except json.JSONDecodeError:
            base_payload = base_payload_raw
except FileNotFoundError:
    base_payload = "# Base payload file not found\n# Expected location: results/response_base.txt"

try:
    with open(current_payload_file, "r", encoding="utf-8") as f:
        current_payload_raw = f.read()
        try:
            # Try to pretty print JSON
            current_payload_obj = json.loads(current_payload_raw)
            current_payload = json.dumps(current_payload_obj, indent=2)
        except json.JSONDecodeError:
            current_payload = current_payload_raw
except FileNotFoundError:
    current_payload = "# Current payload file not found\n# Expected location: results/response_current.txt"

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
    # Helper function to format field path for better readability
    def format_field_path(path):
        """Convert deepdiff path like root['a']['b']['c'] to 'a > b > c' (no leaf)."""
        if not path:
            return "root"
        if path.startswith("root"):
            path = path[4:]  # Remove "root"
        # Extract all keys in path
        parts = []
        for part in path.split("'")[1::2]:  # Get every other element (the keys)
            if part.strip():
                parts.append(part)
        return " > ".join(parts[:-1]) if len(parts) > 1 else parts[0] if parts else "root"
    
    def render_breadcrumb(section_path: str, field_name: str) -> str:
        """Return HTML breadcrumb spans for section + field leaf using › separators."""
        try:
            parts = [p.strip() for p in section_path.split('>')] if section_path else []
            parts = [p for p in (part.replace('\u200b', '') for part in parts) if p]
        except Exception:
            parts = [section_path] if section_path else []

        # Escape each part safely
        safe_parts = [html.escape(p, quote=True) for p in parts]
        safe_leaf = html.escape(field_name or "", quote=True)

        # Build HTML: part › part › leaf (with classes)
        crumb_html_parts = []
        for idx, part in enumerate(safe_parts):
            crumb_html_parts.append(f'<span class="crumb">{part}</span>')
            crumb_html_parts.append('<span class="crumb-sep">›</span>')
        crumb_html_parts.append(f'<span class="crumb-leaf">{safe_leaf}</span>')
        return "".join(crumb_html_parts)

    def extract_field_name(field_path: str) -> str:
        """Extract the last key from a DeepDiff path, fallback to full path."""
        try:
            parts = [p for p in field_path.split("'")[1::2] if p.strip()]
            if not parts:
                parts = [p for p in field_path.split('"')[1::2] if p.strip()]
            return parts[-1] if parts else field_path
        except Exception:
            return field_path

    def iter_path_items(value):
        """Yield (field_path, val_or_None) from DeepDiff values which may be dict or iterable of paths."""
        if isinstance(value, dict):
            for k, v in value.items():
                yield k, v
        else:
            try:
                for k in value:
                    yield k, None
            except TypeError:
                return

    def format_field_path_slash(path):
        """Convert DeepDiff path like root['a']['b']['c'] to 'a/b/c' including leaf."""
        if not path:
            return "root"
        if path.startswith("root"):
            path = path[4:]  # strip leading "root"
        # Try single-quote style first
        parts = [p for p in path.split("'")[1::2] if p.strip()]
        if not parts:
            # Fallback to double-quote style
            parts = [p for p in path.split('"')[1::2] if p.strip()]
        return "/".join(parts) if parts else "root"

    # Handle DeepDiff JSON format
    for key, value in diff_data.items():
        if key == "dictionary_item_added":
            for field_path, val in iter_path_items(value):
                field_name = extract_field_name(field_path)
                if val is not None:
                    field_changes[field_name]["added"].append(str(val))
                else:
                    field_changes[field_name]["added"].append("<added>")
                # store slash-separated full path including leaf
                field_changes[field_name]["section"] = format_field_path_slash(field_path)
        elif key == "dictionary_item_removed":
            for field_path, val in iter_path_items(value):
                field_name = extract_field_name(field_path)
                if val is not None:
                    field_changes[field_name]["removed"].append(str(val))
                else:
                    field_changes[field_name]["removed"].append("<removed>")
                field_changes[field_name]["section"] = format_field_path_slash(field_path)
        elif key == "values_changed":
            for field_path, change_data in value.items():
                field_name = extract_field_name(field_path)
                if "old_value" in change_data:
                    field_changes[field_name]["removed"].append(str(change_data["old_value"]))
                if "new_value" in change_data:
                    field_changes[field_name]["added"].append(str(change_data["new_value"]))
                field_changes[field_name]["section"] = format_field_path_slash(field_path)
else:
    # Handle unified diff format
    diff_lines = diff_content.splitlines()
    for line in diff_lines:
        line = line.rstrip("\n")
        if line.startswith("@@"):
            current_section = line
        elif line.startswith("+") and not line.startswith("+++"):
            content = line[1:].strip()
            # Try robust extraction of key and value (handles nested colons)
            m = re.match(r'"([^"]+)"\s*:\s*(.*)', content)
            if m:
                field_name = m.group(1)
                field_value = m.group(2).rstrip(',').strip()
                field_changes[field_name]["added"].append(field_value)
                field_changes[field_name]["section"] = current_section
        elif line.startswith("-") and not line.startswith("---"):
            content = line[1:].strip()
            m = re.match(r'"([^"]+)"\s*:\s*(.*)', content)
            if m:
                field_name = m.group(1)
                field_value = m.group(2).rstrip(',').strip()
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
    textposition='outside',
    hovertemplate='<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>'
)])

fig.update_layout(
    title="",
    template="plotly_white",
    height=300,
    showlegend=False,
    margin=dict(l=20, r=20, t=20, b=20)
)

# Generate chart with unique div ID for click handling
chart_html = fig.to_html(
    full_html=False, 
    include_plotlyjs='cdn', 
    config={'displayModeBar': False},
    div_id='pieChart'
)


# Create CSS file
css_content = """:root {
  /* Gradient Color Variables */
  --primary: #667eea;
  --primary-dark: #5568d3;
  --secondary: #764ba2;
  --bg-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  --gradient-success: linear-gradient(135deg, #10b981 0%, #059669 100%);
  --gradient-warning: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  --gradient-danger: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: linear-gradient(135deg, #e0e7ff 0%, #f3e8ff 50%, #fce7f3 100%);
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
  box-shadow: 0 4px 20px rgba(102, 126, 234, 0.08);
  display: flex;
  flex-direction: column;
  height: fit-content;
  position: sticky;
  top: 24px;
  z-index: 100;
  transition: box-shadow 0.3s ease;
}

.sidebar:hover {
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.15);
}

.brand {
  font-weight: 700;
  font-size: 1.1em;
  padding: 10px 16px 16px;
  background: var(--bg-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.nav-item {
  padding: 12px 16px;
  border-radius: 10px;
  color: #475569;
  text-decoration: none;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
  overflow: hidden;
}


.nav-item i {
  font-size: 1.1em;
  width: 20px;
  text-align: center;
  transition: transform 0.3s ease;
  z-index: 1;
}

.nav-item:hover i {
  transform: scale(1.1);
}

.nav-item.active i {
  transform: scale(1.15);
}

.nav-item:hover {
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%);
  transform: translateX(4px);
  padding-left: 20px;
}

.nav-item:hover::before {
  opacity: 0.5;
  transform: scale(1);
}

.nav-item.active {
  background: var(--bg-gradient);
  color: white;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
  transform: translateX(4px);
  padding-left: 20px;
}

/* Active dot indicator (fully visible) */
.nav-item.active::before {
  opacity: 1;
  transform: scale(1.2);
  background: white;
  box-shadow: 0 0 8px rgba(255, 255, 255, 0.5);
}

/* Keep active state on hover */
.nav-item.active:hover {
  background: var(--bg-gradient);
  box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
}

.nav-item span {
  font-size: 0.95em;
  letter-spacing: 0.3px;
  transition: font-weight 0.2s ease;
  z-index: 1;
}

.nav-item.active span {
  letter-spacing: 0.5px;
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
  background: var(--bg-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
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

.stat-value {
  background: var(--bg-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.stat-card.new .stat-value {
  background: var(--gradient-success);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-card.modified .stat-value {
  background: var(--gradient-warning);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.stat-card.removed .stat-value {
  background: var(--gradient-danger);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

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
  box-shadow: 0 4px 24px rgba(102, 126, 234, 0.12);
  transition: transform 0.2s, box-shadow 0.2s;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.18);
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
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
  color: #065f46;
}

.badge-modified { 
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  color: #92400e;
}

.badge-removed { 
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  color: #991b1b;
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
  color: white;
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
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  color: #991b1b;
  text-decoration: line-through;
}

.new-value {
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
  color: #065f46;
}

.stat-card {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  padding: 24px;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  transition: transform 0.2s, box-shadow 0.2s;
  position: relative;
  overflow: hidden;
}

.stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: var(--bg-gradient);
  transform: scaleX(0);
  transition: transform 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 40px rgba(102, 126, 234, 0.2);
}

.stat-card:hover::before {
  transform: scaleX(1);
}

.section-tag {
  font-size: 0.75em;
  color: #999;
  font-family: monospace;
}

/* Breadcrumb styling for field paths */
.section-tag .crumb { color: #64748b; }
.section-tag .crumb-leaf { color: #0f172a; font-weight: 600; }
.section-tag .crumb-sep { color: #cbd5e1; padding: 0 6px; }
.section-tag { white-space: nowrap; display: inline-block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; }

.chart-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

/* Make chart clickable */
#pieChart {
  cursor: pointer;
}

#pieChart .slice {
  cursor: pointer;
  transition: opacity 0.2s;
}

#pieChart .slice:hover {
  opacity: 0.85;
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



/* Payload Toggle Buttons */
.payload-toggle {
  display: flex;
  gap: 10px;
}

.toggle-btn {
  padding: 8px 16px;
  border: 2px solid var(--primary);
  background: transparent;
  color: var(--primary);
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9em;
  font-weight: 600;
  transition: all 0.3s ease;
}

.toggle-btn:hover {
  background: rgba(102, 126, 234, 0.1);
  transform: translateY(-2px);
}

.toggle-btn.active {
  background: var(--bg-gradient);
  color: white;
  border-color: transparent;
}

.toggle-btn i {
  font-size: 1em;
}

/* Payload Box Updates */
.payload-box {
  background: #1e1e1e;
  border-radius: 12px;
  padding: 20px;
  max-height: 600px;
  overflow: auto;
  border: 1px solid #333;
  transition: opacity 0.3s ease;
  position: relative;
}

.payload-box.active {
  display: block;
}

.payload-content {
  font-family: 'Courier New', Consolas, monospace;
  font-size: 0.85em;
  color: #d4d4d4;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  margin: 0;
}

@media (max-width: 1024px) {
  .payload-box {
    max-height: 400px;
  }
}

/* Field path toggle styles */
.field-path-cell {
  position: relative;
}

.section-tag {
  font-size: 0.75em;
  color: #999;
  font-family: monospace;
  display: none; /* Hidden by default */
  opacity: 0;
  max-height: 0;
  overflow: hidden;
  transition: all 0.3s ease;
  margin-top: 4px;
}

.section-tag.visible {
  display: block;
  opacity: 1;
  max-height: 100px;
  animation: slideDown 0.3s ease;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Click indicator for modified fields */
.modified-row {
  cursor: pointer;
  position: relative;
}


.modified-row:hover {
  background: rgba(102, 126, 234, 0.05);
}

.modified-row.active {
  background: rgba(102, 126, 234, 0.08);
}

/* Field name with click hint */
.field-name-clickable {
  position: relative;
  padding-left: 20px;
}

.field-name-clickable::before {
  content: '▶';
  position: absolute;
  left: 0;
  color: var(--primary);
  font-size: 0.7em;
  transition: transform 0.3s ease;
}

.modified-row.active .field-name-clickable::before {
  transform: rotate(90deg);
}

/* Click hint text */
.click-hint {
  font-size: 0.7em;
  color: #94a3b8;
  margin-top: 4px;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.modified-row:hover .click-hint {
  opacity: 1;
}

/* Modified Fields Table - Clean Design */
#modified table {
  border-collapse: separate;
  border-spacing: 0;
}

#modified thead th {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 16px;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75em;
  letter-spacing: 1px;
}

/* Modified Row Styling */
.modified-row {
  cursor: pointer;
  transition: all 0.3s ease;
  border-left: 4px solid transparent;
}

.modified-row:hover {
  background: linear-gradient(90deg, rgba(102, 126, 234, 0.05) 0%, transparent 100%);
  border-left-color: var(--primary);
}

.modified-row.active {
  background: linear-gradient(90deg, rgba(102, 126, 234, 0.1) 0%, transparent 100%);
  border-left-color: var(--primary);
  box-shadow: inset 0 0 0 1px rgba(102, 126, 234, 0.2);
}

/* Field Name with Arrow */
.field-name-clickable {
  font-weight: 600;
  color: #1e293b;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
  position: relative;
  padding-left: 20px;
}

.field-name-clickable::before {
  content: '▶';
  position: absolute;
  left: 0;
  color: var(--primary);
  font-size: 0.7em;
  transition: transform 0.3s ease;
  display: inline-block;
}

.modified-row.active .field-name-clickable::before {
  transform: rotate(90deg);
}

/* Field Path - Hidden by Default */
.section-tag {
  display: none;
  opacity: 0;
  max-height: 0;
  overflow: hidden;
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
  margin-top: 8px;
  padding: 12px;
  background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
  border-left: 3px solid var(--primary);
  border-radius: 8px;
  font-family: 'Courier New', monospace;
  font-size: 0.8em;
  color: #475569;
}

.section-tag.visible {
  display: block;
  opacity: 1;
  max-height: 200px;
  animation: expandPath 0.4s ease;
}

@keyframes expandPath {
  0% {
    opacity: 0;
    max-height: 0;
    transform: translateY(-10px);
  }
  100% {
    opacity: 1;
    max-height: 200px;
    transform: translateY(0);
  }
}

.section-tag strong {
  color: var(--primary);
  font-weight: 700;
  margin-right: 8px;
}

/* Value Badges - Improved Design */
.value {
  font-family: 'Courier New', monospace;
  padding: 8px 14px;
  border-radius: 8px;
  display: inline-block;
  font-size: 0.85em;
  font-weight: 500;
  word-break: break-word;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.2s ease;
}

.value:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.old-value {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  color: #991b1b;
  text-decoration: line-through;
  border: 1px solid #fca5a5;
}

.new-value {
  background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%);
  color: #065f46;
  border: 1px solid #6ee7b7;
}

/* Table Cell Spacing */
#modified td {
  padding: 16px;
  vertical-align: middle;
}

/* Hover Effect on Entire Row */
.modified-row td {
  transition: all 0.3s ease;
}

.modified-row:hover td {
  background: transparent;
}

"""

# Write the complete CSS to file
with open(dashboard_css, "w", encoding="utf-8") as f:
    f.write(css_content)

# Generate HTML

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
                    <span>New Fields</span>
                </a>
                <a class="nav-item" href="#modified">
                    <i class="fa-solid fa-pen-to-square"></i>
                    <span>Modified Fields</span>
                </a>
                <a class="nav-item" href="#removed">
                    <i class="fa-solid fa-eraser"></i>
                    <span>Removed Fields</span>
                </a>
                <a class="nav-item" href="#payloads">
                    <i class="fa-solid fa-code-compare"></i>
                    <span>View Payloads</span>
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
                            {round(len(removed_fields) / total_changes * 100) if total_changes > 0 else 0}% Removed
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
                        <th style="width: 30%;">Field</th>
                        <th style="width: 15%;">Field Path</th>
                        <th style="width: 55%;">New Value</th>
                    </tr>
                </thead>
                <tbody>
"""
    for item in new_fields:
        field_path = html.escape(item.get("Field", ""), quote=True)
        section_raw = item.get("Section", "root") or "root"
        breadcrumb_html = html.escape(section_raw, quote=True)
        value = str(item.get("Value", "N/A"))
        display_value = (value[:100] + '...') if len(value) > 100 else value
        display_value = html.escape(display_value, quote=True)
        html_content += f"""
                     <tr>
                         <td class="field-name">{field_path}</td>
                         <td><span class="section-tag">{breadcrumb_html}</span></td>
                         <td><span class="value new-value">{display_value}</span></td>
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
                        <th style="width: 35%;">Field Name</th>
                        <th style="width: 32%;">Previous Value</th>
                        <th style="width: 33%;">New Value</th>
                    </tr>
                </thead>
                <tbody>
"""
    for idx, item in enumerate(modified_fields):
        field_path = html.escape(item.get("Field", ""), quote=True)
        section_raw = item.get("Section", "root") or "root"
        breadcrumb_html = html.escape(section_raw, quote=True)
        old_val = str(item.get("Old Value", "N/A"))
        new_val = str(item.get("New Value", "N/A"))
        old_display = (old_val[:60] + '...') if len(old_val) > 60 else old_val
        new_display = (new_val[:60] + '...') if len(new_val) > 60 else new_val
        old_display = html.escape(old_display, quote=True)
        new_display = html.escape(new_display, quote=True)
        
        html_content += f"""
                     <tr class="modified-row" data-row-id="mod-{idx}">
                         <td class="field-path-cell">
                             <div class="field-name field-name-clickable">{field_path}</div>
                             <div class="section-tag" id="path-mod-{idx}">
                                 <strong>Full Path:</strong> {breadcrumb_html}
                             </div>
                         </td>
                         <td><span class="value old-value">{old_display}</span></td>
                         <td><span class="value new-value">{new_display}</span></td>
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
                        <th style="width: 30%;">Field</th>
                        <th style="width: 15%;">Field Path</th>
                        <th style="width: 55%;">Removed Value</th>
                    </tr>
                </thead>
                <tbody>
"""
    for item in removed_fields:
        field_path = html.escape(item.get("Field", ""), quote=True)
        section_raw = item.get("Section", "root") or "root"
        breadcrumb_html = html.escape(section_raw, quote=True)
        value = str(item.get("Value", "N/A"))
        display_value = (value[:100] + '...') if len(value) > 100 else value
        display_value = html.escape(display_value, quote=True)
        html_content += f"""
                     <tr>
                         <td class=\"field-name\">{field_path}</td>
                         <td><span class=\"section-tag\">{breadcrumb_html}</span></td>
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
"""
html_content += """
        <!-- View Payloads Section -->
        <section id="payloads" class="section">
            <div class="card full-width">
                <div class="card-header">
                    <h2 class="card-title">Payload Viewer</h2>
                    <div class="payload-toggle">
                        <button class="toggle-btn active" data-payload="current">
                            <i class="fa-solid fa-file-code"></i> New Response
                        </button>
                        <button class="toggle-btn" data-payload="base">
                            <i class="fa-solid fa-file-lines"></i> Old Response 
                        </button>
                    </div>
                </div>
                
                <!-- Current Payload (shown by default) -->
                <div class="payload-box active" id="currentPayloadBox">
                    <pre class="payload-content">"""

escaped_current_payload = html.escape(current_payload, quote=True)
html_content += escaped_current_payload

html_content += """</pre>
                </div>
                
                <!-- Base Payload (hidden by default) -->
                <div class="payload-box" id="basePayloadBox" style="display: none;">
                    <pre class="payload-content">"""

escaped_base_payload = html.escape(base_payload, quote=True)
html_content += escaped_base_payload

html_content += """</pre>
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
      (function() {
        const navItems = document.querySelectorAll('.nav .nav-item');
        const sections = document.querySelectorAll('.section');
        
        function showSection(targetId) {
          sections.forEach(section => {
            section.classList.remove('active');
          });
          
          const targetSection = document.getElementById(targetId);
          if (targetSection) {
            targetSection.classList.add('active');
          }
          
          navItems.forEach(nav => {
            nav.classList.remove('active');
            const href = nav.getAttribute('href');
            if ((targetId === 'dashboard' && href === '#') || 
                (href === '#' + targetId)) {
              nav.classList.add('active');
            }
          });
          
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
        
        navItems.forEach(navItem => {
          navItem.addEventListener('click', function(e) {
            e.preventDefault();
            const href = this.getAttribute('href');
            let sectionId = 'dashboard';
            if (href && href !== '#') {
              sectionId = href.substring(1);
            }
            showSection(sectionId);
            history.replaceState(null, '', href || '#dashboard');
          });
        });
        
        const chartDiv = document.getElementById('pieChart');
        if (chartDiv) {
          function handleChartClick(label) {
            let targetSection = 'dashboard';
            if (label === 'New Fields') targetSection = 'new';
            else if (label === 'Modified Fields') targetSection = 'modified';
            else if (label === 'Removed Fields') targetSection = 'removed';
            showSection(targetSection);
            history.replaceState(null, '', '#' + targetSection);
          }

          if (typeof chartDiv.on === 'function') {
            chartDiv.on('plotly_click', function(data) {
              const label = (data && data.points && data.points[0] && data.points[0].label) || '';
              handleChartClick(label);
            });
          } else {
            chartDiv.addEventListener('plotly_click', function(evt) {
              const detail = evt.detail || {};
              const label = (detail && detail.points && detail.points[0] && detail.points[0].label) || '';
              handleChartClick(label);
            });
          }
        }
        
        const initialHash = window.location.hash;
        if (initialHash && initialHash.length > 1) {
          const initialSection = initialHash.substring(1);
          showSection(initialSection);
        } else {
          showSection('dashboard');
        }
        
        // Payload Toggle
        const toggleBtns = document.querySelectorAll('.toggle-btn');
        const currentPayloadBox = document.getElementById('currentPayloadBox');
        const basePayloadBox = document.getElementById('basePayloadBox');

        toggleBtns.forEach(btn => {
          btn.addEventListener('click', function() {
            const payloadType = this.getAttribute('data-payload');
            toggleBtns.forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            
            if (payloadType === 'current') {
              currentPayloadBox.style.display = 'block';
              basePayloadBox.style.display = 'none';
            } else {
              currentPayloadBox.style.display = 'none';
              basePayloadBox.style.display = 'block';
            }
          });
        });

        // ========== NEW: Toggle Field Path on Click ==========
        const modifiedRows = document.querySelectorAll('.modified-row');

        modifiedRows.forEach(row => {
          row.addEventListener('click', function(e) {
            // Don't trigger if clicking on a value span
            if (e.target.classList.contains('value')) return;
            
            const rowId = this.getAttribute('data-row-id');
            const pathElement = document.getElementById('path-' + rowId);
            
            // Close all other paths
            document.querySelectorAll('.section-tag').forEach(tag => {
              if (tag.id !== 'path-' + rowId) {
                tag.classList.remove('visible');
              }
            });
            
            // Remove active class from all rows
            modifiedRows.forEach(r => r.classList.remove('active'));
            
            // Toggle current path
            if (pathElement) {
              const isVisible = pathElement.classList.contains('visible');
              
              if (isVisible) {
                pathElement.classList.remove('visible');
                this.classList.remove('active');
              } else {
                pathElement.classList.add('visible');
                this.classList.add('active');
              }
            }
          });
        });
        
      })();
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
