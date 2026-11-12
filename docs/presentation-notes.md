# Presentation: speaker notes

The script for the 5-minute [presentation](presentation.pdf), one block per slide. It's about 600 words, roughly 4½ minutes at a calm pace.

## 1. Did congestion pricing change NYC’s Green Taxis? (15 s)

Hi, I’m Sean. My project is a data pipeline for New York’s Green Taxi trips. The course asked for revenue per day. I also used the pipeline to answer a question that was in the news: did New York’s congestion pricing change taxi trips and revenue?

## 2. The brief, and the question I added (35 s)

The brief was clear: three months of Green Taxi data, revenue per day, and Prefect as a bonus. Once that worked, I asked a real question. Since 5 January 2025, every taxi trip into lower Manhattan pays a congestion fee. Did that change anything for Green Taxis? To answer it, I extended the pipeline from 3 to 18 months, as on the timeline: the course quarter sits at the end, and the winter before gives me a comparison without the fee.

## 3. How it works: four steps, run by Prefect (45 s)

Here’s how it works, in four steps. Extract downloads one Parquet file per month. Load copies it, unchanged, into Postgres. Transform is dbt: SQL that cleans the trips and adds them up per day, with tests. Report writes the tables and charts and counts rows at every step. Prefect runs all four: it retries failed downloads, keeps the logs, and shows the results in a web UI. I chose ELT over ETL because the raw copy stays in the database. I can change a cleaning rule and re-run it without downloading anything again.

## 4. What the data needed before adding it up (35 s)

Before adding anything up, I explored the data in a notebook. Of 146,486 rows, I kept 146,475. Eleven trips were dated outside the quarter: some in December 2024, some on 1 April. Keep them and you report 94 days instead of 90; the course’s reference solution does exactly that. And 478 rows are refunds with negative amounts. I didn’t drop or hide them: I report gross revenue, refunds and net revenue separately.

## 5. Course result: $3.4 million in 90 days (35 s)

The course result: 3.4 million dollars of net revenue in 90 days, about 37,700 dollars on an average day. The chart shows a clear weekly rhythm: weekdays are busy, and Sundays, the dark dots, are the quietest day of every week. Thursdays earn about 45% more than Sundays. A classmate built the same pipeline independently and got exactly the same numbers, to the cent.

## 6. Congestion pricing: no visible effect (45 s)

So, did congestion pricing change anything? After 5 January, weekday trips fell 3.6% and fare revenue per day fell 10.6%. That looks like an effect, until you check the year before, with no fee. Over the same dates, trips fell 10.5% and revenue 17.3%. So the drop is the normal winter dip after the holidays, and this time it was even smaller. My honest answer: no visible effect on Green Taxis. Only about 1 in 12 weekday trips paid the fee, because Green Taxis can’t pick up street hails in most of Manhattan.

## 7. Built so the numbers can be trusted (30 s)

How do I know the numbers are right? Every run checks itself with 34 data checks, for example that the daily totals match the cleaned trips to the cent. If one fails, the run stops. On top of that, 34 code tests run on every pull request. Running the pipeline twice gives the same result. And I verified it from a fresh clone, the way a reviewer would. On the left is Prefect, showing an 18-month run and its result tables.

## 8. What I’d do next (25 s)

If I had more time: first, make Prefect production-ready. Today it runs on my laptop; next is a Prefect server and worker in Docker, so runs don’t depend on my terminal. Second, load new months automatically as the city publishes them. Third, break revenue down by borough. The code is public on GitHub. Thank you, I’m happy to take questions.
