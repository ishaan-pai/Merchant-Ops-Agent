# src/tools.py
from collections import defaultdict
from langchain.tools import tool
from shopify import graphql
from datetime import datetime, timedelta, timezone

ORDERS_QUERY = """
query ($q: String!, $cursor: String) {
    orders(first: 100, after: $cursor, query: $q, sortKey: PROCESSED_AT) {
        nodes {
            name
            processedAt
            totalPriceSet { shopMoney { amount currencyCode } }
            lineItems(first: 20) { nodes { name quantity } }
        }
    pageInfo { hasNextPage endCursor }
    }
}
"""

@tool
def get_orders(start_date: str, end_date: str) -> dict:
    """Summarize orders from start_date (inclusive) to end_date (exclusive).

    Dates are YYYY-MM-DD. Returns order count, total revenue, revenue per day
    and units sold per product. Call it twice to compare two periods.
    """
    q = f"processed_at:>='{start_date}T00:00:00Z' processed_at:<'{end_date}T00:00:00Z'"
    cursor, count, revenue, currency = None, 0, 0.0, None
    by_day: dict[str, float] = defaultdict(float)
    by_product: dict[str, int] = defaultdict(int)
    while True:
        page = graphql(ORDERS_QUERY, {"q": q, "cursor": cursor})["orders"]
        for order in page["nodes"]:
            money = order["totalPriceSet"]["shopMoney"]
            count += 1
            revenue += float(money["amount"])
            currency = money["currencyCode"]
            by_day[order["processedAt"][:10]] += float(money["amount"])
            for item in order["lineItems"]["nodes"]:
                by_product[item["name"]] += item["quantity"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return {
        "order_count": count,
        "revenue": round(revenue, 2),
        "currency": currency,
        "revenue_by_day": dict(sorted(by_day.items())),
        "units_by_product": dict(sorted(by_product.items(), key=lambda kv: -kv[1])[:15]),
    }

PRODUCTS_QUERY = """
query ($q: String) {
    products(first: 50, query: $q) {
        nodes {
            id
            title
            status
            totalInventory
            variants(first: 20) { nodes { title price inventoryQuantity } }
        }
    }
}
"""

@tool
def get_products(search: str = "") -> list[dict]:
    """Find products by title keyword. Empty search returns the first 50.

    Returns id, title, status (ACTIVE/DRAFT/ARCHIVED) and price per variant.
    Call this when a product's sales drop to zero: a DRAFT or ARCHIVED
    product can't be bought.
    """
    q = f"title:*{search}*" if search else None
    nodes = graphql(PRODUCTS_QUERY, {"q": q})["products"]["nodes"]
    return [
        {
            "id": p["id"],
            "title": p["title"],
            "status": p["status"],
            "variants": [{"title": v["title"], "price": v["price"]} for v in p["variants"]["nodes"]],
        }
        for p in nodes
    ]

@tool
def get_inventory(low_stock_threshold: int = 5) -> dict:
    """Report current stock. Returns products that are out of stock and
    products at or below low_stock_threshold units, with counts per variant.
    """
    nodes = graphql(PRODUCTS_QUERY, {"q": "status:active"})["products"]["nodes"]
    out, low = [], []
    for p in nodes:
        row = {
            "title": p["title"],
            "total": p["totalInventory"],
            "variants": {v["title"]: v["inventoryQuantity"] for v in p["variants"]["nodes"]},
        }
        if p["totalInventory"] <= 0:
            out.append(row)
        elif p["totalInventory"] <= low_stock_threshold:
            low.append(row)
    return {"out_of_stock": out, "low_stock": low, "products_checked": len(nodes)}

DISCOUNT_MUTATION = """
mutation ($input: DiscountCodeBasicInput!) {
    discountCodeBasicCreate(basicCodeDiscount: $input) {
        codeDiscountNode { id }
        userErrors { field message }
    }
}
"""

@tool
def create_discount(code: str, percent_off: float, days_valid: int) -> str:
    """Create a percentage-off discount code that applies to all products.

    percent_off is 1-100. The code starts now and expires after days_valid days.
    """
    if not 1 <= percent_off <= 100:
        return "Error: percent_off must be between 1 and 100."
    now = datetime.now(timezone.utc)
    payload = graphql(DISCOUNT_MUTATION, {"input": {
        "title": code,
        "code": code,
        "startsAt": now.isoformat(),
        "endsAt": (now + timedelta(days=days_valid)).isoformat(),
        "customerSelection": {"all": True},
        "customerGets": {"value": {"percentage": percent_off / 100}, "items": {"all": True}},
    }})["discountCodeBasicCreate"]
    if payload["userErrors"]:
        return f"Shopify rejected the discount: {payload['userErrors']}"
    return f"Created code {code}: {percent_off}% off everything for {days_valid} days."