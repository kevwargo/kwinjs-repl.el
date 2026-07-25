// const DBUS_NAME = ...

function reply(obj) {
  callDBus(DBUS_NAME, "/", DBUS_NAME, "LogJSON", JSON.stringify(obj));
}

function log(msg) {
  print(`[EVALUATOR] ${msg}`);
}

function intro(obj) {
  const data = {};

  [
    ...Object.keys(obj),
    ...Object.getOwnPropertyNames(obj),
    ...Object.getOwnPropertyNames(Object.getPrototypeOf(obj)),
  ].forEach((k) => {
    try {
      if (!data[k]) {
        data[k] = typeof obj[k];
      }
    } catch (e) {}
  });

  return data;
}

const globalEval = eval;

function watchExpr() {
  callDBus(DBUS_NAME, "/", DBUS_NAME, "WatchExpr", (expr) => {
    try {
      if (typeof expr === "string" && expr) {
        log(`Evaluating ${JSON.stringify(expr)}`);
        try {
          const res = globalEval(expr);
          reply({ res });
        } catch (ee) {
          reply({ evalError: `${ee}` });
        }
      }
    } catch (e) {
      log(`ERROR: ${e}`);
    }

    watchExpr();
  });
}

log(`Started watching for code at ${DBUS_NAME} ...`);
watchExpr();
