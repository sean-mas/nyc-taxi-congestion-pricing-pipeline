-- The daily table must account for every staged trip and every cent.
-- Returns a row (and fails) if anything was lost or counted twice.

with staged as (

    select
        count(*) as staged_rows,
        sum(total_amount) as staged_amount,
        sum(fare_revenue) as staged_fare_revenue
    from {{ ref('stg_green_trips') }}

),

daily as (

    select
        sum(trip_count + refund_count) as daily_rows,
        sum(net_revenue) as daily_amount,
        sum(fare_revenue) as daily_fare_revenue
    from {{ ref('fct_daily_revenue') }}

)

select *
from staged
cross join daily
where staged_rows <> daily_rows
   or staged_amount <> daily_amount
   or staged_fare_revenue <> daily_fare_revenue
