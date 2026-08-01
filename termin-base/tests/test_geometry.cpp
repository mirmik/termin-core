#include <cmath>
#include <random>
#include <type_traits>

#include <tcbase/tc_types.h>
#include <termin/geom/affine2.hpp>
#include <termin/geom/affine3.hpp>
#include <termin/geom/color.hpp>
#include <termin/geom/mat44.hpp>
#include <termin/geom/mat66.hpp>
#include <termin/geom/vec6.hpp>
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

TEST_CASE("Mat66 follows the canonical column-major matrix contract")
{
    termin::Mat66 matrix;
    matrix(2, 4) = 7.5;

    CHECK(matrix.ptr()[2 * 6 + 4] == 7.5);
    CHECK(matrix(2, 4) == 7.5);
    CHECK(matrix(4, 2) == 0.0);

    const termin::Mat66 identity = termin::Mat66::identity();
    const termin::Mat66 product = matrix * identity;
    CHECK(product(2, 4) == 7.5);

    const termin::Mat66 transposed = matrix.transposed();
    CHECK(transposed(4, 2) == 7.5);

    const termin::Vec6 vector{1.0, 2.0, 3.0, 4.0, 5.0, 6.0};
    const termin::Vec6 transformed = matrix.transform(vector);
    CHECK(transformed[4] == 22.5);
}

TEST_CASE("Vec6 provides contiguous fixed-size vector operations")
{
    const termin::Vec6 left{1.0, 2.0, 3.0, 4.0, 5.0, 6.0};
    const termin::Vec6 right{6.0, 5.0, 4.0, 3.0, 2.0, 1.0};

    CHECK(left.ptr()[3] == 4.0);
    CHECK(left.dot(right) == 56.0);
    CHECK(left.norm_squared() == 91.0);
    const termin::Vec6 sum{7.0, 7.0, 7.0, 7.0, 7.0, 7.0};
    CHECK((left + right) == sum);
    CHECK((left * 2.0)[5] == 12.0);
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
    static_assert(std::is_same_v<termin::Vec2f, tc_vec2f>);
    static_assert(std::is_same_v<termin::Size2f, tc_size2f>);
    static_assert(std::is_same_v<termin::Bounds2f, tc_bounds2f>);
    static_assert(std::is_same_v<termin::Rect2f, tc_rect2f>);
    static_assert(std::is_same_v<termin::Affine2f, tc_affine2f>);
    static_assert(std::is_same_v<termin::Basis3d, tc_basis3d>);
    static_assert(std::is_same_v<termin::Affine3d, tc_affine3d>);
    static_assert(std::is_standard_layout_v<termin::Size2i>);
    static_assert(std::is_standard_layout_v<termin::Size2f>);
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

    termin::Size2f size_f{640.0f, 480.0f};
    CHECK(size_f == termin::Size2f(640.0f, 480.0f));
}

TEST_CASE("Affine2f composes arbitrary affine transforms exactly") {
    constexpr float half_pi = 1.57079632679489661923f;
    const termin::Affine2f parent =
        termin::Affine2f::translation(5.0f, -3.0f)
        * termin::Affine2f::scaling(2.0f, 0.5f);
    const termin::Affine2f child =
        termin::Affine2f::rotation(half_pi / 2.0f)
        * termin::Affine2f::shear(0.25f, -0.4f);
    const termin::Vec2f point{3.0f, -2.0f};

    const termin::Vec2f sequential =
        parent.transform_point(child.transform_point(point));
    const termin::Vec2f composed = (parent * child).transform_point(point);

    CHECK(std::abs(composed.x - sequential.x) < 1.0e-5f);
    CHECK(std::abs(composed.y - sequential.y) < 1.0e-5f);

    const termin::Affine2f third =
        termin::Affine2f::trs({-1.0f, 4.0f}, -0.3f, {-2.0f, 1.25f});
    const termin::Vec2f left = ((parent * child) * third).transform_point(point);
    const termin::Vec2f right = (parent * (child * third)).transform_point(point);
    CHECK(std::abs(left.x - right.x) < 1.0e-5f);
    CHECK(std::abs(left.y - right.y) < 1.0e-5f);
}

TEST_CASE("Affine2f inverse is explicit and round trips reflections") {
    const termin::Affine2f affine =
        termin::Affine2f::translation(7.0f, -5.0f)
        * termin::Affine2f::rotation(0.37f)
        * termin::Affine2f::scaling(-2.0f, 0.75f)
        * termin::Affine2f::shear(0.3f, -0.2f);
    termin::Affine2f inverse;
    CHECK(affine.try_inverse(inverse));

    const termin::Vec2f point{8.0f, -1.5f};
    const termin::Vec2f round_trip =
        inverse.transform_point(affine.transform_point(point));
    CHECK(std::abs(round_trip.x - point.x) < 1.0e-4f);
    CHECK(std::abs(round_trip.y - point.y) < 1.0e-4f);

    termin::Affine2f unchanged = termin::Affine2f::translation(9.0f, 11.0f);
    const termin::Affine2f singular = termin::Affine2f::scaling(0.0f, 2.0f);
    CHECK(!singular.try_inverse(unchanged));
    CHECK(unchanged.tx == 9.0f);
    CHECK(unchanged.ty == 11.0f);
}

TEST_CASE("Affine2f transforms all bounds corners") {
    const termin::Affine2f affine =
        termin::Affine2f::rotation(0.5f)
        * termin::Affine2f::shear(0.6f, -0.25f);
    const termin::Bounds2f bounds{-2.0f, -1.0f, 3.0f, 4.0f};
    const termin::Bounds2f transformed = affine.transform_bounds(bounds);

    const termin::Vec2f corners[] = {
        {-2.0f, -1.0f},
        {3.0f, -1.0f},
        {-2.0f, 4.0f},
        {3.0f, 4.0f},
    };
    for (const termin::Vec2f& corner : corners) {
        const termin::Vec2f p = affine.transform_point(corner);
        CHECK(p.x >= transformed.x0 - 1.0e-5f);
        CHECK(p.x <= transformed.x1 + 1.0e-5f);
        CHECK(p.y >= transformed.y0 - 1.0e-5f);
        CHECK(p.y <= transformed.y1 + 1.0e-5f);
    }
}

TEST_CASE("Affine2f conversion preserves the rigid Pose2 contract") {
    const termin::Pose2 pose{0.75, {4.0, -6.0}};
    const termin::Affine2f affine = termin::Affine2f::from_pose2(pose);
    const termin::Vec2f point{2.0f, 3.0f};
    const termin::Vec2 pose_result =
        pose.transform_point(point.to_double());
    const termin::Vec2f affine_result = affine.transform_point(point);

    CHECK(std::abs(affine_result.x - static_cast<float>(pose_result.x)) < 1.0e-5f);
    CHECK(std::abs(affine_result.y - static_cast<float>(pose_result.y)) < 1.0e-5f);
}

namespace {

bool affine3_near_vec(
    const termin::Vec3& a,
    const termin::Vec3& b,
    double epsilon = 1.0e-10) {
    return std::abs(a.x - b.x) <= epsilon
        && std::abs(a.y - b.y) <= epsilon
        && std::abs(a.z - b.z) <= epsilon;
}

} // namespace

TEST_CASE("Affine3d preserves hierarchy-generated shear exactly") {
    const termin::Affine3d parent =
        termin::Affine3d::from_translation(5.0, -3.0, 2.0)
        * termin::Affine3d::scaling(2.0, 0.5, 1.25);
    const termin::Affine3d child = termin::Affine3d::trs(
        {-1.0, 4.0, 0.75},
        termin::Quat::from_axis_angle(termin::Vec3::unit_z(), 0.63),
        {0.8, 1.4, 2.0});
    const termin::Affine3d composed = parent * child;
    const termin::Vec3 point{3.0, -2.0, 1.5};

    CHECK(affine3_near_vec(
        composed.transform_point(point),
        parent.transform_point(child.transform_point(point))));
    CHECK(std::abs(composed.basis.x.dot(composed.basis.y)) > 1.0e-3);

    double matrix[16];
    composed.matrix4(matrix);
    termin::Affine3d from_matrix;
    CHECK(termin::Affine3d::try_from_matrix4(matrix, from_matrix));
    CHECK(affine3_near_vec(
        from_matrix.transform_point(point),
        composed.transform_point(point)));
}

TEST_CASE("Affine3d TRS conversion matches the existing public matrix convention") {
    const termin::GeneralPose3 pose{
        termin::Quat::from_axis_angle(
            termin::Vec3{0.2, -0.4, 0.7}.normalized(),
            0.83),
        {4.0, -6.0, 2.5},
        {-2.0, 0.75, 1.5}};
    const termin::Affine3d affine =
        termin::Affine3d::from_general_pose3(pose);

    double expected[16];
    double actual[16];
    pose.matrix4(expected);
    affine.matrix4(actual);
    for (int i = 0; i < 16; ++i) {
        CHECK(std::abs(actual[i] - expected[i]) < 1.0e-12);
    }

    const termin::Vec3 point{1.5, -2.0, 0.25};
    CHECK(affine3_near_vec(
        affine.transform_point(point),
        pose.transform_point(point),
        1.0e-12));
}

TEST_CASE("Affine3d randomized composition and inverse match sequential transforms") {
    std::mt19937_64 rng(0xAFF13DULL);
    std::uniform_real_distribution<double> position(-10.0, 10.0);
    std::uniform_real_distribution<double> axis_component(-1.0, 1.0);
    std::uniform_real_distribution<double> angle(-3.0, 3.0);
    std::uniform_real_distribution<double> positive_scale(0.25, 3.0);

    auto random_affine = [&]() {
        termin::Vec3 axis{
            axis_component(rng),
            axis_component(rng),
            axis_component(rng)};
        if (axis.norm_squared() < 1.0e-6) {
            axis = termin::Vec3::unit_x();
        } else {
            axis = axis.normalized();
        }

        termin::Vec3 scale{
            positive_scale(rng),
            positive_scale(rng),
            positive_scale(rng)};
        if ((rng() & 1U) != 0U) {
            scale.x = -scale.x;
        }
        if ((rng() & 2U) != 0U) {
            scale.y = -scale.y;
        }

        return termin::Affine3d::trs(
            {position(rng), position(rng), position(rng)},
            termin::Quat::from_axis_angle(axis, angle(rng)),
            scale);
    };

    for (int iteration = 0; iteration < 256; ++iteration) {
        const termin::Affine3d first = random_affine();
        const termin::Affine3d second = random_affine();
        const termin::Affine3d third = random_affine();
        const termin::Vec3 point{
            position(rng),
            position(rng),
            position(rng)};
        const termin::Vec3 vector{
            axis_component(rng),
            axis_component(rng),
            axis_component(rng)};

        const termin::Affine3d composed = first * second;
        CHECK(affine3_near_vec(
            composed.transform_point(point),
            first.transform_point(second.transform_point(point)),
            1.0e-9));
        CHECK(affine3_near_vec(
            composed.transform_vector(vector),
            first.transform_vector(second.transform_vector(vector)),
            1.0e-9));

        CHECK(affine3_near_vec(
            ((first * second) * third).transform_point(point),
            (first * (second * third)).transform_point(point),
            1.0e-8));

        termin::Affine3d inverse;
        CHECK(composed.try_inverse(inverse));
        CHECK(affine3_near_vec(
            inverse.transform_point(composed.transform_point(point)),
            point,
            1.0e-8));
        CHECK(affine3_near_vec(
            inverse.transform_vector(composed.transform_vector(vector)),
            vector,
            1.0e-8));
    }
}

TEST_CASE("Affine3d inverse and matrix import fail without modifying output") {
    termin::Affine3d unchanged =
        termin::Affine3d::from_translation(9.0, 11.0, 13.0);
    CHECK(!termin::Affine3d::scaling(0.0, 2.0, 3.0).try_inverse(unchanged));
    CHECK(unchanged.translation == termin::Vec3(9.0, 11.0, 13.0));

    double projective[16] = {
        1.0, 0.0, 0.0, 0.25,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        2.0, 3.0, 4.0, 1.0,
    };
    CHECK(!termin::Affine3d::try_from_matrix4(projective, unchanged));
    CHECK(unchanged.translation == termin::Vec3(9.0, 11.0, 13.0));
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
