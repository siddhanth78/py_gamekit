"""Pygame input translated into one frame of game intent."""

from dataclasses import dataclass
import math

import pygame


@dataclass
class InputFrame:
    move_x: float = 0.0
    move_y: float = 0.0
    aim_x: float = 0.0
    aim_y: float = 0.0
    shooting: bool = False
    dash: bool = False
    restart: bool = False
    upgrade_choice: int | None = None
    click_pos: tuple[int, int] | None = None
    quit: bool = False


class InputHandler:
    def __init__(self):
        self.shooting = False

    def poll(self):
        frame = InputFrame()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                frame.quit = True
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    frame.quit = True
                elif event.key == pygame.K_SPACE:
                    frame.dash = True
                elif event.key == pygame.K_r:
                    frame.restart = True
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                    frame.upgrade_choice = event.key - pygame.K_1
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.shooting = True
                frame.click_pos = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                self.shooting = False

        keys = pygame.key.get_pressed()
        frame.move_x = float(keys[pygame.K_d] - keys[pygame.K_a])
        frame.move_y = float(keys[pygame.K_s] - keys[pygame.K_w])
        length = math.hypot(frame.move_x, frame.move_y)
        if length:
            frame.move_x /= length
            frame.move_y /= length
        frame.aim_x, frame.aim_y = pygame.mouse.get_pos()
        frame.shooting = self.shooting
        return frame
