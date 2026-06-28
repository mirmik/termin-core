#include "inspect/tc_runtime_type_registry.hpp"

#include <tcbase/tc_log.h>

#include <algorithm>
#include <unordered_map>

namespace tc {
namespace {

struct RuntimeTypeFacet {
    void* payload = nullptr;
    tc_runtime_type_facet_destroy_fn destroy = nullptr;
    uint32_t abi_version = 0;
};

struct RuntimeTypeRecord {
    std::string name;
    std::string owner;
    std::string parent;
    uint64_t generation = 1;
    std::unordered_map<std::string, RuntimeTypeFacet> facets;
};

class RuntimeTypeRegistryStorage {
public:
    std::unordered_map<std::string, RuntimeTypeRecord> records;
    std::string current_owner;

    RuntimeTypeRecord& ensure(const std::string& type_name) {
        auto [it, inserted] = records.try_emplace(type_name);
        RuntimeTypeRecord& record = it->second;
        if (inserted) {
            record.name = type_name;
            record.owner = current_owner;
        }
        return record;
    }

    void destroy_facet(RuntimeTypeFacet& facet) {
        if (facet.destroy && facet.payload) {
            facet.destroy(facet.payload);
        }
        facet.payload = nullptr;
        facet.destroy = nullptr;
        facet.abi_version = 0;
    }

    void destroy_record(RuntimeTypeRecord& record) {
        for (auto& [_, facet] : record.facets) {
            destroy_facet(facet);
        }
        record.facets.clear();
    }
};

RuntimeTypeRegistryStorage& storage() {
    static RuntimeTypeRegistryStorage s;
    return s;
}

std::vector<std::string> sorted_record_names() {
    std::vector<std::string> names;
    names.reserve(storage().records.size());
    for (const auto& [name, _] : storage().records) {
        names.push_back(name);
    }
    std::sort(names.begin(), names.end());
    return names;
}

std::vector<std::string>& type_name_cache() {
    static std::vector<std::string> cache;
    return cache;
}

std::vector<std::string>& facet_id_cache() {
    static std::vector<std::string> cache;
    return cache;
}

} // namespace

RuntimeTypeRegistry& RuntimeTypeRegistry::instance() {
    static RuntimeTypeRegistry registry;
    return registry;
}

void RuntimeTypeRegistry::set_registration_owner(const std::string& owner) {
    storage().current_owner = owner;
}

std::string RuntimeTypeRegistry::registration_owner() const {
    return storage().current_owner;
}

bool RuntimeTypeRegistry::has_type(const std::string& type_name) const {
    return storage().records.find(type_name) != storage().records.end();
}

bool RuntimeTypeRegistry::ensure_type(const std::string& type_name) {
    if (type_name.empty()) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] cannot create unnamed runtime type");
        return false;
    }
    storage().ensure(type_name);
    return true;
}

void RuntimeTypeRegistry::unregister_type(const std::string& type_name) {
    auto it = storage().records.find(type_name);
    if (it == storage().records.end()) {
        return;
    }
    storage().destroy_record(it->second);
    storage().records.erase(it);
}

size_t RuntimeTypeRegistry::unregister_owner(const std::string& owner) {
    if (owner.empty()) {
        return 0;
    }

    std::vector<std::string> pending;
    for (const auto& [name, record] : storage().records) {
        if (record.owner == owner) {
            pending.push_back(name);
        }
    }

    for (const std::string& name : pending) {
        unregister_type(name);
    }
    return pending.size();
}

bool RuntimeTypeRegistry::set_owner(
    const std::string& type_name,
    const std::string& owner,
    bool allow_existing_unowned
) {
    if (type_name.empty()) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] cannot set owner for unnamed runtime type");
        return false;
    }
    if (owner.empty()) {
        return true;
    }

    auto it = storage().records.find(type_name);
    if (it == storage().records.end()) {
        RuntimeTypeRecord record;
        record.name = type_name;
        record.owner = owner;
        storage().records.emplace(type_name, std::move(record));
        return true;
    }

    RuntimeTypeRecord& record = it->second;
    if (record.owner.empty()) {
        if (!allow_existing_unowned) {
            return false;
        }
        record.owner = owner;
        record.generation++;
        return true;
    }
    if (record.owner == owner) {
        return true;
    }

    tc_log(
        TC_LOG_WARN,
        "[RuntimeTypeRegistry] owner conflict for type '%s': existing='%s' incoming='%s'",
        type_name.c_str(),
        record.owner.c_str(),
        owner.c_str()
    );
    return false;
}

std::string RuntimeTypeRegistry::owner_of(const std::string& type_name) const {
    auto it = storage().records.find(type_name);
    return it != storage().records.end() ? it->second.owner : "";
}

std::vector<std::string> RuntimeTypeRegistry::list_owned(const std::string& owner) const {
    std::vector<std::string> result;
    if (owner.empty()) {
        return result;
    }
    for (const auto& [name, record] : storage().records) {
        if (record.owner == owner) {
            result.push_back(name);
        }
    }
    std::sort(result.begin(), result.end());
    return result;
}

bool RuntimeTypeRegistry::set_parent(
    const std::string& type_name,
    const std::string& parent_name
) {
    if (type_name.empty()) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] cannot set parent for unnamed runtime type");
        return false;
    }

    RuntimeTypeRecord& record = storage().ensure(type_name);
    if (record.parent == parent_name) {
        return true;
    }
    record.parent = parent_name;
    record.generation++;
    return true;
}

std::string RuntimeTypeRegistry::parent_of(const std::string& type_name) const {
    auto it = storage().records.find(type_name);
    return it != storage().records.end() ? it->second.parent : "";
}

bool RuntimeTypeRegistry::set_facet(
    const std::string& type_name,
    const std::string& facet_id,
    void* payload,
    tc_runtime_type_facet_destroy_fn destroy,
    uint32_t abi_version
) {
    if (type_name.empty() || facet_id.empty()) {
        tc_log(TC_LOG_ERROR, "[RuntimeTypeRegistry] cannot set unnamed facet or type");
        return false;
    }

    RuntimeTypeRecord& record = storage().ensure(type_name);
    RuntimeTypeFacet& facet = record.facets[facet_id];
    storage().destroy_facet(facet);
    facet.payload = payload;
    facet.destroy = destroy;
    facet.abi_version = abi_version;
    record.generation++;
    return true;
}

void* RuntimeTypeRegistry::facet(
    const std::string& type_name,
    const std::string& facet_id
) const {
    auto record_it = storage().records.find(type_name);
    if (record_it == storage().records.end()) {
        return nullptr;
    }
    auto facet_it = record_it->second.facets.find(facet_id);
    return facet_it != record_it->second.facets.end() ? facet_it->second.payload : nullptr;
}

bool RuntimeTypeRegistry::remove_facet(
    const std::string& type_name,
    const std::string& facet_id
) {
    auto record_it = storage().records.find(type_name);
    if (record_it == storage().records.end()) {
        return false;
    }
    auto facet_it = record_it->second.facets.find(facet_id);
    if (facet_it == record_it->second.facets.end()) {
        return false;
    }
    storage().destroy_facet(facet_it->second);
    record_it->second.facets.erase(facet_it);
    record_it->second.generation++;
    return true;
}

bool RuntimeTypeRegistry::has_facet(
    const std::string& type_name,
    const std::string& facet_id
) const {
    auto record_it = storage().records.find(type_name);
    if (record_it == storage().records.end()) {
        return false;
    }
    return record_it->second.facets.find(facet_id) != record_it->second.facets.end();
}

std::vector<std::string> RuntimeTypeRegistry::types() const {
    return sorted_record_names();
}

std::vector<std::string> RuntimeTypeRegistry::facet_ids(const std::string& type_name) const {
    std::vector<std::string> ids;
    auto record_it = storage().records.find(type_name);
    if (record_it == storage().records.end()) {
        return ids;
    }
    ids.reserve(record_it->second.facets.size());
    for (const auto& [id, _] : record_it->second.facets) {
        ids.push_back(id);
    }
    std::sort(ids.begin(), ids.end());
    return ids;
}

bool RuntimeTypeRegistry::info(
    const std::string& type_name,
    RuntimeTypeRecordInfo& out_info
) const {
    auto it = storage().records.find(type_name);
    if (it == storage().records.end()) {
        return false;
    }
    out_info.name = it->second.name;
    out_info.owner = it->second.owner;
    out_info.parent = it->second.parent;
    out_info.generation = it->second.generation;
    out_info.facets = facet_ids(type_name);
    return true;
}

void RuntimeTypeRegistry::clear() {
    for (auto& [_, record] : storage().records) {
        storage().destroy_record(record);
    }
    storage().records.clear();
    storage().current_owner.clear();
}

} // namespace tc

extern "C" {

void tc_runtime_type_registry_set_registration_owner(const char* owner) {
    tc::RuntimeTypeRegistry::instance().set_registration_owner(owner ? owner : "");
}

const char* tc_runtime_type_registry_get_registration_owner(void) {
    static std::string value;
    value = tc::RuntimeTypeRegistry::instance().registration_owner();
    return value.empty() ? nullptr : value.c_str();
}

bool tc_runtime_type_registry_has_type(const char* type_name) {
    return type_name && tc::RuntimeTypeRegistry::instance().has_type(type_name);
}

bool tc_runtime_type_registry_ensure_type(const char* type_name) {
    return type_name && tc::RuntimeTypeRegistry::instance().ensure_type(type_name);
}

void tc_runtime_type_registry_unregister_type(const char* type_name) {
    if (!type_name) {
        return;
    }
    tc::RuntimeTypeRegistry::instance().unregister_type(type_name);
}

size_t tc_runtime_type_registry_unregister_owner(const char* owner) {
    return owner ? tc::RuntimeTypeRegistry::instance().unregister_owner(owner) : 0;
}

bool tc_runtime_type_registry_set_owner(
    const char* type_name,
    const char* owner,
    bool allow_existing_unowned
) {
    if (!type_name || !owner) {
        return false;
    }
    return tc::RuntimeTypeRegistry::instance().set_owner(
        type_name,
        owner,
        allow_existing_unowned
    );
}

const char* tc_runtime_type_registry_get_owner(const char* type_name) {
    static std::string value;
    if (!type_name) {
        return nullptr;
    }
    value = tc::RuntimeTypeRegistry::instance().owner_of(type_name);
    return value.empty() ? nullptr : value.c_str();
}

bool tc_runtime_type_registry_set_parent(const char* type_name, const char* parent_name) {
    if (!type_name) {
        return false;
    }
    return tc::RuntimeTypeRegistry::instance().set_parent(
        type_name,
        parent_name ? parent_name : ""
    );
}

const char* tc_runtime_type_registry_get_parent(const char* type_name) {
    static std::string value;
    if (!type_name) {
        return nullptr;
    }
    value = tc::RuntimeTypeRegistry::instance().parent_of(type_name);
    return value.empty() ? nullptr : value.c_str();
}

bool tc_runtime_type_registry_set_facet(
    const char* type_name,
    const char* facet_id,
    void* payload,
    tc_runtime_type_facet_destroy_fn destroy,
    uint32_t abi_version
) {
    if (!type_name || !facet_id) {
        return false;
    }
    return tc::RuntimeTypeRegistry::instance().set_facet(
        type_name,
        facet_id,
        payload,
        destroy,
        abi_version
    );
}

void* tc_runtime_type_registry_get_facet(const char* type_name, const char* facet_id) {
    if (!type_name || !facet_id) {
        return nullptr;
    }
    return tc::RuntimeTypeRegistry::instance().facet(type_name, facet_id);
}

bool tc_runtime_type_registry_remove_facet(const char* type_name, const char* facet_id) {
    if (!type_name || !facet_id) {
        return false;
    }
    return tc::RuntimeTypeRegistry::instance().remove_facet(type_name, facet_id);
}

bool tc_runtime_type_registry_has_facet(const char* type_name, const char* facet_id) {
    if (!type_name || !facet_id) {
        return false;
    }
    return tc::RuntimeTypeRegistry::instance().has_facet(type_name, facet_id);
}

size_t tc_runtime_type_registry_type_count(void) {
    tc::type_name_cache() = tc::RuntimeTypeRegistry::instance().types();
    return tc::type_name_cache().size();
}

const char* tc_runtime_type_registry_type_at(size_t index) {
    tc::type_name_cache() = tc::RuntimeTypeRegistry::instance().types();
    if (index >= tc::type_name_cache().size()) {
        return nullptr;
    }
    return tc::type_name_cache()[index].c_str();
}

bool tc_runtime_type_registry_get_info(
    const char* type_name,
    tc_runtime_type_record_info* out_info
) {
    if (!type_name || !out_info) {
        return false;
    }

    static tc::RuntimeTypeRecordInfo cached;
    if (!tc::RuntimeTypeRegistry::instance().info(type_name, cached)) {
        return false;
    }

    out_info->name = cached.name.c_str();
    out_info->owner = cached.owner.empty() ? nullptr : cached.owner.c_str();
    out_info->parent = cached.parent.empty() ? nullptr : cached.parent.c_str();
    out_info->generation = cached.generation;
    out_info->facet_count = cached.facets.size();
    return true;
}

size_t tc_runtime_type_registry_facet_count(const char* type_name) {
    if (!type_name) {
        return 0;
    }
    tc::facet_id_cache() = tc::RuntimeTypeRegistry::instance().facet_ids(type_name);
    return tc::facet_id_cache().size();
}

const char* tc_runtime_type_registry_facet_at(const char* type_name, size_t index) {
    if (!type_name) {
        return nullptr;
    }
    tc::facet_id_cache() = tc::RuntimeTypeRegistry::instance().facet_ids(type_name);
    if (index >= tc::facet_id_cache().size()) {
        return nullptr;
    }
    return tc::facet_id_cache()[index].c_str();
}

void tc_runtime_type_registry_clear(void) {
    tc::RuntimeTypeRegistry::instance().clear();
}

} // extern "C"
