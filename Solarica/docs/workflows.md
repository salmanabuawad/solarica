# Workflows

## A) Design review workflow

1. Project manager uploads design set
2. Parser extracts entities (sections, inverters, strings, declared counts)
3. Validation run starts
4. Issues appear as blocker/error/warning/info
5. Project manager resolves or requests exceptions
6. Approved design moves to `approved_for_construction`

## B) Construction progress workflow

1. PM creates work packages by section/inverter/string group
2. Inventory keeper issues materials against package
3. Supervisor updates field completion from mobile/web
4. Daily report updates actual quantities, blockers, photos, ETA
5. System recalculates planned vs actual and completion forecast

## C) Testing & commissioning workflow

1. String / inverter marked ready for QA
2. Continuity + polarity recorded
3. Megger / insulation recorded
4. IV curve uploaded or measured
5. Failures create punch list items
6. Passing all required tests unlocks energization gate

## D) O&M workflow

1. Operational project gets maintenance plan
2. Periodic retest schedules created
3. Incidents and support visits logged
4. Historical performance and recurring faults tracked
