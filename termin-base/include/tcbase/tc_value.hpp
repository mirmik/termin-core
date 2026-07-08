#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <utility>

#include <tcbase/tc_value.h>

namespace tc {

class ValueView {
public:
    constexpr ValueView() noexcept = default;
    constexpr ValueView(std::nullptr_t) noexcept {}
    explicit constexpr ValueView(const tc_value* value) noexcept
        : value_(value) {}
    explicit constexpr ValueView(const tc_value& value) noexcept
        : value_(&value) {}

    constexpr const tc_value* raw() const noexcept {
        return value_;
    }

    constexpr explicit operator bool() const noexcept {
        return value_ != nullptr;
    }

    tc_value_type type() const noexcept {
        return value_ ? value_->type : TC_VALUE_NIL;
    }

    bool is_nil() const noexcept {
        return !value_ || value_->type == TC_VALUE_NIL;
    }

    bool is_bool() const noexcept {
        return value_ && value_->type == TC_VALUE_BOOL;
    }

    bool is_int() const noexcept {
        return value_ && value_->type == TC_VALUE_INT;
    }

    bool is_float() const noexcept {
        return value_ && value_->type == TC_VALUE_FLOAT;
    }

    bool is_double() const noexcept {
        return value_ && value_->type == TC_VALUE_DOUBLE;
    }

    bool is_number() const noexcept {
        return is_int() || is_float() || is_double();
    }

    bool is_string() const noexcept {
        return value_ && value_->type == TC_VALUE_STRING;
    }

    bool is_list() const noexcept {
        return value_ && value_->type == TC_VALUE_LIST;
    }

    bool is_dict() const noexcept {
        return value_ && value_->type == TC_VALUE_DICT;
    }

    bool as_bool(bool fallback = false) const noexcept {
        return is_bool() ? value_->data.b : fallback;
    }

    int64_t as_int(int64_t fallback = 0) const noexcept {
        return is_int() ? value_->data.i : fallback;
    }

    double as_number(double fallback = 0.0) const noexcept {
        if (!value_) {
            return fallback;
        }
        switch (value_->type) {
        case TC_VALUE_INT:
            return static_cast<double>(value_->data.i);
        case TC_VALUE_FLOAT:
            return static_cast<double>(value_->data.f);
        case TC_VALUE_DOUBLE:
            return value_->data.d;
        default:
            return fallback;
        }
    }

    const char* as_c_str(const char* fallback = "") const noexcept {
        return is_string() && value_->data.s ? value_->data.s : fallback;
    }

    std::string as_string(std::string fallback = {}) const {
        return is_string() && value_->data.s ? std::string(value_->data.s) : std::move(fallback);
    }

    std::size_t size() const noexcept {
        if (!value_) {
            return 0;
        }
        if (value_->type == TC_VALUE_LIST) {
            return value_->data.list.count;
        }
        if (value_->type == TC_VALUE_DICT) {
            return value_->data.dict.count;
        }
        return 0;
    }

    ValueView list_at(std::size_t index) const noexcept {
        if (!is_list() || index >= value_->data.list.count) {
            return ValueView();
        }
        return ValueView(value_->data.list.items[index]);
    }

    ValueView dict_get(const char* key) const noexcept {
        if (!is_dict() || !key) {
            return ValueView();
        }
        for (std::size_t i = 0; i < value_->data.dict.count; ++i) {
            const tc_value_dict_entry& entry = value_->data.dict.entries[i];
            if (entry.key && std::strcmp(entry.key, key) == 0) {
                return ValueView(entry.value);
            }
        }
        return ValueView();
    }

    ValueView dict_at(std::size_t index, const char** out_key = nullptr) const noexcept {
        if (!is_dict() || index >= value_->data.dict.count) {
            if (out_key) {
                *out_key = nullptr;
            }
            return ValueView();
        }
        const tc_value_dict_entry& entry = value_->data.dict.entries[index];
        if (out_key) {
            *out_key = entry.key;
        }
        return ValueView(entry.value);
    }

private:
    const tc_value* value_ = nullptr;
};

class Value {
public:
    Value() noexcept
        : value_(tc_value_nil()) {}

    explicit Value(tc_value value) noexcept
        : value_(value) {}

    ~Value() {
        tc_value_free(&value_);
    }

    Value(const Value& other)
        : value_(tc_value_copy(other.raw())) {}

    Value(Value&& other) noexcept
        : value_(other.release()) {}

    Value& operator=(const Value& other) {
        if (this == &other) {
            return *this;
        }
        reset(tc_value_copy(other.raw()));
        return *this;
    }

    Value& operator=(Value&& other) noexcept {
        if (this == &other) {
            return *this;
        }
        reset(other.release());
        return *this;
    }

    static Value adopt(tc_value value) noexcept {
        return Value(value);
    }

    static Value copy_of(const tc_value* value) {
        return Value(tc_value_copy(value));
    }

    static Value copy_of(const tc_value& value) {
        return copy_of(&value);
    }

    static Value nil() noexcept {
        return Value(tc_value_nil());
    }

    static Value boolean(bool value) noexcept {
        return Value(tc_value_bool(value));
    }

    static Value integer(int64_t value) noexcept {
        return Value(tc_value_int(value));
    }

    static Value floating(float value) noexcept {
        return Value(tc_value_float(value));
    }

    static Value number(double value) noexcept {
        return Value(tc_value_double(value));
    }

    static Value string(const char* value) noexcept {
        return Value(tc_value_string(value));
    }

    static Value string(const std::string& value) noexcept {
        return string(value.c_str());
    }

    static Value list() noexcept {
        return Value(tc_value_list_new());
    }

    static Value dict() noexcept {
        return Value(tc_value_dict_new());
    }

    const tc_value* raw() const noexcept {
        return &value_;
    }

    tc_value* raw() noexcept {
        return &value_;
    }

    const tc_value& get() const noexcept {
        return value_;
    }

    tc_value& get() noexcept {
        return value_;
    }

    ValueView view() const noexcept {
        return ValueView(value_);
    }

    tc_value_type type() const noexcept {
        return value_.type;
    }

    bool is_nil() const noexcept {
        return value_.type == TC_VALUE_NIL;
    }

    tc_value release() noexcept {
        tc_value released = value_;
        value_ = tc_value_nil();
        return released;
    }

    void reset(tc_value value = tc_value_nil()) noexcept {
        tc_value_free(&value_);
        value_ = value;
    }

    void swap(Value& other) noexcept {
        using std::swap;
        swap(value_, other.value_);
    }

    void push(Value item) noexcept {
        tc_value_list_push(&value_, item.release());
    }

    void set(const char* key, Value item) noexcept {
        tc_value_dict_set(&value_, key, item.release());
    }

    void set(const std::string& key, Value item) noexcept {
        set(key.c_str(), std::move(item));
    }

private:
    tc_value value_;
};

inline void swap(Value& lhs, Value& rhs) noexcept {
    lhs.swap(rhs);
}

} // namespace tc
