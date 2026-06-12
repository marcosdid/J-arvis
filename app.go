package main

import (
	"context"

	wruntime "github.com/wailsapp/wails/v2/pkg/runtime"
)

type App struct {
	ctx          context.Context
	serverConfig ServerConfig
}

func NewApp() *App {
	return &App{}
}

func (a *App) startup(ctx context.Context) {
	a.ctx = ctx
}

// ServerConfig is handed to the UI at boot so lib/api.ts can reach the
// local HTTP server. Temporary Wails binding — F11.2 replaces it with
// query params injected by the Electron shell.
type ServerConfig struct {
	BaseURL string `json:"base_url"`
	Token   string `json:"token"`
}

func (a *App) SetServerConfig(baseURL, token string) {
	a.serverConfig = ServerConfig{BaseURL: baseURL, Token: token}
}

func (a *App) GetServerConfig() ServerConfig { return a.serverConfig }

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
