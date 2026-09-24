"""GPU-backed entity storage organized into ordered render batches."""

from __future__ import annotations

import moderngl

from gl_utils import (
    build_point_objs,
    build_rect_objs,
    build_tex_objs,
    get_new_instances,
    pstride,
    rstride,
    tstride,
    update_instances,
)


RECORD_LENGTH = {"rect": 10, "point": 7, "tex": 12}
STRIDE = {"rect": rstride, "point": pstride, "tex": tstride}


class GameState:
    """Owns game entities and the exact instance buffers used to draw them."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.entity_counter = 0
        self.entities = {}
        self.batches = {}

    def register_batch(
        self,
        name,
        entity_type,
        program,
        capacity,
        order,
        texture=None,
        atlas_grid=(1, 1),
    ):
        if name in self.batches:
            raise ValueError(f"Render batch already exists: {name}")
        if entity_type not in RECORD_LENGTH:
            raise ValueError(f"Unsupported entity type: {entity_type}")

        rects, points, textures = get_new_instances(
            capacity if entity_type == "rect" else 0,
            capacity if entity_type == "point" else 0,
            capacity if entity_type == "tex" else 0,
        )
        instances = {"rect": rects, "point": points, "tex": textures}[entity_type]
        builder = {
            "rect": build_rect_objs,
            "point": build_point_objs,
            "tex": build_tex_objs,
        }[entity_type]
        vao, vbo = builder(self.ctx, program, instances)
        self.batches[name] = {
            "type": entity_type,
            "program": program,
            "capacity": capacity,
            "order": order,
            "texture": texture,
            "atlas_grid": atlas_grid,
            "data": [],
            "entity_ids": [],
            "instances": instances,
            "vao": vao,
            "vbo": vbo,
        }

    @staticmethod
    def _record(entity_type, values):
        if entity_type == "rect":
            return [
                values.get("x", 0), values.get("y", 0),
                values.get("r", 255), values.get("g", 255),
                values.get("b", 255), values.get("a", 255),
                values.get("thickness", 0.0),
                values.get("width", 32), values.get("height", 32),
                values.get("rotation", 0),
            ]
        if entity_type == "point":
            return [
                values.get("x", 0), values.get("y", 0),
                values.get("r", 255), values.get("g", 255),
                values.get("b", 255), values.get("a", 255),
                values.get("size", 8),
            ]
        return [
            values.get("x", 0), values.get("y", 0),
            values.get("r", 255), values.get("g", 255),
            values.get("b", 255), values.get("a", 255),
            values.get("thickness", 0.0),
            values.get("width", 32), values.get("height", 32),
            values.get("rotation", 0),
            values.get("tile_x", 0), values.get("tile_y", 0),
        ]

    def spawn(self, batch_name, **values):
        batch = self.batches[batch_name]
        slot = len(batch["data"])
        if slot >= batch["capacity"]:
            raise RuntimeError(f"Exceeded capacity for batch {batch_name}")

        entity_id = self.entity_counter
        self.entity_counter += 1
        batch["data"].append(self._record(batch["type"], values))
        batch["entity_ids"].append(entity_id)
        self.entities[entity_id] = {"batch": batch_name, "slot": slot}
        self._sync(batch, slot)
        return entity_id

    def _sync(self, batch, slot):
        update_instances(slot, batch["data"], batch["instances"])
        batch["vbo"].write(
            batch["instances"][slot].tobytes(),
            offset=slot * STRIDE[batch["type"]],
        )

    def get_data(self, entity_id):
        meta = self.entities.get(entity_id)
        if meta is None:
            return None
        batch = self.batches[meta["batch"]]
        return batch["data"][meta["slot"]]

    def modify(self, entity_id, **values):
        meta = self.entities.get(entity_id)
        if meta is None:
            return
        batch = self.batches[meta["batch"]]
        record = batch["data"][meta["slot"]]
        field_map = {
            "rect": {
                "x": 0, "y": 1, "r": 2, "g": 3, "b": 4, "a": 5,
                "thickness": 6, "width": 7, "height": 8, "rotation": 9,
            },
            "point": {
                "x": 0, "y": 1, "r": 2, "g": 3, "b": 4, "a": 5,
                "size": 6,
            },
            "tex": {
                "x": 0, "y": 1, "r": 2, "g": 3, "b": 4, "a": 5,
                "thickness": 6, "width": 7, "height": 8, "rotation": 9,
                "tile_x": 10, "tile_y": 11,
            },
        }[batch["type"]]
        for key, value in values.items():
            if key in field_map:
                record[field_map[key]] = value
        self._sync(batch, meta["slot"])

    def destroy(self, entity_id):
        meta = self.entities.get(entity_id)
        if meta is None:
            return
        batch = self.batches[meta["batch"]]
        slot = meta["slot"]
        last_slot = len(batch["data"]) - 1
        if slot != last_slot:
            moved_id = batch["entity_ids"][last_slot]
            batch["data"][slot] = batch["data"][last_slot]
            batch["entity_ids"][slot] = moved_id
            self.entities[moved_id]["slot"] = slot
            self._sync(batch, slot)
        batch["data"].pop()
        batch["entity_ids"].pop()
        del self.entities[entity_id]

    def clear_batch(self, batch_name):
        batch = self.batches[batch_name]
        for entity_id in batch["entity_ids"]:
            self.entities.pop(entity_id, None)
        batch["data"].clear()
        batch["entity_ids"].clear()

    def render_all(self):
        for batch in sorted(self.batches.values(), key=lambda item: item["order"]):
            count = len(batch["data"])
            if count == 0:
                continue
            if batch["type"] == "tex":
                batch["texture"].use(location=0)
                batch["program"]["u_texture"].value = 0
                batch["program"]["u_atlas_grid"].value = batch["atlas_grid"]
                batch["vao"].render(moderngl.TRIANGLES, instances=count)
            elif batch["type"] == "point":
                batch["vao"].render(moderngl.POINTS, vertices=1, instances=count)
            else:
                batch["vao"].render(moderngl.TRIANGLES, instances=count)

    def release(self):
        for batch in self.batches.values():
            batch["vao"].release()
            batch["vbo"].release()
