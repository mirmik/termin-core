#include "termin/dispatch/dispatcher.hpp"

#include <cassert>

int main() {
    termin::Dispatcher dispatcher;
    int value = 0;
    assert(dispatcher.defer([&] { ++value; }));
    const termin::DispatchStats stats = dispatcher.drain();
    assert(stats.executed == 1);
    assert(value == 1);
    return 0;
}
