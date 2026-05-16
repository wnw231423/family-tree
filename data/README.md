# 数据生成与导入导出

本目录提供课程实验所需的模拟数据生成、PostgreSQL COPY 导入和分支导出脚本。

## 生成 CSV

```bash
python data/generate.py
```

默认生成 10 个族谱，共 102,000 名成员；第一个族谱包含 50,000 名成员。每个族谱生成 30 代人物，并为每名非始祖成员建立至少一条亲子关系。

## 导入数据库

```bash
docker cp data/output family-tree-app-1:/app/data/output
docker compose exec app python data/import_csv.py --truncate
```

脚本使用 PostgreSQL `COPY` 协议批量导入 `data/output/` 下的 CSV 文件。

## 导出分支备份

```bash
docker compose exec app python data/export_branch.py 1 --output data/output/branch_backup.csv
docker cp family-tree-app-1:/app/data/output/branch_backup.csv data/output/branch_backup.csv
```

脚本以指定成员为根节点，使用 Recursive CTE 导出其全部直系后代。
