// const DBUS_NAME = ...

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

function prompt() {
  callDBus(DBUS_NAME, "/", DBUS_NAME, "Prompt", () => {
    log("Calling watchExpr after prompt");
    watchExpr();
  });
}

function watchExpr() {
  callDBus(DBUS_NAME, "/", DBUS_NAME, "WatchExpr", (expr) => {
    try {
      log(`expr:${expr} type:${typeof expr}`);

      if (expr === "<QUIT>") {
        log("Received terminal message, finishing watchExpr loop");
      } else if (expr) {
        log(`Evaluating ${JSON.stringify(expr)}`);
        let res, msg;
        try {
          res = globalEval(expr);
          try {
            msg = serialize(res);
            reply(msg);
          } catch (se) {
            reply(`stringifying: ${se}`);
          }
        } catch (ee) {
          reply(`evalling: ${ee}`);
        }
      } else {
        log("Ignoring empty input, restarting watch call");
        watchExpr();
      }
    } catch (e) {
      log(`ERROR: ${e}`);
    }
  });
}

function reply(msg) {
  callDBus(DBUS_NAME, "/", DBUS_NAME, "Reply", msg, prompt);
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
