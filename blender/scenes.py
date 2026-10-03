"""Animated Blender scenes for the community NetBox deck.

Each scene is a seamless loop (N frames at 24 fps, 4 seconds by default). Every moving thing is a
function of loop time with a whole number of cycles, so the last frame flows into the first.

Run headless, from the repo root:

    /Applications/Blender.app/Contents/MacOS/Blender -b -P blender/scenes.py -- [--quick] [--keep] [scene ...]

For each scene it renders a PNG frame sequence, encodes assets/renders/<name>.mp4 with ffmpeg (H.264,
no audio, faststart) and saves the first frame as assets/renders/<name>.jpg, which the page uses as
the poster and as the reduced-motion fallback. Running headless leaves any open Blender session
untouched.

Palette matches the deck: navy #001423, teal #00f2d4, amber #ffac00, violet #b39dff.
"""
import math
import os
import random
import shutil
import subprocess

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("DECK_RENDER_DIR", os.path.join(HERE, "..", "assets", "renders"))
FRAMES = os.environ.get("DECK_FRAMES_DIR", os.path.join(HERE, "_frames"))
N = int(os.environ.get("DECK_LOOP_FRAMES", "96"))   # frames per loop
FPS = 24
TAU = math.tau


def lin(h):
    """sRGB hex string to linear RGBA."""
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return (*c, 1.0)


NAVY, PANEL, PANEL2 = "#001423", "#04202f", "#0a3347"
TEAL, AMBER, VIOLET, GREEN, BLUE = "#00f2d4", "#ffac00", "#b39dff", "#7ee081", "#7fc8ff"


def interp(kind):
    """Interpolation for keyframes inserted from now on (LINEAR for steady travel, BEZIER for easing)."""
    try:
        bpy.context.preferences.edit.keyframe_new_interpolation_type = kind
    except Exception:
        pass


class Ctx:
    def __init__(self, name, scene=None):
        self.sc = scene or bpy.data.scenes.new(name)
        self.col = self.sc.collection
        self.mats = {}
        self.n = N
        self.sc.frame_start, self.sc.frame_end = 1, N
        self.sc.render.fps = FPS

    # ------------------------------------------------------------------ building
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

    def column(self, name, xy, size_xy, height, mat, bevel=0.02):
        """A box whose origin sits on its base, so scaling Z grows it upward."""
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=Vector((size_xy, size_xy, height)), verts=bm.verts)
        bmesh.ops.translate(bm, vec=Vector((0, 0, height / 2)), verts=bm.verts)
        return self.mesh_from(name, bm, mat, (xy[0], xy[1], 0), bevel)

    def cyl(self, name, loc, r, h, mat, seg=48):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
        return self.mesh_from(name, bm, mat, loc, smooth=True)

    def sphere(self, name, loc, r, mat, seg=32):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=r)
        return self.mesh_from(name, bm, mat, loc, smooth=True)

    def tube(self, name, pts, mat, r=0.03):
        """Bevelled curve through pts."""
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth, cu.bevel_resolution = r, 3
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(pts) - 1)
        for bp, p in zip(sp.bezier_points, pts):
            bp.co = p
            bp.handle_left_type = bp.handle_right_type = "AUTO"
        return self.link(name, cu, mat)

    def point(self, loc, energy, color=TEAL, radius=0.3):
        li = bpy.data.lights.new("p", "POINT")
        li.energy, li.color, li.shadow_soft_size = energy, lin(color)[:3], radius
        return self.link("p", li, loc=loc)

    def area(self, loc, energy, size=6, color="#ffffff", aim=(0, 0, 0)):
        li = bpy.data.lights.new("a", "AREA")
        li.energy, li.size, li.color = energy, size, lin(color)[:3]
        o = self.link("a", li, loc=loc)
        o.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return o

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

    # ------------------------------------------------------------------ animation
    def frame(self, t):
        """Frame number for loop time t in 0..1 (1 is the first frame, N+1 wraps back to it)."""
        return 1 + t * self.n

    def _emit(self, mat):
        b = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        return b.inputs["Emission Strength"]

    def breathe(self, mat, base, amp, cycles=1, phase=0.0):
        """Emission strength follows a sine, `cycles` whole waves per loop."""
        interp("BEZIER")
        s, k_n = self._emit(mat), 12 * cycles
        for k in range(k_n + 1):
            s.default_value = max(0.0, base + amp * math.sin(TAU * (cycles * k / k_n + phase)))
            s.keyframe_insert("default_value", frame=self.frame(k / k_n))

    def blink(self, mat, hi, lo, seed, toggles=6):
        """Emission flips between hi and lo at random frames, like a status LED."""
        interp("BEZIER")
        rnd = random.Random(seed)
        s = self._emit(mat)
        marks = sorted(rnd.sample(range(3, self.n - 2), toggles))
        on = rnd.random() < 0.5
        first = on
        v = lambda state: hi if state else lo
        s.default_value = v(on)
        s.keyframe_insert("default_value", frame=1)
        for f in marks:
            s.default_value = v(on)
            s.keyframe_insert("default_value", frame=f - 1)
            on = not on
            s.default_value = v(on)
            s.keyframe_insert("default_value", frame=f)
        s.default_value = v(on)
        s.keyframe_insert("default_value", frame=self.n)
        s.default_value = v(first)
        s.keyframe_insert("default_value", frame=self.n + 1)

    def orbit(self, obj, base, ax, ay, az, phase=0.0):
        """Offset an object's location by sines. Whole cycles only, so it loops."""
        interp("BEZIER")
        b = Vector(base)
        for k in range(13):
            t = k / 12
            obj.location = b + Vector((ax * math.sin(TAU * t + phase),
                                       ay * math.sin(TAU * t + phase + math.pi / 2),
                                       az * math.sin(2 * TAU * t + phase)))
            obj.keyframe_insert("location", frame=self.frame(t))

    def bob(self, obj, base, amp, phase=0.0, cycles=1):
        interp("BEZIER")
        b = Vector(base)
        for k in range(12 * cycles + 1):
            t = k / (12 * cycles)
            obj.location = b + Vector((0, 0, amp * math.sin(TAU * (cycles * t + phase))))
            obj.keyframe_insert("location", index=2, frame=self.frame(t))

    def spin(self, obj, axis, turn):
        """Steady rotation of `turn` radians per loop. Use a symmetry angle (90 degrees for a square
        prism) so the end frame matches the start."""
        interp("LINEAR")
        r = list(obj.rotation_euler)
        r0 = r[axis]
        r[axis] = r0
        obj.rotation_euler = r
        obj.keyframe_insert("rotation_euler", index=axis, frame=1)
        r[axis] = r0 + turn
        obj.rotation_euler = r
        obj.keyframe_insert("rotation_euler", index=axis, frame=self.n + 1)
        interp("BEZIER")

    def swell(self, obj, base, amp, phase=0.0, cycles=1):
        """Uniform scale pulses."""
        interp("BEZIER")
        for k in range(12 * cycles + 1):
            t = k / (12 * cycles)
            s = base + amp * math.sin(TAU * (cycles * t + phase))
            obj.scale = (s, s, s)
            obj.keyframe_insert("scale", frame=self.frame(t))

    def wave_height(self, obj, amp, phase):
        """Z scale rises and falls, for columns that grow from their base."""
        interp("BEZIER")
        for k in range(13):
            t = k / 12
            obj.scale = (1, 1, 1 + amp * math.sin(TAU * (t - phase)))
            obj.keyframe_insert("scale", index=2, frame=self.frame(t))

    def pulse(self, path_obj, start, dur, mat, r=0.06, reverse=False):
        """A bead of light that travels along a curve once per loop. start and dur are fractions of
        the loop, with start + dur <= 1 so the bead is gone before the seam."""
        start = min(start, 1.0 - dur)
        path_obj.data.use_path = True
        o = self.sphere("pulse", (0, 0, 0), r, mat, 12)
        c = o.constraints.new("FOLLOW_PATH")
        c.target, c.use_fixed_location, c.use_curve_follow = path_obj, True, False
        f0 = max(2, round(self.frame(start)))
        f1 = min(self.n, round(self.frame(start + dur)))
        a, b = (1.0, 0.0) if reverse else (0.0, 1.0)
        interp("LINEAR")
        c.offset_factor = a
        c.keyframe_insert("offset_factor", frame=f0)
        c.offset_factor = b
        c.keyframe_insert("offset_factor", frame=f1)
        interp("BEZIER")
        for f, s in ((1, 0), (f0 - 1, 0), (f0, 1), (f1 - 1, 1), (f1, 0), (self.n + 1, 0)):
            o.scale = (s, s, s)
            o.keyframe_insert("scale", frame=f)
        return o


# --------------------------------------------------------------------------- render plumbing

SIZE = {"hero": (1920, 1080)}
DEFAULT_SIZE = (1280, 720)


def setup_render(ctx, name, samples, quick):
    sc, r = ctx.sc, ctx.sc.render
    w, h = SIZE.get(name, DEFAULT_SIZE)
    if quick:
        w, h = w // 3, h // 3
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
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
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGB"
    r.image_settings.compression = 15
    os.makedirs(FRAMES, exist_ok=True)
    r.filepath = os.path.join(FRAMES, name + "_")


def glow(ctx):
    """Bloom-style glow via the compositor. Best effort: the API differs by version."""
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
    """Data centre aisle: racks with blinking LEDs, light pulses travelling the overhead cabling."""
    rnd = random.Random(7)
    ctx.world(NAVY, 0.4)
    ctx.floor(120)
    body = ctx.mat("body", PANEL2, rough=0.5, metal=0.5)
    dark = ctx.mat("dark", "#010a12", rough=0.6)

    def led(color, v):
        key = f"led{color}{v}"
        fresh = key not in ctx.mats
        m = ctx.mat(key, color, 6 if color == TEAL else 5)
        if fresh and v == 3:
            ctx.blink(m, 6, 0.3, seed=int(color[1:], 16) % 997 + 3, toggles=6)
        elif fresh and v == 4:
            ctx.blink(m, 6, 0.2, seed=int(color[1:], 16) % 997 + 4, toggles=14)
        elif fresh and v == 5:
            ctx.breathe(m, 3.2, 2.8, cycles=2, phase=(int(color[1:], 16) % 7) / 7)
        return m

    for side in (-1, 1):
        y = side * 1.9
        for i in range(12):
            x = i * 1.25
            ctx.box(f"rack{side}{i}", (x, y, 1.15), (1.0, 1.0, 2.3), body, 0.02)
            ctx.box(f"door{side}{i}", (x, y - side * 0.48, 1.15), (0.86, 0.04, 2.1), dark, 0.01)
            for u in range(16):
                if rnd.random() < 0.82:
                    color = TEAL if rnd.random() < 0.7 else rnd.choice([AMBER, VIOLET, GREEN])
                    v = rnd.choice([0, 0, 0, 0, 3, 4, 5])
                    w = rnd.choice((0.5, 0.6, 0.7))
                    ctx.box(f"u{side}{i}{u}", (x - 0.12, y - side * 0.51, 0.3 + u * 0.12),
                            (w, 0.02, 0.05), led(color, v), 0.005)

    tray = ctx.mat("tray", TEAL, 7)
    spark = ctx.mat("spark", "#d8fffa", 16)
    spark_a = ctx.mat("spark_a", AMBER, 14)
    for y in (-0.7, 0.7):
        t = ctx.tube(f"tray{y}", [(2.5, y, 2.85), (9, y, 2.85), (22, y, 2.85)], tray, 0.035)
        for s in (0.02, 0.34, 0.6):
            ctx.pulse(t, s + (0.05 if y > 0 else 0), 0.38, spark, 0.07)
    for i in range(0, 12, 2):
        x = i * 1.25
        for side in (-1, 1):
            col = [TEAL, VIOLET, AMBER][i % 3]
            d = ctx.tube(f"drop{i}{side}", [(x, side * 0.7, 2.9), (x, side * 1.3, 2.7), (x, side * 1.9, 2.35)],
                         ctx.mat("c" + str(i % 3), col, 6), 0.025)
            ctx.pulse(d, 0.06 + ((i * 7) % 50) / 100, 0.3, spark_a if col == AMBER else spark, 0.055)

    cam = ctx.camera((-6.0, 0.0, 1.5), (6.0, 0.0, 1.5), 22)
    ctx.orbit(cam, (-6.0, 0.0, 1.5), 0.45, 0.14, 0.04)
    ctx.area((2, 0, 4.5), 700, 5, TEAL, (6, 0, 0))
    ctx.point((0, 0, 2.5), 400, VIOLET, 1)
    return "hero"


def scene_datamodel(ctx):
    """Region > site > location > rack > device as five floating slabs, with a wave of light climbing them."""
    ctx.world(NAVY, 0.3)
    ctx.floor(80, z=-0.05)
    glass = ctx.mat("glass", PANEL2, rough=0.15, metal=0.3)
    tiers = [(7.0, TEAL), (5.6, VIOLET), (4.2, AMBER), (2.9, BLUE), (1.7, GREEN)]
    rnd = random.Random(3)
    spark = ctx.mat("spark", "#d8fffa", 16)
    beam_mat = ctx.mat("beam", TEAL, 8)
    for i, (s, col) in enumerate(tiers):
        z = i * 1.35
        ctx.box(f"slab{i}", (0, 0, z), (s, s, 0.14), glass, 0.04)
        em = ctx.mat("e" + col, col, 7)
        ctx.box(f"edge{i}", (0, 0, z - 0.09), (s + 0.04, s + 0.04, 0.03), em, 0.01)
        ctx.breathe(em, 6.5, 4.5, cycles=1, phase=-i / 5)        # the wave climbs the tiers
        for k in range(i + 2):
            a = rnd.uniform(0, 6.28)
            rr = (s / 2 - 0.5) * rnd.uniform(0.2, 1.0) if i < 4 else 0
            nd = ctx.box(f"n{i}{k}", (math.cos(a) * rr, math.sin(a) * rr, z + 0.3),
                         (0.35, 0.35, 0.35 + (i % 2) * 0.1), ctx.mat("n" + col, col, 3, rough=0.3), 0.04)
            ctx.bob(nd, nd.location, 0.07, phase=rnd.random())
            ctx.spin(nd, 2, math.pi / 2)
        ctx.breathe(ctx.mat("n" + col, col, 3), 3.0, 1.6, cycles=1, phase=-i / 5)
        if i:
            for dx, dy in ((1, 1), (-1, 1), (1, -1), (-1, -1)):
                p = tiers[i][0] / 2 - 0.15
                b = ctx.tube(f"beam{i}{dx}{dy}", [(dx * p, dy * p, z - 1.2), (dx * p, dy * p, z)], beam_mat, 0.018)
                ctx.pulse(b, 0.05 + 0.13 * i + (0.02 if dx > 0 else 0), 0.22, spark, 0.06)
    cam = ctx.camera((14, -14, 8.5), (0, 0, 2.7), 38)
    ctx.orbit(cam, (14, -14, 8.5), 0.5, 0.5, 0.12)
    ctx.area((5, -5, 10), 900, 8, "#ffffff", (0, 0, 2))
    ctx.point((0, 0, 7), 600, TEAL, 1)
    return "datamodel"


def scene_containers(ctx):
    """Four services on a plinth, with requests flowing between them and status lights blinking."""
    ctx.world(NAVY, 0.3)
    ctx.floor(80, z=-0.3)
    ctx.box("plinth", (0, 0, -0.1), (11, 7, 0.3), ctx.mat("plinth", PANEL2, rough=0.2, metal=0.4), 0.06)
    pe = ctx.mat("pe", TEAL, 7)
    ctx.box("plinth_edge", (0, 0, -0.27), (11.1, 7.1, 0.04), pe, 0.01)
    ctx.breathe(pe, 6, 3, cycles=1)

    nbm = ctx.mat("nbx", TEAL, 0.25, rough=0.25)
    ctx.box("netbox", (0, 0, 1.1), (2.6, 2.6, 2.2), nbm, 0.12)
    ctx.breathe(nbm, 0.35, 0.18, cycles=1)
    nbr = ctx.mat("nbxr", TEAL, 9)
    ctx.box("nbx_ring", (0, 0, 2.3), (2.9, 2.9, 0.08), nbr, 0.01)
    ctx.breathe(nbr, 8, 4, cycles=2)

    ctx.cyl("pg", (-3.6, -1.6, 0.9), 1.0, 1.8, ctx.mat("pg", BLUE, 0.2, rough=0.25))
    for k in range(3):
        rm = ctx.mat(f"pgr{k}", BLUE, 8)
        ctx.cyl(f"pgr{k}", (-3.6, -1.6, 0.35 + k * 0.6), 1.04, 0.05, rm, 48)
        ctx.breathe(rm, 7, 5, cycles=1, phase=-k / 3)             # discs light in sequence

    cm = ctx.mat("cache", AMBER, 0.25, rough=0.25)
    ctx.box("cache", (3.6, -1.6, 0.6), (1.7, 1.7, 1.2), cm, 0.1)
    cr = ctx.mat("cr", AMBER, 9)
    ctx.box("cache_ring", (3.6, -1.6, 0.95), (1.78, 1.78, 0.05), cr, 0.01)
    ctx.breathe(cr, 8, 4, cycles=3, phase=0.2)

    wm = ctx.mat("worker", VIOLET, 0.2, rough=0.25)
    ctx.box("worker", (0, 2.4, 0.7), (2.2, 1.5, 1.4), wm, 0.1)
    wr = ctx.mat("wr", VIOLET, 9)
    ctx.box("worker_ring", (0, 2.4, 1.0), (2.28, 1.58, 0.05), wr, 0.01)
    ctx.breathe(wr, 8, 4, cycles=2, phase=0.5)

    # status lights, one per service, each on its own rhythm
    for k, (loc, col) in enumerate([((-2.6, -0.6, 1.95), BLUE), ((2.9, -0.8, 1.35), AMBER),
                                    ((1.15, 2.4, 1.55), VIOLET), ((1.4, -1.4, 2.0), TEAL)]):
        lm = ctx.mat(f"stat{k}", col, 9)
        ctx.sphere(f"stat{k}", loc, 0.09, lm, 12)
        ctx.blink(lm, 10, 1.0, seed=40 + k, toggles=6 + 2 * k)

    link = ctx.mat("link", TEAL, 8)
    spark = ctx.mat("spark", "#d8fffa", 16)
    spark_a = ctx.mat("spark_a", AMBER, 14)
    l1 = ctx.tube("l1", [(-2.6, -1.4, 0.9), (-1.8, -1.0, 1.0), (-1.3, -0.6, 1.0)], link, 0.05)
    l2 = ctx.tube("l2", [(2.8, -1.4, 0.7), (2.1, -1.0, 0.9), (1.3, -0.6, 1.0)], link, 0.05)
    l3 = ctx.tube("l3", [(0, 1.5, 0.9), (0, 1.0, 1.0), (0, 1.3, 1.0)], link, 0.05)
    for path, a, b in ((l1, 0.04, 0.2), (l1, 0.52, 0.2), (l2, 0.2, 0.2), (l2, 0.68, 0.2), (l3, 0.1, 0.2), (l3, 0.6, 0.2)):
        ctx.pulse(path, a, b, spark_a if path is l2 else spark, 0.1, reverse=a > 0.45)

    cam = ctx.camera((14, -14, 9.5), (0, 0, 0.8), 40)
    ctx.orbit(cam, (14, -14, 9.5), 0.5, 0.5, 0.1)
    ctx.area((4, -6, 9), 800, 7, "#ffffff", (0, 0, 1))
    ctx.point((0, 0, 4), 500, TEAL, 1)
    return "containers"


def scene_ipam(ctx):
    """An address plan as a city: columns breathe in a travelling wave and a light sweeps round it."""
    rnd = random.Random(11)
    ctx.world(NAVY, 0.3)
    ctx.floor(80, z=-0.02)
    n = 16
    lo = ctx.mat("lo", "#0d4a63", 0.08, rough=0.3)
    mid = ctx.mat("mid", TEAL, 0.45, rough=0.3)
    hi = ctx.mat("hi", AMBER, 0.6, rough=0.3)
    ctx.breathe(mid, 0.55, 0.25, cycles=1)
    ctx.breathe(hi, 0.8, 0.35, cycles=1, phase=0.5)
    for i in range(n):
        for j in range(n):
            zone = (i // 4 + j // 4) % 3
            v = min(1.0, max(0.05, rnd.random() * 0.8 + 0.1 * zone))
            h = 0.12 + v * 2.2 * (0.4 + 0.6 * (i / n))
            m = lo if v < 0.4 else mid if v < 0.8 else hi
            col = ctx.column(f"t{i}_{j}", ((i - n / 2) * 0.62, (j - n / 2) * 0.62), 0.52, h, m, 0.02)
            ctx.wave_height(col, 0.22, (i + j) / (2 * n))        # a diagonal ripple across the grid
    cam = ctx.camera((13, -13, 10), (0, 0, 0.4), 40)
    ctx.orbit(cam, (13, -13, 10), 0.4, 0.4, 0.1)
    ctx.area((5, -3, 9), 500, 7, "#ffffff", (0, 0, 0))
    sweep = ctx.point((6, 0, 3.2), 700, TEAL, 0.6)
    interp("BEZIER")
    for k in range(13):                                         # a light circles the grid once per loop
        t = k / 12
        sweep.location = (7 * math.cos(TAU * t), 7 * math.sin(TAU * t), 3.2)
        sweep.keyframe_insert("location", frame=ctx.frame(t))
    ctx.point((0, 0, 5), 300, TEAL, 1)
    return "ipam"


def scene_globe(ctx):
    """Sites around the world, with traffic running along the circuits and beacons breathing."""
    ctx.world(NAVY, 0.3)
    R = 2.2
    rig = bpy.data.objects.new("rig", None)
    ctx.col.objects.link(rig)
    rig.rotation_euler = (math.radians(-20), 0, math.radians(-95))
    parts = [ctx.sphere("core", (0, 0, 0), R * 0.985, ctx.mat("core", "#031a28", rough=0.4))]
    wm = ctx.mat("wire", TEAL, 2.5)
    wire = ctx.sphere("wire", (0, 0, 0), R, wm, 28)
    md = wire.modifiers.new("wf", "WIREFRAME")
    md.thickness, md.use_replace = 0.006, True
    parts.append(wire)
    ctx.breathe(wm, 2.6, 0.9, cycles=1)

    def ll(lat, lon, r=R):
        la, lo = math.radians(lat), math.radians(lon)
        return (r * math.cos(la) * math.cos(lo), r * math.cos(la) * math.sin(lo), r * math.sin(la))

    sites = [(51.5, -0.1), (40.7, -74), (37.8, -122.4), (-23.5, -46.6), (1.35, 103.8), (35.7, 139.7),
             (-33.9, 151.2), (28.6, 77.2), (-26.2, 28), (52.5, 13.4), (25.2, 55.3), (55.7, 37.6)]
    beacon = [ctx.mat("b" + c, c, 9) for c in (TEAL, AMBER, VIOLET)]
    for k, (la, lo) in enumerate(sites):
        b = ctx.sphere(f"s{k}", ll(la, lo, R * 1.01), 0.055, beacon[k % 3], 12)
        ctx.swell(b, 1.0, 0.45, phase=k / len(sites))
        parts += [b, ctx.tube(f"sp{k}", [ll(la, lo, R), ll(la, lo, R * 1.12)], beacon[k % 3], 0.012)]
    link = ctx.mat("arc", AMBER, 6)
    spark = ctx.mat("spark", "#fff3d0", 16)
    arcs = []
    for idx, (a, b) in enumerate([(0, 1), (1, 2), (0, 9), (9, 10), (10, 7), (7, 4), (4, 5), (5, 2), (4, 6), (0, 8),
                                  (1, 3), (11, 5), (9, 11)]):
        pa, pb = Vector(ll(*sites[a], R)).normalized(), Vector(ll(*sites[b], R)).normalized()
        ang = pa.angle(pb)
        pts = []
        for t in range(0, 21):
            f = t / 20
            v = (pa * math.sin((1 - f) * ang) + pb * math.sin(f * ang)) / math.sin(ang)
            pts.append(v.normalized() * (R * 1.01 + math.sin(f * math.pi) * R * 0.18 * (ang / math.pi + 0.3)))
        arc = ctx.tube(f"arc{a}{b}", pts, link, 0.014)
        parts.append(arc)
        arcs.append((arc, idx))
    for p in parts:
        p.parent = rig
    for arc, idx in arcs:                                       # traffic, unparented so it follows the moving arc
        ctx.pulse(arc, 0.04 + (idx * 0.07) % 0.55, 0.38, spark, 0.045, reverse=idx % 2 == 1)

    interp("BEZIER")                                            # the whole globe rocks gently
    for k in range(13):
        t = k / 12
        rig.rotation_euler = (math.radians(-20) + math.radians(3) * math.sin(TAU * t + math.pi / 2), 0,
                              math.radians(-95) + math.radians(11) * math.sin(TAU * t))
        rig.keyframe_insert("rotation_euler", frame=ctx.frame(t))
    ctx.camera((2.0, -11.5, 3.0), (0, 0, 0), 45)
    ctx.area((4, -5, 5), 500, 5, "#ffffff", (0, 0, 0))
    ctx.point((-3, -4, 2), 300, VIOLET, 1)
    return "globe"


def scene_hub(ctx):
    """NetBox in the middle: the core turns, satellites bob and spin, data pulses run along every spoke."""
    ctx.world(NAVY, 0.3)
    ctx.floor(80, z=-0.35)
    ring = bpy.data.meshes.new("ring")
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=False, radius=4.6, segments=96)
    bm.to_mesh(ring)
    bm.free()
    rm = ctx.mat("ringm", TEAL, 5)
    ro = ctx.link("ring", ring, rm, loc=(0, 0, -0.3))
    sk = ro.modifiers.new("sk", "SCREW")
    sk.angle, sk.steps, sk.render_steps, sk.screw_offset = 0, 1, 1, 0
    ctx.breathe(rm, 5, 3, cycles=1)
    ctx.cyl("base", (0, 0, -0.2), 1.9, 0.12, ctx.mat("base", PANEL2, rough=0.2, metal=0.4))

    cm = ctx.mat("core", TEAL, 0.6, rough=0.2)
    core = ctx.box("core", (0, 0, 1.0), (1.8, 1.8, 1.8), cm, 0.1)
    cim = ctx.mat("coreI", "#ffffff", 4)
    inner = ctx.box("core_in", (0, 0, 1.0), (1.2, 1.2, 1.2), cim, 0.05)
    ctx.spin(core, 2, math.pi / 2)
    ctx.spin(inner, 2, -math.pi / 2)
    ctx.breathe(cm, 0.7, 0.3, cycles=1)
    ctx.breathe(cim, 4, 2.2, cycles=2)

    cols = [TEAL, AMBER, VIOLET, BLUE, GREEN, AMBER, VIOLET, BLUE]
    shapes = ["sphere", "box", "cyl", "box", "sphere", "cyl", "box", "sphere"]
    spark = ctx.mat("spark", "#d8fffa", 16)
    for k in range(8):
        a = k / 8 * math.tau + 0.3
        p = (math.cos(a) * 4.6, math.sin(a) * 4.6, 0.55)
        m = ctx.mat(f"sat{k}", cols[k], 1.2, rough=0.25)
        if shapes[k] == "sphere":
            o = ctx.sphere(f"sat{k}", p, 0.6, m)
        elif shapes[k] == "box":
            o = ctx.box(f"sat{k}", p, (1.0, 1.0, 1.0), m, 0.08)
            ctx.spin(o, 2, math.pi / 2)
        else:
            o = ctx.cyl(f"sat{k}", p, 0.55, 1.1, m)
        ctx.bob(o, p, 0.14, phase=k / 8)
        ctx.breathe(m, 1.2, 0.5, cycles=1, phase=-k / 8)
        sp = ctx.tube(f"sp{k}", [(math.cos(a) * 1.0, math.sin(a) * 1.0, 1.0), (math.cos(a) * 2.8, math.sin(a) * 2.8, 1.5),
                                 (math.cos(a) * 4.0, math.sin(a) * 4.0, 0.6)], ctx.mat("sl" + cols[k], cols[k], 8), 0.035)
        start = (k * 0.11) % 0.5
        ctx.pulse(sp, start, 0.3, spark, 0.09)
        ctx.pulse(sp, start + 0.5 - 0.0, 0.3, spark, 0.07, reverse=True)
    cam = ctx.camera((12, -12, 8.5), (0, 0, 0.7), 40)
    ctx.orbit(cam, (12, -12, 8.5), 0.5, 0.5, 0.1)
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


# --------------------------------------------------------------------------- driver

def encode(name, crf=26):
    """Frame sequence to an H.264 loop, plus the first frame as a JPEG poster."""
    ff = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    seq = os.path.join(FRAMES, name + "_%04d.png")
    mp4 = os.path.join(OUT, name + ".mp4")
    jpg = os.path.join(OUT, name + ".jpg")
    subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", seq, "-c:v", "libx264", "-preset", "slow",
                    "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", mp4], check=True)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", os.path.join(FRAMES, name + "_0001.png"), "-frames:v", "1",
                    "-q:v", "3", jpg], check=True)
    return mp4


def render_one(name, samples=64, quick=False, keep=False):
    """Build one scene into the context scene, render the loop, encode it."""
    for f in os.listdir(FRAMES) if os.path.isdir(FRAMES) else []:
        if f.startswith(name + "_"):
            os.remove(os.path.join(FRAMES, f))
    ctx = Ctx(f"deck_{name}", bpy.context.scene)
    for o in list(ctx.col.objects):
        bpy.data.objects.remove(o)
    SCENES[name](ctx)
    setup_render(ctx, name, 16 if quick else samples, quick)
    glow(ctx)
    bpy.ops.render.render(animation=True)
    os.makedirs(OUT, exist_ok=True)
    mp4 = encode(name)
    if not keep:
        for f in os.listdir(FRAMES):
            if f.startswith(name + "_"):
                os.remove(os.path.join(FRAMES, f))
    return mp4


def render_scenes(names, samples=64, quick=False, keep=False):
    """Each scene starts from an empty factory file, so nothing leaks between renders."""
    done = []
    for n in names:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        done.append(render_one(n, samples, quick, keep))
    return done


if __name__ == "__main__":
    # blender -b -P blender/scenes.py -- [--quick] [--keep] [scene ...]
    # Headless on purpose: the render operator draws the window's active scene, so running it
    # inside a live Blender session renders whatever is open instead of the scene built here.
    import sys
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = [a for a in argv if not a.startswith("--")] or list(SCENES)
    print("RENDERED", render_scenes(names, quick="--quick" in argv, keep="--keep" in argv))
