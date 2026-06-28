// tc_runtime_type_registry.hpp - C++ wrapper for domain-agnostic runtime types.
#pragma once

#include "inspect/tc_runtime_type_registry.h"

#include <cstdint>
#include <string>
#include <vector>

#ifdef _WIN32
    #ifdef TERMIN_INSPECT_CPP_EXPORTS
        #define TC_RUNTIME_TYPE_API __declspec(dllexport)
    #else
        #define TC_RUNTIME_TYPE_API __declspec(dllimport)
    #endif
#else
    #define TC_RUNTIME_TYPE_API __attribute__((visibility("default")))
#endif

namespace tc {

struct RuntimeTypeRecordInfo {
    std::string name;
    std::string owner;
    std::string parent;
    uint64_t generation = 0;
    std::vector<std::string> facets;
};

class TC_RUNTIME_TYPE_API RuntimeTypeRegistry {
public:
    static RuntimeTypeRegistry& instance();

    void set_registration_owner(const std::string& owner);
    std::string registration_owner() const;

    bool has_type(const std::string& type_name) const;
    bool ensure_type(const std::string& type_name);
    void unregister_type(const std::string& type_name);
    size_t unregister_owner(const std::string& owner);

    bool set_owner(
        const std::string& type_name,
        const std::string& owner,
        bool allow_existing_unowned
    );
    std::string owner_of(const std::string& type_name) const;
    std::vector<std::string> list_owned(const std::string& owner) const;

    bool set_parent(const std::string& type_name, const std::string& parent_name);
    std::string parent_of(const std::string& type_name) const;

    bool set_facet(
        const std::string& type_name,
        const std::string& facet_id,
        void* payload,
        tc_runtime_type_facet_destroy_fn destroy,
        uint32_t abi_version
    );
    void* facet(const std::string& type_name, const std::string& facet_id) const;
    bool remove_facet(const std::string& type_name, const std::string& facet_id);
    bool has_facet(const std::string& type_name, const std::string& facet_id) const;

    std::vector<std::string> types() const;
    std::vector<std::string> facet_ids(const std::string& type_name) const;
    bool info(const std::string& type_name, RuntimeTypeRecordInfo& out_info) const;

    void clear();
};

} // namespace tc
