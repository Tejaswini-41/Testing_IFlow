# 🚀 CPI Response Compare — Automated iFlow Validation via GitHub Actions

<p align="center">
  <img src="https://img.shields.io/github/actions/workflow/status/tejaswini-41/Testing_IFlow/cicd.yml?branch=main&style=for-the-badge" alt="Build Status" />
  <img src="https://img.shields.io/github/license/tejaswini-41/Testing_IFlow?style=for-the-badge" alt="License" />
  <img src="https://img.shields.io/github/last-commit/tejaswini-41/Testing_IFlow?style=for-the-badge" alt="Last Commit" />
</p>

---

## 📘 Overview

This repository automates the **CPI iFlow Response Comparison** process using **GitHub Actions**.  
It compares two CPI endpoints — typically the *base (old)* and *current (new)* versions — by:
- Sending identical payloads to both.
- Capturing responses (headers + body).
- Comparing them.
- Generating a detailed HTML **Diff Dashboard** for visual inspection.

All of this happens **automatically in CI/CD**, with a shareable dashboard link published in GitHub Pages.

---

## ⚙️ Workflow Summary

### 🔹 Trigger
Manually via **Workflow Dispatch** in GitHub Actions.

### 🔹 Steps
1. **Checkout Code**
2. **Set Up Python Environment**
3. **Fetch OAuth Token / Authenticate**
4. **Hit Both CPI iFlow Endpoints**
5. **Save Responses**
6. **Compare Headers and Body**
7. **Generate HTML Diff Dashboard**
8. **Publish Dashboard to GitHub Pages**
9. **Provide Dashboard Link in Logs**

---

## 🧩 Inputs (Workflow Parameters)

| Input Name | Description | Default |
|-------------|-------------|----------|
| `payload_file` | Payload file name used for both iFlows | `payload.json` |
| `iflow_base_url` | CPI Old Mapping Endpoint URL | — |
| `iflow_current_url` | CPI New Mapping Endpoint URL | — |

---

## 📂 Repository Structure

Testing_IFlow/
├── .github/
│ └── workflows/
│ └── cicd.yml # Main GitHub Actions pipeline
├── payloads/
│ └── payload.json # Sample payload file
├── results/
│ ├── response_base.txt # Old iFlow response
│ ├── response_current.txt # New iFlow response
│ ├── diff.txt # Comparison summary
│ └── diff_dashboard.html # Visual diff dashboard
├── dashboard.py # Generates the dashboard report
├── compare.py # Compares the two responses
└── README.md # This file 😄


---

## 💻 Running the Workflow

### Option 1 — GitHub UI
1. Navigate to **Actions → CPI Response Compare**
2. Click **Run workflow**
3. Provide inputs (`payload_file`, URLs)
4. Click **Run**

### Option 2 — API Trigger
You can trigger it programmatically using:
```bash
curl -X POST \
  -H "Authorization: token <YOUR_GITHUB_TOKEN>" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/tejaswini-41/Testing_IFlow/actions/workflows/cicd.yml/dispatches \
  -d '{"ref":"main","inputs":{"payload_file":"payload.json","iflow_base_url":"<OLD_URL>","iflow_current_url":"<NEW_URL>"}}'
```

📊 Output — Diff Dashboard

At the end of the workflow, you will get a clickable dashboard link in the logs like:
👉 Open this link to view the full comparison results directly in your browser.
```
::notice title=Dashboard URL::https://tejaswini-41.github.io/Testing_IFlow/results/diff_dashboard.html
```


🧠 Example Dashboard Preview
<p align="center"> <img src="https://github.com/tejaswini-41/Testing_IFlow/raw/main/docs/demo_dashboard_preview.png" width="700" alt="Dashboard Preview" /> </p>
🛠️ Tech Stack

GitHub Actions — CI/CD automation

Python 3.x — core comparison and report generation

Plotly — interactive visualization

Pandas — data handling

HTML/CSS — dashboard layout

🧾 License

This project is licensed under the MIT License — see the LICENSE
 file for details.

🌟 Acknowledgments

Special thanks to the Integration Developers community for inspiring this automation.
Maintained by @tejaswini-41
 ✨

<p align="center"> <b>💡 Simplify your CPI testing with automated comparisons and clear visual insights!</b> </p> ```
