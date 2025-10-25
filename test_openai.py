import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # read .env in this folder
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hello from AGIcyborg"}],
)
print(resp.choices[0].message.content)
