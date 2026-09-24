"""命令行入口：python -m tinyledger <命令>"""
import argparse
import sys

from . import store


def cmd_add(args):
    entries = store.load()
    e = store.add(entries, args.category, args.amount, args.note or "")
    store.save(entries)
    print(f"已记账：{e['date']} {e['category']} {e['amount']}")


def cmd_list(args):
    entries = store.load()
    if args.month:
        entries = store.in_month(entries, args.month)
    for e in entries:
        print(f"{e['date']}  {e['category']:<6} {e['amount']:>10}  {e['note']}")
    print(f"合计：{store.total(entries)}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tinyledger")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add", help="记一笔")
    p_add.add_argument("category")
    p_add.add_argument("amount")
    p_add.add_argument("--note")
    p_add.set_defaults(func=cmd_add)
    p_list = sub.add_parser("list", help="列出记录")
    p_list.add_argument("--month", help="只看某月，如 2026-09")
    p_list.set_defaults(func=cmd_list)
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
