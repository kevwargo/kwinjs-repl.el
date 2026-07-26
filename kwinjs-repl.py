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
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path
from tempfile import NamedTemporaryFile

from dbus_next import BusType
from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError
from dbus_next.service import ServiceInterface, method

logging.basicConfig(
    filename=Path("~/.cache/kwinjs-repl.log").expanduser(),
    level=logging.DEBUG,
    format="%(asctime)s [%(process)d] %(levelname)7s | %(message)s",
)

EVALUATOR = Path(__file__).parent / "evaluator.js"


class KWinJSRepl(ServiceInterface):
    NAME = "org.kevwargo.kwinjsrepl"
    PROMPT = "KWin JS #> "

    def __init__(self):
        super().__init__(self.NAME)
        self.bus: MessageBus | None = None

        self.stdout_queue = asyncio.Queue()
        self.expr_queue = asyncio.Queue()
        self.stdin_transport: asyncio.ReadTransport | None = None

        self._at_prompt = False
        self._shutting_down = False

    async def run(self):
        self.register_signals()
        try:
            await self.register_dbus()
            await asyncio.gather(self.stdin_loop(), self.stdout_loop())
        except asyncio.CancelledError:
            pass
        finally:
            await self.cleanup()

    def register_signals(self):
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            asyncio.get_running_loop().add_signal_handler(sig, self.stop_stdin)

    async def register_dbus(self):
        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
        self.bus.export("/", self)
        await self.bus.request_name(self.NAME)
        logging.info(f"D-Bus service {self.NAME} is running")

    async def stdin_loop(self):
        script_body = f"const DBUS_NAME = {self.NAME!r};\n" + EVALUATOR.read_text()
        async with self.script_running(script_body):
            async for expr in self.read_stdin():
                self._at_prompt = False
                await self.expr_queue.put(expr)
                logging.info(f"Read {expr!r} stdin -> queue")

            self.stdout_queue.shutdown(immediate=True)
            self.expr_queue.shutdown(immediate=True)

        logging.info("End of stdin loop")

    async def stdout_loop(self):
        async with stdout_writer() as writer:
            while True:
                try:
                    data = await self.stdout_queue.get()
                except asyncio.queues.QueueShutDown as e:
                    logging.info(f"stdout_queue shutdown: {e}")
                    break

                writer.write(data.encode("utf-8", errors="replace"))
                await writer.drain()

        logging.info("End of stdout loop")

    async def read_stdin(self):
        async with self.stdin_reader() as reader:
            while True:
                line = await reader.readline()
                try:
                    expr = json.loads(line)
                except json.JSONDecodeError:
                    expr = line.decode().strip()

                if not line or expr in ("exit;", "quit;"):
                    logging.debug(f"stdin: final line:{line} expr:{expr!r}")
                    break

                logging.debug(f"stdin: yielding line:{line} expr:{expr!r}")
                yield expr

    @asynccontextmanager
    async def stdin_reader(self) -> asyncio.StreamReader:
        reader = asyncio.StreamReader()
        self.stdin_transport, _ = await asyncio.get_running_loop().connect_read_pipe(
            partial(asyncio.StreamReaderProtocol, reader), sys.stdin
        )
        try:
            yield reader
        finally:
            self.stdin_transport.close()

    @asynccontextmanager
    async def script_running(self, body: str):
        scripting = await self.get_iface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting")
        with NamedTemporaryFile(mode="w+", prefix="kwinjs-repl-", suffix=".js") as f:
            f.write(body)
            f.flush()

            script_id = await scripting.call_load_script(f.name)
            if script_id < 0:
                raise RuntimeError(f"loadScript returned {script_id}")

            iface = await self.get_script_iface(script_id)
            logging.info(f"Loaded script {script_id} as {iface}")
            await iface.call_run()
            logging.info(f"Executed script {script_id}")

        try:
            yield
        finally:
            await iface.call_stop()

    def write_stdout(self, data: str, newline=True):
        self.stdout_queue.put_nowait(data + "\n" if newline else data)

    def write_prompt(self):
        self.write_stdout(self.PROMPT, False)
        self._at_prompt = True

    async def get_iface(self, service: str, path: str, interface: str):
        introspection = await self.bus.introspect(service, path)
        obj = self.bus.get_proxy_object(service, path, introspection)
        return obj.get_interface(interface)

    async def get_script_iface(self, script_id: int):
        for path in (
            "/Scripting/Script{script_id}",  # Plasma 6 style
            "/{script_id}",  # Plasma 5 style
        ):
            try:
                return await self.get_iface(
                    "org.kde.KWin", path.format(script_id=script_id), "org.kde.kwin.Script"
                )
            except DBusError:
                pass

        raise RuntimeError(f"DBus interface for script {script_id} not found")

    def stop_stdin(self, sig=None):
        logging.info(f"Stopping REPL stdin (signal: {sig})")

        if self.stdin_transport:
            self.stdin_transport.close()

    async def cleanup(self):
        logging.info("Cleanup")

        if self.bus:
            try:
                logging.debug("Releasing DBus name")
                await self.bus.release_name(self.NAME)
            except Exception as e:
                logging.warning(f"{type(e).__name__}({e}) when releasing D-Bus name {self.NAME}")

            try:
                logging.debug("Disconnecting from DBus")
                self.bus.disconnect()
            except Exception as e:
                logging.warning(f"{type(e).__name__}({e}) when disconnecting from D-Bus")

    @method()
    def Prompt(self):
        self.write_prompt()

    @method()
    async def WatchExpr(self) -> "s":  # noqa:F821
        try:
            expr = await asyncio.wait_for(self.expr_queue.get(), 15)
            if expr is None:
                logging.info("Sending terminal message from WatchExpr")
                expr = "<QUIT>"
            else:
                logging.info(f"Sending {expr!r} from WatchExpr")

            return expr
        except asyncio.TimeoutError:
            return ""
        except asyncio.queues.QueueShutDown as e:
            logging.info(f"expr_queue shutdown: {e}")
            return "<QUIT>"

    @method()
    def Reply(self, value: "s"):  # noqa:F821
        try:
            value = json.dumps(json.loads(value), indent=2, sort_keys=True)
        except Exception:
            pass

        if self._at_prompt:
            self.write_stdout("\n" + value)
            self.write_prompt()
        else:
            self.write_stdout(value)


@asynccontextmanager
async def stdout_writer() -> asyncio.StreamWriter:
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(transport, protocol, None, loop)

    try:
        yield writer
    finally:
        transport.close()


if __name__ == "__main__":
    asyncio.run(KWinJSRepl().run())
