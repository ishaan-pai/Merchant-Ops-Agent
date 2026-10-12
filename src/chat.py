# src/chat.py
import uuid
from langgraph.types import Command
from agent import agent

config = {"configurable": {"thread_id": str(uuid.uuid4())}}


def run(payload) -> str:
    result = agent.invoke(payload, config=config, version="v2")
    while result.interrupts:
        decisions = []
        for request in result.interrupts[0].value["action_requests"]:
            print(f"\n{request['description']}")
            if input("Should I go ahead? [y/n] ").strip().lower() == "y":
                decisions.append({"type": "approve"})
            else:
                decisions.append({
                    "type": "reject",
                    "message": "The merchant declined. Do not retry; ask what they want instead.",
                })
        result = agent.invoke(Command(resume={"decisions": decisions}), config=config, version="v2")
    return result.value["messages"][-1].text


if __name__ == "__main__":
    print("Merchant ops agent. Type exit to quit.")
    while True:
        question = input("\n> ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if question:
            print(run({"messages": [{"role": "user", "content": question}]}))