#!/usr/bin/env python3
"""
test_pipeline_local.py

Test the LLM pipeline locally without NATS streaming.
Loads customer data, simulates neighbors from similar customers, and runs the pipeline.

Requirements:
  pip install openai aiofiles python-dotenv reportlab pandas numpy scikit-learn

Usage:
  python test_pipeline_local.py
"""

import os
import json
import asyncio
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors

# PDF generation imports
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

load_dotenv()

# ---------- Config ----------
CUSTOMER_CSV = "/root/interiit/TargettedCalling/MASTERFILE.csv"
SCHEMES_NDJSON = "loan_schemes.ndjson"
OUTPUT_DIR = "reports_test"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
NUM_TEST_CUSTOMERS = 3  # Number of customers to test
NUM_NEIGHBORS = 10  # Number of neighbors to find

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------- Load Data ----------
def load_customer_data(csv_path: str) -> pd.DataFrame:
    """Load customer data from CSV"""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Customer CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"✓ Loaded {len(df)} customers from {csv_path}")
    return df

def load_schemes(ndjson_path: str) -> List[Dict[str, Any]]:
    """Load schemes from NDJSON file"""
    if not os.path.exists(ndjson_path):
        raise FileNotFoundError(f"Schemes NDJSON not found: {ndjson_path}")
    
    schemes = []
    with open(ndjson_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                schemes.append(json.loads(line))
    print(f"✓ Loaded {len(schemes)} schemes from {ndjson_path}")
    return schemes

# ---------- Find Similar Customers (Neighbors) ----------
def find_neighbors(df: pd.DataFrame, target_idx: int, n_neighbors: int = 10) -> List[Dict[str, Any]]:
    """
    Find k-nearest neighbors for a customer using numerical features
    """
    # Select numerical features for similarity
    feature_cols = [
        'age', 'yearly_income', 'final_credit_score', 'dti_ratio',
        'savings_rate', 'txn_count_last_30d', 'bounced_txn_count',
        'monthly_fuel_spend', 'monthly_transport_service_spend',
        'existing_loans_count', 'total_credit_limit'
    ]
    
    # Filter to available columns
    available_cols = [col for col in feature_cols if col in df.columns]
    
    # Prepare feature matrix
    X = df[available_cols].fillna(0).values
    
    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Find neighbors
    nn = NearestNeighbors(n_neighbors=n_neighbors+1, metric='euclidean')
    nn.fit(X_scaled)
    
    distances, indices = nn.kneighbors([X_scaled[target_idx]])
    
    # Exclude the customer itself (first result)
    neighbor_indices = indices[0][1:]
    
    # Convert to list of dicts
    neighbors = []
    for idx in neighbor_indices:
        neighbor = df.iloc[idx].to_dict()
        # Convert numpy types to Python types
        neighbor = {k: (v.item() if isinstance(v, np.generic) else v) 
                   for k, v in neighbor.items()}
        neighbors.append(neighbor)
    
    return neighbors

# ---------- Import Pipeline Functions ----------
# We'll recreate the essential functions here or import from pipeline_with_pathway.py

def find_applicable_schemes(customer: Dict[str, Any], schemes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter schemes based on basic customer attributes"""
    city_tier = customer.get("city_tier")
    income = customer.get("yearly_income", 0) or 0
    out = []
    
    for s in schemes:
        # Check city tier
        eligibility = s.get("eligibility_rules", {}) or s.get("eligibility", {})
        allowed_tiers = eligibility.get("allowed_city_tiers") or eligibility.get("city_tiers", [])
        
        if allowed_tiers and city_tier and city_tier not in allowed_tiers:
            continue
        
        # Check income range
        min_inc = s.get("min_income", 0) or 0
        max_inc = s.get("max_income", 10**15) or 10**15
        
        if income < min_inc or income > max_inc:
            continue
        
        out.append(s)
    
    return out

def prescreen_customer_against_scheme(customer: Dict[str, Any], scheme: Dict[str, Any]) -> Dict[str, Any]:
    """Prescreen customer against scheme eligibility rules"""
    rules = scheme.get("eligibility_rules", {})
    reasons = []
    passed = True

    # DTI ratio check
    dti = customer.get("dti_ratio")
    if dti is None:
        reasons.append("dti_ratio missing")
        passed = False
    else:
        max_dti = rules.get("max_dti_ratio")
        if max_dti is not None and dti > max_dti:
            reasons.append(f"dti_ratio {dti:.2f} > max_dti {max_dti}")
            passed = False

    # Bounced transactions check
    bounced = customer.get("bounced_txn_count", 0) or 0
    max_bounced = rules.get("max_bounced_txns_last_90d")
    if max_bounced is not None and bounced > max_bounced:
        reasons.append(f"bounced_txn_count {bounced} > allowed {max_bounced}")
        passed = False

    # Credit score check
    final_score = customer.get("final_credit_score")
    min_score = rules.get("require_final_credit_score_min")
    if min_score is not None:
        if final_score is None:
            reasons.append("final_credit_score missing")
            passed = False
        elif final_score < min_score:
            reasons.append(f"final_credit_score {final_score} < required {min_score}")
            passed = False

    # Existing EMI check
    monthly_income = (customer.get("yearly_income") or 0) / 12.0
    existing_emi = customer.get("existing_loan_monthly_EMI_total", 0) or 0
    max_emi_pct = rules.get("max_existing_emi_pct_of_income")
    if monthly_income > 0 and max_emi_pct is not None:
        emi_ratio = existing_emi / (monthly_income + 1e-9)
        if emi_ratio > max_emi_pct:
            reasons.append(f"existing EMI ratio {emi_ratio:.2f} > allowed {max_emi_pct}")
            passed = False

    return {"passed": passed, "reasons": reasons, "checked_rules": rules}

# ---------- Mock LLM Call (for testing without API key) ----------
def mock_llm_response(customer: Dict[str, Any], neighbors: List[Dict[str, Any]], 
                     passing_schemes: List[Dict[str, Any]]) -> str:
    """
    Generate a mock LLM response for testing without API calls
    """
    cust_id = customer.get('customer_id', 'UNKNOWN')
    income = customer.get('yearly_income', 0)
    credit_score = customer.get('final_credit_score', 0)
    
    response = f"""# Customer Analysis for {cust_id}

## Customer Profile Summary
- Annual Income: ₹{income:,.0f}
- Credit Score: {credit_score}
- DTI Ratio: {customer.get('dti_ratio', 0):.2%}
- City Tier: {customer.get('city_tier', 'N/A')}
- Employment: {customer.get('employment_type', 'N/A')}

## Neighbor Comparison
Compared with {len(neighbors)} similar customers:
- Average neighbor income: ₹{np.mean([n.get('yearly_income', 0) for n in neighbors]):,.0f}
- Average neighbor credit score: {np.mean([n.get('final_credit_score', 0) for n in neighbors]):.0f}

## Scheme Analysis
{len(passing_schemes)} schemes passed initial screening.

"""
    
    if passing_schemes:
        best_scheme = passing_schemes[0]
        response += f"""
## Recommendation
Based on the customer profile and comparison with similar customers, I recommend:

**{best_scheme.get('scheme_name', 'Unknown Scheme')}** (Product ID: {best_scheme.get('product_id', 'N/A')})

### Rationale:
1. Customer's income of ₹{income:,.0f} falls within the scheme's target range
2. Credit score of {credit_score} meets minimum requirements
3. DTI ratio is acceptable for this product tier
4. Similar customers in this profile have successfully obtained this product

### Computed Values:
- Estimated max loan amount: ₹{income * 5:,.0f} (5x annual income)
- Estimated EMI (for 30 years): ₹{(income * 5 * 0.009) / (1 - (1 + 0.009)**-360):,.0f}

```json
{{
  "eligibility": true,
  "chosen_product_id": "{best_scheme.get('product_id', 'N/A')}",
  "computed_values": {{
    "estimated_max_loan": {income * 5},
    "estimated_monthly_emi": {(income * 5 * 0.009) / (1 - (1 + 0.009)**-360)},
    "ltv_ratio": 0.75
  }},
  "rationale": [
    "Income meets minimum requirements",
    "Credit score above threshold",
    "DTI ratio within acceptable range",
    "Similar customers have been approved"
  ],
  "audit": {{
    "product_ids_considered": {json.dumps([s.get('product_id') for s in passing_schemes])},
    "analysis_timestamp": "{datetime.now().isoformat()}"
  }}
}}
```
"""
    else:
        response += """
## Recommendation
Unfortunately, no schemes currently match this customer's profile.

```json
{
  "eligibility": false,
  "chosen_product_id": null,
  "computed_values": {},
  "rationale": [
    "Customer does not meet minimum eligibility criteria for available schemes"
  ],
  "audit": {
    "product_ids_considered": [],
    "analysis_timestamp": """ + f'"{datetime.now().isoformat()}"' + """
  }
}
```
"""
    
    return response

# ---------- PDF Generation ----------
def generate_pdf_report(cust_id: str, timestamp: int, customer: Dict[str, Any], 
                       neighbors: List[Dict[str, Any]], llm_text: str, 
                       decision_obj: Dict[str, Any], prescreen_results: List[Dict[str, Any]],
                       passing_schemes: List[Dict[str, Any]], output_dir: str = OUTPUT_DIR):
    """
    Generate a comprehensive PDF report for the customer analysis
    """
    pdf_file = os.path.join(output_dir, f"{cust_id}_{timestamp}.pdf")
    
    doc = SimpleDocTemplate(
        pdf_file,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#2c5aa0'),
        spaceAfter=12,
        spaceBefore=15,
        fontName='Helvetica-Bold'
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.HexColor('#2c5aa0'),
        spaceAfter=8,
        spaceBefore=8,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=10,
        alignment=TA_LEFT,
        spaceAfter=6,
        leading=14
    )
    
    small_style = ParagraphStyle(
        'Small',
        parent=styles['BodyText'],
        fontSize=8,
        alignment=TA_LEFT,
        leading=10
    )
    
    # Title
    story.append(Paragraph(f"<b>Customer Loan Recommendation Report</b>", title_style))
    story.append(Paragraph(f"Customer ID: {cust_id}", 
                          ParagraphStyle('Subtitle', parent=styles['Normal'], 
                                       fontSize=12, alignment=TA_CENTER, textColor=colors.grey)))
    story.append(Spacer(1, 0.2*inch))
    
    # Report metadata
    story.append(Paragraph(f"<b>Report Generated:</b> {datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}", body_style))
    story.append(Paragraph(f"<b>Analysis Type:</b> Automated LLM-Based Recommendation", body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Executive Summary Box
    eligibility = decision_obj.get('eligibility', False)
    chosen_product = decision_obj.get('chosen_product_id', 'None')
    
    summary_color = colors.HexColor('#d4edda') if eligibility else colors.HexColor('#f8d7da')
    summary_text_color = colors.HexColor('#155724') if eligibility else colors.HexColor('#721c24')
    
    summary_data = [
        ['EXECUTIVE SUMMARY'],
        [f"Eligibility Status: {'✓ ELIGIBLE' if eligibility else '✗ NOT ELIGIBLE'}"],
        [f"Recommended Product: {chosen_product}"],
        [f"Schemes Analyzed: {len(prescreen_results)} | Passed: {len(passing_schemes)}"]
    ]
    
    summary_table = Table(summary_data, colWidths=[6*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), summary_color),
        ('TEXTCOLOR', (0, 1), (-1, -1), summary_text_color),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [summary_color])
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Customer Profile Section
    story.append(Paragraph("<b>1. Customer Profile</b>", heading_style))
    
    # Key metrics table
    key_metrics = [
        ['Metric', 'Value'],
        ['Annual Income', f"₹{customer.get('yearly_income', 0):,.0f}"],
        ['Credit Score', f"{customer.get('final_credit_score', 'N/A')}"],
        ['DTI Ratio', f"{customer.get('dti_ratio', 0):.2%}"],
        ['City Tier', customer.get('city_tier', 'N/A').title()],
        ['Employment Type', customer.get('employment_type', 'N/A')],
        ['Age', f"{customer.get('age', 'N/A')} years"],
        ['Marital Status', customer.get('marital_status', 'N/A')],
        ['Existing Loans', f"{customer.get('existing_loans_count', 0)}"],
        ['Monthly EMI', f"₹{customer.get('existing_loan_monthly_EMI_total', 0):,.0f}"],
        ['Bounced Transactions', f"{customer.get('bounced_txn_count', 0)}"]
    ]
    
    metrics_table = Table(key_metrics, colWidths=[2.5*inch, 3.5*inch])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
    ]))
    
    story.append(metrics_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Neighbor Comparison Section
    story.append(Paragraph("<b>2. Peer Comparison Analysis</b>", heading_style))
    story.append(Paragraph(f"Compared with {len(neighbors)} similar customers based on income, credit score, and financial behavior.", body_style))
    story.append(Spacer(1, 0.1*inch))
    
    if neighbors:
        neighbor_stats = [
            ['Metric', 'Customer', 'Peer Average', 'Difference'],
        ]
        
        metrics_to_compare = [
            ('yearly_income', 'Annual Income', '₹{:,.0f}'),
            ('final_credit_score', 'Credit Score', '{:.0f}'),
            ('dti_ratio', 'DTI Ratio', '{:.2%}'),
            ('savings_rate', 'Savings Rate', '{:.2%}'),
        ]
        
        for field, label, fmt in metrics_to_compare:
            cust_val = customer.get(field, 0) or 0
            neighbor_vals = [n.get(field, 0) or 0 for n in neighbors]
            avg_val = np.mean(neighbor_vals) if neighbor_vals else 0
            diff = cust_val - avg_val
            diff_pct = (diff / avg_val * 100) if avg_val != 0 else 0
            
            neighbor_stats.append([
                label,
                fmt.format(cust_val),
                fmt.format(avg_val),
                f"{diff_pct:+.1f}%"
            ])
        
        neighbor_table = Table(neighbor_stats, colWidths=[1.8*inch, 1.4*inch, 1.4*inch, 1.4*inch])
        neighbor_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
        ]))
        
        story.append(neighbor_table)
    else:
        story.append(Paragraph("No neighbor data available.", body_style))
    
    story.append(Spacer(1, 0.3*inch))
    
    # Scheme Evaluation Section
    story.append(Paragraph("<b>3. Scheme Evaluation Results</b>", heading_style))
    
    prescreen_data = [['Scheme Name', 'Product ID', 'Status', 'Issues']]
    
    for result in prescreen_results:
        status = '✓ PASS' if result['passed'] else '✗ FAIL'
        issues = ', '.join(result['reasons']) if result['reasons'] else 'None'
        # Truncate long issues
        if len(issues) > 50:
            issues = issues[:47] + '...'
        
        prescreen_data.append([
            result['scheme_name'],
            result['product_id'],
            status,
            issues
        ])
    
    prescreen_table = Table(prescreen_data, colWidths=[2*inch, 1*inch, 0.8*inch, 2.2*inch])
    prescreen_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (2, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    
    story.append(prescreen_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Recommendation Details
    story.append(Paragraph("<b>4. Detailed Recommendation</b>", heading_style))
    
    # Parse the LLM text for the recommendation section
    if "## Recommendation" in llm_text:
        rec_section = llm_text.split("## Recommendation")[1].split("```json")[0]
        # Clean and format
        for line in rec_section.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                story.append(Paragraph(line, body_style))
    else:
        story.append(Paragraph("No specific recommendation provided.", body_style))
    
    story.append(Spacer(1, 0.2*inch))
    
    # Rationale
    rationale_list = decision_obj.get('rationale', [])
    if rationale_list:
        story.append(Paragraph("<b>Key Decision Factors:</b>", subheading_style))
        for i, point in enumerate(rationale_list, 1):
            story.append(Paragraph(f"{i}. {point}", body_style))
    
    story.append(Spacer(1, 0.3*inch))
    
    # Computed Values
    computed = decision_obj.get('computed_values', {})
    if computed:
        story.append(Paragraph("<b>5. Financial Calculations</b>", heading_style))
        
        calc_data = [['Parameter', 'Value']]
        for key, value in computed.items():
            label = key.replace('_', ' ').title()
            if isinstance(value, (int, float)):
                if 'loan' in key.lower() or 'emi' in key.lower():
                    val_str = f"₹{value:,.0f}"
                elif 'ratio' in key.lower():
                    val_str = f"{value:.2%}"
                else:
                    val_str = f"{value:,.2f}"
            else:
                val_str = str(value)
            calc_data.append([label, val_str])
        
        calc_table = Table(calc_data, colWidths=[3*inch, 3*inch])
        calc_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
        ]))
        
        story.append(calc_table)
        story.append(Spacer(1, 0.3*inch))
    
    # Audit Trail
    story.append(Paragraph("<b>6. Audit Trail</b>", heading_style))
    audit = decision_obj.get('audit', {})
    story.append(Paragraph(f"<b>Products Considered:</b> {', '.join(audit.get('product_ids_considered', []))}", small_style))
    story.append(Paragraph(f"<b>Analysis Timestamp:</b> {audit.get('analysis_timestamp', 'N/A')}", small_style))
    story.append(Paragraph(f"<b>Total Schemes Evaluated:</b> {len(prescreen_results)}", small_style))
    story.append(Paragraph(f"<b>Schemes Passed Screening:</b> {len(passing_schemes)}", small_style))
    
    # Footer
    story.append(Spacer(1, 0.4*inch))
    story.append(Paragraph("_" * 80, small_style))
    story.append(Paragraph(
        "This report is generated by an automated AI system for informational purposes. "
        "Final lending decisions are subject to manual review and approval.",
        ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, 
                      textColor=colors.grey, alignment=TA_CENTER)
    ))
    
    # Build PDF
    doc.build(story)
    print(f"✓ PDF generated: {pdf_file}")
    return pdf_file

# ---------- Process Single Customer ----------
async def process_test_customer(customer_row: pd.Series, all_customers_df: pd.DataFrame, 
                                schemes: List[Dict[str, Any]], customer_idx: int):
    """Process a single test customer through the pipeline"""
    
    # Convert customer to dict
    customer = customer_row.to_dict()
    customer = {k: (v.item() if isinstance(v, np.generic) else v) 
               for k, v in customer.items()}
    
    cust_id = customer.get('customer_id', f'TEST_{customer_idx}')
    print(f"\n{'='*60}")
    print(f"Processing Customer: {cust_id}")
    print(f"{'='*60}")
    
    # Find neighbors
    print(f"Finding {NUM_NEIGHBORS} nearest neighbors...")
    neighbors = find_neighbors(all_customers_df, customer_idx, NUM_NEIGHBORS)
    print(f"✓ Found {len(neighbors)} neighbors")
    
    # Find applicable schemes
    print(f"Filtering applicable schemes...")
    applicable_schemes = find_applicable_schemes(customer, schemes)
    if not applicable_schemes:
        print(f"⚠ No schemes match basic filters, using all {len(schemes)} schemes")
        applicable_schemes = schemes
    else:
        print(f"✓ {len(applicable_schemes)} schemes match basic filters")
    
    # Prescreen against schemes
    print(f"Prescreening against eligibility rules...")
    passing_schemes = []
    prescreen_results = []
    
    for scheme in applicable_schemes:
        result = prescreen_customer_against_scheme(customer, scheme)
        prescreen_results.append({
            'product_id': scheme.get('product_id'),
            'scheme_name': scheme.get('scheme_name'),
            'passed': result['passed'],
            'reasons': result['reasons']
        })
        
        if result['passed']:
            passing_schemes.append(scheme)
            print(f"  ✓ PASS: {scheme.get('scheme_name')}")
        else:
            print(f"  ✗ FAIL: {scheme.get('scheme_name')} - {', '.join(result['reasons'])}")
    
    print(f"\n✓ {len(passing_schemes)}/{len(applicable_schemes)} schemes passed prescreening")
    
    # Prepare schemes for LLM
    schemes_to_send = passing_schemes if passing_schemes else applicable_schemes[:3]
    
    # Generate mock response (or call real LLM if API key is set)
    print(f"\nGenerating analysis (mock mode)...")
    llm_text = mock_llm_response(customer, neighbors, schemes_to_send)
    
    # Extract JSON from response
    import re
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', llm_text, re.DOTALL)
    if json_match:
        decision_obj = json.loads(json_match.group(1))
    else:
        decision_obj = {
            "error": "Could not extract JSON from response",
            "eligibility": False,
            "chosen_product_id": None
        }
    
    # Add prescreen summary
    decision_obj['prescreen_summary'] = prescreen_results
    decision_obj['product_ids_considered'] = [s.get('product_id') for s in schemes_to_send]
    
    # Save results
    timestamp = int(datetime.now().timestamp())
    base_path = os.path.join(OUTPUT_DIR, f"{cust_id}_{timestamp}")
    
    # Save text report
    with open(f"{base_path}.txt", 'w', encoding='utf-8') as f:
        f.write(llm_text)
    
    # Save decision JSON
    with open(f"{base_path}.decision.json", 'w', encoding='utf-8') as f:
        json.dump(decision_obj, f, indent=2, ensure_ascii=False)
    
    # Save raw response
    with open(f"{base_path}.llm_raw.json", 'w', encoding='utf-8') as f:
        json.dump({"mock_response": llm_text}, f, indent=2, ensure_ascii=False)
    
    # Generate PDF report
    try:
        pdf_path = generate_pdf_report(
            cust_id=cust_id,
            timestamp=timestamp,
            customer=customer,
            neighbors=neighbors,
            llm_text=llm_text,
            decision_obj=decision_obj,
            prescreen_results=prescreen_results,
            passing_schemes=passing_schemes,
            output_dir=OUTPUT_DIR
        )
    except Exception as e:
        print(f"⚠ Failed to generate PDF: {e}")
        pdf_path = None
    
    print(f"\n✓ Saved reports to: {base_path}.*")
    if pdf_path:
        print(f"✓ PDF report: {pdf_path}")
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Summary for {cust_id}:")
    print(f"  Eligible: {decision_obj.get('eligibility')}")
    print(f"  Recommended: {decision_obj.get('chosen_product_id')}")
    print(f"  Schemes Considered: {len(schemes_to_send)}")
    print(f"  Schemes Passed: {len(passing_schemes)}")
    print(f"{'='*60}")
    
    return decision_obj

# ---------- Main Test Function ----------
async def main():
    print("="*60)
    print("LOAN RECOMMENDATION PIPELINE - LOCAL TEST")
    print("="*60)
    
    # Load data
    print("\n1. Loading data...")
    customers_df = load_customer_data(CUSTOMER_CSV)
    schemes = load_schemes(SCHEMES_NDJSON)
    
    # Select test customers (diverse samples)
    print(f"\n2. Selecting {NUM_TEST_CUSTOMERS} test customers...")
    
    # Try to get diverse customers
    test_indices = []
    
    # High income
    high_income = customers_df[customers_df['yearly_income'] > 2000000].head(1)
    if not high_income.empty:
        test_indices.append(high_income.index[0])
    
    # Medium income
    med_income = customers_df[
        (customers_df['yearly_income'] >= 800000) & 
        (customers_df['yearly_income'] <= 1500000)
    ].head(1)
    if not med_income.empty:
        test_indices.append(med_income.index[0])
    
    # Low income or stressed
    low_income = customers_df[customers_df['yearly_income'] < 800000].head(1)
    if not low_income.empty:
        test_indices.append(low_income.index[0])
    
    # If we need more, add random
    while len(test_indices) < NUM_TEST_CUSTOMERS:
        idx = np.random.randint(0, len(customers_df))
        if idx not in test_indices:
            test_indices.append(idx)
    
    test_indices = test_indices[:NUM_TEST_CUSTOMERS]
    
    # Process each test customer
    print(f"\n3. Processing {len(test_indices)} customers...\n")
    
    results = []
    for idx in test_indices:
        customer_row = customers_df.iloc[idx]
        result = await process_test_customer(customer_row, customers_df, schemes, idx)
        results.append(result)
        await asyncio.sleep(0.1)  # Small delay between customers
    
    # Summary statistics
    print(f"\n\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"Total customers processed: {len(results)}")
    print(f"Eligible: {sum(1 for r in results if r.get('eligibility'))}")
    print(f"Not eligible: {sum(1 for r in results if not r.get('eligibility'))}")
    print(f"\nReports saved to: {OUTPUT_DIR}/")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    asyncio.run(main())