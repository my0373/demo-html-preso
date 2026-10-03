# Using community NetBox: an HTML presentation

A 34-slide browser presentation on how to use **community NetBox**, from running it with
netbox-docker through to automation, with eight use cases. It carries animated Blender 3D loops
and a jump-to-slide search.

| | |
|---|---|
| NetBox | **v4.7.2** (released 29 September 2026) |
| netbox-docker | **5.1.1** |
| Container image | `netboxcommunity/netbox:v4.7.2-5.1.1` |

The image tag format is `vX.Y.Z-a.b.c`, where `X.Y.Z` is the NetBox version and `a.b.c` is the
netbox-docker version it was built with. The netbox-docker README says the two must stay in step,
so the deck tells people to clone netbox-docker at tag `5.1.1` rather than `release`.

## View it

Open `index.html` in a browser. There is no server and no build step to view it. The only external
request is the Plus Jakarta Sans web font, and the deck degrades to system fonts without it.

| Key | Does |
|---|---|
| `←` `→` `Space` | Step through reveals, then slides |
| `G`, `/` or `O` | Jump to a slide. Type a title, a topic or a number, then `Enter` |
| `A` | Reveal everything on the current slide |
| `F` | Fullscreen |
| `Home` `End` | First and last slide |

Every slide has a deep link by number (`index.html#12`) or by id (`#model`, `#deploy`, `#usecases`).
Add `?all` to the URL to show every step at once, which is useful for screenshots.

## Rebuild it

`index.html` is generated. Edit the sources and rebuild:

```
python3 build.py
```

| Path | What it is |
|---|---|
| `src/slides-*.html` | The slides, in filename order. Placeholders such as `{{NB}}` and `{{TAG}}` are filled by the build |
| `src/template.html` | The slides engine: tokens, navigation, diagram edges. The deck's base engine, with only the example slides removed |
| `src/extra.css`, `src/extra.js` | This deck's additions: hero image, code panels, jump search, goto links |
| `build.py` | Assembles `index.html`. The three version constants at the top are the only place versions live |
| `blender/scenes.py` | The six Blender scenes |
| `assets/renders/` | The rendered loops (`.mp4`) and their poster frames (`.jpg`) |

### Moving to a new release

1. Change `NB` and `ND` in `build.py`, then run it.
2. Re-read the release notes for anything the deck states as fact. The slides on requirements,
   upgrades, the 4.7 features and the API are the ones tied to a version.
3. Check the image tag exists: `https://hub.docker.com/r/netboxcommunity/netbox/tags`.

## Re-render the 3D loops

The six 3D images are short **seamless animation loops**: 96 frames at 24 fps, so 4 seconds, in
H.264 MP4. They are made with Blender (built with 5.2.2 LTS), headless, so nothing in an open
Blender session is touched. `ffmpeg` encodes the result.

```
/Applications/Blender.app/Contents/MacOS/Blender -b -P blender/scenes.py -- [--quick] [--keep] [scene ...]
```

Scenes: `hero`, `datamodel`, `containers`, `ipam`, `globe`, `hub`. With no names it renders all six.
`--quick` renders at a third of the size with fewer samples, for a fast preview. `--keep` keeps
the PNG frames in `blender/_frames/` (ignored by git). Output goes to `assets/renders/` and can be
redirected with `DECK_RENDER_DIR`.

Each scene writes two files: `<name>.mp4` (the loop) and `<name>.jpg` (its first frame). The page
uses the JPEG as the poster and as the fallback for anyone with reduced motion turned on.

What moves in each scene: rack LEDs blink and pulse and light beads run along the overhead cabling
(`hero`); a wave of light climbs the tiers (`datamodel`); requests flow between services and status
lights blink (`containers`); address columns ripple in a diagonal wave while a light circles the
grid (`ipam`); traffic runs along circuits on a rocking globe (`globe`); the core turns, satellites
bob and pulses run along every spoke (`hub`). Every movement is a whole number of cycles per loop,
which is what makes the seam invisible.

Do not run it from inside a live Blender session through the MCP server. The render operator
draws the window's active scene, so you would render whatever is open instead of the scene built
here. That is why the script is headless.

## Motion in the page

All of it is plain CSS and a little JavaScript, with no libraries, and all of it is switched off
when the viewer has `prefers-reduced-motion` set.

- The 3D loops play **only on the slide in view**. All six preload up front (about 2.7 MB), so each
  starts instantly.
- Diagram connectors carry travelling beads of light, each out of step with its neighbours.
- Slides ease in (eyebrow, headline, then body), with a one-off shimmer across the teal words.
- Code blocks settle in line by line and end on a blinking caret.
- Table rows cascade, flow chevrons pulse, and flow steps light up in sequence.
- Highlighted cards breathe, status chips glow, and a faint ambient light drifts behind everything.

## Where the facts come from

The statements about netbox-docker and NetBox 4.7 were checked against sources rather than written
from memory:

- netbox-docker 5.1.1: `docker-compose.yml`, `docker-compose.override.yml.example`, the `env/`
  files and the README at that tag.
- NetBox v4.7.2: the release notes, and the REST, GraphQL, event rule, change logging, permission
  and configuration pages in its `docs/` folder.
- The `available-ips` and `available-prefixes` endpoints: confirmed in `netbox/ipam/api/urls.py`
  at `v4.7.2`.
- Image tags and dates: Docker Hub and the GitHub release pages.

Every link to a page (57 of 57) was fetched and resolves. Documentation links point at the official NetBox documentation site.

## Notes

- This deck is about community NetBox. It makes no claims about NetBox Enterprise or NetBox Cloud.
- The deck links to public documentation and to `demo.netbox.dev`. It deliberately links to no
  private instance.
- Example IP addresses are private-range illustrations.
- Written in British English.
