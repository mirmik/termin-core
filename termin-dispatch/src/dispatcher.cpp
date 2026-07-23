#include "termin/dispatch/dispatcher.hpp"

#include "tcbase/tc_log.h"

#include <algorithm>
#include <exception>
#include <iterator>
#include <list>
#include <mutex>
#include <new>
#include <string>
#include <vector>

namespace {

enum class SlotState {
    Free,
    Queued,
    Executing,
};

struct QueuedTicket {
    uint32_t slot = 0;
    uint32_t generation = 0;
};

struct DispatchSlot {
    uint32_t generation = 0;
    SlotState state = SlotState::Free;
    tc_dispatch_callback callback = nullptr;
    tc_dispatch_dispose dispose = nullptr;
    void* user_data = nullptr;
    std::list<QueuedTicket>::iterator queue_position;
};

struct DispatchWork {
    tc_dispatch_ticket ticket = tc_dispatch_ticket_invalid();
    tc_dispatch_callback callback = nullptr;
    tc_dispatch_dispose dispose = nullptr;
    void* user_data = nullptr;
};

void log_dispatch_error(const char* operation, const char* message) {
    tc_log_error("[termin-dispatch] %s failed: %s", operation, message);
}

void dispose_payload(tc_dispatch_dispose dispose, void* user_data) noexcept {
    if (!dispose) {
        return;
    }
    try {
        dispose(user_data);
    } catch (const std::exception& error) {
        log_dispatch_error("payload disposal", error.what());
    } catch (...) {
        log_dispatch_error("payload disposal", "unknown exception");
    }
}

} // namespace

struct tc_dispatcher {
    mutable std::mutex mutex;
    std::recursive_mutex drain_mutex;
    bool draining = false;
    bool open = true;
    size_t queued_count = 0;
    std::vector<DispatchSlot> slots{DispatchSlot{}};
    std::vector<uint32_t> free_slots;
    std::list<QueuedTicket> queue;

    tc_dispatch_ticket allocate_locked(
        tc_dispatch_callback callback,
        tc_dispatch_dispose dispose,
        void* user_data
    ) {
        uint32_t slot_index = 0;
        if (!free_slots.empty()) {
            slot_index = free_slots.back();
            free_slots.pop_back();
        } else {
            slot_index = static_cast<uint32_t>(slots.size());
            slots.emplace_back();
        }

        DispatchSlot& slot = slots[slot_index];
        ++slot.generation;
        if (slot.generation == 0) {
            ++slot.generation;
        }
        const tc_dispatch_ticket ticket{slot_index, slot.generation};
        try {
            queue.push_back(QueuedTicket{ticket.slot, ticket.generation});
        } catch (...) {
            free_slots.push_back(slot_index);
            throw;
        }

        slot.state = SlotState::Queued;
        slot.callback = callback;
        slot.dispose = dispose;
        slot.user_data = user_data;
        slot.queue_position = std::prev(queue.end());
        ++queued_count;
        return ticket;
    }

    DispatchSlot* find_locked(tc_dispatch_ticket ticket) {
        if (ticket.slot == 0 || ticket.slot >= slots.size()) {
            return nullptr;
        }
        DispatchSlot& slot = slots[ticket.slot];
        if (slot.generation != ticket.generation) {
            return nullptr;
        }
        return &slot;
    }

    void release_locked(uint32_t slot_index) {
        DispatchSlot& slot = slots[slot_index];
        slot.state = SlotState::Free;
        slot.callback = nullptr;
        slot.dispose = nullptr;
        slot.user_data = nullptr;
        free_slots.push_back(slot_index);
    }
};

extern "C" {

tc_dispatch_ticket tc_dispatch_ticket_invalid(void) {
    return tc_dispatch_ticket{0, 0};
}

bool tc_dispatch_ticket_is_valid(tc_dispatch_ticket ticket) {
    return ticket.slot != 0 && ticket.generation != 0;
}

tc_dispatcher* tc_dispatcher_create(void) {
    try {
        return new tc_dispatcher();
    } catch (const std::exception& error) {
        log_dispatch_error("create", error.what());
    } catch (...) {
        log_dispatch_error("create", "unknown exception");
    }
    return nullptr;
}

bool tc_dispatcher_post(
    tc_dispatcher* dispatcher,
    tc_dispatch_callback callback,
    tc_dispatch_dispose dispose,
    void* user_data,
    tc_dispatch_ticket* out_ticket
) {
    if (out_ticket) {
        *out_ticket = tc_dispatch_ticket_invalid();
    }
    if (!dispatcher || !callback) {
        log_dispatch_error("post", "dispatcher and callback are required");
        return false;
    }
    try {
        std::lock_guard lock(dispatcher->mutex);
        if (!dispatcher->open) {
            return false;
        }
        const tc_dispatch_ticket ticket =
            dispatcher->allocate_locked(callback, dispose, user_data);
        if (out_ticket) {
            *out_ticket = ticket;
        }
        return true;
    } catch (const std::exception& error) {
        log_dispatch_error("post", error.what());
    } catch (...) {
        log_dispatch_error("post", "unknown exception");
    }
    return false;
}

bool tc_dispatcher_cancel(tc_dispatcher* dispatcher, tc_dispatch_ticket ticket) {
    if (!dispatcher || !tc_dispatch_ticket_is_valid(ticket)) {
        return false;
    }

    tc_dispatch_dispose dispose = nullptr;
    void* user_data = nullptr;
    {
        std::lock_guard lock(dispatcher->mutex);
        DispatchSlot* slot = dispatcher->find_locked(ticket);
        if (!slot || slot->state != SlotState::Queued) {
            return false;
        }
        dispose = slot->dispose;
        user_data = slot->user_data;
        dispatcher->queue.erase(slot->queue_position);
        --dispatcher->queued_count;
        dispatcher->release_locked(ticket.slot);
    }
    dispose_payload(dispose, user_data);
    return true;
}

tc_dispatch_stats tc_dispatcher_drain(tc_dispatcher* dispatcher, size_t limit) {
    tc_dispatch_stats stats{};
    if (!dispatcher || limit == 0) {
        if (dispatcher) {
            stats.remaining = tc_dispatcher_pending_count(dispatcher);
        }
        return stats;
    }

    try {
        std::lock_guard drain_lock(dispatcher->drain_mutex);
        {
            std::lock_guard lock(dispatcher->mutex);
            if (dispatcher->draining) {
                stats.busy = true;
                stats.remaining = dispatcher->queued_count;
                return stats;
            }
            dispatcher->draining = true;
        }

        struct DrainGuard {
            tc_dispatcher* dispatcher;
            ~DrainGuard() {
                std::lock_guard lock(dispatcher->mutex);
                dispatcher->draining = false;
            }
        } drain_guard{dispatcher};

        std::vector<DispatchWork> batch;
        {
            std::lock_guard lock(dispatcher->mutex);
            const size_t batch_limit =
                limit == TC_DISPATCH_ALL
                    ? dispatcher->queued_count
                    : std::min(limit, dispatcher->queued_count);
            batch.reserve(batch_limit);
            while (!dispatcher->queue.empty() && batch.size() < batch_limit) {
                const QueuedTicket queued = dispatcher->queue.front();
                dispatcher->queue.pop_front();
                const tc_dispatch_ticket ticket{queued.slot, queued.generation};
                DispatchSlot* slot = dispatcher->find_locked(ticket);
                if (!slot || slot->state != SlotState::Queued) {
                    continue;
                }
                slot->state = SlotState::Executing;
                --dispatcher->queued_count;
                batch.push_back(
                    DispatchWork{ticket, slot->callback, slot->dispose, slot->user_data}
                );
            }
        }

        for (const DispatchWork& work : batch) {
            tc_dispatch_callback_result result = TC_DISPATCH_CALLBACK_FAILED;
            try {
                result = work.callback(work.user_data);
            } catch (const std::exception& error) {
                log_dispatch_error("callback", error.what());
            } catch (...) {
                log_dispatch_error("callback", "unknown exception");
            }

            ++stats.executed;
            if (result != TC_DISPATCH_CALLBACK_OK) {
                ++stats.failed;
            }

            {
                std::lock_guard lock(dispatcher->mutex);
                DispatchSlot* slot = dispatcher->find_locked(work.ticket);
                if (!slot || slot->state != SlotState::Executing) {
                    log_dispatch_error(
                        "callback completion",
                        "executing slot lost its lifetime state"
                    );
                    stats.internal_error = true;
                } else {
                    dispatcher->release_locked(work.ticket.slot);
                }
            }
            dispose_payload(work.dispose, work.user_data);
        }

        stats.remaining = tc_dispatcher_pending_count(dispatcher);
        return stats;
    } catch (const std::exception& error) {
        log_dispatch_error("drain", error.what());
    } catch (...) {
        log_dispatch_error("drain", "unknown exception");
    }
    stats.internal_error = true;
    stats.remaining = tc_dispatcher_pending_count(dispatcher);
    return stats;
}

bool tc_dispatcher_close(tc_dispatcher* dispatcher) {
    if (!dispatcher) {
        return false;
    }
    std::lock_guard lock(dispatcher->mutex);
    const bool changed = dispatcher->open;
    dispatcher->open = false;
    return changed;
}

size_t tc_dispatcher_discard_pending(tc_dispatcher* dispatcher) {
    if (!dispatcher) {
        return 0;
    }

    std::vector<std::pair<tc_dispatch_dispose, void*>> payloads;
    try {
        {
            std::lock_guard lock(dispatcher->mutex);
            payloads.reserve(dispatcher->queued_count);
            for (uint32_t index = 1; index < dispatcher->slots.size(); ++index) {
                const DispatchSlot& slot = dispatcher->slots[index];
                if (slot.state != SlotState::Queued) {
                    continue;
                }
                payloads.emplace_back(slot.dispose, slot.user_data);
            }
            for (uint32_t index = 1; index < dispatcher->slots.size(); ++index) {
                DispatchSlot& slot = dispatcher->slots[index];
                if (slot.state != SlotState::Queued) {
                    continue;
                }
                dispatcher->release_locked(index);
            }
            dispatcher->queued_count = 0;
            dispatcher->queue.clear();
        }
    } catch (const std::exception& error) {
        log_dispatch_error("discard_pending", error.what());
        return 0;
    } catch (...) {
        log_dispatch_error("discard_pending", "unknown exception");
        return 0;
    }

    for (const auto& [dispose, user_data] : payloads) {
        dispose_payload(dispose, user_data);
    }
    return payloads.size();
}

bool tc_dispatcher_is_open(const tc_dispatcher* dispatcher) {
    if (!dispatcher) {
        return false;
    }
    std::lock_guard lock(dispatcher->mutex);
    return dispatcher->open;
}

size_t tc_dispatcher_pending_count(const tc_dispatcher* dispatcher) {
    if (!dispatcher) {
        return 0;
    }
    std::lock_guard lock(dispatcher->mutex);
    return dispatcher->queued_count;
}

void tc_dispatcher_destroy(tc_dispatcher* dispatcher) {
    if (!dispatcher) {
        return;
    }
    tc_dispatcher_close(dispatcher);
    {
        std::lock_guard drain_lock(dispatcher->drain_mutex);
        tc_dispatcher_discard_pending(dispatcher);
    }
    delete dispatcher;
}

} // extern "C"

namespace termin::dispatch_detail {

struct DispatcherState {
    DispatcherState() : native(tc_dispatcher_create()) {
        if (!native) {
            throw std::bad_alloc();
        }
    }

    ~DispatcherState() {
        tc_dispatcher_destroy(native);
    }

    tc_dispatcher* native = nullptr;
};

} // namespace termin::dispatch_detail

namespace {

struct CppCallbackPayload {
    std::function<void()> callback;
};

tc_dispatch_callback_result invoke_cpp_callback(void* user_data) {
    auto* payload = static_cast<CppCallbackPayload*>(user_data);
    try {
        payload->callback();
        return TC_DISPATCH_CALLBACK_OK;
    } catch (const std::exception& error) {
        tc_log_error("[termin-dispatch/cpp] deferred callback failed: %s", error.what());
    } catch (...) {
        tc_log_error("[termin-dispatch/cpp] deferred callback failed: unknown exception");
    }
    return TC_DISPATCH_CALLBACK_FAILED;
}

void dispose_cpp_callback(void* user_data) {
    delete static_cast<CppCallbackPayload*>(user_data);
}

} // namespace

namespace termin {

bool DeferredCall::cancel() const {
    const std::shared_ptr<dispatch_detail::DispatcherState> state = state_.lock();
    return state && tc_dispatcher_cancel(state->native, ticket_);
}

Dispatcher::Dispatcher()
    : state_(std::make_shared<dispatch_detail::DispatcherState>()) {}

DeferredCall Dispatcher::defer(std::function<void()> callback) {
    if (!callback) {
        tc_log_error("[termin-dispatch/cpp] cannot defer an empty callback");
        return {};
    }
    auto* payload = new CppCallbackPayload{std::move(callback)};
    DeferredCall call = post(
        &invoke_cpp_callback,
        &dispose_cpp_callback,
        payload
    );
    if (!call) {
        delete payload;
    }
    return call;
}

DeferredCall Dispatcher::post(
    tc_dispatch_callback callback,
    tc_dispatch_dispose dispose,
    void* user_data
) {
    if (!state_) {
        return {};
    }
    tc_dispatch_ticket ticket = tc_dispatch_ticket_invalid();
    if (!tc_dispatcher_post(
            state_->native,
            callback,
            dispose,
            user_data,
            &ticket
        )) {
        return {};
    }
    return DeferredCall(state_, ticket);
}

DispatchStats Dispatcher::drain(size_t limit) {
    if (!state_) {
        return {};
    }
    return tc_dispatcher_drain(state_->native, limit);
}

bool Dispatcher::close() {
    return state_ && tc_dispatcher_close(state_->native);
}

size_t Dispatcher::discard_pending() {
    return state_ ? tc_dispatcher_discard_pending(state_->native) : 0;
}

bool Dispatcher::is_open() const {
    return state_ && tc_dispatcher_is_open(state_->native);
}

size_t Dispatcher::pending_count() const {
    return state_ ? tc_dispatcher_pending_count(state_->native) : 0;
}

} // namespace termin
