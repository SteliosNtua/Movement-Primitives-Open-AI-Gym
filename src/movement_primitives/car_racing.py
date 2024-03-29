"""
Instructions to run this custom environment

## Execute

    run from cmd python /path/to/file/car_racing.py <corner_num> <controller>
    ex. python src/car_racing.py 85 c
    means run the script for corner 85 degrees with the hand controller

    Options: SCALE    track_v    corner_num     controller
              10        v1          85         c: hand controller
              10        v1          65         k: keyboard 
              10        v1          45         d: desired input actions 
              10        v1          35  
              10        v2          130
              14        v2          100
              10        v2          95
              10        v2          110


        # {10.0}    -> (85)->[58,125]   | (45)->[0,46]        | (35)->[310,348]    | (65)->[282,333]
        # {10.0v2}  -> (95)->[50,111]   | (110)->[250, 297]   | (130)->[128,181]   | 
        # {14.0}    -> (100)->[281,345] |
    
## Initial speed:
    Comment or uncomment initial_speed if you desire the agent to begin with initial speed


"""



__credits__ = ["Andrea PIERRÉ"]

import math

from typing import Optional

import Box2D
import numpy as np
from Box2D.b2 import contactListener, fixtureDef, polygonShape

import gym
from gym import spaces
from car_dynamics import Car
from gym.utils import EzPickle

STATE_W = 96  # less than Atari 160x192
STATE_H = 96
VIDEO_W = 600
VIDEO_H = 400
WINDOW_W = 1000
WINDOW_H = 750

SCALE = 10.0  # Track scale
TRACK_RAD = 900 / SCALE  # Track is heavily morphed circle with this radius
PLAYFIELD = 2000 / SCALE  # Game over boundary
FPS = 50  # Frames per second
ZOOM = 1.7  # Camera zoom
# ZOOM = 0.2  # Camera zoom
ZOOM_FOLLOW = True  # Set to False for fixed view (don't use zoom)


TRACK_DETAIL_STEP = 21 / SCALE
TRACK_TURN_RATE = 0.31
TRACK_WIDTH = (40 / SCALE) * 1.25  # 40 / SCALE
BORDER = 8 / SCALE
BORDER_MIN_COUNT = 4

# Parameters added by Stelios
sim_params_path_v1 = "./simulation_parameters/track_v1.txt"
sim_params_path_v2 = "./simulation_parameters/track_v2.txt"
sim_params_path_v3 = "./simulation_parameters/track_v3.txt"
sim_params_path_v4 = "./simulation_parameters/track_v4.txt"
sim_params_path_v5 = "./simulation_parameters/track_v5.txt"

sim_data_actions = "./simulation_data/actions/"
sim_data_states = "./simulation_data/states/"
desired_data_actions = "./desired_data/actions/"
desired_data_states = "./desired_data/states/"
expert_data_actions = "./expert_dmp/actions/"
expert_data_states = "./expert_dmp/states/"


corners = {
# corner_angle : [x, y, (vel_x, vel_y), angle, SCALE, track_params] <-- initial params
    30: [310,348,(36.4, 38.9), 0, 10, sim_params_path_v1],
    40: [0,35, (11.1, 46.2), 0, 10, sim_params_path_v1], #(0, 46)
    50: [228,275, (46.966, 24.39), 0, 10, sim_params_path_v3], #(228, 280)
    60: [282,333, (49.3, -11.1), -0.06, 10, sim_params_path_v1],
    80: [116,169, (0, 0), 0.1, 10, sim_params_path_v3],
    85: [58,125, (-36.3, 37.5), 0, 10, sim_params_path_v1],
    90: [50,111, (-44.5, 34.5), 0, 10, sim_params_path_v2],
    100: [281,345, (7.2, -52.5), 0, 14, sim_params_path_v1],
    110: [250, 297, (52.1, -23.9), -0.045, 10, sim_params_path_v2],
    130: [128,181, (-35.5, 7.7), -0.045, 10, sim_params_path_v2],
    135: [145,210, (0, 0), -0.19, 10, sim_params_path_v3],
    140: [118,181, (0, 0), 0.02, 10, sim_params_path_v4],
    145: [83,142, (0, 0), -0.22, 10, sim_params_path_v3],
    147: [252,310, (0, 0), -0.185, 10, sim_params_path_v4],
    150: [185,250, (0, 0), -0.085, 10, sim_params_path_v4],
    160: [0,110, (0, 0), -0.04, 10, sim_params_path_v4],
    None: [0,-1, (0,0), None],
    1: [0,-1, (0,0), 0, 10, sim_params_path_v1],
    2: [0,-1, (0,0), 0, 10, sim_params_path_v2],
    3: [0,-1, (0,0), 0, 10, sim_params_path_v3],
    4: [0,-1, (0,0), 0, 10, sim_params_path_v4],
    5: [0,-1, (0,0), 0, 10, sim_params_path_v5],
}

class FrictionDetector(contactListener):
    def __init__(self, env, lap_complete_percent):
        contactListener.__init__(self)
        self.env = env
        self.lap_complete_percent = lap_complete_percent

    def BeginContact(self, contact):
        self._contact(contact, True)

    def EndContact(self, contact):
        self._contact(contact, False)

    def _contact(self, contact, begin):
        tile = None
        obj = None
        u1 = contact.fixtureA.body.userData
        u2 = contact.fixtureB.body.userData
        if u1 and "road_friction" in u1.__dict__:
            tile = u1
            obj = u2
        if u2 and "road_friction" in u2.__dict__:
            tile = u2
            obj = u1
        if not tile:
            return

        # inherit tile color from env
        tile.color = self.env.road_color / 255
        if not obj or "tiles" not in obj.__dict__:
            return
        if begin:
            obj.tiles.add(tile)
            if not tile.road_visited:
                tile.road_visited = True
                self.env.reward += 1000.0 / len(self.env.track)
                self.env.tile_visited_count += 1

                # Lap is considered completed if enough % of the track was covered
                if (
                    tile.idx == 0
                    and self.env.tile_visited_count / len(self.env.track)
                    > self.lap_complete_percent
                ):
                    self.env_new_lap = True
        else:
            obj.tiles.remove(tile)


class CarRacing(gym.Env, EzPickle):
    """
    ### Description
    The easiest continuous control task to learn from pixels - a top-down
    racing environment. Discrete control is reasonable in this environment as
    well; on/off discretization is fine.

    The game is solved when the agent consistently gets 900+ points.
    The generated track is random every episode.

    Some indicators are shown at the bottom of the window along with the
    state RGB buffer. From left to right: true speed, four ABS sensors,
    steering wheel position, and gyroscope.
    To play yourself (it's rather fast for humans), type:
    ```
    python gym/envs/box2d/car_racing.py
    ```
    Remember: it's a powerful rear-wheel drive car - don't press the accelerator
    and turn at the same time.

    ### Action Space
    There are 3 actions: steering (-1 is full left, +1 is full right), gas,
    and breaking.

    ### Observation Space
    State consists of 96x96 pixels.

    ### Rewards
    The reward is -0.1 every frame and +1000/N for every track tile visited,
    where N is the total number of tiles visited in the track. For example,
    if you have finished in 732 frames, your reward is
    1000 - 0.1*732 = 926.8 points.

    ### Starting State
    The car starts at rest in the center of the road.

    ### Episode Termination
    The episode finishes when all of the tiles are visited. The car can also go
    outside of the playfield - that is, far off the track, in which case it will
    receive -100 reward and die.

    ### Arguments
    `lap_complete_percent` dictates the percentage of tiles that must be visited by
    the agent before a lap is considered complete.

    Passing `domain_randomize=True` enabled the domain randomized variant of the environment.
    In this scenario, the background and track colours are different on every reset.

    ### Version History
    - v1: Change track completion logic and add domain randomization (0.24.0)
    - v0: Original version

    ### References
    - Chris Campbell (2014), http://www.iforce2d.net/b2dtut/top-down-car.

    ### Credits
    Created by Oleg Klimov
    """

    metadata = {
        "render_modes": ["human", "rgb_array", "state_pixels"],
        "render_fps": FPS,
    }

    def __init__(
        self,
        verbose: bool = True,
        lap_complete_percent: float = 0.95,
        domain_randomize: bool = False,
        corner_num: int = None,
        sim_params_path: str = None 
    ):
        EzPickle.__init__(self)
        self.corner_num = corner_num
        self.sim_params_path = sim_params_path
        self.domain_randomize = domain_randomize
        self._init_colors()

        self.contactListener_keepref = FrictionDetector(self, lap_complete_percent)
        self.world = Box2D.b2World((0, 0), contactListener=self.contactListener_keepref)
        self.screen = None
        self.clock = None
        self.isopen = True
        self.invisible_state_window = None
        self.invisible_video_window = None
        self.road = None
        self.car = None
        self.reward = 0.0
        self.prev_reward = 0.0
        self.verbose = verbose
        self.new_lap = False
        self.fd_tile = fixtureDef(
            shape=polygonShape(vertices=[(0, 0), (1, 0), (1, -1), (0, -1)])
        )

        # This will throw a warning in tests/envs/test_envs in utils/env_checker.py as the space is not symmetric
        #   or normalised however this is not possible here so ignore
        self.action_space = spaces.Box(
            np.array([-1, 0, 0]).astype(np.float32),
            np.array([+1, +1, +1]).astype(np.float32),
        )  # steer, gas, brake

        self.observation_space = spaces.Box(
            low=0, high=255, shape=(STATE_H, STATE_W, 3), dtype=np.uint8
        )

    def _destroy(self):
        if not self.road:
            return
        for t in self.road:
            self.world.DestroyBody(t)
        self.road = []
        self.car.destroy()
   
    def _init_colors(self):
        if self.domain_randomize:
            # domain randomize the bg and grass colour
            self.road_color = self.np_random.uniform(0, 210, size=3)

            self.bg_color = self.np_random.uniform(0, 210, size=3)

            self.grass_color = np.copy(self.bg_color)
            idx = self.np_random.integers(3)
            self.grass_color[idx] += 20
        else:
            # default colours
            self.road_color = np.array([102, 102, 102])
            self.bg_color = np.array([102, 204, 102])
            self.grass_color = np.array([102, 230, 102])

    def load_checkpoints(self, n_checkpoints, path):
        with open(path) as f:
            lines = f.readlines()
            f.close()
        noise = [float(s.strip()) for s in lines[:n_checkpoints]]
        rad = [float(s.strip()) for s in lines[-n_checkpoints:]]
        checkpoints = []
        for c in range(n_checkpoints):
            alpha = 2 * math.pi * c / n_checkpoints + noise[c]
            if c == 0:
                alpha = 0
                rad[c] = 1.5 * TRACK_RAD
            if c == n_checkpoints - 1:
                alpha = 2 * math.pi * c / n_checkpoints
                self.start_alpha = 2 * math.pi * (-0.5) / n_checkpoints
                rad[c] = 1.5 * TRACK_RAD
            checkpoints.append((alpha, rad[c] * math.cos(alpha), rad[c] * math.sin(alpha)))
        return checkpoints
    
    def store_checkpoints(self, n_checkpoints):
        noise_list = []
        rad_list = []
        # Create checkpoints
        checkpoints = []
        for c in range(n_checkpoints):
            noise = self.np_random.uniform(0, 2 * math.pi * 1 / n_checkpoints)
            alpha = 2 * math.pi * c / n_checkpoints + noise
            rad = self.np_random.uniform(TRACK_RAD / 3, TRACK_RAD)

            if c == 0:
                alpha = 0
                rad = 1.5 * TRACK_RAD
            if c == n_checkpoints - 1:
                alpha = 2 * math.pi * c / n_checkpoints
                self.start_alpha = 2 * math.pi * (-0.5) / n_checkpoints
                rad = 1.5 * TRACK_RAD
            noise_list.append(noise)
            rad_list.append(rad)
            checkpoints.append((alpha, rad * math.cos(alpha), rad * math.sin(alpha)))

        with open(f'new_track_parameters_{SCALE}.txt', 'w') as f:
            for item in noise_list:
                f.write("%s\n" % item)
            f.write("\n")
            for item in rad_list:
                f.write("%s\n" % item)
            f.close()
        return checkpoints

    def _create_track(self):
        CHECKPOINTS = 12
        if self.sim_params_path:
            checkpoints =  self.load_checkpoints(CHECKPOINTS, path=self.sim_params_path)
        else:
            checkpoints = self.store_checkpoints(CHECKPOINTS)

        

        self.road = []

        # Go from one checkpoint to another to create track
        x, y, beta = 1.5 * TRACK_RAD, 0, 0
        dest_i = 0
        laps = 0
        track = []
        no_freeze = 2500
        visited_other_side = False
        while True:
            alpha = math.atan2(y, x)
            if visited_other_side and alpha > 0:
                laps += 1
                visited_other_side = False
            if alpha < 0:
                visited_other_side = True
                alpha += 2 * math.pi

            while True:  # Find destination from checkpoints
                failed = True

                while True:
                    dest_alpha, dest_x, dest_y = checkpoints[dest_i % len(checkpoints)]
                    if alpha <= dest_alpha:
                        failed = False
                        break
                    dest_i += 1
                    if dest_i % len(checkpoints) == 0:
                        break

                if not failed:
                    break

                alpha -= 2 * math.pi
                continue

            r1x = math.cos(beta)
            r1y = math.sin(beta)
            p1x = -r1y
            p1y = r1x
            dest_dx = dest_x - x  # vector towards destination
            dest_dy = dest_y - y
            # destination vector projected on rad:
            proj = r1x * dest_dx + r1y * dest_dy
            while beta - alpha > 1.5 * math.pi:
                beta -= 2 * math.pi
            while beta - alpha < -1.5 * math.pi:
                beta += 2 * math.pi
            prev_beta = beta
            proj *= SCALE
            if proj > 0.3:
                beta -= min(TRACK_TURN_RATE, abs(0.001 * proj))
            if proj < -0.3:
                beta += min(TRACK_TURN_RATE, abs(0.001 * proj))
            x += p1x * TRACK_DETAIL_STEP
            y += p1y * TRACK_DETAIL_STEP
            track.append((alpha, prev_beta * 0.5 + beta * 0.5, x, y))
            if laps > 4:
                break
            no_freeze -= 1
            if no_freeze == 0:
                break

        # Find closed loop range i1..i2, first loop should be ignored, second is OK
        i1, i2 = -1, -1
        i = len(track)
        while True:
            i -= 1
            if i == 0:
                return False  # Failed
            pass_through_start = (
                track[i][0] > self.start_alpha and track[i - 1][0] <= self.start_alpha
            )
            if pass_through_start and i2 == -1:
                i2 = i
            elif pass_through_start and i1 == -1:
                i1 = i
                break
        if self.verbose:
            print("Track generation: %i..%i -> %i-tiles track" % (i1, i2, i2 - i1))
        assert i1 != -1
        assert i2 != -1

        track = track[i1 : i2 - 1]

        first_beta = track[0][1]
        first_perp_x = math.cos(first_beta)
        first_perp_y = math.sin(first_beta)
        # Length of perpendicular jump to put together head and tail
        well_glued_together = np.sqrt(
            np.square(first_perp_x * (track[0][2] - track[-1][2]))
            + np.square(first_perp_y * (track[0][3] - track[-1][3]))
        )
        if well_glued_together > TRACK_DETAIL_STEP:
            return False

        # Red-white border on hard turns
        border = [False] * len(track)
        for i in range(len(track)):
            good = True
            oneside = 0
            for neg in range(BORDER_MIN_COUNT):
                beta1 = track[i - neg - 0][1]
                beta2 = track[i - neg - 1][1]
                good &= abs(beta1 - beta2) > TRACK_TURN_RATE * 0.2
                oneside += np.sign(beta1 - beta2)
            good &= abs(oneside) == BORDER_MIN_COUNT
            border[i] = good
        for i in range(len(track)):
            for neg in range(BORDER_MIN_COUNT):
                border[i - neg] |= border[i]

        # Create tiles
        # {10.0}    -> (85)->[58,125]   | (45)->[0,46]        | (35)->[310,348]    | (65)->[282,333]
        # {10.0v2}  -> (95)->[50,111]   | (110)->[250, 297]   | (130)->[128,181]   | 
        # {14.0}    -> (100)->[281,345] |

        if self.corner_num and self.corner_num > 10:
            iter = range(corners[corner_num][0],corners[corner_num][1])
        else:
            iter = range(len(track))
        for i in iter:
            alpha1, beta1, x1, y1 = track[i]
            alpha2, beta2, x2, y2 = track[i - 1]
            road1_l = (
                x1 - TRACK_WIDTH * math.cos(beta1),
                y1 - TRACK_WIDTH * math.sin(beta1),
            )
            road1_r = (
                x1 + TRACK_WIDTH * math.cos(beta1),
                y1 + TRACK_WIDTH * math.sin(beta1),
            )
            road2_l = (
                x2 - TRACK_WIDTH * math.cos(beta2),
                y2 - TRACK_WIDTH * math.sin(beta2),
            )
            road2_r = (
                x2 + TRACK_WIDTH * math.cos(beta2),
                y2 + TRACK_WIDTH * math.sin(beta2),
            )
            vertices = [road1_l, road1_r, road2_r, road2_l]
            self.fd_tile.shape.vertices = vertices
            t = self.world.CreateStaticBody(fixtures=self.fd_tile)
            t.userData = t
            c = 0.01 * (i % 3) * 255
            t.color = self.road_color + c
            t.road_visited = False
            t.road_friction = 1.0
            t.idx = i
            t.fixtures[0].sensor = True
            self.road_poly.append(([road1_l, road1_r, road2_r, road2_l], t.color))
            self.road.append(t)
            # Comment this if statement to remove red-white corner kerbs
            if border[i]:
                side = np.sign(beta2 - beta1)
                b1_l = (
                    x1 + side * TRACK_WIDTH * math.cos(beta1),
                    y1 + side * TRACK_WIDTH * math.sin(beta1),
                )
                b1_r = (
                    x1 + side * (TRACK_WIDTH + BORDER) * math.cos(beta1),
                    y1 + side * (TRACK_WIDTH + BORDER) * math.sin(beta1),
                )
                b2_l = (
                    x2 + side * TRACK_WIDTH * math.cos(beta2),
                    y2 + side * TRACK_WIDTH * math.sin(beta2),
                )
                b2_r = (
                    x2 + side * (TRACK_WIDTH + BORDER) * math.cos(beta2),
                    y2 + side * (TRACK_WIDTH + BORDER) * math.sin(beta2),
                )
                self.road_poly.append(
                    (
                        [b1_l, b1_r, b2_r, b2_l],
                        (255, 255, 255) if i % 2 == 0 else (255, 0, 0),
                    )
                )
        
        if self.corner_num:
            self.track = track[corners[corner_num][0]:corners[corner_num][1]]
        else:
            self.track = track 
        return True

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        return_info: bool = False,
        options: Optional[dict] = None,
    ):
        super().reset(seed=seed)
        self._destroy()
        self.reward = 0.0
        self.prev_reward = 0.0
        self.tile_visited_count = 0
        self.t = 0.0
        self.new_lap = False
        self.road_poly = []
        self._init_colors()

        while True:
            success = self._create_track()
            if success:
                break
            if self.verbose:
                print(
                    "retry to generate track (normal if there are not many"
                    "instances of this message)"
                )
        self.car = Car(self.world, *self.track[0][1:4], add_angle=corners[self.corner_num][3])

        if not return_info:
            return self.step(None)[0]
        else:
            return self.step(None)[0], {}

    def step(self, action: np.ndarray):
        if action is not None:
            self.car.steer(-action[0])
            self.car.gas(action[1])
            self.car.brake(action[2])

        self.car.step(1.0 / FPS)
        self.world.Step(1.0 / FPS, 6 * 30, 2 * 30)
        self.t += 1.0 / FPS

        self.state = self.render("state_pixels")

        step_reward = 0
        done = False
        if action is not None:  # First step without action, called from reset()
            self.reward -= 0.1
            # We actually don't want to count fuel spent, we want car to be faster.
            # self.reward -=  10 * self.car.fuel_spent / ENGINE_POWER
            self.car.fuel_spent = 0.0
            step_reward = self.reward - self.prev_reward
            self.prev_reward = self.reward
            if self.tile_visited_count == len(self.track) or self.new_lap:
                done = True
            x, y = self.car.hull.position
            if abs(x) > PLAYFIELD or abs(y) > PLAYFIELD:
                done = True
                step_reward = -100

        return self.state, step_reward, done, {}

    def render(self, mode: str = "human"):
        import pygame

        pygame.font.init()

        assert mode in ["human", "state_pixels", "rgb_array"]
        if self.screen is None and mode == "human":
            pygame.init()
            pygame.display.init()
            self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        if self.clock is None:
            self.clock = pygame.time.Clock()

        if "t" not in self.__dict__:
            return  # reset() not called yet

        self.surf = pygame.Surface((WINDOW_W, WINDOW_H))

        # computing transformations
        angle = -self.car.hull.angle
        # Animating first second zoom.
        zoom = 0.1 * SCALE * max(1 - self.t, 0) + ZOOM * SCALE * min(self.t, 1)
        scroll_x = -(self.car.hull.position[0]) * zoom
        scroll_y = -(self.car.hull.position[1]) * zoom
        trans = pygame.math.Vector2((scroll_x, scroll_y)).rotate_rad(angle)
        trans = (WINDOW_W / 2 + trans[0], WINDOW_H / 4 + trans[1])

        self._render_road(zoom, trans, angle)
        self.car.draw(self.surf, zoom, trans, angle, mode != "state_pixels")

        self.surf = pygame.transform.flip(self.surf, False, True)

        # showing stats
        self._render_indicators(WINDOW_W, WINDOW_H)

        font = pygame.font.Font(pygame.font.get_default_font(), 42)
        text = font.render("%04i" % self.reward, True, (255, 255, 255), (0, 0, 0))
        text_rect = text.get_rect()
        text_rect.center = (60, WINDOW_H - WINDOW_H * 2.5 / 40.0)
        self.surf.blit(text, text_rect)

        if mode == "human":
            pygame.event.pump()
            self.clock.tick(self.metadata["render_fps"])
            self.screen.fill(0)
            self.screen.blit(self.surf, (0, 0))
            pygame.display.flip()

        if mode == "rgb_array":
            return self._create_image_array(self.surf, (VIDEO_W, VIDEO_H))
        elif mode == "state_pixels":
            return self._create_image_array(self.surf, (STATE_W, STATE_H))
        else:
            return self.isopen

    def _render_road(self, zoom, translation, angle):
        bounds = PLAYFIELD
        field = [
            (bounds, bounds),
            (bounds, -bounds),
            (-bounds, -bounds),
            (-bounds, bounds),
        ]

        # draw background
        self._draw_colored_polygon(
            self.surf, field, self.bg_color, zoom, translation, angle
        )

        # draw grass patches
        k = bounds / (20.0)
        grass = []
        for x in range(-20, 20, 2):
            for y in range(-20, 20, 2):
                grass.append(
                    [
                        (k * x + k, k * y + 0),
                        (k * x + 0, k * y + 0),
                        (k * x + 0, k * y + k),
                        (k * x + k, k * y + k),
                    ]
                )
        for poly in grass:
            self._draw_colored_polygon(
                self.surf, poly, self.grass_color, zoom, translation, angle
            )

        # draw road
        for poly, color in self.road_poly:
            # converting to pixel coordinates
            poly = [(p[0], p[1]) for p in poly]
            color = [int(c) for c in color]
            self._draw_colored_polygon(self.surf, poly, color, zoom, translation, angle)

    def _render_indicators(self, W, H):
        import pygame

        s = W / 40.0
        h = H / 40.0
        color = (0, 0, 0)
        polygon = [(W, H), (W, H - 5 * h), (0, H - 5 * h), (0, H)]
        pygame.draw.polygon(self.surf, color=color, points=polygon)

        def vertical_ind(place, val):
            return [
                (place * s, H - (h + h * val)),
                ((place + 1) * s, H - (h + h * val)),
                ((place + 1) * s, H - h),
                ((place + 0) * s, H - h),
            ]

        def horiz_ind(place, val):
            return [
                ((place + 0) * s, H - 4 * h),
                ((place + val) * s, H - 4 * h),
                ((place + val) * s, H - 2 * h),
                ((place + 0) * s, H - 2 * h),
            ]

        true_speed = np.sqrt(
            np.square(self.car.hull.linearVelocity[0])
            + np.square(self.car.hull.linearVelocity[1])
        )

        # simple wrapper to render if the indicator value is above a threshold
        def render_if_min(value, points, color):
            if abs(value) > 1e-4:
                pygame.draw.polygon(self.surf, points=points, color=color)

        render_if_min(true_speed, vertical_ind(5, 0.02 * true_speed), (255, 255, 255))
        # ABS sensors
        render_if_min(
            self.car.wheels[0].omega,
            vertical_ind(7, 0.01 * self.car.wheels[0].omega),
            (0, 0, 255),
        )
        render_if_min(
            self.car.wheels[1].omega,
            vertical_ind(8, 0.01 * self.car.wheels[1].omega),
            (0, 0, 255),
        )
        render_if_min(
            self.car.wheels[2].omega,
            vertical_ind(9, 0.01 * self.car.wheels[2].omega),
            (51, 0, 255),
        )
        render_if_min(
            self.car.wheels[3].omega,
            vertical_ind(10, 0.01 * self.car.wheels[3].omega),
            (51, 0, 255),
        )

        render_if_min(
            self.car.wheels[0].joint.angle,
            horiz_ind(20, -10.0 * self.car.wheels[0].joint.angle),
            (0, 255, 0),
        )
        render_if_min(
            self.car.hull.angularVelocity,
            horiz_ind(30, -0.8 * self.car.hull.angularVelocity),
            (255, 0, 0),
        )

    def _draw_colored_polygon(self, surface, poly, color, zoom, translation, angle):
        import pygame
        from pygame import gfxdraw

        poly = [pygame.math.Vector2(c).rotate_rad(angle) for c in poly]
        poly = [
            (c[0] * zoom + translation[0], c[1] * zoom + translation[1]) for c in poly
        ]
        gfxdraw.aapolygon(self.surf, poly, color)
        gfxdraw.filled_polygon(self.surf, poly, color)

    def _create_image_array(self, screen, size):
        import pygame

        scaled_screen = pygame.transform.smoothscale(screen, size)
        return np.transpose(
            np.array(pygame.surfarray.pixels3d(scaled_screen)), axes=(1, 0, 2)
        )

    def close(self):
        if self.screen is not None:
            import pygame

            pygame.display.quit()
            self.isopen = False
            pygame.quit()
def init_controller(controller = "s"):
    import hid
    # hand controller
    if controller == "c":
        gamepad = hid.device()
        gamepad.open(0x2563,0x0575)

    # steering wheel
    if controller == "s":
        gamepad = hid.device(121,6244)
        gamepad.open(121,6244)

    gamepad.set_nonblocking(True)
    return gamepad

def controller_input(gamepad, a):
    steer_cap = 1.0
    report = gamepad.read(64)
    # steering wheel
    if report:
        if report[12] >100:
            print("RESTART EPISODE\n")
            global restart
            restart = True
            return a
        if report[11] >100:
            print("QUIT.....\n")
            env.close()
            return a   
        steer = ((report[3] - 128) / 127)
        # steer = np.tan(x)/(np.pi/2) * steer_cap
        gas = report[13]/255
        brake = report[14]/255
        a = [steer, gas, brake]
    # hand controller
    # if report:
    #     if report[12] >100:
    #         print("RESTART EPISODE\n")
    #         global restart
    #         restart = True
    #         return a
    #     if report[13] >100:
    #         print("QUIT.....\n")
    #         env.close()
    #         return a   
    #     x = ((report[3] - 127) / 127)
    #     steer = np.tan(x)/(np.pi/2) * steer_cap
    #     gas = max(0, -((report[6] - 128)/127))
    #     brake = max(0, ((report[6] - 128)/127))
    #     a = [steer, gas, brake]
    return a

def desired_input(d_actions, steps):
    a = []
    if steps > len(d_actions)-1:
        steps = len(d_actions)-1
    a = [d_actions['s'][steps], d_actions['g'][steps], d_actions['b'][steps]]
    return a

def log_simulation(actions, states, steps, a, env, total_reward, total_time):
    states.loc[steps] = [
        env.car.hull.position[0],
        env.car.hull.linearVelocity[0],
        env.car.hull.position[1],
        env.car.hull.linearVelocity[1],
        env.car.f_force,
        env.car.p_force,
        env.car.hull.angularVelocity,
        -env.car.hull.angle,
        total_reward,
        total_time
        ] 
    actions.loc[steps] = [a[0],a[1],a[2]]
    return actions, states

def register_input():
    for event in pygame.event.get():
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q:
                print("QUIT.....\n")
                env.close()
            if event.key == pygame.K_r:
                print("RESTART EPISODE\n")
                global restart
                restart = True
            if event.key == pygame.K_LEFT:
                a[0] = -1.0
            if event.key == pygame.K_RIGHT:
                a[0] = +1.0
            if event.key == pygame.K_UP:
                a[1] = +1.0
            if event.key == pygame.K_DOWN:
                a[2] = +0.8  # set 1.0 for wheels to block to zero rotation

        if event.type == pygame.KEYUP:
            if event.key == pygame.K_LEFT:
                a[0] = 0
            if event.key == pygame.K_RIGHT:
                a[0] = 0
            if event.key == pygame.K_UP:
                a[1] = 0
            if event.key == pygame.K_DOWN:
                a[2] = 0

def initial_speed(env, corner_num):
    env.car.gas(1)
    env.car.hull.linearVelocity[0], env.car.hull.linearVelocity[1] = corners[corner_num][2]
    env.render()
    return env

if __name__ == "__main__":
    a = np.array([0.0, 0.0, 0.0])
    import pygame
    import time
    import pandas as pd
    import sys

        # {10.0}    -> (85)->[58,125]   | (45)->[0,46]        | (35)->[310,348]    | (65)->[282,333]
        # {10.0v2}  -> (95)->[50,111]   | (110)->[250, 297]   | (130)->[128,181]   | 
        # {14.0}    -> (100)->[281,345] |

    corner_num = None
    controller = "k"
    global sim_params_path
    sim_params_path = None
    if len(sys.argv) > 1: 
        corner_num = int(sys.argv[1])
        if corner_num == -1:
            corner_num = None
            ZOOM = 0.2
        else:    
            if corner_num not in corners:
                print("'\033[91m'This corner is not included")
                exit
            else:
                SCALE = corners[corner_num][4]
                sim_params_path = corners[corner_num][5]
    if len(sys.argv) > 2: 
        controller = sys.argv[2]

    #Initialize controller
    if controller == "c":
        gamepad = init_controller()

    env = CarRacing(corner_num=corner_num, sim_params_path=sim_params_path)
    env.render()

    isopen = True
    episode = 0
    while isopen:
        env.reset()
        import pickle

        # # Save track and road polylines
        # with open("road_poly.pkl", "wb") as fp: 
        #     pickle.dump(env.road_poly, fp)
        # with open("track.pkl", "wb") as fp:  
        #     pickle.dump(env.track, fp)

        total_reward = 0.0
        total_time = 0.0
        steps = 0
        restart = False
        states = pd.DataFrame(columns=['x', 'vx', 'y', 'vy', 'f', 'p', 'w', 'd','r','t'])
        actions = pd.DataFrame(columns=['s', 'g', 'b'])
        
        #initial speed
        env = initial_speed(env, corner_num)
        while True:
            starttime = time.process_time()

            # Analog controller input
            if controller == "c":
                a = controller_input(gamepad, a)

                # Log actions and states of the simulation
                actions, states = log_simulation(actions, states, steps, a, env, total_reward, total_time)

            # Demonstrate desired actions
            elif controller == "d":
                d_actions = pd.read_pickle(f"{expert_data_actions}/actions_{str(corner_num)}.pkl")
                a = desired_input(d_actions, steps)
                actions, states = log_simulation(actions, states, steps, a, env, total_reward, total_time)
            # Keyborad control
            else:
                register_input()
                actions, states = log_simulation(actions, states, steps, a, env, total_reward, total_time)
            
            s, r, done, info = env.step(a)
            time.sleep(0.035)

            # Keep initial speed on the start of the simulation
            if steps < 25:
                env = initial_speed(env, corner_num)
            total_reward += r
            steps += 1
            isopen = env.render()
            if done or restart or isopen is False:
                break

            endtime = time.process_time()
            total_time += (endtime - starttime)
        print(f"Episode total simulation time: {total_time} sec\n")
        print(f"Storing.... \ttrajectory_{str(corner_num)}.pkl")
        states.to_pickle(f"{sim_data_states}states_{str(corner_num)}.pkl")  # THIS CAN BE CHANGED WITH SOMETHING FASTER
        print(f"Storing.... \tactions_{str(corner_num)}.pkl")
        actions.to_pickle(f"{sim_data_actions}actions_{str(corner_num)}.pkl")  # THIS CAN BE CHANGED WITH SOMETHING FASTER        
        
        # with open("./Corners Templates/corner"+str(corner_num)+".txt", "wb") as fp:   #Pickling
        #     pickle.dump(env.track, fp)
        
        print("Total reward in episode {} : {:+0.2f}\n".format(episode, total_reward))
        episode += 1
        if controller == "d":
            break    
    env.close()
