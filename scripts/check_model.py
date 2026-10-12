# scripts/check_model.py
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

load_dotenv()
model = init_chat_model("claude-sonnet-4-6")     # or "openai:gpt-5.5", etc.
print(model.invoke("Reply with the single word: ready").text)