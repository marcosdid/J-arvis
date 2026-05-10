const KEY = 'jarvis.kanban.filters';

export function loadFilters(known?: Set<string>): string[] {
  const raw = localStorage.getItem(KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const ids = parsed.filter((x): x is string => typeof x === 'string');
    return known ? ids.filter((id) => known.has(id)) : ids;
  } catch {
    return [];
  }
}

export function saveFilters(ids: string[]): void {
  localStorage.setItem(KEY, JSON.stringify(ids));
}
