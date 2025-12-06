#!/usr/bin/env python3
"""
STEP-2: Cluster Consolidation Node (Pathway)

✔ Receives cluster batches from NATS
✔ Loads MASTERFILE.csv and enriches each customer
✔ Generates comprehensive analysis with OpenAI
✔ Creates JSON + TXT + PDF reports
✔ Writes summary back to NATS
"""

import os
import json
import traceback
from datetime import datetime
from pathlib import Path

import pathway as pw
from pathway.io.nats import read as nats_read, write as nats_write
from dotenv import load_dotenv

load_dotenv()

# =======================================================
# LOGGING
# =======================================================
CURRENT_DIR = Path(__file__).resolve().parent
LOG_FILE = CURRENT_DIR / "cluster_consolidator.log"

def log(msg: str):
    line = f"[Consolidator] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# =======================================================
# LLM SETUP
# =======================================================
from openai import OpenAI

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","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")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not found in environment")

client = OpenAI(api_key=OPENAI_API_KEY)

# =======================================================
# PATHS & CONFIG
# =======================================================
ROOT = CURRENT_DIR.parent
MASTERFILE_PATH = ROOT / "MASTERFILE.csv"
OUTPUT_DIR = CURRENT_DIR / "output_reports"
os.makedirs(OUTPUT_DIR, exist_ok=True)

NATS_URI = os.getenv("NATS_SERVERS", "nats://127.0.0.1:4222")
INPUT_TOPIC = "reports.cluster.ready"
OUTPUT_TOPIC = "reports.cluster.final"

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")  # Changed to valid model
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))


# =======================================================
# LOAD MASTERFILE
# =======================================================
import pandas as pd

if not MASTERFILE_PATH.exists():
    raise RuntimeError(f"MASTERFILE missing at {MASTERFILE_PATH}")

master_df = pd.read_csv(MASTERFILE_PATH)
master_df.set_index("customer_id", inplace=True)

log(f"Loaded MASTERFILE with {len(master_df)} rows.")


def get_customer_features(cid: str):
    """Return all features for a customer."""
    try:
        return master_df.loc[cid].to_dict()
    except KeyError:
        log(f"⚠ Missing MASTERFILE data for customer: {cid}")
        return {}


# =======================================================
# SCHEMA
# =======================================================
class ClusterBatchSchema(pw.Schema):
    cluster_id: int
    count: int
    customers: str   # JSON string


# =======================================================
# OPENAI ANALYSIS
# =======================================================
def generate_cluster_analysis(payload):
    """Generate comprehensive cluster analysis using OpenAI."""
    
    # Create a concise summary for the LLM
    cluster_summary = {
        "cluster_id": payload["cluster_id"],
        "customer_count": payload["count"],
        "customers": []
    }
    
    for c in payload["customers"]:
        f = c["features"]
        customer_info = {
            "customer_id": c["customer_id"],
            "confidence_score": c["score"],
            "income": f.get("yearly_income", "N/A"),
            "credit_score": f.get("final_credit_score", "N/A"),
            "city_tier": f.get("city_tier", "N/A"),
            "age": f.get("age", "N/A"),
            "employment_type": f.get("employment_type", "N/A"),
            "loan_amount": f.get("loan_amount", "N/A")
        }
        cluster_summary["customers"].append(customer_info)
    
    prompt = f"""You are a financial analyst. Analyze this cluster of customers who are predicted to be eligible for car loans.

Cluster Data:
{json.dumps(cluster_summary, indent=2)}

Provide a comprehensive analysis in the following JSON format (respond ONLY with valid JSON, no other text):

{{
  "cluster_id": {payload["cluster_id"]},
  "count": {payload["count"]},
  "cluster_summary": "Brief overview of this customer cluster (2-3 sentences)",
  "avg_confidence": <average confidence score>,
  "confidence_distribution": {{
    "min": <minimum score>,
    "max": <maximum score>,
    "median": <median score>
  }},
  "prediction_factors": [
    "Key factor 1 that makes these customers good candidates",
    "Key factor 2",
    "Key factor 3"
  ],
  "customer_behavior_patterns": [
    "Pattern 1 observed in customer data",
    "Pattern 2",
    "Pattern 3"
  ],
  "exemplar_insights": [
    "Insight about top customer 1",
    "Insight about top customer 2"
  ],
  "recommendations": [
    "Recommendation 1 for sales team",
    "Recommendation 2",
    "Recommendation 3"
  ],
  "admin_summary": "Executive summary for management (3-4 sentences highlighting key points, average metrics, and recommended actions)"
}}"""

    try:
        log(f"🔵 Calling OpenAI model {LLM_MODEL}...")
        
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial analyst. Respond ONLY with valid JSON. No markdown, no code blocks, just pure JSON."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=MAX_TOKENS
        )
        
        raw = response.choices[0].message.content
        log(f"✅ Received LLM response ({len(raw)} chars)")
        
        # Clean up response - remove markdown code blocks if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Remove ```json and ``` markers
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
        
        # Parse JSON
        parsed = json.loads(cleaned)
        log(f"✅ Parsed JSON successfully with keys: {list(parsed.keys())}")
        
        return parsed, raw
        
    except json.JSONDecodeError as e:
        log(f"❌ JSON parsing failed: {e}")
        log(f"Raw response: {raw[:500]}")
        return {
            "error": "JSON parsing failed",
            "raw_response": raw,
            "cluster_id": payload["cluster_id"],
            "count": payload["count"]
        }, raw
        
    except Exception as e:
        log(f"❌ OpenAI API failed: {e}")
        traceback.print_exc()
        return {
            "error": str(e),
            "cluster_id": payload["cluster_id"],
            "count": payload["count"]
        }, str(e)


# =======================================================
# PDF GENERATION
# =======================================================
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch

def generate_pdf(cluster_id, ts, payload, decision):
    path = os.path.join(OUTPUT_DIR, f"cluster_{cluster_id}_{ts}.pdf")

    log(f"📝 Generating PDF → {path}")

    doc = SimpleDocTemplate(path, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph(f"Cluster Analysis Report — Cluster {cluster_id}", styles["Title"]))
    story.append(Spacer(1, 12))
    
    # Metadata
    story.append(Paragraph(f"<b>Generated:</b> {ts}", styles["Normal"]))
    story.append(Paragraph(f"<b>Customer Count:</b> {payload['count']}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Executive Summary
    story.append(Paragraph("<b>Executive Summary</b>", styles["Heading2"]))
    admin_summary = decision.get("admin_summary", "No summary available.")
    story.append(Paragraph(admin_summary, styles["BodyText"]))
    story.append(Spacer(1, 12))

    # Cluster Overview
    story.append(Paragraph("<b>Cluster Overview</b>", styles["Heading2"]))
    cluster_summary = decision.get("cluster_summary", "No cluster summary available.")
    story.append(Paragraph(cluster_summary, styles["BodyText"]))
    story.append(Spacer(1, 12))

    # Confidence Metrics
    story.append(Paragraph("<b>Confidence Score Distribution</b>", styles["Heading2"]))
    avg_conf = decision.get("avg_confidence", 0)
    conf_dist = decision.get("confidence_distribution", {})
    story.append(Paragraph(f"Average: {avg_conf:.3f}", styles["Normal"]))
    story.append(Paragraph(f"Range: {conf_dist.get('min', 0):.3f} - {conf_dist.get('max', 0):.3f}", styles["Normal"]))
    story.append(Paragraph(f"Median: {conf_dist.get('median', 0):.3f}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Key Prediction Factors
    story.append(Paragraph("<b>Key Prediction Factors</b>", styles["Heading2"]))
    factors = decision.get("prediction_factors", [])
    for i, factor in enumerate(factors, 1):
        story.append(Paragraph(f"{i}. {factor}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Recommendations
    story.append(Paragraph("<b>Recommendations</b>", styles["Heading2"]))
    recommendations = decision.get("recommendations", [])
    for i, rec in enumerate(recommendations, 1):
        story.append(Paragraph(f"{i}. {rec}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # Customer Details Table
    story.append(Paragraph("<b>Customer Details</b>", styles["Heading2"]))
    table_data = [["Customer ID", "Score", "Income", "Credit Score", "City Tier", "Age"]]

    for c in payload["customers"]:
        f = c["features"]
        table_data.append([
            str(c["customer_id"])[:15],  # Truncate if too long
            f"{c['score']:.3f}",
            str(f.get("yearly_income", "N/A")),
            str(f.get("final_credit_score", "N/A")),
            str(f.get("city_tier", "N/A")),
            str(f.get("age", "N/A"))
        ])

    table = Table(table_data, colWidths=[1.5*inch, 0.8*inch, 1*inch, 1*inch, 0.8*inch, 0.6*inch])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#003366")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4)
    ]))

    story.append(table)

    doc.build(story)
    log(f"✅ PDF generated successfully")
    return path


# =======================================================
# MAIN UDF — runs per cluster batch
# =======================================================
def consolidate_cluster(cluster_id, count, customers_json_str):

    log(f"📥 RECEIVED BATCH → cluster={cluster_id}, count={count}")
    
    # Parse the JSON string to get the list
    try:
        customers_list = json.loads(customers_json_str)
        log(f"Parsed {len(customers_list)} customers")
    except Exception as e:
        log(f"❌ Failed to parse customers JSON: {e}")
        return {
            "cluster_id": cluster_id,
            "timestamp": datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
            "report_path": "error",
            "count": 0,
            "error": str(e)
        }

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_path = os.path.join(OUTPUT_DIR, f"cluster_{cluster_id}_{ts}")

    # Enrich customer data
    enriched = []
    for c in customers_list:
        cid = c["customer_id"]
        feats = get_customer_features(cid)
        enriched.append({**c, "features": feats})

    payload = {
        "cluster_id": cluster_id,
        "count": count,
        "customers": enriched
    }

    # Generate analysis via OpenAI
    try:
        decision, raw = generate_cluster_analysis(payload)
        log(f"✅ Analysis completed with keys: {list(decision.keys())}")
    except Exception as e:
        log(f"❌ Analysis failed: {e}")
        traceback.print_exc()
        decision = {
            "error": str(e),
            "cluster_id": cluster_id,
            "count": count
        }
        raw = str(e)

    # Save JSON + TXT
    try:
        with open(base_path + ".json", "w") as f:
            json.dump(decision, f, indent=2)
        
        with open(base_path + ".txt", "w") as f:
            f.write(raw)
        
        log(f"✔ Saved JSON + TXT for cluster {cluster_id}")
    except Exception as e:
        log(f"❌ Failed to save files: {e}")

    # Generate PDF
    try:
        pdf_path = generate_pdf(cluster_id, ts, payload, decision)
        log(f"✅ Complete report generated at {pdf_path}")
    except Exception as e:
        log(f"❌ PDF generation failed: {e}")
        traceback.print_exc()

    return {
        "cluster_id": cluster_id,
        "timestamp": ts,
        "report_path": base_path + ".json",
        "count": count
    }


# =======================================================
# PATHWAY PIPELINE
# =======================================================
def run():

    log("🚀 Cluster Consolidator (Step-2) started...")
    log(f"Listening on → {INPUT_TOPIC}")
    log(f"Using OpenAI model: {LLM_MODEL}")

    batches = nats_read(
        uri=NATS_URI,
        topic=INPUT_TOPIC,
        format="json",
        schema=ClusterBatchSchema
    )

    results = batches.select(
        summary = pw.apply_with_type(
            consolidate_cluster, dict,
            pw.this.cluster_id,
            pw.this.count,
            pw.this.customers
        )
    ).select(
        cluster_id = pw.this.summary["cluster_id"],
        timestamp  = pw.this.summary["timestamp"],
        report_path= pw.this.summary["report_path"],
        count      = pw.this.summary["count"]
    )

    nats_write(
        results,
        uri=NATS_URI,
        topic=OUTPUT_TOPIC,
        format="json"
    )

    pw.run()


if __name__ == "__main__":
    run()