/**
 * Branch slug derivation from task titles.
 *
 * MUST stay in 1:1 sync with `orchestrator/core/slug.py::slugify_for_branch`.
 * Any divergence will cause server-side validation to disagree with the slug
 * preview shown in NewTaskForm placeholder.
 *
 * Rules: lowercase, replace non-[a-z0-9] runs with single hyphen, strip
 * leading/trailing hyphens, truncate at 60 chars. Throws
 * InvalidBranchSlugError if the result is empty.
 */
export class InvalidBranchSlugError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'InvalidBranchSlugError';
  }
}

export function slugifyForBranch(text: string): string {
  let s = text.toLowerCase().trim();
  s = s.replace(/[^a-z0-9]+/g, '-');
  s = s.replace(/-+/g, '-').replace(/^-+|-+$/g, '');
  if (!s) {
    throw new InvalidBranchSlugError(`cannot slugify '${text}' to a valid branch name`);
  }
  return s.slice(0, 60).replace(/-+$/g, '');
}
