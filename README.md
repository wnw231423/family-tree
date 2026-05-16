# 族谱管理系统

数据库课程大作业项目，使用 Flask、Jinja2、psycopg2 与 PostgreSQL 实现多用户族谱管理。

## 第一次启动

### 1. 进入项目目录

```bash
cd /path/to/family-tree
```

### 2. 构建并启动容器

```bash
docker compose up -d --build
```

首次启动会拉取 `postgres:16` 镜像并构建 Flask 应用镜像，耗时取决于网络情况。

### 3. 查看容器状态

```bash
docker compose ps
```

正常情况下应看到 `db` 和 `app` 两个服务均为运行状态。

如果应用启动较慢，可以查看日志：

```bash
docker compose logs -f db
docker compose logs -f app
```

### 4. 生成模拟数据

```bash
docker compose exec app python data/generate.py
```

默认会生成 10 个族谱、102,000 名成员，其中第一个族谱包含 50,000 名成员。

### 5. 导入模拟数据

```bash
docker compose exec app python data/import_csv.py --truncate
```

### 6. 打开系统

浏览器访问：

```text
http://localhost:5000
```

默认账号：

```text
用户名：user1
密码：123456
```

## 日常启动

已经完成首次初始化后，下次只需要：

```bash
cd /path/to/family-tree
docker compose up -d
```

然后访问：

```text
http://localhost:5000
```

## 重新构建应用

修改 Python 或模板代码后，执行：

```bash
docker compose up -d --build app
```

## 常用命令

查看状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f app
docker compose logs -f db
```

停止容器：

```bash
docker compose down
```

停止容器并删除数据库数据：

```bash
docker compose down -v
```

## 数据导出

导出某个成员分支备份：

```bash
docker compose exec app python data/export_branch.py 1 --output data/output/branch_backup.csv
docker compose cp app:/app/data/output/branch_backup.csv data/output/branch_backup.csv
```

## 本地代码检查

```bash
PYTHONPYCACHEPREFIX=/tmp/family-tree-pycache python3 -m py_compile run.py config.py app/*.py data/*.py
```

## 使用提示

第一个族谱包含 50,000 名成员。树形预览页面默认只展开 4 代，避免一次渲染整棵大树导致浏览器卡顿。需要查看更多层级时，可在页面中调整“展开代数”。

## 主要文件

- `app/`：Flask 应用代码。
- `sql/schema.sql`：数据库表、约束、触发器和索引。
- `sql/queries.sql`：核心 SQL 查询。
- `data/`：模拟数据生成、COPY 导入和分支导出脚本。
- `docker-compose.yml`：Flask 与 PostgreSQL 容器编排。
- `docs/dev-doc.md`：数据库设计、功能说明和项目结构文档。
