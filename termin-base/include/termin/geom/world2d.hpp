#pragma once

#include "vec2.hpp"
#include "vec3.hpp"

namespace termin::world2d {

// Canonical Termin world-space basis for 2D gameplay:
//   Vec2.x -> world X (horizontal)
//   depth  -> world Y
//   Vec2.y -> world Z (vertical, Z-up)
//
// Camera-facing direction and positive rotation are intentionally not encoded
// here. They belong to the separate 2D viewing/orientation contract.

constexpr Vec3 world_horizontal_axis() noexcept {
    return {1.0, 0.0, 0.0};
}

constexpr Vec3 world_depth_axis() noexcept {
    return {0.0, 1.0, 0.0};
}

constexpr Vec3 world_vertical_axis() noexcept {
    return {0.0, 0.0, 1.0};
}

constexpr Vec3 position_to_world(const Vec2& position, double depth = 0.0) noexcept {
    return {position.x, depth, position.y};
}

inline Vec3f position_to_world(const Vec2f& position, float depth = 0.0f) noexcept {
    return {position.x, depth, position.y};
}

constexpr Vec2 position_from_world(const Vec3& position) noexcept {
    return {position.x, position.z};
}

inline Vec2f position_from_world(const Vec3f& position) noexcept {
    return {position.x, position.z};
}

constexpr Vec3 vector_to_world(const Vec2& vector) noexcept {
    return {vector.x, 0.0, vector.y};
}

inline Vec3f vector_to_world(const Vec2f& vector) noexcept {
    return {vector.x, 0.0f, vector.y};
}

constexpr Vec2 vector_from_world(const Vec3& vector) noexcept {
    return {vector.x, vector.z};
}

inline Vec2f vector_from_world(const Vec3f& vector) noexcept {
    return {vector.x, vector.z};
}

constexpr double depth_from_world(const Vec3& position) noexcept {
    return position.y;
}

inline float depth_from_world(const Vec3f& position) noexcept {
    return position.y;
}

constexpr Vec3 with_world_depth(const Vec3& position, double depth) noexcept {
    return {position.x, depth, position.z};
}

inline Vec3f with_world_depth(const Vec3f& position, float depth) noexcept {
    return {position.x, depth, position.z};
}

} // namespace termin::world2d
