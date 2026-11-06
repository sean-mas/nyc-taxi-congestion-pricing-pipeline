# Answers to the project questions

Written for the course submission, about the January to March 2025 version of the pipeline. Moved here from the README, which now presents the project as a portfolio piece.

> **Draft notes, not final answers.** Sean: rewrite these in your own words before submitting.

**1. What are the steps you took to complete the project?**
- Set up the repo as an installable package, with Postgres in Docker Compose and one `.env` for Python, dbt and Prefect.
- Wrote the download script (step 1), then explored one quarter of data in a notebook to decide the cleaning rules.
- Loaded the raw files unchanged into Postgres, then built the dbt staging and daily revenue models with tests.
- Added a report step that reconciles row counts, then wrapped everything in a Prefect flow with retries, artifacts and a schedule.
- Delivered it as a series of small pull requests, each with tests.

**2. What challenges did you face?**
- Deciding what "revenue" means: refunds appear as negative rows, so I report gross, refunds and net separately.
- Trips dated outside their month: 11 fall outside the quarter entirely, and the reference solution's approach would report 94 days instead of 90.
- Making re-runs safe: the course loader replaces the table, which keeps only the last month loaded. Delete-and-insert per file fixed it.
- Tooling: a dbt dependency failed to install (GitHub timeout), so I pinned the version the course uses. Prefect didn't show my own log lines until I set their log level.

**3. What would you do differently if you had more time?**
- Run Prefect like production: server and worker in Docker, a work pool, and `flow.deploy()` instead of `serve()`.
- Make loads incremental, so only new months are fetched, and extend the pipeline to more months and years.
- Add a taxi-zone lookup and payment-type seed to break revenue down by borough and payment method.
- Publish dbt docs (a lineage graph) and add a small dashboard.
- Use Postgres `COPY` for faster loads at larger volumes, and set up a Prefect alert for failed runs.
