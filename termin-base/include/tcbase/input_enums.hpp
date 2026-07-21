// Input event enums shared between termin libraries.

#pragma once

namespace tcbase {

// Mouse button values shared by window, input, UI, and editor layers.
// Keep the numeric values stable: they cross C ABI and serialized event boundaries.
enum class MouseButton : int {
    NONE = -1,
    LEFT = 0,
    RIGHT = 1,
    MIDDLE = 2,
    OTHER = 3,
};

constexpr int mouse_button_value(MouseButton button) {
    return static_cast<int>(button);
}

// Action enum.
enum class Action : int {
    RELEASE = 0,
    PRESS = 1,
    REPEAT = 2
};

// Modifier key flags enum.
enum class Mods : int {
    SHIFT = 1,
    CTRL = 2,
    ALT = 4,
    SUPER = 8
};

} // namespace tcbase
