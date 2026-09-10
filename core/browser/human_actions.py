import math
import random
import asyncio
import logging
from typing import Tuple, List, Optional, Union
from playwright.async_api import Page, Locator

logger = logging.getLogger("HumanActions")

# Mapping of adjacent keys for realistic typo simulation (covers both AZERTY and QWERTY common mistypes)
KEY_NEIGHBORS = {
    'a': ['q', 'z', 'w', 's'],
    'b': ['v', 'g', 'h', 'n'],
    'c': ['x', 'd', 'f', 'v'],
    'd': ['s', 'e', 'r', 'f', 'c', 'x'],
    'e': ['w', 'r', 'd', 's', 'z'],
    'f': ['d', 'r', 't', 'g', 'v', 'c'],
    'g': ['f', 't', 'y', 'h', 'b', 'v'],
    'h': ['g', 'y', 'u', 'j', 'n', 'b'],
    'i': ['u', 'o', 'k', 'j'],
    'j': ['h', 'u', 'i', 'k', 'n', 'm'],
    'k': ['j', 'i', 'o', 'l', 'm'],
    'l': ['k', 'o', 'p', 'm'],
    'm': ['l', 'p', 'j', 'k'],
    'n': ['b', 'h', 'j', 'm'],
    'o': ['i', 'p', 'l', 'k'],
    'p': ['o', 'l'],
    'q': ['a', 'w', 's'],
    'r': ['e', 't', 'f', 'd'],
    's': ['a', 'w', 'e', 'd', 'x', 'z', 'q'],
    't': ['r', 'y', 'g', 'f'],
    'u': ['y', 'i', 'j', 'h'],
    'v': ['c', 'f', 'g', 'b'],
    'w': ['q', 'a', 's', 'e'],
    'x': ['z', 's', 'd', 'c'],
    'y': ['t', 'u', 'h', 'g'],
    'z': ['a', 's', 'x', 'e'],
}


def _bezier_point(p0: Tuple[float, float], p1: Tuple[float, float], 
                  p2: Tuple[float, float], p3: Tuple[float, float], t: float) -> Tuple[float, float]:
    """Calculates a point along a cubic Bézier curve at parameter t (0 <= t <= 1)."""
    u = 1 - t
    tt = t * t
    uu = u * u
    uuu = uu * u
    ttt = tt * t

    x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
    y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
    return (x, y)


def generate_bezier_trajectory(start: Tuple[float, float], target: Tuple[float, float], 
                               steps: int = 30) -> List[Tuple[float, float]]:
    """
    Generates a realistic curved trajectory between start and target points with natural
    acceleration, deceleration, and micro-jitter.
    """
    dx = target[0] - start[0]
    dy = target[1] - start[1]
    dist = math.hypot(dx, dy)

    if dist < 5:
        return [target]

    # Calculate control points with natural deviations
    deviation = min(max(dist * 0.25, 20), 120)
    angle = math.atan2(dy, dx)
    perp_angle = angle + math.pi / 2 if random.random() < 0.5 else angle - math.pi / 2

    # First control point
    ctrl1_dist = dist * random.uniform(0.2, 0.4)
    ctrl1_offset = random.uniform(deviation * 0.4, deviation)
    p1 = (
        start[0] + math.cos(angle) * ctrl1_dist + math.cos(perp_angle) * ctrl1_offset,
        start[1] + math.sin(angle) * ctrl1_dist + math.sin(perp_angle) * ctrl1_offset
    )

    # Second control point
    ctrl2_dist = dist * random.uniform(0.6, 0.8)
    ctrl2_offset = random.uniform(deviation * 0.2, deviation * 0.8)
    p2 = (
        start[0] + math.cos(angle) * ctrl2_dist + math.cos(perp_angle) * ctrl2_offset,
        start[1] + math.sin(angle) * ctrl2_dist + math.sin(perp_angle) * ctrl2_offset
    )

    points = []
    for i in range(1, steps + 1):
        # Ease in-out parameter
        raw_t = i / steps
        # Smooth step function: 3*t^2 - 2*t^3
        t = 3 * (raw_t ** 2) - 2 * (raw_t ** 3)
        bx, by = _bezier_point(start, p1, p2, target, t)
        
        # Add tiny human hand micro-jitter (except at very end)
        if i < steps:
            jitter_x = random.gauss(0, 0.6)
            jitter_y = random.gauss(0, 0.6)
            points.append((bx + jitter_x, by + jitter_y))
        else:
            points.append((bx, by))

    return points


class HumanActions:
    """Provides ultra-realistic human-like mouse, keyboard and reading interactions."""

    def __init__(self, page: Page):
        self.page = page
        self.cursor_x: float = random.uniform(100, 300)
        self.cursor_y: float = random.uniform(100, 300)

    async def move_mouse(self, target_x: float, target_y: float, steps: Optional[int] = None):
        """Moves mouse cursor along a smooth cubic Bézier trajectory with variable speed."""
        dist = math.hypot(target_x - self.cursor_x, target_y - self.cursor_y)
        if steps is None:
            # More steps for longer distances, minimum 15
            steps = max(15, min(60, int(dist / 18)))

        trajectory = generate_bezier_trajectory(
            (self.cursor_x, self.cursor_y), 
            (target_x, target_y), 
            steps=steps
        )

        for pt in trajectory:
            await self.page.mouse.move(pt[0], pt[1])
            # Sleep slightly between micro-steps to simulate smooth real-time travel
            await asyncio.sleep(random.uniform(0.006, 0.016))

        self.cursor_x = target_x
        self.cursor_y = target_y

    async def move_to_element(self, locator: Locator) -> Tuple[float, float]:
        """Scrolls element into view smoothly and moves mouse naturally to it with slight random offset."""
        await locator.scroll_into_view_if_needed()
        box = await locator.bounding_box()
        if not box:
            return (self.cursor_x, self.cursor_y)

        # Target slightly off-center (humans rarely click exact center)
        margin_x = box["width"] * 0.2
        margin_y = box["height"] * 0.2
        target_x = box["x"] + box["width"] / 2 + random.uniform(-margin_x, margin_x)
        target_y = box["y"] + box["height"] / 2 + random.uniform(-margin_y, margin_y)

        await self.move_mouse(target_x, target_y)
        return (target_x, target_y)

    async def click(self, selector_or_locator: Union[str, Locator], hover_pause: bool = True):
        """
        Executes a 100% human click:
        1. Natural Bézier mouse travel to element
        2. Brief hesitation/hover pause (120ms - 350ms)
        3. Mouse down
        4. Realistic press duration (60ms - 130ms)
        5. Mouse up
        6. Brief post-click settling pause (150ms - 350ms)
        """
        locator = self.page.locator(selector_or_locator) if isinstance(selector_or_locator, str) else selector_or_locator
        await locator.wait_for(state="visible", timeout=15000)

        # Move mouse realistically
        await self.move_to_element(locator)

        # Human hover hesitation
        if hover_pause:
            await asyncio.sleep(random.uniform(0.12, 0.35))

        # Human click timing: down -> hold -> up
        await self.page.mouse.down()
        await asyncio.sleep(random.uniform(0.06, 0.13))
        await self.page.mouse.up()

        # Post-click pause
        await asyncio.sleep(random.uniform(0.15, 0.35))

    async def type(self, selector_or_locator: Union[str, Locator], text: str, 
                   with_typos: bool = True, clear_first: bool = True):
        """
        Types text like a real human:
        - Clicks into the field naturally
        - Variable keystroke latencies (gaussian distribution)
        - Punctuation reflection pauses (commas, periods, question marks)
        - Occasional realistic typos (2-3% chance) on neighboring keys immediately corrected with Backspace
        """
        locator = self.page.locator(selector_or_locator) if isinstance(selector_or_locator, str) else selector_or_locator
        await locator.wait_for(state="visible", timeout=15000)

        # Click input field naturally
        await self.click(locator, hover_pause=False)
        await asyncio.sleep(random.uniform(0.15, 0.3))

        if clear_first:
            # Human clear: Ctrl+A or Cmd+A then Backspace
            await self.page.keyboard.press("Meta+A")
            await asyncio.sleep(random.uniform(0.05, 0.12))
            await self.page.keyboard.press("Backspace")
            await asyncio.sleep(random.uniform(0.1, 0.2))

        chars = list(text)
        i = 0
        while i < len(chars):
            ch = chars[i]
            lower_ch = ch.lower()

            # Random typo chance (approx 2.5% on alphabetic characters)
            if with_typos and lower_ch in KEY_NEIGHBORS and random.random() < 0.025:
                # Type wrong character
                wrong_char = random.choice(KEY_NEIGHBORS[lower_ch])
                if ch.isupper():
                    wrong_char = wrong_char.upper()
                
                await self.page.keyboard.type(wrong_char, delay=random.randint(40, 90))
                # Notice mistake pause (120ms - 280ms)
                await asyncio.sleep(random.uniform(0.12, 0.28))
                # Press Backspace to correct
                await self.page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.08, 0.2))

            # Base typing delay (average 65-110ms per keystroke)
            press_delay = int(random.gauss(80, 25))
            press_delay = max(35, min(190, press_delay))
            await self.page.keyboard.type(ch, delay=press_delay)

            # Reflection pauses after punctuation
            if ch in [',', ';']:
                await asyncio.sleep(random.uniform(0.18, 0.45))
            elif ch in ['.', '!', '?']:
                await asyncio.sleep(random.uniform(0.35, 0.75))
            elif ch == ' ' and random.random() < 0.15:
                # Brief thought pause between words
                await asyncio.sleep(random.uniform(0.12, 0.32))

            i += 1

        # Pause after finishing input
        await asyncio.sleep(random.uniform(0.25, 0.6))

    async def scroll_and_read(self, min_seconds: float = 2.0, max_seconds: float = 4.5):
        """
        Simulates a human reading a job description or application form:
        - Smooth gradual mousewheel scrolling downwards in readable chunks
        - Pauses between scrolls to simulate reading paragraphs
        - Occasional small scroll back up (15% chance) as humans re-read requirements
        """
        total_reading_time = random.uniform(min_seconds, max_seconds)
        elapsed = 0.0

        while elapsed < total_reading_time:
            # Scroll distance (120px to 320px)
            delta_y = random.randint(120, 320)
            
            # 15% chance of scrolling back up slightly
            if random.random() < 0.15 and elapsed > 1.0:
                delta_y = -random.randint(80, 180)

            # Simulate natural wheel steps
            sub_steps = 4
            for _ in range(sub_steps):
                await self.page.mouse.wheel(0, delta_y / sub_steps)
                await asyncio.sleep(0.03)

            # Reading pause on this section
            pause = random.uniform(0.6, 1.4)
            await asyncio.sleep(pause)
            elapsed += pause + 0.12

        logger.debug(f"Simulated human reading for {elapsed:.1f}s")

    async def select_option(self, selector_or_locator: Union[str, Locator], value: str):
        """Selects an option in a standard <select> element with human click sequence."""
        locator = self.page.locator(selector_or_locator) if isinstance(selector_or_locator, str) else selector_or_locator
        await self.click(locator)
        await asyncio.sleep(random.uniform(0.2, 0.4))
        await locator.select_option(value)
        await asyncio.sleep(random.uniform(0.2, 0.45))

    async def upload_file(self, file_input_locator: Locator, file_path: str):
        """Simulates human file upload with realistic delay."""
        await asyncio.sleep(random.uniform(0.4, 0.9))
        await file_input_locator.set_input_files(file_path)
        await asyncio.sleep(random.uniform(0.8, 1.8))
