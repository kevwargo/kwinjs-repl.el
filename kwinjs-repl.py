#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "dbus-next>=0.2.3",
# ]
# ///

import asyncio
import json
import logging
import signal
import sys
from functools import cached_property
from pathlib import Path
from tempfile import NamedTemporaryFile

from dbus_next import BusType
from dbus_next.aio import MessageBus
from dbus_next.aio.proxy_object import ProxyInterface
from dbus_next.service import ServiceInterface, method

logger = logging.getLogger("kwinctl")
logging.basicConfig(
    filename=Path("~/kwinjs-repl.log").expanduser(),
    level=logging.DEBUG,
    format="[%(levelname)s] %(asctime)s %(message)s",
)

SCRIPT_TEMPLATE = Path(__file__).parent / "script-template.js"


class KWinJSRepl(ServiceInterface):
    NAME = "org.kevwargo.kwinjsrepl"

    def __init__(self):
        super().__init__(self.NAME)
        self.bus: MessageBus | None = None
        self._shutting_down = False
        self._stdin_reader: asyncio.ReadTransport | None = None
        self._script: ProxyInterface | None = None
        self._callback_event = asyncio.Event()
        self._stdout_queue = asyncio.Queue()
        self._stdout_task: asyncio.Task | None = None

    @cached_property
    def loop(self):
        return asyncio.get_running_loop()

    async def run(self):
        self.register_signals()
        try:
            await self.register_dbus()
            self._stdout_task = self.loop.create_task(self.stdout_loop())
            await self.stdin_loop()
        finally:
            await self.shutdown()

    def register_signals(self):
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            self.loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.shutdown(s)))

    async def register_dbus(self):
        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self.bus.export("/", self)
        await self.bus.request_name(self.NAME)
        logging.info(f"D-Bus service {self.NAME} is running")

    async def stdin_loop(self):
        reader = asyncio.StreamReader()
        proto = asyncio.StreamReaderProtocol(reader)
        self._stdin_reader, _ = await self.loop.connect_read_pipe(lambda: proto, sys.stdin)

        logging.debug(f"Started main loop reading from {self._stdin_reader}")

        while True:
            self.write_stdout("KWin JS #> ", False)
            line = await reader.readline()
            if not line or (body := json.loads(line)) in ("exit;", "quit;"):
                logging.info(f"received terminal message {line!r}, stopping")
                break

            try:
                await self.run_script(body)
                await self._callback_event.wait()
            except Exception as e:
                e = f"{type(e).__name__}({e})"
                logging.error(f"Exception when running script: {e}")
                self.write_stdout(e)
            finally:
                self._callback_event.clear()

    async def stdout_loop(self):
        writer, proto = await self.loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        while True:
            data = await self._stdout_queue.get()
            if data is None:
                break

            writer.write(data.encode("utf-8", errors="replace"))
            await proto._drain_helper()

    def write_stdout(self, data: str, newline=True):
        self._stdout_queue.put_nowait(data + "\n" if newline else data)

    async def run_script(self, body: str):
        scripting = await self.get_iface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting")
        with NamedTemporaryFile(mode="w+", prefix="kwinjs-repl-", suffix=".js") as f:
            f.write(
                SCRIPT_TEMPLATE.read_text()
                .replace("<DBUS>", self.NAME)
                .replace('("{<BODY>}");', body)
            )
            f.flush()

            script_id = await scripting.call_load_script(f.name)
            if script_id < 0:
                raise RuntimeError(f"loadScript returned {script_id}")

            self._script = await self.get_iface(
                "org.kde.KWin", f"/Scripting/Script{script_id}", "org.kde.kwin.Script"
            )
            try:
                await self._script.call_run()
            finally:
                try:
                    await self._script.call_stop()
                finally:
                    self._script = None

    async def get_iface(self, service: str, path: str, interface: str):
        introspection = await self.bus.introspect(service, path)
        obj = self.bus.get_proxy_object(service, path, introspection)
        return obj.get_interface(interface)

    async def shutdown(self, sig=None):
        if self._shutting_down:
            return
        self._shutting_down = True

        if sig:
            logging.info(f"Caught sig={sig}, shutting down")
        else:
            logging.info("Shutting down")

        if self._stdin_reader:
            self._stdin_reader.close()

        if self._script:
            try:
                await self._script.call_stop()
            except Exception as e:
                logging.warning(f"{type(e).__name__}({e}) when stopping leftover script")

        self._stdout_queue.put_nowait(None)
        if self._stdout_task:
            self._stdout_task.cancel()
            try:
                await self._stdout_task
            except asyncio.CancelledError:
                pass

        if self.bus:
            try:
                await self.bus.release_name(self.NAME)
            except Exception as e:
                logging.warning(f"{type(e).__name__}({e}) when releasing D-Bus name {self.NAME}")

            try:
                self.bus.disconnect()
            except Exception as e:
                logging.warning(f"{type(e).__name__}({e}) when disconnecting from D-Bus")

    @method()
    def Log(self, value: "s"):  # noqa:F821
        self.write_stdout(value)

    @method()
    def LogJSON(self, value: "s"):  # noqa:F821
        try:
            value = json.dumps(json.loads(value), indent=2, sort_keys=True)
        except Exception:
            pass
        self.write_stdout(value)

    @method()
    def Done(self):
        self._callback_event.set()


if __name__ == "__main__":
    asyncio.run(KWinJSRepl().run())
