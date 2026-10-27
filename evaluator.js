// const DBUS_NAME = ...

function wlist(all) {
  const ws = workspace.windowList();
  return all ? ws : ws.filter((w) => w.normalWindow);
}

function log(msg, level) {
  const logFn =
    (level === "warning" ? console.warn : console[level]) ?? console.info;
  const ms = new Date().toISOString().substring(19, 23);
  logFn(`[EVALUATOR ${ms}] ${msg}`);
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

function runAfter(delay, callback) {
  return startTimer(delay, callback, true);
}

function runEvery(delay, callback) {
  return startTimer(delay, callback, false);
}

function reply(msg, callback) {
  try {
    msg = serialize(msg);
  } catch (err) {
    msg = `serialize(): ${err}`;
  }

  callDBus(DBUS_NAME, "/", DBUS_NAME, "Reply", msg, callback);
}

function serialize(obj) {
  switch (typeof obj) {
    case "function":
    case "undefined":
      return `${obj}`;
    default:
      return JSON.stringify(uncycle(obj));
  }
}

function id(v) {
  return refs.get(v);
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

const dbusWatcher = {
  prompt() {
    callDBus(DBUS_NAME, "/", DBUS_NAME, "Prompt", () => {
      log("Calling dbusWatcher.watch after prompt");
      this.watch();
    });
  },
  watch() {
    callDBus(DBUS_NAME, "/", DBUS_NAME, "WatchExpr", (expr) => {
      try {
        if (expr === "<QUIT>") {
          log("Received terminal message, finishing dbusWatcher loop");
        } else if (expr) {
          reply(this.evalExpr(expr), () => this.prompt());
        } else {
          log("Ignoring empty input, restarting watch call", "debug");
          this.watch();
        }
      } catch (e) {
        log(`${e}`, "error");
      }
    });
  },
  evalExpr(expr) {
    log(`Evaluating ${JSON.stringify(expr)}`, "debug");

    try {
      return globalEval(expr);
    } catch (ee) {
      return `eval(): ${ee}`;
    }
  },
};

const refs = {
  wm: new WeakMap(),
  counter: 0,

  get(v) {
    if (typeof v !== "object" || v === null) return `${v}`;

    if (!this.wm.has(v)) {
      this.wm.set(v, ++this.counter);
    }

    const type = v instanceof Array ? "arr" : "obj";

    return `${type}#${this.wm.get(v)}(${v})`;
  },
};

const startTimer = (delay, callback, singleShot) => {
  const t = new QTimer();

  t.interval = delay;
  t.singleShot = singleShot;
  t.timerType = 0;
  t.timeout.connect(callback);
  t.start();

  return {
    cancel() {
      t.stop();
    },
  };
};

log("Requesting initial prompt");
dbusWatcher.prompt();
