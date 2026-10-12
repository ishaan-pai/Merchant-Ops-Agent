# Merchant Ops Agent
 
A command-line agent that answers operations questions about a single Shopify store ("how did last week compare to the week before?", "why were sales down?", "what's out of stock?") by calling the Shopify Admin GraphQL API. It can also create discount codes, but only after the merchant approves the action.
 
Built with LangChain 1.x (`create_agent`), LangGraph checkpointing, and Claude Sonnet 4.6. This is an MVP: one store, one terminal session, no persistence.
 
## What it does
 
| Tool | Type | What it returns |
| --- | --- | --- |
| `get_orders(start_date, end_date)` | read | Order count, revenue, revenue per day, units per product (top 15) for a date range. Paginates through all orders. |
| `get_products(search)` | read | Products matching a title keyword, with status (`ACTIVE` / `DRAFT` / `ARCHIVED`) and price per variant. |
| `get_inventory(low_stock_threshold)` | read | Active products that are out of stock or at/below the threshold, with counts per variant. |
| `create_discount(code, percent_off, days_valid)` | write | Creates a store-wide percentage discount code. Gated behind human approval. |
 
Design choices worth knowing about:
 
- **The model never does date math.** The system prompt is built at startup with the exact Monday-to-Sunday ranges for "this week", "last week" and "the week before", so the model copies dates instead of computing them.
- **Every number has to come from a tool result.** The prompt forbids guessing and tells the agent to fetch both periods before explaining a change.
- **Writes need a yes.** `HumanInTheLoopMiddleware` interrupts on `create_discount`. The chat loop shows the pending action and asks `[y/n]`. A rejection is sent back to the agent with an instruction not to retry.
- **Tools return summaries, not raw API payloads.** `get_orders` aggregates in Python and returns a small dict, which keeps token use flat regardless of order volume.
## Project layout
 
```
src/
  shopify.py      Token exchange (client credentials, cached in memory) and a graphql() helper
  tools.py        The four tools and their GraphQL queries
  agent.py        System prompt, agent construction, one-shot CLI entry point
  chat.py         Interactive loop with the approve/reject prompt
scripts/
  check_model.py  Confirms the Anthropic key and model name work
  check_tools.py  Calls one read tool directly, without the model
  seed_orders.py  Creates 38 backdated test orders in a dev store
tests/
  questions.yaml  Question / expected-tools / expected-facts cases
  test_questions.py  Runs each case against the live agent
```
 
## Requirements
 
- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- An Anthropic API key
- A Shopify dev store and an app installed on it, with a client ID and client secret
App access scopes (inferred from the queries in `tools.py` and `seed_orders.py`; confirm against your app config): `read_orders`, `read_products`, `read_inventory`, `write_discounts`, and `write_orders` if you use the seed script.
 
## Setup
 
Commands are for Windows PowerShell, run from the repo root.
 
1. Install dependencies.
```powershell
   uv sync
```
 
2. Create a file named `.env` in the repo root with these four values. It is already in `.gitignore`.
```
   ANTHROPIC_API_KEY=sk-ant-...
   SHOPIFY_SHOP=your-store-subdomain
   SHOPIFY_CLIENT_ID=...
   SHOPIFY_CLIENT_SECRET=...
```
 
   `SHOPIFY_SHOP` is the subdomain only: for `my-store.myshopify.com`, use `my-store`.
 
3. Check the Shopify connection. This should print three products.
```powershell
   uv run python src/shopify.py
```
 
4. Check the model. This should print `ready`.
```powershell
   uv run python scripts/check_model.py
```
 
5. Check a tool without the model in the loop. Valid names are `get_orders`, `get_products` and `get_inventory`.
```powershell
   uv run python scripts/check_tools.py get_orders
```
 
## Usage
 
Interactive chat (this is the one that handles discount approvals):
 
```powershell
uv run python src/chat.py
```
 
```
> Why were sales down last week?
> Make a 20% off code SAVE20 for 3 days
 
The assistant wants to change your store ...
Should I go ahead? [y/n]
```
 
One-shot question, with the full message trace (tool calls and results) printed:
 
```powershell
uv run python src/agent.py "How did last week compare to the week before?"
```
 
The one-shot entry point doesn't handle approvals. If the question triggers `create_discount`, the run stops at the interrupt.
 
## Test data
 
`scripts/seed_orders.py` builds a known scenario in a dev store so the agent has something to explain:
 
| Week | Orders | Orders containing the "hero" product |
| --- | --- | --- |
| Week before last | 24 | 10 |
| Last week | 14 | 0 |
 
The hero is the first active product the API returns. The plan is seeded (`random.seed(7)`), so every run generates the same 38 orders. Dates are relative to the Monday of the week you run it in.
 
1. Create one order to confirm it works.
```powershell
   uv run python scripts/seed_orders.py 0 1
```
 
2. Create the rest. This takes about eight minutes, because dev stores allow five new orders per minute and the script sleeps 13 seconds between orders.
```powershell
   uv run python scripts/seed_orders.py 1
```
 
3. Note the hero product name printed at the end.
4. In the Shopify admin, set that product's status to **Draft**. This step isn't scripted. It's what gives the agent a cause to find: the product sold in 10 orders, then zero, and `get_products` shows it can't be bought.
If the script fails partway, rerun it with the index of the first order that wasn't created as the start argument.
 
## Tests
 
```powershell
uv run pytest
```
 
These are live evaluations, not unit tests. Each case in `tests/questions.yaml` calls the real model and the real store, so they cost API tokens and need the seeded data above. A case can assert:
 
- `expect_tools`: tools that must have been called
- `expect_in_answer`: substrings that must appear in the final answer (case-insensitive)
- `expect_interrupt`: the tool that must be waiting for approval. The test stops there and never approves.
The current cases assume the hero product is a gift card in Draft status (`expect_in_answer: ["gift card", "draft"]`) and that last week has exactly 14 orders.
 
## Known limitations
 
- **The seeded scenario expires.** Order dates are relative to seed time. Once a new week starts, "last week" no longer contains the 14 seeded orders and the count test fails.
- **Local dates vs UTC.** Week boundaries are computed from the local date, but orders are queried and bucketed in UTC. Orders near midnight can land on the wrong day or week for a non-UTC store.
- **Dates are fixed at startup.** A chat session left open past midnight keeps the old "today".
- **No pagination on products.** `get_products` and `get_inventory` read the first 50 products and first 20 variants each. `get_orders` reads the first 20 line items per order.
- **Conversation memory is in-process.** `InMemorySaver` loses everything when the process exits, including a pending approval.
- **No retry or rate-limit handling** in `shopify.graphql()`. An HTTP or GraphQL error raises.
- **Discounts are store-wide only.** No per-product or per-customer targeting, and there's no tool to list or delete codes.
- **The off-topic test is weak.** The weather case only checks that the agent returns without error; it doesn't assert that no tool was called.
