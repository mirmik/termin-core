// tc_tensor.h - ABI-friendly typed strided memory descriptor
#ifndef TCBASE_TC_TENSOR_H
#define TCBASE_TC_TENSOR_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include <tcbase/tcbase_api.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TC_TENSOR_MAX_DIMS 8

typedef enum tc_dtype {
    TC_DTYPE_INVALID = 0,
    TC_DTYPE_U8,
    TC_DTYPE_U16,
    TC_DTYPE_U32,
    TC_DTYPE_U64,
    TC_DTYPE_I8,
    TC_DTYPE_I16,
    TC_DTYPE_I32,
    TC_DTYPE_I64,
    TC_DTYPE_F32,
    TC_DTYPE_F64,
} tc_dtype;

enum {
    TC_TENSOR_READONLY = 1u << 0,
};

typedef void (*tc_tensor_release_fn)(void* owner);

typedef struct tc_tensor {
    void* data;
    void* owner;
    tc_tensor_release_fn release_owner;
    tc_dtype dtype;
    uint8_t ndim;
    uint32_t flags;
    size_t shape[TC_TENSOR_MAX_DIMS];
    ptrdiff_t strides[TC_TENSOR_MAX_DIMS]; // byte strides
} tc_tensor;

// Describes externally owned tensor storage. The descriptor keeps the C ABI
// extensible without growing tc_tensor_init_external's parameter list.
typedef struct tc_tensor_external_desc {
    void* data;
    void* owner;
    tc_tensor_release_fn release_owner;
    tc_dtype dtype;
    uint8_t ndim;
    const size_t* shape;
    const ptrdiff_t* strides;
    uint32_t flags;
} tc_tensor_external_desc;

TCBASE_API size_t tc_dtype_size(tc_dtype dtype);
TCBASE_API const char* tc_dtype_name(tc_dtype dtype);

TCBASE_API tc_tensor tc_tensor_empty(void);

TCBASE_API bool tc_tensor_init_borrowed(
    tc_tensor* tensor,
    void* data,
    tc_dtype dtype,
    uint8_t ndim,
    const size_t* shape,
    const ptrdiff_t* strides,
    uint32_t flags
);

TCBASE_API bool tc_tensor_init_external(
    tc_tensor* tensor,
    const tc_tensor_external_desc* desc
);

TCBASE_API bool tc_tensor_init_owned(
    tc_tensor* tensor,
    tc_dtype dtype,
    uint8_t ndim,
    const size_t* shape,
    uint32_t flags
);

TCBASE_API void tc_tensor_free(tc_tensor* tensor);

TCBASE_API bool tc_tensor_is_valid(const tc_tensor* tensor);
TCBASE_API bool tc_tensor_is_readonly(const tc_tensor* tensor);
TCBASE_API bool tc_tensor_is_c_contiguous(const tc_tensor* tensor);

TCBASE_API size_t tc_tensor_element_count(const tc_tensor* tensor);
TCBASE_API size_t tc_tensor_contiguous_byte_size(const tc_tensor* tensor);
TCBASE_API bool tc_tensor_make_c_strides(
    tc_dtype dtype,
    uint8_t ndim,
    const size_t* shape,
    ptrdiff_t* out_strides
);

TCBASE_API bool tc_tensor_copy_contiguous(tc_tensor* dst, const tc_tensor* src);

#ifdef __cplusplus
}
#endif

#endif // TCBASE_TC_TENSOR_H
