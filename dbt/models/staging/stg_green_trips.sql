-- One row per trip picked up in the reporting period, with clear names and types.
-- Each rule comes from a finding in notebooks/01_explore_green_taxi.ipynb.

with source as (

    select * from {{ source('raw', 'green_trips') }}

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
    -- Negative amounts are refunds, disputes and voided trips.
    total_amount < 0 as is_refund,
    source_file
from source
-- A few trips in the files are dated outside the period (e.g. December 2024).
where lpep_pickup_datetime >= '{{ var("period_start") }}'
  and lpep_pickup_datetime < '{{ var("period_end") }}'
