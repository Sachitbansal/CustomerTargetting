import pandas as pd
import os

def analyze_car_loans():
    file_path = 'customers_master_multi_product.csv'
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: '{file_path}' not found.")
        print("Please run your generate_data.py script first to create the dataset.")
        return

    print("Loading data...")
    df = pd.read_csv(file_path)
    
    total_customers = len(df)
    opted_count = df['opted_car_loan'].sum()
    opted_pct = (opted_count / total_customers) * 100

    print("-" * 50)
    print(f"TOTAL ANALYSIS (N={total_customers})")
    print("-" * 50)
    print(f"Customers opting for Car Loan: {opted_count}")
    print(f"Percentage of Total Base:      {opted_pct:.2f}%")
    print("-" * 50)

    # --- BREAKDOWN 1: IMPACT OF EXISTING LOANS ---
    # The logic applies a -5 penalty for existing loans. 
    # Let's see how many overcame that penalty.
    print("\nBREAKDOWN BY EXISTING AUTO LOAN STATUS")
    print("(Logic: Existing loans get a -5 score penalty)")
    print("-" * 50)
    
    group_existing = df.groupby('has_existing_auto_loan')['opted_car_loan'].agg(['count', 'sum', 'mean'])
    group_existing.columns = ['Total Customers', 'Opted Count', 'Conversion Rate']
    group_existing.index = ['No Existing Car', 'Has Existing Car']
    print(group_existing)

    # --- BREAKDOWN 2: THE "UPGRADE BUYERS" ---
    # People with existing loans who bought anyway (likely High Income/High Credit)
    print("\n\nANALYSIS OF 'UPGRADE BUYERS' (Existing Car + Opted Again)")
    print("-" * 50)
    
    upgrade_buyers = df[(df['has_existing_auto_loan'] == 1) & (df['opted_car_loan'] == 1)]
    avg_income = upgrade_buyers['yearly_income'].mean()
    avg_score = upgrade_buyers['final_credit_score'].mean()
    
    print(f"Number of Upgrade Buyers: {len(upgrade_buyers)}")
    print(f"Their Avg Yearly Income:  ₹{avg_income:,.2f}")
    print(f"Their Avg Credit Score:   {avg_score:.1f}")
    print("Insight: These customers overcame the -5 penalty because")
    print("High Income (>900k) gave +2 and High Score (>720) gave +3.")

    # --- BREAKDOWN 3: THE "FIRST TIME" BUYERS ---
    print("\n\nANALYSIS OF 'FIRST TIME BUYERS' (No Existing Car)")
    print("-" * 50)
    first_timers = df[(df['has_existing_auto_loan'] == 0)]
    ft_opted = first_timers['opted_car_loan'].sum()
    ft_rate = first_timers['opted_car_loan'].mean()
    
    print(f"Total First Timers: {len(first_timers)}")
    print(f"Opted Count:        {ft_opted}")
    print(f"Conversion Rate:    {ft_rate:.2%}")

if __name__ == "__main__":
    analyze_car_loans()