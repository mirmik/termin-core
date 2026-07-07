#include <cmath>
#include <type_traits>

#include <tcbase/tc_types.h>
#include <termin/geom/color.hpp>
#include <termin/geom/ray3.hpp>
#include <termin/geom/bounds2.hpp>
#include <termin/geom/rect2.hpp>
#include <termin/geom/size2.hpp>

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

GUARD_TEST_MAIN();
