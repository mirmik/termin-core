# termin-dispatch

`termin-dispatch` — маленький независимый модуль отложенного исполнения для
application composition. Он позволяет произвольным producer-потокам публиковать
работу, но сам не создаёт потоков и не выбирает, где эта работа должна
исполняться. Callback исполняется только явным вызовом `drain` /
`run_pending`, на потоке вызывающей стороны.

Модуль не является scheduler-ом движка, event loop, UI host или job system.
Termin-приложения не подключают его автоматически. Владелец приложения сам
решает, где хранить dispatcher и в какой фазе своего цикла его обслуживать.

Связанные документы:

- [Language-neutral deferred dispatcher](../../docs/architecture/2026-07-24-language-neutral-deferred-dispatcher.md)
- [No owner-thread restrictions](../../docs/architecture/2026-07-24-no-owner-thread-restrictions.md)
- [Module Map](../../docs/modules.md#termin-dispatch)

## C ABI

Канонический контракт находится в
`termin/dispatch/dispatcher.h`. Минимальный цикл:

```c
tc_dispatcher* dispatcher = tc_dispatcher_create();
tc_dispatch_ticket ticket;

if (!tc_dispatcher_post(
        dispatcher, callback, dispose_payload, payload, &ticket)) {
    dispose_payload(payload); /* ownership was not transferred */
}

tc_dispatch_stats stats =
    tc_dispatcher_drain(dispatcher, TC_DISPATCH_ALL);

tc_dispatcher_close(dispatcher);
tc_dispatcher_destroy(dispatcher);
```

Успешный `post` передаёт dispatcher-у владение `user_data`. Если задан
`dispose`, он вызывается ровно один раз: после callback, успешной отмены,
discard или уничтожения dispatcher-а. Неуспешный `post` владение не принимает.

Tickets содержат slot и generation. Поэтому старый ticket не может отменить
новую задачу, случайно занявшую тот же slot.

## C++ API

`termin/dispatch/dispatcher.hpp` предоставляет move-only
`termin::Dispatcher`, `defer(std::function<void()>)` и лёгкий
`termin::DeferredCall` для явной отмены:

```cpp
termin::Dispatcher dispatcher;
termin::DeferredCall call = dispatcher.defer([] {
    refresh_preview();
});

dispatcher.drain();
```

Исключение из callback не покидает C ABI: оно логируется и учитывается в
`DispatchStats::failed`, а оставшаяся часть batch продолжает исполняться.

## Python API

```python
from termin.dispatch import Dispatcher

dispatcher = Dispatcher()
call = dispatcher.defer(refresh_preview)

# В выбранной приложением фазе цикла:
stats = dispatcher.run_pending()
```

Python binding освобождает GIL на время `run_pending`. Каждый Python callback и
его финализация захватывают GIL локально, поэтому `defer`, `cancel` и
`run_pending` могут вызываться разными Python-потоками. Это не превращает
Termin в многопоточное приложение: dispatcher начнёт участвовать в конкретной
программе только после явной композиции со стороны этой программы.

## Batch и concurrency semantics

- `post`, `cancel`, `close` и queries можно вызывать конкурентно;
- конкурентные внешние `drain` сериализуются;
- рекурсивный `drain` из callback немедленно возвращает `busy=true`;
- `TC_DISPATCH_ALL` означает снимок очереди в начале drain;
- работа, опубликованная callback-ом, остаётся до следующего drain;
- `close` запрещает новые публикации, но не выбрасывает уже принятые;
- `discard_pending` не затрагивает callback, который уже исполняется;
- `destroy` нельзя вызывать конкурентно с другими API-вызовами.

Последний пункт — lifetime-контракт C handle, а не thread affinity: внешнее
владение самим handle должно переживать все операции над ним.
