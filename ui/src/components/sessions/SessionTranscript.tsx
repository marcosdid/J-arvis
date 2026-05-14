import { useTranscript } from '@/hooks/useTranscript';

export function SessionTranscript({ sessionId }: { sessionId: string }) {
  const { data: messages = [], isLoading } = useTranscript(sessionId);
  if (isLoading) {
    return <div className="text-xs text-zinc-500">Carregando transcript…</div>;
  }
  if (messages.length === 0) {
    return <div className="text-xs text-zinc-500">Sem transcript ainda.</div>;
  }
  return (
    <div className="space-y-2" data-testid="session-transcript">
      {messages.map((m) => (
        <div key={`${m.source_file}:${m.timestamp}`} className="text-xs">
          <span className="font-mono text-zinc-400">{m.role}</span>{' '}
          {m.tool_name && <span className="text-blue-400">[{m.tool_name}]</span>}{' '}
          <span>{m.content}</span>
        </div>
      ))}
    </div>
  );
}
