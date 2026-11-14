// anti_debug_bypass.js — 绕过常见反调试（ptrace / TracerPid / debug flag）
Java.perform(function () {
  function log(m) { console.log('[antidebug] ' + m); }
  // android.os.Debug.isDebuggerConnected / waitForDebugger
  try {
    var Debug = Java.use('android.os.Debug');
    Debug.isDebuggerConnected.implementation = function () { log('isDebuggerConnected -> false'); return false; };
    if (Debug.waitForDebugger) {
      Debug.waitForDebugger.implementation = function () { log('waitForDebugger skipped'); };
    }
  } catch (e) {}
  // ActivityThread 的 debug 标志
  try {
    var AT = Java.use('android.app.ActivityThread');
    AT.currentActivityThread.implementation = function () {
      var t = this.currentActivityThread();
      try { t.mDebug.value = false; } catch (e) {}
      return t;
    };
  } catch (e) {}
  // /proc/self/status TracerPid 读取
  try {
    var Files = Java.use('java.nio.file.Files');
    Files.readAllLines.implementation = function (p, cs) {
      var r = this.readAllLines(p, cs);
      try {
        var s = p.toString();
        if (s.indexOf('/proc/self/status') >= 0) {
          var out = Java.use('java.util.ArrayList').$new();
          for (var i = 0; i < r.size(); i++) {
            var line = r.get(i);
            out.add(line.indexOf('TracerPid') >= 0 ? 'TracerPid:\t0' : line);
          }
          log('TracerPid patched'); return out;
        }
      } catch (e) {}
      return r;
    };
  } catch (e) {}
  log('loaded');
});
