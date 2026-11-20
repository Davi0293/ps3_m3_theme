# PS3 M3 Expressive themes

Four `.p3t` themes (Purple, Blue, Green, Coral) in a Material 3 Expressive / Pixel style,
built by GitHub Actions.

## Get the themes
1. Push this folder to a GitHub repo (branch `main`).
2. Open the **Actions** tab, run **Build PS3 themes** (or just push).
3. Download the `ps3-m3-expressive-themes` artifact: it holds `M3_Expressive_*.p3t`.
4. Copy the `.p3t` files to a USB stick and install them from Settings > Theme Settings > Install Themes
   (on the PS3, or through webMAN's file manager).

## How it works
`build_theme.py` writes the same p3tcompiler input XML that
[theme-studio](https://github.com/mohasi/ps3-dev/tree/main/tools/theme-studio) writes,
then runs Sony's `p3tcompiler.exe`. The workflow fetches that exe from `mohasi/ps3-dev`
at build time, so no Sony binaries live in this repo. It needs Windows, hence `windows-latest`.

Locally on Windows: `python build_theme.py --tools <path to theme-studio\tools>`.
On any OS, `python build_theme.py --dry-run` validates sizes and writes the XML without compiling.

## Layout of a theme folder (`themes/<name>/`)
| File | Spec |
|---|---|
| `bg_hd.jpg` | 1920x1080 JPEG |
| `bg_sd.jpg` | 640x480 JPEG (4:3) |
| `icon.png` | 64x64 PNG with alpha |
| `preview.png` | 480x270 PNG |
| `icons/icon_*.png` | 128x128 PNG, named after the XMB slot (`icon_game.png`, ...) |
| `theme.json` | name, author, genre, version, comment, font, color |

Only the nine main-row icons are themed (user, setting, photo, music, video, game, network,
friend, tv). Other slots keep the stock Sony icons.

## Not verified
The compiler step has not been run: it needs Windows, and this was prepared on Linux.
The XML layout was checked against theme-studio's `ThemeBuild.cs` and sizes are validated, but the first
Actions run is the real test. If it fails, the log shows p3tcompiler's own message.
