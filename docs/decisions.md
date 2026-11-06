# Decisions

Short log of the choices behind the pipeline: what was decided, why, and the alternative that wasn't picked.

## How the pipeline is built

### 1. ELT, not ETL

- **Decision:** load the raw files unchanged into Postgres first, then clean them with SQL inside the database (extract, load, transform).
- **Why:** the raw copy stays untouched, so a cleaning rule can change and run again without downloading anything. Every row can be traced back to its file, and each layer can be tested on its own.
- **Not picked:** ETL with pandas, which cleans the data before storing it (the course's reference solution works this way). It's simpler for one quarter, but every rule change means reading all files again, and the stored data no longer shows what was removed.

### 2. Postgres and dbt, not pandas or DuckDB

- **Decision:** keep the data in Postgres (in Docker) and write the transforms as dbt models: SQL files that build tables in order and test them.
- **Why:** the cleaning rules are plain SQL anyone can read, each table has its tests next to it, and a failing test stops the run. This is how analytics teams usually work, and it's what the course teaches.
- **Not picked:** pandas alone, where the rules hide in Python and are harder to test step by step. DuckDB, a database in a single file with no server: honestly the simpler and faster choice for a million rows, but not picked so the project practises a server database like the ones used in production.

### 3. Replace each file's rows on every load

- **Decision:** in one transaction per file, delete that file's rows and insert them again.
- **Why:** running the pipeline twice gives the same table, never duplicates. If a load fails halfway, the old rows come back.
- **Not picked:** replacing the whole table (the course's loader did this, so only the last month loaded survived), or only appending (duplicates on every re-run).

### 4. A fixed column list for the raw table

- **Decision:** create `raw.green_trips` from a column list in [load.py](../src/green_taxi/load.py). A file without a column loads NULL into it; a file with an unknown column stops the load.
- **Why:** files before 2025 have no `cbd_congestion_fee` column. A table copied from whichever file loads first would reject every 2025 file if a 2024 file came first.
- **Not picked:** letting pandas create the table from the first file (the result depends on load order), or silently dropping unknown columns (data loss nobody notices).

### 5. `dbt build`, not `dbt run`

- **Decision:** run `dbt build`.
- **Why:** it tests each table right after building it and skips everything that depends on a failed test, so a wrong number never reaches the outputs.
- **Not picked:** `dbt run` followed by `dbt test`, which builds every table first and only then finds out something is wrong.

### 6. The months choose both the files and the days

- **Decision:** `--months` decides which files count and which days dbt keeps (passed as `dbt build --vars`). The months must follow each other.
- **Why:** the result then depends on `--months` alone, not on what earlier runs left in the raw table: January to March 2025 gives the course's $3,395,290.56 even after an 18-month run. A gap between months would leave days without data inside the period.
- **Not picked:** a fixed period in `dbt_project.yml` (changing the window meant editing two places), or using every file in the raw table.

### 7. Postgres on port 5433

- **Decision:** expose Postgres on port 5433 on the laptop.
- **Why:** other course projects run their own Postgres containers on the default 5432, and two containers can't share a port.
- **Not picked:** 5432, which clashes as soon as another course container is running.

### 8. dbt's parser package pinned to 2.0.8

- **Decision:** pin `dbt-core-experimental-parser`, which dbt itself depends on, to 2.0.8 in `pyproject.toml`.
- **Why:** 2.0.11 installs by downloading a file from GitHub, which timed out. 2.0.8 installs cleanly and is the version the course's workflow-orchestration repo uses.
- **Not picked:** the latest version, which doesn't install reliably.

## What counts as revenue

### 9. Gross revenue, refunds and net revenue apart

- **Decision:** rows with a negative `total_amount` count as refunds, not trips. Net revenue = gross revenue + refunds.
- **Why:** January to March 2025 has 478 such rows (−$6,462.61): refunds, disputes and voided trips. Counting them as trips inflates the trip count; dropping them overstates revenue.
- **Not picked:** dropping negative rows, or treating them as ordinary trips.

### 10. Each trip counts on its pickup date, across all files

- **Decision:** group by pickup date over all chosen files, and keep only pickups inside the period.
- **Why:** in January to March 2025, 62 trips sit in a neighbouring month's file and 11 are dated outside the quarter. Totals per file would put those trips in the wrong month, and without the period filter the result would have 94 days instead of 90 (the course's reference approach does this).
- **Not picked:** totals per file.

### 11. Fare revenue next to net revenue

- **Decision:** add `fare_revenue` = fare + extras + tips, added up from its own three columns.
- **Why:** `total_amount` includes taxes, tolls and surcharges that are passed on to the city, the state and the MTA, and from 2025 the $0.75 congestion fee itself, which would make net revenue rise from the fee alone. The parts don't always add up to `total_amount` (about 14% of rows), so subtracting taxes from the total would carry those gaps along.
- **Not picked:** `total_amount` minus taxes.

## The congestion pricing question

### 12. Compare with the winter before

- **Decision:** split two winters on 5 January: 2024/25, when the fee started, and 2023/24, without it. The fee's effect is the difference between their changes (analysts call this a difference-in-differences). The winters are listed in [a small CSV](../dbt/seeds/congestion_pricing_windows.csv).
- **Why:** taxi demand always drops after the holidays. A plain before/after comparison would blame the fee for that dip. The winter before shows how big the normal dip is: weekday trips fell 10.5% then, against 3.6% with the fee.
- **Not picked:** a plain before/after comparison (it would report the seasonal drop as the fee's effect), or comparing the months after the fee with the same months a year earlier (that mixes in Green Taxi's long-term decline: trips were already 17% lower before the fee).

### 13. Weekdays apart from weekends

- **Decision:** compare weekdays with weekdays and weekends with weekends.
- **Why:** they have different trip patterns, and the before and after periods don't hold the same mix of them.
- **Not picked:** all days together.
