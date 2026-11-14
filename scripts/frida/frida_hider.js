// frida_hider.js — 隐藏常见 Frida 痕迹（端口/线程名/内存特征）
Java.perform(function () {
  function log(m) { console.log('[hider] ' + m); }
  // 隐藏线程名
  try {
    var Thread = Java.use('java.lang.Thread');
    Thread.getName.implementation = function () {
      var n = this.getName();
      return /gum-js-loop|gmain|gdbus|frida/i.test(n) ? 'main' : n;
    };
  } catch (e) {}
  // /proc/net/tcp 里的 27042/27043 端口（读文件时过滤）
  try {
    var Files = Java.use('java.nio.file.Files');
    Files.readAllLines.implementation = function (p, cs) {
      var r = this.readAllLines(p, cs);
      try {
        var s = p.toString();
        if (s.indexOf('/proc/net/tcp') >= 0) {
          var out = Java.use('java.util.ArrayList').$new();
          for (var i = 0; i < r.size(); i++) {
            var line = r.get(i);
            // 27043 = 0x6993, 27042 = 0x6992
            if (/\b699[23]\b/.test(line)) { log('hide frida port line'); continue; }
            out.add(line);
          }
          return out;
        }
      } catch (e) {}
      return r;
    };
  } catch (e) {}
  // maps 里的 frida agent 字符串
  try {
    var BufferedReader = Java.use('java.io.BufferedReader');
  } catch (e) {}
  log('loaded');
});
