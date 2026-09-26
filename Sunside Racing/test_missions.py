"""Progression, mission givers and offers, in-world missions, drag races, and saving."""

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TOOLKIT_ROOT = PROJECT_ROOT.parent
if str(TOOLKIT_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLKIT_ROOT))

from car import TOP_SPEED, Car
from collision_manager import CollisionManager
from drag_race import DragRace, TrackLevel
from missions import DELIVERY_PENALTY, Missions, Offer, difficulty
from player_save import PlayerSave
from progression import Progress, reward
from world import TILE_SIZE, World


class ProgressionTests(unittest.TestCase):
    def test_levels_cost_ten_times_level(self):
        progress = Progress()
        self.assertEqual(progress.add("city", 9), [])
        self.assertEqual(progress.add("city", 1), [2])
        self.assertEqual(progress.add("city", 20 + 30), [3, 4])
        self.assertEqual((progress.levels["city"], progress.mastery["city"]), (4, 0))
        self.assertEqual(progress.levels["snow"], 1)  # Levels are per region.

    def test_rewards_grow_by_one_per_level_and_double_for_veterans(self):
        self.assertEqual(reward(2, 1), 2)
        self.assertEqual(reward(2, 4), 5)
        self.assertEqual(reward(3, 5, harder=True), 14)
        self.assertEqual(reward(0, 9, harder=True), 0)

    def test_level_upgrades(self):
        progress = Progress({"desert": {"level": 5, "mastery": 3}})
        self.assertAlmostEqual(progress.speed_scale("desert"), 1.16)
        self.assertEqual(progress.speed_scale("beach"), 1.0)
        self.assertTrue(progress.harder_unlocked("desert"))
        self.assertFalse(progress.harder_unlocked("city"))

    def test_difficulty_labels(self):
        self.assertEqual([difficulty(s) for s in (0.5, 0.79, 0.8, 1.04, 1.05, 1.25)],
                         ["Easy", "Easy", "Medium", "Medium", "Hard", "Hard"])


class GiverAndOfferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = World()

    def test_three_givers_and_three_veterans_per_region_off_the_road(self):
        missions = Missions(self.world, self.world.seed)
        self.assertEqual(len(missions.givers), 30)
        for giver in missions.givers:
            self.assertEqual(self.world.region_at(giver.x, giver.y), giver.region)
            self.assertFalse(self.world._road_style(int(giver.x // TILE_SIZE), int(giver.y // TILE_SIZE)))
        self.assertEqual(len(missions.visible_givers()), 15)  # Veterans wait for level 5.

    def test_offers_match_their_type_and_survive_a_round_trip(self):
        missions = Missions(self.world, self.world.seed)
        for giver in missions.givers[:6]:
            offer = missions.offer_for(giver)
            self.assertEqual(offer.type, giver.type)
            self.assertTrue(0.8 if giver.harder else 0.5 <= offer.scale <= 1.25)
            if offer.type == "drag":
                self.assertIn(offer.track["kind"], ("straight", "circuit"))
            else:
                self.assertNotIn(self.world.region_at(*offer.target), ("sea", "island"))
        again = Missions(self.world, self.world.seed, json.loads(json.dumps(missions.to_dict())))
        self.assertEqual({k: v.to_dict() for k, v in again.offers.items()},
                         {k: v.to_dict() for k, v in missions.offers.items()})

    def test_bad_saved_offers_are_dropped(self):
        data = {"offers": {"city-drag": {"type": "drag", "scale": 9}, "nobody": {"type": "speed"}}}
        missions = Missions(self.world, self.world.seed, data)
        self.assertEqual(missions.offers, {})
        with self.assertRaises(ValueError):
            Offer.from_dict("city-speed", {"type": "speed", "scale": 1.0, "target": None})

    def test_speed_limit_tightens_with_difficulty(self):
        missions = Missions(self.world, self.world.seed)
        giver = missions.by_id["city-speed"]
        easy = Offer(giver.id, "speed", 0.5, (giver.x + 3000, giver.y))
        hard = Offer(giver.id, "speed", 1.25, (giver.x + 3000, giver.y))
        start = (giver.x, giver.y)
        self.assertAlmostEqual(missions.speed_limit(easy, start) / missions.speed_limit(hard, start), 2.5)


class InWorldMissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = World()

    def start(self, giver_id, scale=1.0):
        missions = Missions(self.world, self.world.seed)
        giver = missions.by_id[giver_id]
        missions.offers[giver_id] = Offer(giver_id, giver.type, scale, (giver.x + 3000, giver.y))
        missions.accept(giver)
        return missions, giver

    def test_delivery_crashes_cost_points_by_difficulty_with_grace(self):
        missions, giver = self.start("city-delivery", 1.2)  # Hard: -15.
        missions.update(0.1, giver.x, giver.y, True, True, True)
        missions.update(0.1, giver.x, giver.y, True, True, True)   # Within the grace period.
        self.assertEqual((missions.active.points, missions.active.crashes), (85, 1))
        self.assertEqual(missions.status()[1], f"CRASH  -{DELIVERY_PENALTY['Hard']}")
        missions.update(1.0, giver.x, giver.y, True, True, False)
        missions.update(0.1, giver.x, giver.y, True, True, True)
        self.assertEqual(missions.active.points, 70)
        result = missions.update(0.1, giver.x + 3000, giver.y, False, False, False)
        self.assertTrue(result["success"])
        self.assertEqual(result["mastery"], 1)          # 70 points: 50+ tier.
        self.assertNotIn(giver.id, missions.offers)     # A fresh offer is ready.

    def test_delivery_fails_below_fifty_points(self):
        missions, giver = self.start("city-delivery", 0.9)  # Medium: -10.
        result = None
        for _ in range(6):
            result = missions.update(1.1, giver.x, giver.y, True, True, True)
        self.assertFalse(result["success"])
        self.assertIn(giver.id, missions.offers)        # Same offer kept for a retry.

    def test_aborting_fails_the_mission_and_keeps_the_offer(self):
        missions, giver = self.start("city-delivery", 1.0)
        offer = missions.offers[giver.id]
        result = missions.abort()
        self.assertFalse(result["success"])
        self.assertEqual((result["mastery"], result["giver"]), (0, giver))
        self.assertIsNone(missions.active)
        self.assertIs(missions.offers[giver.id], offer)   # Same mission to retry.
        self.assertEqual(missions.progress.completed["city"]["delivery"], 0)

    def test_speed_check_clock_starts_when_driving(self):
        missions, giver = self.start("city-speed", 1.0)
        limit = missions.active.time_limit
        missions.update(5.0, giver.x, giver.y, False, False, False)  # Still on foot.
        self.assertEqual(missions.active.time_left, limit)
        missions.update(1.0, giver.x, giver.y, True, True, False)
        self.assertAlmostEqual(missions.active.time_left, limit - 1.0)
        result = missions.update(0.1, giver.x + 3000, giver.y, True, True, False)
        self.assertTrue(result["success"])
        self.assertEqual(result["mastery"], 1)

    def test_speed_check_times_out(self):
        missions, giver = self.start("city-speed", 1.0)
        missions.update(0.1, giver.x, giver.y, True, True, False)
        result = missions.update(missions.active.time_limit, giver.x, giver.y, True, True, False)
        self.assertFalse(result["success"])

    def test_level_up_from_missions(self):
        missions, giver = self.start("city-delivery", 0.6)
        missions.progress.mastery["city"] = 9
        result = missions.update(0.1, giver.x + 3000, giver.y, True, False, False)
        self.assertEqual((result["mastery"], result["levels"], result["level"]), (2, [2], 2))

    def test_mastery_rows_show_levels_bonuses_completions_and_missions(self):
        missions, giver = self.start("city-speed", 1.0)
        missions.update(0.1, giver.x, giver.y, True, True, False)
        missions.update(0.1, giver.x + 3000, giver.y, True, True, False)  # Completed.
        missions.progress.add("desert", 10 + 20 + 30 + 40)                 # Level 5.
        desert = missions.by_id["desert-delivery"]
        missions.offers[desert.id] = Offer(desert.id, "delivery", 0.9, (desert.x + 3000, desert.y))
        missions.accept(desert)
        rows = {row["region"]: row for row in missions.mastery_rows()}
        self.assertEqual(rows["city"]["completed"], {"delivery": 0, "speed": 1, "drag": 0})
        self.assertEqual((rows["city"]["mastery"], rows["city"]["need"]), (1, 10))
        self.assertEqual((rows["desert"]["level"], rows["desert"]["speed"], rows["desert"]["veterans"]),
                         (5, 16, True))
        self.assertEqual(rows["desert"]["mission"], "Ongoing  ·  Delivery")
        restored = Missions(self.world, self.world.seed, json.loads(json.dumps(missions.to_dict())))
        rows = {row["region"]: row for row in restored.mastery_rows()}
        self.assertEqual(rows["desert"]["mission"], "")          # Ongoing missions aren't saved.
        self.assertEqual(rows["city"]["completed"]["speed"], 1)  # Completions are saved.

    def test_an_ongoing_mission_is_never_saved_and_its_offer_stays(self):
        missions, giver = self.start("city-speed", 1.0)
        offer = missions.offers[giver.id]
        missions.update(3.0, giver.x, giver.y, True, True, False)
        data = json.loads(json.dumps(missions.to_dict()))
        self.assertNotIn("queued", data)
        restored = Missions(self.world, self.world.seed, data)
        self.assertIsNone(restored.active)
        self.assertIsNone(restored.status())
        self.assertEqual(restored.offers[giver.id].to_dict(), offer.to_dict())  # Same mission.
        restored.accept(restored.by_id[giver.id])
        self.assertEqual(restored.active.time_left, restored.active.time_limit)  # Fresh clock.

    def test_old_saves_with_a_queued_mission_load_without_it(self):
        missions = Missions(self.world, self.world.seed, {"queued": "city-drag", "offers": {}})
        self.assertIsNone(missions.active)
        self.assertFalse(hasattr(missions, "queued"))

    def test_player_save_keeps_missions(self):
        with tempfile.TemporaryDirectory() as temp:
            store = PlayerSave(Path(temp) / "player.json")
            missions, giver = self.start("city-delivery", 1.0)
            missions.progress.add("snow", 35)
            store.save(Car(), None, missions.to_dict())
            store.load_state(CollisionManager(None, self.world))
            restored = Missions(self.world, self.world.seed, store.missions_data)
            self.assertEqual(restored.progress.levels["snow"], 3)
            self.assertIsNone(restored.active)
            self.assertIn(giver.id, restored.offers)


class FastTravelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = World()

    def test_travel_unlocks_at_level_three_and_not_during_missions(self):
        missions = Missions(self.world, self.world.seed)
        missions.progress.add("snow", 10 + 20)
        rows = {r["region"]: r["travel"] for r in missions.mastery_rows("city")}
        self.assertEqual((rows["snow"], rows["jungle"]), ("ready", "locked"))
        self.assertEqual({r["region"]: r["travel"] for r in missions.mastery_rows("snow")}["snow"], "here")
        giver = missions.by_id["city-speed"]
        missions.offers[giver.id] = Offer(giver.id, "speed", 1.0, (giver.x + 3000, giver.y))
        missions.accept(giver)
        self.assertEqual({r["region"]: r["travel"] for r in missions.mastery_rows("city")}["snow"], "busy")

    def test_lands_just_inside_each_region_on_clear_ground(self):
        from fast_travel import INSET, destination, region_anchor
        collisions = CollisionManager(None, self.world)
        start = Car()  # City start.
        for region in ("jungle", "desert", "snow", "rural"):
            x, y, heading = destination(self.world, collisions, start, region, start.x, start.y)
            self.assertEqual(self.world.region_at(x, y), region)
            probe = Car(x=x, y=y, heading=heading)
            self.assertTrue(collisions.can_move(probe.collision_record()))
            # Near the border, far closer to the player than the region's center is.
            self.assertLess(math.dist((x, y), (start.x, start.y)),
                            math.dist(region_anchor(self.world, region), (start.x, start.y)))
            self.assertEqual(start.heading, 0.0)  # The search does not turn the real car.


class DragRaceTests(unittest.TestCase):
    def test_tracks_are_walled_and_tiled(self):
        for kind, shape in (("straight", 0), ("circuit", 0), ("circuit", 1), ("circuit", 2)):
            level = TrackLevel(kind, "desert", shape)
            names = {s.name for s in level.sprites if s.atlas == "track-atlas"}
            self.assertTrue({"track_desert_base", "track_desert_edge", "track_fence",
                             "track_desert_finish"} <= names)
            if kind == "circuit":
                self.assertTrue({"track_desert_corner", "track_desert_inner", "track_tires"} <= names)
            self.assertEqual(level.region_at(*level.path[0]), "desert")  # Desert grip on track.
            # Every track cell is fenced off from the outside world.
            for tx, ty in level.track:
                for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                    cell = (tx + dx, ty + dy)
                    if cell not in level.track:
                        x, y = (cell[0] + 0.5) * TILE_SIZE, (cell[1] + 0.5) * TILE_SIZE
                        self.assertTrue(any(abs(o.x - x) < 1 and abs(o.y - y) < 1
                                            for o in level.nearby_obstacles(x, y)))

    def run_race(self, track, scale, drive):
        race = DragRace(track, scale, 1.0, 3)
        for _ in range(60 * 120):
            throttle, steer = drive(race)
            race.update(1 / 60, throttle, steer, False)
            if race.result:
                return race
        self.fail("race never finished")

    def test_full_throttle_beats_a_slow_rival_on_the_straight(self):
        race = self.run_race({"kind": "straight", "theme": "city"}, 0.5, lambda r: (1, 0))
        self.assertEqual(race.result, "win")
        self.assertEqual(race.position(), 1)

    def test_a_fast_rival_wins_the_straight(self):
        race = self.run_race({"kind": "straight", "theme": "city"}, 1.25, lambda r: (1, 0))
        self.assertEqual(race.result, "lose")

    def test_rival_laps_the_circuit_on_the_track(self):
        race = DragRace({"kind": "circuit", "theme": "snow", "shape": 2}, 1.0, 1.0, 3)
        race.clock = 0.0
        on_track = 0
        steps = 0
        while race.rival.progress < race.level.race_length:
            race.rival.update(1 / 60, 10.0)
            steps += 1
            cell = (int(race.rival.x // TILE_SIZE), int(race.rival.y // TILE_SIZE))
            on_track += cell in race.level.track
        self.assertEqual(on_track, steps)
        self.assertLess(steps / 60, 60)

    def test_circuit_progress_follows_the_lap(self):
        level = TrackLevel("circuit", "city", 0)
        progress = level.progress_of(level.start_x - 96, level.path[0][1], -96)
        self.assertAlmostEqual(progress, -96, delta=1)
        # Walk the centerline all the way round; progress should rise to a full lap.
        x, y = level.path[0]
        for (ax, ay), (bx, by) in level._segments():
            for i in range(1, 41):
                x, y = ax + (bx - ax) * i / 40, ay + (by - ay) * i / 40
                progress = level.progress_of(x, y, progress)
        # Back at the first corner, 256 px short of the start/finish line...
        self.assertAlmostEqual(progress, level.lap_length - (level.start_x - level.path[0][0]), delta=2)
        # ...and crossing the line completes the lap.
        for i in range(1, 11):
            progress = level.progress_of(level.path[0][0] + (level.start_x - level.path[0][0]) * i / 10,
                                         level.path[0][1], progress)
        self.assertAlmostEqual(progress, level.lap_length, delta=2)


if __name__ == "__main__":
    unittest.main()
