"""
Easiest continuous control task to learn from pixels, a top-down racing
environment.
Discrete control is reasonable in this environment as well, on/off
discretization is fine.

State consists of STATE_W x STATE_H pixels.

The reward is -0.1 every frame and +1000/N for every track tile visited, where
N is the total number of tiles visited in the track. For example, if you have
finished in 732 frames, your reward is 1000 - 0.1*732 = 926.8 points.

The game is solved when the agent consistently gets 900+ points. The generated
track is random every episode.

The episode finishes when all the tiles are visited. The car also can go
outside of the PLAYFIELD -  that is far off the track, then it will get -100
and die.

Some indicators are shown at the bottom of the window along with the state RGB
buffer. From left to right: the true speed, four ABS sensors, the steering
wheel position and gyroscope.

To play yourself (it's rather fast for humans), type:

python gym/envs/box2d/car_racing.py

Remember it's a powerful rear-wheel drive car -  don't press the accelerator
and turn at the same time.

Created by Oleg Klimov. Licensed on the same terms as the rest of OpenAI Gym.
"""
import sys
import math
import numpy as np

import Box2D
from Box2D.b2 import fixtureDef
from Box2D.b2 import polygonShape
from Box2D.b2 import contactListener

import gym
from gym import spaces
from gym.envs.box2d.car_dynamics_modified import Car
from gym.utils import seeding, EzPickle

import pyglet
import pickle

pyglet.options["debug_gl"] = False
from pyglet import gl

STATE_W = 96  # less than Atari 160x192
STATE_H = 96
VIDEO_W = 600
VIDEO_H = 400
WINDOW_W = 800#1000
WINDOW_H = 700#800

SCALE = 10.0#6.0  # Track scale
TRACK_RAD = 900 / SCALE  # Track is heavily morphed circle with this radius
PLAYFIELD = 2000 / SCALE  # Game over boundary
FPS = 50 #50  # Frames per second
ZOOM = 1#0.13#1.5#2.7  # Camera zoom
ZOOM_FOLLOW = True  # Set to False for fixed view (don't use zoom)


TRACK_DETAIL_STEP = 21 / SCALE
TRACK_TURN_RATE = 0.31
TRACK_WIDTH = (40 / SCALE) * 2#1.25 #40 / SCALE
BORDER = 8 / SCALE
BORDER_MIN_COUNT = 4

ROAD_COLOR = [0.4, 0.4, 0.4]


class FrictionDetector(contactListener):
    def __init__(self, env):
        contactListener.__init__(self)
        self.env = env

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

        tile.color[0] = ROAD_COLOR[0]
        tile.color[1] = ROAD_COLOR[1]
        tile.color[2] = ROAD_COLOR[2]
        if not obj or "tiles" not in obj.__dict__:
            return
        if begin:
            obj.tiles.add(tile)
            if not tile.road_visited:
                tile.road_visited = True
                self.env.reward += 1000.0 / len(self.env.track)
                self.env.tile_visited_count += 1
        else:
            obj.tiles.remove(tile)


class CarRacing(gym.Env, EzPickle):
    metadata = {
        "render.modes": ["human", "rgb_array", "state_pixels"],
        "video.frames_per_second": FPS,
    }

    def __init__(self, verbose=1):
        EzPickle.__init__(self)
        self.seed()
        self.contactListener_keepref = FrictionDetector(self)
        self.world = Box2D.b2World((0, 0), contactListener=self.contactListener_keepref)
        self.viewer = None
        self.invisible_state_window = None
        self.invisible_video_window = None
        self.road = None
        self.car = None
        self.reward = 0.0
        self.prev_reward = 0.0
        self.last_tile = False
        self.verbose = verbose
        self.fd_tile = fixtureDef(
            shape=polygonShape(vertices=[(0, 0), (1, 0), (1, -1), (0, -1)])
        )

        self.action_space = spaces.Box(
            np.array([-1, 0, 0]), np.array([+1, +1, +1]), dtype=np.float32
        )  # steer, gas, brake

        self.observation_space = spaces.Box(
            low=0, high=255, shape=(STATE_H, STATE_W, 3), dtype=np.uint8
        )

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [1]#[seed]

    def _destroy(self):
        if not self.road:
            return
        for t in self.road:
            self.world.DestroyBody(t)
        self.road = []
        self.car.destroy()

    def _create_track(self):
        CHECKPOINTS = 12

# THIS PART FOR SAVING TRACK PARAMETERS        
        # noise_list = []
        # rad_list = []
        # # Create checkpoints
        # checkpoints = []
        # for c in range(CHECKPOINTS):
        #     noise = self.np_random.uniform(0, 2 * math.pi * 1 / CHECKPOINTS)
        #     alpha = 2 * math.pi * c / CHECKPOINTS + noise
        #     rad = self.np_random.uniform(TRACK_RAD / 3, TRACK_RAD)

        #     if c == 0:
        #         alpha = 0
        #         rad = 1.5 * TRACK_RAD
        #     if c == CHECKPOINTS - 1:
        #         alpha = 2 * math.pi * c / CHECKPOINTS
        #         self.start_alpha = 2 * math.pi * (-0.5) / CHECKPOINTS
        #         rad = 1.5 * TRACK_RAD
        #     noise_list.append(noise)
        #     rad_list.append(rad)
        #     checkpoints.append((alpha, rad * math.cos(alpha), rad * math.sin(alpha)))

        # with open('track_noise_parameters.txt', 'w') as f:
        #     for item in noise_list:
        #         f.write("%s\n" % item)
        #     f.close()
        # with open('track_rad_parameters.txt', 'w') as f:
        #     for item in rad_list:
        #         f.write("%s\n" % item)
        #     f.close()
# THIS PART FOR SAVING TRACK PARAMETERS 

# THIS PART FOR READING TRACK PARAMETERS
        #Create checkpoints
        # with open('./Simulation Parameters/desired_track_parameters.txt') as f:
        with open('./Simulation Parameters/desired2_track_parameters.txt') as f:
            lines = f.readlines()
            f.close()
        noise = [float(s.strip()) for s in lines[:12]]
        rad = [float(s.strip()) for s in lines[-12:]]
        checkpoints = []
        for c in range(CHECKPOINTS):
            alpha = 2 * math.pi * c / CHECKPOINTS + noise[c]
            if c == 0:
                alpha = 0
                rad[c] = 1.5 * TRACK_RAD
            if c == CHECKPOINTS - 1:
                alpha = 2 * math.pi * c / CHECKPOINTS
                self.start_alpha = 2 * math.pi * (-0.5) / CHECKPOINTS
                rad[c] = 1.5 * TRACK_RAD
            checkpoints.append((alpha, rad[c] * math.cos(alpha), rad[c] * math.sin(alpha)))
# THIS PART FOR READING TRACK PARAMETERS

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
        if self.verbose == 1:
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

        start_point, end_point = 50,111 #math.floor(0.2*len(track)), math.floor(0.35*len(track)) 
        # print(start_point,end_point)
        # track = track[start_point:end_point]
        for i in range(start_point,end_point): #range(len(track)):
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
            c = 0.01 * (i % 3)
            t.color = [ROAD_COLOR[0] + c, ROAD_COLOR[1] + c, ROAD_COLOR[2] + c]
            t.road_visited = False
            t.road_friction = 1.0
            t.fixtures[0].sensor = True
            self.road_poly.append(([road1_l, road1_r, road2_r, road2_l], t.color))
            self.road.append(t)
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
                    ([b1_l, b1_r, b2_r, b2_l], (1, 1, 1) if i % 2 == 0 else (1, 0, 0))
                )
        self.track = track[start_point:end_point] #track
        print(abs(self.track[0][1]-self.track[-1][1])*180/np.pi)
        return True

        #_____________________________________________________________________________________________________

    def reset(self):
        self._destroy()
        self.reward = 0.0
        self.prev_reward = 0.0
        self.tile_visited_count = 0
        self.t = 0.0
        self.road_poly = []

        while True:
            success = self._create_track()
            if success:
                break
            if self.verbose == 1:
                print(
                    "retry to generate track (normal if there are not many"
                    "instances of this message)"
                )
        self.car = Car(self.world, *self.track[0][1:4])

        return self.step(None)[0]

    def step(self, action):
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
        # last_tile = False
        if action is not None:  # First step without action, called from reset()
            self.reward -= 0.1
            # We actually don't want to count fuel spent, we want car to be faster.
            # self.reward -=  10 * self.car.fuel_spent / ENGINE_POWER
            self.car.fuel_spent = 0.0
            step_reward = self.reward - self.prev_reward
            self.prev_reward = self.reward
            if self.last_tile:
                done = True
                self.last_tile = False
            if self.tile_visited_count == len(self.track):
                if not done: 
                    self.last_tile = True
            x, y = self.car.hull.position
            if abs(x) > PLAYFIELD or abs(y) > PLAYFIELD:
                done = True
                step_reward = -100

        return self.state, step_reward, done, {}

    def render(self, mode="human"):
        assert mode in ["human", "state_pixels", "rgb_array"]
        if self.viewer is None:
            from gym.envs.classic_control import rendering

            self.viewer = rendering.Viewer(WINDOW_W, WINDOW_H)
            self.score_label = pyglet.text.Label(
                "0000",
                font_size=36,
                x=20,
                y=WINDOW_H * 2.5 / 40.00,
                anchor_x="left",
                anchor_y="center",
                color=(255, 0, 255, 255),
            )
            self.transform = rendering.Transform()

        if "t" not in self.__dict__:
            return  # reset() not called yet

        # Animate zoom first second:
        zoom = 0.1 * SCALE * max(1 - self.t, 0) + ZOOM * SCALE * min(self.t, 1)
        scroll_x = self.car.hull.position[0]
        scroll_y = self.car.hull.position[1]
        angle = -self.car.hull.angle
        vel = self.car.hull.linearVelocity
        if np.linalg.norm(vel) > 0.5:
            angle = math.atan2(vel[0], vel[1])
        self.transform.set_scale(zoom, zoom)
        self.transform.set_translation(
            WINDOW_W / 2
            - (scroll_x * zoom * math.cos(angle) - scroll_y * zoom * math.sin(angle)),
            WINDOW_H / 4
            - (scroll_x * zoom * math.sin(angle) + scroll_y * zoom * math.cos(angle)),
        )
        self.transform.set_rotation(angle)

        self.car.draw(self.viewer, mode != "state_pixels")

        arr = None
        win = self.viewer.window
        win.switch_to()
        win.dispatch_events()

        win.clear()
        t = self.transform
        if mode == "rgb_array":
            VP_W = VIDEO_W
            VP_H = VIDEO_H
        elif mode == "state_pixels":
            VP_W = STATE_W
            VP_H = STATE_H
        else:
            pixel_scale = 1
            if hasattr(win.context, "_nscontext"):
                pixel_scale = (
                    win.context._nscontext.view().backingScaleFactor()
                )  # pylint: disable=protected-access
            VP_W = int(pixel_scale * WINDOW_W)
            VP_H = int(pixel_scale * WINDOW_H)

        gl.glViewport(0, 0, VP_W, VP_H)
        t.enable()
        self.render_road()
        ######################## !!!!!!!!!!!!!!!!!!!!!!!!!!!! #############################
        # PLOT ON TRACK THE DESIRED TRAJECTORY
        # traj = pd.read_pickle('./DMPs/trajectory_1.pkl')
        # posx = traj['Position x']
        # posy = traj['Position y']
        # for i in range(len(posx)-1):
        #     self.viewer.draw_line((posx[i],posy[i]),(posx[i+1],posy[i+1]))
        # self.viewer.draw_line((posx[0],posy[0]),(posx[len(posx)-1],posy[len(posx)-1]))
        ####################### !!!!!!!!!!!!!!!!!!!!!!!!!!!! ##############################
        for geom in self.viewer.onetime_geoms:
            geom.render()
        self.viewer.onetime_geoms = []
        t.disable()
        self.render_indicators(WINDOW_W, WINDOW_H)

        if mode == "human":
            win.flip()
            return self.viewer.isopen

        image_data = (
            pyglet.image.get_buffer_manager().get_color_buffer().get_image_data()
        )
        arr = np.fromstring(image_data.get_data(), dtype=np.uint8, sep="")
        arr = arr.reshape(VP_H, VP_W, 4)
        arr = arr[::-1, :, 0:3]

        return arr

    def close(self):
        if self.viewer is not None:
            self.viewer.close()
            self.viewer = None

    def render_road(self):
        colors = [0.4, 0.8, 0.4, 1.0] * 4
        polygons_ = [
            +PLAYFIELD,
            +PLAYFIELD,
            0,
            +PLAYFIELD,
            -PLAYFIELD,
            0,
            -PLAYFIELD,
            -PLAYFIELD,
            0,
            -PLAYFIELD,
            +PLAYFIELD,
            0,
        ]

        k = PLAYFIELD / 20.0
        colors.extend([0.4, 0.9, 0.4, 1.0] * 4 * 20 * 20)
        for x in range(-20, 20, 2):
            for y in range(-20, 20, 2):
                polygons_.extend(
                    [
                        k * x + k,
                        k * y + 0,
                        0,
                        k * x + 0,
                        k * y + 0,
                        0,
                        k * x + 0,
                        k * y + k,
                        0,
                        k * x + k,
                        k * y + k,
                        0,
                    ]
                )

        for poly, color in self.road_poly:
            colors.extend([color[0], color[1], color[2], 1] * len(poly))
            for p in poly:
                polygons_.extend([p[0], p[1], 0])

        vl = pyglet.graphics.vertex_list(
            len(polygons_) // 3, ("v3f", polygons_), ("c4f", colors)  # gl.GL_QUADS,
        )
        vl.draw(gl.GL_QUADS)

    def render_indicators(self, W, H):
        s = W / 40.0
        h = H / 40.0
        colors = [0, 0, 0, 1] * 4
        polygons = [W, 0, 0, W, 5 * h, 0, 0, 5 * h, 0, 0, 0, 0]

        def vertical_ind(place, val, color):
            colors.extend([color[0], color[1], color[2], 1] * 4)
            polygons.extend(
                [
                    place * s,
                    h + h * val,
                    0,
                    (place + 1) * s,
                    h + h * val,
                    0,
                    (place + 1) * s,
                    h,
                    0,
                    (place + 0) * s,
                    h,
                    0,
                ]
            )

        def horiz_ind(place, val, color):
            colors.extend([color[0], color[1], color[2], 1] * 4)
            polygons.extend(
                [
                    (place + 0) * s,
                    4 * h,
                    0,
                    (place + val) * s,
                    4 * h,
                    0,
                    (place + val) * s,
                    2 * h,
                    0,
                    (place + 0) * s,
                    2 * h,
                    0,
                ]
            )

        true_speed = np.sqrt(
            np.square(self.car.hull.linearVelocity[0])
            + np.square(self.car.hull.linearVelocity[1])
        )

        vertical_ind(5, 0.02 * true_speed, (1, 1, 1))
        vertical_ind(7, 0.01 * self.car.wheels[0].omega, (0.0, 0, 1))  # ABS sensors
        vertical_ind(8, 0.01 * self.car.wheels[1].omega, (0.0, 0, 1))
        vertical_ind(9, 0.01 * self.car.wheels[2].omega, (0.2, 0, 1))
        vertical_ind(10, 0.01 * self.car.wheels[3].omega, (0.2, 0, 1))
        horiz_ind(20, -10.0 * self.car.wheels[0].joint.angle, (0, 1, 0))
        horiz_ind(30, -0.8 * self.car.hull.angularVelocity, (1, 0, 0))
        vl = pyglet.graphics.vertex_list(
            len(polygons) // 3, ("v3f", polygons), ("c4f", colors)  # gl.GL_QUADS,
        )
        vl.draw(gl.GL_QUADS)
        self.score_label.text = "%04i" % self.reward
        self.score_label.draw()


if __name__ == "__main__":
    import time
    from pyglet.window import key
    import pygame
    path = "C:/Users/Stelios/Desktop/Thesis/Project/Simulation Data/"
    a = np.array([0.0, 0.0, 0.0])


    # def returnInput(a):
    #     for event in pygame.event.get():
    #         if event.type != pygame.JOYAXISMOTION:
    #             continue            
            
    #         if event.axis == 1:
    #             a[1] = (event.value + 1)/(-2)+1
    #         elif event.axis == 0:
    #             a[0] = event.value/4
    #         elif event.axis == 2:
    #             a[2] = (event.value + 1)/(-2)+1

    #         # print(a)
    #     return a
    def returnInput(a):
        for event in pygame.event.get():
            if event.type != pygame.JOYAXISMOTION:
                continue            
            # print(event.value)
            if event.axis == 3 and event.value < 0:
                a[1] = -event.value#(event.value + 1)/(-2)+1
            elif event.axis == 0:
                a[0] = event.value/4
            elif event.axis == 3 and event.value > 0:
                # print(-event.value)
                a[2] = event.value#(event.value + 1)/(-2)+1

            # print(a)
        return a    
  
    def key_press(k, mod):
        global restart
        if k == key.ESCAPE:
            env.close()
        if k == key.R:
            restart = True
        # if k == 0xFF0D:
        #     restart = True
        if k == key.LEFT:
            a[0] = -1.0
        if k == key.RIGHT:
            a[0] = +1.0
        if k == key.UP:
            a[1] = +1.0
        if k == key.DOWN:
            a[2] = +0.8  # set 1.0 for wheels to block to zero rotation

    def key_release(k, mod):
        if k == key.LEFT and a[0] == -1.0:
            a[0] = 0
        if k == key.RIGHT and a[0] == +1.0:
            a[0] = 0
        if k == key.UP:
            a[1] = 0
        if k == key.DOWN:
            a[2] = 0

    ##### READ DESIRED ACTION INPUTS ####
    import pandas as pd
    corner_num = 95
    # d_actions = pd.read_pickle('./Simulation Data/actions_0.pkl')
    d_actions = pd.read_pickle('./Desired Data/actions_'+str(corner_num)+'.pkl')
    # print(d_actions.shape)
    import pygame
    # import matplotlib.pyplot as plt
    # import matplotlib.patches as mpatches

    # plt.plot(d_actions[:,0])
    # plt.plot(d_actions0['Steering Angle'])

    # red_patch = mpatches.Patch(color='blue', label='Primitive')
    # blue_patch = mpatches.Patch(color='orange', label='Ground Truth')

    # plt.legend(handles=[red_patch,blue_patch])
    # plt.show()

    # pygame.init()
    # pygame.joystick.init()

    # print(pygame.joystick.get_count())
    # joystick = pygame.joystick.Joystick(0)
    # joystick.init()
    # print(joystick.get_name())

    env = CarRacing()
    env.render()
    env.viewer.window.on_key_press = key_press
    env.viewer.window.on_key_release = key_release
    record_video = False
    if record_video:
        # from gym.wrappers.monitor import Monitor
        from gym.wrappers import Monitor
        env = Monitor(env, "./video-test", force=True)
    isopen = True
    episode = 0    
    while isopen:
        env.reset()
        total_reward = 0.0
        steps = 0
        ep_time = 0
        new_episode = False
        restart = False
        position = []
        velocity = []
        df = pd.DataFrame(columns=['Position x', 'Velocity x', 'Position y', 'Velocity y', 'Angular Velocity ω', 'Angle δ','Reward r','Timestep t'])
        actions = pd.DataFrame(columns=['Steering Angle', 'Gas', 'Brake'])
        
        prev_val = 0.0
        
        while True:
            starttime = time.process_time()
            df.loc[steps] = [env.car.hull.position[0],env.car.hull.linearVelocity[0],env.car.hull.position[1],env.car.hull.linearVelocity[1],env.car.hull.angularVelocity,-env.car.hull.angle,total_reward,ep_time] 
            actions.loc[steps] = [a[0],a[1],a[2]]
            # a = returnInput(a)
            if steps > len(d_actions)-1:
                steps = len(d_actions)-1
            a[0],a[1],a[2] = d_actions['Steering Angle'][steps], d_actions['Gas'][steps], d_actions['Brake'][steps]
            # a[0],a[1],a[2] = d_actions[:,0][steps], d_actions[:,1][steps], d_actions[:,2][steps]
            

            s, r, done, info = env.step(a)
            time.sleep(0.025)
            total_reward += r
            steps += 1
            isopen = env.render()
            if done or restart or isopen == False:
                break
        
            endtime = time.process_time()
            ep_time += (endtime - starttime)
        print("Episode total simulation time: ",ep_time, " sec")

        
        if restart == True:
            print("Restarting episode....")
            continue

        print("Storing.... ", 'trajectory_' + str(corner_num) + '.pkl' )
        df.to_pickle(path + 'trajectory_' + str(corner_num) + '.pkl')  # THIS CAN BE CHANGED WITH SOMETHING FASTER
        print("Storing.... ", 'actions_' + str(corner_num) + '.pkl' )
        actions.to_pickle(path + 'actions_' + str(corner_num) + '.pkl')  # THIS CAN BE CHANGED WITH SOMETHING FASTER        
        
        # with open("./Corners Templates/corner"+str(corner_num)+".txt", "wb") as fp:   #Pickling
        #     pickle.dump(env.track, fp)
        
        print("Total reward in episode {} : {:+0.2f}".format(episode, total_reward))
        episode += 1           
    env.close()
