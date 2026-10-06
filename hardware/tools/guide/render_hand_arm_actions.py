#!/usr/bin/env python3
"""Render guide hand, arm, strap and stand action images from checked, accepted CAD meshes.

Printed surfaces are unchanged source triangles, rigidly posed or clipped for
visibility. Magnets use catalog dimensions. The drilled horn is nominal drawing
geometry (measured 23.55 mm OD; illustrative 1.6 mm thickness), not vendor CAD.
The regular scene-review/source gates remain mandatory. Review scratch results
before --write; this command never changes CAD, print inputs or source locks.
"""

import argparse
import copy
import importlib
import json
import math
import os
from pathlib import Path
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import trimesh

from render_models import ROOT, SRC, checked_source, digest

BG = (243, 247, 250)
INK = (34, 56, 78)
ARROW = (169, 85, 34)
STEEL = (190, 199, 209)
ACTION_PATHS = {
    "assets/r19/wrist-socket.png",
    "assets/r19/wrist-peg.png",
    "assets/r19/wrist-round.png",
    "assets/community/arm-horn-left.png",
    "assets/community/arm-horn-right.png",
    "assets/r22/head-straps-installed.png",
    "assets/community/stand-head-saddle-actions.png",
}
MAGNET_DIAMETER = 25.4 * 3 / 16
MAGNET_THICKNESS = 25.4 / 16
WRIST_ORIGIN = np.array([48.14, 0, 56.0])
WRIST_AXIS = np.array([0, -math.sin(math.radians(20)), -math.cos(math.radians(20))])
WRIST_BASIS = np.column_stack(
    (
        [1, 0, 0],
        [0, -math.cos(math.radians(20)), math.sin(math.radians(20))],
        WRIST_AXIS,
    )
)


def row(mesh, name, color):
    return dict(
        id=name,
        root=name,
        occ=0,
        v=mesh.vertices.copy(),
        f=mesh.faces.copy(),
        source={},
        guide_color=color,
        flat_shading=True,
    )


def shifted(parts, offset):
    result = []
    for item in parts:
        m = dict(item, v=item["v"] + offset)
        m.pop("normals", None)
        m.pop("corner_normals", None)
        result.append(m)
    return result


def wrist_local(parts):
    result = []
    for item in parts:
        m = dict(item, v=(item["v"] - WRIST_ORIGIN) @ WRIST_BASIS - [0, 0, 18.9])
        m.pop("normals", None)
        m.pop("corner_normals", None)
        result.append(m)
    return result


def circle_witness(parts, axis, plane, center, radius):
    points = np.concatenate([m["v"] for m in parts])
    other = [i for i in range(3) if i != axis]
    mask = (abs(points[:, axis] - plane) < 0.002) & (
        abs(np.linalg.norm(points[:, other] - center, axis=1) - radius) < 0.002
    )
    if np.count_nonzero(mask) < 20:
        raise ValueError(
            f"Accepted feature changed: axis {axis}, plane {plane}, radius {radius}"
        )
    return int(np.count_nonzero(mask))


def disc(center):
    mesh = trimesh.creation.cylinder(MAGNET_DIAMETER / 2, MAGNET_THICKNESS, sections=96)
    mesh.apply_translation(center)
    return row(mesh, "Disc magnet", STEEL)


def horn_mesh():
    """Analytic circular boundaries extruded along X; three real open bores.

    Horizontal strips split at each circle's extrema, so the drilled pair and
    central opening remain holes rather than painted circles over a solid disk.
    """
    outer = 11.775
    holes = [(-9.0, 1.05), (0.0, 3.0), (9.0, 1.05)]
    levels = sorted(
        set(np.linspace(-outer, outer, 240).tolist() + [-3.0, -1.05, 0.0, 1.05, 3.0])
    )
    verts, faces = [], []

    def quad(points):
        i = len(verts)
        verts.extend(points)
        faces.extend([[i, i + 1, i + 2], [i, i + 2, i + 3]])

    for low, high in zip(levels, levels[1:]):
        middle = (low + high) / 2
        active = [(c, r) for c, r in holes if abs(middle) < r]

        def endpoints(z):
            edges = [-math.sqrt(max(0.0, outer * outer - z * z))]
            for center, radius in active:
                reach = math.sqrt(max(0.0, radius * radius - z * z))
                edges.extend([center - reach, center + reach])
            edges.append(math.sqrt(max(0.0, outer * outer - z * z)))
            return edges

        a, b = endpoints(low), endpoints(high)
        for i in range(0, len(a), 2):
            for x, reverse in [(-0.8, True), (0.8, False)]:
                points = [
                    [x, a[i], low],
                    [x, a[i + 1], low],
                    [x, b[i + 1], high],
                    [x, b[i], high],
                ]
                quad(points[::-1] if reverse else points)
            for j in [i, i + 1]:
                quad(
                    [
                        [-0.8, a[j], low],
                        [0.8, a[j], low],
                        [0.8, b[j], high],
                        [-0.8, b[j], high],
                    ]
                )
    mesh = trimesh.Trimesh(verts, faces, process=True)
    mesh.remove_unreferenced_vertices()
    return mesh


class Painter:
    def __init__(self, render, output, font):
        self.render, self.output, self.font = render, output, font
        self.index = 0

    def panel(
        self,
        parts,
        camera,
        title,
        *,
        labels=(),
        arrows=(),
        marks=(),
        footer="",
        size=(800, 720),
    ):
        name = f"hand-arm-action-{self.index:02}"
        self.index += 1
        self.render.meshes = parts
        vertices = np.concatenate([m["v"] for m in parts])
        margin = 74 if size[1] <= 500 else 96
        self.render.render(
            name,
            dict(
                select=["all"],
                camera=camera,
                clean=True,
                size=list(size),
                margin=margin,
            ),
        )
        im = Image.open(self.output / (name + ".png")).convert("RGB")
        draw = ImageDraw.Draw(im)
        z = np.asarray(camera, float)
        z /= np.linalg.norm(z)
        x = np.cross([0, 0, 1], z)
        x /= np.linalg.norm(x)
        rotation = np.array([x, np.cross(z, x), z]).T
        projected_vertices = vertices @ rotation
        lo, high = projected_vertices[:, :2].min(0), projected_vertices[:, :2].max(0)
        scale = min(
            (size[0] - 2 * margin) / max(high[0] - lo[0], 1),
            (size[1] - 2 * margin) / max(high[1] - lo[1], 1),
        )
        center = (lo + high) / 2

        def project(point):
            p = np.array(point) @ rotation
            return np.array(
                [
                    (p[0] - center[0]) * scale + size[0] / 2,
                    size[1] / 2 - (p[1] - center[1]) * scale,
                ]
            )

        for start, end in arrows:
            a, b = project(start), project(end)
            delta = b - a
            length = np.linalg.norm(delta)
            if length < 1:
                continue
            unit = delta / length
            normal = np.array([-unit[1], unit[0]])
            draw.line([tuple(a), tuple(b)], fill="white", width=12)
            draw.line([tuple(a), tuple(b)], fill=ARROW, width=5)
            draw.polygon(
                [
                    tuple(b),
                    tuple(b - unit * 17 + normal * 8),
                    tuple(b - unit * 17 - normal * 8),
                ],
                fill=ARROW,
            )
        for text, point in marks:
            xy = project(point)
            draw.text(
                tuple(xy),
                text,
                anchor="mm",
                font=ImageFont.truetype(str(self.font), 24),
                fill=INK,
            )
        for text, target, pos in labels:
            if target is not None:
                draw.line([pos, tuple(project(target))], fill=(80, 101, 119), width=2)
            draw.text(
                pos,
                text,
                font=ImageFont.truetype(str(self.font), 30),
                fill=INK,
                stroke_width=4,
                stroke_fill=BG,
            )
        # The title is a part label, not a heading or an instruction.
        if title:
            draw.text(
                (24, 22), title, font=ImageFont.truetype(str(self.font), 34), fill=INK
            )
        if footer:
            draw.text(
                (24, size[1] - 48),
                footer,
                font=ImageFont.truetype(str(self.font), 25),
                fill=INK,
            )
        return im

    def combine(self, images, filename):
        canvas = Image.new(
            "RGB", (max(im.width for im in images), sum(im.height for im in images)), BG
        )
        y = 0
        for im in images:
            canvas.paste(im, (0, y))
            y += im.height
        canvas.save(self.output / filename, optimize=True)
        return self.output / filename


def make_images(render, output, font):
    from guide_closeups import clipped
    from guide_fasteners import hex_nut, screw

    original = render.meshes

    def parts(pid):
        return copy.deepcopy([m for m in original if m["id"] == pid])

    paint = Painter(render, output, font)
    witnesses = {}
    forearm, hand = wrist_local(parts("AR02")), wrist_local(parts("AR03"))
    for item in forearm + hand:
        item["guide_color"] = (83, 112, 174)
    if not np.isclose(np.linalg.det(WRIST_BASIS), 1):
        raise ValueError("Wrist display rotation must preserve handedness")
    for name, meshes, floor in [("forearm", forearm, -1.75), ("hand", hand, 1.77)]:
        witnesses[name + "-mouth"] = circle_witness(meshes, 2, 0, [0, 0], 2.5)
        witnesses[name + "-floor"] = circle_witness(meshes, 2, floor, [0, 0], 2.5)
    outputs = {}
    for pid, mesh, sign, floor, filename, title in [
        ("AR02", forearm, 1, -1.75, "wrist-socket.png", "AR02 · A magnet"),
        ("AR03", hand, -1, 1.77, "wrist-peg.png", "AR03 · B magnet"),
    ]:
        seated = floor + sign * MAGNET_THICKNESS / 2
        camera = [0.7, -0.65, sign * 1.3]
        entry = paint.panel(
            mesh + [disc([0, 0, sign * 10])],
            camera,
            title,
            arrows=[([0, 0, sign * 8.7], [0, 0, sign * 0.3])],
            labels=[
                ("Magnet seat", [0, 0, 0], (25, 435)),
                ("Disc", [0, 0, sign * 10], (590, 85)),
            ],
            marks=[
                ("A" if sign > 0 else "B", [0, 0, sign * (10 + MAGNET_THICKNESS / 2)])
            ],
            size=(800, 500),
        )
        cut = clipped(mesh + [disc([0, 0, seated])], [[-12, -12, -6], [0, 12, 9]])
        # Actual mesh section, with the nominal magnet seated against its floor.
        section = paint.panel(
            cut,
            [0.9, -0.65, sign * 0.5],
            "",
            labels=[
                ("Recessed face", [0, 0, floor + sign * MAGNET_THICKNESS], (25, 306))
            ],
            size=(800, 360),
        )
        outputs["assets/r19/" + filename] = paint.combine([entry, section], filename)
    separated_hand = shifted(hand, [0, 0, 13])
    forearm_magnet = disc([0, 0, -1.75 + MAGNET_THICKNESS / 2])
    hand_magnet = disc([0, 0, 13 + 1.77 - MAGNET_THICKNESS / 2])
    join = paint.panel(
        forearm + separated_hand + [forearm_magnet, hand_magnet],
        [0.9, -0.7, 0.28],
        "",
        labels=[("AR02", [3.5, 0, -8], (30, 580)), ("AR03", [3, 0, 30], (600, 140))],
        arrows=[([0, 0, 11], [0, 0, 4.5])],
        size=(800, 760),
    )
    outputs["assets/r19/wrist-round.png"] = paint.combine([join], "wrist-round.png")
    horn = horn_mesh()
    for suffix, pid, sign in [("left", "AR01", 1), ("right", "AR04", -1)]:
        arm = parts(pid)
        witnesses[pid + "-recess"] = circle_witness(
            arm, 0, sign * 41.94, [0, 90], 12.075
        )
        # Accepted shoulder bores are 3.4 × 2.4 mm obrounds, centered on
        # the drilled 18 mm horn pair. Validate their boundary independently.
        for y in [-9, 9]:
            points = np.concatenate([m["v"] for m in arm])
            delta = np.column_stack(
                (np.maximum(abs(points[:, 1] - y) - 0.5, 0), points[:, 2] - 90)
            )
            mask = (abs(points[:, 0] - sign * 41.94) < 0.002) & (
                abs(np.linalg.norm(delta, axis=1) - 1.2) < 0.002
            )
            count = int(np.count_nonzero(mask))
            if count < 20:
                raise ValueError("Accepted shoulder obround changed: " + pid)
            witnesses[pid + f"-bore-{y}"] = count
        local_arm = clipped(arm, [[-70, -18, 74], [70, 18, 108]])
        model = horn.copy()
        model.apply_translation([sign * 32, 0, 90])
        h = row(model, "Drilled horn", (226, 220, 193))
        main_parts = local_arm + [h]
        for y in [-9, 9]:
            main_parts += screw(2, 6, [sign * 20, y, 90], [sign, 0, 0])
        face = paint.panel(
            main_parts,
            [-sign * 1.7, -0.65, 0.45],
            pid,
            labels=[
                ("2 × M2 × 6", [sign * 20, -9, 90], (25, 100)),
                ("Horn", [sign * 32, 0, 98], (620, 80)),
            ],
            arrows=[([sign * 26.5, y, 90], [sign * 30.5, y, 90]) for y in [-9, 9]],
            size=(800, 480),
        )
        # The channels' flat walls are at Z=87.875/92.125. Preserve nut flats
        # in Z by rotating the generic X-axis nut 90 degrees around its bore.
        inset = clipped(
            arm, [[-55 if sign < 0 else 39, 4, 86], [-39 if sign < 0 else 55, 18, 94]]
        )
        center = np.array([sign * 44.64, 19, 90.0])
        n = hex_nut(2, [0, 0, 0], [1, 0, 0])
        rot = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])
        n["v"] = n["v"] @ rot.T + center
        insert = paint.panel(
            inset + [n],
            [-sign * 0.8, 1.4, 0.8],
            "2 × M2 nuts",
            labels=[("M2 nut", center, (450, 80))],
            arrows=[([sign * 44.64, 17.4, 90], [sign * 44.64, 9.5, 90])],
            size=(800, 380),
        )
        filename = "arm-horn-" + suffix + ".png"
        outputs["assets/community/" + filename] = paint.combine(
            [insert, face], filename
        )
    straps = []
    for pid, camera, axis, plane, pegs in [
        ("GS01", [-1, -0.15, 0.65], 0, 35.352, [[35.352, -10, 147], [35.352, 10, 147]]),
        (
            "GS02",
            [1, -0.15, 0.65],
            0,
            -35.352,
            [[-35.352, -10, 147], [-35.352, 10, 147]],
        ),
        ("GS03", [0, -1, 0.65], 1, 35.352, [[-10, 35.352, 147], [10, 35.352, 147]]),
    ]:
        mesh = parts(pid)
        for number, peg in enumerate(pegs):
            center = [peg[i] for i in range(3) if i != axis]
            witnesses[pid + f"-peg-{number}"] = circle_witness(
                mesh, axis, plane, center, 0.8
            )
        straps.append(
            paint.panel(
                mesh,
                camera,
                pid,
                labels=[
                    ("Pegs", pegs[0], (24, 245)),
                    ("", pegs[1], (260, 245)),
                ],
                size=(800, 300),
            )
        )
    outputs["assets/r22/head-straps-installed.png"] = paint.combine(
        straps, "head-straps-installed.png"
    )
    # The accepted J06 documentation envelope includes cylinders filling J05's
    # counterbores. Do not depict it as a loose manufactured pad with pegs.
    # Show the contact face from above, installed after the saddle fastening.
    # No accepted mesh is trimmed to invent a replacement foam manufacturing part.
    import gzip
    from render_models import verify_stand_reuse

    provenance = json.loads(
        (ROOT / "hardware/rendering/r23-service-stand-provenance.json").read_text()
    )
    fixture_source = ROOT / provenance["mesh"]["path"]
    if digest(fixture_source) != provenance["mesh"]["sha256"]:
        raise ValueError("Changed stand mesh")
    rows = json.load(gzip.open(fixture_source, "rt"))
    registry = json.loads(
        (ROOT / "hardware/cad/design-control/registry.json").read_text()
    )
    accepted = {
        r["path"]: r
        for r in json.loads(
            (ROOT / "hardware/cad/current/release-assembly.json").read_text()
        )["occurrences"]
    }
    verify_stand_reuse(provenance, registry, accepted, rows)
    fixtures = {}
    for source_row in rows:
        pid = source_row["part_id"]
        if pid not in ("J04", "J05", "J06"):
            continue
        transform = np.array(source_row["transform"]).reshape(4, 4)
        points = (
            np.array(source_row["vertices_cm"]).reshape(-1, 3) @ transform[:3, :3].T
            + transform[:3, 3]
        ) * 10
        points = points[:, [2, 1, 0]].copy()
        points[:, 2] = 138 - points[:, 2]
        color = {"J04": (188, 145, 91), "J05": (94, 116, 184), "J06": (70, 76, 82)}[pid]
        fixtures[pid] = dict(
            id=pid,
            occ=0,
            root=source_row["path"],
            v=points,
            f=np.array(source_row["faces"]).reshape(-1, 3),
            source=source_row,
            guide_color=color,
            flat_shading=True,
        )
    for yy in [-10, 10]:
        witnesses[f"J05-bore-{yy}"] = circle_witness(
            [fixtures["J05"]], 2, 88, [146, yy], 2.25
        )
        witnesses[f"J05-head-seat-{yy}"] = circle_witness(
            [fixtures["J05"]], 2, 93, [146, yy], 4.25
        )
    riser = clipped([fixtures["J04"]], [[127, -18, 76], [165, 18, 88]])
    fastening = paint.panel(
        riser + [fixtures["J05"]],
        [0.3, -0.45, 1.6],
        "Fasten J05 before adding foam",
        labels=[
            ("2 × 4 × 20 mm", [146, -10, 93], (20, 365)),
            ("pan-head screws", [146, 10, 93], (380, 405)),
            ("J04 wood", [163, 0, 82], (575, 90)),
        ],
        size=(800, 460),
    )
    lining = paint.panel(
        riser + [fixtures["J05"], fixtures["J06"]],
        [0.3, -0.45, 1.6],
        "Then line the curved face",
        labels=[("4 mm foam", [146, 0, 99], (25, 330))],
        size=(800, 380),
    )
    outputs["assets/community/stand-head-saddle-actions.png"] = paint.combine(
        [fastening, lining], "stand-head-saddle-actions.png"
    )
    witnesses["stand_mesh_sha256"] = digest(fixture_source)
    witnesses["stand_provenance_sha256"] = digest(
        ROOT / "hardware/rendering/r23-service-stand-provenance.json"
    )
    render.meshes = original
    return outputs, witnesses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--font",
        type=Path,
        default=Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source, registry, registry_hash = checked_source()
    lock = ROOT / "hardware/rendering/source-lock.json"
    lock_hash = digest(lock)
    os.environ.update(
        BGB_RENDER_OUTPUT=str(args.output.resolve()),
        BGB_RENDER_FONT=str(args.font.resolve()),
        BGB_RENDER_MESH_SOURCE=str(source),
    )
    sys.path.insert(0, str(ROOT / "hardware/tools/rendering"))
    render = importlib.import_module("render")
    palette = {
        (r["path"], r["body"]): r["chosen_rgb"]
        for r in json.loads((ROOT / "hardware/rendering/r22-colors.json").read_text())[
            "assignments"
        ]
    }
    base = render.col
    render.col = lambda m, h: (
        m.get("guide_color")
        or tuple(
            palette.get((m["source"].get("path"), m["source"].get("body")))
            or base(m, h)
        )
    )
    outputs, witnesses = make_images(render, args.output, args.font)
    if (
        digest(ROOT / "hardware/cad/design-control/registry.json") != registry_hash
        or digest(lock) != lock_hash
    ):
        raise ValueError(
            "Accepted inputs changed during rendering; inspect before adopting"
        )
    receipt = dict(
        cad=registry["main"],
        mesh_source=str(source.relative_to(ROOT)),
        mesh_sha256=digest(source),
        registry_sha256=registry_hash,
        source_lock_sha256=lock_hash,
        generator_sha256=digest(Path(__file__)),
        renderer_sha256=digest(ROOT / "hardware/tools/rendering/render.py"),
        fasteners_sha256=digest(ROOT / "hardware/tools/rendering/guide_fasteners.py"),
        catalog_sha256=digest(ROOT / "hardware/catalog/supplies.json"),
        font_sha256=digest(args.font),
        geometry_witnesses=witnesses,
        magnet_mm=[MAGNET_DIAMETER, MAGNET_THICKNESS],
        horn_mm=dict(
            diameter=23.55,
            thickness_illustrative=1.6,
            drilled_pair_spacing=18,
            drill_diameter=2.1,
        ),
        outputs={path: digest(tmp) for path, tmp in outputs.items()},
        applied=args.write,
    )
    (args.output / "render-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n"
    )
    if args.write:
        for path, tmp in outputs.items():
            if path not in ACTION_PATHS or (
                not (SRC / path).is_file()
                and path != "assets/community/stand-head-saddle-actions.png"
            ):
                raise ValueError(
                    "Only the owned existing assets and authorized new stand image may be written: "
                    + path
                )
            shutil.copyfile(tmp, SRC / path)
    print(
        json.dumps(
            dict(
                outputs=list(outputs),
                applied=args.write,
                receipt=str(args.output / "render-receipt.json"),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
