-- No day outside the reporting period may reach the daily table.

select service_date
from {{ ref('fct_daily_revenue') }}
where service_date < '{{ var("period_start") }}'
   or service_date >= '{{ var("period_end") }}'
