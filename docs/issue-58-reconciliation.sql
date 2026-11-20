-- Read-only reconciliation against the isolated SQLite fixture created by
-- backend/scripts/issue58_reconciliation_seed.py.
CREATE TEMP VIEW issue58_matching AS
SELECT a.id AS application_id, a.account, a.name, a.email, a.department,
       a.application_date, k.status AS key_status
FROM api_key_applications AS a
JOIN api_keys AS k ON k.application_id = a.id
WHERE a.application_date BETWEEN '2026-05-01' AND '2026-05-31';

CREATE TEMP VIEW issue58_by_owner AS
SELECT account, name, email, MAX(department) AS owner_department,
       COUNT(*) AS total_applications,
       SUM(CASE WHEN key_status = 'active' THEN 1 ELSE 0 END) AS active_count,
       SUM(CASE WHEN key_status = 'revoked' THEN 1 ELSE 0 END) AS revoked_count,
       SUM(CASE WHEN key_status = 'expired' THEN 1 ELSE 0 END) AS expired_count
FROM issue58_matching
GROUP BY account, name, email;

SELECT account, department, application_date, key_status
FROM issue58_matching
ORDER BY application_date, account;

SELECT owner_department AS label,
       SUM(total_applications) AS value
FROM issue58_by_owner
GROUP BY owner_department
ORDER BY value DESC, label ASC
LIMIT 5;

SELECT COUNT(*) AS group_count, SUM(value) AS total_value,
       (SELECT SUM(value) FROM (
           SELECT owner_department, SUM(total_applications) AS value
           FROM issue58_by_owner GROUP BY owner_department
           ORDER BY value DESC, owner_department ASC LIMIT 5
       )) AS displayed_value
FROM (
    SELECT owner_department, SUM(total_applications) AS value
    FROM issue58_by_owner GROUP BY owner_department
);

SELECT account AS label, total_applications AS value
FROM issue58_by_owner
ORDER BY value DESC, label ASC
LIMIT 5;

SELECT COUNT(*) AS group_count,
       SUM(total_applications) AS total_value,
       (SELECT SUM(value) FROM (
           SELECT total_applications AS value FROM issue58_by_owner
           ORDER BY value DESC, account ASC LIMIT 5
       )) AS displayed_value,
       SUM(active_count) AS active_count,
       SUM(revoked_count) AS revoked_count,
       SUM(expired_count) AS expired_count
FROM issue58_by_owner;
