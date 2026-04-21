import os
import sys
import json
import html
import re
import plotly.graph_objects as go
import xml.dom.minidom as minidom
from pathlib import Path
from collections import defaultdict
import logging
import difflib
import copy

# ========== LOGGING SETUP ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ========== HELPER FUNCTION FOR TABLE ROW GENERATION ==========
def create_field_row(item, row_type, idx):
    """
    Generate HTML for a table row (new/modified/removed).
    
    Args:
        item: Dictionary containing field data
        row_type: 'new', 'modified', or 'removed'
        idx: Row index for unique ID generation
    
    Returns:
        HTML string for the table row
    """
    field_path = html.escape(item.get("Field", ""), quote=True)
    section_raw = item.get("Section", "root") or "root"
    breadcrumb_html = html.escape(section_raw, quote=True)
    include_path_row = bool(section_raw) and section_raw != "Headers"
    row_id = f'{row_type}-{idx}' if row_type != 'modified' else f'mod-{idx}'
    # Path row is hidden by default, shown when main row is active (by JS toggle)
    path_row = (
        f"""
        <tr id='row-path-{row_id}' class="field-path-row" style="display:none;background:#faf6f7;"><td colspan='100'><span class='full-path-label'>Full Path:</span> <span class='full-path-mono'>{breadcrumb_html}</span></td></tr>
        """
        if include_path_row else ""
    )
    row_class = f"{row_type}-row" if row_type != 'modified' else 'modified-row'
    if row_type == "modified":
        old_val = str(item.get("Old Value", "N/A"))
        new_val = str(item.get("New Value", "N/A"))
        old_display = (old_val[:60] + '...') if len(old_val) > 60 else old_val
        new_display = (new_val[:60] + '...') if len(new_val) > 60 else new_val
        old_display = html.escape(old_display, quote=True)
        new_display = html.escape(new_display, quote=True)
        main_row = f"""
            <tr class="{row_class}" data-row-id="{row_id}" style='cursor:pointer;'>
                <td class="field-path-cell"><div class="field-name field-name-clickable">{field_path}</div></td>
                <td><span class="value old-value">{old_display}</span></td>
                <td><span class="value new-value">{new_display}</span></td>
            </tr>
        """
        return main_row + path_row
    else:
        value = str(item.get("Value", "N/A"))
        display_value = (value[:80] + '...') if len(value) > 80 else value
        display_value = html.escape(display_value, quote=True)
        value_class = "new-value" if row_type == "new" else "old-value"
        main_row = f"""
            <tr class="{row_class}" data-row-id="{row_id}" style='cursor:pointer;'>
                <td class="field-path-cell"><div class="field-name field-name-clickable">{field_path}</div></td>
                <td><span class="value {value_class}">{display_value}</span></td>
            </tr>
        """
        return main_row + path_row

def html_escape(s):
    import html
    return html.escape(s, quote=False)

def build_diff_table(diff):
    html_rows = ['<table class="diff-table"><thead><tr><th>Old Response</th><th>New Response</th></tr></thead><tbody>']
    for line in diff:
        tag, text = line[0], line[2:]
        if tag == ' ':  # Unchanged
            html_rows.append(f'<tr><td class="diff-ctx">{html_escape(text)}</td><td class="diff-ctx">{html_escape(text)}</td></tr>')
        elif tag == '-':  # Deletion
            html_rows.append(f'<tr><td class="diff-del">{html_escape(text)}</td><td class="diff-empty"></td></tr>')
        elif tag == '+':  # Addition
            html_rows.append(f'<tr><td class="diff-empty"></td><td class="diff-add">{html_escape(text)}</td></tr>')
        # ignore '?' hint lines
    html_rows.append('</tbody></table>')
    return '\n'.join(html_rows)

  def pretty_print_xml(xml_text: str) -> str:
    try:
      parsed = minidom.parseString(xml_text)
      pretty = parsed.toprettyxml(indent="  ")
      # Remove blank lines from minidom output
      return "\n".join(line for line in pretty.splitlines() if line.strip())
    except Exception:
      return xml_text

diff_file = sys.argv[1] if len(sys.argv) > 1 else "results/diff.txt"
output_dir = Path("results")
output_dir.mkdir(exist_ok=True)

dashboard_html = output_dir / "diff_dashboard.html"
dashboard_css = output_dir / "diff_dashboard.css"

# Calculate logo path relative to script location (works for GitHub/workflows)
script_dir = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(script_dir, "assests", "syngenta_logo.jpg")
# Calculate relative path from HTML output location to logo for browser
logo_relative_path = os.path.relpath(logo_path, os.path.dirname(dashboard_html)).replace("\\", "/")

if not os.path.exists(diff_file):
    print(f"Diff file not found: {diff_file}")
    sys.exit(1)

try:
    logger.info(f"Reading diff file: {diff_file}")
    with open(diff_file, "r", encoding="utf-8") as f:
        diff_content = f.read()
    logger.info(f"Successfully read diff file ({len(diff_content)} bytes)")
except Exception as e:
    logger.error(f"Failed to read diff file: {e}")
    print(f"Error reading diff file: {e}")
    sys.exit(1)

# Load payload files
base_payload_file = "results/response_base.txt"
current_payload_file = "results/response_current.txt"

base_payload = ""
current_payload = ""

try:
    logger.info(f"Loading base payload: {base_payload_file}")
    with open(base_payload_file, "r", encoding="utf-8") as f:
        base_payload_raw = f.read()
        try:
            base_payload_obj = json.loads(base_payload_raw)
            base_payload = json.dumps(base_payload_obj, indent=2, sort_keys=True)
            logger.info("Base payload parsed as JSON")
        except json.JSONDecodeError:
          base_payload = pretty_print_xml(base_payload_raw)
          logger.info("Base payload loaded as XML/plain text")
except FileNotFoundError:
    logger.warning(f"Base payload file not found: {base_payload_file}")
    base_payload = "# Base payload file not found\n# Expected location: results/response_base.txt"
except Exception as e:
    logger.error(f"Error loading base payload: {e}")
    base_payload = f"# Error loading base payload: {str(e)}"

try:
    logger.info(f"Loading current payload: {current_payload_file}")
    with open(current_payload_file, "r", encoding="utf-8") as f:
        current_payload_raw = f.read()
        try:
            current_payload_obj = json.loads(current_payload_raw)
            current_payload = json.dumps(current_payload_obj, indent=2, sort_keys=True)
            logger.info("Current payload parsed as JSON")
        except json.JSONDecodeError:
          current_payload = pretty_print_xml(current_payload_raw)
          logger.info("Current payload loaded as XML/plain text")
except FileNotFoundError:
    logger.warning(f"Current payload file not found: {current_payload_file}")
    current_payload = "# Current payload file not found\n# Expected location: results/response_current.txt"
except Exception as e:
    logger.error(f"Error loading current payload: {e}")
    current_payload = f"# Error loading current payload: {str(e)}"

escaped_base_payload = html.escape(base_payload, quote=True)
escaped_current_payload = html.escape(current_payload, quote=True)

# Check if it's JSON format (DeepDiff) or unified diff format
is_json_format = False
diff_data = {}
diff_mode = None
try:
  diff_data = json.loads(diff_content)
  # Support wrapped diff format: {"mode": "json|xml|text", "diff": ...}
  if isinstance(diff_data, dict) and "mode" in diff_data and "diff" in diff_data:
    diff_mode = diff_data.get("mode")
    diff_payload = diff_data.get("diff")
    if diff_mode == "text" and isinstance(diff_payload, str):
      diff_content = diff_payload
      is_json_format = False
      diff_data = {}
      logger.info("Diff format detected: Wrapped text diff")
    else:
      diff_data = diff_payload if isinstance(diff_payload, dict) else {}
      is_json_format = True
      logger.info("Diff format detected: Wrapped JSON diff")
  else:
    is_json_format = True
    logger.info("Diff format detected: JSON (DeepDiff)")
except json.JSONDecodeError:
  logger.info("Diff format detected: Unified diff")
  pass

# Parse diff intelligently
# Store by FULL PATH to avoid collisions between identical leaf names in different branches
field_changes = defaultdict(lambda: {"added": [], "removed": [], "section": "", "field": ""})
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

    def flatten_object_change(old_obj, new_obj, base_path_slash):
        """Flatten nested dict changes into per-leaf entries under field_changes keyed by full path."""
        if isinstance(old_obj, dict) and isinstance(new_obj, dict):
            keys = set(old_obj.keys()) | set(new_obj.keys())
            for k in keys:
                child_old = old_obj.get(k, None)
                child_new = new_obj.get(k, None)
                child_path = f"{base_path_slash}/{k}" if base_path_slash else k
                if isinstance(child_old, dict) and isinstance(child_new, dict):
                    flatten_object_change(child_old, child_new, child_path)
                else:
                    full_key = child_path
                    leaf = str(k)
                    # added / removed / changed
                    if child_old is None and child_new is not None:
                        field_changes[full_key]["added"].append(str(child_new))
                    elif child_new is None and child_old is not None:
                        field_changes[full_key]["removed"].append(str(child_old))
                    elif child_old is not None and child_new is not None and child_old != child_new:
                        field_changes[full_key]["removed"].append(str(child_old))
                        field_changes[full_key]["added"].append(str(child_new))
                    # section and display field
                    field_changes[full_key]["section"] = full_key
                    field_changes[full_key]["field"] = leaf
        else:
            # Primitive to primitive change at base path
            if old_obj != new_obj:
                full_key = base_path_slash
                leaf = base_path_slash.split("/")[-1] if base_path_slash else base_path_slash
                field_changes[full_key]["removed"].append(str(old_obj))
                field_changes[full_key]["added"].append(str(new_obj))
                field_changes[full_key]["section"] = full_key
                field_changes[full_key]["field"] = leaf

    # Handle DeepDiff JSON format
    for key, value in diff_data.items():
        if key == "dictionary_item_added":
            for field_path, val in iter_path_items(value):
                full_path = format_field_path_slash(field_path)
                field_name = extract_field_name(field_path)
                if val is not None:
                    field_changes[full_path]["added"].append(str(val))
                else:
                    field_changes[full_path]["added"].append("<added>")
                field_changes[full_path]["section"] = full_path
                field_changes[full_path]["field"] = field_name
        elif key == "dictionary_item_removed":
            for field_path, val in iter_path_items(value):
                full_path = format_field_path_slash(field_path)
                field_name = extract_field_name(field_path)
                if val is not None:
                    field_changes[full_path]["removed"].append(str(val))
                else:
                    field_changes[full_path]["removed"].append("<removed>")
                field_changes[full_path]["section"] = full_path
                field_changes[full_path]["field"] = field_name
        elif key == "values_changed":
            for field_path, change_data in value.items():
                full_path = format_field_path_slash(field_path)
                field_name = extract_field_name(field_path)
                old_v = change_data.get("old_value")
                new_v = change_data.get("new_value")
                # If object-level change, flatten into per-leaf rows
                if isinstance(old_v, dict) and isinstance(new_v, dict):
                    flatten_object_change(old_v, new_v, full_path)
                else:
                    if "old_value" in change_data:
                        field_changes[full_path]["removed"].append(str(old_v))
                    if "new_value" in change_data:
                        field_changes[full_path]["added"].append(str(new_v))
                    field_changes[full_path]["section"] = full_path
                    field_changes[full_path]["field"] = field_name
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

for full_path, changes in field_changes.items():
    display_field = changes.get("field") or full_path.split("/")[-1]
    if changes["added"] and changes["removed"]:
        modified_fields.append({
            "Field": display_field,
            "Old Value": ", ".join(changes["removed"]),
            "New Value": ", ".join(changes["added"]),
            "Section": changes["section"] or full_path
        })
    elif changes["added"]:
        new_fields.append({
            "Field": display_field,
            "Value": ", ".join(changes["added"]),
            "Section": changes["section"] or full_path
        })
    elif changes["removed"]:
        removed_fields.append({
            "Field": display_field,
            "Value": ", ".join(changes["removed"]),
            "Section": changes["section"] or full_path
        })

# Create summary metrics
total_changes = len(new_fields) + len(modified_fields) + len(removed_fields)
no_changes = total_changes == 0

logger.info(f"Diff parsing complete:")
logger.info(f"  - New fields: {len(new_fields)}")
logger.info(f"  - Modified fields: {len(modified_fields)}")
logger.info(f"  - Removed fields: {len(removed_fields)}")
logger.info(f"  - Total changes: {total_changes}")

if no_changes:
    logger.warning("No differences found in the comparison")
    print("No differences found. Generating summary dashboard.")

# ===================== HEADERS DIFF PARSING (results/diff_headers.txt) =====================
headers_diff_file = "results/diff_headers.txt"
headers_diff_content = ""
headers_is_json_format = False
headers_new = []
headers_modified = []
headers_removed = []

if os.path.exists(headers_diff_file):
    try:
        logger.info(f"Reading headers diff file: {headers_diff_file}")
        with open(headers_diff_file, "r", encoding="utf-8") as hf:
            headers_diff_content = hf.read()
    except Exception as e:
        logger.warning(f"Failed to read headers diff file: {e}")

    if headers_diff_content:
        # Try DeepDiff JSON first
        headers_changes_map = defaultdict(lambda: {"added": [], "removed": [], "section": "", "field": ""})
        try:
            headers_diff_data = json.loads(headers_diff_content)
            headers_is_json_format = True
            # Helpers for full-path handling and flattening
            def _hdr_full_path(path: str) -> str:
                if not path:
                    return "root"
                p = path[4:] if path.startswith("root") else path
                parts = [x for x in p.split("'")[1::2] if x.strip()]
                if not parts:
                    parts = [x for x in p.split('"')[1::2] if x.strip()]
                return "/".join(parts) if parts else "root"
            def _hdr_leaf(path: str) -> str:
                try:
                    parts = [x for x in path.split("'")[1::2] if x.strip()] or [x for x in path.split('"')[1::2] if x.strip()]
                    return parts[-1] if parts else path
                except Exception:
                    return path
            def _flatten_hdr(old_obj, new_obj, base_path: str):
                if isinstance(old_obj, dict) and isinstance(new_obj, dict):
                    keys = set(old_obj.keys()) | set(new_obj.keys())
                    for k in keys:
                        o = old_obj.get(k)
                        n = new_obj.get(k)
                        fp = f"{base_path}/{k}" if base_path else str(k)
                        if isinstance(o, dict) and isinstance(n, dict):
                            _flatten_hdr(o, n, fp)
                        else:
                            if o is None and n is not None:
                                headers_changes_map[fp]["added"].append(str(n))
                            elif n is None and o is not None:
                                headers_changes_map[fp]["removed"].append(str(o))
                            elif o is not None and n is not None and o != n:
                                headers_changes_map[fp]["removed"].append(str(o))
                                headers_changes_map[fp]["added"].append(str(n))
                            headers_changes_map[fp]["section"] = fp
                            headers_changes_map[fp]["field"] = str(k)
                else:
                    if old_obj != new_obj:
                        fp = base_path
                        headers_changes_map[fp]["removed"].append(str(old_obj))
                        headers_changes_map[fp]["added"].append(str(new_obj))
                        headers_changes_map[fp]["section"] = fp
                        headers_changes_map[fp]["field"] = fp.split("/")[-1]

            # Handle DeepDiff JSON for headers
            if "dictionary_item_added" in headers_diff_data:
                for path in headers_diff_data["dictionary_item_added"]:
                    fp = _hdr_full_path(path)
                    leaf = _hdr_leaf(path)
                    headers_changes_map[fp]["added"].append("<added>")
                    headers_changes_map[fp]["section"] = fp
                    headers_changes_map[fp]["field"] = leaf
            if "dictionary_item_removed" in headers_diff_data:
                for path in headers_diff_data["dictionary_item_removed"]:
                    fp = _hdr_full_path(path)
                    leaf = _hdr_leaf(path)
                    headers_changes_map[fp]["removed"].append("<removed>")
                    headers_changes_map[fp]["section"] = fp
                    headers_changes_map[fp]["field"] = leaf
            if "values_changed" in headers_diff_data:
                for path, change in headers_diff_data["values_changed"].items():
                    fp = _hdr_full_path(path)
                    leaf = _hdr_leaf(path)
                    old_val = change.get("old_value")
                    new_val = change.get("new_value")
                    if isinstance(old_val, dict) and isinstance(new_val, dict):
                        _flatten_hdr(old_val, new_val, fp)
                    else:
                        if "old_value" in change:
                            headers_changes_map[fp]["removed"].append(str(old_val))
                        if "new_value" in change:
                            headers_changes_map[fp]["added"].append(str(new_val))
                        headers_changes_map[fp]["section"] = fp
                        headers_changes_map[fp]["field"] = leaf
        except json.JSONDecodeError:
            # Unified diff style: +Header: value, -Header: value
            for line in headers_diff_content.splitlines():
                line = line.rstrip("\n")
                if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                    continue
                if line.startswith("+") and not line.startswith("+++"):
                    content = line[1:].strip()
                    m = re.match(r"([^:]+):\s*(.*)", content)
                    if m:
                        name = m.group(1).strip()
                        val = m.group(2).strip()
                        headers_changes_map[name]["added"].append(val)
                elif line.startswith("-") and not line.startswith("---"):
                    content = line[1:].strip()
                    m = re.match(r"([^:]+):\s*(.*)", content)
                    if m:
                        name = m.group(1).strip()
                        val = m.group(2).strip()
                        headers_changes_map[name]["removed"].append(val)

        # Categorize
        for name, ch in headers_changes_map.items():
            display_field = ch.get("field") or name
            section = ch.get("section") or "Headers"
            if ch["added"] and ch["removed"]:
                headers_modified.append({
                    "Field": display_field,
                    "Old Value": ", ".join(ch["removed"]),
                    "New Value": ", ".join(ch["added"]),
                    "Section": section
                })
            elif ch["added"]:
                headers_new.append({
                    "Field": display_field,
                    "Value": ", ".join(ch["added"]),
                    "Section": section
                })
            elif ch["removed"]:
                headers_removed.append({
                    "Field": display_field,
                    "Value": ", ".join(ch["removed"]),
                    "Section": section
                })

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

/* Collapsed layout for sidebar */
.layout.collapsed {
  grid-template-columns: 72px 1fr;
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

/* Collapsed sidebar styling */
.sidebar.collapsed {
  padding: 16px 8px;
  align-items: center;
}

.sidebar.collapsed .brand-text,
.sidebar.collapsed .brand-subtitle,
.sidebar.collapsed .nav-item span,
.sidebar.collapsed .nav-submenu {
  display: none;
}

/* Allow header submenu to show as overlay when collapsed */
.sidebar.collapsed .nav { position: relative; }
.sidebar.collapsed #nav-header { position: relative; }
.sidebar.collapsed .nav-submenu.show {
  display: flex;
  position: absolute;
  left: 74px; /* just outside collapsed sidebar */
  top: 0;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  z-index: 2000;
  min-width: 220px;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 12px 10px;
}

.sidebar.collapsed .caret { display: none; }

.sidebar:hover {
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.15);
}

.brand {
  font-weight: 700;
  font-size: 1em;
  padding: 10px 16px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  border-bottom: 2px solid #f0f0f0;
}

/* Sidebar toggle button */
.sidebar-toggle {
  margin-left: auto;
  background: rgba(102, 126, 234, 0.1);
  border: 1px solid rgba(102, 126, 234, 0.25);
  color: #5568d3;
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease;
}

.sidebar-toggle:hover { background: rgba(102, 126, 234, 0.18); transform: translateY(-1px); }
.sidebar.collapsed .sidebar-toggle { margin: 0; }

.brand-icon {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: #ffffff;
  color: #5568d3;
  font-size: 1.25em;
  box-shadow: 0 1px 2px rgba(0,0,0,0.06);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease, background 0.2s ease;
}

.brand-icon:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(102, 126, 234, 0.18);
  background: rgba(255,255,255,0.95);
}

.brand-icon i {
  pointer-events: none;
}

/* Shrink icon when sidebar is collapsed */
.sidebar.collapsed .brand-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  font-size: 1.1em;
}

.brand-text {
  font-weight: 700;
  font-size: 1.1em;
  background: var(--bg-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.brand-subtitle {
  font-size: 0.8em;
  color: #64748b;
  font-weight: 600;
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

/* Submenu styling for Header dropdown */
.nav-submenu {
  display: none;
  flex-direction: column;
  gap: 6px;
  margin: 6px 0 0 36px;
}

.nav-submenu.show {
  display: flex;
}

.nav-subitem {
  padding: 10px 14px;
  border-radius: 8px;
  color: #5b6472;
  text-decoration: none;
  transition: background 0.2s ease, transform 0.2s ease;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.9em;
}

.nav-subitem:hover {
  background: rgba(102, 126, 234, 0.08);
  transform: translateX(3px);
}

.nav-subitem i {
  font-size: 0.95em;
  width: 16px;
  text-align: center;
}

.nav-item .caret {
  margin-left: auto;
  font-size: 0.8em;
  color: #94a3b8;
  transition: transform 0.2s ease;
}

.nav-item.expanded .caret {
  transform: rotate(90deg);
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
  color: #333;
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
  font-family: 'Montserrat', sans-serif;
  background: #f5f5f5;
  padding: 6px 10px;
  border-radius: 6px;
  display: inline-block;
  font-size: 1em;
  word-break: break-word;
}

.old-value {
  background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
  color: #991b1b;
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

/* Path rows toggling inside tables */
.field-path-row { display: none; }
.field-path-row.visible { display: table-row !important; }

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



/* ========== CONSOLIDATED TABLE STYLING FOR ALL SECTIONS ========== */

/* Base table styling for all sections */
#modified table,
#new table,
#removed table {
  border-collapse: separate;
  border-spacing: 0;
}

/* Common table header styling */
#modified thead th,
#new thead th,
#removed thead th {
  color: white;
  padding: 16px;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75em;
  letter-spacing: 1px;
}

/* Section-specific header colors */
#modified thead th {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

#new thead th {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
}

#removed thead th {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
}

/* Common row styling for all change types */
.modified-row,
.new-row,
.removed-row {
  cursor: pointer;
  transition: all 0.3s ease;
  border-left: 4px solid transparent;
}

/* Hover states with section-specific colors */
.modified-row:hover {
  background: linear-gradient(90deg, rgba(102, 126, 234, 0.05) 0%, transparent 100%);
  border-left-color: var(--primary);
}

.new-row:hover {
  background: linear-gradient(90deg, rgba(16, 185, 129, 0.05) 0%, transparent 100%);
  border-left-color: #10b981;
}

.removed-row:hover {
  background: linear-gradient(90deg, rgba(239, 68, 68, 0.05) 0%, transparent 100%);
  border-left-color: #ef4444;
}

/* Active states with section-specific colors */
.modified-row.active {
  background: linear-gradient(90deg, rgba(102, 126, 234, 0.1) 0%, transparent 100%);
  border-left-color: var(--primary);
  box-shadow: inset 0 0 0 1px rgba(102, 126, 234, 0.2);
}

.new-row.active {
  background: linear-gradient(90deg, rgba(16, 185, 129, 0.1) 0%, transparent 100%);
  border-left-color: #10b981;
  box-shadow: inset 0 0 0 1px rgba(16, 185, 129, 0.2);
}

.removed-row.active {
  background: linear-gradient(90deg, rgba(239, 68, 68, 0.1) 0%, transparent 100%);
  border-left-color: #ef4444;
  box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.2);
}

/* Arrow indicators - section-specific colors */
.modified-row .field-name-clickable::before {
  color: var(--primary);
}

.new-row .field-name-clickable::before {
  color: #10b981;
}

.removed-row .field-name-clickable::before {
  color: #ef4444;
}

/* Rotate arrow on active */
.modified-row.active .field-name-clickable::before,
.new-row.active .field-name-clickable::before,
.removed-row.active .field-name-clickable::before {
  transform: rotate(90deg);
}

/* Field path styling - section-specific border colors */
.modified-row .section-tag {
  border-left-color: var(--primary);
}

.new-row .section-tag {
  border-left-color: #10b981;
}

.removed-row .section-tag {
  border-left-color: #ef4444;
}

/* Field path strong text - section-specific colors */
.modified-row .section-tag strong {
  color: var(--primary);
}

.new-row .section-tag strong {
  color: #10b981;
}

.removed-row .section-tag strong {
  color: #ef4444;
}

/* Common table cell padding */
#modified td,
#new td,
#removed td {
  padding: 16px;
  vertical-align: middle;
}

/* Hover effect on entire row */
.modified-row td,
.new-row td,
.removed-row td {
  transition: all 0.3s ease;
}

.modified-row:hover td,
.new-row:hover td,
.removed-row:hover td {
  background: transparent;
}

"""

# Add CSS for .diff-table, .diff-del (red), .diff-add (green), .diff-ctx (no bg), .diff-empty (blank cell) right before writing CSS file:
css_content += '''
.diff-table { border-collapse: separate; border-spacing: 0; width: 100%; font-size: 0.93em; font-family: "Fira Mono", "Courier New", monospace; }
.diff-table th { background: #f4f0fa; color: #4c3487; padding: 8px 12px; border-bottom: 2px solid #ddd; font-size:1em;}
.diff-table td { padding: 3px 12px; vertical-align: top; white-space: pre; }
.diff-del { background: #fbeaea; color: #bf2222; border-left: 4px solid #f95b5b; }
.diff-add { background: #e7faea; color: #13773b; border-left: 4px solid #21c65a; }
.diff-ctx { background: #fff; color: #333; }
.diff-empty { background: #f8fafc; }
'''

# Add the CSS for .full-path-label and .full-path-mono
css_content += """
.full-path-label { color: #b91c1c; font-size: 0.95em; font-weight: bold; font-family: monospace; margin-right: 6px; }
.full-path-mono { font-family: monospace; color: #374151; font-size: 0.97em; }
"""

# Add/replace CSS for sticky header/footer, e.g.
css_content += '''
.header {
  background: rgba(255, 255, 255, 0.95);
  position: sticky;
  top: 0;
  z-index: 201;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
'''

css_content += """
/* Download Button Styling */
.download-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 0.85em;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.25);
}

.download-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.35);
}

.download-btn:active {
  transform: translateY(0);
}

.download-btn i {
  font-size: 1em;
}
"""

# Update the .footer CSS (remove position: sticky and bottom: 0)
css_content += '''
.footer {
  /* No sticky or fixed positioning */
  position: static;
  margin-top: auto;
  background: rgba(255, 255, 255, 0.98);
  z-index: 200;
  box-shadow: 0 -2px 8px rgba(0,0,0,0.06);
}
'''



# Write the complete CSS to file
try:
    logger.info(f"Writing CSS file: {dashboard_css}")
    with open(dashboard_css, "w", encoding="utf-8") as f:
        f.write(css_content)
    logger.info(f"CSS file written successfully ({len(css_content)} bytes)")
except Exception as e:
    logger.error(f"Failed to write CSS file: {e}")
    print(f"Error writing CSS file: {e}")
    sys.exit(1)

# Generate HTML

base_lines = base_payload.splitlines()
current_lines = current_payload.splitlines()
diff = list(difflib.ndiff(base_lines, current_lines))

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Variance Analysis Dashboard</title>
    <link rel="stylesheet" href="diff_dashboard.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
 </head>
 <body>
    <div class="layout">
        <aside class="sidebar">
            <div class="brand">
              <div class="brand-icon" title="Toggle sidebar">
                <i class="fa-solid fa-bars"></i>
              </div>
              <div style="display:flex;flex-direction:column;gap:2px;">
                <span class="brand-text">SAP-Testing</span>
              </div>
            </div>
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
                <a class="nav-item" href="#compare">
                    <i class="fa-solid fa-code-compare"></i>
                    <span>Compare Responses</span>
                </a>
                <a class="nav-item" href="#payloads">
                    <i class="fa-solid fa-book-open-reader"></i>
                    <span>View Responses</span>
                </a>
                <a id="nav-header" class="nav-item">
                    <i class="fa-solid fa-code"></i>
                    <span>Header</span>
                    <i class="fa-solid fa-chevron-right caret"></i>
                </a>
                <div id="nav-header-submenu" class="nav-submenu">
                    <a class="nav-subitem" href="#header-new"><i class="fa-solid fa-square-plus"></i><span>New Header</span></a>
                    <a class="nav-subitem" href="#header-modified"><i class="fa-solid fa-wand-magic-sparkles"></i><span>Modified Header</span></a>
                    <a class="nav-subitem" href="#header-removed"><i class="fa-solid fa-trash-can"></i><span>Removed Header</span></a>
                </div>
            </nav>
        </aside>
        <main class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-content">
                <div>
                    <h1>Variance Analysis Dashboard</h1>
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

        
"""

# New Fields
html_content += f"""
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
                        <th style="width: 40%;">Field Name</th>
                        <th style="width: 60%;">New Value</th>
                    </tr>
                </thead>
                <tbody>
"""
    for idx, item in enumerate(new_fields):
        html_content += create_field_row(item, "new", idx)
    
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

html_content += """
        </div>
        </section>
"""
html_content += f"""
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
        html_content += create_field_row(item, "modified", idx)
    
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
"""
# ===================== HEADERS SECTIONS =====================
html_content += f"""
        <!-- New Headers -->
        <section id="header-new" class="section">
        <div class="card full-width">
            <div class="card-header">
                <h2 class="card-title">New Headers</h2>
                <span class="badge badge-new">{len(headers_new)} items</span>
            </div>
"""
if headers_new:
    html_content += """
            <table>
                <thead>
                    <tr>
                        <th style="width: 40%;">Header</th>
                        <th style="width: 60%;">New Value</th>
                    </tr>
                </thead>
                <tbody>
"""
    for idx, item in enumerate(headers_new):
        html_content += create_field_row(item, "new", idx)
    html_content += """
                </tbody>
            </table>
"""
else:
    html_content += """
            <div class="empty-state"><p>No new headers detected</p></div>
"""
html_content += """
        </div>
        </section>
"""

html_content += f"""
        <!-- Modified Headers -->
        <section id="header-modified" class="section">
        <div class="card full-width">
            <div class="card-header">
                <h2 class="card-title">Modified Headers</h2>
                <span class="badge badge-modified">{len(headers_modified)} items</span>
            </div>
"""
if headers_modified:
    html_content += """
            <table>
                <thead>
                    <tr>
                        <th style="width: 35%;">Header</th>
                        <th style="width: 32%;">Previous Value</th>
                        <th style="width: 33%;">New Value</th>
                    </tr>
                </thead>
                <tbody>
"""
    for idx, item in enumerate(headers_modified):
        html_content += create_field_row(item, "modified", idx)
    html_content += """
                </tbody>
            </table>
"""
else:
    html_content += """
            <div class="empty-state"><p>No modified headers detected</p></div>
"""
html_content += """
        </div>
        </section>
"""

html_content += f"""
        <!-- Removed Headers -->
        <section id="header-removed" class="section">
        <div class="card full-width">
            <div class="card-header">
                <h2 class="card-title">Removed Headers</h2>
                <span class="badge badge-removed">{len(headers_removed)} items</span>
            </div>
"""
if headers_removed:
    html_content += """
            <table>
                <thead>
                    <tr>
                        <th style="width: 40%;">Header</th>
                        <th style="width: 60%;">Removed Value</th>
                    </tr>
                </thead>
                <tbody>
"""
    for idx, item in enumerate(headers_removed):
        html_content += create_field_row(item, "removed", idx)
    html_content += """
                </tbody>
            </table>
"""
else:
    html_content += """
            <div class="empty-state"><p>No removed headers detected</p></div>
"""
html_content += """
        </div>
        </section>
"""

# Removed Fields
html_content += f"""
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
                        <th style="width: 40%;">Field Name</th>
                        <th style="width: 60%;">Removed Value</th>
                    </tr>
                </thead>
                <tbody>
"""
    for idx, item in enumerate(removed_fields):
        html_content += create_field_row(item, "removed", idx)
    
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
# (1) Add new helper to render a field-based comparison table for all change types

def render_compare_field_table(new_fields, modified_fields, removed_fields):
    html_sections = []
    if new_fields:
        html_sections.append('<h3 style="color: #10b981; margin-top:16px;">New Fields</h3>')
        html_sections.append('<table><thead><tr><th style="width: 40%;">Field Name</th><th style="width: 60%;">New Value</th></tr></thead><tbody>')
        for idx, item in enumerate(new_fields):
            html_sections.append(create_field_row(item, "new", idx))
        html_sections.append('</tbody></table>')
    if modified_fields:
        html_sections.append('<h3 style="color: #FF9800; margin-top:22px;">Modified Fields</h3>')
        html_sections.append('<table><thead><tr><th style="width: 35%;">Field Name</th><th style="width: 32%;">Old Value</th><th style="width: 33%;">New Value</th></tr></thead><tbody>')
        for idx, item in enumerate(modified_fields):
            html_sections.append(create_field_row(item, "modified", idx))
        html_sections.append('</tbody></table>')
    if removed_fields:
        html_sections.append('<h3 style="color: #F44336; margin-top:22px;">Removed Fields</h3>')
        html_sections.append('<table><thead><tr><th style="width: 40%;">Field Name</th><th style="width: 60%;">Removed Value</th></tr></thead><tbody>')
        for idx, item in enumerate(removed_fields):
            html_sections.append(create_field_row(item, "removed", idx))
        html_sections.append('</tbody></table>')
    if not html_sections:
        return '<div class="empty-state"><p>No differences found.</p></div>'
    return '\n'.join(html_sections)

# NEW FUNCTION: render_side_by_side_field_diff_table

def render_side_by_side_field_diff_table(new_fields, modified_fields, removed_fields):
    html_rows = []
    html_rows.append('<table class="diff-table"><thead><tr><th>Field Name / Path</th><th>Old Value</th><th>New Value</th></tr></thead><tbody>')
    idx = 0
    for item in modified_fields:
        field_name = html.escape(item.get('Field', ''), quote=True)
        section = html.escape(item.get('Section', ''), quote=True)
        path = f"<div style='font-size:0.9em;color:#888;'>{section}</div>" if section else ''
        html_rows.append(f'<tr class="modified-row"><td><b>{field_name}</b>{path}</td><td class="diff-del">{html.escape(item.get("Old Value", ""), quote=True)}</td><td class="diff-add">{html.escape(item.get("New Value", ""), quote=True)}</td></tr>')
        idx += 1
    for item in new_fields:
        field_name = html.escape(item.get('Field', ''), quote=True)
        section = html.escape(item.get('Section', ''), quote=True)
        path = f"<div style='font-size:0.9em;color:#888;'>{section}</div>" if section else ''
        html_rows.append(f'<tr class="new-row"><td><b>{field_name}</b>{path}</td><td class="diff-empty"></td><td class="diff-add">{html.escape(item.get("Value", ""), quote=True)}</td></tr>')
        idx += 1
    for item in removed_fields:
        field_name = html.escape(item.get('Field', ''), quote=True)
        section = html.escape(item.get('Section', ''), quote=True)
        path = f"<div style='font-size:0.9em;color:#888;'>{section}</div>" if section else ''
        html_rows.append(f'<tr class="removed-row"><td><b>{field_name}</b>{path}</td><td class="diff-del">{html.escape(item.get("Value", ""), quote=True)}</td><td class="diff-empty"></td></tr>')
        idx += 1
    if idx == 0:
        html_rows.append('<tr><td colspan="3" class="diff-ctx" style="text-align:center;color:#888;">No differences found.</td></tr>')
    html_rows.append('</tbody></table>')
    return '\n'.join(html_rows)

# NEW FUNCTION: render_json_side_by_side_diff

def parse_deepdiff_paths(deepdiff_dict):
    # Convert DeepDiff string paths (root['a']['b']) to tuple paths ('a','b')
    added = set()
    removed = set()
    changed = set()
    changed_old = {}  # path: old_value
    changed_new = {}  # path: new_value
    if 'dictionary_item_added' in deepdiff_dict:
        for path in deepdiff_dict['dictionary_item_added']:
            parts = tuple([p for p in re.findall(r"\['([^']+)'\]", path)])
            added.add(parts)
    if 'dictionary_item_removed' in deepdiff_dict:
        for path in deepdiff_dict['dictionary_item_removed']:
            parts = tuple([p for p in re.findall(r"\['([^']+)'\]", path)])
            removed.add(parts)
    if 'values_changed' in deepdiff_dict:
        for path, value in deepdiff_dict['values_changed'].items():
            parts = tuple([p for p in re.findall(r"\['([^']+)'\]", path)])
            changed.add(parts)
            changed_old[parts] = value.get('old_value')
            changed_new[parts] = value.get('new_value')
    return added, removed, changed, changed_old, changed_new

def render_json_with_highlight(obj, highlights, highlight_vals, context='base'):
    # highlights: dict of path -> type: 'add', 'remove', 'change'
    # highlight_vals: dict of path -> override value for 'change'
    # context: 'base' or 'current' (affects which changes/values to display)
    def _render(val, path=()):
        if isinstance(val, dict):
            s = '{\n'
            for ix, (k, v) in enumerate(val.items()):
                new_path = path + (k,)
                comma = ',' if (ix+1)<len(val) else ''
                tag = highlights.get(new_path)
                highlight_class = ''
                value_override = None
                if tag == 'add' and context == 'current':
                    highlight_class = 'diff-add'
                elif tag == 'remove' and context == 'base':
                    highlight_class = 'diff-del'
                elif tag == 'change':
                    highlight_class = 'diff-mod'
                    if context == 'base':
                        value_override = highlight_vals['old'].get(new_path)
                    else:
                        value_override = highlight_vals['new'].get(new_path)
                else:
                    highlight_class = ''
                # Field key
                key_html = f'  "{k}": '
                # Value (recursively)
                if value_override is not None:
                    # Pretty render complex overrides (dict/list) to match View Responses formatting
                    if isinstance(value_override, (dict, list)):
                        val_html = _render(value_override, new_path)
                    else:
                        val_html = json.dumps(value_override, ensure_ascii=False)
                else:
                    val_html = _render(v, new_path)
                content = key_html + val_html + comma
                if highlight_class:
                    content = f'<span class="{highlight_class}">{content}</span>'
                s += content + '\n'
            s += '}'
            return s
        elif isinstance(val, list):
            s = '[\n'
            for ix, v in enumerate(val):
                new_path = path + (ix,)
                val_html = _render(v, new_path)
                comma = ',' if (ix+1)<len(val) else ''
                tag = highlights.get(new_path)
                highlight_class = ''
                if tag == 'add' and context == 'current':
                    highlight_class = 'diff-add'
                elif tag == 'remove' and context == 'base':
                    highlight_class = 'diff-del'
                elif tag == 'change':
                    highlight_class = 'diff-mod'
                else:
                    highlight_class = ''
                if highlight_class:
                    val_html = f'<span class="{highlight_class}">{val_html}</span>'
                s += '  ' + val_html + comma + '\n'
            s += ']'            
            return s
        else:
            return json.dumps(val, ensure_ascii=False)
    return _render(obj)

def render_json_side_by_side_diff(base_obj, current_obj, diff_data):
    def str_path_to_tuple(path_str):
        if not path_str:
            return tuple()
        parts = [p for p in path_str.split('/') if p != '']
        # Keep as strings; list indices are unlikely here and safe as strings for highlighting
        return tuple(parts)

    MISSING = object()

    def get_value_at_path(obj, path_tuple):
        cur = obj
        for key in path_tuple:
            try:
                cur = cur[key]
            except Exception:
                return MISSING
        return cur

    # Prefer our normalized field_changes to classify add/remove/change consistently
    highlights = {}
    changed_old = {}
    changed_new = {}
    try:
        for full_path in field_changes.keys():
            path_tuple = str_path_to_tuple(full_path)
            base_val = get_value_at_path(base_obj, path_tuple)
            curr_val = get_value_at_path(current_obj, path_tuple)
            base_missing = (base_val is MISSING)
            curr_missing = (curr_val is MISSING)
            if base_missing and not curr_missing:
                highlights[path_tuple] = 'add'
            elif curr_missing and not base_missing:
                highlights[path_tuple] = 'remove'
            else:
                if base_val != curr_val:
                    highlights[path_tuple] = 'change'
                    changed_old[path_tuple] = base_val
                    changed_new[path_tuple] = curr_val
    except Exception:
        # Fallback to DeepDiff parsing if something goes wrong
        added, removed, changed, dd_old, dd_new = parse_deepdiff_paths(diff_data)
        for path in added:
            highlights[path] = 'add'
        for path in removed:
            highlights[path] = 'remove'
        for path in changed:
            highlights[path] = 'change'
        changed_old = dd_old
        changed_new = dd_new

    highlight_vals = {'old': changed_old, 'new': changed_new}
    # Tables
    left = render_json_with_highlight(base_obj, highlights, highlight_vals, 'base')
    right = render_json_with_highlight(current_obj, highlights, highlight_vals, 'current')
    
    # Main HTML table
    out = []
    out.append('<style>.diff-table-json td {vertical-align:top; background:white;} .diff-add {background: #d1fae5;} .diff-del {background: #fee2e2;} .diff-mod {background: #dbeafe !important; border-left: 4px solid #3b82f6 !important;} .full-path-label { color: #b91c1c; font-size: 0.95em; font-weight: bold; font-family: monospace; margin-right: 6px; } .full-path-mono { font-family: monospace; color: #374151; font-size: 0.97em; }</style>')
    out.append('<table class="diff-table-json" style="width:100%;table-layout:fixed"><tr>')
    out.append('<td style="width:50%;border-right:1.5px solid #dddddd;padding:0 6px"><div style="font-weight:bold;padding-bottom:4px;">Old Response</div><pre style="padding:0;margin:0;overflow-x:auto;font-size:1em;">'+left+'</pre></td>')
    out.append('<td style="width:50%;padding:0 6px"><div style="font-weight:bold;padding-bottom:4px;">New Response</div><pre style="padding:0;margin:0;overflow-x:auto;font-size:1em;">'+right+'</pre></td>')
    out.append('</tr></table>')
    return ''.join(out)

# Replace original field diff rendering in Compare Responses section:
html_content += """
        <!-- Compare Responses Section (Visual Side-by-Side JSON Diff + Download) -->
        <section id="compare" class="section">
            <div class="card full-width">
                <div class="card-header" style="display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;">
                    <div style="display:flex; flex-direction:column; gap:8px;">
                        <h2 class="card-title">Compare Responses</h2>
                        <div class="legend" style="display:flex; align-items:center; gap: 12px; font-size: 0.9em; color:#475569;">
                            <div class="legend-item" style="display:flex; align-items:center; gap:6px;">
                                <span class="swatch" style="display:inline-block; width:14px; height:14px; background:#d1fae5; border-left:4px solid #21c65a; border-radius:3px;"></span>
                                <span>Added</span>
                            </div>
                            <div class="legend-item" style="display:flex; align-items:center; gap:6px;">
                                <span class="swatch" style="display:inline-block; width:14px; height:14px; background:#fee2e2; border-left:4px solid #f95b5b; border-radius:3px;"></span>
                                <span>Removed</span>
                            </div>
                            <div class="legend-item" style="display:flex; align-items:center; gap:6px;">
                                <span class="swatch" style="display:inline-block; width:14px; height:14px; background:#dbeafe; border-left:4px solid #3b82f6; border-radius:3px;"></span>
                                <span>Modified</span>
                            </div>
                        </div>
                    </div>
                    <button id="downloadDiffBtn" class="download-btn"><i class="fa fa-download"></i></button>
                </div>
                <div style='overflow-x:auto;padding:0 5px 15px 5px;'>
"""
# Call the new renderer with parsed objects and diff:
try:
  base_json_obj = json.loads(base_payload)
  current_json_obj = json.loads(current_payload)
  html_content += render_json_side_by_side_diff(base_json_obj, current_json_obj, diff_data)
except Exception as e:
    # Fallback for XML/text: show side-by-side text diff, plus path-based field changes
    html_content += """
      <div style=\"margin-bottom:16px;\">"""
    html_content += build_diff_table(diff)
    html_content += """</div>"""
    html_content += render_side_by_side_field_diff_table(new_fields, modified_fields, removed_fields)
html_content += """
                </div>
            </div>
        </section>
"""
html_content += """
        <!-- View Payloads Section -->
        <section id="payloads" class="section">
            <div class="card full-width">
                <div class="card-header">
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
                <div style='padding-top:18px;text-align:right;'>
                    <button id='compareBtn' style="background:var(--gradient-warning);color:#fff;padding:10px 20px;border:none;border-radius:7px;cursor:pointer;font-weight:600;font-size:1em;box-shadow:0 2px 10px rgba(102,126,234,0.06);">Compare Responses</button>
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
        const layoutEl = document.querySelector('.layout');
        const sidebarEl = document.querySelector('.sidebar');
        
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

        // Header dropdown toggle
        const headerNav = document.getElementById('nav-header');
        const headerSubmenu = document.getElementById('nav-header-submenu');
        if (headerNav && headerSubmenu) {
          headerNav.addEventListener('click', function(e) {
            // Toggle submenu open/close, but still allow navigation to #header if desired
            headerSubmenu.classList.toggle('show');
            headerNav.classList.toggle('expanded');
          });
          // Submenu item clicks should also update active state
          headerSubmenu.querySelectorAll('a').forEach(item => {
            item.addEventListener('click', function(e) {
              const href = this.getAttribute('href') || '#header';
              const sectionId = href.substring(1);
              showSection(sectionId);
              history.replaceState(null, '', href);
            });
          });
        }

        // Sidebar collapse toggle on logo
        const brandIconEl = document.querySelector('.brand-icon');
        if (brandIconEl && layoutEl && sidebarEl) {
          brandIconEl.addEventListener('click', function(e) {
            e.stopPropagation();
            sidebarEl.classList.toggle('collapsed');
            layoutEl.classList.toggle('collapsed');
            this.title = sidebarEl.classList.contains('collapsed') ? 'Expand sidebar' : 'Collapse sidebar';
            const icon = this.querySelector('i');
            if (icon) {
              if (sidebarEl.classList.contains('collapsed')) {
                icon.classList.remove('fa-bars');
                icon.classList.add('fa-angles-right');
              } else {
                icon.classList.add('fa-bars');
                icon.classList.remove('fa-angles-right');
              }
            }
          });
        }
        
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

        const compareBtn = document.getElementById('compareBtn');
        if(compareBtn) {
          compareBtn.addEventListener('click', function() {
            showSection('compare');
            history.replaceState(null, '', '#compare');
          });
        }
        
        
        // ========== CONSOLIDATED: Toggle Field Path for All Row Types ==========
        function setupRowToggle(rowSelector) {
          const rows = document.querySelectorAll(rowSelector);
          
          rows.forEach(row => {
            row.addEventListener('click', function(e) {
              // Don't trigger if clicking on a value span
              if (e.target.classList.contains('value')) return;
              
              const rowId = this.getAttribute('data-row-id');
              const pathElement = document.getElementById('row-path-' + rowId);
              
              // Get the row type class (e.g., 'new-row', 'modified-row', 'removed-row')
              const rowClass = this.classList[0];
              
              // Close all other path rows within the same table body
              const tbody = this.closest('tbody');
              if (tbody) {
                tbody.querySelectorAll('.field-path-row.visible').forEach(tag => {
                  if (tag.id !== 'row-path-' + rowId) {
                    tag.classList.remove('visible');
                  }
                });
              }
              
              // Remove active class from all rows in this section
              rows.forEach(r => r.classList.remove('active'));
              
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
        }

        // Apply to all three row types
        setupRowToggle('.new-row');
        setupRowToggle('.removed-row');
        setupRowToggle('.modified-row');
        
      })();
    </script>
    """
diff_json_js = json.dumps(diff_data) if is_json_format else 'null'
html_content += f"""
    <script>window._dashboardDiffData = {diff_json_js};</script>
"""
html_content += """
    <script>
      // ========== NATIVE BROWSER SAVE DIALOG ==========
      document.getElementById('downloadDiffBtn').addEventListener('click', async function() {
        const section = document.querySelector('#compare .card.full-width');
        if (!section) return;
        
        const clone = section.cloneNode(true);
        const btn = clone.querySelector('.download-btn');
        if (btn) btn.remove();
        
        const htmlDoc = '<!DOCTYPE html>\\n' +
          '<html>\\n' +
          '<head>\\n' +
          '  <meta charset="UTF-8">\\n' +
          '  <title>Compare Responses - Diff Report</title>\\n' +
          '  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">\\n' +
          '  <style>\\n' +
          '    body { font-family: \\'Inter\\', sans-serif; background: #f7f6fa; margin: 0; padding: 32px; }\\n' +
          '    .card { background: #fff; border-radius: 16px; padding: 24px; max-width: 1100px; margin: 0 auto; box-shadow: 0 2px 12px rgba(90,90,160,0.07); }\\n' +
          '    .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 16px; border-bottom: 2px solid #f0f0f0; }\\n' +
          '    .card-title { font-size: 2em; font-weight: 700; margin-bottom: 16px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }\\n' +
          '    .diff-table-json { width: 100%; table-layout: fixed; border-spacing: 0; border-collapse: collapse; }\\n' +
          '    .diff-table-json td { vertical-align: top; background: white; padding: 8px; }\\n' +
          '    .diff-add { background: #d1fae5; }\\n' +
          '    .diff-del { background: #fee2e2; }\\n' +
          '    .diff-mod { background: #dbeafe !important; border-left: 4px solid #3b82f6 !important; }\\n' +
          '    pre { font-family: \\'Courier New\\', monospace; margin: 0; overflow-x: auto; font-size: 0.99em; padding: 0; }\\n' +
          '  </style>\\n' +
          '</head>\\n' +
          '<body>' + clone.outerHTML + '</body>\\n' +
          '</html>';
        
        const blob = new Blob([htmlDoc], { type: 'text/html' });
        
        // ========== CHECK IF FILE SYSTEM ACCESS API IS SUPPORTED ==========
        if ('showSaveFilePicker' in window) {
          try {
            // Modern browsers - shows native file picker
            const handle = await window.showSaveFilePicker({
              suggestedName: 'compare-responses-' + new Date().toISOString().slice(0,10) + '.html',
              types: [{
                description: 'HTML Files',
                accept: { 'text/html': ['.html'] }
              }]
            });
            
            const writable = await handle.createWritable();
            await writable.write(blob);
            await writable.close();
            
            alert('✅ File saved successfully!');
          } catch (err) {
            if (err.name !== 'AbortError') {
              console.error('Save failed:', err);
              fallbackDownload(blob);
            }
          }
        } else {
          // Fallback for older browsers
          fallbackDownload(blob);
        }
      });

      // Fallback download method
      function fallbackDownload(blob) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'compare-responses-' + new Date().toISOString().slice(0,10) + '.html';
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 500);
      }
      </script>
 </body>
</html>
"""

# Save HTML file into results directory
try:
    logger.info(f"Writing HTML file: {dashboard_html}")
    with open(dashboard_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logger.info(f"HTML file written successfully ({len(html_content)} bytes)")
except Exception as e:
    logger.error(f"Failed to write HTML file: {e}")
    print(f"Error writing HTML file: {e}")
    sys.exit(1)

logger.info("Dashboard generation completed successfully")
print("\n" + "="*60)
print("✅ Dashboard generated successfully!")
print("="*60)
print("\nFiles created:")
print(f"   📄 {dashboard_html}")
print(f"   🎨 {dashboard_css}")
print(f"\n📊 Summary:")
print(f"   • Total changes: {total_changes}")
print(f"   • New fields: {len(new_fields)}")
print(f"   • Modified fields: {len(modified_fields)}")
print(f"   • Removed fields: {len(removed_fields)}")
print("\n🌐 Open 'results/diff_dashboard.html' in your browser to view the dashboard")
print("="*60 + "\n")
