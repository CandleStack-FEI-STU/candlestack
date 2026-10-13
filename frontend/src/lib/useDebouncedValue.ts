import { useEffect, useState } from 'react';

// The value as it was `delay` ms after it last changed: typing "btc" quickly gives one update,
// not three.
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
