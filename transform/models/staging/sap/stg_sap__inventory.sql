-- Staging: rename, cast, deduplicate. No business logic.

with source as (

    select
        inventory_id,
        product_id,
        brand_id,
        category_id,
        store_id,
        quantity_on_hand,
        quantity_reserved,
        reorder_point,
        unit_cost,
        snapshot_date,
        dt
    from {{ source('sap', 'inventory') }}
    where dt >= date('{{ var("raw_start_date") }}')

),

typed as (

    select
        inventory_id,
        product_id,
        brand_id,
        category_id,
        store_id,
        safe_cast(quantity_on_hand as int64) as quantity_on_hand,
        safe_cast(quantity_reserved as int64) as quantity_reserved,
        safe_cast(reorder_point as int64) as reorder_point,
        safe_cast(unit_cost as numeric) as unit_cost,
        safe_cast(snapshot_date as date) as snapshot_date,
        dt as loaded_dt
    from source

),

deduplicated as (

    select
        inventory_id,
        product_id,
        brand_id,
        category_id,
        store_id,
        quantity_on_hand,
        quantity_reserved,
        reorder_point,
        unit_cost,
        snapshot_date,
        loaded_dt
    from typed
    qualify row_number() over (partition by inventory_id order by loaded_dt desc) = 1

)

select
    inventory_id,
    product_id,
    brand_id,
    category_id,
    store_id,
    quantity_on_hand,
    quantity_reserved,
    reorder_point,
    unit_cost,
    snapshot_date,
    loaded_dt
from deduplicated
