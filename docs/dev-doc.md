# 开发文档

---

## 一、数据库设计

### 1.1 ER 图

![](./graph/ER.png)

### 1.2 实体与联系

| 实体                  | 联系             | 类型                        |
| --------------------- | ---------------- | --------------------------- |
| users — genealogies   | 用户创建族谱     | 1:N                         |
| users — genealogies   | 用户参与族谱协作 | M:N（通过 genealogy_users） |
| genealogies — members | 族谱包含成员     | 1:N                         |
| members — members     | 亲子关系         | M:N（通过 parent_child）    |
| members — members     | 婚姻关系         | 1:N（通过 marriages）       |

### 1.3 表结构

#### users（用户表）

| 列            | 类型         | 约束             | 含义                     |
| ------------- | ------------ | ---------------- | ------------------------ |
| id            | SERIAL       | PRIMARY KEY      | 用户 ID，自增            |
| username      | VARCHAR(50)  | UNIQUE, NOT NULL | 登录用户名               |
| password_hash | VARCHAR(255) | NOT NULL         | 密码的哈希值（不存明文） |
| created_at    | TIMESTAMP    | DEFAULT NOW()    | 注册时间                 |

#### genealogies（族谱表）

| 列          | 类型         | 约束                     | 含义                     |
| ----------- | ------------ | ------------------------ | ------------------------ |
| id          | SERIAL       | PRIMARY KEY              | 族谱 ID                  |
| name        | VARCHAR(100) | NOT NULL                 | 谱名，如"陇西李氏大宗谱" |
| surname     | VARCHAR(20)  | NOT NULL                 | 本族姓氏，如"李"         |
| compiled_at | DATE         |                          | 修谱日期                 |
| creator_id  | INT          | NOT NULL, FK → users(id) | 创建该族谱的用户         |

#### genealogy_users（族谱协作表）

用户与族谱的多对多中间表。一个用户可以参与多个族谱，一个族谱可以有多个协作者。

| 列           | 类型 | 约束                                   | 含义                   |
| ------------ | ---- | -------------------------------------- | ---------------------- |
| genealogy_id | INT  | FK → genealogies(id) ON DELETE CASCADE | 族谱 ID                |
| user_id      | INT  | FK → users(id) ON DELETE CASCADE       | 用户 ID                |
|              |      | PRIMARY KEY (genealogy_id, user_id)    | 联合主键，防止重复加入 |

#### members（成员表）

族谱中记录的每一个人的基本信息。

| 列           | 类型        | 约束                                             | 含义                      |
| ------------ | ----------- | ------------------------------------------------ | ------------------------- |
| id           | SERIAL      | PRIMARY KEY                                      | 成员 ID                   |
| genealogy_id | INT         | NOT NULL, FK → genealogies(id) ON DELETE CASCADE | 所属族谱                  |
| name         | VARCHAR(50) | NOT NULL                                         | 姓名                      |
| gender       | CHAR(1)     | NOT NULL, CHECK (gender IN ('M', 'F'))           | 性别（M = 男，F = 女）    |
| birth_year   | INT         |                                                  | 出生年份（公元）          |
| death_year   | INT         |                                                  | 卒年年份（在世则为 NULL） |
| bio          | TEXT        |                                                  | 生平简介                  |

CHECK 约束：

- 出生年份必须早于卒年年份（仅当两者都已知时检查）

#### parent_child（亲子关系表）

记录"谁是谁的父母"。parent_id 指向父母，child_id 指向子女，父母是父亲还是母亲由 members 表的 gender 区分。

| 列        | 类型 | 约束                               | 含义                         |
| --------- | ---- | ---------------------------------- | ---------------------------- |
| parent_id | INT  | FK → members(id) ON DELETE CASCADE | 父/母的成员 ID               |
| child_id  | INT  | FK → members(id) ON DELETE CASCADE | 子女的成员 ID                |
|           |      | PRIMARY KEY (parent_id, child_id)  | 联合主键，同一关系不重复记录 |

CHECK 约束：

- parent_id 不能等于 child_id（不能把自己设为自己的父母）

#### marriages（婚姻关系表）

一个人可以有多段婚姻（丧偶再婚等），因此婚姻关系独立建表。

| 列         | 类型   | 约束                                         | 含义                            |
| ---------- | ------ | -------------------------------------------- | ------------------------------- |
| id         | SERIAL | PRIMARY KEY                                  | 婚姻记录 ID                     |
| husband_id | INT    | NOT NULL, FK → members(id) ON DELETE CASCADE | 丈夫的成员 ID                   |
| wife_id    | INT    | NOT NULL, FK → members(id) ON DELETE CASCADE | 妻子的成员 ID                   |
| start_year | INT    |                                              | 结婚年份                        |
| end_year   | INT    |                                              | 婚姻结束年份（NULL = 持续至今） |

CHECK 约束：

- husband_id 不等于 wife_id
- 结婚年份不晚于结束年份

### 1.4 跨表校验（触发器实现）

触发器（TRIGGER）是在数据增删改时自动执行的检查逻辑。PostgreSQL 的 CHECK 约束只能检查同一行内的列，无法跨表比较（如检查配偶的 gender），因此跨表规则通过触发器实现：

| 规则                 | 触发条件                     |
| -------------------- | ---------------------------- |
| 夫为男性，妻为女性   | INSERT / UPDATE marriages    |
| 父母出生年份早于子女 | INSERT / UPDATE parent_child |
| 亲子双方属于同一族谱 | INSERT / UPDATE parent_child |
| 婚姻双方属于同一族谱 | INSERT / UPDATE marriages    |

### 1.5 索引设计

索引类似于书的目录——没有索引时数据库需逐行扫描，建了索引后可直接定位目标行。

| 索引                      | 作用                          | 类型           |
| ------------------------- | ----------------------------- | -------------- |
| `members.name` 的模糊搜索 | 支持 `LIKE '%张三%'` 快速检索 | GIN（pg_trgm） |
| `parent_child.parent_id`  | 根据父母快速查找所有子女      | B-tree         |
| `parent_child.child_id`   | 根据子女快速查找父母          | B-tree         |
| `members.genealogy_id`    | 快速筛选某族谱的全部成员      | B-tree         |
| `marriages.husband_id`    | 快速查找丈夫的婚姻记录        | B-tree         |
| `marriages.wife_id`       | 快速查找妻子的婚姻记录        | B-tree         |

GIN + pg_trgm 索引需要先启用 PostgreSQL 扩展：

```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

其原理是将姓名拆分为连续三元组（如"张三丰"拆为"张三""三丰"），搜索时匹配三元组而非全表扫描。

---

## 二、技术选型

### 2.1 后端

| 领域       | 选型                                                      |
| ---------- | --------------------------------------------------------- |
| 语言       | Python 3.12                                               |
| Web 框架   | Flask 3.x                                                 |
| 数据库     | PostgreSQL 16                                             |
| 数据库驱动 | psycopg2（含内置连接池）                                  |
| 认证       | Flask-Login                                               |
| 密码加密   | Werkzeug `generate_password_hash` / `check_password_hash` |
| 配置管理   | python-dotenv                                             |

**说明：**

- 不使用 ORM。本项目核心查询依赖 PostgreSQL Recursive CTE，半数为递归场景，ORM 在此场景下仍需退化为原生 SQL，引入 ORM 徒增一层抽象，收益为负。
- 不使用 Flask-WTF / WTForms。表单数量有限，直接通过 `request.form` 取值并手动校验即可。
- 表结构变更通过 SQL 脚本直接管理，不引入 Alembic。

### 2.2 前端

| 领域     | 选型                    |
| -------- | ----------------------- |
| 模板引擎 | Jinja2（Flask 内置）    |
| CSS 框架 | Bootstrap 5（CDN 引入） |

### 2.3 数据生成

| 领域     | 选型                                              |
| -------- | ------------------------------------------------- |
| 生成脚本 | Python 脚本                                       |
| 假数据   | Faker（`zh_CN` locale）                           |
| 输出格式 | CSV                                               |
| 导入方式 | `psycopg2.copy_from()`，使用 PostgreSQL COPY 协议 |

### 2.4 部署

| 领域     | 选型                                        |
| -------- | ------------------------------------------- |
| 容器编排 | Docker Compose（Flask + PostgreSQL 双容器） |

---

## 三、部分选择的依据

以下决策受项目客观约束或当前阶段权衡影响，记录于此以便回顾。

1. **Flask + Jinja 而非前后端分离** — 本项目以数据查询与展示为主，交互复杂度低，服务端渲染足以覆盖全部页面，引入前端框架会增加不必要的构建环节。
2. **递归模板而非 JavaScript 图表库** — 树形展示仅需表示层级父子关系，JS 图表库（D3.js、ECharts）的交互能力在此场景为过度设计，且引入后需额外处理数据序列化与异步加载。
3. **psycopg2 直连而非 ORM** — 核心查询为递归 CTE，ORM 在此类查询上无抽象优势，直接写 SQL 可减少认知层数。

---

## 四、预期项目结构

```
family-tree/
├── app/
│   ├── __init__.py          # create_app() 工厂
│   ├── db.py                # psycopg2 连接池管理，提供 get_db()
│   ├── routes.py            # 首页路由（hello-world）
│   ├── auth.py              # 注册 / 登录 / 登出 Blueprint（待实现）
│   ├── genealogy.py         # 族谱 CRUD Blueprint（待实现）
│   ├── member.py            # 成员 CRUD + 关系设置 Blueprint（待实现）
│   ├── query.py             # 祖先查询 / 亲缘查询 Blueprint（待实现）
│   ├── templates/
│   │   └── index.html       # 首页模板
│   └── static/
├── sql/
│   ├── schema.sql           # 建表 DDL
│   └── queries.sql          # 核心查询 SQL
├── data/
│   ├── generate.py          # 模拟数据生成脚本（待实现）
│   └── output/              # 生成的 CSV 文件（待实现）
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── config.py
├── run.py
└── README.md
```
