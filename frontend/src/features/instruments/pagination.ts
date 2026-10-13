// The last page for `total` results; an empty result still has page 1.
export function lastPage(total: number, pageSize: number): number {
  return Math.max(1, Math.ceil(total / pageSize));
}

// The page to show instead when `page` is past the end, e.g. from an old or shared link; undefined
// when it is fine or the total is unknown (the API before #109).
export function clampedPage(page: number, total: number | undefined, pageSize: number): number | undefined {
  if (total === undefined) return undefined;
  const last = lastPage(total, pageSize);
  return page > last ? last : undefined;
}
