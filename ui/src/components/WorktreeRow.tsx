import type { Worktree } from '../lib/api';

type Props = {
  wt: Worktree;
  showRepoName: boolean;
  onRemove?: (id: string) => void;
};

export function WorktreeRow({ wt, showRepoName, onRemove }: Props) {
  const branchLabel = wt.branch ?? '(detached)';
  return (
    <div className="wt-row" title={wt.path} data-worktree-id={wt.id}>
      <span className="indent">└─</span>
      {showRepoName && <code className="repo-name">{wt.repository_name}</code>}
      {showRepoName && <span> / </span>}
      <code className="branch">{branchLabel}</code>
      {onRemove && (
        <button
          type="button"
          aria-label={`remove-worktree-${wt.id}`}
          onClick={() => onRemove(wt.id)}
        >
          ✕
        </button>
      )}
    </div>
  );
}
