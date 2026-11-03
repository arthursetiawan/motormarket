# Publish Motormarket / NegoMotor demo

## Motormarket GitHub Pages (preferred)

Repo Pages is enabled with **GitHub Actions** (`build_type: workflow`).
Pushing to `main` (or running **Actions → Deploy portfolio to GitHub Pages**) publishes
`docs/portfolio/` to:

- https://arthursetiawan.github.io/motormarket/ — portfolio homepage
- https://arthursetiawan.github.io/motormarket/motormarket/ — static Motormarket demo

Workflow: `.github/workflows/pages.yml`

## Optional: arthursetiawan.github.io

`cursor[bot]` cannot push there unless the Cursor GitHub App includes
`arthursetiawan/arthursetiawan.github.io` with Contents read/write. One-step go-live:

```bash
# from a clone of arthursetiawan.github.io on main
SRC=/path/to/motormarket/docs/portfolio
DEST=/path/to/arthursetiawan.github.io

cp "$SRC/index.html" "$DEST/index.html"
rm -rf "$DEST/motormarket"
cp -a "$SRC/motormarket" "$DEST/motormarket"
# optional: keep site favicon if portfolio has one
test -f "$SRC/favicon.ico" && cp "$SRC/favicon.ico" "$DEST/favicon.ico"
cd "$DEST"
git add index.html motormarket
git commit -m "Polish portfolio homepage with Motormarket front and center"
git push origin main
```

Live targets after that push:

- https://arthursetiawan.github.io/
- https://arthursetiawan.github.io/motormarket/

Preserves existing `resume/`, `favicon.ico`, `pic.jpeg`, etc. when only those two paths change.
