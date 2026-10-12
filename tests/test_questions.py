# tests/test_questions.py
import uuid
from pathlib import Path

import pytest
import yaml
from agent import agent

CASES = yaml.safe_load(
    (Path(__file__).parent / "questions.yaml").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["question"][:40])
def test_question(case):
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": case["question"]}]},
        config=config,
        version="v2",
    )
    if "expect_interrupt" in case:
        pending = result.interrupts[0].value["action_requests"][0]["name"]
        assert pending == case["expect_interrupt"]
        return                                    # never approve in tests
    messages = result.value["messages"]
    called = {tc["name"] for m in messages for tc in getattr(m, "tool_calls", [])}
    assert set(case["expect_tools"]) <= called
    answer = messages[-1].text.lower()
    for fact in case["expect_in_answer"]:
        assert fact.lower() in answer