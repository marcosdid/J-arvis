import type { ServiceStatus } from '../lib/api';

const ICON: Record<ServiceStatus['state'], string> = {
  pending: '·',
  building: '◐',
  seeding: '◑',
  ready: '●',
  failed: '✗',
  stopping: '◯',
  stopped: '○',
};

type Props = { service: ServiceStatus };

export function ServiceStatusBadge({ service }: Props) {
  return (
    <span
      className={`service-badge service-badge-${service.state}`}
      data-service-name={service.name}
      data-service-state={service.state}
      title={service.error ?? ''}
    >
      {ICON[service.state]} {service.name}
    </span>
  );
}
