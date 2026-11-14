// root_bypass.js — 常见 root 检测伪装（不保证全部）
Java.perform(function () {
  function log(m) { console.log('[root] ' + m); }
  // 文件存在性检测：su / magisk 路径返回 false
  try {
    var File = Java.use('java.io.File');
    File.exists.implementation = function () {
      var p = this.getAbsolutePath();
      if (/(^|\/)(su|magisk|busybox|supersu)(\/|$)/i.test(p) || p.indexOf('/system/xbin/su') >= 0) {
        log('hide root path: ' + p); return false;
      }
      return this.exists();
    };
  } catch (e) {}
  // Build.TAGS 含 test-keys 检测
  try {
    var Build = Java.use('android.os.Build');
    var tags = Build.TAGS;
  } catch (e) {}
  log('loaded');
});
