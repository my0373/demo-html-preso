"""Blender scenes for the community NetBox deck.

Run headless, from the repo root:

    /Applications/Blender.app/Contents/MacOS/Blender -b -P blender/scenes.py -- [--quick] [scene ...]

Each scene is built from an empty factory file and rendered to assets/renders/<name>.webp.
Running headless leaves any open Blender session untouched.

Palette matches the deck: navy #001423, teal #00f2d4, amber #ffac00, violet #b39dff.
"""
import math
import os
import random

import bmesh
import bpy
from mathutils import Vector

OUT = os.environ.get(
    "DECK_RENDER_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "renders"),
)
RES = (1920, 1080)


def lin(h):
    """sRGB hex string to linear RGBA."""
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return (*c, 1.0)


NAVY, PANEL, PANEL2 = "#001423", "#04202f", "#0a3347"
TEAL, AMBER, VIOLET, GREEN, BLUE = "#00f2d4", "#ffac00", "#b39dff", "#7ee081", "#7fc8ff"


class Ctx:
    def __init__(self, name, scene=None):
        self.sc = scene or bpy.data.scenes.new(name)
        self.col = self.sc.collection
        self.mats = {}

    def mat(self, key, color, emit=0.0, rough=0.35, metal=0.0, alpha=1.0):
        if key in self.mats:
            return self.mats[key]
        m = bpy.data.materials.new(f"{self.sc.name}_{key}")
        m.use_nodes = True
        b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Base Color"].default_value = lin(color)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Metallic"].default_value = metal
        b.inputs["Alpha"].default_value = alpha
        if emit:
            b.inputs["Emission Color"].default_value = lin(color)
            b.inputs["Emission Strength"].default_value = emit
        self.mats[key] = m
        return m

    def link(self, name, data, mat=None, loc=(0, 0, 0), rot=(0, 0, 0)):
        o = bpy.data.objects.new(name, data)
        o.location, o.rotation_euler = loc, rot
        if mat is not None and hasattr(data, "materials"):
            data.materials.append(mat)
        self.col.objects.link(o)
        return o

    def mesh_from(self, name, bm, mat, loc=(0, 0, 0), bevel=0.0, smooth=False):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        o = self.link(name, me, mat, loc)
        if smooth:
            for p in me.polygons:
                p.use_smooth = True
        if bevel:
            md = o.modifiers.new("bevel", "BEVEL")
            md.width, md.segments, md.limit_method = bevel, 2, "ANGLE"
        return o

    def box(self, name, loc, size, mat, bevel=0.02):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
        return self.mesh_from(name, bm, mat, loc, bevel)

    def cyl(self, name, loc, r, h, mat, seg=48):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
        return self.mesh_from(name, bm, mat, loc, smooth=True)

    def sphere(self, name, loc, r, mat, seg=32):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=r)
        return self.mesh_from(name, bm, mat, loc, smooth=True)

    def tube(self, name, pts, mat, r=0.03, arc=0.0):
        """Bevelled curve through pts. arc>0 lifts the middle control point."""
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth, cu.bevel_resolution = r, 3
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(pts) - 1)
        for bp, p in zip(sp.bezier_points, pts):
            bp.co = p
            bp.handle_left_type = bp.handle_right_type = "AUTO"
        return self.link(name, cu, mat)

    def arc(self, name, a, b, mat, lift, r=0.02):
        a, b = Vector(a), Vector(b)
        mid = (a + b) / 2
        mid = mid + (mid.normalized() if mid.length else Vector((0, 0, 1))) * lift \
            if lift < 0 else mid + Vector((0, 0, lift))
        return self.tube(name, [a, mid, b], mat, r)

    def point(self, loc, energy, color=TEAL, radius=0.3):
        li = bpy.data.lights.new("p", "POINT")
        li.energy, li.color, li.shadow_soft_size = energy, lin(color)[:3], radius
        self.link("p", li, loc=loc)

    def area(self, loc, energy, size=6, color="#ffffff", aim=(0, 0, 0)):
        li = bpy.data.lights.new("a", "AREA")
        li.energy, li.size, li.color = energy, size, lin(color)[:3]
        o = self.link("a", li, loc=loc)
        d = Vector(aim) - Vector(loc)
        o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

    def floor(self, size=80, color=PANEL, rough=0.18, z=0.0):
        bm = bmesh.new()
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
        return self.mesh_from("floor", bm, self.mat("floor", color, rough=rough, metal=0.2), (0, 0, z))

    def camera(self, loc, aim, lens=50):
        cam = bpy.data.cameras.new("cam")
        cam.lens = lens
        o = self.link("cam", cam, loc=loc)
        o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        self.sc.camera = o
        return o

    def world(self, color=NAVY, strength=1.0):
        w = bpy.data.worlds.new(self.sc.name)
        w.use_nodes = True
        bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
        bg.inputs["Color"].default_value = lin(color)
        bg.inputs["Strength"].default_value = strength
        self.sc.world = w


def setup_render(ctx, path, samples=96):
    sc = ctx.sc
    r = sc.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = *RES, 100
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            r.engine = eng
            break
        except TypeError:
            continue
    try:
        sc.eevee.taa_render_samples = samples
        sc.eevee.use_raytracing = True
    except Exception:
        pass
    try:
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
    except Exception:
        pass
    fmts = [i.identifier for i in r.image_settings.bl_rna.properties["file_format"].enum_items]
    fmt = "WEBP" if "WEBP" in fmts else "JPEG"
    r.image_settings.file_format = fmt
    r.image_settings.quality = 90
    ext = ".webp" if fmt == "WEBP" else ".jpg"
    r.filepath = os.path.join(OUT, path + ext)
    return r.filepath


def glow(ctx):
    """Bloom-style glow via the compositor. Best effort: API differs by version."""
    sc = ctx.sc
    try:
        if hasattr(sc, "compositing_node_group"):
            ng = bpy.data.node_groups.new("glow", "CompositorNodeTree")
            sc.compositing_node_group = ng
        else:
            sc.use_nodes = True
            ng = sc.node_tree
            ng.nodes.clear()
        rl = ng.nodes.new("CompositorNodeRLayers")
        gl = ng.nodes.new("CompositorNodeGlare")
        try:
            gl.glare_type = "BLOOM"
        except Exception:
            pass
        try:
            gl.quality, gl.threshold, gl.size = "HIGH", 0.8, 7
        except Exception:
            pass
        for nm, val in (("Threshold", 0.9), ("Strength", 0.6), ("Size", 0.7), ("Type", "Bloom")):
            try:
                gl.inputs[nm].default_value = val
            except Exception:
                pass
        if hasattr(sc, "compositing_node_group"):
            out = ng.nodes.new("NodeGroupOutput")
            try:
                ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
            except Exception:
                pass
        else:
            out = ng.nodes.new("CompositorNodeComposite")
        ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ng.links.new(gl.outputs["Image"], out.inputs[0])
        return True
    except Exception as e:
        print("glow unavailable:", e)
        return False


# --------------------------------------------------------------------------- scenes

def scene_hero(ctx):
    """Data centre aisle: two rows of racks, glowing front panels, overhead cabling."""
    rnd = random.Random(7)
    ctx.world(NAVY, 0.4)
    ctx.floor(120)
    body = ctx.mat("body", PANEL2, rough=0.5, metal=0.5)
    dark = ctx.mat("dark", "#010a12", rough=0.6)
    leds = [ctx.mat("t", TEAL, 6), ctx.mat("a", AMBER, 5), ctx.mat("v", VIOLET, 5), ctx.mat("g", GREEN, 5)]
    for side in (-1, 1):
        y = side * 1.9
        for i in range(12):
            x = i * 1.25
            ctx.box(f"rack{side}{i}", (x, y, 1.15), (1.0, 1.0, 2.3), body, 0.02)
            ctx.box(f"door{side}{i}", (x, y - side * 0.48, 1.15), (0.86, 0.04, 2.1), dark, 0.01)
            for u in range(16):
                if rnd.random() < 0.82:
                    m = leds[0] if rnd.random() < 0.7 else rnd.choice(leds[1:])
                    w = rnd.choice((0.5, 0.6, 0.7))
                    ctx.box(f"u{side}{i}{u}", (x - 0.12, y - side * 0.51, 0.3 + u * 0.12),
                            (w, 0.02, 0.05), m, 0.005)
    # overhead trays and drops
    tray = ctx.mat("tray", TEAL, 7)
    for y in (-0.7, 0.7):
        ctx.tube(f"tray{y}", [(2.5, y, 2.85), (9, y, 2.85), (22, y, 2.85)], tray, 0.035)
    for i in range(0, 12, 2):
        x = i * 1.25
        for side in (-1, 1):
            ctx.tube(f"drop{i}{side}", [(x, side * 0.7, 2.9), (x, side * 1.3, 2.7), (x, side * 1.9, 2.35)],
                     ctx.mat("c" + str(i % 3), [TEAL, VIOLET, AMBER][i % 3], 6), 0.025)
    ctx.camera((-6.0, 0.0, 1.5), (6.0, 0.0, 1.5), 22)
    ctx.area((2, 0, 4.5), 700, 5, TEAL, (6, 0, 0))
    ctx.point((0, 0, 2.5), 400, VIOLET, 1)
    return "hero"


def scene_datamodel(ctx):
    """Region > site > location > rack > device as five floating slabs."""
    ctx.world(NAVY, 0.3)
    ctx.floor(80, z=-0.05)
    glass = ctx.mat("glass", PANEL2, rough=0.15, metal=0.3)
    edge = ctx.mat("edge", TEAL, 8)
    tiers = [(7.0, TEAL), (5.6, VIOLET), (4.2, AMBER), (2.9, BLUE), (1.7, GREEN)]
    rnd = random.Random(3)
    for i, (s, col) in enumerate(tiers):
        z = i * 1.35
        ctx.box(f"slab{i}", (0, 0, z), (s, s, 0.14), glass, 0.04)
        ctx.box(f"edge{i}", (0, 0, z - 0.09), (s + 0.04, s + 0.04, 0.03), ctx.mat("e" + col, col, 7), 0.01)
        for k in range(i + 2):
            a = rnd.uniform(0, 6.28)
            rr = (s / 2 - 0.5) * rnd.uniform(0.2, 1.0) if i < 4 else 0
            ctx.box(f"n{i}{k}", (math.cos(a) * rr, math.sin(a) * rr, z + 0.3),
                    (0.35, 0.35, 0.35 + (i % 2) * 0.1), ctx.mat("n" + col, col, 3, rough=0.3), 0.04)
        if i:
            for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                p = tiers[i][0] / 2 - 0.15
                ctx.tube(f"beam{i}{dx}{dy}", [(dx * p, dy * p, z - 1.2), (dx * p, dy * p, z)], edge, 0.018)
    ctx.camera((14, -14, 8.5), (0, 0, 2.7), 38)
    ctx.area((5, -5, 10), 900, 8, "#ffffff", (0, 0, 2))
    ctx.point((0, 0, 7), 600, TEAL, 1)
    return "datamodel"


def scene_containers(ctx):
    """Four services on a plinth, linked by glowing tubes."""
    ctx.world(NAVY, 0.3)
    ctx.floor(80, z=-0.3)
    ctx.box("plinth", (0, 0, -0.1), (11, 7, 0.3), ctx.mat("plinth", PANEL2, rough=0.2, metal=0.4), 0.06)
    ctx.box("plinth_edge", (0, 0, -0.27), (11.1, 7.1, 0.04), ctx.mat("pe", TEAL, 7), 0.01)
    nbx = ctx.box("netbox", (0, 0, 1.1), (2.6, 2.6, 2.2), ctx.mat("nbx", TEAL, 0.25, rough=0.25), 0.12)
    ctx.box("nbx_ring", (0, 0, 2.3), (2.9, 2.9, 0.08), ctx.mat("nbxr", TEAL, 9), 0.01)
    pg = ctx.cyl("pg", (-3.6, -1.6, 0.9), 1.0, 1.8, ctx.mat("pg", BLUE, 0.2, rough=0.25))
    for k in range(3):
        ctx.cyl(f"pgr{k}", (-3.6, -1.6, 0.35 + k * 0.6), 1.04, 0.05, ctx.mat("pgr", BLUE, 8), 48)
    ctx.box("cache", (3.6, -1.6, 0.6), (1.7, 1.7, 1.2), ctx.mat("cache", AMBER, 0.25, rough=0.25), 0.1)
    ctx.box("cache_ring", (3.6, -1.6, 0.95), (1.78, 1.78, 0.05), ctx.mat("cr", AMBER, 9), 0.01)
    ctx.box("worker", (0, 2.4, 0.7), (2.2, 1.5, 1.4), ctx.mat("worker", VIOLET, 0.2, rough=0.25), 0.1)
    ctx.box("worker_ring", (0, 2.4, 1.0), (2.28, 1.58, 0.05), ctx.mat("wr", VIOLET, 9), 0.01)
    link = ctx.mat("link", TEAL, 8)
    ctx.tube("l1", [(-2.6, -1.4, 0.9), (-1.8, -1.0, 1.0), (-1.3, -0.6, 1.0)], link, 0.05)
    ctx.tube("l2", [(2.8, -1.4, 0.7), (2.1, -1.0, 0.9), (1.3, -0.6, 1.0)], link, 0.05)
    ctx.tube("l3", [(0, 1.5, 0.9), (0, 1.0, 1.0), (0, 1.3, 1.0)], link, 0.05)
    ctx.camera((14, -14, 9.5), (0, 0, 0.8), 40)
    ctx.area((4, -6, 9), 800, 7, "#ffffff", (0, 0, 1))
    ctx.point((0, 0, 4), 500, TEAL, 1)
    return "containers"


def scene_ipam(ctx):
    """An address plan as a city: height is utilisation."""
    rnd = random.Random(11)
    ctx.world(NAVY, 0.3)
    ctx.floor(80, z=-0.02)
    n = 16
    mats = [(ctx.mat("lo", "#0d4a63", 0.08, rough=0.3), 0.15),
            (ctx.mat("mid", TEAL, 0.45, rough=0.3), 0.55),
            (ctx.mat("hi", AMBER, 0.6, rough=0.3), 1.0)]
    # a few "prefix" zones with their own base level so it reads as structure
    for i in range(n):
        for j in range(n):
            zone = (i // 4 + j // 4) % 3
            v = min(1.0, max(0.05, rnd.random() * 0.8 + 0.1 * zone))
            h = 0.12 + v * 2.2 * (0.4 + 0.6 * (i / n))
            m = mats[0][0] if v < 0.4 else mats[1][0] if v < 0.8 else mats[2][0]
            ctx.box(f"t{i}_{j}", ((i - n / 2) * 0.62, (j - n / 2) * 0.62, h / 2), (0.52, 0.52, h), m, 0.02)
    ctx.camera((13, -13, 10), (0, 0, 0.4), 40)
    ctx.area((5, -3, 9), 500, 7, "#ffffff", (0, 0, 0))
    ctx.point((0, 0, 5), 300, TEAL, 1)
    return "ipam"


def scene_globe(ctx):
    """Sites around the world, linked by great-circle arcs (circuits)."""
    ctx.world(NAVY, 0.3)
    R = 2.2
    ctx.sphere("core", (0, 0, 0), R * 0.985, ctx.mat("core", "#031a28", rough=0.4))
    wire = ctx.sphere("wire", (0, 0, 0), R, ctx.mat("wire", TEAL, 2.5), 28)
    md = wire.modifiers.new("wf", "WIREFRAME")
    md.thickness, md.use_replace = 0.006, True

    def ll(lat, lon, r=R):
        la, lo = math.radians(lat), math.radians(lon)
        return (r * math.cos(la) * math.cos(lo), r * math.cos(la) * math.sin(lo), r * math.sin(la))

    sites = [(51.5, -0.1), (40.7, -74), (37.8, -122.4), (-23.5, -46.6), (1.35, 103.8), (35.7, 139.7),
             (-33.9, 151.2), (28.6, 77.2), (-26.2, 28), (52.5, 13.4), (25.2, 55.3), (55.7, 37.6)]
    beacon = [ctx.mat("b" + c, c, 9) for c in (TEAL, AMBER, VIOLET)]
    for k, (la, lo) in enumerate(sites):
        ctx.sphere(f"s{k}", ll(la, lo, R * 1.01), 0.055, beacon[k % 3], 12)
        ctx.tube(f"sp{k}", [ll(la, lo, R), ll(la, lo, R * 1.12)], beacon[k % 3], 0.012)
    link = ctx.mat("arc", AMBER, 6)
    for a, b in [(0, 1), (1, 2), (0, 9), (9, 10), (10, 7), (7, 4), (4, 5), (5, 2), (4, 6), (0, 8), (1, 3), (11, 5), (9, 11)]:
        pa, pb = Vector(ll(*sites[a], R)).normalized(), Vector(ll(*sites[b], R)).normalized()
        ang = pa.angle(pb)
        pts = []
        for t in range(0, 21):
            f = t / 20
            v = (pa * math.sin((1 - f) * ang) + pb * math.sin(f * ang)) / math.sin(ang)
            pts.append(v.normalized() * (R * 1.01 + math.sin(f * math.pi) * R * 0.18 * (ang / math.pi + 0.3)))
        ctx.tube(f"arc{a}{b}", pts, link, 0.014)
    ctx.camera((2.0, -11.5, 3.0), (0, 0, 0), 45)
    ctx.area((4, -5, 5), 500, 5, "#ffffff", (0, 0, 0))
    ctx.point((-3, -4, 2), 300, VIOLET, 1)
    ctx.sc.world.node_tree.nodes  # keep world alive
    # tilt so the Europe/Asia side faces the camera
    for o in list(ctx.col.objects):
        if o.type in {"MESH", "CURVE"}:
            o.rotation_euler = (0, 0, math.radians(-95))
            o.rotation_euler[0] = math.radians(-20)
    return "globe"


def scene_hub(ctx):
    """NetBox in the middle, integrations around it."""
    ctx.world(NAVY, 0.3)
    ctx.floor(80, z=-0.35)
    ring = bpy.data.meshes.new("ring")
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, radius=4.6, segments=96)
    bm.to_mesh(ring)
    bm.free()
    ro = ctx.link("ring", ring, ctx.mat("ringm", TEAL, 5), loc=(0, 0, -0.3))
    sk = ro.modifiers.new("sk", "SCREW")
    sk.angle, sk.steps, sk.render_steps, sk.screw_offset = 0, 1, 1, 0
    ctx.cyl("base", (0, 0, -0.2), 1.9, 0.12, ctx.mat("base", PANEL2, rough=0.2, metal=0.4))
    ctx.box("core", (0, 0, 1.0), (1.8, 1.8, 1.8), ctx.mat("core", TEAL, 0.6, rough=0.2), 0.1)
    ctx.box("core_in", (0, 0, 1.0), (1.2, 1.2, 1.2), ctx.mat("coreI", "#ffffff", 4), 0.05)
    cols = [TEAL, AMBER, VIOLET, BLUE, GREEN, AMBER, VIOLET, BLUE]
    shapes = ["sphere", "box", "cyl", "box", "sphere", "cyl", "box", "sphere"]
    for k in range(8):
        a = k / 8 * math.tau + 0.3
        p = (math.cos(a) * 4.6, math.sin(a) * 4.6, 0.55)
        m = ctx.mat(f"sat{k}", cols[k], 1.2, rough=0.25)
        if shapes[k] == "sphere":
            ctx.sphere(f"sat{k}", p, 0.6, m)
        elif shapes[k] == "box":
            ctx.box(f"sat{k}", p, (1.0, 1.0, 1.0), m, 0.08)
        else:
            ctx.cyl(f"sat{k}", p, 0.55, 1.1, m)
        ctx.tube(f"sp{k}", [(math.cos(a) * 1.0, math.sin(a) * 1.0, 1.0), (math.cos(a) * 2.8, math.sin(a) * 2.8, 1.5),
                            (math.cos(a) * 4.0, math.sin(a) * 4.0, 0.6)], ctx.mat("sl" + cols[k], cols[k], 8), 0.035)
    ctx.camera((12, -12, 8.5), (0, 0, 0.7), 40)
    ctx.area((4, -6, 9), 800, 7, "#ffffff", (0, 0, 1))
    ctx.point((0, 0, 3.5), 700, TEAL, 1)
    return "hub"


SCENES = {
    "hero": scene_hero,
    "datamodel": scene_datamodel,
    "containers": scene_containers,
    "ipam": scene_ipam,
    "globe": scene_globe,
    "hub": scene_hub,
}


def render_one(name, samples=96, with_glow=True):
    """Build and render one scene into the current (context) scene."""
    ctx = Ctx(f"deck_{name}", bpy.context.scene)
    for o in list(ctx.col.objects):
        bpy.data.objects.remove(o)
    SCENES[name](ctx)
    path = setup_render(ctx, name, samples)
    if with_glow:
        glow(ctx)
    bpy.ops.render.render(write_still=True)
    return path


def render_scenes(names, samples=96, with_glow=True):
    """Each scene starts from an empty factory file, so nothing leaks between renders."""
    os.makedirs(OUT, exist_ok=True)
    done = []
    for n in names:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        done.append(render_one(n, samples, with_glow))
    return done


if __name__ == "__main__":
    # blender -b -P blender/scenes.py -- [--quick] [scene ...]
    # Headless on purpose: the render operator draws the window's active scene, so running it
    # inside a live Blender session renders whatever is open instead of the scene built here.
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    quick = "--quick" in argv
    names = [a for a in argv if not a.startswith("--")] or list(SCENES)
    print("RENDERED", render_scenes(names, samples=24 if quick else 96))
