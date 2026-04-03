import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

interface FieldConfigContextValue {
  /** Increment this to force grids to re-fetch their field configs */
  revision: number;
  bump: () => void;
}

const FieldConfigContext = createContext<FieldConfigContextValue>({
  revision: 0,
  bump: () => {},
});

export function FieldConfigProvider({ children }: { children: ReactNode }) {
  const [revision, setRevision] = useState(0);
  const bump = useCallback(() => setRevision(r => r + 1), []);
  return (
    <FieldConfigContext.Provider value={{ revision, bump }}>
      {children}
    </FieldConfigContext.Provider>
  );
}

export function useFieldConfigContext() {
  return useContext(FieldConfigContext);
}
