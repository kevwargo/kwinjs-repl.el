# KWinJS REPL

KwinJS REPL is an Emacs plugin that allows interactive (albeit a little bit limited) interaction
with the actively running KWin JS scripting engine (should work on both Plasma 5 and 6,
but tested only on 6).

## Installation

1. Install [uv](https://github.com/astral-sh/uv).
2. If using [straight.el](https://github.com/radian-software/straight.el) add
`(straight-use-package '(kwinjs-repl :host github :repo "kevwargo/kwinjs-repl.el"))`
to `~/.emacs`.

## Usage

The entry function is `kwinjs`, which pops up a REPL-like buffer where you can write code
which will be executed by KWin scripting engine. The result values of your expressions are **not**
returned to REPL (not yet anyway), so to actually see some output use several available
helper functions.

**Note**: the `RET` key actually submits input only if `(point)` is immediately after a `;`
(semicolon), otherwise it just inserts a newline.

### Helper functions

- `log(msg)`: returns `msg` back to the REPL by converting it to string using `${msg}` JS syntax
- `jlog(obj)`: similar, but serializes `obj` to JSON and prettifies it
- `intro(obj)`: returns (not to REPL, but as a value in JS, so use `jlog(intro(...))` to see
the result) a basic introspection of `obj`.

### Examples

#### Simple logging

```
KWin JS #> log(typeof workspace);
object
KWin JS #> log(workspace.windowList().filter(w => w.normalWindow).map(w => `${w.resourceClass}(${w.caption})`));
brave-browser(Built-in Types — Python 3.14.4 documentation - Brave),org.kde.konsole(kev@kevwarch:~ — Konsole),Emacs(*kwinjs* - GNU Emacs at kevwarch)
```

#### JSON logging (and introspection)

```
KWin JS #> jlog(intro(workspace));
{
  "activeScreen": "object",
  "activeWindow": "object",
  "activities": "object",
  "activitiesChanged": "function",
  "activityAdded": "function",
  "activityRemoved": "function",
  "clientArea": "function",
  "constrain": "function",
  "createDesktop": "function",
  "currentActivity": "string",
  "currentActivityChanged": "function",
  "currentDesktop": "object",
  "currentDesktopChanged": "function",
  "cursorPos": "object",
  "cursorPosChanged": "function",
  "desktopGridHeight": "number",
  "desktopGridSize": "object",
  "desktopGridWidth": "number",
  "desktopLayoutChanged": "function",
  "desktops": "object",
  "desktopsChanged": "function",
  "getClient": "function",
  "hideOutline": "function",
  "isEffectActive": "function",
  "moveDesktop": "function",
  "objectName": "string",
  "objectNameChanged": "function",
  "raiseWindow": "function",
  "removeDesktop": "function",
  "rootTile": "function",
  "screenAt": "function",
  "screenOrder": "object",
  "screenOrderChanged": "function",
  "screens": "object",
  "screensChanged": "function",
  "sendClientToScreen": "function",
  "showOutline": "function",
  "slotActivateAttentionWindow": "function",
  "slotIncreaseWindowOpacity": "function",
  "slotLowerWindowOpacity": "function",
  "slotSwitchDesktopDown": "function",
  "slotSwitchDesktopLeft": "function",
  "slotSwitchDesktopNext": "function",
  "slotSwitchDesktopPrevious": "function",
  "slotSwitchDesktopRight": "function",
  "slotSwitchDesktopUp": "function",
  "slotSwitchToAboveScreen": "function",
  "slotSwitchToBelowScreen": "function",
  "slotSwitchToLeftScreen": "function",
  "slotSwitchToNextScreen": "function",
  "slotSwitchToPrevScreen": "function",
  "slotSwitchToRightScreen": "function",
  "slotSwitchWindowDown": "function",
  "slotSwitchWindowLeft": "function",
  "slotSwitchWindowRight": "function",
  "slotSwitchWindowUp": "function",
  "slotToggleShowDesktop": "function",
  "slotWindowAbove": "function",
  "slotWindowBelow": "function",
  "slotWindowClose": "function",
  "slotWindowExcludeFromCapture": "function",
  "slotWindowExpandHorizontal": "function",
  "slotWindowExpandVertical": "function",
  "slotWindowFullScreen": "function",
  "slotWindowLower": "function",
  "slotWindowMaximize": "function",
  "slotWindowMaximizeHorizontal": "function",
  "slotWindowMaximizeVertical": "function",
  "slotWindowMinimize": "function",
  "slotWindowMove": "function",
  "slotWindowMoveDown": "function",
  "slotWindowMoveLeft": "function",
  "slotWindowMoveRight": "function",
  "slotWindowMoveUp": "function",
  "slotWindowNoBorder": "function",
  "slotWindowOnAllDesktops": "function",
  "slotWindowOperations": "function",
  "slotWindowQuickTileBottom": "function",
  "slotWindowQuickTileBottomLeft": "function",
  "slotWindowQuickTileBottomRight": "function",
  "slotWindowQuickTileLeft": "function",
  "slotWindowQuickTileRight": "function",
  "slotWindowQuickTileTop": "function",
  "slotWindowQuickTileTopLeft": "function",
  "slotWindowQuickTileTopRight": "function",
  "slotWindowRaise": "function",
  "slotWindowRaiseOrLower": "function",
  "slotWindowResize": "function",
  "slotWindowShrinkHorizontal": "function",
  "slotWindowShrinkVertical": "function",
  "slotWindowToAboveScreen": "function",
  "slotWindowToBelowScreen": "function",
  "slotWindowToDesktopDown": "function",
  "slotWindowToDesktopLeft": "function",
  "slotWindowToDesktopRight": "function",
  "slotWindowToDesktopUp": "function",
  "slotWindowToLeftScreen": "function",
  "slotWindowToNextDesktop": "function",
  "slotWindowToNextScreen": "function",
  "slotWindowToPrevScreen": "function",
  "slotWindowToPreviousDesktop": "function",
  "slotWindowToRightScreen": "function",
  "stackingOrder": "object",
  "supportInformation": "function",
  "tilingForScreen": "function",
  "unconstrain": "function",
  "virtualScreenGeometry": "object",
  "virtualScreenGeometryChanged": "function",
  "virtualScreenSize": "object",
  "virtualScreenSizeChanged": "function",
  "windowActivated": "function",
  "windowAdded": "function",
  "windowAt": "function",
  "windowList": "function",
  "windowRemoved": "function",
  "workspaceHeight": "number",
  "workspaceSize": "object",
  "workspaceWidth": "number"
}
```

#### Multi-line prompts

```
KWin JS #> var scs = workspace.screens
jlog(scs)
log(scs);
[
  {
    "devicePixelRatio": 1,
    "geometry": {
      "height": 1080,
      "width": 1920,
      "x": 0,
      "y": 0
    },
    "manufacturer": "Lenovo Group Limited",
    "model": "eDP-1-0x40A9",
    "name": "eDP-1",
    "objectName": "",
    "serialNumber": ""
  }
]
KWin::LogicalOutput(0x561895a54ca0)
```
