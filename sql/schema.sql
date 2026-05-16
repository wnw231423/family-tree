-- ============================================================
-- 族谱管理系统数据库初始化脚本
-- RDBMS: PostgreSQL 16
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

BEGIN;

-- 用户表：系统注册用户。
CREATE TABLE users (
    id              SERIAL          PRIMARY KEY,
    username        VARCHAR(50)     UNIQUE NOT NULL,
    password_hash   VARCHAR(255)    NOT NULL,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- 族谱表：每个族谱对应一个家族。
CREATE TABLE genealogies (
    id              SERIAL          PRIMARY KEY,
    name            VARCHAR(100)    NOT NULL,
    surname         VARCHAR(20)     NOT NULL,
    compiled_at     DATE,
    creator_id      INT             NOT NULL REFERENCES users(id),
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- 族谱协作表：用户与族谱之间的多对多关系。
CREATE TABLE genealogy_users (
    genealogy_id    INT             NOT NULL
                                    REFERENCES genealogies(id) ON DELETE CASCADE,
    user_id         INT             NOT NULL
                                    REFERENCES users(id) ON DELETE CASCADE,
    role            VARCHAR(20)     NOT NULL DEFAULT 'collaborator'
                                    CHECK (role IN ('owner', 'collaborator')),
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    PRIMARY KEY (genealogy_id, user_id)
);

-- 成员表：记录族谱中的人物基础信息。
CREATE TABLE members (
    id              SERIAL          PRIMARY KEY,
    genealogy_id    INT             NOT NULL
                                    REFERENCES genealogies(id) ON DELETE CASCADE,
    name            VARCHAR(50)     NOT NULL,
    gender          CHAR(1)         NOT NULL CHECK (gender IN ('M', 'F')),
    birth_year      INT,
    death_year      INT,
    generation      INT             NOT NULL DEFAULT 1 CHECK (generation > 0),
    bio             TEXT,
    created_at      TIMESTAMP       NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_lifetime CHECK (
        birth_year IS NULL
        OR death_year IS NULL
        OR birth_year < death_year
    ),
    CONSTRAINT chk_birth_year CHECK (
        birth_year IS NULL OR birth_year > 0
    ),
    CONSTRAINT chk_death_year CHECK (
        death_year IS NULL OR death_year > 0
    )
);

-- 亲子关系表：记录父亲/母亲与子女的血缘关系。
CREATE TABLE parent_child (
    parent_id       INT             NOT NULL
                                    REFERENCES members(id) ON DELETE CASCADE,
    child_id        INT             NOT NULL
                                    REFERENCES members(id) ON DELETE CASCADE,
    PRIMARY KEY (parent_id, child_id),
    CONSTRAINT chk_not_self CHECK (parent_id != child_id)
);

-- 婚姻关系表：记录夫妻关系。
CREATE TABLE marriages (
    id              SERIAL          PRIMARY KEY,
    husband_id      INT             NOT NULL
                                    REFERENCES members(id) ON DELETE CASCADE,
    wife_id         INT             NOT NULL
                                    REFERENCES members(id) ON DELETE CASCADE,
    start_year      INT,
    end_year        INT,
    CONSTRAINT chk_not_same CHECK (husband_id != wife_id),
    CONSTRAINT chk_marriage_period CHECK (
        start_year IS NULL
        OR end_year IS NULL
        OR start_year <= end_year
    )
);

-- 新建族谱时，将创建者同步为 owner 协作者。
CREATE OR REPLACE FUNCTION add_genealogy_owner()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO genealogy_users (genealogy_id, user_id, role)
    VALUES (NEW.id, NEW.creator_id, 'owner')
    ON CONFLICT (genealogy_id, user_id) DO UPDATE
        SET role = 'owner';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_add_genealogy_owner
    AFTER INSERT ON genealogies
    FOR EACH ROW EXECUTE FUNCTION add_genealogy_owner();

-- 校验婚姻双方性别与所属族谱。
CREATE OR REPLACE FUNCTION check_marriage_members()
RETURNS TRIGGER AS $$
DECLARE
    husband_gender CHAR(1);
    wife_gender CHAR(1);
    husband_genealogy INT;
    wife_genealogy INT;
BEGIN
    SELECT gender, genealogy_id
    INTO husband_gender, husband_genealogy
    FROM members
    WHERE id = NEW.husband_id;

    SELECT gender, genealogy_id
    INTO wife_gender, wife_genealogy
    FROM members
    WHERE id = NEW.wife_id;

    IF husband_gender != 'M' THEN
        RAISE EXCEPTION 'husband_id=% must reference a male member',
            NEW.husband_id;
    END IF;

    IF wife_gender != 'F' THEN
        RAISE EXCEPTION 'wife_id=% must reference a female member',
            NEW.wife_id;
    END IF;

    IF husband_genealogy != wife_genealogy THEN
        RAISE EXCEPTION 'marriage members must belong to the same genealogy';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_marriage_members
    BEFORE INSERT OR UPDATE ON marriages
    FOR EACH ROW EXECUTE FUNCTION check_marriage_members();

-- 校验亲子关系的年代、所属族谱和父母数量。
CREATE OR REPLACE FUNCTION check_parent_child_members()
RETURNS TRIGGER AS $$
DECLARE
    parent_birth_year INT;
    child_birth_year INT;
    parent_genealogy INT;
    child_genealogy INT;
    parent_gender CHAR(1);
    same_gender_parent_count INT;
BEGIN
    SELECT birth_year, genealogy_id, gender
    INTO parent_birth_year, parent_genealogy, parent_gender
    FROM members
    WHERE id = NEW.parent_id;

    SELECT birth_year, genealogy_id
    INTO child_birth_year, child_genealogy
    FROM members
    WHERE id = NEW.child_id;

    IF parent_genealogy != child_genealogy THEN
        RAISE EXCEPTION 'parent and child must belong to the same genealogy';
    END IF;

    IF parent_birth_year IS NOT NULL
       AND child_birth_year IS NOT NULL
       AND parent_birth_year >= child_birth_year THEN
        RAISE EXCEPTION 'parent birth year % must be earlier than child birth year %',
            parent_birth_year, child_birth_year;
    END IF;

    SELECT COUNT(*)
    INTO same_gender_parent_count
    FROM parent_child pc
    JOIN members m ON m.id = pc.parent_id
    WHERE pc.child_id = NEW.child_id
      AND pc.parent_id != NEW.parent_id
      AND m.gender = parent_gender;

    IF same_gender_parent_count > 0 THEN
        RAISE EXCEPTION 'a child can have only one recorded father and one recorded mother';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_parent_child_members
    BEFORE INSERT OR UPDATE ON parent_child
    FOR EACH ROW EXECUTE FUNCTION check_parent_child_members();

-- 索引设计。
CREATE INDEX idx_users_username ON users (username);
CREATE INDEX idx_genealogies_creator ON genealogies (creator_id);
CREATE INDEX idx_genealogy_users_user ON genealogy_users (user_id);
CREATE INDEX idx_members_genealogy ON members (genealogy_id);
CREATE INDEX idx_members_genealogy_generation ON members (genealogy_id, generation);
CREATE INDEX idx_members_name_trgm ON members USING gin (name gin_trgm_ops);
CREATE INDEX idx_parent_child_parent ON parent_child (parent_id);
CREATE INDEX idx_parent_child_child ON parent_child (child_id);
CREATE INDEX idx_marriages_husband ON marriages (husband_id);
CREATE INDEX idx_marriages_wife ON marriages (wife_id);
CREATE UNIQUE INDEX idx_marriages_pair_period
    ON marriages (husband_id, wife_id, COALESCE(start_year, 0));

COMMIT;
