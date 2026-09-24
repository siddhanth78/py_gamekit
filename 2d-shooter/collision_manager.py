"""Logical hitboxes and collision queries for the arena."""

from gl_utils import check_collision, point_in_rotated_rect


class CollisionManager:
    @staticmethod
    def rect_record(x, y, width, height, rotation=0.0):
        return [x, y, 255, 255, 255, 255, 0.0, width, height, rotation]

    def rects_overlap(self, first, second):
        return bool(check_collision(first, [second], "rect"))

    @staticmethod
    def point_hits_rect(x, y, rect):
        return point_in_rotated_rect(
            x, y, rect[0], rect[1], rect[7], rect[8], rect[9]
        )

    @staticmethod
    def clamp_center(x, y, half_width, half_height, bounds):
        left, top, right, bottom = bounds
        return (
            max(left + half_width, min(right - half_width, x)),
            max(top + half_height, min(bottom - half_height, y)),
        )
