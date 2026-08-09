#include "common.hpp"

#include <termin/geom/color.hpp>

namespace termin {

    namespace {

        template <typename Color>
        void bind_color_fields(nb::class_<Color>& cls) {
            cls.def(nb::init<>())
                .def("__init__",
                     [](Color* self, float r, float g, float b, float a) {
                         new (self) Color{r, g, b, a};
                     },
                     nb::arg("r"),
                     nb::arg("g"),
                     nb::arg("b"),
                     nb::arg("a") = 1.0f)
                .def_rw("r", &Color::r)
                .def_rw("g", &Color::g)
                .def_rw("b", &Color::b)
                .def_rw("a", &Color::a)
                .def("__len__", [](const Color&) { return 4; })
                .def("__getitem__",
                     [](const Color& value, int index) {
                         if (index < 0 || index >= 4)
                             throw nb::index_error();
                         return (&value.r)[index];
                     })
                .def("__iter__", [](const Color& value) {
                    return nb::iter(nb::make_tuple(value.r, value.g, value.b, value.a));
                })
                .def("tolist", [](const Color& value) {
                    return nb::make_tuple(value.r, value.g, value.b, value.a);
                });
        }

    } // namespace

    void bind_color(nb::module_& m) {
        auto srgb = nb::class_<SrgbColor>(m, "SrgbColor");
        bind_color_fields(srgb);

        auto linear = nb::class_<LinearColor>(m, "LinearColor");
        bind_color_fields(linear);

        m.def("srgb_to_linear", &srgb_to_linear, nb::arg("value"));
        m.def("linear_to_srgb", &linear_to_srgb, nb::arg("value"));
    }

} // namespace termin
