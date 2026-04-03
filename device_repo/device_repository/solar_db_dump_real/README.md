# Solar equipment PostgreSQL dump

This bundle contains a ready-to-load PostgreSQL dataset built from real public equipment lists and a small vulnerability seed.

## What is included

- 28,470 real device rows
- 607,830 real spec rows
- 527 manufacturers
- 8 vulnerability records

### Device rows by category

{
  "pv_module": 16199,
  "energy_storage_system": 5926,
  "solar_inverter": 2032,
  "pcs": 1614,
  "battery_inverter": 1025,
  "battery": 879,
  "meter": 795
}

## Sources used

1. NREL / SAM CEC Modules library  
   File URL in source metadata: `CEC Modules.csv`
2. California Energy Commission Solar Equipment Lists:
   - Inverters
   - Batteries
   - Meters
   - Energy Storage Systems
   - Power Control Systems

## Important limitations

- This bundle contains **real public device data**, but it is **not** a universal global catalog of every solar product on earth.
- It does **not** yet include a bulk public optimizer or tracker catalog because I did not find a comparably large official public list for those categories during this build.
- The vulnerability table is a **starter seed**, not a complete CVE mirror. It includes several real solar/energy-related advisories so your schema and joins are ready.

## Files

- `schema.sql` – create tables
- `import.sql` – load CSV files with `psql`
- `views.sql` – convenience views
- `*.csv` – the actual loaded data

## Load instructions

From inside this folder:

```bash
createdb solar_assets
psql -d solar_assets -f schema.sql
psql -d solar_assets -f import.sql
psql -d solar_assets -f views.sql
```

Because `import.sql` uses `\copy`, run it from this folder so the relative CSV paths resolve.

## Quick checks

```sql
SELECT category_code, count(*) 
FROM vw_devices
GROUP BY category_code
ORDER BY count(*) DESC;

SELECT manufacturer_name, model_name
FROM vw_devices
WHERE manufacturer_name ILIKE 'Huawei%'
LIMIT 20;

SELECT *
FROM vw_device_vulnerabilities
ORDER BY published_date DESC, manufacturer_name, model_name;
```
