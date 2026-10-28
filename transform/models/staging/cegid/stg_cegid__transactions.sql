-- Staging: rename, cast, deduplicate. No business logic.
-- Reads the BigLake table with an explicit `dt` filter (partition filter is
-- required, see infra/biglake.tf).

with source as (

    select
        transaction_id,
        store_id,
        brand_id,
        transaction_date,
        product_id,
        category_id,
        quantity,
        unit_price,
        total_price,
        payment_type,
        dt
    from {{ source('cegid', 'transactions') }}
    where dt >= date('{{ var("raw_start_date") }}')

),

typed as (

    select
        transaction_id,
        store_id,
        brand_id,
        safe_cast(transaction_date as timestamp) as transaction_at,
        date(safe_cast(transaction_date as timestamp)) as transaction_date,
        product_id,
        nullif(trim(category_id), '') as category_id,
        safe_cast(quantity as int64) as quantity,
        safe_cast(unit_price as numeric) as unit_price,
        safe_cast(total_price as numeric) as total_price,
        coalesce(nullif(trim(payment_type), ''), 'unknown') as payment_type,
        dt as loaded_dt
    from source

),

deduplicated as (

    select
        transaction_id,
        store_id,
        brand_id,
        transaction_at,
        transaction_date,
        product_id,
        category_id,
        quantity,
        unit_price,
        total_price,
        payment_type,
        loaded_dt
    from typed
    -- a re-run rewrites its own dt, a later load wins over an earlier one
    qualify row_number() over (partition by transaction_id order by loaded_dt desc) = 1

)

select
    transaction_id,
    store_id,
    brand_id,
    transaction_at,
    transaction_date,
    product_id,
    category_id,
    quantity,
    unit_price,
    total_price,
    payment_type,
    loaded_dt
from deduplicated
