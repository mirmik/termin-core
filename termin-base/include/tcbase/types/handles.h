// tcbase/types/handles.h - opaque engine handles shared by C APIs
#ifndef TCBASE_TYPES_HANDLES_H
#define TCBASE_TYPES_HANDLES_H

#ifdef __cplusplus
struct tc_transform;
struct tc_entity;
struct tc_component;
struct tc_component_vtable;
struct tc_component_ref_vtable;
struct tc_drawable_vtable;
struct tc_input_vtable;
struct tc_scene;
struct tc_viewport;
struct tc_pipeline;
#else
typedef struct tc_transform tc_transform;
typedef struct tc_entity tc_entity;
typedef struct tc_component tc_component;
typedef struct tc_component_vtable tc_component_vtable;
typedef struct tc_component_ref_vtable tc_component_ref_vtable;
typedef struct tc_drawable_vtable tc_drawable_vtable;
typedef struct tc_input_vtable tc_input_vtable;
typedef struct tc_scene tc_scene;
typedef struct tc_viewport tc_viewport;
typedef struct tc_pipeline tc_pipeline;
#endif

#endif // TCBASE_TYPES_HANDLES_H
