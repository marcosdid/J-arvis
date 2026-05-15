type Props = { taskId: string };

export function LogsTab({ taskId }: Props) {
  return (
    <div className="p-4 text-text-subtle text-sm">
      <p>Run logs streaming coming soon.</p>
      <p className="text-text-faint text-xs mt-2">Task ID: {taskId}</p>
    </div>
  );
}
