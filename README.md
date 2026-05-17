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

如本地尚未安装 Python 依赖，先执行：

```bash
python3 -m pip install -r requirements-data.txt
```

```bash
python3 data/generate.py
```

默认会生成 10 个族谱 CSV，共 102,000 名成员，其中第一个族谱包含 50,000 名成员。每个 CSV 文件对应一个族谱，只包含族谱、成员、亲子关系和婚姻关系数据。

生成指定族谱示例：

```bash
python3 data/generate.py --sizes 1000 --surname 陈 --name 陈氏宗谱 --compiled-at 2026-05-17
```

### 5. 导入模拟数据

登录系统后，在 Dashboard 选择一个或多个族谱 CSV 文件并点击“导入族谱 CSV”。导入后的族谱创建者为当前登录用户。

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

进入族谱详情页后，点击“导出 CSV”可下载该族谱的纯数据文件。导出的 CSV 不包含用户、创建者或协作者信息，可由其他用户重新导入为自己的族谱。

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
- `data/`：模拟族谱 CSV 生成脚本。
- `docker-compose.yml`：Flask 与 PostgreSQL 容器编排。
- `requirements.txt`：Web 应用和 Docker 镜像依赖。
- `requirements-data.txt`：本地数据生成脚本依赖。
- `docs/dev-doc.md`：数据库设计、功能说明和项目结构文档。
