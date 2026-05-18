# Tray icon setup + known issues

J-arvis uses [fyne.io/systray](https://github.com/fyne-io/systray) to put
an icon in your DE's status area. On Linux this uses the
`org.kde.StatusNotifierItem` D-Bus protocol (AppIndicator).

## GNOME 40+

GNOME does NOT show StatusNotifierItem icons by default. Install the
extension:

- **AppIndicator and KStatusNotifierItem Support**
  https://extensions.gnome.org/extension/615/appindicator-support/

Enable via GNOME Tweaks → Extensions, or via the browser plugin.

## KDE Plasma

Works out of the box. Icon appears in the system tray. Right-click to
see the menu.

## Sway / Wayland compositors

Most compositors with a status bar that speaks StatusNotifierItem
(Waybar, swaybar with `tray` module enabled) will show the icon. Pure
Wayland setups without a status bar daemon won't see it; J-arvis still
runs but the tray feature is invisible.

## Tested DEs

| DE | Version | Status |
|---|---|---|
| GNOME | 46 (Wayland) | OK with AppIndicator extension |
| KDE Plasma | 6.x | OK |
| Sway | 1.9 | OK with Waybar (tray module enabled) |

## Known issues

### `ssh -X` zumbi state

If you run J-arvis on a remote machine via `ssh -X`, the `$DISPLAY` env
is set but the remote D-Bus session bus may not actually carry a
StatusNotifierItem watcher. PreflightOK returns true → app enables
close-to-tray → tray icon never appears → user closes window → app
becomes invisible but keeps running.

**Workaround:** `kill <pid>` from a terminal, or use a future env flag
`JARVIS_NO_TRAY=1` (not yet implemented; track in F10.8 backlog).

### Tray icon missing in GNOME without the extension

Confirmed: app still works, just no tray. Use Alt+Tab or `jarvis --focus`
from a bound shortcut (see [hotkey-binding.md](hotkey-binding.md)) to
bring the window back.
