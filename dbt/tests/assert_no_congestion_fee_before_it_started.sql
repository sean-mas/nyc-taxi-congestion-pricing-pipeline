-- The congestion pricing fee started on 5 January 2025. A fee on an earlier trip
-- would mean the data, or the start date in congestion_pricing_windows, is wrong.

select pickup_at, cbd_congestion_fee
from {{ ref('stg_green_trips') }}
where cbd_congestion_fee <> 0
  and service_date < (
      select min(splits_on)
      from {{ ref('congestion_pricing_windows') }}
      where has_congestion_pricing
  )
