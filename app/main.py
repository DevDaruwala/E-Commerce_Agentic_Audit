"""
main.py — the FastAPI app.

Phase 1 job: expose ONE endpoint, POST /listings/audit, that:
  1. takes a raw product listing (see schemas.py for the shape)
  2. validates it (validation.py)
  3. scores it with the classifier (classifier/predict.py)
  4. if high risk, runs it through the fixed llm_audit.py pipeline
  5. returns a report (report.py)

Keep this file thin — it should mostly call other modules, not contain logic itself.
"""

from fastapi import FastAPI

app = FastAPI(title="E-Commerce Agentic Audit")


@app.get("/health")
def health_check():
    """Simple check so you know the server is actually running."""
    return {"status": "ok"}


# TODO (Phase 1, build task 6): add the POST /listings/audit endpoint here,
# once schemas.py, validation.py, classifier/predict.py, llm_audit.py,
# and report.py each work on their own.
