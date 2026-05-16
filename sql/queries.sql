-- ============================================================
-- 族谱管理系统核心查询 SQL
-- 参数写法采用 psql 变量，例如 :member_id、:genealogy_id。
-- ============================================================

-- 1. 给定成员 ID，查询其配偶及所有子女。
WITH target AS (
    SELECT :member_id::INT AS member_id
),
spouses AS (
    SELECT
        m.id,
        m.name,
        m.gender,
        'spouse' AS relation_type
    FROM target t
    JOIN marriages ma
        ON ma.husband_id = t.member_id OR ma.wife_id = t.member_id
    JOIN members m
        ON m.id = CASE
            WHEN ma.husband_id = t.member_id THEN ma.wife_id
            ELSE ma.husband_id
        END
),
children AS (
    SELECT
        m.id,
        m.name,
        m.gender,
        'child' AS relation_type
    FROM target t
    JOIN parent_child pc ON pc.parent_id = t.member_id
    JOIN members m ON m.id = pc.child_id
)
SELECT * FROM spouses
UNION ALL
SELECT * FROM children
ORDER BY relation_type, id;

-- 2. Recursive CTE：输入成员 ID，输出向上追溯的所有历代祖先。
WITH RECURSIVE ancestors AS (
    SELECT
        p.id,
        p.name,
        p.gender,
        p.birth_year,
        p.death_year,
        1 AS depth,
        ARRAY[c.id, p.id] AS path
    FROM members c
    JOIN parent_child pc ON pc.child_id = c.id
    JOIN members p ON p.id = pc.parent_id
    WHERE c.id = :member_id::INT

    UNION ALL

    SELECT
        gp.id,
        gp.name,
        gp.gender,
        gp.birth_year,
        gp.death_year,
        a.depth + 1,
        a.path || gp.id
    FROM ancestors a
    JOIN parent_child pc ON pc.child_id = a.id
    JOIN members gp ON gp.id = pc.parent_id
    WHERE NOT gp.id = ANY(a.path)
)
SELECT *
FROM ancestors
ORDER BY depth, id;

-- 3. 统计某个家族中平均寿命最长的一代人。
SELECT
    generation,
    COUNT(*) AS member_count,
    ROUND(AVG(death_year - birth_year), 2) AS avg_lifespan
FROM members
WHERE genealogy_id = :genealogy_id::INT
  AND birth_year IS NOT NULL
  AND death_year IS NOT NULL
GROUP BY generation
HAVING COUNT(*) > 0
ORDER BY avg_lifespan DESC, generation
LIMIT 1;

-- 4. 查询年龄超过 50 岁且没有配偶的男性成员。
SELECT
    m.id,
    m.name,
    m.birth_year,
    EXTRACT(YEAR FROM CURRENT_DATE)::INT - m.birth_year AS age
FROM members m
WHERE m.genealogy_id = :genealogy_id::INT
  AND m.gender = 'M'
  AND m.birth_year IS NOT NULL
  AND EXTRACT(YEAR FROM CURRENT_DATE)::INT - m.birth_year > 50
  AND NOT EXISTS (
      SELECT 1
      FROM marriages ma
      WHERE ma.husband_id = m.id OR ma.wife_id = m.id
  )
ORDER BY age DESC, m.id;

-- 5. 找出出生年份早于该辈分平均出生年份的所有成员。
WITH generation_avg AS (
    SELECT
        genealogy_id,
        generation,
        AVG(birth_year) AS avg_birth_year
    FROM members
    WHERE genealogy_id = :genealogy_id::INT
      AND birth_year IS NOT NULL
    GROUP BY genealogy_id, generation
)
SELECT
    m.id,
    m.name,
    m.generation,
    m.birth_year,
    ROUND(ga.avg_birth_year, 2) AS generation_avg_birth_year
FROM members m
JOIN generation_avg ga
    ON ga.genealogy_id = m.genealogy_id
   AND ga.generation = m.generation
WHERE m.genealogy_id = :genealogy_id::INT
  AND m.birth_year IS NOT NULL
  AND m.birth_year < ga.avg_birth_year
ORDER BY m.generation, m.birth_year, m.id;

-- 6. 查询两名成员之间是否存在亲缘链路。
WITH RECURSIVE
up_a AS (
    SELECT
        m.id,
        ARRAY[m.id] AS path_ids,
        ARRAY[m.name::TEXT] AS path_names,
        0 AS depth
    FROM members m
    WHERE m.id = :member_a_id::INT
      AND m.genealogy_id = :genealogy_id::INT

    UNION ALL

    SELECT
        parent.id,
        up_a.path_ids || parent.id,
        up_a.path_names || parent.name::TEXT,
        up_a.depth + 1
    FROM up_a
    JOIN parent_child pc ON pc.child_id = up_a.id
    JOIN members parent ON parent.id = pc.parent_id
    WHERE parent.genealogy_id = :genealogy_id::INT
      AND NOT parent.id = ANY(up_a.path_ids)
      AND up_a.depth < 60
),
up_b AS (
    SELECT
        m.id,
        ARRAY[m.id] AS path_ids,
        ARRAY[m.name::TEXT] AS path_names,
        0 AS depth
    FROM members m
    WHERE m.id = :member_b_id::INT
      AND m.genealogy_id = :genealogy_id::INT

    UNION ALL

    SELECT
        parent.id,
        up_b.path_ids || parent.id,
        up_b.path_names || parent.name::TEXT,
        up_b.depth + 1
    FROM up_b
    JOIN parent_child pc ON pc.child_id = up_b.id
    JOIN members parent ON parent.id = pc.parent_id
    WHERE parent.genealogy_id = :genealogy_id::INT
      AND NOT parent.id = ANY(up_b.path_ids)
      AND up_b.depth < 60
),
common_ancestor_paths AS (
    SELECT
        up_a.path_ids ||
            COALESCE((
                SELECT array_agg(value ORDER BY ord DESC)
                FROM unnest(up_b.path_ids) WITH ORDINALITY AS t(value, ord)
                WHERE ord < cardinality(up_b.path_ids)
            ), ARRAY[]::INT[]) AS path_ids,
        up_a.path_names ||
            COALESCE((
                SELECT array_agg(value ORDER BY ord DESC)
                FROM unnest(up_b.path_names) WITH ORDINALITY AS t(value, ord)
                WHERE ord < cardinality(up_b.path_names)
            ), ARRAY[]::TEXT[]) AS path_names,
        up_a.depth + up_b.depth AS depth
    FROM up_a
    JOIN up_b ON up_b.id = up_a.id
),
spouse_paths AS (
    SELECT
        ARRAY[a.id, b.id] AS path_ids,
        ARRAY[a.name::TEXT, b.name::TEXT] AS path_names,
        1 AS depth
    FROM members a
    JOIN members b
        ON b.id = :member_b_id::INT
       AND b.genealogy_id = :genealogy_id::INT
    WHERE a.id = :member_a_id::INT
      AND a.genealogy_id = :genealogy_id::INT
      AND EXISTS (
          SELECT 1
          FROM marriages ma
          WHERE (ma.husband_id = a.id AND ma.wife_id = b.id)
             OR (ma.husband_id = b.id AND ma.wife_id = a.id)
      )
),
candidate_paths AS (
    SELECT * FROM common_ancestor_paths
    UNION ALL
    SELECT * FROM spouse_paths
)
SELECT
    path_ids,
    array_to_string(path_names, ' -> ') AS relation_path,
    depth
FROM candidate_paths
ORDER BY depth, cardinality(path_ids)
LIMIT 1;

-- 7. 查询某成员的所有直系后代。
WITH RECURSIVE descendants AS (
    SELECT
        c.id,
        c.name,
        c.gender,
        c.birth_year,
        c.generation,
        1 AS depth,
        ARRAY[p.id, c.id] AS path
    FROM members p
    JOIN parent_child pc ON pc.parent_id = p.id
    JOIN members c ON c.id = pc.child_id
    WHERE p.id = :member_id::INT

    UNION ALL

    SELECT
        c.id,
        c.name,
        c.gender,
        c.birth_year,
        c.generation,
        d.depth + 1,
        d.path || c.id
    FROM descendants d
    JOIN parent_child pc ON pc.parent_id = d.id
    JOIN members c ON c.id = pc.child_id
    WHERE NOT c.id = ANY(d.path)
)
SELECT *
FROM descendants
ORDER BY depth, generation, birth_year NULLS LAST, id;

-- 8. 查询某曾祖父的所有曾孙，供 EXPLAIN 性能对比使用。
SELECT DISTINCT great_grandchild.*
FROM parent_child pc1
JOIN parent_child pc2 ON pc2.parent_id = pc1.child_id
JOIN parent_child pc3 ON pc3.parent_id = pc2.child_id
JOIN members great_grandchild ON great_grandchild.id = pc3.child_id
WHERE pc1.parent_id = :member_id::INT
ORDER BY great_grandchild.id;
