package main

import (
	"embed"

	"github.com/marcosdid/jarvis/internal/api"
	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

//go:embed all:ui/dist
var assets embed.FS

func main() {
	app := NewApp()
	health := api.NewHealthAPI()

	err := wails.Run(&options.App{
		Title:  "J-arvis",
		Width:  1400,
		Height: 900,
		AssetServer: &assetserver.Options{
			Assets: assets,
		},
		BackgroundColour: &options.RGBA{R: 3, G: 5, B: 3, A: 1},
		OnStartup:        app.startup,
		Bind: []any{
			app,
			health,
		},
	})

	if err != nil {
		println("Error:", err.Error())
	}
}
