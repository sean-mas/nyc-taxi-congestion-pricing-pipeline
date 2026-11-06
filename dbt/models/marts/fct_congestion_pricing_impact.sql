-- Did congestion pricing (from 5 January 2025) change Green Taxi trips and revenue?
--
-- Each winter is split on 5 January into before and after. A plain before/after
-- comparison would mix the fee with the normal winter dip, so the winter a year
-- earlier, without the fee, is split on the same date: the fee's effect is the
-- difference between the two winters' changes, not the raw drop.
--
-- Weekdays and weekends are compared apart, because they have different trip
-- patterns and the periods don't hold the same mix of them.

with windows as (

    select * from {{ ref('congestion_pricing_windows') }}

),

days as (

    select
        windows.winter,
        windows.has_congestion_pricing,
        windows.splits_on,
        case
            when extract(isodow from daily.service_date) <= 5 then 'weekday'
            else 'weekend'
        end as day_type,
        case
            when daily.service_date < windows.splits_on then 'before'
            else 'after'
        end as period,
        daily.service_date,
        daily.trip_count,
        daily.net_revenue,
        daily.fare_revenue,
        daily.cbd_fee_trip_count
    from {{ ref('fct_daily_revenue') }} as daily
    -- Days outside both winters (April to September) aren't compared.
    inner join windows
        on daily.service_date >= windows.starts_on
        and daily.service_date < windows.ends_on

)

select
    winter,
    has_congestion_pricing,
    splits_on,
    day_type,
    period,
    min(service_date) as first_day,
    max(service_date) as last_day,
    count(*) as days,
    sum(trip_count) as trips,
    round(sum(trip_count) / count(*), 1) as trips_per_day,
    round(sum(net_revenue) / count(*), 2) as net_revenue_per_day,
    round(sum(fare_revenue) / count(*), 2) as fare_revenue_per_day,
    round(sum(net_revenue) / nullif(sum(trip_count), 0), 2) as net_revenue_per_trip,
    round(sum(fare_revenue) / nullif(sum(trip_count), 0), 2) as fare_revenue_per_trip,
    round(sum(cbd_fee_trip_count) / nullif(sum(trip_count), 0), 4) as cbd_fee_trip_share
from days
group by winter, has_congestion_pricing, splits_on, day_type, period
