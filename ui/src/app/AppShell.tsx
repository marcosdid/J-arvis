import type { ReactNode } from 'react';

import { AppHeader } from '@/components/header/AppHeader';
import { HudTopBar } from '@/components/hud/HudTopBar';
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
    <div className="grid grid-rows-[auto_auto_1fr_auto] h-screen overflow-hidden">
      <HudTopBar wsRtt={wsRtt} />
      <AppHeader
        projectsCount={projectsCount}
        tasksCount={tasksCount}
        activeCount={activeCount}
        {...(onFilter !== undefined && { onFilter })}
        {...(onToggleProjects !== undefined && { onToggleProjects })}
        {...(onNewTask !== undefined && { onNewTask })}
      />
      <main className="overflow-auto">{children}</main>
      <StatusBar />
    </div>
  );
}
