package main

import (
	"context"

	wruntime "github.com/wailsapp/wails/v2/pkg/runtime"
)

type App struct {
	ctx context.Context
}

func NewApp() *App {
	return &App{}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
}

// ChooseDirectory opens the native folder picker rooted at the user's HOME and
// returns the absolute path of the selected directory. Empty string means the
// user cancelled the dialog (Wails surfaces cancellation as ("", nil), which
// the frontend should treat as a no-op rather than an error).
func (a *App) ChooseDirectory() (string, error) {
	if a.ctx == nil {
		return "", nil
	}
	return wruntime.OpenDirectoryDialog(a.ctx, wruntime.OpenDialogOptions{
		Title: "Selecione a pasta do projeto",
	})
}
