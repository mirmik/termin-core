#include <tcbase/tc_tensor.h>

#include <limits.h>
#include <stdlib.h>
#include <string.h>

#include <tcbase/tc_log.h>

static bool checked_mul_size(size_t a, size_t b, size_t* out) {
    if (!out) return false;
    if (a != 0 && b > SIZE_MAX / a) {
        return false;
    }
    *out = a * b;
    return true;
}

static bool validate_shape(uint8_t ndim, const size_t* shape) {
    if (ndim > TC_TENSOR_MAX_DIMS) {
        tc_log_error("tc_tensor: ndim=%u exceeds TC_TENSOR_MAX_DIMS=%u",
                     (unsigned)ndim,
                     (unsigned)TC_TENSOR_MAX_DIMS);
        return false;
    }
    if (ndim > 0 && !shape) {
        tc_log_error("tc_tensor: shape is NULL for ndim=%u", (unsigned)ndim);
        return false;
    }
    return true;
}

static ptrdiff_t size_to_ptrdiff(size_t value) {
    if (value > (size_t)PTRDIFF_MAX) {
        return -1;
    }
    return (ptrdiff_t)value;
}

size_t tc_dtype_size(tc_dtype dtype) {
    switch (dtype) {
    case TC_DTYPE_U8:
    case TC_DTYPE_I8:
        return 1;
    case TC_DTYPE_U16:
    case TC_DTYPE_I16:
        return 2;
    case TC_DTYPE_U32:
    case TC_DTYPE_I32:
    case TC_DTYPE_F32:
        return 4;
    case TC_DTYPE_U64:
    case TC_DTYPE_I64:
    case TC_DTYPE_F64:
        return 8;
    default:
        return 0;
    }
}

const char* tc_dtype_name(tc_dtype dtype) {
    switch (dtype) {
    case TC_DTYPE_U8: return "u8";
    case TC_DTYPE_U16: return "u16";
    case TC_DTYPE_U32: return "u32";
    case TC_DTYPE_U64: return "u64";
    case TC_DTYPE_I8: return "i8";
    case TC_DTYPE_I16: return "i16";
    case TC_DTYPE_I32: return "i32";
    case TC_DTYPE_I64: return "i64";
    case TC_DTYPE_F32: return "f32";
    case TC_DTYPE_F64: return "f64";
    default: return "invalid";
    }
}

tc_tensor tc_tensor_empty(void) {
    tc_tensor tensor;
    memset(&tensor, 0, sizeof(tensor));
    tensor.dtype = TC_DTYPE_INVALID;
    return tensor;
}

bool tc_tensor_make_c_strides(
    tc_dtype dtype,
    uint8_t ndim,
    const size_t* shape,
    ptrdiff_t* out_strides
) {
    if (!validate_shape(ndim, shape)) {
        return false;
    }
    if (ndim > 0 && !out_strides) {
        tc_log_error("tc_tensor_make_c_strides: out_strides is NULL");
        return false;
    }

    size_t stride = tc_dtype_size(dtype);
    if (stride == 0) {
        tc_log_error("tc_tensor_make_c_strides: invalid dtype=%d", (int)dtype);
        return false;
    }

    for (size_t i = 0; i < ndim; ++i) {
        size_t dim = ndim - i - 1;
        ptrdiff_t signed_stride = size_to_ptrdiff(stride);
        if (signed_stride < 0) {
            tc_log_error("tc_tensor_make_c_strides: stride overflow");
            return false;
        }
        out_strides[dim] = signed_stride;
        if (!checked_mul_size(stride, shape[dim], &stride)) {
            tc_log_error("tc_tensor_make_c_strides: shape product overflow");
            return false;
        }
    }
    return true;
}

static bool init_tensor(
    tc_tensor* tensor,
    void* data,
    void* owner,
    tc_tensor_release_fn release_owner,
    tc_dtype dtype,
    uint8_t ndim,
    const size_t* shape,
    const ptrdiff_t* strides,
    uint32_t flags
) {
    if (!tensor) {
        tc_log_error("tc_tensor: tensor is NULL");
        return false;
    }
    *tensor = tc_tensor_empty();

    if (!validate_shape(ndim, shape)) {
        return false;
    }
    if (tc_dtype_size(dtype) == 0) {
        tc_log_error("tc_tensor: invalid dtype=%d", (int)dtype);
        return false;
    }

    tensor->data = data;
    tensor->owner = owner;
    tensor->release_owner = release_owner;
    tensor->dtype = dtype;
    tensor->ndim = ndim;
    tensor->flags = flags;

    for (uint8_t i = 0; i < ndim; ++i) {
        tensor->shape[i] = shape[i];
    }

    if (strides) {
        for (uint8_t i = 0; i < ndim; ++i) {
            tensor->strides[i] = strides[i];
        }
    } else if (!tc_tensor_make_c_strides(dtype, ndim, shape, tensor->strides)) {
        *tensor = tc_tensor_empty();
        return false;
    }

    return true;
}

bool tc_tensor_init_borrowed(
    tc_tensor* tensor,
    void* data,
    tc_dtype dtype,
    uint8_t ndim,
    const size_t* shape,
    const ptrdiff_t* strides,
    uint32_t flags
) {
    return init_tensor(tensor, data, NULL, NULL, dtype, ndim, shape, strides, flags);
}

bool tc_tensor_init_external(
    tc_tensor* tensor,
    void* data,
    void* owner,
    tc_tensor_release_fn release_owner,
    tc_dtype dtype,
    uint8_t ndim,
    const size_t* shape,
    const ptrdiff_t* strides,
    uint32_t flags
) {
    return init_tensor(tensor, data, owner, release_owner, dtype, ndim, shape, strides, flags);
}

bool tc_tensor_init_owned(
    tc_tensor* tensor,
    tc_dtype dtype,
    uint8_t ndim,
    const size_t* shape,
    uint32_t flags
) {
    if (!tensor) {
        tc_log_error("tc_tensor_init_owned: tensor is NULL");
        return false;
    }
    *tensor = tc_tensor_empty();

    if (!validate_shape(ndim, shape)) {
        return false;
    }

    const size_t byte_size = tc_dtype_size(dtype);
    if (byte_size == 0) {
        tc_log_error("tc_tensor_init_owned: invalid dtype=%d", (int)dtype);
        return false;
    }

    size_t total = byte_size;
    for (uint8_t i = 0; i < ndim; ++i) {
        if (!checked_mul_size(total, shape[i], &total)) {
            tc_log_error("tc_tensor_init_owned: allocation size overflow");
            return false;
        }
    }

    void* data = NULL;
    if (total > 0) {
        data = calloc(1, total);
        if (!data) {
            tc_log_error("tc_tensor_init_owned: allocation failed for %zu bytes", total);
            return false;
        }
    }

    if (!init_tensor(tensor, data, data, free, dtype, ndim, shape, NULL, flags)) {
        free(data);
        return false;
    }
    return true;
}

void tc_tensor_free(tc_tensor* tensor) {
    if (!tensor) return;
    if (tensor->owner && tensor->release_owner) {
        tensor->release_owner(tensor->owner);
    }
    *tensor = tc_tensor_empty();
}

bool tc_tensor_is_readonly(const tc_tensor* tensor) {
    return tensor && ((tensor->flags & TC_TENSOR_READONLY) != 0);
}

size_t tc_tensor_element_count(const tc_tensor* tensor) {
    if (!tensor || tensor->dtype == TC_DTYPE_INVALID) return 0;
    size_t count = 1;
    for (uint8_t i = 0; i < tensor->ndim; ++i) {
        if (!checked_mul_size(count, tensor->shape[i], &count)) {
            return 0;
        }
    }
    return count;
}

size_t tc_tensor_contiguous_byte_size(const tc_tensor* tensor) {
    if (!tensor) return 0;
    size_t count = tc_tensor_element_count(tensor);
    size_t bytes = 0;
    if (!checked_mul_size(count, tc_dtype_size(tensor->dtype), &bytes)) {
        return 0;
    }
    return bytes;
}

bool tc_tensor_is_valid(const tc_tensor* tensor) {
    if (!tensor || tc_dtype_size(tensor->dtype) == 0) return false;
    if (tensor->ndim > TC_TENSOR_MAX_DIMS) return false;
    return tensor->data != NULL || tc_tensor_element_count(tensor) == 0;
}

bool tc_tensor_is_c_contiguous(const tc_tensor* tensor) {
    if (!tc_tensor_is_valid(tensor)) return false;
    ptrdiff_t expected[TC_TENSOR_MAX_DIMS] = {0};
    if (!tc_tensor_make_c_strides(tensor->dtype, tensor->ndim, tensor->shape, expected)) {
        return false;
    }
    for (uint8_t i = 0; i < tensor->ndim; ++i) {
        if (tensor->strides[i] != expected[i]) {
            return false;
        }
    }
    return true;
}

static ptrdiff_t offset_for_ordinal(const tc_tensor* tensor, size_t ordinal) {
    ptrdiff_t offset = 0;
    for (uint8_t i = 0; i < tensor->ndim; ++i) {
        const uint8_t dim = (uint8_t)(tensor->ndim - i - 1);
        const size_t extent = tensor->shape[dim];
        const size_t index = extent == 0 ? 0 : ordinal % extent;
        ordinal = extent == 0 ? 0 : ordinal / extent;
        offset += (ptrdiff_t)index * tensor->strides[dim];
    }
    return offset;
}

bool tc_tensor_copy_contiguous(tc_tensor* dst, const tc_tensor* src) {
    if (!dst || !src) {
        tc_log_error("tc_tensor_copy_contiguous: dst/src is NULL");
        return false;
    }
    if (!tc_tensor_is_valid(src)) {
        tc_log_error("tc_tensor_copy_contiguous: invalid source tensor");
        return false;
    }
    if (!tc_tensor_init_owned(dst, src->dtype, src->ndim, src->shape, src->flags)) {
        return false;
    }

    const size_t count = tc_tensor_element_count(src);
    const size_t item_size = tc_dtype_size(src->dtype);
    const char* src_bytes = (const char*)src->data;
    char* dst_bytes = (char*)dst->data;
    for (size_t i = 0; i < count; ++i) {
        memcpy(dst_bytes + i * item_size, src_bytes + offset_for_ordinal(src, i), item_size);
    }
    return true;
}
