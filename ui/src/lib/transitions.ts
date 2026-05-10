const VALID = new Set([
  'idea→ready', 'idea→discarded',
  'ready→idea', 'ready→in_progress', 'ready→discarded',
  'in_progress→review', 'in_progress→discarded',
  'review→in_progress', 'review→done', 'review→discarded',
  'discarded→idea',
]);

export function isValidTransition(from: string, to: string): boolean {
  if (from === to) return true;
  return VALID.has(`${from}→${to}`);
}

const COLUMN_TO_STATE: Record<string, string> = {
  Backlog: 'ready',
  'In Progress': 'in_progress',
  Review: 'review',
  Done: 'done',
  Discarded: 'discarded',
};

export function resolveColumnState(column: string): string {
  const target = COLUMN_TO_STATE[column];
  if (!target) throw new Error(`unknown kanban column: ${column}`);
  return target;
}
