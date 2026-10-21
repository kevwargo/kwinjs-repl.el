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

if (!Object.fromEntries) {
  Object.defineProperty(Object, "fromEntries", {
    value(entries) {
      const obj = {};
      entries.forEach(([k, v]) => {
        obj[k] = v;
      });
      return obj;
    },
    writable: true,
    configurable: true,
  });
}

Object.defineProperties(Object, {
  filter: {
    value(obj, pred) {
      return Object.fromEntries(
        Object.entries(obj).filter(([k, v]) => pred(k, v)),
      );
    },
    writable: true,
    configurable: true,
  },
  merge: {
    value(...objs) {
      return Object.assign({}, ...objs);
    },
    writable: true,
    configurable: true,
  },
});

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
      return JSON.stringify(uncycle(obj));
  }
}

class ObjectRefs {
  constructor() {
    this.wm = new WeakMap();
    this.counter = 0;
  }

  ref(v) {
    if (typeof v !== "object") return `${v}`;

    if (!this.wm.has(v)) {
      this.wm.set(v, ++this.counter);
    }

    const type = v instanceof Array ? "arr" : "obj";

    return `${type}#${this.wm.get(v)}(${v})`;
  }
}

R = new ObjectRefs();

function id(v) {
  return R.ref(v);
}

function uncycle(obj, visited) {
  if (typeof obj !== "object" || obj === null) return obj;
  const isArray = obj instanceof Array;

  if (isArray) {
    return obj.map((v) => uncycle(v, visited));
  }

  for (const v of visited ?? []) {
    if (v.orig === obj) {
      v.copy["#id"] = id(obj);
      return id(obj);
    }
  }

  const copy = {};

  Object.keys(obj).forEach((k) => {
    copy[k] = uncycle(obj[k], [{ orig: obj, copy }, ...(visited ?? [])]);
  });

  return copy;
}

log("Requesting initial prompt");
prompt();
