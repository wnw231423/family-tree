-- ============================================================
-- 族谱管理系统 数据库初始化
-- ============================================================
-- 所有 SQL 关键字采用大写是为了提高可读性，这是 SQL 脚本的通用写法。
-- SERIAL = 自增整数，插入时无需手动指定值
-- REFERENCES xxx(id) = 外键，指向 xxx 表的 id 列
-- ON DELETE CASCADE = 级联删除：删除主表记录时，自动删除关联的子表记录

CREATE EXTENSION IF NOT EXISTS pg_trgm;

BEGIN;

-- ============================================================
-- 1. 用户表（users）
-- ============================================================
CREATE TABLE users (
    id              SERIAL          PRIMARY KEY,        -- 用户 ID（自增主键）
    username        VARCHAR(50)     UNIQUE NOT NULL,    -- 登录用户名（不可重复）
    password_hash   VARCHAR(255)    NOT NULL,           -- 密码哈希值（不存明文）
    created_at      TIMESTAMP       DEFAULT NOW()       -- 注册时间
);

-- ============================================================
-- 2. 族谱表（genealogies）
-- ============================================================
CREATE TABLE genealogies (
    id              SERIAL          PRIMARY KEY,        -- 族谱 ID
    name            VARCHAR(100)    NOT NULL,           -- 谱名，如"陇西李氏大宗谱"
    surname         VARCHAR(20)     NOT NULL,           -- 本族姓氏，如"李"
    compiled_at     DATE,                               -- 修谱日期（首次编纂时间）
    creator_id      INT             NOT NULL REFERENCES users(id) -- 创建者
);

-- ============================================================
-- 3. 族谱协作表（genealogy_users）
--    用户 <=> 族谱 的多对多关系
--    如：张三创建了李氏宗谱，又邀请李四一起编辑
-- ============================================================
CREATE TABLE genealogy_users (
    genealogy_id    INT NOT NULL REFERENCES genealogies(id) ON DELETE CASCADE,  -- 族谱 ID
    user_id         INT NOT NULL REFERENCES users(id)       ON DELETE CASCADE,  -- 用户 ID
    PRIMARY KEY (genealogy_id, user_id)     -- 防止同一用户被重复加入同一族谱
);

-- ============================================================
-- 4. 成员表（members）
--    族谱中记录的每一个人
-- ============================================================
CREATE TABLE members (
    id              SERIAL          PRIMARY KEY,        -- 成员 ID
    genealogy_id    INT             NOT NULL REFERENCES genealogies(id) ON DELETE CASCADE, -- 所属族谱
    name            VARCHAR(50)     NOT NULL,           -- 姓名
    gender          CHAR(1)         NOT NULL            -- 性别：M = 男，F = 女
                                    CHECK (gender IN ('M', 'F')),
    birth_year      INT,                                -- 出生年份（公元，如 1885）
    death_year      INT,                                -- 卒年年份（在世则为 NULL）
    bio             TEXT,                               -- 生平简介
    -- 校验：出生年份必须早于卒年年份（仅当两者都已知时检查）
    CONSTRAINT chk_lifetime CHECK (
        birth_year IS NULL
        OR death_year IS NULL
        OR birth_year < death_year
    )
);

-- ============================================================
-- 5. 亲子关系表（parent_child）
--    记录"谁是谁的父母"
--    例如：parent_id=5, child_id=12 表示成员 5 是成员 12 的父母
--          至于 5 是父亲还是母亲，通过 members 表的 gender 区分
-- ============================================================
CREATE TABLE parent_child (
    parent_id   INT NOT NULL REFERENCES members(id) ON DELETE CASCADE, -- 父/母的成员 ID
    child_id    INT NOT NULL REFERENCES members(id) ON DELETE CASCADE, -- 子女的成员 ID
    PRIMARY KEY (parent_id, child_id),
    CONSTRAINT chk_not_self CHECK (parent_id != child_id) -- 不能把自己设为自己的父母
);

-- ============================================================
-- 6. 婚姻关系表（marriages）
--    记录夫妻关系
--    一个人可以有多段婚姻（丧偶再婚等），所以单独建表
-- ============================================================
CREATE TABLE marriages (
    id          SERIAL  PRIMARY KEY,        -- 婚姻记录 ID
    husband_id  INT     NOT NULL REFERENCES members(id) ON DELETE CASCADE, -- 丈夫的成员 ID
    wife_id     INT     NOT NULL REFERENCES members(id) ON DELETE CASCADE, -- 妻子的成员 ID
    start_year  INT,                        -- 结婚年份
    end_year    INT,                        -- 婚姻结束年份（离婚或丧偶，NULL = 持续至今）
    CONSTRAINT chk_not_same CHECK (husband_id != wife_id),      -- 不能和自己结婚
    CONSTRAINT chk_marriage_period CHECK (
        start_year IS NULL
        OR end_year IS NULL
        OR start_year <= end_year                              -- 结婚年份不晚于结束年份
    )
);


-- ============================================================
-- 触发器（TRIGGER）
-- ============================================================
-- 触发器 = 数据库的"自动守门员"，在增删改数据时自动执行检查，
-- 不满足条件就拒绝操作。用于实现单表 CHECK 做不到的跨表校验。

-- --------------------------------------------------------
-- 触发器 1：插入婚姻记录时，校验夫必须是男、妻必须是女
-- --------------------------------------------------------
CREATE OR REPLACE FUNCTION check_marriage_gender()
RETURNS TRIGGER AS $$
DECLARE
    hus_gender CHAR(1);         -- 临时变量：存丈夫的性别
    wife_gender CHAR(1);        -- 临时变量：存妻子的性别
BEGIN
    -- 查出 husband_id 对应的性别
    SELECT gender INTO hus_gender FROM members WHERE id = NEW.husband_id;
    -- 查出 wife_id 对应的性别
    SELECT gender INTO wife_gender FROM members WHERE id = NEW.wife_id;

    IF hus_gender != 'M' THEN
        RAISE EXCEPTION '丈夫（ID=%）性别是 %，必须是 M', NEW.husband_id, hus_gender;
    END IF;
    IF wife_gender != 'F' THEN
        RAISE EXCEPTION '妻子（ID=%）性别是 %，必须是 F', NEW.wife_id, wife_gender;
    END IF;
    RETURN NEW; -- 校验通过，放行
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_marriage_gender
    BEFORE INSERT OR UPDATE ON marriages      -- 在新增或修改 marriages 之前触发
    FOR EACH ROW EXECUTE FUNCTION check_marriage_gender();

-- --------------------------------------------------------
-- 触发器 2：插入亲子记录时，校验父母出生年份早于子女 + 同族谱
-- --------------------------------------------------------
CREATE OR REPLACE FUNCTION check_parent_age()
RETURNS TRIGGER AS $$
DECLARE
    parent_by INT;
    child_by INT;
    parent_genealogy INT;
    child_genealogy INT;
BEGIN
    -- 查出父母的出生年份和族谱
    SELECT birth_year, genealogy_id INTO parent_by, parent_genealogy
        FROM members WHERE id = NEW.parent_id;
    -- 查出子女的出生年份和族谱
    SELECT birth_year, genealogy_id INTO child_by, child_genealogy
        FROM members WHERE id = NEW.child_id;

    -- 双方出生年份都已知时，父母必须早于子女
    IF parent_by IS NOT NULL AND child_by IS NOT NULL AND parent_by >= child_by THEN
        RAISE EXCEPTION '父母出生年份（%）必须早于子女出生年份（%）', parent_by, child_by;
    END IF;

    -- 亲子必须属于同一族谱
    IF parent_genealogy != child_genealogy THEN
        RAISE EXCEPTION '亲子关系双方必须属于同一族谱';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_parent_age
    BEFORE INSERT OR UPDATE ON parent_child      -- 在新增或修改 parent_child 之前触发
    FOR EACH ROW EXECUTE FUNCTION check_parent_age();

-- --------------------------------------------------------
-- 触发器 3：插入婚姻记录时，校验夫妻属于同一族谱
-- --------------------------------------------------------
CREATE OR REPLACE FUNCTION check_marriage_genealogy()
RETURNS TRIGGER AS $$
DECLARE
    hus_genealogy INT;
    wife_genealogy INT;
BEGIN
    SELECT genealogy_id INTO hus_genealogy FROM members WHERE id = NEW.husband_id;
    SELECT genealogy_id INTO wife_genealogy FROM members WHERE id = NEW.wife_id;

    IF hus_genealogy != wife_genealogy THEN
        RAISE EXCEPTION '婚姻关系双方必须属于同一族谱';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_marriage_genealogy
    BEFORE INSERT OR UPDATE ON marriages        -- 在新增或修改 marriages 之前触发
    FOR EACH ROW EXECUTE FUNCTION check_marriage_genealogy();


-- ============================================================
-- 索引（INDEX）
-- ============================================================
-- 索引 = 书的目录。没有索引，数据库需要逐行扫描（翻遍整本书）；
-- 建了索引，数据库可以快速定位目标行（直接查目录）。

-- --------------------------------------------------------
-- 索引 1：姓名模糊搜索
-- --------------------------------------------------------
-- 使用 pg_trgm 插件实现 LIKE '%张三%' 的快速搜索。
-- GIN 是索引结构的一种（倒排索引），
-- gin_trgm_ops 是把姓名拆成连续三个字符一组（三元组），搜索时匹配三元组，
-- 比全表扫描快几十到上百倍。
-- 使用前需在数据库中执行：CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_members_name_trgm ON members USING gin (name gin_trgm_ops);

-- --------------------------------------------------------
-- 索引 2：查某人的所有子女（按 parent_id 查找 child_id）
-- --------------------------------------------------------
-- B-tree 是索引的默认类型，适合等值查询（parent_id = 某值）和范围查询。
-- 不加这条索引时，查 5 万成员中某人的子女需要扫全表；
-- 加上后只需几次磁盘读取。
CREATE INDEX idx_parent_child_parent ON parent_child (parent_id);

-- --------------------------------------------------------
-- 索引 3：查某人的父母是谁（按 child_id 查找 parent_id）
-- --------------------------------------------------------
CREATE INDEX idx_parent_child_child  ON parent_child (child_id);

-- --------------------------------------------------------
-- 索引 4：查某个族谱下的所有成员
-- --------------------------------------------------------
CREATE INDEX idx_members_genealogy ON members (genealogy_id);

-- --------------------------------------------------------
-- 索引 5、6：查某人的配偶
-- --------------------------------------------------------
CREATE INDEX idx_marriages_husband ON marriages (husband_id);
CREATE INDEX idx_marriages_wife    ON marriages (wife_id);

COMMIT;
