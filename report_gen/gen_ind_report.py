#!/usr/bin/env python3
"""
individual_customer_report.py

Generates a comprehensive report for a single customer on-demand.

Usage:
    python individual_customer_report.py CUST_004643

Requirements:
    pip install openai python-dotenv reportlab pandas redis

Environment:
    - OPENAI_API_KEY must be set
    - PREDICTION_CACHE_PATH (optional, default: prediction_cache.csv)
    - REDIS_HOST (optional, default: localhost)
    - REDIS_PORT (optional, default: 6379)
    - REDIS_DB (optional, default: 1)
    - SCHEMES_NDJSON_PATH (optional, default: loan_schemes.ndjson)
    - OUTPUT_DIR (optional, default: individual_reports)
"""

import os
import sys
import json
import re
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd

# OpenAI
from openai import OpenAI

# PDF generation
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

load_dotenv()

# ---------- Config ----------
CURRENT_DIR = Path(__file__).resolve().parent
ROOT = CURRENT_DIR.parent

# Add root to path for imports
sys.path.append(str(ROOT))

PREDICTION_CACHE_PATH = os.getenv("PREDICTION_CACHE_PATH", str(CURRENT_DIR / "prediction_cache.csv"))
SCHEMES_NDJSON_PATH = os.getenv("SCHEMES_NDJSON_PATH", str(CURRENT_DIR / "loan_schemes.ndjson"))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(CURRENT_DIR / "individual_reports"))

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "1"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY","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")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY must be set in environment")

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2000"))

client = OpenAI(api_key=OPENAI_API_KEY)
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"Config:")
print(f"  Prediction cache: {PREDICTION_CACHE_PATH}")
print(f"  MASTERFILE: Redis @ {REDIS_HOST}:{REDIS_PORT} (db={REDIS_DB})")
print(f"  Schemes NDJSON: {SCHEMES_NDJSON_PATH}")
print(f"  Output directory: {OUTPUT_DIR}")
print(f"  OpenAI model: {OPENAI_MODEL}\n")

# ---------- Load Data ----------
def load_masterfile_from_redis() -> pd.DataFrame:
    """Load MASTERFILE from Redis using RedisDataManager."""
    from dataManager.redis_data_manager import get_data_manager
    
    data_manager = get_data_manager(REDIS_HOST, REDIS_PORT, REDIS_DB)
    
    # Test connection
    try:
        data_manager.redis_client.ping()
    except Exception as e:
        raise RuntimeError(f"Cannot connect to Redis at {REDIS_HOST}:{REDIS_PORT}: {e}")
    
    df = data_manager.get_dataframe()
    if df is None or df.empty:
        raise RuntimeError("MASTERFILE not found in Redis. Run load_masterfile_to_redis.py first.")
    
    df.set_index('customer_id', inplace=True)
    print(f"✓ Loaded MASTERFILE from Redis with {len(df)} customers")
    return df

def load_prediction_cache_from_redis() -> pd.DataFrame:
    """Load prediction cache from Redis."""
    import pickle
    
    from dataManager.redis_data_manager import get_data_manager
    data_manager = get_data_manager(REDIS_HOST, REDIS_PORT, REDIS_DB)
    
    PREDICTION_CACHE_KEY = "prediction_cache"
    
    try:
        # Get all predictions from Redis hash
        all_predictions = data_manager.redis_client.hgetall(PREDICTION_CACHE_KEY)
        
        if not all_predictions:
            print(f"⚠ No predictions found in Redis cache (key: {PREDICTION_CACHE_KEY})")
            return pd.DataFrame(columns=['customer_id', 'cluster_id', 'score', 'exemplars'])
        
        # Unpickle each prediction
        rows = []
        for customer_id_bytes, prediction_bytes in all_predictions.items():
            try:
                customer_id = customer_id_bytes.decode('utf-8') if isinstance(customer_id_bytes, bytes) else customer_id_bytes
                prediction = pickle.loads(prediction_bytes)
                prediction['customer_id'] = customer_id
                rows.append(prediction)
            except Exception as e:
                print(f"  Warning: Failed to parse prediction for {customer_id_bytes}: {e}")
        
        df = pd.DataFrame(rows)
        
        # Clean up customer_id
        if 'customer_id' in df.columns:
            df['customer_id'] = df['customer_id'].astype(str).str.strip().str.strip("'\"")
        
        # Convert numeric columns
        if 'cluster_id' in df.columns:
            df['cluster_id'] = pd.to_numeric(df['cluster_id'], errors='coerce')
        if 'score' in df.columns:
            df['score'] = pd.to_numeric(df['score'], errors='coerce')
        
        print(f"✓ Loaded prediction cache from Redis with {len(df)} entries")
        if len(df) > 0:
            print(f"  Columns: {list(df.columns)}")
            print(f"  Sample customer IDs: {df['customer_id'].head(3).tolist()}")
        
        return df
        
    except Exception as e:
        print(f"⚠ Error loading prediction cache from Redis: {e}")
        return pd.DataFrame(columns=['customer_id', 'cluster_id', 'score', 'exemplars'])

def load_schemes_from_ndjson(path: str) -> List[Dict[str, Any]]:
    """Load loan schemes from NDJSON file."""
    schemes = []
    if not os.path.exists(path):
        raise FileNotFoundError(f"NDJSON file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                schemes.append(json.loads(line))
            except Exception as e:
                print(f"Warning: skipping invalid JSON line: {e}")
    print(f"✓ Loaded {len(schemes)} loan schemes\n")
    return schemes

# Load all data
MASTERFILE_DF = load_masterfile_from_redis()
PREDICTION_CACHE_DF = load_prediction_cache_from_redis()
SCHEMES = load_schemes_from_ndjson(SCHEMES_NDJSON_PATH)

# ---------- Data Extraction ----------
def get_customer_data(cust_id: str) -> Optional[Dict[str, Any]]:
    """Get customer data from MASTERFILE."""
    try:
        return MASTERFILE_DF.loc[cust_id].to_dict()
    except KeyError:
        return None

def get_prediction_data(cust_id: str) -> Optional[Dict[str, Any]]:
    """Get prediction data from cache."""
    # Strip whitespace from input
    cust_id = str(cust_id).strip().strip("'\"")
    
    matches = PREDICTION_CACHE_DF[PREDICTION_CACHE_DF['customer_id'] == cust_id]
    if matches.empty:
        print(f"  ✗ Customer {cust_id} not found in prediction cache")
        return None
    
    row = matches.iloc[0]
    
    # Parse exemplars (they're stored as string representation of list)
    exemplars_str = row['exemplars']
    try:
        # Handle both string representation and actual list
        if isinstance(exemplars_str, str):
            # Clean up the string and parse
            exemplars_str = exemplars_str.strip()
            if exemplars_str.startswith('[') and exemplars_str.endswith(']'):
                exemplars = eval(exemplars_str)
            else:
                exemplars = []
        else:
            exemplars = exemplars_str
        
        # Clean quotes from exemplar IDs
        exemplars = [str(e).strip("'\"") for e in exemplars]
    except Exception as e:
        print(f"  Warning: Failed to parse exemplars: {e}")
        exemplars = []
    
    try:
        return {
            "customer_id": str(row['customer_id']).strip("'\""),
            "cluster_id": int(row['cluster_id']),
            "score": float(row['score']),
            "exemplars": exemplars
        }
    except Exception as e:
        print(f"  ✗ Error parsing prediction data: {e}")
        print(f"  Row data: {row.to_dict()}")
        return None

def get_neighbor_data(exemplar_ids: List[str]) -> List[Dict[str, Any]]:
    """Get data for neighbor/exemplar customers."""
    neighbors = []
    for ex_id in exemplar_ids:
        # Strip extra quotes if present
        ex_id_clean = str(ex_id).strip("'\"")
        if ex_id_clean in MASTERFILE_DF.index:
            neighbor = MASTERFILE_DF.loc[ex_id_clean].to_dict()
            neighbor['customer_id'] = ex_id_clean
            neighbors.append(neighbor)
    return neighbors

# ---------- Scheme Matching Logic ----------
def find_applicable_schemes(customer: Dict[str, Any], schemes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter schemes based on basic heuristics."""
    city_tier = customer.get("city_tier")
    income = customer.get("yearly_income", 0) or 0
    out = []
    
    for s in schemes:
        # Check city tier eligibility
        eligibility = s.get("eligibility_rules") or s.get("eligibility", {})
        allowed_tiers = eligibility.get("allowed_city_tiers") or eligibility.get("city_tiers")
        if allowed_tiers and city_tier and city_tier not in allowed_tiers:
            continue
        
        # Check income range
        min_inc = s.get("min_income") or s.get("loan_limits", {}).get("min_amount", 0) or 0
        max_inc = s.get("max_income", 10**15) or 10**15
        if income < min_inc or income > max_inc:
            continue
        
        out.append(s)
    
    return out if out else schemes  # Return all if none match

def prescreen_customer_against_scheme(customer: Dict[str, Any], scheme: Dict[str, Any]) -> Dict[str, Any]:
    """Detailed prescreen check against scheme rules."""
    rules = scheme.get("eligibility_rules", {})
    reasons = []
    passed = True

    # DTI check
    dti = customer.get("dti_ratio")
    max_dti = rules.get("max_dti_ratio")
    if dti is not None and max_dti is not None and dti > max_dti:
        reasons.append(f"DTI ratio {dti:.2f} exceeds max {max_dti}")
        passed = False

    # Bounced transactions
    bounced = customer.get("bounced_txn_count", 0) or 0
    max_bounced = rules.get("max_bounced_txns_last_90d")
    if max_bounced is not None and bounced > max_bounced:
        reasons.append(f"Bounced transactions {bounced} > allowed {max_bounced}")
        passed = False

    # Credit score
    final_score = customer.get("final_credit_score")
    min_score = rules.get("require_final_credit_score_min")
    if min_score is not None:
        if final_score is None:
            reasons.append("Credit score missing")
            passed = False
        elif final_score < min_score:
            reasons.append(f"Credit score {final_score} < required {min_score}")
            passed = False

    # Existing EMI ratio
    monthly_income = (customer.get("yearly_income") or 0) / 12.0
    existing_emi = customer.get("existing_loan_monthly_EMI_total", 0) or 0
    max_emi_pct = rules.get("max_existing_emi_pct_of_income")
    if monthly_income > 0 and max_emi_pct is not None:
        emi_ratio = existing_emi / (monthly_income + 1e-9)
        if emi_ratio > max_emi_pct:
            reasons.append(f"EMI ratio {emi_ratio:.2%} > allowed {max_emi_pct:.2%}")
            passed = False

    return {
        "passed": passed,
        "reasons": reasons if not passed else ["All checks passed"],
        "checked_rules": list(rules.keys())
    }

# ---------- LLM Analysis ----------
def extract_json_from_response(text: str) -> Dict[str, Any]:
    """Extract JSON from LLM response with markdown fence handling."""
    # Try to find ```json fenced block
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except:
            pass
    
    # Try any fenced block
    m2 = re.search(r"```(?:\w+)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(1))
        except:
            pass
    
    # Fallback: find first {...} block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except:
            pass
    
    raise ValueError("No valid JSON found in LLM response")

def generate_llm_analysis(customer: Dict[str, Any], prediction: Dict[str, Any], 
                         neighbors: List[Dict[str, Any]], passing_schemes: List[Dict[str, Any]]) -> tuple:
    """Generate comprehensive analysis using OpenAI."""
    
    # Build compact representation
    customer_summary = {
        "customer_id": customer.get("customer_id"),
        "cluster_id": prediction.get("cluster_id"),
        "prediction_score": prediction.get("score"),
        "income": customer.get("yearly_income"),
        "credit_score": customer.get("final_credit_score"),
        "city_tier": customer.get("city_tier"),
        "age": customer.get("age"),
        "employment_type": customer.get("employment_type"),
        "dti_ratio": customer.get("dti_ratio"),
        "existing_emi": customer.get("existing_loan_monthly_EMI_total")
    }
    
    neighbor_summary = []
    for n in neighbors[:5]:  # Top 5 neighbors
        neighbor_summary.append({
            "customer_id": n.get("customer_id"),
            "income": n.get("yearly_income"),
            "credit_score": n.get("final_credit_score"),
            "city_tier": n.get("city_tier")
        })
    
    schemes_compact = [
        {
            "product_id": s.get("product_id"),
            "scheme_name": s.get("scheme_name"),
            "interest_rate": s.get("interest_rate"),
            "loan_limits": s.get("loan_limits"),
            "eligibility_rules": s.get("eligibility_rules")
        }
        for s in passing_schemes
    ]
    
    prompt = f"""You are a financial analyst generating a comprehensive car loan eligibility report.

CUSTOMER DATA:
{json.dumps(customer_summary, indent=2)}

SIMILAR CUSTOMERS (Cluster neighbors):
{json.dumps(neighbor_summary, indent=2)}

ELIGIBLE LOAN SCHEMES:
{json.dumps(schemes_compact, indent=2)}

TASK:
1. Analyze the customer's eligibility for car loans
2. Compare with similar customers in their cluster
3. Recommend the best loan scheme (or explain why none are suitable)
4. Provide actionable recommendations

Respond with a detailed analysis followed by a JSON decision in ```json ... ``` format.

JSON STRUCTURE:
{{
  "eligibility_verdict": "APPROVED" | "CONDITIONAL" | "REJECTED",
  "recommended_scheme_id": "product_id or null",
  "confidence_score": <0.0 to 1.0>,
  "key_factors": ["factor1", "factor2", ...],
  "risk_assessment": {{
    "credit_risk": "LOW|MEDIUM|HIGH",
    "income_stability": "STABLE|MODERATE|UNSTABLE",
    "existing_debt_burden": "LOW|MEDIUM|HIGH"
  }},
  "comparison_with_peers": "Brief comparison with cluster neighbors",
  "recommendations": ["recommendation1", "recommendation2", ...],
  "executive_summary": "2-3 sentence summary for bank management"
}}"""

    try:
        print(f"  Calling OpenAI {OPENAI_MODEL}...")
        
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial analyst. Provide detailed analysis followed by valid JSON in markdown fences."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.3,
            max_tokens=MAX_TOKENS
        )
        
        raw_text = response.choices[0].message.content
        print(f"  ✓ Received response ({len(raw_text)} chars)")
        
        # Extract JSON decision
        decision = extract_json_from_response(raw_text)
        print(f"  ✓ Extracted JSON decision")
        
        return raw_text, decision
        
    except Exception as e:
        print(f"  ✗ LLM analysis failed: {e}")
        return f"Error: {e}", {"error": str(e)}

# ---------- PDF Generation ----------
def generate_pdf_report(cust_id: str, customer: Dict[str, Any], prediction: Dict[str, Any],
                       neighbors: List[Dict[str, Any]], schemes_analysis: Dict[str, Any],
                       llm_text: str, decision: Dict[str, Any]) -> str:
    """Generate comprehensive PDF report."""
    
    timestamp = int(time.time())
    pdf_file = os.path.join(OUTPUT_DIR, f"{cust_id}_{timestamp}.pdf")
    
    doc = SimpleDocTemplate(pdf_file, pagesize=A4, 
                          rightMargin=0.5*inch, leftMargin=0.5*inch,
                          topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle('title', parent=styles['Heading1'], 
                                fontSize=18, alignment=1, spaceAfter=12)
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], 
                       fontSize=14, textColor=colors.HexColor('#2c5aa0'), spaceAfter=6)
    body = ParagraphStyle('body', parent=styles['BodyText'], 
                         fontSize=10, leading=14, spaceAfter=6)
    
    # Title
    story.append(Paragraph(f"Car Loan Eligibility Report", title_style))
    story.append(Paragraph(f"Customer ID: {cust_id}", styles['Heading3']))
    story.append(Spacer(1, 0.1*inch))
    
    # Metadata
    story.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body))
    story.append(Paragraph(f"<b>Cluster:</b> {prediction.get('cluster_id')}", body))
    story.append(Paragraph(f"<b>Prediction Score:</b> {prediction.get('score', 0):.3f}", body))
    story.append(Spacer(1, 0.15*inch))
    
    # Executive Summary
    story.append(Paragraph("Executive Summary", h2))
    exec_summary = decision.get("executive_summary", "No summary available")
    story.append(Paragraph(exec_summary, body))
    
    verdict = decision.get("eligibility_verdict", "UNKNOWN")
    verdict_color = {
        "APPROVED": colors.green,
        "CONDITIONAL": colors.orange,
        "REJECTED": colors.red
    }.get(verdict, colors.grey)
    
    story.append(Paragraph(f"<b>Verdict:</b> <font color='{verdict_color.hexval()}'>{verdict}</font>", body))
    story.append(Paragraph(f"<b>Recommended Scheme:</b> {decision.get('recommended_scheme_id', 'None')}", body))
    story.append(Spacer(1, 0.15*inch))
    
    # Customer Profile
    story.append(Paragraph("Customer Profile", h2))
    cust_data = [
        ["Income (Yearly)", f"₹{customer.get('yearly_income', 0):,.0f}"],
        ["Credit Score", str(customer.get('final_credit_score', 'N/A'))],
        ["City Tier", str(customer.get('city_tier', 'N/A'))],
        ["Age", str(customer.get('age', 'N/A'))],
        ["Employment Type", str(customer.get('employment_type', 'N/A'))],
        ["DTI Ratio", f"{customer.get('dti_ratio', 0):.2f}"],
        ["Existing EMI", f"₹{customer.get('existing_loan_monthly_EMI_total', 0):,.0f}"]
    ]
    t = Table(cust_data, colWidths=[2.5*inch, 3*inch])
    t.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#e8f4f8')),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold')
    ]))
    story.append(t)
    story.append(Spacer(1, 0.15*inch))
    
    # Risk Assessment
    story.append(Paragraph("Risk Assessment", h2))
    risk = decision.get("risk_assessment", {})
    story.append(Paragraph(f"<b>Credit Risk:</b> {risk.get('credit_risk', 'N/A')}", body))
    story.append(Paragraph(f"<b>Income Stability:</b> {risk.get('income_stability', 'N/A')}", body))
    story.append(Paragraph(f"<b>Debt Burden:</b> {risk.get('existing_debt_burden', 'N/A')}", body))
    story.append(Spacer(1, 0.15*inch))
    
    # Eligible Schemes
    story.append(Paragraph("Scheme Analysis", h2))
    passing = schemes_analysis.get('passing_schemes', [])
    if passing:
        scheme_data = [["Scheme", "Interest Rate", "Status"]]
        for s in passing[:5]:
            prescreen = s.get('prescreen', {})
            status = "✓ Eligible" if prescreen.get('passed') else "✗ Not Eligible"
            scheme_data.append([
                s['scheme'].get('scheme_name', 'N/A'),
                f"{s['scheme'].get('interest_rate', 0):.2f}%",
                status
            ])
        t2 = Table(scheme_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
        t2.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
        ]))
        story.append(t2)
    else:
        story.append(Paragraph("No schemes passed eligibility criteria.", body))
    story.append(Spacer(1, 0.15*inch))
    
    # Recommendations
    story.append(Paragraph("Recommendations", h2))
    recs = decision.get("recommendations", [])
    for i, rec in enumerate(recs, 1):
        story.append(Paragraph(f"{i}. {rec}", body))
    story.append(Spacer(1, 0.15*inch))
    
    # Cluster Comparison
    story.append(Paragraph("Cluster Comparison", h2))
    comparison = decision.get("comparison_with_peers", "No comparison available")
    story.append(Paragraph(comparison, body))
    story.append(Spacer(1, 0.1*inch))
    
    if neighbors:
        story.append(Paragraph(f"<b>Similar Customers ({len(neighbors)}):</b>", body))
        neigh_data = [["ID", "Income", "Credit Score", "City"]]
        for n in neighbors[:5]:
            neigh_data.append([
                str(n.get('customer_id', ''))[:15],
                f"₹{n.get('yearly_income', 0):,.0f}",
                str(n.get('final_credit_score', 'N/A')),
                str(n.get('city_tier', 'N/A'))
            ])
        t3 = Table(neigh_data, colWidths=[1.5*inch, 1.5*inch, 1.2*inch, 1*inch])
        t3.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9)
        ]))
        story.append(t3)
    
    doc.build(story)
    return pdf_file

# ---------- Main Processing ----------
def generate_report_for_customer(cust_id: str):
    """Generate complete report for a single customer."""
    
    print(f"\n{'='*60}")
    print(f"Generating report for customer: {cust_id}")
    print(f"{'='*60}\n")
    
    # 1. Fetch customer data
    print("1. Fetching customer data...")
    customer = get_customer_data(cust_id)
    if not customer:
        print(f"  ✗ Customer {cust_id} not found in MASTERFILE")
        return None
    customer['customer_id'] = cust_id
    print(f"  ✓ Found customer data")
    
    # 2. Fetch prediction data
    print("2. Fetching prediction data...")
    prediction = get_prediction_data(cust_id)
    if not prediction:
        print(f"  ✗ No prediction data found for {cust_id}")
        return None
    print(f"  ✓ Found prediction (cluster={prediction['cluster_id']}, score={prediction['score']:.3f})")
    
    # 3. Fetch neighbor data
    print("3. Fetching neighbor/exemplar data...")
    neighbors = get_neighbor_data(prediction['exemplars'])
    print(f"  ✓ Found {len(neighbors)} neighbors")
    
    # 4. Find applicable schemes
    print("4. Analyzing loan schemes...")
    applicable_schemes = find_applicable_schemes(customer, SCHEMES)
    print(f"  ✓ Found {len(applicable_schemes)} applicable schemes")
    
    # 5. Prescreen schemes
    print("5. Prescreening schemes...")
    passing_schemes = []
    schemes_analysis = {'passing_schemes': [], 'failing_schemes': []}
    
    for scheme in applicable_schemes:
        prescreen = prescreen_customer_against_scheme(customer, scheme)
        scheme_info = {
            'scheme': scheme,
            'prescreen': prescreen
        }
        if prescreen['passed']:
            passing_schemes.append(scheme)
            schemes_analysis['passing_schemes'].append(scheme_info)
        else:
            schemes_analysis['failing_schemes'].append(scheme_info)
    
    print(f"  ✓ {len(passing_schemes)} schemes passed prescreen")
    
    # 6. Generate LLM analysis
    print("6. Generating AI analysis...")
    schemes_to_analyze = passing_schemes if passing_schemes else applicable_schemes[:3]
    llm_text, decision = generate_llm_analysis(customer, prediction, neighbors, schemes_to_analyze)
    
    # 7. Save text reports
    print("7. Saving reports...")
    timestamp = int(time.time())
    base_path = os.path.join(OUTPUT_DIR, f"{cust_id}_{timestamp}")
    
    with open(base_path + ".txt", "w", encoding="utf-8") as f:
        f.write(llm_text)
    
    with open(base_path + ".decision.json", "w", encoding="utf-8") as f:
        json.dump(decision, f, indent=2, ensure_ascii=False)
    
    with open(base_path + ".schemes_analysis.json", "w", encoding="utf-8") as f:
        # Make schemes JSON serializable
        schemes_json = {
            'passing_count': len(schemes_analysis['passing_schemes']),
            'failing_count': len(schemes_analysis['failing_schemes']),
            'passing_schemes': [
                {
                    'product_id': s['scheme'].get('product_id'),
                    'scheme_name': s['scheme'].get('scheme_name'),
                    'prescreen': s['prescreen']
                }
                for s in schemes_analysis['passing_schemes']
            ]
        }
        json.dump(schemes_json, f, indent=2, ensure_ascii=False)
    
    print(f"  ✓ Saved text reports to {base_path}.*")
    
    # 8. Generate PDF
    print("8. Generating PDF report...")
    try:
        pdf_path = generate_pdf_report(cust_id, customer, prediction, neighbors, 
                                      schemes_analysis, llm_text, decision)
        print(f"  ✓ PDF generated: {pdf_path}")
    except Exception as e:
        print(f"  ✗ PDF generation failed: {e}")
        pdf_path = None
    
    print(f"\n{'='*60}")
    print(f"✅ Report generation complete!")
    print(f"{'='*60}")
    print(f"Files saved:")
    print(f"  - {base_path}.txt")
    print(f"  - {base_path}.decision.json")
    print(f"  - {base_path}.schemes_analysis.json")
    if pdf_path:
        print(f"  - {pdf_path}")
    print()
    
    return base_path

# ---------- Main ----------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python individual_customer_report.py <CUSTOMER_ID>")
        print("\nExample:")
        print("  python individual_customer_report.py CUST_004643")
        print("\nAvailable customers in prediction cache:")
        
        # Show first 10 customer IDs
        available = PREDICTION_CACHE_DF['customer_id'].head(10).tolist()
        for cid in available:
            print(f"  - {cid}")
        
        if len(PREDICTION_CACHE_DF) > 10:
            print(f"  ... and {len(PREDICTION_CACHE_DF) - 10} more")
        
        # Ask for input interactively
        print("\nEnter customer ID (or press Ctrl+C to exit):")
        try:
            cust_id = input("> ").strip()
            if not cust_id:
                print("No customer ID provided. Exiting.")
                sys.exit(1)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            sys.exit(0)
    else:
        cust_id = sys.argv[1].strip()
    
    try:
        result = generate_report_for_customer(cust_id)
        if result:
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)