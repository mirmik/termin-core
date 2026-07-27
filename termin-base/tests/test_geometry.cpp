#include <cmath>
#include <type_traits>

#include <tcbase/tc_types.h>
#include <termin/geom/color.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/geom/ray3.hpp>
#include <termin/geom/bounds2.hpp>
#include <termin/geom/rect2.hpp>
#include <termin/geom/size2.hpp>
#include <termin/geom/world2d.hpp>

#include "guard_main.h"

TEST_CASE("tc_vec3 normalized zero vector returns NaNs") {
    tc_vec3 normalized = tc_vec3::zero().normalized();

    CHECK(std::isnan(normalized.x));
    CHECK(std::isnan(normalized.y));
    CHECK(std::isnan(normalized.z));
}

TEST_CASE("tc_vec3 normalized non-zero vector remains unit length") {
    tc_vec3 normalized = tc_vec3{3.0, 4.0, 0.0}.normalized();

    CHECK(std::abs(normalized.x - 0.6) < 1.0e-12);
    CHECK(std::abs(normalized.y - 0.8) < 1.0e-12);
    CHECK(std::abs(normalized.z) < 1.0e-12);
}

TEST_CASE("Ray3 is tc_ray3 alias and normalizes direction") {
    static_assert(std::is_same_v<termin::Ray3, tc_ray3>);

    termin::Ray3 ray{tc_vec3{1.0, 2.0, 3.0}, tc_vec3{0.0, 0.0, 2.0}};

    CHECK(std::abs(ray.direction.x) < 1.0e-12);
    CHECK(std::abs(ray.direction.y) < 1.0e-12);
    CHECK(std::abs(ray.direction.z - 1.0) < 1.0e-12);

    tc_vec3 point = ray.point_at(2.0);
    CHECK(std::abs(point.x - 1.0) < 1.0e-12);
    CHECK(std::abs(point.y - 2.0) < 1.0e-12);
    CHECK(std::abs(point.z - 5.0) < 1.0e-12);
}

TEST_CASE("base geometry value types preserve simple construction semantics") {
    static_assert(std::is_standard_layout_v<termin::Color4>);
    static_assert(std::is_standard_layout_v<termin::Size2i>);
    static_assert(std::is_standard_layout_v<termin::Bounds2i>);
    static_assert(std::is_standard_layout_v<termin::Bounds2f>);
    static_assert(std::is_standard_layout_v<termin::Rect2i>);
    static_assert(std::is_standard_layout_v<termin::Rect2f>);

    termin::Color4 color = termin::Color4::green();
    CHECK(color.r == 0.0f);
    CHECK(color.g == 1.0f);
    CHECK(color.b == 0.0f);
    CHECK(color.a == 1.0f);

    termin::Size2i size{320, 240};
    termin::Bounds2i rect = termin::Bounds2i::from_size(size);

    CHECK(size == termin::Size2i(320, 240));
    CHECK(rect.x0 == 0);
    CHECK(rect.y0 == 0);
    CHECK(rect.x1 == 320);
    CHECK(rect.y1 == 240);
    CHECK(rect.width() == 320);
    CHECK(rect.height() == 240);

    termin::Rect2i viewport{10, 20, 320, 240};
    CHECK(viewport.x == 10);
    CHECK(viewport.y == 20);
    CHECK(viewport.width == 320);
    CHECK(viewport.height == 240);

    termin::Rect2f rect_f{1.5f, 2.0f, 3.25f, 4.5f};
    termin::Bounds2f bounds_f = rect_f.bounds();
    CHECK(bounds_f.x0 == 1.5f);
    CHECK(bounds_f.y0 == 2.0f);
    CHECK(bounds_f.x1 == 4.75f);
    CHECK(bounds_f.y1 == 6.5f);
    CHECK(bounds_f.width() == 3.25f);
    CHECK(bounds_f.height() == 4.5f);
}

TEST_CASE("world2d maps double positions between Vec2 and the canonical XZ plane") {
    constexpr termin::Vec2 position_2d{2.5, -4.0};
    constexpr termin::Vec3 position_world =
        termin::world2d::position_to_world(position_2d, 7.25);

    static_assert(position_world.x == 2.5);
    static_assert(position_world.y == 7.25);
    static_assert(position_world.z == -4.0);

    constexpr termin::Vec2 round_trip =
        termin::world2d::position_from_world(position_world);
    static_assert(round_trip.x == position_2d.x);
    static_assert(round_trip.y == position_2d.y);
    static_assert(termin::world2d::depth_from_world(position_world) == 7.25);

    constexpr termin::Vec3 moved_in_depth =
        termin::world2d::with_world_depth(position_world, -3.0);
    static_assert(moved_in_depth.x == position_world.x);
    static_assert(moved_in_depth.y == -3.0);
    static_assert(moved_in_depth.z == position_world.z);

    CHECK(round_trip == position_2d);
}

TEST_CASE("world2d maps vectors without injecting world depth") {
    constexpr termin::Vec2 vector_2d{-1.5, 3.0};
    constexpr termin::Vec3 vector_world =
        termin::world2d::vector_to_world(vector_2d);

    static_assert(vector_world.x == -1.5);
    static_assert(vector_world.y == 0.0);
    static_assert(vector_world.z == 3.0);

    constexpr termin::Vec2 round_trip =
        termin::world2d::vector_from_world(vector_world);
    static_assert(round_trip.x == vector_2d.x);
    static_assert(round_trip.y == vector_2d.y);

    CHECK(round_trip == vector_2d);
}

TEST_CASE("world2d float helpers preserve the canonical basis and depth") {
    constexpr termin::Vec3 horizontal =
        termin::world2d::world_horizontal_axis();
    constexpr termin::Vec3 depth = termin::world2d::world_depth_axis();
    constexpr termin::Vec3 vertical =
        termin::world2d::world_vertical_axis();

    static_assert(horizontal.x == 1.0 && horizontal.y == 0.0 && horizontal.z == 0.0);
    static_assert(depth.x == 0.0 && depth.y == 1.0 && depth.z == 0.0);
    static_assert(vertical.x == 0.0 && vertical.y == 0.0 && vertical.z == 1.0);

    const termin::Vec2f position_2d{12.5f, -8.25f};
    const termin::Vec3f position_world =
        termin::world2d::position_to_world(position_2d, 4.5f);
    const termin::Vec2f round_trip =
        termin::world2d::position_from_world(position_world);
    const termin::Vec3f moved_in_depth =
        termin::world2d::with_world_depth(position_world, -2.0f);

    CHECK(position_world.x == 12.5f);
    CHECK(position_world.y == 4.5f);
    CHECK(position_world.z == -8.25f);
    CHECK(round_trip.x == position_2d.x);
    CHECK(round_trip.y == position_2d.y);
    CHECK(termin::world2d::depth_from_world(position_world) == 4.5f);
    CHECK(moved_in_depth.x == position_world.x);
    CHECK(moved_in_depth.y == -2.0f);
    CHECK(moved_in_depth.z == position_world.z);

    const termin::Vec3f vector_world =
        termin::world2d::vector_to_world(termin::Vec2f{2.0f, 6.0f});
    const termin::Vec2f vector_round_trip =
        termin::world2d::vector_from_world(vector_world);
    CHECK(vector_world.y == 0.0f);
    CHECK(vector_round_trip.x == 2.0f);
    CHECK(vector_round_trip.y == 6.0f);

    CHECK(round_trip == position_2d);
}

TEST_CASE("world2d canonical camera and sprite face each other along world Y") {
    constexpr termin::Vec3 camera_forward =
        termin::world2d::canonical_camera_forward_axis();
    constexpr termin::Vec3 sprite_front =
        termin::world2d::canonical_sprite_front_axis();

    static_assert(camera_forward.x == 0.0);
    static_assert(camera_forward.y == 1.0);
    static_assert(camera_forward.z == 0.0);
    static_assert(sprite_front.x == 0.0);
    static_assert(sprite_front.y == -1.0);
    static_assert(sprite_front.z == 0.0);
    static_assert(
        termin::world2d::positive_rotation_axis().y == sprite_front.y);

    CHECK(camera_forward.dot(sprite_front) == -1.0);
}

TEST_CASE("look_at preserves the Y-forward Z-up camera convention") {
    const termin::Vec3 eye{0.0, -2.0, 0.0};
    const termin::Vec3 target{0.0, 0.0, 0.0};
    const termin::Vec3 world_up{0.0, 0.0, 1.0};

    const termin::Mat44 view = termin::Mat44::look_at(eye, target, world_up);
    const termin::Vec3 eye_view = view.transform_point(eye);
    const termin::Vec3 target_view = view.transform_point(target);
    const termin::Vec3 up_view =
        view.transform_point(target + world_up);

    CHECK((eye_view - termin::Vec3{0.0, 0.0, 0.0}).norm() < 1.0e-12);
    CHECK((target_view - termin::Vec3{0.0, 2.0, 0.0}).norm() < 1.0e-12);
    CHECK((up_view - termin::Vec3{0.0, 2.0, 1.0}).norm() < 1.0e-12);

    const termin::Mat44f view_f = termin::Mat44f::look_at(eye, target, world_up);
    const termin::Vec3 target_view_f = view_f.transform_point(target);
    const termin::Vec3 up_view_f =
        view_f.transform_point(target + world_up);
    CHECK((target_view_f - termin::Vec3{0.0, 2.0, 0.0}).norm() < 1.0e-6);
    CHECK((up_view_f - termin::Vec3{0.0, 2.0, 1.0}).norm() < 1.0e-6);
}

TEST_CASE("world2d positive angle is counter-clockwise in the visible XZ plane") {
    constexpr double half_pi = 1.57079632679489661923;
    const termin::Quat rotation =
        termin::world2d::rotation_to_world(half_pi);
    const termin::Vec3 rotated_horizontal =
        rotation.rotate(termin::world2d::world_horizontal_axis());

    CHECK(std::abs(rotated_horizontal.x) < 1.0e-12);
    CHECK(std::abs(rotated_horizontal.y) < 1.0e-12);
    CHECK(std::abs(rotated_horizontal.z - 1.0) < 1.0e-12);
}

TEST_CASE("world2d canonical quad has logical CCW winding toward the camera") {
    constexpr termin::Vec3 bottom_left{-1.0, 0.0, -1.0};
    constexpr termin::Vec3 bottom_right{1.0, 0.0, -1.0};
    constexpr termin::Vec3 top_right{1.0, 0.0, 1.0};

    const termin::Vec3 normal =
        (bottom_right - bottom_left).cross(top_right - bottom_left).normalized();
    const termin::Vec3 sprite_front =
        termin::world2d::canonical_sprite_front_axis();

    CHECK(std::abs(normal.x - sprite_front.x) < 1.0e-12);
    CHECK(std::abs(normal.y - sprite_front.y) < 1.0e-12);
    CHECK(std::abs(normal.z - sprite_front.z) < 1.0e-12);
}

GUARD_TEST_MAIN();
