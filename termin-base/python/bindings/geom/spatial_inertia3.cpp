#include "common.hpp"

namespace termin {
    void bind_spatial_inertia3(nb::module_& module) {
        nb::class_<SpatialInertia3>(module, "SpatialInertia3")
            .def(nb::init<>())
            .def_rw("mass", &SpatialInertia3::mass)
            .def_rw("principal_moments", &SpatialInertia3::principal_moments)
            .def_rw("inertia_frame", &SpatialInertia3::inertia_frame)
            .def("is_finite", &SpatialInertia3::is_finite)
            .def("is_valid", &SpatialInertia3::is_valid)
            .def("central_inertia", &SpatialInertia3::central_inertia)
            .def("momentum", &SpatialInertia3::momentum)
            .def("kinetic_energy", &SpatialInertia3::kinetic_energy)
            .def("rotated_by", &SpatialInertia3::rotated_by)
            .def("transformed_by", &SpatialInertia3::transformed_by)
            .def("inverse_transformed_by", &SpatialInertia3::inverse_transformed_by);
    }
} // namespace termin
