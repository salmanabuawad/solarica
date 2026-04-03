import { useState, useEffect } from 'react';
import type { ColDef } from 'ag-grid-community';
import { getFieldConfigs, type FieldConfigItem } from './api';
import { useFieldConfigContext } from './FieldConfigContext';

/**
 * Loads field configurations for a grid and merges them into the provided
 * column definitions. Returns the merged defs (ready to pass to AG Grid).
 *
 * Columns NOT present in the DB config are shown with their default visibility.
 * The hook re-runs whenever the global revision counter is bumped (after admin saves).
 */
export function useFieldConfig(gridName: string, defaultCols: ColDef[]): ColDef[] {
  const { revision } = useFieldConfigContext();
  const [configs, setConfigs] = useState<FieldConfigItem[]>([]);

  useEffect(() => {
    getFieldConfigs(gridName).then(setConfigs).catch(() => {});
  }, [gridName, revision]);

  if (configs.length === 0) return defaultCols;

  const configMap = new Map<string, FieldConfigItem>(
    configs.map(c => [c.field_name, c]),
  );

  // Build ordered list: configured cols first (by column_order), then any
  // remaining defaultCols that have no config entry yet.
  const configured = configs
    .slice()
    .sort((a, b) => (a.column_order ?? 999) - (b.column_order ?? 999));

  const configuredNames = new Set(configs.map(c => c.field_name));
  const unconfigured = defaultCols.filter(c => c.field != null && !configuredNames.has(c.field as string));

  const orderedFields = [
    ...configured.map(c => c.field_name),
    ...unconfigured.map(c => c.field as string),
  ];

  return orderedFields
    .map(fieldName => {
      const base = defaultCols.find(c => c.field === fieldName);
      if (!base) return null;
      const cfg = configMap.get(fieldName);
      if (!cfg) return base;
      return {
        ...base,
        hide:  !cfg.visible,
        width: cfg.width ?? base.width,
      };
    })
    .filter(Boolean) as ColDef[];
}
