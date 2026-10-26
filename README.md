# smi2ass

**smi2ass** converts SAMI subtitle files (`.smi`) to SubStation Alpha (`.ass`).
This fork provides a drag-and-drop desktop app for macOS and Windows, as well
as a command-line interface.

## Features

- Convert dropped subtitle files or folders immediately. Folders are searched
  recursively.
- Show the desktop interface in Korean or English based on the device language.
- Follow the system light or dark appearance automatically.
- When adding a folder, search its subfolders recursively. The desktop app
  accepts `.smi` extensions without regard to letter case, including `.SMI`
  and `.SmI`.
- Write each `.ass` beside its source `.smi`; source files are left in place.
- Convert SAMI files containing multiple languages into separate language
  outputs, such as `episode.eng.ass` and `episode.kor.ass`.
- In the desktop app, preserve existing `.ass` files by default. Missing
  language outputs are still created when only some outputs already exist.
  Enable **기존 ASS 파일 덮어쓰기** to replace existing outputs.
- Repair recognized SAMI markup and timestamp damage, and show repairs, skipped
  cues, existing outputs, and file errors in the app or CLI.

## Download

Run a build from the repository's
[GitHub Actions](https://github.com/AHRI2nd/smi2assF/actions) page. The
**CI checks** workflow runs tests and Windows package lifecycle checks on pushes
to `master` and pull requests. To
build release files, open **Build release draft**, select **Run workflow**, and
enter a release tag such as `v1.2.0`. The workflow builds Apple Silicon macOS
and separate native Windows x86-64 and ARM64 versions from `master`, then
creates a draft release. Intel Mac builds are not provided.

Select **verify_only** to run the same package builds and smoke tests without
creating a release draft. Windows builds verify installation, the installed app,
and uninstallation. Installer diagnostic logs are saved as a separate artifact
on both successful and failed runs.

| Artifact | Build |
| --- | --- |
| `smi2assF.osx-arm64.dmg` | macOS disk image containing `smi2assF.app` |
| `smi2assF.windows-x86_64.exe` | Native Windows x86-64 installer |
| `smi2assF.windows-arm64.exe` | Native Windows ARM64 installer |
| `*.sha256` | SHA-256 checksums for the release files |

Actions artifacts are uploaded as individual files without ZIP packaging.
Download the file for your operating system and processor architecture. The
draft release also contains all three installers and their checksums as direct
downloads.
Review the draft and publish it from the
[Releases page](https://github.com/AHRI2nd/smi2assF/releases) when it is ready.

## Use the desktop app

1. Open `smi2assF.app` on macOS. On Windows, run the matching
   `smi2assF.windows-x86_64.exe` or `smi2assF.windows-arm64.exe` installer,
   then launch `smi2assF`
   from the Start menu. The x86-64 and ARM64 installers use separate folders
   under `%LOCALAPPDATA%\Programs` and each adds its own uninstaller.
2. Drag `.smi` or `.SMI` files or folders into the drop area. Conversion starts
   immediately, and results are written beside each source file.
3. Turn on **기존 ASS 파일 덮어쓰기** at the bottom only when existing outputs
   should be replaced. The desktop interface follows the device language and
   uses Korean or English.

Folders are searched recursively. Other extensions, such as `.sub` or `.srt`,
are not added by the desktop app. When a source
contains multiple languages, the app checks each language output separately:
existing files are preserved by default while missing language outputs are
created.

## Command-line use

Python 3.14 is required. Install the runtime dependencies, then pass one or
more input paths to the converter:

```sh
python3.14 -m pip install -r requirements.txt
python3.14 smi2ass.py episode.smi
python3.14 smi2ass.py episode-one.smi episode-two.smi
```

The CLI writes outputs beside the input files. Single-language output uses
`.kor.ass` by default; multilanguage input produces one file per detected
language. The CLI overwrites existing outputs. It accepts the paths you
provide directly; extension filtering and recursive folder discovery are
desktop-app features.

## Recovery and diagnostics

The converter repairs recognized, unambiguous damage, including:

- A missing `</SYNC>` before the next `SYNC` cue.
- A closing `SYNC` tag without a matching open tag.
- Unclosed supported formatting tags within a cue.
- Recognized punctuation after an integer timestamp, for example
  `Start=479501??`.

Cues with missing, negative, or ambiguous timestamps are skipped while other
cues and input files continue. Unsupported font colors are reported and left
unapplied. The desktop app keeps its existing on-screen summary and writes
skipped-cue reasons, failed conversions, file and folder scan errors, and
unexpected worker exceptions to its rotating log. The CLI prints diagnostics
and returns a nonzero status if a cue was skipped or a file could not be
processed. SMI states shorter than ASS's 10 ms timestamp precision are
collapsed to the following state at that centisecond and shown as warnings;
they do not fail an otherwise successful conversion.

The app log is limited to 1 MiB per file and keeps three rotated backups:

- macOS: `~/Library/Logs/smi2assF/app.log`
- Windows: `%LOCALAPPDATA%\smi2assF\Logs\app.log`
- Linux: `${XDG_STATE_HOME:-~/.local/state}/smi2assF/app.log`

Supported subtitle markup includes `<p>`, `<br>`, `<b>`, `<i>`, `<u>`, `<s>`,
`<font>`, and `<rt>` (Ruby tags).

## Development

Use Python 3.14 on macOS and Windows. The Windows release workflow pins Python
3.14.8. A Python build with Tk support is needed to run the desktop interface.
Install development dependencies, run the tests, and launch the GUI:

```sh
python3.14 -m pip install -r requirements-dev.txt
python3.14 -m pytest -q
python3.14 smi2ass_gui.py
```

To package the app locally, use Python 3.14 with Tk support on macOS or Windows:

```sh
PYTHON=python3.14 bash install.sh
bash build.sh
```

On Windows, use `PYTHON=python` with Python 3.14 selected in `PATH`.

The build scripts support Apple Silicon macOS, Windows x86-64, and Windows
ARM64. The manual release workflow builds all three packages from `master`, runs
the test suite, smoke-tests each app, and creates a draft release with SHA-256
checksums.
Enable **verify_only** when validating packaging changes without creating a draft.

## Project lineage and credits

This repository continues work from two earlier projects:

1. The original SAMI conversion implementation was derived from the
   [`service.subtitles.gomtv` Kodi add-on](https://github.com/hojel/service.subtitles.gomtv/tree/3a7342961e140eaf8250659b0ac6158ce5e6bc5c/resources/lib).
   The converter's source header identifies this upstream snapshot and commit.
2. [Trustin Lee's `smi2ass`](https://github.com/trustin/smi2ass) adapted that
   converter into a standalone project. Its README credits Trustin Lee with
   Ruby tag support, improved whitespace preservation, executable packaging,
   the Python 2 to Python 3 and BeautifulSoup 3 to BeautifulSoup 4 updates, and
   cleanup. The converter source retains its 2018 copyright notice for Trustin
   Heuiseung Lee and other contributors.

Additional contributions recorded in this repository include:

- [goodGhost](https://github.com/good-ghost): Python 3.7 compatibility and a
  BeautifulSoup compatibility fix.
- Tsukimori Ahri, current fork maintainer: Python 3.14 modernization, SAMI
  recovery and diagnostics, the desktop interface, recursive folder handling,
  and macOS/Windows GitHub Actions packaging.

The source code is licensed under the GNU General Public License, version 2 or
any later version, as stated in the source notices. See [LICENSE.txt](LICENSE.txt)
for the license text. Please retain the existing copyright and license notices
when redistributing the source.
