import type { ReactNode } from 'react';

import { AppHeader } from '@/components/header/AppHeader';
import { HudTopBar } from '@/components/hud/HudTopBar';
import { ErrorBanner } from '@/components/status/ErrorBanner';
import { StatusBar } from '@/components/status/StatusBar';

type Props = {
  projectsCount: number;
  tasksCount: number;
  activeCount: number;
  wsRtt: number | null;
  onFilter?: () => void;
  onToggleProjects?: () => void;
  onNewTask?: () => void;
  children: ReactNode;
};

export function AppShell({
  projectsCount,
  tasksCount,
  activeCount,
  wsRtt,
  onFilter,
  onToggleProjects,
  onNewTask,
  children,
}: Props) {
  return (
    <div className="flex flex-col flex-1 min-w-0 h-screen overflow-hidden">
      <HudTopBar wsRtt={wsRtt} />
      <ErrorBanner />
      <AppHeader
        projectsCount={projectsCount}
        tasksCount={tasksCount}
        activeCount={activeCount}
        {...(onFilter !== undefined && { onFilter })}
        {...(onToggleProjects !== undefined && { onToggleProjects })}
        {...(onNewTask !== undefined && { onNewTask })}
      />
      <main className="flex flex-col flex-1 min-h-0 overflow-hidden">{children}</main>
      <StatusBar />
    </div>
  );
}
