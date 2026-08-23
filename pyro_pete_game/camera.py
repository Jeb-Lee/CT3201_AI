"""Simple camera that follows a target point and clamps to map bounds."""


class Camera:
    def __init__(self, screen_w, screen_h, map_w, map_h):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.map_w = map_w
        self.map_h = map_h
        self.x = 0.0
        self.y = 0.0

    def update(self, target_x, target_y):
        # center the camera on the target, then clamp so it never shows
        # past the edge of the map (or if the map is smaller than the
        # screen, keep it centered/pinned instead of jittering)
        self.x = target_x - self.screen_w / 2
        self.y = target_y - self.screen_h / 2

        max_x = max(0, self.map_w - self.screen_w)
        max_y = max(0, self.map_h - self.screen_h)
        self.x = max(0, min(self.x, max_x))
        self.y = max(0, min(self.y, max_y))

        if self.map_w < self.screen_w:
            self.x = -(self.screen_w - self.map_w) / 2
        if self.map_h < self.screen_h:
            self.y = -(self.screen_h - self.map_h) / 2

    @property
    def offset(self):
        return (self.x, self.y)
