import pandas as pd
import json
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from datetime import datetime, timedelta
import random
import math
import os

# ---------- Utility functions ----------
def fmt_inr(x):
    try:
        return f"₹{int(x):,}"
    except:
        return str(x)

def compute_emi(principal, annual_rate_pct, tenure_years):
    """
    Standard EMI formula
    EMI = P * r * (1+r)^n / ((1+r)^n - 1)
    where r = monthly rate, n = months
    """
    if principal <= 0 or annual_rate_pct <= 0 or tenure_years <= 0:
        return None
    r = annual_rate_pct / 12.0 / 100.0
    n = tenure_years * 12
    try:
        emi = principal * r * (1 + r) ** n / ((1 + r) ** n - 1)
    except ZeroDivisionError:
        emi = principal / n
    return emi

def approximate_apr(annual_rate_pct, processing_fee_pct, processing_fee_fixed=0, tenure_years=20):
    """
    Very rough APR-ish indicator that includes processing fee amortized over tenure.
    Not a regulatory APR; include as an example note only.
    """
    # amortize processing fee over tenure by adding to principal
    # This is a simplified view for brochure examples (not a legally-binding APR)
    # effective_rate ≈ nominal_rate + (processing_fee_amount / (principal * tenure_years)) * 100
    # We'll produce a demonstrative APR for a sample principal of 1 (normalize).
    principal = 1_000_000
    processing_fee_amount = principal * (processing_fee_pct / 100.0) + processing_fee_fixed
    added_pct = (processing_fee_amount / (principal * tenure_years)) * 100
    return round(annual_rate_pct + added_pct, 3)

# ---------- Updated schemes with metadata, rules, and fees detail ----------
def define_loan_schemes():
    """
    Create loan schemes targeting different customer segments from the synthetic data,
    enriched with LLM-friendly, dataset-aligned fields (product_id, issue_date, valid_until,
    contact info, explicit eligibility rules, variables used/ignored, and fees detail).
    """
    base_issue = datetime.now()
    schemes = [
        {
            'product_id': 'PREM-HL-2025-001',
            'scheme_name': 'Premium Home Loan',
            'target_segment': 'High_Net_Worth, Urban_Tech_Couples',
            'description': 'Exclusive home loan for high-income professionals and business owners',
            'min_income': 2000000,
            'max_income': 15000000,
            'min_credit_score': 750,
            'loan_amount_range': (5000000, 50000000),
            'interest_rate_variable': 8.25,
            'interest_rate_fixed_1yr': 8.50,
            'interest_rate_fixed_3yr': 8.75,
            'interest_rate_fixed_5yr': 9.00,
            'processing_fee_pct': 0.5,
            'processing_fee_min': 5000,
            'processing_fee_max': 150000,
            'processing_fee_gst_applicable': True,
            'prepayment_charges_fixed_rate_pct': 1.0,   # fixed-rate prepayment penalty pct
            'max_loan_tenure_years': 30,
            'max_ltv_ratio': 80,
            'features': [
                'Zero pre-payment charges on variable rate loans',
                'Free property valuation',
                'Doorstep service for documentation',
                'Dedicated relationship manager',
                'Top-up loan facility available',
                'Offset savings account option'
            ],
            'eligibility': {
                'age_min': 25,
                'age_max': 60,
                'employment_types': ['Salaried', 'Self-Employed'],
                'city_tiers': ['tier1'],
                'min_work_experience_years': 3
            },
            # explicit rule set aligned to dataset variables
            'eligibility_rules': {
                'max_dti_ratio': 0.45,
                'max_existing_emi_pct_of_income': 0.55,  # total EMI <= 55% of monthly income
                'max_bounced_txns_last_90d': 0,
                'require_final_credit_score_min': 740,
                'allowed_city_tiers': ['tier1']
            },
            'fees_detail': 'Processing fee 0.5% (min ₹5,000, max ₹150,000) + GST where applicable; fixed-rate prepayment charges 1% of outstanding principal.',
            'uses_variables': ['yearly_income', 'existing_loan_monthly_EMI_total', 'dti_ratio', 'final_credit_score', 'bounced_txn_count', 'city_tier'],
            'ignores_variables': ['txn_intensity', 'monthly_fuel_spend', 'monthly_transport_service_spend', 'avg_monthly_investment_debit'],
            'contact': {
                'phone': '+91-1800-XXX-XXXX',
                'email': 'home.loans@bankexample.co.in',
                'url': 'https://bankexample.co.in/home-loans'
            },
            'issue_date': base_issue.strftime('%Y-%m-%d'),
            'valid_until': (base_issue + timedelta(days=90)).strftime('%Y-%m-%d')
        },
        # --- Smart Professional Home Loan (example with dataset-aligned rules) ---
        {
            'product_id': 'SMART-HL-2025-001',
            'scheme_name': 'Smart Professional Home Loan',
            'target_segment': 'Urban_Tech_Couples, Independent_Women_Earners',
            'description': 'Designed for young professionals with stable income',
            'min_income': 1000000,
            'max_income': 3000000,
            'min_credit_score': 720,
            'loan_amount_range': (2000000, 15000000),
            'interest_rate_variable': 8.50,
            'interest_rate_fixed_1yr': 8.75,
            'interest_rate_fixed_3yr': 9.00,
            'interest_rate_fixed_5yr': 9.25,
            'processing_fee_pct': 0.75,
            'processing_fee_min': 3500,
            'processing_fee_max': 100000,
            'processing_fee_gst_applicable': True,
            'prepayment_charges_fixed_rate_pct': 1.0,
            'max_loan_tenure_years': 30,
            'max_ltv_ratio': 85,
            'features': [
                'Quick online application and approval',
                'Balance transfer facility',
                'Flexible repayment options',
                'Part-payment allowed (up to 25% annually)',
                'Preferential rates for women borrowers',
                'Digital documentation process'
            ],
            'eligibility': {
                'age_min': 23,
                'age_max': 58,
                'employment_types': ['Salaried'],
                'city_tiers': ['tier1', 'tier2'],
                'min_work_experience_years': 2
            },
            'eligibility_rules': {
                'max_dti_ratio': 0.5,
                'max_existing_emi_pct_of_income': 0.55,
                'max_bounced_txns_last_90d': 0,
                'require_final_credit_score_min': 700,
                'allowed_city_tiers': ['tier1', 'tier2']
            },
            'fees_detail': 'Processing fee 0.75% (min ₹3,500, max ₹100,000) + GST; fixed-rate prepayment charges 1% of outstanding principal.',
            'uses_variables': ['yearly_income', 'existing_loan_monthly_EMI_total', 'dti_ratio', 'final_credit_score', 'bounced_txn_count', 'city_tier'],
            'ignores_variables': ['txn_category_*', 'txn_intensity'],
            'contact': {
                'phone': '+91-1800-YYY-YYYY',
                'email': 'smartloans@bankexample.co.in',
                'url': 'https://bankexample.co.in/smart-loans'
            },
            'issue_date': base_issue.strftime('%Y-%m-%d'),
            'valid_until': (base_issue + timedelta(days=120)).strftime('%Y-%m-%d')
        },
        # --- Add other schemes similarly, condensed for brevity; ensure they include the new keys ---
        # Business Owner Home Loan
        {
            'product_id': 'BUS-HL-2025-001',
            'scheme_name': 'Business Owner Home Loan',
            'target_segment': 'Tier2_Business_Owners',
            'description': 'Tailored for self-employed business owners and traders',
            'min_income': 1500000,
            'max_income': 10000000,
            'min_credit_score': 700,
            'loan_amount_range': (3000000, 30000000),
            'interest_rate_variable': 8.75,
            'interest_rate_fixed_1yr': 9.00,
            'interest_rate_fixed_3yr': 9.25,
            'interest_rate_fixed_5yr': 9.50,
            'processing_fee_pct': 1.0,
            'processing_fee_min': 7500,
            'processing_fee_max': 200000,
            'processing_fee_gst_applicable': True,
            'prepayment_charges_fixed_rate_pct': 1.5,
            'max_loan_tenure_years': 25,
            'max_ltv_ratio': 75,
            'features': [
                'Flexible income documentation',
                'Business cash flow considered',
                'Overdraft facility on home loan',
                'Part-payment up to 20% per year',
                'Multiple property financing',
                'Step-up EMI options available'
            ],
            'eligibility': {
                'age_min': 28,
                'age_max': 65,
                'employment_types': ['Self-Employed'],
                'city_tiers': ['tier1', 'tier2'],
                'min_work_experience_years': 5
            },
            'eligibility_rules': {
                'max_dti_ratio': 0.5,
                'max_existing_emi_pct_of_income': 0.55,
                'max_bounced_txns_last_90d': 1,
                'require_final_credit_score_min': 690,
                'allowed_city_tiers': ['tier1', 'tier2']
            },
            'fees_detail': 'Processing fee 1.0% (min ₹7,500, max ₹200,000) + GST; fixed-rate prepayment charges 1.5% of outstanding principal.',
            'uses_variables': ['yearly_income', 'existing_loan_monthly_EMI_total', 'dti_ratio', 'final_credit_score', 'bounced_txn_count'],
            'ignores_variables': ['txn_category_*', 'txn_intensity'],
            'contact': {
                'phone': '+91-1800-ZZZ-ZZZZ',
                'email': 'business.loans@bankexample.co.in',
                'url': 'https://bankexample.co.in/business-loans'
            },
            'issue_date': base_issue.strftime('%Y-%m-%d'),
            'valid_until': (base_issue + timedelta(days=180)).strftime('%Y-%m-%d')
        },
        # Government Employee Special (condensed)
        {
            'product_id': 'GOV-HL-2025-001',
            'scheme_name': 'Government Employee Special',
            'target_segment': 'Govt_Employees',
            'description': 'Exclusive scheme for government employees with attractive rates',
            'min_income': 800000,
            'max_income': 2500000,
            'min_credit_score': 680,
            'loan_amount_range': (1500000, 10000000),
            'interest_rate_variable': 8.15,
            'interest_rate_fixed_1yr': 8.40,
            'interest_rate_fixed_3yr': 8.65,
            'interest_rate_fixed_5yr': 8.90,
            'processing_fee_pct': 0.25,
            'processing_fee_min': 2000,
            'processing_fee_max': 50000,
            'processing_fee_gst_applicable': True,
            'prepayment_charges_fixed_rate_pct': 0.0,
            'max_loan_tenure_years': 30,
            'max_ltv_ratio': 90,
            'features': [
                'Lowest interest rates',
                'Extended loan tenure options',
                'Minimal documentation',
                'Pre-approved loans for eligible employees',
                'Pension-linked repayment available',
                'Zero foreclosure charges'
            ],
            'eligibility': {
                'age_min': 25,
                'age_max': 60,
                'employment_types': ['Salaried'],
                'city_tiers': ['tier1', 'tier2', 'tier3'],
                'min_work_experience_years': 2,
                'specific_occupation': ['Govt. Employee']
            },
            'eligibility_rules': {
                'max_dti_ratio': 0.5,
                'max_existing_emi_pct_of_income': 0.6,
                'max_bounced_txns_last_90d': 0,
                'require_final_credit_score_min': 660,
                'allowed_city_tiers': ['tier1', 'tier2', 'tier3']
            },
            'fees_detail': 'Processing fee 0.25% (min ₹2,000, max ₹50,000) + GST; zero foreclosure charges.',
            'uses_variables': ['yearly_income', 'existing_loan_monthly_EMI_total', 'dti_ratio', 'final_credit_score', 'bounced_txn_count', 'occupation'],
            'ignores_variables': ['txn_category_*', 'txn_intensity'],
            'contact': {
                'phone': '+91-1800-GOV-GOVN',
                'email': 'gov.loans@bankexample.co.in',
                'url': 'https://bankexample.co.in/gov-loans'
            },
            'issue_date': base_issue.strftime('%Y-%m-%d'),
            'valid_until': (base_issue + timedelta(days=365)).strftime('%Y-%m-%d')
        },
        # First Home Buyer Advantage (condensed)
        {
            'product_id': 'FHB-HL-2025-001',
            'scheme_name': 'First Home Buyer Advantage',
            'target_segment': 'First_Time_Professionals, Stable_Renters',
            'description': 'Special scheme for first-time home buyers',
            'min_income': 600000,
            'max_income': 1800000,
            'min_credit_score': 680,
            'loan_amount_range': (1000000, 8000000),
            'interest_rate_variable': 8.65,
            'interest_rate_fixed_1yr': 8.90,
            'interest_rate_fixed_3yr': 9.15,
            'interest_rate_fixed_5yr': 9.40,
            'processing_fee_pct': 0.50,
            'processing_fee_min': 2500,
            'processing_fee_max': 75000,
            'processing_fee_gst_applicable': True,
            'prepayment_charges_fixed_rate_pct': 1.0,
            'max_loan_tenure_years': 30,
            'max_ltv_ratio': 90,
            'features': [
                'Higher loan-to-value ratio up to 90%',
                'Reduced processing fees',
                'Step-up EMI facility',
                'Free credit counseling',
                'Co-applicant benefits',
                'Government subsidy assistance'
            ],
            'eligibility': {
                'age_min': 21,
                'age_max': 45,
                'employment_types': ['Salaried'],
                'city_tiers': ['tier1', 'tier2', 'tier3'],
                'min_work_experience_years': 1,
                'first_time_buyer': True
            },
            'eligibility_rules': {
                'max_dti_ratio': 0.5,
                'max_existing_emi_pct_of_income': 0.55,
                'max_bounced_txns_last_90d': 0,
                'require_final_credit_score_min': 680,
                'allowed_city_tiers': ['tier1', 'tier2', 'tier3']
            },
            'fees_detail': 'Processing fee 0.50% (min ₹2,500, max ₹75,000) + GST; government subsidy assistance guidance included.',
            'uses_variables': ['yearly_income', 'existing_loan_monthly_EMI_total', 'dti_ratio', 'final_credit_score', 'bounced_txn_count'],
            'ignores_variables': ['txn_category_*', 'txn_intensity'],
            'contact': {
                'phone': '+91-1800-FHB-FHB1',
                'email': 'fhb@bankexample.co.in',
                'url': 'https://bankexample.co.in/fhb-loans'
            },
            'issue_date': base_issue.strftime('%Y-%m-%d'),
            'valid_until': (base_issue + timedelta(days=365)).strftime('%Y-%m-%d')
        },
        # Affordable Housing Loan (condensed)
        {
            'product_id': 'AFF-HL-2025-001',
            'scheme_name': 'Affordable Housing Loan',
            'target_segment': 'Financially_Stressed, Stable_Renters',
            'description': 'Affordable home loan for middle-income groups',
            'min_income': 400000,
            'max_income': 1200000,
            'min_credit_score': 650,
            'loan_amount_range': (500000, 5000000),
            'interest_rate_variable': 8.85,
            'interest_rate_fixed_1yr': 9.10,
            'interest_rate_fixed_3yr': 9.35,
            'interest_rate_fixed_5yr': 9.60,
            'processing_fee_pct': 0.50,
            'processing_fee_min': 1500,
            'processing_fee_max': 50000,
            'processing_fee_gst_applicable': True,
            'prepayment_charges_fixed_rate_pct': 1.5,
            'max_loan_tenure_years': 25,
            'max_ltv_ratio': 85,
            'features': [
                'Affordable EMI options',
                'Government scheme benefits (PMAY)',
                'Minimal documentation for salaried',
                'Extended repayment tenure',
                'Joint applicant advantages',
                'Flexible income proof requirements'
            ],
            'eligibility': {
                'age_min': 21,
                'age_max': 55,
                'employment_types': ['Salaried', 'Self-Employed'],
                'city_tiers': ['tier1', 'tier2', 'tier3'],
                'min_work_experience_years': 1
            },
            'eligibility_rules': {
                'max_dti_ratio': 0.55,
                'max_existing_emi_pct_of_income': 0.6,
                'max_bounced_txns_last_90d': 1,
                'require_final_credit_score_min': 650,
                'allowed_city_tiers': ['tier1', 'tier2', 'tier3']
            },
            'fees_detail': 'Processing fee 0.50% (min ₹1,500, max ₹50,000) + GST; fixed-rate prepayment charges 1.5% of outstanding principal.',
            'uses_variables': ['yearly_income', 'existing_loan_monthly_EMI_total', 'dti_ratio', 'final_credit_score', 'bounced_txn_count'],
            'ignores_variables': ['txn_category_*', 'txn_intensity'],
            'contact': {
                'phone': '+91-1800-AFF-AFF1',
                'email': 'affordable@bankexample.co.in',
                'url': 'https://bankexample.co.in/affordable-loans'
            },
            'issue_date': base_issue.strftime('%Y-%m-%d'),
            'valid_until': (base_issue + timedelta(days=365)).strftime('%Y-%m-%d')
        }
    ]
    return schemes

# ---------- PDF generation with added sections and JSON export ----------
def generate_scheme_pdf(scheme, output_filename):
    """
    Generate a PDF document for a loan scheme with enriched, LLM-friendly content:
    - product metadata
    - explicit eligibility rules & non-eligibility examples
    - variables used / ignored (so LLM doesn't hallucinate)
    - sample EMI / APR examples
    - machine-readable JSON exported alongside the PDF
    """
    # Create output directory if not exists
    outdir = os.path.dirname(output_filename) or '.'
    os.makedirs(outdir, exist_ok=True)

    doc = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    story = []
    styles = getSampleStyleSheet()

    # Styles
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=22,
                                 textColor=colors.HexColor('#1a1a1a'), spaceAfter=18, alignment=TA_CENTER,
                                 fontName='Helvetica-Bold')
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=14,
                                   textColor=colors.HexColor('#2c5aa0'), spaceAfter=8, spaceBefore=8,
                                   fontName='Helvetica-Bold')
    body_style = ParagraphStyle('CustomBody', parent=styles['BodyText'], fontSize=10,
                                alignment=TA_JUSTIFY, spaceAfter=8, leading=13)
    mono_style = ParagraphStyle('Mono', parent=styles['Code'], fontSize=8, leading=10)

    # Header / metadata
    story.append(Paragraph(f"<b>{scheme['scheme_name']}</b>", title_style))
    meta_par = (
        f"Product ID: {scheme.get('product_id','N/A')} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Issue Date: {scheme.get('issue_date','N/A')} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Valid Until: {scheme.get('valid_until','N/A')}"
    )
    story.append(Paragraph(meta_par, ParagraphStyle('meta', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)))
    story.append(Spacer(1, 0.2*inch))

    # Description
    story.append(Paragraph("<b>Product Overview</b>", heading_style))
    story.append(Paragraph(scheme['description'], body_style))
    story.append(Spacer(1, 0.1*inch))

    # Contact
    story.append(Paragraph("<b>Contact & Support</b>", heading_style))
    contact = scheme.get('contact', {})
    story.append(Paragraph(f"Phone: {contact.get('phone','TBD')}  &nbsp;&nbsp;|&nbsp;&nbsp; Email: {contact.get('email','TBD')}", body_style))
    story.append(Paragraph(f"Website: {contact.get('url','TBD')}", body_style))
    story.append(Spacer(1, 0.15*inch))

    # Interest rates table
    story.append(Paragraph("<b>Interest Rates</b>", heading_style))
    rate_data = [
        ['Rate Type', 'Interest Rate (% p.a.)'],
        ['Variable Rate', f"{scheme['interest_rate_variable']}%"],
        ['Fixed Rate (1 Year)', f"{scheme['interest_rate_fixed_1yr']}%"],
        ['Fixed Rate (3 Years)', f"{scheme['interest_rate_fixed_3yr']}%"],
        ['Fixed Rate (5 Years)', f"{scheme['interest_rate_fixed_5yr']}%"],
    ]
    rate_table = Table(rate_data, colWidths=[3*inch, 2*inch])
    rate_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    story.append(rate_table)
    story.append(Spacer(1, 0.15*inch))

    # Loan details
    story.append(Paragraph("<b>Loan Details</b>", heading_style))
    loan_data = [
        ['Parameter', 'Details'],
        ['Loan Amount Range', f"{fmt_inr(scheme['loan_amount_range'][0])} — {fmt_inr(scheme['loan_amount_range'][1])}"],
        ['Loan Tenure', f"Up to {scheme['max_loan_tenure_years']} years"],
        ['Loan-to-Value (LTV) Ratio', f"Up to {scheme['max_ltv_ratio']}%"],
        ['Processing Fee', f"{scheme['processing_fee_pct']}% (min {fmt_inr(scheme.get('processing_fee_min',0))}, max {fmt_inr(scheme.get('processing_fee_max',0))}) {'+ GST' if scheme.get('processing_fee_gst_applicable') else ''}"],
        ['Prepayment Charges (fixed-rate)', f"{scheme.get('prepayment_charges_fixed_rate_pct',0)}% of outstanding principal (see details)"],
        ['Minimum Income Required', f"₹{scheme['min_income']:,} per annum"],
        ['Minimum Credit Score (guideline)', f"{scheme['min_credit_score']}"]
    ]
    loan_table = Table(loan_data, colWidths=[2.5*inch, 3*inch])
    loan_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    story.append(loan_table)
    story.append(Spacer(1, 0.15*inch))

    # Key features
    story.append(Paragraph("<b>Key Features</b>", heading_style))
    for feature in scheme['features']:
        story.append(Paragraph(f"• {feature}", body_style))
    story.append(Spacer(1, 0.15*inch))

    # Eligibility section: structured rules (very important for LLMs)
    story.append(Paragraph("<b>Eligibility Criteria (structured rules)</b>", heading_style))
    elig = scheme.get('eligibility', {})
    erules = scheme.get('eligibility_rules', {})
    story.append(Paragraph(f"<b>Age:</b> {elig.get('age_min','N/A')} to {elig.get('age_max','N/A')} years", body_style))
    story.append(Paragraph(f"<b>Employment Type(s):</b> {', '.join(elig.get('employment_types',[]))}", body_style))
    story.append(Paragraph(f"<b>City Coverage:</b> {', '.join([t.replace('tier','Tier ').title() for t in elig.get('city_tiers',[])])}", body_style))
    story.append(Paragraph(f"<b>Minimum Work Experience:</b> {elig.get('min_work_experience_years','N/A')} years", body_style))
    story.append(Spacer(1, 0.05*inch))

    # Explicit rules table mapping to dataset features
    story.append(Paragraph("<b>Explicit Eligibility Rules (these map to dataset fields)</b>", body_style))
    rules_data = [
        ['Rule (dataset field)', ' Requirement '],
        ['Maximum DTI (dti_ratio)', f"<= {erules.get('max_dti_ratio','N/A')}"],
        ['Max total EMI as % of monthly income (existing + proposed)', f"<= {int(erules.get('max_existing_emi_pct_of_income',0)*100)}%"],
        ['Bounced debits allowed (bounced_txn_count in last 90 days)', f"<= {erules.get('max_bounced_txns_last_90d','N/A')}"],
        ['Minimum final credit score (final_credit_score)', f">= {erules.get('require_final_credit_score_min','N/A')}"],
        ['Allowed city tiers (city_tier)', f"{', '.join(erules.get('allowed_city_tiers',[]))}"]
    ]
    rules_table = Table(rules_data, colWidths=[3*inch, 2.5*inch])
    rules_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white)
    ]))
    story.append(rules_table)
    story.append(Spacer(1, 0.15*inch))

    # Non-eligibility examples to prevent hallucination
    story.append(Paragraph("<b>Non-Eligibility Examples (explicit)</b>", heading_style))
    story.append(Paragraph("• Applicants with DTI > {0} are not eligible.".format(erules.get('max_dti_ratio','N/A')), body_style))
    story.append(Paragraph("• Applicants with > {0} bounced debit(s) in the last 90 days are not eligible.".format(erules.get('max_bounced_txns_last_90d','N/A')), body_style))
    story.append(Paragraph("• Applicants from city tiers outside the allowed tiers are not eligible for this scheme.", body_style))
    story.append(Paragraph("• If required input fields (property value and requested loan amount) are not provided the application cannot be assessed.", body_style))
    story.append(Spacer(1, 0.15*inch))

    # Variables used vs ignored (so the LLM knows what's authoritative)
    story.append(Paragraph("<b>Dataset Variables — USED (authoritative)</b>", heading_style))
    used = scheme.get('uses_variables', [])
    story.append(Paragraph(", ".join(used), body_style))
    story.append(Paragraph("<b>Dataset Variables — IGNORED for eligibility (do not use to decide)</b>", heading_style))
    ignored = scheme.get('ignores_variables', [])
    story.append(Paragraph(", ".join(ignored), body_style))
    story.append(Spacer(1, 0.15*inch))

    # Required inputs not present in synthetic dataset (explicitly call out)
    story.append(Paragraph("<b>Additional Required Inputs (must be provided to compute LTV and final eligibility)</b>", heading_style))
    story.append(Paragraph("• Property market value (property_value).", body_style))
    story.append(Paragraph("• Requested loan amount (requested_loan_amount).", body_style))
    story.append(Paragraph("• Proof of stable employment / business (documents) if not already provided.", body_style))
    story.append(Spacer(1, 0.15*inch))

    # Repayment and EMI examples
    story.append(Paragraph("<b>Repayment Options & EMI Examples (illustrative)</b>", heading_style))
    story.append(Paragraph("• Repayment Type: Principal & Interest (EMI) or Interest Only (subject to approval).", body_style))
    story.append(Paragraph("• Frequency: Monthly. Part-payments permitted as per scheme rules (see prepayment charges).", body_style))
    story.append(Spacer(1, 0.05*inch))

    # Calculate sample EMIs for two representative principal amounts:
    sample_principals = [max(scheme['loan_amount_range'][0], 2_000_000), int((scheme['loan_amount_range'][0] + scheme['loan_amount_range'][1]) / 2)]
    sample_tenures = [15, 20]  # years
    emi_rows = [['Sample Loan (P)', 'Tenure (yrs)', 'Rate (%)', 'Monthly EMI (approx)']]
    for P in sample_principals:
        for t in sample_tenures:
            r = scheme['interest_rate_variable']
            emi = compute_emi(P, r, t)
            emi_rows.append([fmt_inr(P), t, f"{r}%", f"{int(round(emi)):,}" if emi else 'N/A'])
    emi_table = Table(emi_rows, colWidths=[2.2*inch, 1*inch, 1.2*inch, 2*inch])
    emi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c5aa0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
    ]))
    story.append(emi_table)
    story.append(Spacer(1, 0.15*inch))

    # APR illustrative example (approximate)
    apr_example = approximate_apr(scheme['interest_rate_variable'], scheme['processing_fee_pct'], tenure_years=20)
    story.append(Paragraph(f"<b>Example APR (illustrative):</b> Approx. {apr_example}% (nominal rate plus amortized processing fee — illustrative only, not a regulatory APR).", body_style))
    story.append(Spacer(1, 0.15*inch))

    # Required documents section
    story.append(Paragraph("<b>Required Documents</b>", heading_style))
    story.append(Paragraph("<b>For Salaried Individuals:</b>", body_style))
    story.append(Paragraph("• Identity Proof (Aadhaar, PAN, Passport)", body_style))
    story.append(Paragraph("• Address Proof (Utility bills, Rental agreement)", body_style))
    story.append(Paragraph("• Last 6 months salary slips", body_style))
    story.append(Paragraph("• Last 6 months bank statements", body_style))
    story.append(Paragraph("• Form 16 for last 2 years", body_style))
    story.append(Spacer(1, 0.05*inch))
    story.append(Paragraph("<b>For Self-Employed:</b>", body_style))
    story.append(Paragraph("• Identity and Address Proof", body_style))
    story.append(Paragraph("• Business proof and registration documents", body_style))
    story.append(Paragraph("• Last 2 years IT returns", body_style))
    story.append(Paragraph("• Last 12 months bank statements", body_style))
    story.append(Paragraph("• Financial statements (Balance Sheet, P&L)", body_style))
    story.append(Spacer(1, 0.2*inch))

    # Important information and compliance notes
    story.append(Paragraph("<b>Important Information & LLM/Platform Notes</b>", heading_style))
    story.append(Paragraph("• All loans are subject to credit approval and verification of documents.", body_style))
    story.append(Paragraph("• The dataset-derived signals used for automated pre-screening are: yearly_income, existing_loan_monthly_EMI_total, dti_ratio, final_credit_score, bounced_txn_count, city_tier.", body_style))
    story.append(Paragraph("• Spending category features (e.g., fuel/transport/shopping/investment debits) are NOT used for eligibility decisions in this product — they can be used for advisory but not for eligibility rules.", body_style))
    story.append(Paragraph("• When feeding brochure + customer data into an LLM: include product_id, issue_date, valid_until; do NOT instruct the model to invent fees or contact info. Provide property_value and requested_loan_amount to compute LTV.", body_style))
    story.append(Paragraph("• This brochure contains illustrative EMI/APR examples — always compute final figures at underwriting using exact inputs.", body_style))
    story.append(Spacer(1, 0.2*inch))

    # Footer
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
    story.append(Paragraph(f"This document is valid as of {scheme.get('issue_date')} and valid until {scheme.get('valid_until')}. For latest information, visit {scheme.get('contact',{}).get('url','website')}.", footer_style))

    doc.build(story)

    # Save JSON metadata for machine ingestion
    json_filename = os.path.splitext(output_filename)[0] + '.json'
    # Build a compact machine-friendly object
    machine_obj = {
        'product_id': scheme.get('product_id'),
        'scheme_name': scheme.get('scheme_name'),
        'issuer': 'Bank Example',  # replace with real issuer
        'issue_date': scheme.get('issue_date'),
        'valid_until': scheme.get('valid_until'),
        'contact': scheme.get('contact', {}),
        'interest_rates': {
            'variable_rate': scheme.get('interest_rate_variable'),
            'fixed_1yr': scheme.get('interest_rate_fixed_1yr'),
            'fixed_3yr': scheme.get('interest_rate_fixed_3yr'),
            'fixed_5yr': scheme.get('interest_rate_fixed_5yr'),
            'apr_illustrative_note': f"approx {approximate_apr(scheme.get('interest_rate_variable',0), scheme.get('processing_fee_pct',0), tenure_years=20)}% (illustrative)"
        },
        'loan_limits': {
            'min_amount': scheme['loan_amount_range'][0],
            'max_amount': scheme['loan_amount_range'][1],
            'max_tenure_years': scheme['max_loan_tenure_years'],
            'max_ltv_percent': scheme['max_ltv_ratio']
        },
        'fees': {
            'processing_fee_pct': scheme.get('processing_fee_pct'),
            'processing_fee_min': scheme.get('processing_fee_min'),
            'processing_fee_max': scheme.get('processing_fee_max'),
            'processing_fee_gst_applicable': scheme.get('processing_fee_gst_applicable'),
            'prepayment_charges_fixed_rate_pct': scheme.get('prepayment_charges_fixed_rate_pct'),
            'notes': scheme.get('fees_detail')
        },
        'eligibility_rules': scheme.get('eligibility_rules', {}),
        'required_additional_inputs': ['property_value', 'requested_loan_amount'],
        'uses_variables': scheme.get('uses_variables', []),
        'ignores_variables': scheme.get('ignores_variables', []),
        'features': scheme.get('features', []),
        'description': scheme.get('description')
    }
    with open(json_filename, 'w', encoding='utf-8') as jf:
        json.dump(machine_obj, jf, indent=2)
    print(f"Generated: {output_filename}  (metadata: {json_filename})")


def generate_all_scheme_pdfs(output_folder='.'):
    schemes = define_loan_schemes()
    summary_data = []
    for idx, scheme in enumerate(schemes, 1):
        filename = os.path.join(output_folder, f"loan_scheme_{idx}_{scheme['scheme_name'].replace(' ', '_').lower()}.pdf")
        generate_scheme_pdf(scheme, filename)
        # Add row for CSV
        summary_data.append({
            'Product ID': scheme['product_id'],
            'Scheme Name': scheme['scheme_name'],
            'Target Segment': scheme['target_segment'],
            'Min Income': scheme['min_income'],
            'Max Income': scheme['max_income'],
            'Min Credit Score': scheme['min_credit_score'],
            'Variable Rate (%)': scheme['interest_rate_variable'],
            'Max LTV (%)': scheme['max_ltv_ratio'],
            'Processing Fee (%)': scheme['processing_fee_pct']
        })
    summary_df = pd.DataFrame(summary_data)
    summary_csv = os.path.join(output_folder, 'loan_schemes_summary_enriched.csv')
    summary_df.to_csv(summary_csv, index=False)
    print(f"\nGenerated {summary_csv}\nTotal schemes generated: {len(schemes)}")


if __name__ == '__main__':
    # Example: generate into ./output_schemes
    generate_all_scheme_pdfs(output_folder='output_schemes')
