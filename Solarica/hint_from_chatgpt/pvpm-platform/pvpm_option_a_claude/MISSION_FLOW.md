# Mission Execution Flow

## Create mission
- Choose site
- Enter mission name
- Add ordered strings

Example:
- S1
- S2
- S3

## Execution screen
Display:
- mission name
- site
- current item
- progress
- checklist
- notes
- measure button

## Recommended checklist
- Inverter/DC safely isolated according to field procedure
- Correct string connected
- Irradiance/temp sensors connected if required
- Operator PPE confirmed

## Measure sequence
1. Operator presses Confirm Ready
2. Operator presses Measure
3. App calls backend
4. Backend calls device adapter
5. Raw + parsed result saved
6. Item marked completed
7. Next item shown

## Failure flow
- Do not auto-complete item
- Show error
- Allow Retry or Skip

## Skip flow
- Require reason
- Mark item skipped
- Move to next item
