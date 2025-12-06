#!/usr/bin/env python3
"""
pipeline_with_pathway.py

Integrated pipeline using Pathway xpack-llm (OpenAIChat -> gpt-4) or fallback OpenAI direct call.

Requirements:
  pip install "pathway[xpack-llm]" nats-py openai aiofiles python-dotenv reportlab

Environment:
  - OPENAI_API_KEY must be set (used by Pathway and openai).
  - NATS_SERVERS (optional), CUSTOMER_TOPIC, NEIGHBORS_TOPIC, SCHEMES_NDJSON_PATH, OUTPUT_DIR.

Behavior:
  - Loads schemes NDJSON
  - Waits for customer + neighbors on NATS
  - Pre-screens schemes deterministically, sends all passing schemes to the LLM
  - Expects human text + fenced JSON decision
  - Saves .txt, .decision.json, .llm_raw.json, .pdf and publishes summary to NATS
"""

import os
import json
import re
import time
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timezone
from dotenv import load_dotenv
import aiofiles
import openai

# NATS client
from nats.aio.client import Client as NATS

# PDF generation
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

load_dotenv()

# ---------- Config ----------
NATS_SERVERS = os.getenv("NATS_SERVERS", "nats://127.0.0.1:4222")
CUSTOMER_TOPIC = os.getenv("CUSTOMER_TOPIC", "customers.updates")
NEIGHBORS_TOPIC = os.getenv("NEIGHBORS_TOPIC", "customers.neighbors")
RESULT_TOPIC = os.getenv("RESULT_TOPIC", "customers.reports")
SCHEMES_NDJSON_PATH = os.getenv("SCHEMES_NDJSON_PATH", "loan_schemes.ndjson")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "reports")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
USE_PATHWAY_XPACK = os.getenv("USE_PATHWAY_XPACK", "true").lower() in ("1", "true", "yes")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY must be set in the environment or .env")

openai.api_key = OPENAI_API_KEY

# ---------- In-memory buffers ----------
customer_buffer: Dict[str, Dict[str, Any]] = {}
neighbors_buffer: Dict[str, Dict[str, Any]] = {}
nc_global = None

# ---------- Load schemes ----------
def load_schemes_from_ndjson(path: str) -> List[Dict[str, Any]]:
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
                print(f"Warning: skipping invalid JSON line in schemes file: {e}")
    print(f"Loaded {len(schemes)} schemes from {path}")
    return schemes

SCHEMES = load_schemes_from_ndjson(SCHEMES_NDJSON_PATH)

# ---------- Heuristics & prescreen ----------
def find_applicable_schemes(customer: Dict[str, Any], schemes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    city_tier = customer.get("city_tier")
    income = customer.get("yearly_income", 0) or 0
    out = []
    for s in schemes:
        allowed_tiers = (s.get("eligibility_rules") or {}).get("allowed_city_tiers") or (s.get("eligibility") or {}).get("city_tiers")
        if allowed_tiers and city_tier and city_tier not in allowed_tiers:
            continue
        min_inc = s.get("min_income", s.get("loan_limits", {}).get("min_amount", 0)) or 0
        max_inc = s.get("max_income", 10**15) or 10**15
        if income < min_inc or income > max_inc:
            continue
        out.append(s)
    return out

def prescreen_customer_against_scheme(customer: Dict[str, Any], scheme: Dict[str, Any]) -> Dict[str, Any]:
    rules = scheme.get("eligibility_rules", {})
    reasons = []
    passed = True

    # DTI
    dti = customer.get("dti_ratio")
    if dti is None:
        reasons.append("dti_ratio missing")
        passed = False
    else:
        max_dti = rules.get("max_dti_ratio")
        if max_dti is not None and dti > max_dti:
            reasons.append(f"dti_ratio {dti} > max_dti {max_dti}")
            passed = False

    # bounced txns
    bounced = customer.get("bounced_txn_count", 0) or 0
    max_bounced = rules.get("max_bounced_txns_last_90d")
    if max_bounced is not None and bounced > max_bounced:
        reasons.append(f"bounced_txn_count {bounced} > allowed {max_bounced}")
        passed = False

    # credit score
    final_score = customer.get("final_credit_score")
    min_score = rules.get("require_final_credit_score_min")
    if min_score is not None:
        if final_score is None:
            reasons.append("final_credit_score missing")
            passed = False
        elif final_score < min_score:
            reasons.append(f"final_credit_score {final_score} < required {min_score}")
            passed = False

    # existing EMI % of income
    monthly_income = (customer.get("yearly_income") or 0) / 12.0
    existing_emi = customer.get("existing_loan_monthly_EMI_total", 0) or 0
    max_emi_pct = rules.get("max_existing_emi_pct_of_income")
    if monthly_income > 0 and max_emi_pct is not None:
        if existing_emi / (monthly_income + 1e-9) > max_emi_pct:
            reasons.append(f"existing EMI {existing_emi} > allowed ratio {max_emi_pct} of monthly income {monthly_income}")
            passed = False

    return {"passed": passed, "reasons": reasons, "checked_rules": rules}

# ---------- OpenAI direct call (fallback) ----------
def call_openai_chat(messages: List[Dict[str, str]], model: str = OPENAI_MODEL, max_tokens: int = 1500, temperature: float = 0.0) -> Dict[str, Any]:
    resp = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature
    )
    return resp

# ---------- Pathway wrapper ----------
def call_pathway_xpack(messages: List[Dict[str, str]], model_name: str = "gpt-4", temperature: float = 0.0, capacity: int = 2):
    """
    Uses Pathway xpack-llm OpenAIChat wrapper to call gpt-4.
    Returns assistant text string.
    """
    try:
        import pathway as pw
        from pathway.xpacks.llm.llms import OpenAIChat
    except Exception as e:
        raise RuntimeError("Pathway or pathway.xpacks.llm not installed. Install with: pip install 'pathway[xpack-llm]'") from e

    # Build a single-row markdown table safely (escape pipes & backticks)
    prompt_parts = []
    for m in messages:
        role = m.get("role", "")
        content = m.get("content", "")
        content_escaped = content.replace("```", "`\u200b``").replace("|", "\\|")
        prompt_parts.append(f"[{role}] {content_escaped}")
    single_prompt = "\n\n".join(prompt_parts)

    md = f"""
| prompt |
|---|
| {single_prompt} |
"""
    table = pw.debug.table_from_markdown(md)

    # Instantiate Pathway wrapper
    model = OpenAIChat(
        model=model_name,
        temperature=temperature,
        capacity=capacity,
        retry_strategy=pw.udfs.ExponentialBackoffRetryStrategy(max_retries=3),
    )

    # Create messages column for the UDF (system + user)
    messages_table = table.select(
        messages=[
            {"role": "system", "content": messages[0]["content"] if len(messages) > 0 else ""},
            {"role": "user", "content": single_prompt}
        ]
    )

    # Apply model
    result_table = messages_table.select(
        prompt=messages_table.prompt,
        response=model(pw.this.messages)
    )

    # Execute and collect one-row result
    rows = pw.debug.compute_and_collect(result_table)
    if not rows:
        raise RuntimeError("Pathway returned no rows.")
    # The wrapper returns a response; attempt to extract assistant text
    resp = rows[0].get("response") or rows[0].get("response_text") or rows[0].get("response_str")
    # If it's dict-like with choices, extract
    if isinstance(resp, dict) and "choices" in resp:
        try:
            return resp["choices"][0].get("message", {}).get("content", "")
        except Exception:
            return json.dumps(resp)
    return resp

# ---------- Robust JSON extraction ----------
def extract_json_from_fenced_block(text: str) -> Dict[str, Any]:
    # prefer ```json fenced blocks
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # other fenced blocks
    m2 = re.search(r"```(?:\w+)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(1))
        except Exception:
            pass
    # fallback: first {...}
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        maybe = text[start:end+1]
        try:
            return json.loads(maybe)
        except Exception:
            for i in range(end, start, -1):
                try:
                    return json.loads(text[start:i+1])
                except Exception:
                    continue
    raise ValueError("No valid JSON found in LLM output.")

# ---------- Build prompt for all passing schemes ----------
def build_prompt_payload_all_passing(customer: Dict[str, Any], neighbors: List[Dict[str, Any]], passing_schemes: List[Dict[str, Any]]) -> Dict[str, Any]:
    system = (
        "You are a careful, auditable financial product analyst. Use ONLY the provided scheme JSONs, the customer JSON, "
        "and the neighbors JSON. Do NOT invent policy or fees. If required additional input (property_value or requested_loan_amount) is missing, return {\"missing_fields\": [...]} in the decision JSON. "
        "Return a human-readable analysis followed by a JSON decision inside a ```json ... ``` fenced block. "
        "The JSON decision must be of shape: {\"eligibility\": bool, \"chosen_product_id\": str|null, \"computed_values\": {...}, \"rationale\": [str], \"audit\": {\"product_ids_considered\": [...], \"issue_dates\": [...]}}. "
        "Show step-by-step numeric calculations (LTV and EMI) and reference neighbor comparisons."
    )

    schemes_compact = [json.dumps(s, separators=(",", ":"), ensure_ascii=False) for s in passing_schemes]
    user_payload = {
        "schemes_considered_count": len(passing_schemes),
        "schemes": schemes_compact,
        "customer": customer,
        "neighbors": neighbors,
        "task": "Choose the best scheme for this customer among the provided schemes (or null) and produce required JSON decision in a ```json ... ``` fence."
    }

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user_payload, indent=2, ensure_ascii=False)}
    ]
    return {"messages": messages}

# ---------- Persistence helpers ----------
async def save_report_async(cust_id: str, report_text: str, decision_obj: Dict[str, Any], raw_llm_response: Dict[str, Any]):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = int(time.time())
    base = os.path.join(OUTPUT_DIR, f"{cust_id}_{timestamp}")
    async with aiofiles.open(base + ".txt", "w", encoding="utf-8") as f:
        await f.write(report_text or "")
    async with aiofiles.open(base + ".decision.json", "w", encoding="utf-8") as f:
        await f.write(json.dumps(decision_obj, indent=2, ensure_ascii=False))
    async with aiofiles.open(base + ".llm_raw.json", "w", encoding="utf-8") as f:
        await f.write(json.dumps(raw_llm_response, indent=2, ensure_ascii=False))
    print(f"Saved: {base}.*")
    return base, timestamp

# ---------- PDF generation ----------
def generate_pdf_report(cust_id: str, timestamp: int, customer: Dict[str, Any], neighbors: List[Dict[str, Any]], human_text: str, decision_obj: Dict[str, Any], output_dir: str = OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    pdf_file = os.path.join(output_dir, f"{cust_id}_{timestamp}.pdf")
    doc = SimpleDocTemplate(pdf_file, pagesize=A4, rightMargin=0.5*inch, leftMargin=0.5*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []
    title_style = ParagraphStyle('title', parent=styles['Heading1'], fontSize=16, alignment=1)
    h2 = ParagraphStyle('h2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#2c5aa0'))
    body = ParagraphStyle('body', parent=styles['BodyText'], fontSize=10, leading=12)

    story.append(Paragraph(f"Customer Report — {cust_id}", title_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph(f"Generated: {datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()}", body))
    story.append(Paragraph(f"Decision summary: {json.dumps(decision_obj.get('eligibility'), ensure_ascii=False)} — chosen: {decision_obj.get('chosen_product_id')}", body))
    story.append(Spacer(1, 0.15*inch))

    # Customer table
    story.append(Paragraph("Customer Data", h2))
    cust_rows = [["Field", "Value"]]
    for k, v in customer.items():
        if isinstance(v, (dict, list)):
            vstr = json.dumps(v, ensure_ascii=False)
        else:
            vstr = str(v)
        cust_rows.append([k, vstr])
    t = Table(cust_rows, colWidths=[2.2*inch, 3.8*inch])
    t.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#2c5aa0')),('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke)]))
    story.append(t)
    story.append(Spacer(1, 0.15*inch))

    # Neighbors
    story.append(Paragraph("Nearest Neighbors (top 10)", h2))
    if neighbors:
        keys = list(neighbors[0].keys())
        neigh_rows = [keys]
        for nb in neighbors:
            row = [json.dumps(nb.get(k, ""), ensure_ascii=False) if isinstance(nb.get(k,""), (dict,list)) else str(nb.get(k,"")) for k in keys]
            neigh_rows.append(row)
        colw = (6.0*inch) / max(1, len(keys))
        t2 = Table(neigh_rows, colWidths=[colw]*len(keys), repeatRows=1)
        t2.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.grey), ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#2c5aa0')),('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke)]))
        story.append(t2)
    else:
        story.append(Paragraph("No neighbors provided.", body))
    story.append(Spacer(1, 0.15*inch))

    # LLM explanation
    story.append(Paragraph("LLM Explanation & Reasoning", h2))
    for para in (human_text or "").split("\n\n"):
        story.append(Paragraph(para.replace("\n", " "), body))
        story.append(Spacer(1, 0.05*inch))

    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph("Decision JSON (audit)", h2))
    story.append(Paragraph("<pre>" + json.dumps(decision_obj, indent=2, ensure_ascii=False) + "</pre>", body))

    doc.build(story)
    return pdf_file

# ---------- Main processing ----------
async def process_customer_pair(nc: NATS, cust_id: str):
    customer = customer_buffer.get(cust_id)
    neighbors_msg = neighbors_buffer.get(cust_id)
    if not customer or not neighbors_msg:
        return
    neighbors = neighbors_msg.get("neighbors", [])

    applicable_schemes = find_applicable_schemes(customer, SCHEMES)
    if not applicable_schemes:
        applicable_schemes = SCHEMES
        print(f"[{cust_id}] No heuristically filtered schemes; using all schemes.")

    # deterministic prescreen: collect all passing schemes
    passing_schemes = []
    prescreen_results = []
    for s in applicable_schemes:
        pres = prescreen_customer_against_scheme(customer, s)
        prescreen_results.append({'product_id': s.get('product_id'), 'scheme_name': s.get('scheme_name'), 'prescreen': pres})
        if pres['passed']:
            passing_schemes.append(s)

    # choose what to send to LLM
    to_send_schemes = passing_schemes if passing_schemes else applicable_schemes[:3]

    payload = build_prompt_payload_all_passing(customer, neighbors, to_send_schemes)
    messages = payload['messages']

    # call LLM via Pathway or OpenAI
    try:
        if USE_PATHWAY_XPACK:
            llm_text = call_pathway_xpack(messages, model_name=OPENAI_MODEL, temperature=0.0, capacity=2)
            raw_resp = {"pathway_response_text": llm_text}
        else:
            raw_resp = call_openai_chat(messages, model=OPENAI_MODEL, max_tokens=1500, temperature=0.0)
            choices = raw_resp.get("choices", [])
            llm_text = choices[0].get("message", {}).get("content", "") if choices else ""
    except Exception as e:
        print(f"[{cust_id}] LLM call error: {e}")
        base, ts = await save_report_async(cust_id, f"LLM call failed: {e}", {"error": str(e)}, {"error": str(e)})
        customer_buffer.pop(cust_id, None)
        neighbors_buffer.pop(cust_id, None)
        return

    # extract JSON decision
    try:
        decision_obj = extract_json_from_fenced_block(llm_text)
    except Exception as e:
        decision_obj = {"error_extracting_json": str(e), "prescreen_summary": prescreen_results}
        print(f"[{cust_id}] JSON extraction failed: {e}")

    # embed prescreen summary and product list
    decision_obj.setdefault('prescreen_summary', prescreen_results)
    decision_obj.setdefault('product_ids_considered', [s.get('product_id') for s in to_send_schemes])

    # save text + json + raw
    base, timestamp = await save_report_async(cust_id, llm_text, decision_obj, raw_resp)

    # generate PDF
    try:
        pdf_path = generate_pdf_report(cust_id, timestamp, customer, neighbors, llm_text, decision_obj, output_dir=OUTPUT_DIR)
        print(f"[{cust_id}] PDF generated: {pdf_path}")
    except Exception as e:
        print(f"[{cust_id}] Failed to generate PDF: {e}")

    # publish summary to NATS
    try:
        result_payload = {"cust_id": cust_id, "timestamp": timestamp, "decision": decision_obj}
        await nc.publish(RESULT_TOPIC, json.dumps(result_payload).encode("utf-8"))
        print(f"[{cust_id}] Published decision to {RESULT_TOPIC}")
    except Exception as e:
        print(f"[{cust_id}] Failed to publish decision: {e}")

    # cleanup
    customer_buffer.pop(cust_id, None)
    neighbors_buffer.pop(cust_id, None)

# ---------- NATS message handlers ----------
async def customer_msg_handler(msg):
    try:
        data = json.loads(msg.data.decode())
    except Exception as e:
        print("Invalid JSON on customer topic:", e)
        return
    cust_id = data.get("cust_id")
    if not cust_id:
        print("customer message missing cust_id, ignoring.")
        return
    customer_buffer[cust_id] = data
    print(f"[{cust_id}] Received customer update.")
    if cust_id in neighbors_buffer:
        await process_customer_pair(nc_global, cust_id)

async def neighbors_msg_handler(msg):
    try:
        data = json.loads(msg.data.decode())
    except Exception as e:
        print("Invalid JSON on neighbors topic:", e)
        return
    cust_id = data.get("cust_id")
    if not cust_id:
        print("neighbors message missing cust_id, ignoring.")
        return
    neighbors_buffer[cust_id] = data
    print(f"[{cust_id}] Received neighbors update (count={len(data.get('neighbors', []))}).")
    if cust_id in customer_buffer:
        await process_customer_pair(nc_global, cust_id)

# ---------- Main run ----------
async def run(loop):
    global nc_global, nc
    nc = NATS()
    nc_global = nc
    try:
        await nc.connect(servers=[NATS_SERVERS], io_loop=loop)
    except Exception as e:
        print("Failed to connect to NATS:", e)
        return

    await nc.subscribe(CUSTOMER_TOPIC, cb=lambda msg: asyncio.create_task(customer_msg_handler(msg)))
    await nc.subscribe(NEIGHBORS_TOPIC, cb=lambda msg: asyncio.create_task(neighbors_msg_handler(msg)))
    print(f"Subscribed to {CUSTOMER_TOPIC} and {NEIGHBORS_TOPIC} on {NATS_SERVERS}")

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await nc.drain()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run(loop))
    except KeyboardInterrupt:
        print("Shutting down.")
