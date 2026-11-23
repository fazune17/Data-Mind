
from dotenv import load_dotenv
from google import genai
import os

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

print("\nAVAILABLE GEMINI MODELS\n")

try:
    models = client.models.list()

    for model in models:
        actions = model.supported_actions or []

        if "generateContent" in actions:
            print(model.name)

except Exception as error:
    print("MODEL DISCOVERY FAILED")
    print(type(error).__name__)
    print(error)
