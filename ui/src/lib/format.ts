const STATUS_LABELS: Record<string, string> = {
  executing: 'Em execução',
  awaiting_approval: 'Aguardando aprovação',
  awaiting_response: 'Aguardando resposta',
  idle: 'Ocioso',
  error: 'Erro',
  done: 'Concluído',
};

export function formatStatus(status: string): string {
  return STATUS_LABELS[status] ?? status;
}
