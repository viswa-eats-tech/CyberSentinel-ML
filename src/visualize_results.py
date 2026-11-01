from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

METRICS = [
    ("accuracy", "Accuracy"),
    ("precision_attack", "Precision attack"),
    ("recall_attack", "Recall attack"),
    ("f1_attack", "F1 attack"),
    ("roc_auc", "ROC-AUC"),
]

MODEL_LABELS = {
    "random_forest": "Random Forest",
    "bagging": "Bagging Classifier",
    "gradient_boosting": "Gradient Boosting",
}


def main() -> None:
    args = parse_args()
    results = json.loads(args.results_json.read_text(encoding="utf-8"))
    args.output_html.parent.mkdir(parents=True, exist_ok=True)
    args.output_html.write_text(render_dashboard(results), encoding="utf-8")
    print(f"Dashboard written to {args.output_html}")


def parse_args() -> argparse.Namespace:
    root = project_root()
    parser = argparse.ArgumentParser(
        description="Generate an HTML dashboard for training results."
    )
    parser.add_argument(
        "--results-json",
        type=Path,
        default=root / "reports" / "training_results.json",
        help="Path to training_results.json.",
    )
    parser.add_argument(
        "--output-html",
        type=Path,
        default=root / "reports" / "training_dashboard.html",
        help="Path where the HTML dashboard is written.",
    )
    return parser.parse_args()


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def render_dashboard(results: dict[str, Any]) -> str:
    if "scenarios" in results:
        return render_robustness_dashboard(results)

    model_cards = "\n".join(
        render_model_card(model_name, metrics)
        for model_name, metrics in results["models"].items()
    )

    comparison_rows = "\n".join(
        [
            render_comparison_row(results["models"], "threshold", "Decision threshold"),
            *[
                render_comparison_row(results["models"], metric_key, label)
                for metric_key, label in METRICS
            ],
        ]
    )

    generated_at = html.escape(results["generated_at"])
    categorical_features = ", ".join(results["categorical_features"])
    primary_model = results["models"].get("random_forest", {})
    threshold_panel = render_threshold_selection(results)
    primary_threshold = results.get("decision_threshold")
    primary_name = (
        "random_forest" if "random_forest" in results["models"] else next(iter(results["models"]))
    )
    primary_label = MODEL_LABELS.get(primary_name, primary_name)
    comparison_headers = "".join(
        f"<th>{html.escape(MODEL_LABELS.get(name, name))}</th>"
        for name in results["models"]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Netshield Training Results</title>
  <style>
    :root {{
      --bg: #f3f5f8;
      --surface: #ffffff;
      --surface-soft: #f8fafc;
      --text: #172033;
      --muted: #647084;
      --border: #d8dee8;
      --border-strong: #b8c2d2;
      --green: #16845b;
      --blue: #2b65c8;
      --red: #c83d3d;
      --amber: #b86b00;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, Helvetica, sans-serif;
      line-height: 1.45;
    }}

    main {{
      width: min(1240px, calc(100vw - 40px));
      margin: 26px auto 48px;
    }}

    header {{
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 18px;
      align-items: end;
      margin-bottom: 18px;
    }}

    h1 {{
      margin: 0 0 5px;
      font-size: 28px;
      font-weight: 750;
      letter-spacing: 0;
    }}

    h2 {{
      margin: 0 0 12px;
      font-size: 17px;
      font-weight: 700;
      letter-spacing: 0;
    }}

    h3 {{
      margin: 0 0 12px;
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0;
    }}

    .muted {{ color: var(--muted); }}
    .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      width: fit-content;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--surface);
      color: var(--muted);
      padding: 7px 10px;
      font-size: 13px;
      font-weight: 650;
      white-space: nowrap;
    }}

    .dot {{
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--green);
    }}

    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 1px;
      border: 1px solid var(--border);
      background: var(--border);
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 16px;
    }}

    .metric-box {{
      background: var(--surface);
      padding: 14px 16px;
      min-height: 86px;
    }}

    .panel {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
    }}

    .metric-box span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .03em;
    }}

    .metric-box strong {{
      display: block;
      font-size: 23px;
      font-weight: 760;
      margin-top: 4px;
    }}

    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      margin-bottom: 18px;
    }}

    .metric-row {{
      display: grid;
      grid-template-columns: 142px 1fr 58px;
      gap: 10px;
      align-items: center;
      margin: 9px 0;
      font-size: 14px;
    }}

    .bar {{
      height: 8px;
      background: #e6eaf0;
      border-radius: 999px;
      overflow: hidden;
    }}

    .fill {{
      height: 100%;
      background: var(--blue);
      border-radius: 999px;
    }}

    .fill.good {{ background: var(--green); }}

    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}

    th, td {{
      padding: 9px 8px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: middle;
    }}

    th {{
      color: var(--muted);
      font-weight: 600;
    }}

    tbody tr:last-child td {{
      border-bottom: 0;
    }}

    .matrix {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 12px;
    }}

    .matrix-cell {{
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 11px 12px;
      background: var(--surface-soft);
    }}

    .matrix-cell strong {{
      display: block;
      font-size: 21px;
      margin-bottom: 2px;
    }}

    .model-note {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      background: #f7fbf8;
      border: 1px solid #c7dfd2;
      border-radius: 8px;
      padding: 13px 15px;
      margin-bottom: 16px;
      font-size: 14px;
    }}

    .threshold-note {{
      background: #f8fbff;
      border-color: #c9d9f4;
    }}

    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 1px;
      border: 1px solid var(--border);
      background: var(--border);
      border-radius: 8px;
      overflow: hidden;
      margin-top: 12px;
    }}

    .detail-item {{
      background: var(--surface-soft);
      padding: 12px 13px;
    }}

    .detail-item span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: .03em;
      margin-bottom: 4px;
    }}

    .detail-item strong {{
      display: block;
      font-size: 18px;
      font-weight: 740;
    }}

    .positive {{ color: var(--green); }}
    .negative {{ color: var(--red); }}
    .warning {{ color: var(--amber); }}

    @media (max-width: 860px) {{
      main {{ width: min(100vw - 24px, 720px); }}
      header {{ grid-template-columns: 1fr; align-items: start; }}
      .summary, .grid {{ grid-template-columns: 1fr; }}
      .detail-grid {{ grid-template-columns: 1fr; }}
      .metric-row {{ grid-template-columns: 130px 1fr 52px; }}
      .model-note {{ display: block; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Model Evaluation Report</h1>
        <div class="muted">UNSW-NB15 binary intrusion detection - generated <span class="mono">{generated_at}</span></div>
      </div>
      <div class="badge"><span class="dot"></span> Primary model: {html.escape(primary_label)}</div>
    </header>

    <section class="summary">
      <div class="metric-box"><span>Training rows</span><strong>{results["train_rows"]:,}</strong></div>
      <div class="metric-box"><span>Testing rows</span><strong>{results["test_rows"]:,}</strong></div>
      <div class="metric-box"><span>Input features</span><strong>{len(results["numeric_features"]) + len(results["categorical_features"])}</strong></div>
      <div class="metric-box"><span>RF threshold</span><strong>{format_metric(primary_threshold)}</strong></div>
      <div class="metric-box"><span>Attack recall</span><strong>{format_metric(primary_model.get("recall_attack"))}</strong></div>
      <div class="metric-box"><span>F1 attack</span><strong>{format_metric(primary_model.get("f1_attack"))}</strong></div>
    </section>

    <section class="model-note">
      <div><strong>Feature set:</strong> {len(results["numeric_features"])} numeric fields plus categorical protocol context (<span class="mono">{html.escape(categorical_features)}</span>).</div>
      <div class="muted">Excluded from training: <span class="mono">id</span>, <span class="mono">attack_cat</span></div>
    </section>

    {threshold_panel}

    <section class="panel" style="margin-bottom: 18px;">
      <h2>Model comparison on held-out test split</h2>
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            {comparison_headers}
          </tr>
        </thead>
        <tbody>
          {comparison_rows}
        </tbody>
      </table>
    </section>

    <section class="grid">
      {model_cards}
    </section>
  </main>
</body>
</html>
"""


def render_robustness_dashboard(results: dict[str, Any]) -> str:
    scenario_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(row['scenario']))}</td>"
        f"<td>{format_percent(row['review_rate'])}</td>"
        f"<td>{float(row['total_baseline_errors']):.1f}</td>"
        f"<td>{float(row['uncertainty_errors_caught']):.1f}</td>"
        f"<td>{float(row['random_mean_errors_caught']):.1f}</td>"
        f"<td>{float(row['errors_caught_lift_vs_random_mean']):+.1f}</td>"
        f"<td>{int(row.get('seeds_beating_random', 0))}/{int(row.get('training_seed_count', 1))}</td>"
        f"<td>{format_percent(row.get('fdr_q_value', row.get('randomization_p_value')))}</td>"
        "</tr>"
        for row in results.get("scenarios", [])
    )
    category_rows = "\n".join(
        "<tr>"
        f"<td>{html.escape(str(row['scenario']))}</td>"
        f"<td>{html.escape(str(row['attack_category']))}</td>"
        f"<td>{float(row['rows']):.1f}</td>"
        f"<td>{float(row['baseline_errors']):.1f}</td>"
        f"<td>{float(row['uncertainty_errors_caught']):.1f}</td>"
        f"<td>{float(row['random_mean_errors_caught']):.2f}</td>"
        f"<td>{float(row['errors_caught_lift_vs_random_mean']):+.2f}</td>"
        f"<td>{format_percent(row['uncertainty_error_capture_rate'])}</td>"
        f"<td>{int(row.get('seeds_beating_random', 0))}/{int(row.get('training_seed_count', 1))}</td>"
        f"<td>{format_percent(row.get('fdr_q_value', row.get('randomization_p_value')))}</td>"
        "</tr>"
        for row in results.get("attack_category_results", [])
    )
    generated_at = html.escape(str(results.get("generated_at", "unknown")))
    protocol = results.get("protocol", {})
    budget = format_percent(protocol.get("review_budget_target", 0))
    repeats = int(protocol.get("random_review_repeats", 0))
    test_rows = int(protocol.get("official_test_rows", 0))
    category_section = (
        f"""<section><h2>Attack category results</h2>
<div class="table-wrap"><table><thead><tr>
<th>Scenario</th><th>Category</th><th>Rows</th><th>Baseline errors</th>
<th>Errors caught by uncertainty</th><th>Random mean</th><th>Lift</th>
<th>Category error capture</th><th>Seeds ahead</th><th>Adjusted q</th>
</tr></thead><tbody>{category_rows}</tbody></table></div></section>"""
        if category_rows
        else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Feature outage and alert triage experiment</title>
<style>
body {{ margin: 0; background: #f3f5f8; color: #172033;
  font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; }}
main {{ max-width: 1200px; margin: 32px auto; padding: 0 20px; }}
section {{ background: white; border: 1px solid #d8dee8; border-radius: 10px;
  margin: 18px 0; padding: 18px; }}
h1 {{ margin-bottom: 4px; }} .muted {{ color: #647084; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; white-space: nowrap; }}
th, td {{ text-align: left; border-bottom: 1px solid #e5e9ef; padding: 10px; }}
th {{ background: #f8fafc; }}
</style></head><body><main>
<h1>Feature outage and alert triage</h1>
<p class="muted">Generated {generated_at}. Review budget: {budget}; random baseline:
{repeats} same-size draws per scenario and seed. Test rows: {test_rows}; training
seeds: {int(protocol.get('training_seed_count', 1))}. Outages replace all values in
one feature group with missing values. Seed-level sign tests are paired; q-values
use Benjamini-Hochberg across scenario and category comparisons.</p>
<section><h2>Scenario summary</h2><div class="table-wrap"><table>
<thead><tr><th>Scenario</th><th>Review rate</th><th>Baseline errors</th>
<th>Uncertainty errors caught</th><th>Random mean</th><th>Lift (#)</th>
<th>Seeds ahead</th><th>Adjusted q</th></tr></thead>
<tbody>{scenario_rows}</tbody></table></div></section>
{category_section}
</main></body></html>"""


def format_percent(value: Any) -> str:
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "n/a"


def render_threshold_selection(results: dict[str, Any]) -> str:
    selection = results.get("threshold_selection", {}).get("random_forest")
    random_forest = results.get("models", {}).get("random_forest", {})
    threshold = random_forest.get("threshold", results.get("decision_threshold"))

    if not selection:
        return f"""<section class="panel threshold-note" style="margin-bottom: 18px;">
      <h2>Random Forest operating threshold</h2>
      <div class="muted">The API uses a fixed Random Forest threshold configured during training. At this operating point, the model keeps attack recall high while reducing false positives compared with a more aggressive high-recall threshold.</div>
      <div class="detail-grid">
        <div class="detail-item"><span>Mode</span><strong>fixed threshold</strong></div>
        <div class="detail-item"><span>Threshold</span><strong>{format_metric(threshold)}</strong></div>
        <div class="detail-item"><span>Test recall</span><strong>{format_metric(random_forest.get("recall_attack"))}</strong></div>
        <div class="detail-item"><span>Test F1</span><strong>{format_metric(random_forest.get("f1_attack"))}</strong></div>
      </div>
    </section>"""

    selected = selection["selected_metrics"]
    method = html.escape(selection["method"].replace("_", " "))
    rule = html.escape(selection["selection_rule"])

    return f"""<section class="panel threshold-note" style="margin-bottom: 18px;">
      <h2>Random Forest threshold selection</h2>
      <div class="muted">The threshold was selected on a validation split from the training set. The held-out test set below is used only for final reporting.</div>
      <div class="detail-grid">
        <div class="detail-item"><span>Method</span><strong>{method}</strong></div>
        <div class="detail-item"><span>Selected threshold</span><strong>{format_metric(selection["selected_threshold"])}</strong></div>
        <div class="detail-item"><span>Validation recall</span><strong>{format_metric(selected["recall_attack"])}</strong></div>
        <div class="detail-item"><span>Validation F1</span><strong>{format_metric(selected["f1_attack"])}</strong></div>
      </div>
      <p class="muted" style="margin: 12px 0 0;">Selection rule: {rule}.</p>
    </section>"""


def render_model_card(model_name: str, metrics: dict[str, Any]) -> str:
    label = html.escape(MODEL_LABELS.get(model_name, model_name))
    metric_rows = "\n".join(
        render_metric_bar(metric_key, label, metrics[metric_key])
        for metric_key, label in METRICS
        if metric_key in metrics
    )
    matrix = metrics["confusion_matrix"]

    return f"""<article class="panel">
  <h3>{label}</h3>
  {metric_rows}
  <h3 style="margin-top: 16px;">Confusion matrix</h3>
  <div class="matrix">
    <div class="matrix-cell"><strong class="positive">{matrix["true_positive"]:,}</strong><span>Attack detected</span></div>
    <div class="matrix-cell"><strong class="warning">{matrix["false_positive"]:,}</strong><span>Normal flagged</span></div>
    <div class="matrix-cell"><strong>{matrix["true_negative"]:,}</strong><span>Normal allowed</span></div>
    <div class="matrix-cell"><strong class="negative">{matrix["false_negative"]:,}</strong><span>Attack missed</span></div>
  </div>
</article>"""


def render_metric_bar(metric_key: str, label: str, value: float | None) -> str:
    if value is None:
        width = 0
        formatted = "n/a"
    else:
        width = max(0, min(100, value * 100))
        formatted = format_metric(value)

    fill_class = (
        "fill good"
        if metric_key in {"recall_attack", "f1_attack", "roc_auc"}
        else "fill"
    )
    return (
        f'<div class="metric-row">'
        f"<span>{html.escape(label)}</span>"
        f'<div class="bar"><div class="{fill_class}" style="width: {width:.2f}%;"></div></div>'
        f"<strong>{formatted}</strong>"
        f"</div>"
    )


def render_comparison_row(
    models: dict[str, dict[str, Any]],
    metric_key: str,
    label: str,
) -> str:
    values = "".join(
        f"<td>{format_metric(metrics.get(metric_key))}</td>"
        for metrics in models.values()
    )
    return (
        "<tr>"
        f"<td>{html.escape(label)}</td>"
        f"{values}"
        "</tr>"
    )


def format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


if __name__ == "__main__":
    main()
