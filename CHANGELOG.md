# Changelog

All notable changes to the Racing Tagger project will be documented in this file.

## [1.2.0] - 2025-12-23

### Fixed
- **Color as List Bug**: Fixed issue where model returning color as a list (e.g., `['black', 'blue', 'purple']`) caused malformed keywords in Lightroom
  - Now joins list elements with " and " (e.g., "black and blue and purple")
- **Numbers Containing Non-Numeric Values**: Fixed parsing to filter out non-numeric values from numbers array
  - Only digit strings are now accepted as car numbers

### Changed
- **Primary Car Selection**: Updated all prompts (Porsche, NASCAR, IMSA) to prioritize the car that is:
  1. Most prominent in the frame (largest, most centered)
  2. In sharpest focus
  - Cars mostly outside the frame, blurry, or in background are now ignored entirely
- **Anti-Hallucination Guidance**: Added explicit instructions to prevent number hallucination
  - Only report numbers that can be ACTUALLY READ CLEARLY
  - Return empty numbers array for head-on/rear shots where number isn't visible
  - Do not guess numbers from livery, sponsor colors, or other inference
  - Do not report numbers from blurry or out-of-focus cars

### Testing
- Tested IMSA profile on 1,237 images from 2018 IMSA VIR event
- Tested NASCAR profile on 534 images from 2024 SOBO Thunder Road event
- Verified primary car selection works for multi-car shots
- Confirmed hierarchical keywords display correctly in Lightroom

---

## [1.1.1] - 2025-12-21

### Fixed
- **Hierarchical Keywords Not Displaying as Trees in Lightroom**: Fixed issue where AI Keywords were written to XMP but not displayed as expandable tree structure in Lightroom's Keyword List
  - Root cause: Hierarchical keywords were being written to HierarchicalSubject field only, which Lightroom doesn't display in Keyword List
  - Solution: Write hierarchical keywords to Subject field using pipe-separated paths (e.g., `AI Keywords|Make|Porsche`)
  - Lightroom now correctly displays the keyword hierarchy as expandable trees with categories and values
  - Tested with multiple image formats and batch processing

### Changed
- `xmp_writer.py`: Updated keyword writing logic
  - Now writes hierarchical keywords using pipe-separated paths in Subject field
  - Maintains compatibility with HierarchicalSubject field for other applications
  - Each hierarchy level is written as a separate distinct value

### Testing
- ✅ Verified hierarchical structure displays correctly in Lightroom's Keyword List
- ✅ Tested with multiple car models and classifications
- ✅ Confirmed expandable/collapsible tree behavior works
- ✅ Batch processing of 7+ images successful

---

## [1.1.0] - 2025-12-20

### Fixed
- **Windows Lightroom Plugin Crash**: Fixed "attempt to call field 'getenv' (a nil value)" error
  - Lightroom's Lua sandbox doesn't expose the `os` library for security reasons
  - Replaced all `os.getenv()` calls with Lightroom's officially supported `LrPathUtils` API
  - Plugin now fully compatible with Windows Lightroom Classic and CC

### Changed
- `RacingTagger.lrplugin/Config.lua`: Removed environment variable dependencies
  - `getLogFile()` now uses `LrPathUtils.getStandardFilePath('temp')`
  - `getOutputLog()` now uses `LrPathUtils.getStandardFilePath('temp')`
  - `getPythonPath()` simplified to rely on PATH and standard installation locations

### Details
- No changes to Python code
- No changes to other Lua modules
- No API changes or user-facing behavior changes
- Maintains backward compatibility with macOS and Linux

### Testing
- ✅ Windows 10/11 with Lightroom Classic 13
- ✅ Single photo and batch processing (11 image test)
- ✅ XMP sidecar creation and keyword writing verified
- ✅ Both dry-run and live processing modes

---

## [1.0.0] - 2024-12-18

### Added
- Initial release of Racing Tagger
- Automatic metadata extraction from racing photography using local vision models
- Support for multiple profiles (racing-porsche, racing-general, college-sports)
- XMP keyword writing for Lightroom searchability
- Batch processing capabilities
- Dry-run mode for preview before writing
- Support for RAW files (NEF, CR2, etc.) with XMP sidecars
- Support for embedded metadata (JPG, TIFF, PNG)
- Progress tracking and logging
- Windows, macOS, and Linux support

---

[1.1.1]: https://github.com/blwfish/LrC-classification/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/blwfish/LrC-classification/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/blwfish/LrC-classification/releases/tag/v1.0.0
