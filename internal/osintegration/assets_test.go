package osintegration

import "testing"

func TestTrayIconPNG_Embedded(t *testing.T) {
	if len(TrayIconPNG) < 100 {
		t.Fatalf("tray icon seems empty or truncated: %d bytes", len(TrayIconPNG))
	}
	// PNG magic bytes: 89 50 4E 47
	if TrayIconPNG[0] != 0x89 || TrayIconPNG[1] != 'P' || TrayIconPNG[2] != 'N' || TrayIconPNG[3] != 'G' {
		t.Errorf("not a PNG: first 4 bytes = % x", TrayIconPNG[:4])
	}
}
