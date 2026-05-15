import { Skeleton } from '@/components/ui/skeleton';

export function TaskCardSkeleton() {
  return (
    <div className="bg-bg-elevated border border-border-subtle rounded-sm p-2 flex flex-col gap-2">
      <Skeleton className="h-3 w-1/3 bg-bg-deep" />
      <Skeleton className="h-4 w-full bg-bg-deep" />
      <div className="flex gap-1">
        <Skeleton className="h-3 w-12 bg-bg-deep" />
        <Skeleton className="h-3 w-16 bg-bg-deep" />
      </div>
    </div>
  );
}
