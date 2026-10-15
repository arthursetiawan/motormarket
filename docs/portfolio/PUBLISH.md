# Publish to arthursetiawan.github.io

`cursor[bot]` cannot push to `arthursetiawan/arthursetiawan.github.io` (403). One-step go-live from this folder:

```bash
# from a clone of arthursetiawan.github.io on main
SRC=/path/to/motormarket/docs/portfolio
DEST=/path/to/arthursetiawan.github.io

cp "$SRC/index.html" "$DEST/index.html"
rm -rf "$DEST/motormarket"
cp -a "$SRC/motormarket" "$DEST/motormarket"
cd "$DEST"
git add index.html motormarket
git commit -m "Polish portfolio homepage with Motormarket front and center"
git push origin main
```

Live targets after push:
- https://arthursetiawan.github.io/
- https://arthursetiawan.github.io/motormarket/

Preserves existing `resume/`, `favicon.ico`, `pic.jpeg`, etc.
