import json
import logging
from .gemini_client import generate_ai_response
from .prompt_templates import (
    analysis_plan_prompt,
    insight_prompt
)
from analytics.query_engine import execute_analysis
from analytics.schema_mapper import inspect_dataset_schema

logger = logging.getLogger(__name__)


def analyze_dataset(question, df, schema=None, profile=None):
    # Step 1: Extract complete schema grounding info
    schema_info = inspect_dataset_schema(df)

    # Step 2: Request structured analytical plan from Gemini
    plan_prompt = analysis_plan_prompt(
        question=question,
        df=df,
        schema_info=schema_info
    )

    plan_response = generate_ai_response(plan_prompt)

    # Step 3: Clean and parse structured JSON
    cleaned_plan = plan_response.strip()
    if cleaned_plan.startswith("```"):
        lines = cleaned_plan.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned_plan = "\n".join(lines).strip()

    try:
        plan = json.loads(cleaned_plan)
    except json.JSONDecodeError:
        # Fallback to direct SQL query if plan is not JSON
        logger.warning("Gemini plan was not valid JSON; attempting fallback plan.")
        plan = {
            "operation": "sql_query",
            "sql": cleaned_plan,
            "chart_type": "none"
        }

    if not isinstance(plan, dict):
        raise ValueError("Invalid analysis plan format received.")

    if plan.get("operation") == "unsupported":
        raise ValueError(
            plan.get("reason", "The requested information cannot be calculated from this dataset.")
        )

    # Step 4: Execute verified analytical operations on dataset
    results = execute_analysis(df, plan)

    # Step 5: Synthesize business insights
    explanation_prompt = insight_prompt(
        question=question,
        results=results
    )

    explanation = generate_ai_response(explanation_prompt)

    return {
        "question": question,
        "analysis_plan": plan,
        "results": results,
        "insights": explanation
    }
