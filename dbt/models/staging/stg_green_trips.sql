-- One row per trip picked up in the reporting period, with clear names and types.
-- Each rule comes from a finding in notebooks/01_explore_green_taxi.ipynb.

with source as (

    select * from {{ source('raw', 'green_trips') }}
    -- Only the files of the chosen months (green_tripdata_YYYY-MM.parquet), so the
    -- result depends on --months alone, not on what earlier runs left in the table.
    where to_date(substring(source_file from '\d{4}-\d{2}'), 'YYYY-MM')
            >= '{{ var("period_start") }}'
      and to_date(substring(source_file from '\d{4}-\d{2}'), 'YYYY-MM')
            < '{{ var("period_end") }}'

)

select
    vendorid::integer as vendor_id,
    lpep_pickup_datetime as pickup_at,
    lpep_dropoff_datetime as dropoff_at,
    -- Revenue is counted on the day the trip started.
    lpep_pickup_datetime::date as service_date,
    -- Missing payment types are kept: their amounts are valid.
    payment_type::integer as payment_type,
    -- numeric instead of float, so sums of money are exact.
    total_amount::numeric(12, 2) as total_amount,
    -- What the driver and the taxi company keep: the metered fare, extras (rush-hour
    -- and overnight charges) and the tip. total_amount also holds taxes, tolls and
    -- surcharges that are passed on to the city, the state and the MTA. Added up from
    -- its own parts, because the parts don't always add up to total_amount.
    (
        fare_amount::numeric(12, 2)
        + extra::numeric(12, 2)
        + tip_amount::numeric(12, 2)
    ) as fare_revenue,
    -- The congestion pricing fee only exists from 5 January 2025; earlier files
    -- have no such column, so no fee means zero.
    coalesce(cbd_congestion_fee, 0)::numeric(12, 2) as cbd_congestion_fee,
    -- Negative amounts are refunds, disputes and voided trips.
    total_amount < 0 as is_refund,
    source_file
from source
-- A few trips in the files are dated outside the period (e.g. a month earlier).
-- Trips dated in a neighbouring chosen month still count, on their pickup date.
where lpep_pickup_datetime >= '{{ var("period_start") }}'
  and lpep_pickup_datetime < '{{ var("period_end") }}'
