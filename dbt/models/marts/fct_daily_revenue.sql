-- Revenue per pickup day. Refund rows reverse earlier charges, so they're
-- counted apart from trips: net_revenue = gross_revenue + refunds.

select
    service_date,
    count(*) filter (where not is_refund) as trip_count,
    count(*) filter (where is_refund) as refund_count,
    coalesce(sum(total_amount) filter (where not is_refund), 0) as gross_revenue,
    coalesce(sum(total_amount) filter (where is_refund), 0) as refunds,
    sum(total_amount) as net_revenue
from {{ ref('stg_green_trips') }}
group by service_date
