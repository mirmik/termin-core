#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>
#include <utility>

#include <tcbase/tc_value.h>

namespace tc {

enum class trent_type {
    nil,
    boolean,
    numer,
    string,
    list,
    dict,
};

class trent;
class trent_ref;
class trent_view;

struct trent_dict_entry_view {
    const char* key = nullptr;
    const tc_value* value = nullptr;

    trent_view view() const noexcept;
};

struct trent_dict_entry_ref {
    const char* key = nullptr;
    tc_value* value = nullptr;

    trent_ref ref() const noexcept;
    trent_view view() const noexcept;
};

class trent_view {
public:
    constexpr trent_view() noexcept = default;
    constexpr trent_view(std::nullptr_t) noexcept {}
    explicit constexpr trent_view(const tc_value* value) noexcept
        : value_(value) {}
    explicit constexpr trent_view(const tc_value& value) noexcept
        : value_(&value) {}

    constexpr const tc_value* raw() const noexcept {
        return value_;
    }

    constexpr explicit operator bool() const noexcept {
        return value_ != nullptr;
    }

    tc_value_type raw_type() const noexcept {
        return value_ ? value_->type : TC_VALUE_NIL;
    }

    trent_type type() const noexcept {
        switch (raw_type()) {
        case TC_VALUE_BOOL:
            return trent_type::boolean;
        case TC_VALUE_INT:
        case TC_VALUE_FLOAT:
        case TC_VALUE_DOUBLE:
            return trent_type::numer;
        case TC_VALUE_STRING:
            return trent_type::string;
        case TC_VALUE_LIST:
            return trent_type::list;
        case TC_VALUE_DICT:
            return trent_type::dict;
        case TC_VALUE_NIL:
        default:
            return trent_type::nil;
        }
    }

    bool is_nil() const noexcept {
        return !value_ || value_->type == TC_VALUE_NIL;
    }

    bool is_bool() const noexcept {
        return value_ && value_->type == TC_VALUE_BOOL;
    }

    bool is_numer() const noexcept {
        return value_ &&
            (value_->type == TC_VALUE_INT ||
             value_->type == TC_VALUE_FLOAT ||
             value_->type == TC_VALUE_DOUBLE);
    }

    bool is_integer() const noexcept {
        return value_ && value_->type == TC_VALUE_INT;
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

    int64_t as_integer(int64_t fallback = 0) const noexcept {
        if (!value_) {
            return fallback;
        }
        switch (value_->type) {
        case TC_VALUE_INT:
            return value_->data.i;
        case TC_VALUE_FLOAT:
            return static_cast<int64_t>(value_->data.f);
        case TC_VALUE_DOUBLE:
            return static_cast<int64_t>(value_->data.d);
        default:
            return fallback;
        }
    }

    double as_numer(double fallback = 0.0) const noexcept {
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

    bool contains(const char* key) const noexcept {
        return static_cast<bool>(get(key));
    }

    bool contains(const std::string& key) const noexcept {
        return contains(key.c_str());
    }

    trent_view get(const char* key) const noexcept {
        if (!is_dict() || !key) {
            return trent_view();
        }
        for (std::size_t i = 0; i < value_->data.dict.count; ++i) {
            const tc_value_dict_entry& entry = value_->data.dict.entries[i];
            if (entry.key && std::strcmp(entry.key, key) == 0) {
                return trent_view(entry.value);
            }
        }
        return trent_view();
    }

    trent_view get(const std::string& key) const noexcept {
        return get(key.c_str());
    }

    trent_view dict_get(const char* key) const noexcept {
        return get(key);
    }

    trent_view dict_get(const std::string& key) const noexcept {
        return get(key);
    }

    trent_view _get(const char* key) const noexcept {
        return get(key);
    }

    trent_view _get(const std::string& key) const noexcept {
        return get(key);
    }

    trent_view at(std::size_t index) const noexcept {
        if (!is_list() || index >= value_->data.list.count) {
            return trent_view();
        }
        return trent_view(value_->data.list.items[index]);
    }

    trent_view list_at(std::size_t index) const noexcept {
        return at(index);
    }

    trent_view operator[](std::size_t index) const noexcept {
        return at(index);
    }

    trent_view operator[](int index) const noexcept {
        return index >= 0 ? at(static_cast<std::size_t>(index)) : trent_view();
    }

    trent_view operator[](const char* key) const noexcept {
        return get(key);
    }

    trent_view operator[](const std::string& key) const noexcept {
        return get(key);
    }

    class list_view {
    public:
        class iterator {
        public:
            using difference_type = std::ptrdiff_t;
            using value_type = trent_view;

            iterator(const tc_value* items, std::size_t index) noexcept
                : items_(items)
                , index_(index) {}

            trent_view operator*() const noexcept {
                return trent_view(items_[index_]);
            }

            iterator& operator++() noexcept {
                ++index_;
                return *this;
            }

            bool operator!=(const iterator& other) const noexcept {
                return items_ != other.items_ || index_ != other.index_;
            }

        private:
            const tc_value* items_ = nullptr;
            std::size_t index_ = 0;
        };

        explicit list_view(const tc_value* value) noexcept
            : value_(value && value->type == TC_VALUE_LIST ? value : nullptr) {}

        iterator begin() const noexcept {
            return iterator(value_ ? value_->data.list.items : nullptr, 0);
        }

        iterator end() const noexcept {
            return iterator(value_ ? value_->data.list.items : nullptr, size());
        }

        std::size_t size() const noexcept {
            return value_ ? value_->data.list.count : 0;
        }

        bool empty() const noexcept {
            return size() == 0;
        }

    private:
        const tc_value* value_ = nullptr;
    };

    class dict_view {
    public:
        class iterator {
        public:
            using difference_type = std::ptrdiff_t;
            using value_type = trent_dict_entry_view;

            iterator(const tc_value_dict_entry* entries, std::size_t index) noexcept
                : entries_(entries)
                , index_(index) {}

            trent_dict_entry_view operator*() const noexcept {
                const tc_value_dict_entry& entry = entries_[index_];
                return {entry.key, entry.value};
            }

            iterator& operator++() noexcept {
                ++index_;
                return *this;
            }

            bool operator!=(const iterator& other) const noexcept {
                return entries_ != other.entries_ || index_ != other.index_;
            }

        private:
            const tc_value_dict_entry* entries_ = nullptr;
            std::size_t index_ = 0;
        };

        explicit dict_view(const tc_value* value) noexcept
            : value_(value && value->type == TC_VALUE_DICT ? value : nullptr) {}

        iterator begin() const noexcept {
            return iterator(value_ ? value_->data.dict.entries : nullptr, 0);
        }

        iterator end() const noexcept {
            return iterator(value_ ? value_->data.dict.entries : nullptr, size());
        }

        std::size_t size() const noexcept {
            return value_ ? value_->data.dict.count : 0;
        }

        bool empty() const noexcept {
            return size() == 0;
        }

    private:
        const tc_value* value_ = nullptr;
    };

    list_view as_list() const noexcept {
        return list_view(value_);
    }

    dict_view as_dict() const noexcept {
        return dict_view(value_);
    }

private:
    const tc_value* value_ = nullptr;
};

class trent_ref {
public:
    constexpr trent_ref() noexcept = default;
    explicit constexpr trent_ref(tc_value* value) noexcept
        : value_(value) {}

    constexpr tc_value* raw() noexcept {
        return value_;
    }

    constexpr const tc_value* raw() const noexcept {
        return value_;
    }

    constexpr explicit operator bool() const noexcept {
        return value_ != nullptr;
    }

    trent_view view() const noexcept {
        return trent_view(value_);
    }

    operator trent_view() const noexcept {
        return view();
    }

    tc_value_type raw_type() const noexcept {
        return view().raw_type();
    }

    trent_type type() const noexcept {
        return view().type();
    }

    bool is_nil() const noexcept { return view().is_nil(); }
    bool is_bool() const noexcept { return view().is_bool(); }
    bool is_numer() const noexcept { return view().is_numer(); }
    bool is_integer() const noexcept { return view().is_integer(); }
    bool is_string() const noexcept { return view().is_string(); }
    bool is_list() const noexcept { return view().is_list(); }
    bool is_dict() const noexcept { return view().is_dict(); }
    bool as_bool(bool fallback = false) const noexcept { return view().as_bool(fallback); }
    int64_t as_integer(int64_t fallback = 0) const noexcept { return view().as_integer(fallback); }
    double as_numer(double fallback = 0.0) const noexcept { return view().as_numer(fallback); }
    const char* as_c_str(const char* fallback = "") const noexcept { return view().as_c_str(fallback); }
    std::string as_string(std::string fallback = {}) const { return view().as_string(std::move(fallback)); }
    std::size_t size() const noexcept { return view().size(); }
    bool contains(const char* key) const noexcept { return view().contains(key); }
    bool contains(const std::string& key) const noexcept { return view().contains(key); }

    void init(trent_type type) noexcept {
        if (!value_) {
            return;
        }
        tc_value_free(value_);
        switch (type) {
        case trent_type::boolean:
            *value_ = tc_value_bool(false);
            break;
        case trent_type::numer:
            *value_ = tc_value_int(0);
            break;
        case trent_type::string:
            *value_ = tc_value_string("");
            break;
        case trent_type::list:
            *value_ = tc_value_list_new();
            break;
        case trent_type::dict:
            *value_ = tc_value_dict_new();
            break;
        case trent_type::nil:
        default:
            *value_ = tc_value_nil();
            break;
        }
    }

    void reset(tc_value value) noexcept {
        if (!value_) {
            tc_value_free(&value);
            return;
        }
        tc_value_free(value_);
        *value_ = value;
    }

    trent_ref& operator=(trent_view other) noexcept {
        reset(tc_value_copy(other.raw()));
        return *this;
    }

    trent_ref& operator=(const trent& other) noexcept;

    trent_ref& operator=(trent&& other) noexcept;

    trent_ref& operator=(std::nullptr_t) noexcept {
        reset(tc_value_nil());
        return *this;
    }

    trent_ref& operator=(bool value) noexcept {
        reset(tc_value_bool(value));
        return *this;
    }

    trent_ref& operator=(int value) noexcept {
        reset(tc_value_int(value));
        return *this;
    }

    trent_ref& operator=(int64_t value) noexcept {
        reset(tc_value_int(value));
        return *this;
    }

    trent_ref& operator=(float value) noexcept {
        reset(tc_value_float(value));
        return *this;
    }

    trent_ref& operator=(double value) noexcept {
        reset(tc_value_double(value));
        return *this;
    }

    trent_ref& operator=(const char* value) noexcept {
        reset(tc_value_string(value));
        return *this;
    }

    trent_ref& operator=(const std::string& value) noexcept {
        reset(tc_value_string(value.c_str()));
        return *this;
    }

    trent_view get(const char* key) const noexcept {
        return view().get(key);
    }

    trent_view get(const std::string& key) const noexcept {
        return view().get(key);
    }

    trent_view dict_get(const char* key) const noexcept {
        return get(key);
    }

    trent_view dict_get(const std::string& key) const noexcept {
        return get(key);
    }

    trent_view _get(const char* key) const noexcept {
        return view()._get(key);
    }

    trent_view _get(const std::string& key) const noexcept {
        return view()._get(key);
    }

    trent_ref operator[](const char* key) noexcept {
        if (!value_) {
            return trent_ref();
        }
        if (value_->type != TC_VALUE_DICT) {
            reset(tc_value_dict_new());
        }
        tc_value* child = tc_value_dict_get(value_, key);
        if (!child) {
            tc_value_dict_set(value_, key, tc_value_nil());
            child = tc_value_dict_get(value_, key);
        }
        return trent_ref(child);
    }

    trent_ref operator[](const std::string& key) noexcept {
        return (*this)[key.c_str()];
    }

    trent_view operator[](const char* key) const noexcept {
        return view()[key];
    }

    trent_view operator[](const std::string& key) const noexcept {
        return view()[key];
    }

    trent_ref at(std::size_t index) noexcept {
        if (!value_ || value_->type != TC_VALUE_LIST || index >= value_->data.list.count) {
            return trent_ref();
        }
        return trent_ref(&value_->data.list.items[index]);
    }

    trent_ref list_at(std::size_t index) noexcept {
        return at(index);
    }

    trent_view at(std::size_t index) const noexcept {
        return view().at(index);
    }

    trent_view list_at(std::size_t index) const noexcept {
        return at(index);
    }

    trent_ref operator[](std::size_t index) noexcept {
        return at(index);
    }

    trent_view operator[](std::size_t index) const noexcept {
        return at(index);
    }

    trent_ref operator[](int index) noexcept {
        return index >= 0 ? at(static_cast<std::size_t>(index)) : trent_ref();
    }

    trent_view operator[](int index) const noexcept {
        return index >= 0 ? at(static_cast<std::size_t>(index)) : trent_view();
    }

    void push_back(trent&& value) noexcept;
    void push_back(const trent& value) noexcept;
    void push_back(trent_view value) noexcept {
        push_back_raw(tc_value_copy(value.raw()));
    }
    void push_back(bool value) noexcept { push_back_raw(tc_value_bool(value)); }
    void push_back(int value) noexcept { push_back_raw(tc_value_int(value)); }
    void push_back(int64_t value) noexcept { push_back_raw(tc_value_int(value)); }
    void push_back(float value) noexcept { push_back_raw(tc_value_float(value)); }
    void push_back(double value) noexcept { push_back_raw(tc_value_double(value)); }
    void push_back(const char* value) noexcept { push_back_raw(tc_value_string(value)); }
    void push_back(const std::string& value) noexcept { push_back_raw(tc_value_string(value.c_str())); }

    void set(const char* key, trent&& value) noexcept;
    void set(const char* key, const trent& value) noexcept;
    void set(const char* key, trent_view value) noexcept {
        set_raw(key, tc_value_copy(value.raw()));
    }
    void set(const std::string& key, trent&& value) noexcept {
        set(key.c_str(), std::move(value));
    }
    void set(const std::string& key, const trent& value) noexcept {
        set(key.c_str(), value);
    }
    void set(const std::string& key, trent_view value) noexcept {
        set(key.c_str(), value);
    }

    class list_ref {
    public:
        class iterator {
        public:
            using difference_type = std::ptrdiff_t;
            using value_type = trent_ref;

            iterator(tc_value* items, std::size_t index) noexcept
                : items_(items)
                , index_(index) {}

            trent_ref operator*() const noexcept {
                return trent_ref(&items_[index_]);
            }

            iterator& operator++() noexcept {
                ++index_;
                return *this;
            }

            bool operator!=(const iterator& other) const noexcept {
                return items_ != other.items_ || index_ != other.index_;
            }

        private:
            tc_value* items_ = nullptr;
            std::size_t index_ = 0;
        };

        explicit list_ref(tc_value* value) noexcept
            : value_(value && value->type == TC_VALUE_LIST ? value : nullptr) {}

        iterator begin() const noexcept {
            return iterator(value_ ? value_->data.list.items : nullptr, 0);
        }

        iterator end() const noexcept {
            return iterator(value_ ? value_->data.list.items : nullptr, size());
        }

        std::size_t size() const noexcept {
            return value_ ? value_->data.list.count : 0;
        }

        bool empty() const noexcept {
            return size() == 0;
        }

    private:
        tc_value* value_ = nullptr;
    };

    class dict_ref {
    public:
        class iterator {
        public:
            using difference_type = std::ptrdiff_t;
            using value_type = trent_dict_entry_ref;

            iterator(tc_value_dict_entry* entries, std::size_t index) noexcept
                : entries_(entries)
                , index_(index) {}

            trent_dict_entry_ref operator*() const noexcept {
                tc_value_dict_entry& entry = entries_[index_];
                return {entry.key, entry.value};
            }

            iterator& operator++() noexcept {
                ++index_;
                return *this;
            }

            bool operator!=(const iterator& other) const noexcept {
                return entries_ != other.entries_ || index_ != other.index_;
            }

        private:
            tc_value_dict_entry* entries_ = nullptr;
            std::size_t index_ = 0;
        };

        explicit dict_ref(tc_value* value) noexcept
            : value_(value && value->type == TC_VALUE_DICT ? value : nullptr) {}

        iterator begin() const noexcept {
            return iterator(value_ ? value_->data.dict.entries : nullptr, 0);
        }

        iterator end() const noexcept {
            return iterator(value_ ? value_->data.dict.entries : nullptr, size());
        }

        std::size_t size() const noexcept {
            return value_ ? value_->data.dict.count : 0;
        }

        bool empty() const noexcept {
            return size() == 0;
        }

    private:
        tc_value* value_ = nullptr;
    };

    list_ref as_list() noexcept {
        return list_ref(value_);
    }

    trent_view::list_view as_list() const noexcept {
        return view().as_list();
    }

    dict_ref as_dict() noexcept {
        return dict_ref(value_);
    }

    trent_view::dict_view as_dict() const noexcept {
        return view().as_dict();
    }

private:
    void push_back_raw(tc_value value) noexcept {
        if (!value_) {
            tc_value_free(&value);
            return;
        }
        if (value_->type != TC_VALUE_LIST) {
            reset(tc_value_list_new());
        }
        tc_value_list_push(value_, value);
    }

    void set_raw(const char* key, tc_value value) noexcept {
        if (!value_ || !key) {
            tc_value_free(&value);
            return;
        }
        if (value_->type != TC_VALUE_DICT) {
            reset(tc_value_dict_new());
        }
        tc_value_dict_set(value_, key, value);
    }

    tc_value* value_ = nullptr;
};

class trent {
public:
    using type = trent_type;

    trent() noexcept
        : value_(tc_value_nil()) {}

    explicit trent(tc_value value) noexcept
        : value_(value) {}

    trent(std::nullptr_t) noexcept
        : value_(tc_value_nil()) {}

    trent(bool value) noexcept
        : value_(tc_value_bool(value)) {}

    trent(int value) noexcept
        : value_(tc_value_int(value)) {}

    trent(int64_t value) noexcept
        : value_(tc_value_int(value)) {}

    trent(float value) noexcept
        : value_(tc_value_float(value)) {}

    trent(double value) noexcept
        : value_(tc_value_double(value)) {}

    trent(const char* value) noexcept
        : value_(tc_value_string(value)) {}

    trent(const std::string& value) noexcept
        : value_(tc_value_string(value.c_str())) {}

    ~trent() {
        tc_value_free(&value_);
    }

    trent(const trent& other)
        : value_(tc_value_copy(other.raw())) {}

    trent(trent&& other) noexcept
        : value_(other.release()) {}

    trent& operator=(const trent& other) {
        if (this == &other) {
            return *this;
        }
        reset(tc_value_copy(other.raw()));
        return *this;
    }

    trent& operator=(trent&& other) noexcept {
        if (this == &other) {
            return *this;
        }
        reset(other.release());
        return *this;
    }

    trent& operator=(trent_view other) noexcept {
        reset(tc_value_copy(other.raw()));
        return *this;
    }

    trent& operator=(std::nullptr_t) noexcept { reset(tc_value_nil()); return *this; }
    trent& operator=(bool value) noexcept { reset(tc_value_bool(value)); return *this; }
    trent& operator=(int value) noexcept { reset(tc_value_int(value)); return *this; }
    trent& operator=(int64_t value) noexcept { reset(tc_value_int(value)); return *this; }
    trent& operator=(float value) noexcept { reset(tc_value_float(value)); return *this; }
    trent& operator=(double value) noexcept { reset(tc_value_double(value)); return *this; }
    trent& operator=(const char* value) noexcept { reset(tc_value_string(value)); return *this; }
    trent& operator=(const std::string& value) noexcept { reset(tc_value_string(value.c_str())); return *this; }

    static trent adopt(tc_value value) noexcept {
        return trent(value);
    }

    static trent copy_of(const tc_value* value) {
        return trent(tc_value_copy(value));
    }

    static trent copy_of(const tc_value& value) {
        return copy_of(&value);
    }

    static trent nil() noexcept {
        return trent();
    }

    static trent boolean(bool value) noexcept {
        return trent(value);
    }

    static trent integer(int64_t value) noexcept {
        return trent(value);
    }

    static trent numer(double value) noexcept {
        return trent(value);
    }

    static trent string(const char* value) noexcept {
        return trent(value);
    }

    static trent string(const std::string& value) noexcept {
        return trent(value);
    }

    static trent list() noexcept {
        return trent(tc_value_list_new());
    }

    static trent dict() noexcept {
        return trent(tc_value_dict_new());
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

    trent_view view() const noexcept {
        return trent_view(value_);
    }

    trent_ref ref() noexcept {
        return trent_ref(&value_);
    }

    operator trent_view() const noexcept {
        return view();
    }

    tc_value_type raw_type() const noexcept { return view().raw_type(); }
    trent_type get_type() const noexcept { return view().type(); }
    trent_type type_value() const noexcept { return view().type(); }
    bool is_nil() const noexcept { return view().is_nil(); }
    bool is_bool() const noexcept { return view().is_bool(); }
    bool is_numer() const noexcept { return view().is_numer(); }
    bool is_integer() const noexcept { return view().is_integer(); }
    bool is_string() const noexcept { return view().is_string(); }
    bool is_list() const noexcept { return view().is_list(); }
    bool is_dict() const noexcept { return view().is_dict(); }
    bool as_bool(bool fallback = false) const noexcept { return view().as_bool(fallback); }
    int64_t as_integer(int64_t fallback = 0) const noexcept { return view().as_integer(fallback); }
    double as_numer(double fallback = 0.0) const noexcept { return view().as_numer(fallback); }
    const char* as_c_str(const char* fallback = "") const noexcept { return view().as_c_str(fallback); }
    std::string as_string(std::string fallback = {}) const { return view().as_string(std::move(fallback)); }
    std::size_t size() const noexcept { return view().size(); }
    bool contains(const char* key) const noexcept { return view().contains(key); }
    bool contains(const std::string& key) const noexcept { return view().contains(key); }

    tc_value release() noexcept {
        tc_value released = value_;
        value_ = tc_value_nil();
        return released;
    }

    void reset(tc_value value = tc_value_nil()) noexcept {
        tc_value_free(&value_);
        value_ = value;
    }

    void init(trent_type type) noexcept {
        ref().init(type);
    }

    void swap(trent& other) noexcept {
        using std::swap;
        swap(value_, other.value_);
    }

    trent_view get(const char* key) const noexcept { return view().get(key); }
    trent_view get(const std::string& key) const noexcept { return view().get(key); }
    trent_view dict_get(const char* key) const noexcept { return view().dict_get(key); }
    trent_view dict_get(const std::string& key) const noexcept { return view().dict_get(key); }
    trent_view _get(const char* key) const noexcept { return view()._get(key); }
    trent_view _get(const std::string& key) const noexcept { return view()._get(key); }
    trent_ref operator[](const char* key) noexcept { return ref()[key]; }
    trent_ref operator[](const std::string& key) noexcept { return ref()[key]; }
    trent_view operator[](const char* key) const noexcept { return view()[key]; }
    trent_view operator[](const std::string& key) const noexcept { return view()[key]; }
    trent_ref at(std::size_t index) noexcept { return ref().at(index); }
    trent_view at(std::size_t index) const noexcept { return view().at(index); }
    trent_ref list_at(std::size_t index) noexcept { return ref().list_at(index); }
    trent_view list_at(std::size_t index) const noexcept { return view().list_at(index); }
    trent_ref operator[](std::size_t index) noexcept { return ref()[index]; }
    trent_view operator[](std::size_t index) const noexcept { return view()[index]; }
    trent_ref operator[](int index) noexcept { return ref()[index]; }
    trent_view operator[](int index) const noexcept { return view()[index]; }

    void push_back(trent&& value) noexcept { ref().push_back(std::move(value)); }
    void push_back(const trent& value) noexcept { ref().push_back(value); }
    void push_back(trent_view value) noexcept { ref().push_back(value); }
    void push_back(bool value) noexcept { ref().push_back(value); }
    void push_back(int value) noexcept { ref().push_back(value); }
    void push_back(int64_t value) noexcept { ref().push_back(value); }
    void push_back(float value) noexcept { ref().push_back(value); }
    void push_back(double value) noexcept { ref().push_back(value); }
    void push_back(const char* value) noexcept { ref().push_back(value); }
    void push_back(const std::string& value) noexcept { ref().push_back(value); }

    void set(const char* key, trent&& value) noexcept { ref().set(key, std::move(value)); }
    void set(const char* key, const trent& value) noexcept { ref().set(key, value); }
    void set(const char* key, trent_view value) noexcept { ref().set(key, value); }
    void set(const std::string& key, trent&& value) noexcept { ref().set(key, std::move(value)); }
    void set(const std::string& key, const trent& value) noexcept { ref().set(key, value); }
    void set(const std::string& key, trent_view value) noexcept { ref().set(key, value); }

    trent_ref::list_ref as_list() noexcept { return ref().as_list(); }
    trent_view::list_view as_list() const noexcept { return view().as_list(); }
    trent_ref::dict_ref as_dict() noexcept { return ref().as_dict(); }
    trent_view::dict_view as_dict() const noexcept { return view().as_dict(); }

private:
    tc_value value_;
};

inline trent_ref& trent_ref::operator=(const trent& other) noexcept {
    reset(tc_value_copy(other.raw()));
    return *this;
}

inline trent_view trent_dict_entry_view::view() const noexcept {
    return trent_view(value);
}

inline trent_ref trent_dict_entry_ref::ref() const noexcept {
    return trent_ref(value);
}

inline trent_view trent_dict_entry_ref::view() const noexcept {
    return trent_view(value);
}

inline trent_ref& trent_ref::operator=(trent&& other) noexcept {
    reset(other.release());
    return *this;
}

inline void trent_ref::push_back(trent&& value) noexcept {
    push_back_raw(value.release());
}

inline void trent_ref::push_back(const trent& value) noexcept {
    push_back_raw(tc_value_copy(value.raw()));
}

inline void trent_ref::set(const char* key, trent&& value) noexcept {
    set_raw(key, value.release());
}

inline void trent_ref::set(const char* key, const trent& value) noexcept {
    set_raw(key, tc_value_copy(value.raw()));
}

inline void swap(trent& lhs, trent& rhs) noexcept {
    lhs.swap(rhs);
}

} // namespace tc
