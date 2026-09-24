# tinyledger

一个命令行记账小工具，只用 Python 标准库。

## 用法

```bash
python -m tinyledger add 餐饮 12.5 --note 午饭
python -m tinyledger list
python -m tinyledger list --month 2026-09
```

数据存在当前目录的 `ledger.json`，可用环境变量 `TINYLEDGER_FILE` 指定别的位置。

## 开发

```bash
python -m unittest
```
