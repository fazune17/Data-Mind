from ai_engine.gemini_client import generate_ai_response
import os

print("Testing DataMind Gemini...")
print("Selected model:", os.getenv("GEMINI_MODEL"))

try:
    response = generate_ai_response(
        "Explain data analysis in two sentences."
    )

    print("\nGEMINI CONNECTION SUCCESSFUL")
    print(response)

except Exception as error:
    print("\nGEMINI CONNECTION FAILED")
    print(type(error).__name__)
    print(error)