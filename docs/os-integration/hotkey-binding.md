# Binding Super+J → `jarvis --focus`

J-arvis doesn't capture global hotkeys directly — Linux has no portable
in-process API, especially on Wayland. Instead, you bind your DE's
shortcut system to call `jarvis --focus`, which sends a D-Bus message to
the already-running instance (via Wails `SingleInstanceLock`) and that
instance focuses its window.

`--focus` is a documented intent flag. Today the running instance focuses
on ANY second invocation; the flag exists so future versions can
distinguish "focus only" vs "focus and navigate to task X".

## GNOME (Ubuntu, Fedora, Pop!_OS)

Settings → Keyboard → View and Customize Shortcuts → Custom Shortcuts →
"+":

- **Name:** Focus J-arvis
- **Command:** `/usr/local/bin/jarvis --focus` (or wherever your binary is)
- **Shortcut:** Press the keys you want — typically `Super+J`

## KDE Plasma

System Settings → Shortcuts → Custom Shortcuts → Edit → New → Global
Shortcut → Command/URL:

- **Trigger:** `Super+J`
- **Action:** Command: `jarvis --focus`

## Sway / i3

Add to `~/.config/sway/config` (or `~/.config/i3/config`):

```
bindsym $mod+j exec jarvis --focus
```

Then reload (`Mod+Shift+c` in Sway, `Mod+Shift+r` in i3).

## Verifying the binding works

1. Open J-arvis and minimize it (or close to tray — see [tray-setup.md](tray-setup.md)).
2. Press `Super+J`.
3. The window should pop to the front.

If nothing happens, check:
- `which jarvis` returns the binary path your shortcut points to.
- `jarvis --focus` from a terminal works while another instance is running.
- The D-Bus session bus is reachable (`echo $DBUS_SESSION_BUS_ADDRESS`).
