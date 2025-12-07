#!/usr/bin/env python3
"""
Enhanced Car Loan Tester with VAPI Calling and LLM Sentiment Analysis

✔ Filters positive predictions from NATS
✔ Loads customer data from MASTERFILE
✔ Matches customers with loan offers
✔ Makes VAPI calls to customers
✔ Collects call transcripts
✔ Analyzes transcript with OpenAI for loan decision
✔ Streams feedback back to NATS
"""

import pathway as pw
import numpy as np
import json
import os
import csv
import requests
import threading
import queue
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# =======================================================
# LOGGING
# =======================================================
CURRENT_DIR = Path(__file__).resolve().parent
LOG_FILE = CURRENT_DIR / "caller_node.log"

def log(msg: str):
    """Simple logging function - prints and writes to file"""
    line = f"[CallerNode] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# =======================================================
# CONFIGURATION
# =======================================================
NATS_URI = "nats://localhost:4222"
INPUT_TOPIC = "leads.callCarLoan"
OUTPUT_TOPIC = "feedback.carLoan"

ROOT = CURRENT_DIR.parent
import sys
sys.path.append(str(ROOT))

CALL_TRANSCRIPTS_JSON = CURRENT_DIR / "call_transcripts.json"

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "1"))

# VAPI Configuration
VAPI_API_KEY = "704a9601-3f91-432e-83ec-f275d938482c"
VAPI_BASE_URL = "https://api.vapi.ai"
VAPI_PHONE_NUMBER_ID = "ed8ca566-93de-4687-b10e-6092222d506b"

# OpenAI Configuration for Sentiment Analysis
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = "https://api.openai.com/v1"

# Hardcoded phone number for testing
HARDCODED_PHONE = os.getenv("HARDCODED_PHONE")

# Global data structures
call_queue = queue.Queue()
customer_data_cache = {}
loan_offers_cache = []
call_transcripts = {}
call_in_progress_lock = threading.Lock()  # Lock to ensure one call at a time

# =======================================================
# SCHEMA
# =======================================================
class PredictionSchema(pw.Schema):
    customer_id: str
    predicted_eligible: bool
    cluster_id: int
    confidence_score: float
    similar_customers: str

# =======================================================
# REDIS CONNECTION
# =======================================================
import redis
import pickle

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=False
)

# =======================================================
# DATA LOADING (FROM REDIS)
# =======================================================
def load_masterfile():
    """Load customer master data from Redis"""
    global customer_data_cache
    try:
        # Try to ping Redis first
        redis_client.ping()
        
        # Load from Redis hash 'masterfile:data'
        serialized = redis_client.get('masterfile:data')
        if serialized is None:
            log(f"❌ MASTERFILE not found in Redis. Run load_csvs_to_redis.py first.")
            return
        
        import pandas as pd
        df = pickle.loads(serialized)
        
        # Convert DataFrame to dict cache
        for _, row in df.iterrows():
            customer_data_cache[row['customer_id']] = row.to_dict()
        
        log(f"✔ Loaded {len(customer_data_cache)} customer records from Redis (masterfile:data)")
    except redis.ConnectionError as e:
        log(f"❌ Redis connection failed: {e}")
    except Exception as e:
        log(f"❌ Error loading MASTERFILE from Redis: {e}")

def load_loan_offers():
    """Load loan offers from Redis"""
    global loan_offers_cache
    try:
        # Load from Redis key 'loan_offers:data'
        serialized = redis_client.get('loan_offers:data')
        if serialized is None:
            log(f"❌ Loan offers not found in Redis. Run load_csvs_to_redis.py first.")
            return
        
        import pandas as pd
        df = pickle.loads(serialized)
        
        # Convert DataFrame to list of dicts
        loan_offers_cache = df.to_dict('records')
        
        log(f"✔ Loaded {len(loan_offers_cache)} loan offers from Redis (loan_offers:data)")
    except redis.ConnectionError as e:
        log(f"❌ Redis connection failed: {e}")
    except Exception as e:
        log(f"❌ Error loading loan offers from Redis: {e}")

# =======================================================
# LOAN MATCHING
# =======================================================
def calculate_loan_score(customer: Dict, loan: Dict) -> float:
    """Calculate matching score between customer and loan"""
    score = 0.0
    
    # Credit score match (35 points)
    if 'credit_score' in customer and 'min_credit_score' in loan:
        try:
            customer_credit = int(customer.get('credit_score', 0))
            min_credit = int(loan.get('min_credit_score', 0))
            if customer_credit >= min_credit:
                score += 30
                score += min(20, (customer_credit - min_credit) / 10)
        except ValueError:
            pass
    
    # Annual income match (25 points)
    if 'annual_income' in customer and 'min_income' in loan:
        try:
            customer_income = float(customer.get('annual_income', 0))
            min_income = float(loan.get('min_income', 0))
            if customer_income >= min_income:
                score += 25
                income_ratio = customer_income / max(min_income, 1)
                score += min(10, (income_ratio - 1) * 5)
        except ValueError:
            pass
    
    # Interest rate (15 points)
    if 'interest_rate' in loan:
        try:
            rate = float(loan.get('interest_rate', 10))
            score += max(0, (15 - rate) * 2)
        except ValueError:
            pass
    
    return score

def find_top_loans(customer: Dict) -> list:
    """Find top 3 matching loans for customer"""
    if not loan_offers_cache:
        return []
    
    loan_purpose = customer.get('loan_purpose', 'auto purchase').lower()
    
    # Filter by purpose
    matching_loans = [
        loan for loan in loan_offers_cache 
        if loan.get('loan_purpose', '').lower() == loan_purpose
    ]
    
    if not matching_loans:
        matching_loans = [
            loan for loan in loan_offers_cache 
            if 'auto' in loan.get('loan_purpose', '').lower()
        ]
    
    # Score and sort
    scored_loans = []
    for loan in matching_loans:
        score = calculate_loan_score(customer, loan)
        scored_loans.append({'loan': loan, 'score': score})
    
    scored_loans.sort(key=lambda x: x['score'], reverse=True)
    return [item['loan'] for item in scored_loans[:3]]

# =======================================================
# OPENAI SENTIMENT ANALYSIS
# =======================================================
def analyze_transcript_sentiment(transcript: str, customer_name: str) -> int:
    """
    Analyze call transcript using OpenAI to determine if customer wants the loan.
    Returns: 1 if customer wants loan, 0 if not
    """
    log(f"\n  🤖 Analyzing transcript with OpenAI...")
    
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Structured output request
        request_body = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": """You are an expert at analyzing sales call transcripts to determine customer intent.
Your task is to analyze a car loan sales call transcript and determine if the customer wants to proceed with the loan.

Look for explicit signals such as:
- Direct YES/NO responses when asked about proceeding
- Positive phrases like "I'm interested", "Let's move forward", "Sign me up", "Sounds good"
- Negative phrases like "Not interested", "I'll pass", "Maybe later", "Need to think about it"
- Questions about next steps (indicates interest)
- Requests for more information (indicates interest)
- Concerns about affordability or terms (indicates hesitation/rejection)

Return your analysis in JSON format with:
- decision: 1 if customer wants the loan, 0 if they don't
- confidence: a number between 0.0 and 1.0 indicating your confidence
- reasoning: brief explanation of your decision"""
                },
                {
                    "role": "user",
                    "content": f"""Analyze this car loan sales call transcript for customer {customer_name}:

TRANSCRIPT:
{transcript}

Based on this transcript, does the customer want to proceed with the car loan?
Provide your analysis in the specified JSON format."""
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "loan_decision_analysis",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "decision": {
                                "type": "integer",
                                "description": "1 if customer wants the loan, 0 if not"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence score between 0.0 and 1.0"
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Brief explanation of the decision"
                            }
                        },
                        "required": ["decision", "confidence", "reasoning"],
                        "additionalProperties": False
                    }
                }
            },
            "temperature": 0.3
        }
        
        response = requests.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            headers=headers,
            json=request_body,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            analysis = json.loads(content)
            
            decision = analysis.get('decision', 0)
            confidence = analysis.get('confidence', 0.0)
            reasoning = analysis.get('reasoning', 'No reasoning provided')
            
            log(f"  ✔ OpenAI Analysis Complete:")
            log(f"     Decision: {decision} ({'WANTS LOAN' if decision == 1 else 'DOES NOT WANT LOAN'})")
            log(f"     Confidence: {confidence:.2f}")
            log(f"     Reasoning: {reasoning}")
            
            return decision
        else:
            log(f"  ❌ OpenAI API error: {response.status_code}")
            log(f"     Response: {response.text}")
            # Default to 0 (no loan) on API error
            return 0
            
    except Exception as e:
        log(f"  ❌ Error analyzing transcript: {e}")
        # Default to 0 (no loan) on error
        return 0

# =======================================================
# VAPI INTEGRATION
# =======================================================
def generate_call_prompt(customer: Dict, top_loans: list) -> str:
    """Generate dynamic prompt for VAPI assistant"""
    customer_name = customer.get('name', 'valued customer')
    loan_purpose = customer.get('loan_purpose', 'auto loan')
    
    prompt = f"""You are a professional loan advisor calling {customer_name} about their car loan application.
You are friendly, professional, and genuinely interested in helping them.

CUSTOMER CONTEXT:
- Name: {customer_name}
- Phone: {HARDCODED_PHONE}
- Loan Purpose: {loan_purpose}
- Annual Income: ${float(customer.get('annual_income', 0)):,.0f}
- Credit Score: {customer.get('credit_score', 'N/A')}
- Employment: {customer.get('employment_status', 'N/A')}

TOP RECOMMENDED LOANS:
"""
    
    for idx, loan in enumerate(top_loans, 1):
        prompt += f"""
{idx}. {loan.get('loan_name', 'Loan Offer')}
   - Interest Rate: {loan.get('interest_rate', 'N/A')}% APR
   - Maximum Amount: ${float(loan.get('max_loan_amount', 0)):,.0f}
   - Loan Term: {loan.get('loan_term', 'N/A')} months
   - Features: {loan.get('features', 'N/A')}
"""
    
    prompt += f"""
CALL OBJECTIVE:
1. Greet warmly and introduce yourself as their loan advisor
2. Confirm you're calling about their {loan_purpose} inquiry
3. Present the top loan options that match their profile
4. Answer questions about rates, terms, and eligibility
5. ASK CLEARLY: "Are you interested in proceeding with this car loan?"
6. Wait for their YES or NO response
7. Thank them for their time

CONVERSATION GUIDELINES:
- Be conversational and warm, not scripted
- Keep the call focused (3-5 minutes)
- Listen carefully to their response
- If YES: Congratulate and explain next steps
- If NO: Thank them and offer to follow up later
- End the call professionally

Remember: Your goal is to present options and get a clear YES or NO decision.
"""
    
    return prompt

def create_vapi_assistant(prompt: str, customer_name: str) -> Optional[Dict]:
    """Create VAPI assistant"""
    try:
        assistant_config = {
            "name": f"Car Loan Advisor for {customer_name}",
            "model": {
                "provider": "openai",
                "model": "gpt-4",
                "messages": [
                    {
                        "role": "system",
                        "content": prompt
                    }
                ],
                "temperature": 0.7
            },
            "voice": {
                "provider": "deepgram",
                "voiceId": "asteria"
            },
            "firstMessage": f"Hello, may I speak with {customer_name}? This is calling from the bank regarding your car loan application.",
            "recordingEnabled": True,
            "endCallFunctionEnabled": True,
            "endCallMessage": "Thank you for your time. Have a great day!"
        }
        
        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{VAPI_BASE_URL}/assistant",
            headers=headers,
            json=assistant_config,
            timeout=30
        )
        
        if response.status_code == 201:
            log(f"  ✔ Assistant created successfully")
            return response.json()
        else:
            log(f"  ❌ Failed to create assistant: {response.status_code}")
            return None
    except Exception as e:
        log(f"  ❌ Error creating assistant: {e}")
        return None

def make_call(assistant_id: str, phone_number: str, customer_name: str) -> Optional[Dict]:
    """Initiate phone call via VAPI"""
    try:
        call_config = {
            "assistantId": assistant_id,
            "phoneNumberId": VAPI_PHONE_NUMBER_ID,
            "customer": {
                "number": phone_number,
                "name": customer_name
            }
        }
        
        headers = {
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{VAPI_BASE_URL}/call/phone",
            headers=headers,
            json=call_config,
            timeout=30
        )
        
        if response.status_code == 201:
            log(f"  ✔ Call initiated successfully")
            return response.json()
        else:
            log(f"  ❌ Failed to initiate call: {response.status_code}")
            return None
    except Exception as e:
        log(f"  ❌ Error making call: {e}")
        return None

def wait_for_call_completion(call_id: str, max_wait_time: int = 300) -> Optional[Dict]:
    """Poll VAPI API until call is complete"""
    headers = {
        "Authorization": f"Bearer {VAPI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    log(f"  ⏳ Waiting for call to complete (polling every 5 seconds)...")
    
    start_time = time.time()
    poll_interval = 5  # Check every 5 seconds
    
    while True:
        try:
            response = requests.get(
                f"{VAPI_BASE_URL}/call/{call_id}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                call_data = response.json()
                call_status = call_data.get('status', 'unknown')
                
                log(f"     Call status: {call_status}")
                
                # Check if call has ended
                if call_status in ['ended', 'completed', 'failed', 'busy', 'no-answer']:
                    log(f"  ✔ Call ended with status: {call_status}")
                    return call_data
                
                # Check if max wait time exceeded
                elapsed = time.time() - start_time
                if elapsed > max_wait_time:
                    log(f"  ⚠ Max wait time ({max_wait_time}s) exceeded, assuming call ended")
                    return call_data
                
                # Wait before next poll
                time.sleep(poll_interval)
            else:
                log(f"  ⚠ Failed to fetch call status: {response.status_code}")
                return None
                
        except Exception as e:
            log(f"  ⚠ Error polling call status: {e}")
            return None

def get_call_transcript(call_id: str) -> Optional[str]:
    """Fetch call transcript from VAPI after call completes"""
    try:
        # Wait for call to actually complete
        call_data = wait_for_call_completion(call_id)
        
        if not call_data:
            log(f"  ⚠ Could not get call data")
            return None
        
        # Extract transcript
        log(f"  📄 Extracting transcript from completed call...")
        transcript = call_data.get('transcript', '')
        
        if isinstance(transcript, list):
            transcript = ' '.join([msg.get('content', '') for msg in transcript])
        
        if transcript:
            log(f"  ✔ Transcript retrieved ({len(transcript)} chars)")
        else:
            log(f"  ⚠ Transcript is empty")
            
        return transcript if transcript else "Transcript not available"
        
    except Exception as e:
        log(f"  ⚠ Error fetching transcript: {e}")
        return None

def save_transcript(customer_id: str, transcript: str, decision: int):
    """Save call transcript to JSON file"""
    global call_transcripts
    call_transcripts[customer_id] = {
        'customer_id': customer_id,
        'transcript': transcript,
        'decision': decision,
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        with open(CALL_TRANSCRIPTS_JSON, 'w') as f:
            json.dump(call_transcripts, f, indent=2)
        log(f"  ✔ Transcript saved ({len(transcript)} chars, decision={decision})")
    except Exception as e:
        log(f"  ⚠ Error saving transcript: {e}")

# =======================================================
# CALL PROCESSING
# =======================================================
def process_customer_call(customer_id: str, customer_data: Dict) -> int:
    """Process a single customer call and return decision (1=bought, 0=rejected)"""
    log(f"\n{'='*70}")
    log(f"📞 Processing Customer {customer_id}")
    log(f"{'='*70}")
    
    try:
        log(f"  👤 Name: {customer_data.get('name')}")
        log(f"  📱 Phone: {HARDCODED_PHONE} (hardcoded for testing)")
        log(f"  💼 Loan Purpose: {customer_data.get('loan_purpose')}")
        log(f"  💰 Annual Income: ${float(customer_data.get('annual_income', 0)):,.0f}")
        log(f"  ⭐ Credit Score: {customer_data.get('credit_score')}")
        
        # Find matching loans
        log(f"\n  🔍 Finding matching loans...")
        top_loans = find_top_loans(customer_data)
        
        if not top_loans:
            log(f"  ⚠ No matching loans found. Defaulting to decision=0")
            return 0
        
        log(f"  ✔ Found {len(top_loans)} matching loans")
        for idx, loan in enumerate(top_loans, 1):
            log(f"     {idx}. {loan.get('loan_name')} - {loan.get('interest_rate')}% APR")
        
        # Generate prompt
        log(f"\n  📝 Generating call script...")
        prompt = generate_call_prompt(customer_data, top_loans)
        
        # Create assistant
        log(f"  🤖 Creating VAPI assistant...")
        assistant = create_vapi_assistant(prompt, customer_data.get('name', 'Customer'))
        
        if not assistant:
            log(f"  ⚠ Failed to create assistant. Defaulting to decision=0")
            return 0
        
        assistant_id = assistant.get('id')
        
        # Make call with hardcoded phone number
        log(f"\n  📱 Initiating call to {HARDCODED_PHONE}...")
        call = make_call(assistant_id, HARDCODED_PHONE, customer_data.get('name', 'Customer'))
        
        if not call:
            log(f"  ⚠ Failed to initiate call. Defaulting to decision=0")
            return 0
        
        call_id = call.get('id')
        call_status = call.get('status', 'initiated')
        
        log(f"  ✔ Call ID: {call_id}")
        log(f"  ✔ Status: {call_status}")
        
        # Fetch transcript (includes waiting for call completion)
        log(f"\n  📄 Fetching call transcript...")
        transcript = get_call_transcript(call_id)
        
        if not transcript or transcript == "Transcript not available":
            log(f"  ⚠ Transcript not available. Defaulting to decision=0")
            save_transcript(customer_id, transcript or "Not available", 0)
            return 0
        
        # Analyze transcript with OpenAI
        decision = analyze_transcript_sentiment(transcript, customer_data.get('name', 'Customer'))
        
        # Save transcript with decision
        save_transcript(customer_id, transcript, decision)
        
        log(f"{'='*70}\n")
        
        return decision
        
    except Exception as e:
        log(f"  ❌ Error processing customer {customer_id}: {e}")
        return 0

def calling_agent_worker():
    """Worker thread that processes the call queue - ONE CALL AT A TIME"""
    log("\n🎯 Calling Agent Worker Started")
    log("   Processing ONE call at a time - queue updates in background\n")
    
    while True:
        try:
            # Wait for a customer in the queue (blocking)
            customer_id, customer_data = call_queue.get()
            
            log(f"📥 Picked customer {customer_id} from TOP of queue")
            log(f"   Current queue size: {call_queue.qsize()}")
            log(f"🔒 Starting call - no other calls until this completes\n")
            
            # Acquire lock and process the call
            with call_in_progress_lock:
                # Process the entire call (includes waiting for call + LLM analysis)
                decision = process_customer_call(customer_id, customer_data)
                
                # Store decision
                customer_data['_decision'] = decision
            
            # Mark this customer as done (removes from queue)
            call_queue.task_done()
            
            log(f"✅ Call completed for customer {customer_id} | Decision: {decision}")
            log(f"🔓 Customer removed from queue")
            log(f"   Remaining in queue: {call_queue.qsize()}")
            
            # Wait 5 seconds before picking next customer
            if call_queue.qsize() > 0:
                log(f"⏳ Waiting 5 seconds before next call...\n")
                time.sleep(5)
            else:
                log(f"   Queue empty - waiting for new customers...\n")
            
        except Exception as e:
            log(f"❌ Error in calling agent worker: {e}")
            try:
                call_queue.task_done()
            except:
                pass
            time.sleep(5)

# =======================================================
# FEEDBACK SIMULATOR
# =======================================================
class FeedbackSimulator:
    """Handles feedback generation"""
    
    def __init__(self):
        self.total_processed = 0
        self.decisions_cache = {}
    
    def get_decision(self, customer_id: str) -> int:
        return self.decisions_cache.get(customer_id, 0)
    
    def store_decision(self, customer_id: str, decision: int):
        self.decisions_cache[customer_id] = decision
        self.total_processed += 1

simulator = FeedbackSimulator()

# =======================================================
# PATHWAY PIPELINE
# =======================================================
def run():
    log("═══════════════════════════════════════════════")
    log("   ENHANCED CAR LOAN TESTER WITH LLM ANALYSIS  ")
    log("═══════════════════════════════════════════════")
    log(f"Input Topic:    {INPUT_TOPIC}")
    log(f"Output Topic:   {OUTPUT_TOPIC}")
    log(f"Data Source:    Redis @ {REDIS_HOST}:{REDIS_PORT} (db={REDIS_DB})")
    log(f"Log File:       {LOG_FILE}")
    log(f"Transcripts:    {CALL_TRANSCRIPTS_JSON}")
    log(f"OpenAI Model:   gpt-4o-mini (with structured output)")
    log("═══════════════════════════════════════════════\n")
    
    # Load data
    load_masterfile()
    load_loan_offers()
    
    # Start calling agent worker thread
    worker_thread = threading.Thread(target=calling_agent_worker, daemon=True)
    worker_thread.start()
    log("✔ Calling agent worker thread started\n")
    
    # Read predictions from NATS
    all_predictions = pw.io.nats.read(
        uri=NATS_URI,
        topic=INPUT_TOPIC,
        format="json",
        schema=PredictionSchema
    )
    
    log(f"✔ LISTENING TO: {INPUT_TOPIC}")
    log(f"✔ Listening for car loan predictions...\n")
    
    # Filter only positive predictions
    positive_predictions = all_predictions.filter(pw.this.predicted_eligible == True)
    
    log(f"✔ FILTERING: Only customers with predicted_eligible=True")
    
    # Process positive predictions
    @pw.udf
    def process_positive_prediction(customer_id: str) -> str:
        customer_data = customer_data_cache.get(customer_id)
        
        if customer_data:
            call_queue.put((customer_id, customer_data.copy()))
            log(f"➕ Added customer {customer_id} to call queue (Queue size: {call_queue.qsize()})")
            
            # Wait for decision from calling agent (will be populated by worker thread)
            # The decision will be determined by LLM analysis
            decision = simulator.get_decision(customer_id)
            
            return f"{customer_id}|{decision}"
        else:
            log(f"⚠ Customer {customer_id} not found in MASTERFILE")
            return f"{customer_id}|0"
    
    # Apply processing
    with_decision = positive_predictions.select(
        customer_id=pw.this.customer_id,
        predicted_eligible=pw.this.predicted_eligible,
        cluster_id=pw.this.cluster_id,
        confidence_score=pw.this.confidence_score,
        similar_customers=pw.this.similar_customers,
        decision_str=process_positive_prediction(pw.this.customer_id)
    )
    
    # Parse decision string for feedback
    feedback_data = with_decision.select(
        customer_id=pw.apply_with_type(
            lambda s: s.split('|')[0],
            str,
            pw.this.decision_str
        ),
        custBoughtLoanOrNot=pw.apply_with_type(
            lambda s: bool(int(s.split('|')[1])),
            bool,
            pw.this.decision_str
        )
    )
    
    log(f"✔ STREAMING TO: {OUTPUT_TOPIC}")
    log(f"✔ Streaming feedback to '{OUTPUT_TOPIC}'...\n")
    
    # Write feedback to NATS
    pw.io.nats.write(
        feedback_data,
        uri=NATS_URI,
        topic=OUTPUT_TOPIC,
        format="json"
    )
    
    log("\n✔ Enhanced Tester Node with LLM Analysis is running.\n")
    log("=" * 60)
    log("PIPELINE FLOW:")
    log(f"  1. Listen to predictions on: {INPUT_TOPIC}")
    log(f"  2. Filter ONLY positive predictions (predicted_eligible=True)")
    log(f"  3. Fetch customer details from Redis")
    log(f"  4. Add customer to call queue")
    log(f"  5. Calling agent processes queue ONE AT A TIME")
    log(f"  6. Make VAPI call and collect transcript")
    log(f"  7. Analyze transcript with OpenAI LLM (structured output)")
    log(f"  8. Get decision (1=wants loan, 0=doesn't want loan)")
    log(f"  9. Stream feedback to: {OUTPUT_TOPIC}")
    log(f" 10. Save transcripts to: {CALL_TRANSCRIPTS_JSON}")
    log("=" * 60 + "\n")
    
    pw.run()

if __name__ == "__main__":
    run()