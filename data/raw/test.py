import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix, mean_squared_error
import matplotlib.pyplot as plt
import seaborn as sns

# -----------------------------
# STEP 1: Load Data
# -----------------------------
print("Loading data...")
account = pd.read_csv("account.asc", sep=";")
card = pd.read_csv("card.asc", sep=";")
client = pd.read_csv("client.asc", sep=";")
disp = pd.read_csv("disp.asc", sep=";")
district = pd.read_csv("district.asc", sep=";")
district.rename(columns={"A1": "district_id"}, inplace=True)
loan = pd.read_csv("loan.asc", sep=";")
order = pd.read_csv("order.asc", sep=";")
trans = pd.read_csv("trans.asc", sep=";", low_memory=False)
print(f"account shape: {account.shape}")
print(f"client shape: {client.shape}")
print(f"disp shape: {disp.shape}")
print(f"district shape: {district.shape}")
print(f"loan shape: {loan.shape}")
print(f"trans shape: {trans.shape}")

# -----------------------------
# STEP 2: Merge Based on ER Diagram
# -----------------------------
print("Merging tables...")
data = disp.merge(client, on="client_id", how="left")
data = data.merge(account, on="account_id", how="left", suffixes=("_client", "_account"))
if "district_id_client" in data.columns and "district_id_account" in data.columns:
    data["district_id"] = data["district_id_client"].fillna(data["district_id_account"])
    data.drop(columns=["district_id_client", "district_id_account"], inplace=True)
elif "district_id_client" in data.columns:
    data["district_id"] = data["district_id_client"]
    data.drop(columns=["district_id_client"], inplace=True)
elif "district_id_account" in data.columns:
    data["district_id"] = data["district_id_account"]
    data.drop(columns=["district_id_account"], inplace=True)
data = data.merge(district, on="district_id", how="left", suffixes=("", "_district"))
data = data.merge(loan, on="account_id", how="left", suffixes=("", "_loan"))
print(f"merged shape after loan: {data.shape}")
print("Aggregating transaction data...")
trans_summary = trans.groupby("account_id").agg({
    "amount": ["mean", "sum", "count"],
    "balance": ["mean", "max", "min"]
})
trans_summary.columns = ['_'.join(col) for col in trans_summary.columns]
trans_summary.reset_index(inplace=True)
data = data.merge(trans_summary, on="account_id", how="left")
print(f"merged shape after trans: {data.shape}")

# -----------------------------
# STEP 3: Feature Engineering
# -----------------------------
print("Creating target variables...")
data["loan_taker"] = data["loan_id"].notnull().astype(int)
data["loan_amount"] = data["amount"].fillna(0)
data["balance_per_txn"] = data["balance_mean"] / (data["amount_count"] + 1)
print(f"Target (loan_taker) counts:\n{data['loan_taker'].value_counts()}")

# -----------------------------
# STEP 4: Prepare Data for ML
# -----------------------------
print("Preparing data for training...")
features = data.select_dtypes(include=["int64", "float64"]).fillna(0)
target_class = data["loan_taker"]
target_reg = data["loan_amount"]
# Split data for both classification and regression
X_train, X_test, y_train, y_test, y_train_reg, y_test_reg = train_test_split(
    features, target_class, target_reg, test_size=0.2, random_state=42
)
print(f"X_train shape: {X_train.shape}")
print(f"X_test shape: {X_test.shape}")
print(f"y_train: {np.unique(y_train, return_counts=True)}")
print(f"y_test: {np.unique(y_test, return_counts=True)}")
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# -----------------------------
# STEP 5: Train Classification Model
# -----------------------------
print("\nTraining classification model...")
clf = RandomForestClassifier(n_estimators=200, random_state=42)
clf.fit(X_train_scaled, y_train)
y_pred_class_train = clf.predict(X_train_scaled)
y_pred_class = clf.predict(X_test_scaled)
# Metrics
train_acc = accuracy_score(y_train, y_pred_class_train)
test_acc = accuracy_score(y_test, y_pred_class)
print(f"Train Accuracy: {train_acc:.4f}")
print(f"Test Accuracy: {test_acc:.4f}")
print("\nClassification Report (Train):")
print(classification_report(y_train, y_pred_class_train))
print("Classification Report (Test):")
print(classification_report(y_test, y_pred_class))
print("\nConfusion Matrix (Test set):")
confmat = confusion_matrix(y_test, y_pred_class)
print(confmat)
sns.heatmap(confmat, annot=True, fmt="d", cmap="Blues")
plt.title("Confusion Matrix (Test)")
plt.xlabel("Predicted")
plt.ylabel("Actual")
plt.show()

# Sample outputs: train and test
print("\nSample Predictions on Training Set:")
train_sample_idx = np.random.choice(np.arange(X_train.shape[0]), size=5, replace=False)
for i in train_sample_idx:
    print(f"Train sample {i} (Actual: {y_train.iloc[i]}, Pred: {y_pred_class_train[i]}) Match: {y_train.iloc[i]==y_pred_class_train[i]}")
print("\nSample Predictions on Test Set:")
test_sample_idx = np.random.choice(np.arange(X_test.shape[0]), size=5, replace=False)
for i in test_sample_idx:
    print(f"Test sample {i} (Actual: {y_test.iloc[i]}, Pred: {y_pred_class[i]}) Match: {y_test.iloc[i]==y_pred_class[i]}")

# -----------------------------
# STEP 6: Train Regression Model
# -----------------------------
print("\nTraining regression model...")
reg = RandomForestRegressor(n_estimators=200, random_state=42)
reg.fit(X_train_scaled, y_train_reg)
y_pred_reg_train = reg.predict(X_train_scaled)
y_pred_amount = reg.predict(X_test_scaled)
train_mse = mean_squared_error(y_train_reg, y_pred_reg_train)
test_mse = mean_squared_error(y_test_reg, y_pred_amount)
print(f"Train Regression MSE: {train_mse:.2f}")
print(f"Test Regression MSE: {test_mse:.2f}")

# Plot residuals for regression (test)
residuals = y_test_reg - y_pred_amount
plt.figure(figsize=(6, 4))
sns.histplot(residuals, bins=40, kde=True)
plt.title("Regression Residuals (y_true - y_pred) on Test Set")
plt.xlabel("Prediction Error")
plt.ylabel("Frequency")
plt.show()

# Show first 5 predicted vs true loan amounts in test set
print("\nSample Test Predictions (Regression):")
for i in test_sample_idx:
    print(f"Test sample {i}: True Loan Amount: {y_test_reg.iloc[i]:.2f}, Predicted: {y_pred_amount[i]:.2f}, Error: {(y_test_reg.iloc[i] - y_pred_amount[i]):.2f}")
# Scatter plot: True vs Predicted amounts
plt.figure(figsize=(6, 6))
plt.scatter(y_test_reg, y_pred_amount, alpha=0.5)
plt.xlabel("True Loan Amount")
plt.ylabel("Predicted Loan Amount")
plt.title("Regression: True vs Predicted Amounts (Test Set)")
plt.plot([y_test_reg.min(), y_test_reg.max()], [y_test_reg.min(), y_test_reg.max()], 'r--')
plt.tight_layout()
plt.show()

# -----------------------------
# STEP 7: Feature Importance
# -----------------------------
print("\nPlotting feature importance...")
feat_importances = pd.Series(clf.feature_importances_, index=features.columns)
top_features = feat_importances.nlargest(15)
top_features.plot(kind="barh", title="Top 15 Important Features")
plt.xlabel("Importance Score")
plt.ylabel("Feature")
plt.tight_layout()
plt.show()

print("\n✅ Model training and evaluation complete!\n")
