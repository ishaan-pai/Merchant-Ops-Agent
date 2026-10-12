# scripts/check_tools.py
# Usage:  check_tools.py <tool_name>
import sys
from datetime import date, timedelta

sys.path.insert(0, "src")
import tools

monday = date.today() - timedelta(days=date.today().weekday())
CALLS = {
    "get_orders": {"start_date": str(monday - timedelta(days=7)), "end_date": str(monday)},
    "get_products": {"search": ""},
    "get_inventory": {"low_stock_threshold": 5},
}

name = sys.argv[1]
print(getattr(tools, name).invoke(CALLS[name]))