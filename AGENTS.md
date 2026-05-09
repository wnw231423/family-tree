# AGENTS.md

## 文档写作规范

1. **开发文档（docs/）应保持客观、正式**，不使用口语化表达（如"够用不折腾""零学习成本""一行代码搞定"等），不将内部讨论中的修改过程暴露到文档中。
2. **主观决策应单独说明**。若某个技术选型受项目阶段、人员规模等主观因素影响，不在选型表格的"理由"栏中夹杂看法，而是统一归入"部分选择的依据"章节集中陈述。
3. **只写结论，不写排除项**。不在文档中列出"不使用 XXX 及原因"这类列表——文档的读者只关心用了什么，不关心没用什么。

## 代码写作规范

1. Python 代码遵循 PEP 8，使用 4 空格缩进。
2. 不使用 ORM（SQLAlchemy 等），所有数据库操作使用 `psycopg2` 原生 SQL。
3. 路由函数中通过 `flask.g` 获取数据库连接，连接由 `app.teardown_appcontext` 自动归还连接池。
4. 递归查询使用 PostgreSQL Recursive CTE，不在 Python 层做递归。
5. Jinja2 模板中，缩进树使用递归 macro 渲染。
6. 静态资源（CSS / JS）优先使用 CDN 引入，不做本地构建。

## 文档一致性

1. 代码变更涉及项目结构（新增/删除/重命名文件）时，必须同步更新 `docs/dev-doc.md` 中的"预期项目结构"章节。
2. 新增或修改配置参数时，同步更新 `docs/dev-doc.md` 对应章节。
3. 数据库 schema 变更时，`sql/schema.sql` 和 `docs/dev-doc.md` 的"表结构"章节必须一致。

## 项目上下文

- 项目经理 + 开发 = 2 人。
- 项目无后续迭代计划，功能完成后即交付。
- 所有交互（查询、展示、CRUD）均走服务端渲染，无前端路由，无 SPA。
- 配置通过 `.env` 文件管理，不硬编码任何连接信息。

## 数据库操作模式

```python
# app/db.py 示例
import psycopg2
from psycopg2 import pool
from flask import g, current_app

connection_pool = None

def init_pool(app):
    global connection_pool
    connection_pool = pool.ThreadedConnectionPool(
        1, 10,
        **app.config['DB_PARAMS']
    )

def get_db():
    if 'db' not in g:
        g.db = connection_pool.getconn()
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        connection_pool.putconn(db)
```

在 `create_app()` 中注册：

```python
from app.db import init_pool, close_db

app.teardown_appcontext(close_db)
with app.app_context():
    init_pool(app)
```

## 常用命令

```bash
# 启动
docker-compose up -d

# 初始化数据库
docker exec -i family-tree-db psql -U postgres -d family_tree < sql/schema.sql

# 运行测试
pytest tests/ -v
```
