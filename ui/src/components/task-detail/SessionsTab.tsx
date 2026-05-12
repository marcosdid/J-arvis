type Props = { taskId: string };

export function SessionsTab({ taskId }: Props) {
  // Full implementation deferred to Phase 10 (master session integration).
  return (
    <div className="p-4 text-text-subtle text-sm">
      <p>Sessions list coming with master session integration.</p>
      <p className="text-text-faint text-xs mt-2">Task ID: {taskId}</p>
    </div>
  );
}
