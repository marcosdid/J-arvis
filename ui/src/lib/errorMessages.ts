const RULES: Array<[RegExp, string]> = [
  [/^task already has active session$/i, 'Esta task já tem sessão ativa.'],
  [/^cannot start session: task is in terminal state/i,
    'Não dá pra iniciar sessão: task em estado terminal.'],
  [/^invalid transition:/i, 'Transição não permitida.'],
  [/^title cannot be empty/i, 'Título não pode ser vazio.'],
  [/^project has \d+ task/i, 'Descarte as tasks deste projeto antes de excluí-lo.'],
];

export function translateError(message: string): string {
  for (const [pattern, pt] of RULES) {
    if (pattern.test(message)) return pt;
  }
  return message;
}
