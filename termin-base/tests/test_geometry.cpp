#include <cmath>
#include <type_traits>

#include <tcbase/tc_types.h>
#include <termin/geom/color.hpp>
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

GUARD_TEST_MAIN();
