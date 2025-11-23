# MASTERFILENode/logic.py
import pathway as pw
import numpy as np

def update_customer_profile(customer_state, transactions):
    """
    This function defines the logic for updating a customer's profile
    based on a stream of their transactions. It's designed to be used
    with Pathway's `update` method on a stateful table.
    
    Args:
        customer_state: A Pathway Table representing the current state of a single customer.
        transactions: A Pathway Table representing all new transactions for that customer.
    """
    
    # --- Step 1: Iterate through new transactions to update raw 'vitals' ---
    # We will aggregate changes from all new transactions for this customer.
    
    # Calculate the sum of transaction amounts to update the balance
    total_amount_change = pw.this.sum(transactions.txn_amount)
    
    # Count bounced transactions
    bounced_count_change = pw.this.sum(transactions.bounced_flag.cast(int))
    
    # Count successful debits (for credit score reward)
    successful_debits_count = pw.this.sum(
        ((transactions.txn_amount < 0) & (transactions.bounced_flag == False)).cast(int)
    )
    
    max_txn_time = pw.this.max(transactions.txn_datetime)

    # Calculate total spend by category
    fuel_spend_change = pw.this.sum(
        pw.if_else(transactions.txn_category == "Fuel", abs(transactions.txn_amount), 0)
    )
    transport_spend_change = pw.this.sum(
        pw.if_else(transactions.txn_category == "Transport", abs(transactions.txn_amount), 0)
    )
    investment_debit_change = pw.this.sum(
        pw.if_else(transactions.txn_category == "Investment", abs(transactions.txn_amount), 0)
    )

    # --- Step 2: Apply updates to the customer state ---
    
    # Update balance and volume trackers
    current_balance = customer_state.final_avg_monthly_balance + total_amount_change
    vol_increase = pw.this.sum(abs(transactions.txn_amount))
    
    customer_state.final_avg_monthly_balance = current_balance
    customer_state.volTransLastStreamed_home += vol_increase
    customer_state.volTransLastStreamed_car += vol_increase
    customer_state.volTransLastStreamed_elss += vol_increase
    customer_state.volTransLastStreamed_nifty50 += vol_increase
    
    # Update credit score (using a simplified version of the simulation's logic)
    # The min/max logic is slightly different in SQL-like operations.
    score_penalty = bounced_count_change * 10
    score_reward = successful_debits_count * 0.5
    customer_state.final_credit_score = customer_state.final_credit_score - score_penalty + score_reward
    
    # Update rolling counts with decay (approximated for streaming)
    # A simple increment is more robust in many streaming setups. We will add decay later if needed.
    decay = 0.98 
    num_new_txns = pw.this.count(transactions.customer_id)
    customer_state.txn_count_last_30d = customer_state.txn_count_last_30d * (decay**num_new_txns) + num_new_txns
    customer_state.bounced_txn_count += bounced_count_change
    customer_state.monthly_fuel_spend = customer_state.monthly_fuel_spend * (decay**num_new_txns) + fuel_spend_change
    customer_state.monthly_transport_service_spend = customer_state.monthly_transport_service_spend * (decay**num_new_txns) + transport_spend_change
    customer_state.avg_monthly_investment_debit = customer_state.avg_monthly_investment_debit * (decay**num_new_txns) + investment_debit_change

    customer_state.last_update_timestamp = max_txn_time
    
    # --- Step 3: Re-calculate derived features ---
    monthly_income = customer_state.yearly_income / 12
    customer_state.savings_rate = current_balance / (monthly_income + 1)
    customer_state.txn_intensity = customer_state.txn_count_last_30d / (customer_state.yearly_income / 10000 + 1)
    customer_state.score_x_log_income = customer_state.final_credit_score * np.log1p(customer_state.yearly_income)
    
    return customer_state