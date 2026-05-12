import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { queryKeys } from '../../lib/query-keys';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '../ui/sheet';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { OverviewTab } from './OverviewTab';
import { SessionsTab } from './SessionsTab';
import { RunTab } from './RunTab';
import { LogsTab } from './LogsTab';

type Props = { taskId: string | null; onClose: () => void };

export function TaskDetailSheet({ taskId, onClose }: Props) {
  const open = taskId !== null;
  const task = useQuery({
    queryKey: taskId ? queryKeys.task(taskId) : ['task', '__pending__'],
    queryFn: () => api.getTask(taskId!),
    enabled: open,
  });

  return (
    <Sheet open={open} onOpenChange={(o) => { if (!o) onClose(); }}>
      <SheetContent
        side="right"
        className="w-[480px] sm:max-w-[480px] bg-bg-surface border-l border-border-subtle overflow-y-auto"
      >
        <SheetHeader>
          <SheetTitle className="font-display text-text-emphasis">
            {task.data?.title ?? 'Loading...'}
          </SheetTitle>
        </SheetHeader>
        {taskId && task.data && (
          <Tabs defaultValue="overview" className="mt-4">
            <TabsList className="grid grid-cols-4 w-full">
              <TabsTrigger value="overview">overview</TabsTrigger>
              <TabsTrigger value="sessions">sessions</TabsTrigger>
              <TabsTrigger value="run">run</TabsTrigger>
              <TabsTrigger value="logs">logs</TabsTrigger>
            </TabsList>
            <TabsContent value="overview">
              <OverviewTab task={task.data} />
            </TabsContent>
            <TabsContent value="sessions">
              <SessionsTab taskId={taskId} />
            </TabsContent>
            <TabsContent value="run">
              <RunTab taskId={taskId} />
            </TabsContent>
            <TabsContent value="logs">
              <LogsTab taskId={taskId} />
            </TabsContent>
          </Tabs>
        )}
      </SheetContent>
    </Sheet>
  );
}
