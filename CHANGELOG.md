# Changelog

🇬🇧 **English** · 🇮🇹 [Italiano](CHANGELOG.it.md)

## 1.0.0

First public release. Compared with the version presented for the Software Engineering course (December 2023):

### Interface
- New interface with a sidebar, parameter cards, graph statistics and dark and light themes (☀/☾ button at the
  top, next to the title).
- GitHub token entered in the app and never saved to disk: one-click verification, the real remaining quota
  read from GitHub's headers and the reset time.
- **Git** card showing whether Git is installed, with a download link and a "Check again" button.
- Background download with progress in the status bar and a **Cancel download** button.
- Multilingual interface (Italian and English): the language follows Windows and a selector changes it on the
  fly; each language is a JSON file in `src/locales`, so adding one needs no code.

### Data
- Only the chosen interval is downloaded ("From"–"To", by default the last 3 months), without the old fixed
  minimum date; widening the interval downloads again only when needed.
- Explicit saving and loading of the data in `.graphapp` files (instead of the automatic cache), read safely;
  after loading, the calendar is limited to the period available in the file.
- Parallel requests on 8 threads, with handling of GitHub's limits (primary and secondary) and retries on
  network errors.
- Lower quota usage: commits read from a partial local git clone (e.g. `apache/commons-io`, 3 months:
  1 request instead of 107), issue and PR comments downloaded in bulk.

### Graphs and export
- Smooth large graphs: lighter drawing above 150 nodes, node names on hover, zoom and pan in ~0.07 s instead
  of ~2.4 s.
- **Export…**: graph and raw data for R, MATLAB and Python (node and edge CSV, GraphML, `.mat`, timestamped
  edits and interactions) and an image of the graph as PNG (300 dpi), SVG or PDF; with several formats, a
  single `.zip`. Graph types in file names and metadata are always in English (`collaboration`,
  `communication`, `composite`).

### Distribution
- Windows executable (no Python installation needed), attached to the release.
- Requirements: Python 3.10 or later to run from source; dependencies reduced to the ones actually used and
  compatible with recent versions of Python and the libraries.
