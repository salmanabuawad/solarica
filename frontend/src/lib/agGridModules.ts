import {
  CellStyleModule,
  ClientSideRowModelModule,
  DateFilterModule,
  InfiniteRowModelModule,
  ModuleRegistry,
  NumberEditorModule,
  NumberFilterModule,
  PaginationModule,
  RenderApiModule,
  RowDragModule,
  RowSelectionModule,
  RowStyleModule,
  TextFilterModule,
  ValidationModule,
} from 'ag-grid-community';

let registered = false;

export function registerAgGridModules() {
  if (registered) return;

  ModuleRegistry.registerModules([
    ClientSideRowModelModule,
    InfiniteRowModelModule,
    PaginationModule,
    TextFilterModule,
    NumberFilterModule,
    DateFilterModule,
    RowSelectionModule,
    CellStyleModule,
    RowStyleModule,
    RenderApiModule,
    RowDragModule,
    NumberEditorModule,
    ...(import.meta.env.DEV ? [ValidationModule] : []),
  ]);

  registered = true;
}
