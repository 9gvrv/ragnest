/**
 * Timestamps from the API carry no timezone suffix, but they are UTC (the
 * column defaults to `now()` in a UTC database). JavaScript would read them as
 * local time and shift them by the viewer's offset, so mark them explicitly.
 */
export function parseApiDate(value: string): Date {
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}
