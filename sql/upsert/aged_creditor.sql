BEGIN;

\echo Create import table...

CREATE TEMPORARY TABLE aged_creditor_upsert
(
        demarcation_code TEXT,
        period_code TEXT,
        item_code TEXT,
        g1_amount DECIMAL,
        l1_amount DECIMAL,
        l120_amount DECIMAL,
        l150_amount DECIMAL,
        l180_amount DECIMAL,
        l30_amount DECIMAL,
        l60_amount DECIMAL,
        l90_amount DECIMAL,
        total_amount DECIMAL
) ON COMMIT DROP;

\echo Read data...

\copy aged_creditor_upsert (demarcation_code, period_code, item_code, g1_amount, l1_amount, l120_amount, l150_amount, l180_amount, l30_amount, l60_amount, l90_amount, total_amount) FROM '/home/jdb/proj/code4sa/municipal_finance/datasets/2017q1/Section 71 Q1 2016-17/cred_2017q1_acrmun.csv' DELIMITER ',' CSV HEADER;

\echo Drop not null constraints...

alter table aged_creditor_facts
      alter column financial_year drop not null,
      alter column amount_type_code drop not null,
      alter column period_length drop not null,
      alter column financial_period drop not null;

\echo Update changed values...

UPDATE aged_creditor_facts f
SET g1_amount = i.g1_amount,
    l1_amount = i.l1_amount,
    l120_amount = i.l120_amount,
    l150_amount = i.l150_amount,
    l180_amount = i.l180_amount,
    l30_amount = i.l30_amount,
    l60_amount = i.l60_amount,
    l90_amount = i.l90_amount,
    total_amount = i.total_amount
FROM aged_creditor_upsert i
WHERE f.demarcation_code = i.demarcation_code
AND f.period_code = i.period_code
AND f.item_code = i.item_code
AND (f.g1_amount != i.g1_amount or
     f.l1_amount != i.l1_amount or
     f.l120_amount != i.l120_amount or
     f.l150_amount != i.l150_amount or
     f.l180_amount != i.l180_amount or
     f.l30_amount != i.l30_amount or
     f.l60_amount != i.l60_amount or
     f.l90_amount != i.l90_amount or
     f.total_amount != i.total_amount);

\echo Insert new values...

INSERT INTO aged_creditor_facts
(
    demarcation_code,
    period_code,
    item_code,
    g1_amount,
    l1_amount,
    l120_amount,
    l150_amount,
    l180_amount,
    l30_amount,
    l60_amount,
    l90_amount,
    total_amount
)
SELECT demarcation_code, period_code, item_code, g1_amount, l1_amount, l120_amount, l150_amount, l180_amount, l30_amount, l60_amount, l90_amount, total_amount
FROM aged_creditor_upsert i
WHERE
    NOT EXISTS (
        SELECT * FROM aged_creditor_facts f
        WHERE f.demarcation_code = i.demarcation_code
        AND f.period_code = i.period_code
        AND f.item_code = i.item_code
    );

\echo Decode period_code...

update aged_creditor_facts set financial_year = cast(left(period_code, 4) as int) where financial_year is null;
update aged_creditor_facts set amount_type_code = substr(period_code, 5) where substr(period_code, 5) in ('IBY1', 'IBY2', 'ADJB', 'ORGB', 'AUDA', 'PAUD') and amount_type_code is null;
update aged_creditor_facts set amount_type_code = 'ACT' where substr(period_code, 5) not in ('IBY1', 'IBY2', 'ADJB', 'ORGB', 'AUDA', 'PAUD') and amount_type_code is null;
update aged_creditor_facts set period_length = 'year' where substr(period_code, 5, 3) not similar to 'M\d{2}' and period_length is null;
update aged_creditor_facts set period_length = 'month' where substr(period_code, 5, 3) similar to 'M\d{2}' and period_length is null;
update aged_creditor_facts set financial_period = cast(right(period_code, 2) as int) where period_length = 'month' and financial_period is null;
update aged_creditor_facts set financial_period = cast(left(period_code, 4) as int) where period_length = 'year' and financial_period is null;

\echo Add back not null constraints...

alter table aged_creditor_facts
      alter column financial_year set not null,
      alter column amount_type_code set not null,
      alter column period_length set not null,
      alter column financial_period set not null;

COMMIT;
