# src/agent.py
import sys
from datetime import date, timedelta
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import InMemorySaver
from tools import get_orders, get_inventory, get_products, create_discount

load_dotenv()

today = date.today()
this_monday = today - timedelta(days=today.weekday())
last_monday = this_monday - timedelta(days=7)
prior_monday = this_monday - timedelta(days=14)

SYSTEM_PROMPT = f"""You are an operations assistant for one Shopify store.
Today is {today:%A} {today.isoformat()}. Weeks run Monday to Sunday.

Date ranges, as start_date and end_date for get_orders (end_date is exclusive):
- "This week" (still in progress): {this_monday} to {this_monday + timedelta(days=7)}
- "Last week": {last_monday} to {this_monday}
- "The week before" or "the week before last": {prior_monday} to {last_monday}
Use these exact dates. Never count the week in progress as "last week".

Rules:
- Every number in your answer must come from a tool result in this conversation.
- To explain a change, fetch both periods and compare them before answering.
- If the tools can't answer the question, say what's missing. Don't guess.
- Keep answers to a few sentences and lead with the conclusion.
"""

agent = create_agent(
    model="claude-sonnet-4-6",
    tools=[get_orders, get_inventory, get_products, create_discount],
    system_prompt=SYSTEM_PROMPT,
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={"create_discount": {"allowed_decisions": ["approve", "reject"]}},
            description_prefix="The assistant wants to change your store",
        ),
    ],
    checkpointer=InMemorySaver(),
)

if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or "How did last week compare to the week before?"
    result = agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"configurable": {"thread_id": "dev"}},
    )
    for m in result["messages"]:
        m.pretty_print()
