# scripts/seed_orders.py
# Usage:  seed_orders.py [start] [count]
#   seed_orders.py 0 1   -> create only order 0
#   seed_orders.py 1     -> create orders 1 to the end
import random, sys, time
from datetime import date, datetime, time as dtime, timedelta, timezone

sys.path.insert(0, "src")
from shopify import graphql

PRODUCTS = """
{ products(first: 10, query: "status:active") {
    nodes { title variants(first: 1) { nodes { id } } } } }
"""

CREATE = """
mutation ($order: OrderCreateOrderInput!) {
    orderCreate(order: $order) {
        order { name processedAt }
        userErrors { field message }
    }
}
"""


def variant_id(product: dict) -> str:
    return product["variants"]["nodes"][0]["id"]


def build_jobs(products: list[dict]) -> list[tuple[datetime, list[dict]]]:
    """Plan all 38 orders up front so every run produces the same list."""
    random.seed(7)
    hero, others = products[0], products[1:]
    this_monday = date.today() - timedelta(days=date.today().weekday())
    plan = [                # (week start, orders, orders that include the hero)
        (this_monday - timedelta(days=14), 24, 10),
        (this_monday - timedelta(days=7), 14, 0),
    ]
    jobs = []
    for week_start, total, with_hero in plan:
        for i in range(total):
            ids = [variant_id(random.choice(others))]
            if i < with_hero:
                ids.append(variant_id(hero))
            day = week_start + timedelta(days=i % 7)
            when = datetime.combine(
                day, dtime(random.randint(13, 22), random.randint(0, 59)), tzinfo=timezone.utc
            )
            lines = [{"variantId": v, "quantity": random.randint(1, 2)} for v in ids]
            jobs.append((when, lines))
    return jobs


def create_order(n: int, when: datetime, lines: list[dict]) -> None:
    result = graphql(CREATE, {"order": {
        "lineItems": lines,
        "processedAt": when.isoformat(),
        "financialStatus": "PAID",
    }})["orderCreate"]
    if result["userErrors"]:
        raise SystemExit(f"Order {n} rejected: {result['userErrors']}")
    print(n, result["order"]["name"], result["order"]["processedAt"])
    time.sleep(13)          # dev stores allow 5 new orders per minute


if __name__ == "__main__":
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    count = int(sys.argv[2]) if len(sys.argv) > 2 else None
    products = graphql(PRODUCTS)["products"]["nodes"]
    jobs = build_jobs(products)
    end = len(jobs) if count is None else min(start + count, len(jobs))
    for n in range(start, end):
        create_order(n, *jobs[n])
    print(f"\nCreated orders {start} to {end - 1} of {len(jobs)}.")
    print(f"Hero product: {products[0]['title']}")