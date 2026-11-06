-- Every day and trip inside a compared winter must land in exactly one row of
-- fct_congestion_pricing_impact. Returns the winters where the counts differ.

with expected as (

    select
        windows.winter,
        count(*) as days,
        sum(daily.trip_count) as trips
    from {{ ref('fct_daily_revenue') }} as daily
    inner join {{ ref('congestion_pricing_windows') }} as windows
        on daily.service_date >= windows.starts_on
        and daily.service_date < windows.ends_on
    group by windows.winter

),

actual as (

    select winter, sum(days) as days, sum(trips) as trips
    from {{ ref('fct_congestion_pricing_impact') }}
    group by winter

)

select *
from expected
full outer join actual using (winter)
where expected.days is distinct from actual.days
   or expected.trips is distinct from actual.trips
