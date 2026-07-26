// const DBUS_NAME = ...

function log(msg) {
  print(`[EVALUATOR] ${msg}`);
}

function intro(obj) {
  const attrTypes = {};

  [
    ...Object.keys(obj),
    ...Object.getOwnPropertyNames(obj),
    ...Object.getOwnPropertyNames(Object.getPrototypeOf(obj)),
  ].forEach((k) => {
    try {
      if (!attrTypes[k]) {
        attrTypes[k] = typeof obj[k];
      }
    } catch (e) {}
  });

  return attrTypes;
}

const globalEval = eval;

function prompt() {
  callDBus(DBUS_NAME, "/", DBUS_NAME, "Prompt", () => {
    log("Calling watchExpr after prompt");
    watchExpr();
  });
}

function watchExpr() {
  callDBus(DBUS_NAME, "/", DBUS_NAME, "WatchExpr", (expr) => {
    try {
      if (expr === "<QUIT>") {
        log("Received terminal message, finishing watchExpr loop");
      } else if (expr) {
        reply(evalDBusExpr(expr), prompt);
      } else {
        log("Ignoring empty input, restarting watch call");
        watchExpr();
      }
    } catch (e) {
      log(`ERROR: ${e}`);
    }
  });
}

function evalDBusExpr(expr) {
  log(`Evaluating ${JSON.stringify(expr)}`);

  try {
    let res = globalEval(expr);
    try {
      return serialize(res);
    } catch (se) {
      return `serialize(): ${se}`;
    }
  } catch (ee) {
    return `eval(): ${ee}`;
  }
}

function reply(msg, callback) {
  callDBus(DBUS_NAME, "/", DBUS_NAME, "Reply", msg, callback);
}

function serialize(obj) {
  switch (typeof obj) {
    case "function":
    case "undefined":
    case "null":
      return `${obj}`;
    default:
      return JSON.stringify(obj);
  }
}

log("Requesting initial prompt");
prompt();
