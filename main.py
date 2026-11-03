import os
from dotenv import load_dotenv
from sarvamai import SarvamAI

# Load environment variables from .env
load_dotenv()

# Initialize Sarvam client reading key from environment
api_key = os.getenv("SARVAM_API_KEY")
if not api_key:
    raise ValueError("SARVAM_API_KEY not found in environment. Please set it in .env")

client = SarvamAI(api_subscription_key=api_key)

# Make a chat completion call with sarvam-105b-conversations
response = client.chat.completions(
    model="sarvam-105b-conversations",
    messages=[
        {"role": "user", "content": "Hello! Introduce yourself briefly in one sentence."}
    ]
)

# Print the reply
print("Response from Sarvam AI:")
print(response.choices[0].message.content)
