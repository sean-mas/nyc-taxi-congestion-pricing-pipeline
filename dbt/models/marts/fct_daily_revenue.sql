-- Revenue per pickup day. Refund rows reverse earlier charges, so they're
-- counted apart from trips: net_revenue = gross_revenue + refunds.

select
    service_date,
    count(*) filter (where not is_refund) as trip_count,
    count(*) filter (where is_refund) as refund_count,
    coalesce(sum(total_amount) filter (where not is_refund), 0) as gross_revenue,
    coalesce(sum(total_amount) filter (where is_refund), 0) as refunds,
    sum(total_amount) as net_revenue,
    -- Same rows as net_revenue (refunds included), without taxes, tolls and surcharges.
    sum(fare_revenue) as fare_revenue,
    count(*) filter (where not is_refund and cbd_congestion_fee > 0) as cbd_fee_trip_count
from {{ ref('stg_green_trips') }}
group by service_date
