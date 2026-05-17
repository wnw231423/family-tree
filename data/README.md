# 数据生成

本目录提供课程实验所需的模拟数据生成脚本。

## 生成 CSV

如本地尚未安装 Python 依赖，先执行：

```bash
python3 -m pip install -r requirements.txt
```

```bash
python3 data/generate.py
```

默认生成 10 个族谱 CSV，共 102,000 名成员；第一个族谱包含 50,000 名成员。每个族谱生成 30 代人物，并为每名非始祖成员建立至少一条亲子关系。

可通过 `--output-dir` 指定输出目录，通过 `--sizes` 指定各族谱成员数量，通过 `--generations` 指定生成代数。

生成单个指定族谱：

```bash
python3 data/generate.py --sizes 1000 --surname 陈 --name 陈氏宗谱 --compiled-at 2026-05-17
```

批量指定多个族谱：

```bash
python3 data/generate.py --sizes 1000,800 --surnames 陈,林 --names 陈氏宗谱,林氏族谱 --compiled-dates 2026-05-17,2026-06-01
```

每个输出文件对应一个族谱，采用单文件 CSV 格式。文件包含 `genealogy`、`member`、`parent_child` 和 `marriage` 四类记录，不包含用户、创建者或协作者信息。

生成后的 CSV 文件通过系统 Dashboard 页面导入。族谱详情页导出的 CSV 使用相同格式。
