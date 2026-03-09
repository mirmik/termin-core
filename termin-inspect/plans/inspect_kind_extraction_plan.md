# Plan: Extract and Generalize Inspect/Kind into `termin-inspect`

## Goal
Move `inspect/kind` from `termin` into an independent library that works with any runtime object (not only components/passes).

## Non-Goals
- No behavior changes in scene/entity runtime during phase 1.
- No immediate migration of all callsites in one step.
- No temporary fallback layers "just in case".

## Current Constraints (from existing code)
- `InspectFieldInfo::action` is effectively component-centric in usage.
- C entrypoints are split as `tc_component_inspect_*` and `tc_pass_inspect_*` adapters.
- C++ inspect runtime is mixed with component/pass specifics in one place.
- C++ kind runtime currently auto-registers domain handles (`tc_mesh`, `tc_material`) that belong to higher layers.

## Target Architecture

### 1) Core package (`termin-inspect`)
Contains only generic reflection/serialization runtime:
- Type registry (fields, inheritance, metadata)
- Kind registry (C dispatcher + C++ runtime + optional Python runtime extension)
- Generic field get/set/action dispatch
- JSON/tc_value conversion helpers for inspect path

Core must not depend on:
- Scene/entity
- Render passes
- Mesh/material handles
- Editor UI

### 2) Adapter packages (outside core)
Use generic API and provide runtime-specific object mapping:
- `termin-scene` adapters for component objects
- `termin-render` adapters for pass objects
- `termin` Python bindings adapters

These adapters own:
- `tc_component_inspect_*`
- `tc_pass_inspect_*`
- Domain kind registrations (`tc_mesh`, `tc_material`, etc.)

## Generic API Boundary

### C-level boundary
Introduce/normalize a generic object entrypoint:
- `tc_inspect_get_object(void* obj, const char* type_name, const char* path)`
- `tc_inspect_set_object(void* obj, const char* type_name, const char* path, tc_value value, tc_scene_handle scene)`
- `tc_inspect_action_object(void* obj, const char* type_name, const char* path)`

Keep `tc_component_inspect_*` and `tc_pass_inspect_*` as thin adapters built outside core.

### C++ boundary
Generalize action signature:
- from component-specific callback usage
- to `std::function<void(void*, const InspectContext&)>`

`InspectContext` keeps optional runtime data (scene handle, user context).

### Kind boundary
Core `KindRegistryCpp` should only include primitive/builtin kinds.
Domain kinds must be registered by consumers:
- scene/graphics layer registers mesh/material handles
- other projects can register their own handle types

## Migration Stages

### Stage 0: Bootstrap `termin-inspect`
- Create CMake project and install/export config.
- Add CI skeleton (C/C++ + Python if bindings enabled).
- Add minimal smoke tests for registry create/register/query.

### Stage 1: Move pure dispatcher C layer
Move from `termin/core_c/include/inspect/*` and implementation parts that are runtime-agnostic:
- `tc_inspect.h/.c`
- `tc_kind.h/.c`
- `tc_value` JSON helpers used by inspect path

Validation:
- Existing `termin` compiles by linking `termin-inspect`.
- C tests for parser, registry, dispatch pass.

### Stage 2: Split C++ inspect runtime into core + adapters
In current `tc_inspect_instance` logic:
- Keep only generic registry/vtable logic in core.
- Move component/pass object mapping to adapter files in `termin`/`termin-scene`.

Validation:
- Same behavior via adapters for component/pass calls.
- No component/pass includes inside core files.

### Stage 3: Extract kind C++ runtime
Move `tc_kind_cpp` into core, but remove domain auto-registration.
- Keep builtin scalar/vector/quat kinds in core.
- Move mesh/material registrations to graphics/scene integration layer.

Validation:
- Core tests for builtin kinds.
- Integration tests in consumer for mesh/material kinds.

### Stage 4: Python extension layering
Split Python bindings:
- core python binding (optional): inspect registry + kind registry generic API
- consumer bindings: entity/pass-specific adapters

Validation:
- Python tests for:
  - register_python_fields
  - serialize/deserialize generic objects
  - custom kind handlers

### Stage 5: Replace direct callsites
Update `termin` code to use adapter-owned entrypoints and eliminate internal old paths.

Validation:
- editor/project load
- C++ module load/reload path still works
- python component serialization unchanged

## Testing Plan

### C tests
- kind parser (`list[T]`)
- lang vtable registration and dispatch
- field metadata traversal with inheritance

### C++ tests
- InspectRegistry field add/get/set with primitive and custom kinds
- generic action callback invocation
- unregister type behavior

### Python tests
- register_python_fields + serialize/deserialize
- custom python kind handlers
- list kind lazy ensure behavior

### Integration tests (consumer side)
- component adapter: get/set/action through generic core
- pass adapter: get/set through generic core
- domain handle kinds (`tc_mesh`, `tc_material`) registered externally

## Compatibility Strategy
- Preserve existing public adapter APIs during migration.
- Keep binary-compatible C symbols where feasible.
- If symbol move is unavoidable, provide deprecation window in adapter layer (not in core).

## Risks
- Singleton duplication across shared libs if link topology is wrong.
- Python lifetime/refcount errors around action callbacks and class registry.
- Hidden dependencies on scene/render types in inspect/kind callsites.

## Definition of Done
- `termin-inspect` builds and tests independently.
- `termin` links against `termin-inspect` without embedded inspect/kind core sources.
- component/pass inspect works via adapters only.
- mesh/material and other domain kinds are registered outside core.
- CI covers C/C++ and Python API smoke for the new package.
