#include "termin/dispatch/dispatcher.hpp"

#include <atomic>
#include <cassert>
#include <stdexcept>
#include <thread>
#include <vector>

namespace {

struct RacePayload {
    std::atomic<int>* callbacks;
    std::atomic<int>* disposals;
};

tc_dispatch_callback_result invoke_race_payload(void* user_data) {
    auto* payload = static_cast<RacePayload*>(user_data);
    payload->callbacks->fetch_add(1, std::memory_order_relaxed);
    return TC_DISPATCH_CALLBACK_OK;
}

void dispose_race_payload(void* user_data) {
    auto* payload = static_cast<RacePayload*>(user_data);
    payload->disposals->fetch_add(1, std::memory_order_relaxed);
    delete payload;
}

} // namespace

int main() {
    termin::Dispatcher dispatcher;
    std::atomic<int> executed{0};

    constexpr int producer_count = 8;
    constexpr int work_per_producer = 250;
    std::vector<std::thread> producers;
    for (int producer = 0; producer < producer_count; ++producer) {
        producers.emplace_back([&] {
            for (int index = 0; index < work_per_producer; ++index) {
                const termin::DeferredCall call = dispatcher.defer([&] {
                    executed.fetch_add(1, std::memory_order_relaxed);
                });
                assert(call);
            }
        });
    }
    for (std::thread& producer : producers) {
        producer.join();
    }
    assert(dispatcher.pending_count() == producer_count * work_per_producer);

    std::atomic<size_t> drained{0};
    std::thread first_drain([&] {
        drained.fetch_add(
            dispatcher.drain(700).executed,
            std::memory_order_relaxed
        );
    });
    std::thread second_drain([&] {
        drained.fetch_add(
            dispatcher.drain(700).executed,
            std::memory_order_relaxed
        );
    });
    first_drain.join();
    second_drain.join();
    drained.fetch_add(
        dispatcher.drain().executed,
        std::memory_order_relaxed
    );
    assert(drained == producer_count * work_per_producer);
    assert(executed == producer_count * work_per_producer);

    termin::DeferredCall stale = dispatcher.defer([] {});
    assert(stale.cancel());
    termin::DeferredCall reused = dispatcher.defer([] {});
    assert(reused);
    assert(!stale.cancel());
    assert(reused.cancel());

    for (int index = 0; index < 10000; ++index) {
        termin::DeferredCall cancelled = dispatcher.defer([] {});
        assert(cancelled.cancel());
    }
    assert(dispatcher.pending_count() == 0);

    for (int iteration = 0; iteration < 100; ++iteration) {
        std::atomic<int> callbacks{0};
        std::atomic<int> disposals{0};
        std::atomic<bool> start{false};
        termin::DeferredCall raced = dispatcher.post(
            &invoke_race_payload,
            &dispose_race_payload,
            new RacePayload{&callbacks, &disposals}
        );
        assert(raced);

        std::thread canceller([&] {
            while (!start.load(std::memory_order_acquire)) {
            }
            raced.cancel();
        });
        std::thread drainer([&] {
            while (!start.load(std::memory_order_acquire)) {
            }
            dispatcher.drain(1);
        });
        start.store(true, std::memory_order_release);
        canceller.join();
        drainer.join();

        assert(callbacks.load(std::memory_order_relaxed) <= 1);
        assert(disposals.load(std::memory_order_relaxed) == 1);
    }

    int after_failure = 0;
    assert(dispatcher.defer([] {
        throw std::runtime_error("expected test failure");
    }));
    assert(dispatcher.defer([&] { ++after_failure; }));
    const termin::DispatchStats failure_stats = dispatcher.drain();
    assert(failure_stats.executed == 2);
    assert(failure_stats.failed == 1);
    assert(after_failure == 1);

    return 0;
}
