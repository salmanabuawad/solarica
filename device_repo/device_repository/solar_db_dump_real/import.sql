
\set ON_ERROR_STOP on

BEGIN;

\copy data_sources FROM 'sources.csv' CSV HEADER;
\copy asset_categories FROM 'asset_categories.csv' CSV HEADER;
\copy manufacturers FROM 'manufacturers.csv' CSV HEADER;
\copy device_models FROM 'device_models.csv' CSV HEADER;
\copy device_specs FROM 'device_specs.csv' CSV HEADER;
\copy vulnerabilities FROM 'vulnerabilities.csv' CSV HEADER;
\copy vulnerability_matches FROM 'vulnerability_matches.csv' CSV HEADER;

COMMIT;
