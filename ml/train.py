import json
import os

import joblib
import pandas as pd
import xgboost as xgb
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame()
    # 1. Hunk size
    features["hunk_lines"] = df["hunk"].apply(lambda x: len(str(x).split("\n")))
    # 2. File extension risk (e.g. .py is riskier than .md)
    features["is_python"] = df["file_path"].apply(lambda x: 1 if str(x).endswith(".py") else 0)
    features["is_doc"] = df["file_path"].apply(lambda x: 1 if str(x).endswith((".md", ".txt")) else 0)
    # 3. Comment length (heuristic for explanation complexity)
    features["explanation_length"] = df["body"].apply(lambda x: len(str(x)))

    return features


if __name__ == "__main__":
    df = pd.read_csv("ml/data/training_set.csv")

    X = extract_features(df)
    y = df["is_actionable"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Train XGBoost
    model = xgb.XGBClassifier(n_estimators=100, max_depth=3, learning_rate=0.1)
    model.fit(X_train, y_train)

    # Evaluate
    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:, 1]

    os.makedirs("ml/reports", exist_ok=True)
    with open("ml/reports/metrics.txt", "w") as f:
        f.write("XGBoost Evaluation:\n")
        f.write(classification_report(y_test, preds))
        f.write(f"\nROC-AUC: {roc_auc_score(y_test, probs):.4f}\n")

    print(classification_report(y_test, preds))

    # Save Artifacts
    os.makedirs("ml/artifacts", exist_ok=True)
    joblib.dump(model, "ml/artifacts/xgboost_model.pkl")

    # Feature Schema for inference validation
    schema = {"features": list(X.columns)}
    with open("ml/artifacts/feature_schema.json", "w") as f:
        json.dump(schema, f)
