function log(msg) {
  callDBus("<DBUS>", "/", "<DBUS>", "Log", `${msg}`);
}

function jlog(obj) {
  callDBus("<DBUS>", "/", "<DBUS>", "LogJSON", JSON.stringify(obj));
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

try {
  ("{<BODY>}");
} catch (e) {
  log(e);
} finally {
  callDBus("<DBUS>", "/", "<DBUS>", "Done");
}
