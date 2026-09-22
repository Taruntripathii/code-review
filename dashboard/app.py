import os

import httpx
import streamlit as st

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8000")

st.title("CodeReviewBot - Human Review Queue")


# Fetch Pending Reviews
def fetch_pending_reviews():
    # Assume we expose this endpoint in main.py
    try:
        resp = httpx.get(f"{API_URL}/api/reviews?status=PENDING_HUMAN_REVIEW")
        return resp.json() if resp.status_code == 200 else []
    except httpx.ConnectError:
        return []


reviews = fetch_pending_reviews()

if not reviews:
    st.success("Inbox zero! No pending reviews.")
else:
    for review in reviews:
        with st.expander(f"PR #{review['pull_request_id']} — {review['summary']}"):
            # Fetch findings for this review
            resp = httpx.get(f"{API_URL}/api/reviews/{review['id']}/findings")
            findings = resp.json() if resp.status_code == 200 else []

            for f in findings:
                st.markdown(f"**File:** `{f['file_path']}:{f['line']}` | **Category:** {f['category']}")
                st.info(f["explanation"])

                col1, col2 = st.columns(2)
                col1.metric("LLM Confidence", f"{f.get('llm_confidence', 0) * 100:.1f}%")
                col2.metric("ML Probability", f"{f.get('ml_probability', 0) * 100:.1f}%")

                # Decision Buttons
                action_col1, action_col2 = st.columns(2)
                if action_col1.button("Approve", key=f"approve_{f['id']}"):
                    httpx.patch(f"{API_URL}/api/findings/{f['id']}", json={"decision": "approved"})
                    st.success("Approved!")
                    st.rerun()
                if action_col2.button("Reject", key=f"reject_{f['id']}"):
                    httpx.patch(f"{API_URL}/api/findings/{f['id']}", json={"decision": "rejected"})
                    st.error("Rejected.")
                    st.rerun()

            if st.button("Publish Review to GitHub", key=f"publish_{review['id']}", type="primary"):
                # Call publisher endpoint (Day 12)
                resp = httpx.post(f"{API_URL}/api/reviews/{review['id']}/publish")
                if resp.status_code == 200:
                    st.balloons()
                    st.rerun()
