"""账本存储：JSON 文件，一条记录一个对象。"""
import json
import os
from datetime import date

DEFAULT_FILE = "ledger.json"


def ledger_path():
    return os.environ.get("TINYLEDGER_FILE", DEFAULT_FILE)


def load(path=None):
    path = path or ledger_path()
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save(entries, path=None):
    path = path or ledger_path()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(entries, fh, ensure_ascii=False, indent=2)


def add(entries, category, amount, note="", day=None):
    entry = {
        "date": (day or date.today()).isoformat(),
        "category": category,
        "amount": float(amount),
        "note": note,
    }
    entries.append(entry)
    return entry


def total(entries):
    result = 0
    for e in entries:
        result += e["amount"]
    return result


def in_month(entries, month):
    """month 形如 2026-09。"""
    return [e for e in entries if e["date"].startswith(month)]
