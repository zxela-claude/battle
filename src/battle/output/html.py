import json
from dataclasses import asdict
from battle.storage import RunManifest


def manifest_to_html(manifest: RunManifest) -> str:
    data = asdict(manifest)
    data_json = json.dumps(data)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Battle Report — {manifest.run_id}</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 1200px; margin: 40px auto; padding: 0 20px; background: #0f0f0f; color: #e0e0e0; }}
  h1 {{ color: #fff; }}
  .meta {{ color: #888; margin-bottom: 24px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 32px; }}
  th {{ background: #1a1a2e; color: #7eb8f7; padding: 10px 14px; text-align: left; font-size: 13px; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #222; font-size: 14px; }}
  tr:hover td {{ background: #1a1a1a; }}
  .score-high {{ color: #4ade80; font-weight: bold; }}
  .score-mid {{ color: #facc15; font-weight: bold; }}
  .score-low {{ color: #f87171; font-weight: bold; }}
  .plugin {{ font-weight: bold; color: #7eb8f7; }}
  details {{ margin-top: 8px; }}
  summary {{ cursor: pointer; color: #888; font-size: 12px; }}
  pre {{ background: #111; padding: 12px; border-radius: 4px; font-size: 12px; overflow-x: auto; }}
  .cost {{ color: #888; }}
</style>
</head>
<body>
<h1>⚔️ Battle Report</h1>
<div class="meta">
  <strong>Run ID:</strong> {manifest.run_id} &nbsp;|&nbsp;
  <strong>Test:</strong> {manifest.test_name} &nbsp;|&nbsp;
  <strong>Total cost:</strong> ${manifest.total_cost_usd:.3f}
</div>
<table id="results-table">
  <thead>
    <tr>
      <th>Plugin</th><th>Model</th><th>Overall</th>
      <th>AC</th><th>Style</th><th>Quality</th><th>Security</th><th>Bugs</th>
      <th>ESLint Errors</th><th>Cost</th>
    </tr>
  </thead>
  <tbody id="results-body"></tbody>
</table>
<div id="details"></div>
<script>
const data = {data_json};

function scoreClass(s) {{
  if (s >= 8) return 'score-high';
  if (s >= 6) return 'score-mid';
  return 'score-low';
}}

function overall(cell) {{
  const r = cell.rubric;
  return (r.ac_completeness + r.code_style + r.code_quality + r.security + r.bugs) / 5;
}}

// Group by plugin+model
const groups = {{}};
for (const cell of data.cells) {{
  const key = cell.plugin_id + '|' + cell.model;
  if (!groups[key]) groups[key] = [];
  groups[key].push(cell);
}}

function avg(cells, fn) {{
  return cells.reduce((s, c) => s + fn(c), 0) / cells.length;
}}

const tbody = document.getElementById('results-body');
const details = document.getElementById('details');

for (const [key, cells] of Object.entries(groups)) {{
  const [plugin_id, model] = key.split('|');
  const ov = avg(cells, overall);
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="plugin">${{plugin_id}}</td>
    <td>${{model}}</td>
    <td class="${{scoreClass(ov)}}">${{ov.toFixed(1)}}</td>
    <td>${{avg(cells, c => c.rubric.ac_completeness).toFixed(1)}}</td>
    <td>${{avg(cells, c => c.rubric.code_style).toFixed(1)}}</td>
    <td>${{avg(cells, c => c.rubric.code_quality).toFixed(1)}}</td>
    <td>${{avg(cells, c => c.rubric.security).toFixed(1)}}</td>
    <td>${{avg(cells, c => c.rubric.bugs).toFixed(1)}}</td>
    <td>${{Math.round(avg(cells, c => c.static.error_count))}}</td>
    <td class="cost">$${{avg(cells, c => c.cost_usd).toFixed(3)}}</td>
  `;
  tbody.appendChild(tr);

  // Details section
  const section = document.createElement('details');
  section.innerHTML = `<summary>${{plugin_id}} × ${{model}} — ${{cells.length}} run(s)</summary>
    <pre>${{cells.map(c => JSON.stringify(c.rubric, null, 2)).join('\\n---\\n')}}</pre>`;
  details.appendChild(section);
}}
</script>
</body>
</html>"""
