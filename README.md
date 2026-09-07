<a id="readme-top"></a>

# Mattel App Inspector

Computer-vision completeness inspection for PTMI production lines.

<details>
<summary>Table of contents</summary>

- [About the project](#about-the-project)
- [Getting started](#getting-started)
- [Usage](#usage)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)
- [Acknowledgments](#acknowledgments)

</details>

## About the project

Missing product components — accessories, shoes, inserts, wheels, labels, packaging — slip through
manual inspection. This project is aimed at catching them automatically across the roughly 130
production lines at PT Mattel Indonesia, at a cost per line that makes deploying to all of them
realistic.

What is in the repository today is the first prototype: a single-page [Streamlit][streamlit-url]
app that compares a captured photo against the stored golden samples for its SKU using structural
similarity (SSIM), and boxes any region that differs by more than a tunable amount. It runs on a phone or a
laptop webcam with no model, no training data and no GPU, which makes it useful for demonstrating
the interaction and gathering reference imagery.

Products are held by SKU. Each SKU keeps its own golden samples and its own named regions, so an
operator picks the product from a list rather than finding and uploading a photograph.

A SKU can hold several golden samples, and that is how tolerance is expressed. The capture is
scored against every one of them and the best agreement is kept for each pixel, so an area only
counts as differing when it differs from all of them. Photograph three or four correct units and
the normal variation between units stops reading as a defect. Adding a sample can only ever forgive
a difference, never create one.

Captures are registered against the samples before they are compared, and every inspection is
recorded to SQLite with the frame that produced it, so the archive accumulates into the labelled
set a later stage will need.

Naming the component is handled without a model. Regions of interest are named once per SKU on its
golden sample — `shoe_left`, `brush`, `stand` — and because a capture is registered onto that frame before
comparison, a rectangle drawn once keeps meaning the same thing on every later unit. A difference
is reported against the region it falls in rather than as an anonymous box.

It remains a prototype rather than the production design. SSIM detects that pixels changed, not
that a component is absent, so it cannot distinguish a missing part from a displaced or discoloured
one, and every region has to be named by hand. Object detection over component classes with a
per-SKU bill of materials would resolve both, and is deliberately deferred. See
[Roadmap](#roadmap).

### Built with

- [Streamlit][streamlit-url] — UI, camera capture and file upload
- [OpenCV][opencv-url] — image decoding, resizing, thresholding and contour extraction
- [scikit-image][skimage-url] — `structural_similarity`, the comparison itself
- [NumPy][numpy-url] — array handling between the three
- `sqlite3` and `hashlib` from the standard library — the inspection log, the named regions and the
  frame archive

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting started

### Prerequisites

- Python 3.12 — developed and compile-checked against 3.12.3
- A webcam, or a phone browser pointed at the running app

Check the interpreter:

```sh
python3 -V
```

### Installation

1. Clone the repository.

   ```sh
   git clone git@github.com:theonegareth/mattel-app-inspector.git
   cd mattel-app-inspector
   ```

2. Create and activate a virtual environment.

   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install the dependencies.

   ```sh
   pip install -r requirements.txt
   ```

There is no configuration file, no environment variable and no database. The app holds nothing
between sessions.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

Start the app:

```sh
streamlit run app.py
```

Streamlit serves on `http://localhost:8501` and opens a browser tab. The workflow runs top to bottom:

1. **Pick the SKU.** The dropdown lists every SKU that already has a golden sample. Choosing
   *— new SKU —* asks for a code instead.
2. **Give it golden samples.** A photograph of a correct, complete unit, stored under `references/`
   and remembered against the SKU. Upload more than one to widen the tolerance; the uploader keeps
   offering to add another, and the same file twice stays one sample. The first sample is the
   **anchor**: it fixes the coordinate frame, every later sample is registered onto it, and a
   sample too unlike it to register is named and left out of the comparison rather than allowed to
   corrupt it. The *Golden samples* expander lists them, marks the anchor and removes any of them.
   Nothing below appears until a SKU has at least one — the camera widget stays hidden.
3. **Name its regions**, once, under *Inspection regions*. Give each component's area a name and a
   rectangle. Regions belong to the SKU, not to a photograph, so adding or removing samples keeps
   them; saving a name that already exists moves that region rather than adding a second.
   This step is optional — without it a difference is reported as an anonymous box.
4. **Capture a unit.** Position the product in frame and tap the shutter. The frame is letterboxed
   onto a 640x480 canvas, converted to grayscale and blurred, exactly as the reference was.
5. **Registration.** ORB features are matched between the capture and the anchor and a partial
   affine transform is fitted, so the two are compared point for point rather than pixel for pixel.
   Where the match is not trustworthy the app says so and compares the frame as shot.
6. **Read the verdict.** PASS or REJECT, alongside a similarity percentage. A failure names the
   regions to check — *Check these regions: brush, shoe_left* — and each box on the overlay carries
   its region's name. A collapsible binary difference mask and the last ten inspections sit below.

Two parameters in the sidebar control the decision, and both re-evaluate the last capture as soon
as they move:

| Parameter | Range | Default | Effect |
| --- | --- | --- | --- |
| Sensitivity Threshold | 30-200, step 5 | 80 | Local similarity below this value counts as differing. Higher rejects more. |
| Min Defect Size (px) | 100-5000, step 100 | 800 | A differing region smaller than this is ignored. 800 px is about 0.26 percent of the frame. |

The verdict is driven by the region test alone: REJECT means at least one connected differing region
exceeded the minimum size. The similarity percentage is reported for context and does not enter the
decision.

### What is recorded

Each capture writes one row to `inspections.db` and one file to `captures/`. Golden samples go to
`references/`. All three are created on first use and all three are ignored by git.

Alongside the inspection log the database holds a `reference` row per golden sample — its SKU,
digest, path and when it was added, unique on SKU and digest — and a `zone` row per named region.
A database written by an earlier version keeps loading: columns added after the fact carry a
default and arrive by `ALTER TABLE`, and the `reference` table, which once allowed a SKU only one
sample, is rebuilt on open with that sample carried over as its first.

| Column | Holds |
| --- | --- |
| `inspected_at` | when the capture was judged |
| `sku` | the product the capture was judged against |
| `verdict` | `PASS` or `REJECT` |
| `similarity` | the SSIM score as a percentage |
| `defects` | how many regions exceeded the minimum size |
| `regions` | the named regions those differences fell in, comma separated |
| `aligned` | whether registration succeeded, or the frame was compared as shot |
| `threshold`, `min_area` | the parameters in force at capture time |
| `capture` | path to the frame, named by its content hash |

One row per capture. Re-tuning the sliders re-scores the frame on screen without recording it
again.

### Known limitations

These are properties of the SSIM approach, not defects to be tuned out. They are the reason for the
[Roadmap](#roadmap).

- **A difference is not a diagnosis.** A named region tells you where to look, not what went wrong:
  SSIM cannot separate an absent part from a displaced, rotated or discoloured one. The report says
  "check these regions" for that reason.
- **Regions are named by hand.** Each one is a rectangle typed in as four numbers. A difference
  falling outside every named region is still reported as an anonymous box.
- **Tolerance is only as wide as the samples given.** A SKU photographed once has none: hold three
  or four correct units, or normal variation reads as a defect.
- **Registration declines on repeating detail.** A grid of identical parts, or a repeated print
  pattern, matches many places equally well. Rather than risk a confident fit one repeat out of
  place, the app declines to warp and warns. That is the safe answer, not a good one.
- **Only shift, rotation and scale are corrected.** A station shooting the product at an angle
  needs a homography, which this does not fit.
- **Padding bars only cancel when both images share an aspect ratio.** One fixed station camera
  satisfies that; a phone photograph as the reference against a webcam capture does not.
- **Colour is discarded** before comparison, so a wrong-colour variant of the right shape passes.
- **Camera access needs a secure context.** Browsers block `getUserMedia` on plain `http://`, so
  anything beyond `localhost` has to be served over HTTPS or the shutter silently does nothing.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Roadmap

- [x] SSIM prototype with live sensitivity tuning
- [x] Guard a failed image decode instead of throwing inside `cv2.resize`
- [x] Clip the SSIM map before the `uint8` cast, so a negative local score cannot wrap to a match
- [x] Register the capture against the reference before comparing, and decline an untrustworthy fit
- [x] Letterbox the capture rather than squashing it onto the canvas
- [x] Record every inspection to SQLite and keep the frame that produced it
- [x] Pin `requirements.txt` from a real environment
- [x] Name regions on the golden sample, and report which of them a difference falls in
- [x] Store a golden sample and its regions per SKU, so neither needs re-uploading
- [x] Accept several golden samples per SKU, scoring a capture against the best-agreeing one
- [ ] Agree the component class list with PTMI
- [ ] Collect roughly 150-300 labelled images per class on the line, under production lighting
- [ ] Train a YOLO detector over component classes
- [ ] Replace the SSIM comparison with detection plus a per-SKU bill of materials, reporting missing
      and extra parts by name
- [ ] Serve over HTTPS for on-floor use

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contributing

1. Branch from `main`, named for the change.

   ```sh
   git switch -c fix/decode-guard
   ```

2. Make the change, then compile-check anything you touched and run the self-checks.

   ```sh
   python3 -m py_compile app.py
   python3 test_align.py
   python3 test_log.py
   python3 test_zones.py
   python3 test_reference.py
   ```

3. Commit using the project convention: an emoji, then `type(scope): summary`, a blank line, then a
   bullet for every notable change. The summary and bullets are lowercase apart from formal or
   technical terms. One commit is one major change.

   ```
   🐛 fix(inspector): guard a failed decode, and stop the diff map wrapping

   - halt with a message when cv2.imdecode returns None, instead of throwing inside cv2.resize
   - clip the SSIM map to [0, 1] before the uint8 cast
   ```

   | Emoji | Type | Use for |
   | --- | --- | --- |
   | ✨ | `feat` | a new feature or capability |
   | 🐛 | `fix` | a bug fix |
   | ♻️ | `refactor` | restructuring with no behaviour change |
   | 🎨 | `style` | formatting only, no logic change |
   | 🔧 | `chore` | tooling, config, dependency, maintenance |
   | ✅ | `test` | adding or updating tests |
   | 📝 | `docs` | documentation only |
   | ⚡ | `perf` | performance improvement |
   | ⏪ | `revert` | reverting a previous commit |
   | 👷 | `ci` | CI/CD pipeline changes |
   | 🔒 | `security` | security fixes or hardening |
   | 🗃️ | `db` | schema or migration changes |

4. Push the branch and open a pull request against `main`.

Code style: four-space indentation, matching `app.py`. Comments only where the intent is not
obvious from the code.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

Distributed under the Apache License 2.0. See [`LICENSE`][license-url] for the full text.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contact

Gareth A. Harrison — [@theonegareth][github-profile]

Repository: [theonegareth/mattel-app-inspector][repo-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Acknowledgments

- The reference-versus-capture SSIM difference pattern this prototype follows is the one popularised
  by [PyImageSearch][pyimagesearch-url].
- [scikit-image][skimage-url] implements `structural_similarity`, which does the actual comparison.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

[repo-url]: https://github.com/theonegareth/mattel-app-inspector
[github-profile]: https://github.com/theonegareth
[license-url]: https://github.com/theonegareth/mattel-app-inspector/blob/main/LICENSE
[streamlit-url]: https://streamlit.io
[opencv-url]: https://opencv.org
[skimage-url]: https://scikit-image.org
[numpy-url]: https://numpy.org
[pyimagesearch-url]: https://pyimagesearch.com/2017/06/19/image-difference-with-opencv-and-python/
