import joblib
import pandas as pd
import shap


class FindingPredictor:
    def __init__(self, model_path: str = "ml/artifacts/xgboost_model.pkl"):
        try:
            self.model = joblib.load(model_path)
            self.explainer = shap.TreeExplainer(self.model)
        except FileNotFoundError:
            self.model = None  # Graceful degradation if model not trained

    def _extract_features(self, finding) -> pd.DataFrame:
        # Must match Day 9 exactly
        features = {
            "hunk_lines": [10],  # Approximation for runtime, or pass real hunk size
            "is_python": [1 if finding.file_path.endswith(".py") else 0],
            "is_doc": [1 if finding.file_path.endswith((".md", ".txt")) else 0],
            "explanation_length": [len(finding.explanation)],
        }
        return pd.DataFrame(features)

    def predict(self, finding) -> dict:
        if not self.model:
            return {"probability": 0.5, "shap_values": {}}

        X = self._extract_features(finding)
        prob = float(self.model.predict_proba(X)[0][1])

        # SHAP values for explainability on the UI
        shap_vals = self.explainer.shap_values(X)
        shap_dict = {col: float(val) for col, val in zip(X.columns, shap_vals[0])}

        return {"probability": prob, "shap_values": shap_dict}


# Singleton instance
predictor = FindingPredictor()
