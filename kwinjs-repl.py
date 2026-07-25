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
from dbus_next.errors import DBusError
from dbus_next.service import ServiceInterface, method

logging.basicConfig(
    filename=Path("~/.cache/kwinjs-repl.log").expanduser(),
    level=logging.INFO,
    format="%(asctime)s %(levelname)7s | %(message)s",
)

SCRIPT_TEMPLATE = Path(__file__).parent / "script-template.js"
EVALUATOR = Path(__file__).parent / "evaluator.js"


class KWinJSRepl(ServiceInterface):
    NAME = "org.kevwargo.kwinjsrepl"

    def __init__(self):
        super().__init__(self.NAME)
        self.bus: MessageBus | None = None
        self._shutting_down = False
        self._stdin_reader: asyncio.ReadTransport | None = None
        self._script_iface: ProxyInterface | None = None
        self._callback_event = asyncio.Event()
        self._stdout_queue = asyncio.Queue()
        self._stdout_task: asyncio.Task | None = None
        self._detected_kwin_script_path: str | None = None

        self._new = "--new" in sys.argv[1:]
        self._expr_queue = asyncio.Queue()

    @cached_property
    def loop(self):
        return asyncio.get_running_loop()

    async def run(self):
        logging.info(f"Executed with {sys.argv[1:]}")

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

        if self._new:
            await self._long_script(reader)
        else:
            await self._singleshot_loop(reader)

    async def _long_script(self, reader: asyncio.StreamReader):
        script_body = f"const DBUS_NAME = {self.NAME!r};\n" + EVALUATOR.read_text()
        await self._run_kwinjs_script(script_body)
        if not self._script_iface:
            return

        async for expr in self._read_expressions(reader):
            await self._expr_queue.put(expr)
            logging.info(f"Queued {expr!r}")

    async def _read_expressions(self, reader: asyncio.StreamReader):
        while True:
            logging.info("printing prompt")
            self.write_stdout("KWin JS #> ", False)
            line = await reader.readline()
            try:
                expr = json.loads(line)
            except json.JSONDecodeError:
                expr = line.decode().strip()

            if not line or expr in ("exit;", "quit;"):
                logging.info(f"received terminal message {line!r}, stopping")
                break

            yield expr

    async def _singleshot_loop(self, reader: asyncio.StreamReader):
        async for expr in self._read_expressions(reader):
            try:
                await self._run_singleshot_script(expr)
                await self._callback_event.wait()
            except Exception as e:
                e = f"{type(e).__name__}({e})"
                logging.exception(f"Exception when running script: {e}")
                self.write_stdout(e)
            finally:
                self._callback_event.clear()

    async def _run_singleshot_script(self, body: str):
        try:
            await self._run_kwinjs_script(
                SCRIPT_TEMPLATE.read_text()
                .replace("<DBUS>", self.NAME)
                .replace('("{<BODY>}");', body)
            )
        finally:
            try:
                await self._script_iface.call_stop()
            finally:
                self._script_iface = None

    async def _run_kwinjs_script(self, body: str):
        scripting = await self.get_iface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting")
        with NamedTemporaryFile(mode="w+", prefix="kwinjs-repl-", suffix=".js") as f:
            f.write(body)
            f.flush()

            script_id = await scripting.call_load_script(f.name)
            if script_id < 0:
                raise RuntimeError(f"loadScript returned {script_id}")

            self._script_iface = await self.get_script_iface(script_id)
            logging.info(f"Loaded script {script_id} as {self._script_iface}")
            if self._script_iface:
                await self._script_iface.call_run()

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

    async def get_iface(self, service: str, path: str, interface: str):
        introspection = await self.bus.introspect(service, path)
        obj = self.bus.get_proxy_object(service, path, introspection)
        return obj.get_interface(interface)

    async def get_script_iface(self, script_id: int):
        svc, iface = "org.kde.KWin", "org.kde.kwin.Script"
        if self._detected_kwin_script_path:
            return await self.get_iface(
                svc, self._detected_kwin_script_path.format(script_id=script_id), iface
            )

        last_exception = None
        for path in (
            "/Scripting/Script{script_id}",  # Plasma 6 style
            "/{script_id}",  # Plasma 5 style
        ):
            try:
                script = await self.get_iface(
                    "org.kde.KWin", path.format(script_id=script_id), "org.kde.kwin.Script"
                )
            except DBusError as e:
                last_exception = e
            else:
                self._detected_kwin_script_path = path
                logging.info(f"Found script {script_id} iface {script} at {path}")

                return script

        raise last_exception

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

        if self._script_iface:
            try:
                await self._script_iface.call_stop()
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

        logging.info(f"Writing {value!r} to stdout")
        self.write_stdout(value)

    @method()
    def Done(self):
        self._callback_event.set()

    @method()
    async def WatchExpr(self) -> "s":  # noqa:F821
        logging.debug("Received WatchExpr call")
        try:
            expr = await asyncio.wait_for(self._expr_queue.get(), 5)
        except asyncio.TimeoutError:
            logging.debug("No expression in the queue, repeating ...")
            return ""

        logging.info(f"Returning {expr!r} from WatchExpr")

        return expr


if __name__ == "__main__":
    asyncio.run(KWinJSRepl().run())
