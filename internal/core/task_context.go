package core

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/marcosdid/jarvis/internal/store"
)

// TaskContextInput collects everything needed to render the per-task context
// file that lands in <cwd>/.jarvis/CONTEXT.md. The file is read automatically
// by the Claude Code session spawned for the task — it explains the layout
// and replaces what a project-side skill (e.g. work-on-story) used to do.
type TaskContextInput struct {
	Cwd     string
	Project store.Project
	Task    store.Task
	Branch  string
	Repos   []store.Repository
}

// WriteTaskContext writes <Cwd>/.jarvis/CONTEXT.md describing the task and the
// multi-repo layout. Creates .jarvis/ if missing. Mode 0644 (no secrets).
func WriteTaskContext(in TaskContextInput) error {
	dir := filepath.Join(in.Cwd, ".jarvis")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("mkdir .jarvis: %w", err)
	}
	return os.WriteFile(filepath.Join(dir, "CONTEXT.md"), []byte(renderTaskContext(in)), 0o644)
}

func renderTaskContext(in TaskContextInput) string {
	var b strings.Builder
	b.WriteString("# J-arvs Task Context\n\n")
	b.WriteString("Este arquivo foi gerado automaticamente pelo J-arvs ao criar a worktree desta task. Use-o para entender a estrutura antes de começar.\n\n")

	b.WriteString("## Projeto\n\n")
	b.WriteString(fmt.Sprintf("- Nome: `%s`\n", in.Project.Name))
	b.WriteString(fmt.Sprintf("- Path original: `%s`\n\n", in.Project.Path))

	b.WriteString("## Task\n\n")
	b.WriteString(fmt.Sprintf("- ID: `%s`\n", in.Task.ID))
	b.WriteString(fmt.Sprintf("- Título: %s\n", in.Task.Title))
	if in.Task.Template != nil {
		b.WriteString(fmt.Sprintf("- Template: `%s`\n", *in.Task.Template))
	}
	b.WriteString(fmt.Sprintf("- Branch: `%s`\n", in.Branch))
	b.WriteString(fmt.Sprintf("- Estado: `%s`\n\n", in.Task.State))

	multi := len(in.Repos) > 1
	if multi {
		b.WriteString("## Estrutura desta worktree\n\n")
		b.WriteString("É uma worktree **multi-repo**. Você tem checkouts independentes lado-a-lado:\n\n")
	} else {
		b.WriteString("## Repositório desta worktree\n\n")
	}
	for _, r := range in.Repos {
		purpose := "checkout independente"
		if r.SubPath == "." {
			purpose = "repo principal (raiz do projeto)"
		}
		b.WriteString(fmt.Sprintf("- `%s/` — %s\n", r.Name, purpose))
	}
	b.WriteString(fmt.Sprintf("\nCada repo está na branch `%s` (criada a partir da default).\n\n", in.Branch))

	b.WriteString("## Como operar\n\n")
	if multi {
		b.WriteString("- Para mudanças num repo: `cd <repo>` (ex: `cd backend`).\n")
		b.WriteString("- Cada repo tem seu próprio `git`. **Commits são por repo**.\n")
		b.WriteString("- **NÃO faça `git add -A` da worktree-raiz** — não captura os sub-repos.\n")
		b.WriteString("- Quando finalizar mudanças num repo, commite **dentro dele**, não da raiz.\n")
	} else {
		b.WriteString("- Worktree single-repo. Comite normalmente na raiz.\n")
	}
	b.WriteString("\n")

	b.WriteString("## Encerramento\n\n")
	b.WriteString("O J-arvs observa o estado da sessão. Quando terminar, feche o terminal — o ciclo da task (Backlog → In Progress → Review → Done) é controlado pelo Kanban.\n")
	return b.String()
}
