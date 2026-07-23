#pragma once

#include "termin/dispatch/dispatcher.h"

#include <functional>
#include <memory>
#include <utility>

namespace termin {

using DispatchStats = tc_dispatch_stats;

namespace dispatch_detail {
struct DispatcherState;
}

class DeferredCall {
public:
    DeferredCall() = default;

    bool cancel() const;
    tc_dispatch_ticket ticket() const noexcept { return ticket_; }
    explicit operator bool() const noexcept {
        return tc_dispatch_ticket_is_valid(ticket_);
    }

private:
    friend class Dispatcher;
    DeferredCall(
        std::weak_ptr<dispatch_detail::DispatcherState> state,
        tc_dispatch_ticket ticket
    ) : state_(std::move(state)), ticket_(ticket) {}

    std::weak_ptr<dispatch_detail::DispatcherState> state_;
    tc_dispatch_ticket ticket_ = tc_dispatch_ticket_invalid();
};

class Dispatcher {
public:
    Dispatcher();
    ~Dispatcher() = default;

    Dispatcher(const Dispatcher&) = delete;
    Dispatcher& operator=(const Dispatcher&) = delete;
    Dispatcher(Dispatcher&&) noexcept = default;
    Dispatcher& operator=(Dispatcher&&) noexcept = default;

    DeferredCall defer(std::function<void()> callback);
    DeferredCall post(
        tc_dispatch_callback callback,
        tc_dispatch_dispose dispose,
        void* user_data
    );

    DispatchStats drain(size_t limit = TC_DISPATCH_ALL);
    bool close();
    size_t discard_pending();
    bool is_open() const;
    size_t pending_count() const;

private:
    std::shared_ptr<dispatch_detail::DispatcherState> state_;
};

} // namespace termin
