import { useMutation, useQueryClient } from '@tanstack/react-query';

import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useSessions } from '@/hooks/useSessions';
import { api } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';

import { SessionHistoryItem } from './SessionHistoryItem';
import { SessionStatusChip } from './SessionStatusChip';
import { SessionTranscript } from './SessionTranscript';

export function SessionPanel({
  taskId,
  open,
  onOpenChange,
}: {
  taskId: string | null;
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const { data: sessions = [] } = useSessions(taskId);
  const queryClient = useQueryClient();
  const stopMut = useMutation({
    mutationFn: (sid: string) => api.stopSession(sid),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.sessionsForTask(taskId) }),
  });

  const active = sessions.filter((s) => s.ended_at == null);
  const history = sessions.filter((s) => s.ended_at != null);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[480px]">
        <SheetHeader>
          <SheetTitle>Sessões</SheetTitle>
        </SheetHeader>

        {active.map((s) => (
          <div key={s.id} className="border rounded p-3 mt-3">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs">sid:{s.id.slice(0, 6)}</span>
              <SessionStatusChip session={s} />
            </div>
            <button
              onClick={() => stopMut.mutate(s.id)}
              className="text-xs underline mt-2"
            >
              Stop
            </button>
            <div className="text-xs text-zinc-500 mt-2">
              Abra seu terminal pra interagir com o claude.
            </div>
            <div className="mt-3">
              <SessionTranscript sessionId={s.id} />
            </div>
          </div>
        ))}

        {history.length > 0 && (
          <div className="mt-4">
            <h4 className="text-xs font-semibold">Histórico</h4>
            {history.map((s) => (
              <SessionHistoryItem key={s.id} session={s} />
            ))}
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
